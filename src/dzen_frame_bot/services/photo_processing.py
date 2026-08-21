"""Async boundary around the CPU-bound image processor."""

from __future__ import annotations

import asyncio

from dzen_frame_bot.image_processing import (
    ImageProcessor,
    ProcessedImage,
)


class PhotoProcessingService:
    """Serialize native detector calls and keep the event loop responsive."""

    def __init__(self, processor: ImageProcessor) -> None:
        self._processor = processor
        self._processing_lock = asyncio.Lock()

    @property
    def max_input_bytes(self) -> int:
        return self._processor.max_input_bytes

    async def process(self, image_bytes: bytes) -> ProcessedImage:
        """Run one in-memory image operation in a worker thread."""
        async with self._processing_lock:
            return await asyncio.to_thread(self._processor.process, image_bytes)
