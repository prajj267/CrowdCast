"""Download the YOLOX ONNX models listed in configs/vision/yolox_models.yaml and verify them.

Each file is checked against the recorded size and, once recorded, its SHA-256. Files already
present are verified, not re-downloaded. Weights go to models/yolox/ (git-ignored).

Usage (from backend/):  uv run python -m tools.vision.fetch_models [--only yolox_nano ...]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from crowdcast.common.config import REPO_ROOT

MANIFEST = REPO_ROOT / "configs" / "vision" / "yolox_models.yaml"
MODEL_DIR = REPO_ROOT / "models" / "yolox"
DOWNLOAD_ATTEMPTS = 3


def load_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh)
    return data


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path, size_bytes: int, sha256: str | None) -> list[str]:
    """Return a list of problems (empty when the file matches the manifest)."""
    problems: list[str] = []
    actual_size = path.stat().st_size
    if actual_size != size_bytes:
        problems.append(f"size {actual_size} != expected {size_bytes}")
    if sha256 is not None and sha256_of(path) != sha256:
        problems.append("sha256 mismatch")
    return problems


def fetch(name: str, spec: dict[str, Any], model_dir: Path = MODEL_DIR) -> Path:
    model_dir.mkdir(parents=True, exist_ok=True)
    target = model_dir / f"{name}.onnx"
    if not target.exists():
        tmp = target.with_suffix(".part")
        print(f"downloading {name} ({spec['size_bytes'] / 1e6:.1f} MB) from {spec['url']}")
        for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
            try:
                urllib.request.urlretrieve(spec["url"], tmp)
                break
            except urllib.error.ContentTooShortError:
                # GitHub's CDN occasionally drops the connection mid-file; the size check
                # below would also catch a truncated file, so simply retry.
                tmp.unlink(missing_ok=True)
                if attempt == DOWNLOAD_ATTEMPTS:
                    raise
                print(f"  incomplete download, retrying ({attempt}/{DOWNLOAD_ATTEMPTS})")
        tmp.replace(target)
    problems = verify(target, int(spec["size_bytes"]), spec.get("sha256"))
    if problems:
        raise SystemExit(f"{target}: {'; '.join(problems)} - delete it and fetch again")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="model names to fetch (default: all)")
    args = parser.parse_args(argv)

    manifest = load_manifest()
    models: dict[str, dict[str, Any]] = manifest["models"]
    names = args.only or list(models)
    for name in names:
        if name not in models:
            raise SystemExit(f"unknown model {name!r}; known: {', '.join(models)}")
        path = fetch(name, models[name])
        recorded = models[name].get("sha256")
        status = "verified" if recorded else "NOT YET RECORDED - add to manifest"
        print(f"{name}: {path}  sha256={sha256_of(path)}  ({status})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
