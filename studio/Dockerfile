# Terragravity Studio API — runs beside Hermes.
# NOTE: Hermes itself is expected on PATH in the runtime (mounted or installed
# in the same environment). This image packages the FastAPI bridge.
FROM python:3.12-slim

WORKDIR /app

# system deps for git ops + healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates bash && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8088
ENV HERMES_BIN=hermes \
    HERMES_TIMEOUT_S=600

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8088/health || exit 1

# GATEWAY_HMAC_SECRET must be provided at runtime (-e or secret mount).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088"]
