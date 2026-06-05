#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${CATCHAT_SERVER_REPO_URL:-https://github.com/kokorodonguri/catchat-server.git}"
INSTALL_DIR="${CATCHAT_INSTALL_DIR:-$HOME/catchat-server}"

fail() {
  echo "Error: $*" >&2
  exit 1
}

has_command() {
  command -v "$1" >/dev/null 2>&1
}

has_command git || fail "git が必要です。インストールしてからもう一度実行してください。"
has_command docker || fail "Docker が必要です。Docker Desktop または Docker Engine をインストールしてください。"

if ! docker info >/dev/null 2>&1; then
  cat >&2 <<'EOF'
Docker は見つかりましたが、現在のユーザーで利用できません。

よくある原因:
- Docker Desktop / Docker Engine が起動していない
- Linux で現在のユーザーが docker グループに入っていない
- sudo なしで Docker を使えない設定になっている

確認:
  docker info
  sudo docker info

よくある対処:
  sudo systemctl start docker
  sudo usermod -aG docker $USER

docker グループに追加した後は、ログアウトしてログインし直してください。
一時的に sudo が必要な環境では、次のように手動で実行してください。

  git clone https://github.com/kokorodonguri/catchat-server.git
  cd catchat-server
  sudo docker compose up -d --build

通常は Docker を sudo なしで使える状態にしてから ./setup.sh を実行するのを推奨します。
EOF
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  :
elif has_command docker-compose; then
  :
else
  fail "Docker Compose が必要です。Docker Compose v2 をインストールしてください。"
fi

if [[ -d "${INSTALL_DIR}/.git" ]]; then
  echo "既存の repository を更新します: ${INSTALL_DIR}"
  git -C "${INSTALL_DIR}" pull --ff-only
elif [[ -e "${INSTALL_DIR}" ]]; then
  fail "${INSTALL_DIR} は存在しますが git repository ではありません。CATCHAT_INSTALL_DIR で別の場所を指定してください。"
else
  echo "clone します: ${REPO_URL} -> ${INSTALL_DIR}"
  git clone "${REPO_URL}" "${INSTALL_DIR}"
fi

cd "${INSTALL_DIR}"
exec bash ./setup.sh
