#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD=()
PRINT_INVITE=false
NON_INTERACTIVE=false

usage() {
  cat <<'EOF'
Usage:
  ./setup.sh
  ./setup.sh --print-invite
  ./setup.sh invite
  ./setup.sh --non-interactive

Options:
  --print-invite      .env から現在の招待リンクを表示します。Docker は起動しません。
  invite              --print-invite と同じです。
  --non-interactive  将来用の非対話セットアップ入口です。現時点では必須 .env 値の確認だけ行います。
  -h, --help         このヘルプを表示します。
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --print-invite|invite)
        PRINT_INVITE=true
        ;;
      --non-interactive)
        NON_INTERACTIVE=true
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Unknown option: $1"
        ;;
    esac
    shift
  done
}

fail() {
  echo "Error: $*" >&2
  exit 1
}

has_command() {
  command -v "$1" >/dev/null 2>&1
}

detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
  elif has_command docker-compose; then
    COMPOSE_CMD=(docker-compose)
  else
    fail "Docker Compose が見つかりません。Docker Compose v2 を入れてからもう一度実行してください。"
  fi
}

prompt() {
  local label="$1"
  local default_value="$2"
  local value
  read -r -p "${label} [${default_value}]: " value
  echo "${value:-$default_value}"
}

prompt_required() {
  local label="$1"
  local value=""
  while [[ -z "${value}" ]]; do
    read -r -p "${label}: " value
  done
  echo "${value}"
}

env_quote() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "$value"
}

json_quote() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  printf '"%s"' "$value"
}

is_localhost_url() {
  [[ "$1" =~ ^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:|/|$) ]]
}

public_url_host() {
  local value="${1,,}"
  local host
  value="${value#http://}"
  value="${value#https://}"
  host="${value%%/*}"
  host="${host#*@}"
  host="${host%%:*}"
  echo "${host}"
}

is_placeholder_public_url() {
  local host
  host="$(public_url_host "$1")"
  [[ -z "${host}" || "${host}" == "example.com" || "${host}" == *.example.com || "${host}" == your-* || "${host}" == your.* || "${host}" == *placeholder* ]]
}

validate_public_url() {
  local value="$1"
  [[ "${value}" =~ ^https?://[^[:space:]]+$ ]]
}

validate_external_public_url() {
  local value="$1"
  validate_public_url "${value}" && ! is_localhost_url "${value}" && ! is_placeholder_public_url "${value}"
}

prompt_external_public_url() {
  local label="$1"
  local value=""
  while true; do
    value="$(prompt_required "${label}")"
    if ! validate_public_url "${value}"; then
      echo "http:// または https:// で始まる URL を入力してください。" >&2
      continue
    fi
    if is_localhost_url "${value}"; then
      echo "Public URL に localhost / 127.0.0.1 / 0.0.0.0 は使えません。" >&2
      echo "Cloudflare Tunnel、Nginx + HTTPS、Tailscale、または外部から到達できる URL を指定してください。" >&2
      continue
    fi
    if is_placeholder_public_url "${value}"; then
      echo "Public URL に example.com や your-* などの placeholder URL は使えません。" >&2
      echo "Cloudflare Tunnel、Nginx + HTTPS、Tailscale、または実在する外部公開 URL を指定してください。" >&2
      continue
    fi
    echo "${value%/}"
    return 0
  done
}

confirm_yes_no() {
  local question="$1"
  local default="${2:-N}"
  local answer
  read -r -p "${question} " answer
  case "${answer}" in
    y|Y|yes|YES) return 0 ;;
    n|N|no|NO) return 1 ;;
    "")
      [[ "${default}" == "Y" ]]
      return
      ;;
    *) return 1 ;;
  esac
}

read_env_value() {
  local key="$1"
  local line value

  [[ -f .env ]] || return 0
  line="$(grep -E "^[[:space:]]*(export[[:space:]]+)?${key}=" .env | tail -n 1 || true)"
  [[ -n "${line}" ]] || return 0

  line="${line#"${line%%[![:space:]]*}"}"
  line="${line#export }"
  value="${line#*=}"
  value="${value%$'\r'}"

  if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
    value="${value:1:${#value}-2}"
    value="${value//\\\"/\"}"
    value="${value//\\\\/\\}"
  elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi

  printf '%s' "${value}"
}

is_placeholder_value() {
  local value="${1,,}"
  [[ -z "${value}" || "${value}" == replace-with-* || "${value}" == *placeholder* || "${value}" == *change-this* || "${value}" == *your-server.example.com* ]]
}

append_unmanaged_env_lines() {
  [[ -f .env ]] || return 0

  awk '
    /^[[:space:]]*(export[[:space:]]+)?CATCHAT_SERVER_NAME=/ { next }
    /^[[:space:]]*(export[[:space:]]+)?CATCHAT_SERVER_PUBLIC_URL=/ { next }
    /^[[:space:]]*(export[[:space:]]+)?CATCHAT_HUB_URL=/ { next }
    /^[[:space:]]*(export[[:space:]]+)?CATCHAT_SERVER_SECRET=/ { next }
    /^[[:space:]]*(export[[:space:]]+)?CATCHAT_INVITE_CODE=/ { next }
    /^[[:space:]]*(export[[:space:]]+)?CATCHAT_PORT=/ { next }
    /^[[:space:]]*(export[[:space:]]+)?CATCHAT_SERVER_REGISTRATION_TOKEN=/ { next }
    /^[[:space:]]*#[[:space:]]*Existing custom settings preserved by setup\.sh[[:space:]]*$/ { next }
    {
      if (/^[[:space:]]*$/) {
        blank_lines = blank_lines $0 "\n"
      } else {
        if (seen) {
          printf "%s", blank_lines
        }
        blank_lines = ""
        print $0
        seen = 1
      }
    }
  ' .env
}

check_docker_access() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi

  cat >&2 <<'EOF'
Docker は見つかりましたが、現在のユーザーで利用できません。

よくある原因:
- Docker Desktop / Docker Engine が起動していない
- Linux で現在のユーザーが docker グループに入っていない
- sudo なしで Docker を使えない設定になっている

確認:
  docker info
  sudo docker info

Linux での一般的な対処:
  sudo systemctl start docker
  sudo usermod -aG docker $USER

docker グループに追加した後は、ログアウトしてログインし直してください。
その後、もう一度 ./setup.sh を実行してください。
EOF
  exit 1
}

choose_public_url() {
  local port="$1"
  local current_public_url="${2:-}"
  local choice=""
  local public_url=""

  if [[ -n "${current_public_url}" ]]; then
    echo >&2
    echo "現在の Public URL: ${current_public_url}" >&2
    if is_localhost_url "${current_public_url}"; then
      echo "現在の Public URL は localhost 系のため使用できません。外部から到達できる URL を選び直してください。" >&2
    elif is_placeholder_public_url "${current_public_url}"; then
      echo "現在の Public URL は placeholder のため使用できません。実在する外部公開 URL を選び直してください。" >&2
    elif confirm_yes_no "この Public URL をそのまま使いますか？ [Y/n]:" "Y"; then
      echo "${current_public_url%/}"
      return 0
    fi
  fi

  echo >&2
  echo "公開方法を選んでください。" >&2
  echo "  1) Cloudflare Tunnel で簡単公開" >&2
  echo "  2) Nginx + ドメインで本番公開" >&2
  echo "  3) Tailscale で仲間内だけ公開" >&2
  echo "  4) Public URL を直接入力" >&2

  while [[ ! "${choice}" =~ ^[1-4]$ ]]; do
    read -r -p "番号 [1-4]: " choice
  done

  case "${choice}" in
    1)
      echo >&2
      if has_command cloudflared; then
        echo "cloudflared は見つかりました。別ターミナルで次を実行してください。" >&2
      else
        echo "cloudflared が見つかりません。Cloudflare Tunnel を使うには先にインストールしてください。" >&2
        echo "インストール後、別ターミナルで次を実行してください。" >&2
      fi
      echo >&2
      echo "  cloudflared tunnel --url http://localhost:${port}" >&2
      echo >&2
      echo "表示された https://xxxxx.trycloudflare.com を入力してください。" >&2
      echo "trycloudflare.com の URL は一時的です。本番では固定 Tunnel と独自ドメインを推奨します。" >&2
      public_url="$(prompt_external_public_url "Cloudflare Tunnel URL")"
      ;;
    2)
      local domain=""
      echo >&2
      domain="$(prompt_required "ドメイン名 例: chat.my-domain.com")"
      domain="${domain#http://}"
      domain="${domain#https://}"
      domain="${domain%%/*}"
      public_url="https://${domain}"
      echo >&2
      echo "CATCHAT_SERVER_PUBLIC_URL=${public_url} として保存します。" >&2
      echo "Nginx 設定例と certbot 手順は docs/nginx.md にあります。" >&2
      echo >&2
      echo "最小手順:" >&2
      echo "  sudo apt install nginx certbot python3-certbot-nginx" >&2
      echo "  sudo nginx -t && sudo systemctl reload nginx" >&2
      echo "  sudo certbot --nginx -d ${domain}" >&2
      ;;
    3)
      local ts_ip=""
      echo >&2
      if has_command tailscale; then
        ts_ip="$(tailscale ip -4 2>/dev/null | head -n 1 || true)"
      fi
      if [[ -n "${ts_ip}" ]]; then
        public_url="$(prompt "Tailscale URL" "http://${ts_ip}:${port}")"
      else
        echo "Tailscale IP を自動取得できませんでした。tailscale が起動しているか確認してください。" >&2
        public_url="$(prompt_required "Tailscale URL 例: http://100.x.y.z:${port}")"
      fi
      echo >&2
      echo "Tailscale は tailnet 内の仲間だけで使う用途に向いています。" >&2
      echo "tailnet 外のユーザーや通常の hub からは接続できない場合があります。" >&2
      ;;
    4)
      echo >&2
      public_url="$(prompt_external_public_url "Public URL")"
      ;;
  esac

  if is_localhost_url "${public_url}"; then
    fail "Public URL に localhost / 127.0.0.1 / 0.0.0.0 は使えません。"
  fi
  if is_placeholder_public_url "${public_url}"; then
    fail "Public URL に example.com や your-* などの placeholder URL は使えません。"
  fi
  echo "${public_url%/}"
}

health_check() {
  local port="$1"
  local url="http://127.0.0.1:${port}/api/server/health"

  echo
  echo "Health check: ${url}"
  for _ in $(seq 1 30); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      echo "OK: サーバーは起動しています。"
      return 0
    fi
    sleep 2
  done

  echo
  echo "NG: health check に失敗しました。直近ログ:"
  "${COMPOSE_CMD[@]}" logs --tail=80 catchat-server || true
  fail "サーバーが正常起動しませんでした。docs/troubleshooting.md を確認してください。"
}

build_legacy_invite_url() {
  local hub_url="$1"
  local public_url="$2"
  local invite_code="$3"
  local payload

  payload="$(printf '{"url":%s,"code":%s}' "$(json_quote "${public_url%/}")" "$(json_quote "${invite_code}")" | openssl base64 -A | tr '+/' '-_' | tr -d '=')"
  echo "${hub_url%/}/add-server?invite=${payload}"
}

register_hub_invite() {
  local hub_url="$1"
  local public_url="$2"
  local server_name="$3"
  local invite_code="$4"
  local registration_token="$5"
  local response json_res join_url

  if [[ -z "${registration_token}" ]]; then
    return 1
  fi

  if is_localhost_url "${public_url}"; then
    return 1
  fi

  response=$(curl -fsS -X POST \
    -H "Content-Type: application/json" \
    -d "{\"server_name\":$(json_quote "${server_name}"),\"server_public_url\":$(json_quote "${public_url%/}"),\"server_invite_code\":$(json_quote "${invite_code}"),\"registration_token\":$(json_quote "${registration_token}")}" \
    --max-time 10 \
    "${hub_url%/}/api/server-registry/register" 2>/dev/null || true)

  if [[ -z "${response}" ]]; then
    return 1
  fi

  if has_command python3; then
    join_url=$(echo "${response}" | python3 -c 'import sys, json; print(json.load(sys.stdin).get("join_url", ""))' 2>/dev/null || true)
  else
    join_url=$(echo "${response}" | grep -o '"join_url":"[^"]*' | cut -d'"' -f4 || true)
  fi

  if [[ -z "${join_url}" ]]; then
    return 1
  fi

  echo "${join_url}"
  return 0
}

print_invite_details() {
  local hub_url="$1"
  local public_url="$2"
  local server_name="$3"
  local invite_code="$4"
  local registration_token="$5"
  local is_setup_complete_flow="${6:-false}"

  local legacy_invite_url join_url
  legacy_invite_url="$(build_legacy_invite_url "${hub_url}" "${public_url}" "${invite_code}")"

  join_url=""
  if [[ -n "${registration_token}" ]] && ! is_localhost_url "${public_url}"; then
    join_url="$(register_hub_invite "${hub_url}" "${public_url}" "${server_name}" "${invite_code}" "${registration_token}" || true)"
  fi

  if [[ "${is_setup_complete_flow}" == "true" ]]; then
    echo
    echo "============================================================"
    echo "catChat Server setup complete"
    echo "============================================================"
    echo "サーバー状態: 起動中"
    echo "Local health URL: http://127.0.0.1:${port}/api/server/health"
    echo "Public URL: ${public_url}"
    echo
  fi

  if [[ -n "${join_url}" ]]; then
    echo "共通招待リンク:"
    echo "${join_url}"
    echo
    echo "互換用招待リンク:"
    echo "${legacy_invite_url}"
  else
    if [[ -z "${registration_token}" ]]; then
      echo "CATCHAT_SERVER_REGISTRATION_TOKEN が未設定のため、Hubへの共通招待リンク登録をスキップします。"
      echo
    elif ! is_localhost_url "${public_url}"; then
      echo "⚠️ Hubへの共通招待リンク登録に失敗またはスキップしたため、互換用リンクのみ表示します。"
      echo
    fi
    echo "catChat Hub への招待リンク (互換用):"
    echo "${legacy_invite_url}"
  fi

  echo
  echo "重要:"
  echo "- CATCHAT_SERVER_SECRET は招待リンクに含まれていません。"
  echo "- .env は公開しないでください。"
}

print_invite_from_env() {
  [[ -f .env ]] || fail ".env がありません。先に ./setup.sh を実行してください。"
  has_command openssl || fail "openssl が必要です。"

  local public_url hub_url invite_code port server_name registration_token
  public_url="$(read_env_value CATCHAT_SERVER_PUBLIC_URL)"
  hub_url="$(read_env_value CATCHAT_HUB_URL)"
  invite_code="$(read_env_value CATCHAT_INVITE_CODE)"
  port="$(read_env_value CATCHAT_PORT)"
  server_name="$(read_env_value CATCHAT_SERVER_NAME)"
  registration_token="$(read_env_value CATCHAT_SERVER_REGISTRATION_TOKEN)"

  [[ -n "${public_url}" ]] || fail "CATCHAT_SERVER_PUBLIC_URL が .env にありません。"
  ! is_localhost_url "${public_url}" || fail "CATCHAT_SERVER_PUBLIC_URL が localhost / 127.0.0.1 / 0.0.0.0 です。招待リンクは表示できません。外部から到達できる Public URL に変更して ./setup.sh を再実行してください。"
  ! is_placeholder_public_url "${public_url}" || fail "CATCHAT_SERVER_PUBLIC_URL が placeholder URL です。招待リンクは表示できません。Cloudflare Tunnel、Nginx + HTTPS、Tailscale、または実在する外部公開 URL に変更して ./setup.sh を再実行してください。"
  [[ -n "${hub_url}" ]] || hub_url="https://chat.dongurihub.com"
  [[ -n "${invite_code}" ]] || fail "CATCHAT_INVITE_CODE が .env にありません。"
  [[ -n "${port}" ]] || port="8100"
  [[ -n "${server_name}" ]] || server_name="My catChat Server"

  echo "Local health URL: http://127.0.0.1:${port}/api/server/health"
  echo "Public URL: ${public_url%/}"
  echo

  print_invite_details "${hub_url}" "${public_url}" "${server_name}" "${invite_code}" "${registration_token}" "false"
}

check_non_interactive_ready() {
  [[ -f .env ]] || fail "--non-interactive は現在 .env が必要です。先に .env.example をコピーして値を設定してください。"

  local missing=()
  for key in CATCHAT_SERVER_NAME CATCHAT_SERVER_PUBLIC_URL CATCHAT_HUB_URL CATCHAT_SERVER_SECRET CATCHAT_INVITE_CODE CATCHAT_PORT; do
    if is_placeholder_value "$(read_env_value "${key}")"; then
      missing+=("${key}")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    printf 'Error: --non-interactive に必要な値が不足または placeholder です:\n' >&2
    printf '  %s\n' "${missing[@]}" >&2
    exit 1
  fi

  if is_localhost_url "$(read_env_value CATCHAT_SERVER_PUBLIC_URL)"; then
    fail "--non-interactive では CATCHAT_SERVER_PUBLIC_URL に localhost / 127.0.0.1 / 0.0.0.0 は使えません。"
  fi
  if is_placeholder_public_url "$(read_env_value CATCHAT_SERVER_PUBLIC_URL)"; then
    fail "--non-interactive では CATCHAT_SERVER_PUBLIC_URL に placeholder URL は使えません。"
  fi
}

parse_args "$@"

[[ -f docker-compose.yml ]] || fail "catchat-server ディレクトリで実行してください。"

if [[ "${PRINT_INVITE}" == true ]]; then
  print_invite_from_env
  exit 0
fi

if [[ "${NON_INTERACTIVE}" == true ]]; then
  check_non_interactive_ready
fi

has_command docker || fail "Docker が見つかりません。Docker Desktop または Docker Engine をインストールしてください。"
check_docker_access
detect_compose
has_command openssl || fail "openssl が必要です。"
has_command curl || fail "curl が必要です。"

existing_env=false
if [[ -f .env ]]; then
  existing_env=true
  if [[ "${NON_INTERACTIVE}" == false ]]; then
    echo ".env が既にあります。"
    echo "既存の CATCHAT_SERVER_SECRET、CATCHAT_INVITE_CODE、CATCHAT_SERVER_REGISTRATION_TOKEN は基本的に保持します。"
    echo "今回はサーバー名、Public URL、Hub URL、ポートを更新できます。"
    if ! confirm_yes_no "続けますか？ [Y/n]:" "Y"; then
      echo "キャンセルしました。"
      exit 0
    fi
  fi
fi

existing_server_name="$(read_env_value CATCHAT_SERVER_NAME)"
existing_public_url="$(read_env_value CATCHAT_SERVER_PUBLIC_URL)"
existing_hub_url="$(read_env_value CATCHAT_HUB_URL)"
existing_server_secret="$(read_env_value CATCHAT_SERVER_SECRET)"
existing_invite_code="$(read_env_value CATCHAT_INVITE_CODE)"
existing_port="$(read_env_value CATCHAT_PORT)"
existing_registration_token="$(read_env_value CATCHAT_SERVER_REGISTRATION_TOKEN)"

if [[ "${NON_INTERACTIVE}" == true ]]; then
  server_name="${existing_server_name}"
  hub_url="${existing_hub_url}"
  port="${existing_port}"
  registration_token="${existing_registration_token}"
else
  server_name="$(prompt "サーバー名" "${existing_server_name:-My catChat Server}")"
  hub_url="$(prompt "catChat Hub URL" "${existing_hub_url:-https://chat.dongurihub.com}")"
  port="$(prompt "公開するポート" "${existing_port:-8100}")"
  if [[ -n "${existing_registration_token}" ]]; then
    registration_token="$(prompt "Hub登録トークン (Enterで既存値を保持)" "${existing_registration_token}")"
  else
    registration_token="$(prompt "Hub登録トークン (未入力で共通招待リンク登録をスキップ)" "")"
  fi
fi
[[ "${port}" =~ ^[0-9]+$ ]] || fail "ポート番号は数字で入力してください。"

if [[ "${NON_INTERACTIVE}" == true ]]; then
  public_url="${existing_public_url%/}"
  if is_localhost_url "${public_url}"; then
    fail "CATCHAT_SERVER_PUBLIC_URL に localhost / 127.0.0.1 / 0.0.0.0 は使えません。"
  fi
  if is_placeholder_public_url "${public_url}"; then
    fail "CATCHAT_SERVER_PUBLIC_URL に placeholder URL は使えません。"
  fi
else
  public_url="$(choose_public_url "${port}" "${existing_public_url}")"
fi

if [[ "${existing_env}" == true && -n "${existing_public_url}" ]]; then
  echo
  echo "現在の Public URL: ${existing_public_url}"
  echo "新しい Public URL: ${public_url}"
fi

if [[ "${existing_env}" == true ]] && ! is_placeholder_value "${existing_server_secret}"; then
  server_secret="${existing_server_secret}"
  echo "CATCHAT_SERVER_SECRET: 既存値を保持します。"
  if [[ "${NON_INTERACTIVE}" == false ]] && confirm_yes_no "CATCHAT_SERVER_SECRET を再生成しますか？既存登録が壊れる可能性があります。 [y/N]:" "N"; then
    server_secret="$(openssl rand -hex 32)"
    echo "CATCHAT_SERVER_SECRET: 再生成しました。"
  fi
else
  server_secret="$(openssl rand -hex 32)"
  echo "CATCHAT_SERVER_SECRET: 新しく生成しました。"
fi

if [[ "${existing_env}" == true ]] && ! is_placeholder_value "${existing_invite_code}"; then
  invite_code="${existing_invite_code}"
  echo "CATCHAT_INVITE_CODE: 既存値を保持します。"
  if [[ "${NON_INTERACTIVE}" == false ]] && confirm_yes_no "CATCHAT_INVITE_CODE を再生成しますか？既存の招待リンクが無効になる可能性があります。 [y/N]:" "N"; then
    invite_code="INVITE-$(openssl rand -hex 12 | tr '[:lower:]' '[:upper:]')"
    echo "CATCHAT_INVITE_CODE: 再生成しました。"
  fi
else
  invite_code="INVITE-$(openssl rand -hex 12 | tr '[:lower:]' '[:upper:]')"
  echo "CATCHAT_INVITE_CODE: 新しく生成しました。"
fi

unmanaged_env_lines="$(append_unmanaged_env_lines || true)"

cat > .env <<EOF_ENV
CATCHAT_SERVER_NAME=$(env_quote "${server_name}")
CATCHAT_SERVER_PUBLIC_URL=$(env_quote "${public_url}")
CATCHAT_HUB_URL=$(env_quote "${hub_url%/}")
CATCHAT_SERVER_SECRET=$(env_quote "${server_secret}")
CATCHAT_INVITE_CODE=$(env_quote "${invite_code}")
CATCHAT_PORT=$(env_quote "${port}")
CATCHAT_SERVER_REGISTRATION_TOKEN=$(env_quote "${registration_token}")
EOF_ENV

if [[ -n "${unmanaged_env_lines}" ]]; then
  {
    echo
    echo "# Existing custom settings preserved by setup.sh"
    printf '%s\n' "${unmanaged_env_lines}"
  } >> .env
fi

mkdir -p data uploads

echo
echo "Docker Compose で起動します..."
"${COMPOSE_CMD[@]}" up -d --build

health_check "${port}"

registration_token="$(read_env_value CATCHAT_SERVER_REGISTRATION_TOKEN)"
print_invite_details "${hub_url}" "${public_url}" "${server_name}" "${invite_code}" "${registration_token}" "true"
echo "- 困った時は docs/troubleshooting.md を確認してください。"
