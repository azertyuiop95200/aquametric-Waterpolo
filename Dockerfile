FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /bundle
COPY bundle_parts/ ./bundle_parts/

RUN python - <<'PY'
from pathlib import Path
import base64, shutil, tarfile
parts = sorted(Path('/bundle/bundle_parts').glob('part_*'))
encoded = ''.join(p.read_text(encoding='ascii') for p in parts)
archive = Path('/bundle/aquametric.tar.xz')
archive.write_bytes(base64.b64decode(encoded))
extract_dir = Path('/bundle/extracted')
extract_dir.mkdir(parents=True, exist_ok=True)
with tarfile.open(archive, 'r:xz') as tf:
    tf.extractall(extract_dir)
src = extract_dir / 'aquametric_v11_2_release'
shutil.copytree(src, '/app', dirs_exist_ok=True)
PY

# Small web-deployment overlay: security middleware, refreshed evidence-backed
# rosters/staff and clickable player/coach profiles. The V11.2 bundle remains
# unchanged and reproducible underneath this layer.
COPY overrides/ /app/

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 10000
CMD ["sh", "-c", "uvicorn web_entry:app --host 0.0.0.0 --port ${PORT:-10000}"]
