"""In-memory photo cropping and frame composition."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageOps, UnidentifiedImageError

DEFAULT_OUTPUT_SIZE = 1280
DEFAULT_MAX_INPUT_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_INPUT_PIXELS = 40_000_000
SUPPORTED_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


class ImageProcessingError(RuntimeError):
    """Base class for expected image processing failures."""


class InvalidImageError(ImageProcessingError):
    """Raised when uploaded bytes are not a supported, decodable image."""


class ImageTooLargeError(ImageProcessingError):
    """Raised when an input exceeds configured byte or pixel limits."""


class InvalidFrameError(ImageProcessingError):
    """Raised when the configured overlay cannot be used."""


@dataclass(frozen=True, slots=True)
class FaceBox:
    """Face bounding box expressed in source-image pixel coordinates."""

    x: float
    y: float
    width: float
    height: float

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    @property
    def area(self) -> float:
        return max(self.width, 0) * max(self.height, 0)


@dataclass(frozen=True, slots=True)
class CropBox:
    """Square crop coordinates in the source image."""

    left: int
    top: int
    size: int

    @property
    def pillow_box(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.left + self.size, self.top + self.size)


@dataclass(frozen=True, slots=True)
class ProcessedImage:
    """Encoded result variants and non-sensitive processing metadata."""

    png: bytes
    jpeg: bytes
    detected_faces: int
    used_face_crop: bool


class FaceDetector(Protocol):
    """Interface implemented by local face detectors and test doubles."""

    def detect(self, image: Image.Image) -> Sequence[FaceBox]:
        """Return face boxes for an upright RGB image."""


def calculate_square_crop(
    image_size: tuple[int, int],
    faces: Sequence[FaceBox],
    *,
    face_target: tuple[float, float] = (0.60, 0.38),
) -> CropBox:
    """Choose a square crop, preferring faces and never introducing padding."""
    width, height = image_size
    if width <= 0 or height <= 0:
        raise InvalidImageError("Image dimensions must be positive")

    crop_size = min(width, height)
    valid_faces = tuple(
        face
        for face in faces
        if face.width > 0
        and face.height > 0
        and face.x < width
        and face.y < height
        and face.x + face.width > 0
        and face.y + face.height > 0
    )

    if not valid_faces:
        return CropBox(
            left=(width - crop_size) // 2,
            top=(height - crop_size) // 2,
            size=crop_size,
        )

    focus = _choose_face_focus(valid_faces, crop_size)
    target_x, target_y = face_target
    desired_left = round(focus.center_x - crop_size * target_x)
    desired_top = round(focus.center_y - crop_size * target_y)

    return CropBox(
        left=_clamp(desired_left, 0, width - crop_size),
        top=_clamp(desired_top, 0, height - crop_size),
        size=crop_size,
    )


def _choose_face_focus(faces: Sequence[FaceBox], crop_size: int) -> FaceBox:
    """Use all nearby faces, otherwise prioritize the largest visible face."""
    left = min(face.x for face in faces)
    top = min(face.y for face in faces)
    right = max(face.x + face.width for face in faces)
    bottom = max(face.y + face.height for face in faces)
    union = FaceBox(left, top, right - left, bottom - top)

    safe_span = crop_size * 0.85
    if union.width <= safe_span and union.height <= safe_span:
        return union
    return max(faces, key=lambda face: face.area)


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


class ImageProcessor:
    """Create framed square images without persisting user photos."""

    def __init__(
        self,
        detector: FaceDetector,
        frame_path: Path,
        *,
        output_size: int = DEFAULT_OUTPUT_SIZE,
        max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES,
        max_input_pixels: int = DEFAULT_MAX_INPUT_PIXELS,
    ) -> None:
        self._detector = detector
        self._output_size = output_size
        self._max_input_bytes = max_input_bytes
        self._max_input_pixels = max_input_pixels
        self._frame = self._load_frame(frame_path)

    def process(self, image_bytes: bytes) -> ProcessedImage:
        """Decode, orient, crop, frame and encode one image entirely in memory."""
        image = self._decode_image(image_bytes)
        faces = tuple(self._detector.detect(image))
        crop_box = calculate_square_crop(image.size, faces)

        cropped = image.crop(crop_box.pillow_box)
        resized = cropped.resize(
            (self._output_size, self._output_size),
            Image.Resampling.LANCZOS,
        )
        composed = Image.alpha_composite(resized.convert("RGBA"), self._frame)

        return ProcessedImage(
            png=self._encode_png(composed),
            jpeg=self._encode_jpeg(composed),
            detected_faces=len(faces),
            used_face_crop=bool(faces),
        )

    def _decode_image(self, image_bytes: bytes) -> Image.Image:
        if not image_bytes:
            raise InvalidImageError("Image is empty")
        if len(image_bytes) > self._max_input_bytes:
            raise ImageTooLargeError("Image file exceeds the allowed size")

        try:
            with Image.open(BytesIO(image_bytes)) as source:
                if source.format not in SUPPORTED_IMAGE_FORMATS:
                    raise InvalidImageError("Unsupported image format")
                width, height = source.size
                if width * height > self._max_input_pixels:
                    raise ImageTooLargeError("Image dimensions exceed the allowed size")

                upright = ImageOps.exif_transpose(source)
                upright.load()
                return upright.convert("RGB")
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
            raise InvalidImageError("Image cannot be decoded") from error

    def _load_frame(self, frame_path: Path) -> Image.Image:
        try:
            with Image.open(frame_path) as frame:
                frame.load()
                rgba = frame.convert("RGBA")
        except (UnidentifiedImageError, OSError) as error:
            raise InvalidFrameError("Frame cannot be decoded") from error

        expected_size = (self._output_size, self._output_size)
        if rgba.size != expected_size:
            raise InvalidFrameError(
                f"Frame must be {self._output_size}x{self._output_size} pixels"
            )
        return rgba

    @staticmethod
    def _encode_png(image: Image.Image) -> bytes:
        buffer = BytesIO()
        image.save(buffer, format="PNG", compress_level=6)
        return buffer.getvalue()

    @staticmethod
    def _encode_jpeg(image: Image.Image) -> bytes:
        buffer = BytesIO()
        image.convert("RGB").save(
            buffer,
            format="JPEG",
            quality=95,
            optimize=True,
            subsampling=0,
        )
        return buffer.getvalue()
