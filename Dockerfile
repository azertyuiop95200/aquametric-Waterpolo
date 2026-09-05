FROM node:24-bookworm-slim AS pot-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /root
RUN git clone --depth 1 --single-branch --branch 1.3.2 \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git
WORKDIR /root/bgutil-ytdlp-pot-provider/server
RUN npm ci && npx tsc

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Node 24 is required by the current yt-dlp EJS challenge solver and by the
# local PO-token generation script used for YouTube requests from datacenters.
COPY --from=pot-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=pot-builder /root/bgutil-ytdlp-pot-provider /root/bgutil-ytdlp-pot-provider

# Deploy the exact V12 source validated by GitHub Actions rather than
# reconstructing an older release bundle at container build time.
COPY source/ /app/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg tesseract-ocr ca-certificates \
       libcairo2 libpango-1.0-0 libjpeg62-turbo libgif7 librsvg2-2 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 10000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
