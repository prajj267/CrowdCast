"""FrameSource: sampled frames of a recorded video, stamped with EVENT time (WORKFLOW 6.1.1).

The timestamp of frame i is ``recording_start + i / source_fps`` - derived from the frame index,
never from the wall clock, so processing speed and replays cannot shift the timeline
(doc 09 §3, CLAUDE.md §4). Frames live only in memory: nothing is written to disk (doc 19).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from crowdcast.common.time import ensure_utc
from crowdcast.vision.interfaces import ImageBGR


@dataclass(frozen=True)
class Frame:
    index: int  # frame number in the source file
    time: datetime  # event time (UTC)
    image: ImageBGR


class FrameSource:
    """Iterate a video file at ``sample_fps`` (every n-th frame, n = round(source / sample))."""

    def __init__(self, path: Path, recording_start: datetime, sample_fps: float = 5.0) -> None:
        if sample_fps <= 0:
            raise ValueError("sample_fps must be positive")
        self.path = path
        self.recording_start = ensure_utc(recording_start)
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise FileNotFoundError(f"cannot open video {path}")
        self.source_fps = float(cap.get(cv2.CAP_PROP_FPS))
        self.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.size = (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
        cap.release()
        if self.source_fps <= 0:
            raise ValueError(f"{path}: video reports no frame rate")
        self.step = max(1, round(self.source_fps / sample_fps))

    @property
    def sample_fps(self) -> float:
        return self.source_fps / self.step

    def time_of(self, index: int) -> datetime:
        return self.recording_start + timedelta(seconds=index / self.source_fps)

    def __iter__(self) -> Iterator[Frame]:
        cap = cv2.VideoCapture(str(self.path))
        try:
            index = 0
            while True:
                if index % self.step == 0:
                    ok, img = cap.read()
                    if not ok:
                        return
                    yield Frame(index, self.time_of(index), np.asarray(img, dtype=np.uint8))
                elif not cap.grab():  # skipped frames are decoded but not kept
                    return
                index += 1
        finally:
            cap.release()
