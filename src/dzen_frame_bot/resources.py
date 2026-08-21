"""Paths to immutable image-processing resources bundled with the package."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
RESOURCES_DIR = PACKAGE_ROOT / "resources"
FRAME_PATH = RESOURCES_DIR / "frame.png"
FACE_MODEL_PATH = RESOURCES_DIR / "blaze_face_short_range.tflite"
