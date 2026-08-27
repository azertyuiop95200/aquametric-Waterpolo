#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
IP=$(python - <<'PY'
import socket
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
try:
    s.connect(('8.8.8.8',80)); print(s.getsockname()[0])
except Exception:
    print('YOUR_COMPUTER_IP')
finally:
    s.close()
PY
)
echo "On your phone, connected to the SAME Wi-Fi, open: http://$IP:8000"
echo "Keep this terminal open while using AquaMetric."
python -m uvicorn main:app --host 0.0.0.0 --port 8000
