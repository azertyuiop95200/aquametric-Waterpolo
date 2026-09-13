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
    subprocess.run([sys.executable, "-c", "from rapidocr_onnxruntime import RapidOCR; RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1); print('Bundled CPU OCR ready')"], check=True)


if __name__ == "__main__":
    main()
