FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Deploy the exact V12 source validated by GitHub Actions rather than
# reconstructing an older release bundle at container build time.
COPY source/ /app/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg tesseract-ocr ca-certificates \
       libcairo2 libpango-1.0-0 libjpeg62-turbo libgif7 librsvg2-2 \
    && rm -rf /var/lib/apt/lists/*

RUN python scripts/install_dependencies.py

EXPOSE 10000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
