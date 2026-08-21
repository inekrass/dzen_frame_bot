"""Tests for deterministic, in-memory image framing."""

from collections.abc import Sequence
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from dzen_frame_bot.image_processing import (
    CropBox,
    FaceBox,
    ImageProcessor,
    ImageTooLargeError,
    InvalidFrameError,
    InvalidImageError,
    calculate_square_crop,
)


class StaticFaceDetector:
    def __init__(self, faces: Sequence[FaceBox] = ()) -> None:
        self._faces = tuple(faces)

    def detect(self, image: Image.Image) -> tuple[FaceBox, ...]:
        return self._faces


class RecordingFaceDetector:
    def __init__(self) -> None:
        self.image_size: tuple[int, int] | None = None

    def detect(self, image: Image.Image) -> tuple[FaceBox, ...]:
        self.image_size = image.size
        return ()


def make_frame(path: Path, size: int, *, marker: bool = False) -> None:
    frame = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if marker:
        frame.putpixel((0, 0), (255, 255, 255, 255))
    frame.save(path, format="PNG")


def encode_image(image: Image.Image, image_format: str = "PNG") -> bytes:
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def decode_image(image_bytes: bytes) -> Image.Image:
    with Image.open(BytesIO(image_bytes)) as image:
        image.load()
        return image.copy()


def test_center_crop_is_used_without_faces() -> None:
    crop = calculate_square_crop((300, 100), ())

    assert crop == CropBox(left=100, top=0, size=100)


def test_face_crop_places_face_away_from_lower_left_branding() -> None:
    crop = calculate_square_crop(
        (300, 100),
        (FaceBox(x=220, y=20, width=40, height=50),),
    )

    assert crop == CropBox(left=180, top=0, size=100)


def test_processor_returns_square_png_and_jpeg(tmp_path: Path) -> None:
    frame_path = tmp_path / "frame.png"
    make_frame(frame_path, 64, marker=True)
    source = Image.new("RGB", (120, 80), (12, 34, 56))
    processor = ImageProcessor(
        StaticFaceDetector(),
        frame_path,
        output_size=64,
    )

    result = processor.process(encode_image(source))

    png = decode_image(result.png)
    jpeg = decode_image(result.jpeg)
    assert png.size == (64, 64)
    assert jpeg.size == (64, 64)
    assert png.getpixel((0, 0)) == (255, 255, 255, 255)
    assert result.detected_faces == 0
    assert result.used_face_crop is False


def test_processor_reports_detected_faces(tmp_path: Path) -> None:
    frame_path = tmp_path / "frame.png"
    make_frame(frame_path, 32)
    processor = ImageProcessor(
        StaticFaceDetector((FaceBox(10, 10, 20, 20),)),
        frame_path,
        output_size=32,
    )

    result = processor.process(encode_image(Image.new("RGB", (50, 50), "black")))

    assert result.detected_faces == 1
    assert result.used_face_crop is True


def test_processor_rejects_invalid_bytes(tmp_path: Path) -> None:
    frame_path = tmp_path / "frame.png"
    make_frame(frame_path, 32)
    processor = ImageProcessor(
        StaticFaceDetector(),
        frame_path,
        output_size=32,
    )

    with pytest.raises(InvalidImageError, match="cannot be decoded"):
        processor.process(b"not an image")


def test_processor_applies_exif_orientation(tmp_path: Path) -> None:
    frame_path = tmp_path / "frame.png"
    make_frame(frame_path, 32)
    detector = RecordingFaceDetector()
    processor = ImageProcessor(detector, frame_path, output_size=32)
    source = Image.new("RGB", (40, 80), "black")
    exif = source.getexif()
    exif[274] = 6
    buffer = BytesIO()
    source.save(buffer, format="JPEG", exif=exif)

    processor.process(buffer.getvalue())

    assert detector.image_size == (80, 40)


def test_processor_rejects_file_over_byte_limit(tmp_path: Path) -> None:
    frame_path = tmp_path / "frame.png"
    make_frame(frame_path, 32)
    processor = ImageProcessor(
        StaticFaceDetector(),
        frame_path,
        output_size=32,
        max_input_bytes=3,
    )

    with pytest.raises(ImageTooLargeError, match="file exceeds"):
        processor.process(b"four")


def test_processor_rejects_frame_with_wrong_dimensions(tmp_path: Path) -> None:
    frame_path = tmp_path / "frame.png"
    make_frame(frame_path, 16)

    with pytest.raises(InvalidFrameError, match="32x32"):
        ImageProcessor(StaticFaceDetector(), frame_path, output_size=32)
