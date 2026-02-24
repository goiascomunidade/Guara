# ── Stage 1: Download Piper model ────────────────────────────────────────────
FROM python:3.12-slim AS model-downloader

RUN apt-get update && apt-get install -y --no-install-recommends wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /models

RUN wget -q \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx" \
    -O pt_BR-faber-medium.onnx \
    && wget -q \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json" \
    -O pt_BR-faber-medium.onnx.json

# ── Stage 2: Python dependencies ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml .
COPY . .

RUN pip install --no-cache-dir -e ".[all-providers]"

# ── Stage 3: Final image ──────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=model-downloader /models /models
COPY . .

EXPOSE 8080

ENV GUARA_LLM=openai \
    GUARA_STT=whisper \
    GUARA_TTS=piper \
    PIPER_MODEL_PATH=/models/pt_BR-faber-medium.onnx \
    WHISPER_MODEL_SIZE=base

CMD ["python3", "-m", "runtime.main", "--host", "0.0.0.0", "--port", "8080"]
