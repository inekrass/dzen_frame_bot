"""MediaPipe implementation of the local face detector interface."""

from __future__ import annotations

from pathlib import Path

import mediapipe as mp
import numpy as np
from PIL import Image

from dzen_frame_bot.image_processing import FaceBox

DEFAULT_DETECTION_MAX_SIDE = 1600


class MediaPipeFaceDetector:
    """Detect faces locally with the bundled short-range BlazeFace model."""

    def __init__(
        self,
        model_path: Path,
        *,
        min_confidence: float = 0.55,
        detection_max_side: int = DEFAULT_DETECTION_MAX_SIDE,
    ) -> None:
        options = mp.tasks.vision.FaceDetectorOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=str(model_path),
                delegate=mp.tasks.BaseOptions.Delegate.CPU,
            ),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            min_detection_confidence=min_confidence,
        )
        self._detector = mp.tasks.vision.FaceDetector.create_from_options(options)
        self._detection_max_side = detection_max_side

    def detect(self, image: Image.Image) -> tuple[FaceBox, ...]:
        """Return detected boxes scaled back to the original image size."""
        detection_image = image.copy()
        detection_image.thumbnail(
            (self._detection_max_side, self._detection_max_side),
            Image.Resampling.LANCZOS,
        )

        scale_x = image.width / detection_image.width
        scale_y = image.height / detection_image.height
        pixels = np.ascontiguousarray(detection_image, dtype=np.uint8)
        media_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=pixels)
        result = self._detector.detect(media_image)

        return tuple(
            FaceBox(
                x=detection.bounding_box.origin_x * scale_x,
                y=detection.bounding_box.origin_y * scale_y,
                width=detection.bounding_box.width * scale_x,
                height=detection.bounding_box.height * scale_y,
            )
            for detection in result.detections
        )

    def close(self) -> None:
        """Release native MediaPipe resources."""
        self._detector.close()

    def __enter__(self) -> MediaPipeFaceDetector:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
