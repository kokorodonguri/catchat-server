# Multi-stage build: use slim image for lightweight production
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install only essential runtime dependencies (if any needed)
# sqlite3 is already included in python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and the public settings template.
COPY main.py .
COPY server.properties.example ./server.properties

# Create directories for persistent mounts.
RUN mkdir -p /app/data /app/uploads

# Expose the application port
EXPOSE 8100

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8100/api/server/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
