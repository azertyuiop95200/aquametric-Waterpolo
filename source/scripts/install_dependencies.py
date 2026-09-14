"""Shared build for native Render, Docker and CI, including offline OCR models.

RapidOCR's wheel declares GUI opencv-python; our server supplies the compatible
headless API instead. Install the model wheel without replacing that API or
introducing a libGL dependency. All other dependencies are in requirements.txt.
"""
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(root / "requirements.txt")], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "rapidocr-onnxruntime==1.4.4"], check=True)
    # Fail the build, rather than silently shipping a server without working OCR.
    subprocess.run([sys.executable, "-c", """
import cv2
import numpy as np
from services.scoreboard_ocr import _onnx_image, parse_scoreboard_text
image = np.full((86, 640, 3), 255, dtype=np.uint8)
cv2.putText(image, 'Q1 7:30 2 1', (12, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 2)
text, confidence = _onnx_image(image)
score = parse_scoreboard_text(text)
assert score['home_score'] == 2 and score['away_score'] == 1, (text, confidence)
print('Bundled CPU OCR ready: real cropped scoreboard inference passed')
"""], cwd=root, check=True)


if __name__ == "__main__":
    main()
