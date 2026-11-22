"""FrameSource (6.1.1) and camera YAML v1 (6.1.2). Uses a generated test video (no people)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from pydantic import ValidationError

from crowdcast.venue_graph.interfaces import CameraConfig, load_venue_config
from crowdcast.vision.frames import FrameSource

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
START = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)


@pytest.fixture
def video(tmp_path: Path) -> Path:
    path = tmp_path / "clip.avi"
    w = cv2.VideoWriter(str(path), cv2.VideoWriter.fourcc(*"MJPG"), 25, (64, 48))
    for i in range(50):  # 2 s at 25 fps; frame i has brightness i * 5
        w.write(np.full((48, 64, 3), i * 5, np.uint8))
    w.release()
    return path


def test_frames_are_sampled_and_stamped_in_event_time(video: Path) -> None:
    src = FrameSource(video, START, sample_fps=5)
    assert (src.source_fps, src.step, src.sample_fps) == (25.0, 5, 5.0)
    frames = list(src)
    assert [f.index for f in frames] == list(range(0, 50, 5))
    assert [f.time for f in frames] == [START + timedelta(seconds=i / 25) for i in range(0, 50, 5)]
    assert frames[0].image.shape == (48, 64, 3) and frames[0].image.dtype == np.uint8
    assert abs(int(frames[2].image.mean()) - 50) <= 3  # frame 10, brightness 50 (MJPG lossy)


def test_frame_source_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        FrameSource(tmp_path / "nope.mp4", START)


def _camera() -> dict[str, Any]:
    return {
        "format_version": 1,
        "camera": {
            "code": "CAM1",
            "venue": "v1",
            "source": "videos/x.mp4",
            "recording_start": "2026-11-01T10:00:00Z",
            "image_width": 1920,
            "image_height": 1080,
        },
        "regions": [{"zone": "C1", "polygon_px": [[0, 0], [900, 0], [900, 1000], [0, 1000]]}],
        "lines": [
            {"from": "C1", "to": "MS", "p1": [950, 0], "p2": [950, 1080], "positive_side": "MS"}
        ],
    }


def test_valid_camera_config_matches_the_venue() -> None:
    cam = CameraConfig.model_validate(_camera())
    assert cam.camera.sample_fps == 5.0 and cam.camera.detector == "yolox_s"
    assert cam.camera.recording_start == START
    cam.check_against_venue(load_venue_config(CONFIGS / "venues" / "v1.yaml"))


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (
            lambda c: c["regions"][0].update(polygon_px=[[0, 0], [10, 10], [10, 0], [0, 10]]),
            "non-self-intersecting",
        ),
        (lambda c: c["lines"][0].update(p2=[950, 2000]), "outside the 1920x1080 image"),
        (lambda c: c["lines"][0].update(positive_side="FC"), "one end of the connection"),
        (lambda c: c["regions"].append(dict(c["regions"][0])), "more than one primary"),
        (  # same connection, opposite direction: still a second line on it (doc 09 §8)
            lambda c: c["lines"].append(
                {"from": "MS", "to": "C1", "p1": [960, 0], "p2": [960, 1080], "positive_side": "C1"}
            ),
            "more than one counting line",
        ),
        (lambda c: c["camera"].update(recording_start="2026-11-01T10:00:00"), "timezone"),
    ],
)
def test_invalid_camera_configs(change: Any, match: str) -> None:
    data = _camera()
    change(data)
    with pytest.raises(ValidationError, match=match):
        CameraConfig.model_validate(data)


def test_camera_must_fit_its_venue() -> None:
    venue = load_venue_config(CONFIGS / "venues" / "v1.yaml")
    data = _camera()
    data["lines"][0].update({"from": "C1", "to": "WC", "positive_side": "WC"})  # no such edge
    with pytest.raises(ValueError, match="no such connection"):
        CameraConfig.model_validate(data).check_against_venue(venue)
    data = _camera()
    data["regions"][0]["zone"] = "ZZ"
    with pytest.raises(ValueError, match="not in the venue"):
        CameraConfig.model_validate(data).check_against_venue(venue)
