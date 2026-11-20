# Experiment Log

Every training, evaluation or benchmark run gets one row, **newest first**. No number may appear in the report or the documentation unless it comes from a row here, produced by committed code (CLAUDE.md §6).

`data` must state the origin: SYNTHETIC (SYN-clean / SYN-noisy), REAL (which public dataset) or MANUAL.

| Date | Run ID | Task | Config / command | Data (origin) | Seed | Git commit | Result path | Key result | Deviation from plan |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-20 | bench-20261120T133002Z | 1.4.2 | `uv run python -m tools.vision.bench_detector --video ../videos/public/shibuya_crossing.webm` (5 FPS sampling, 3 warm-up frames, ORT default threads, CPU Ryzen 7 8840HS, onnxruntime 1.32.0) | REAL, public: Wikimedia Commons "Shibuya Crossing, Tokyo, Japan (video).webm" by Basile Morin, CC BY-SA 4.0; 1920×1080, 25 fps, 58.6 s; SHA-1 matches Commons | n/a (deterministic) | **none — code not yet committed; PROVISIONAL, re-run after first commit before citing** | `runs/bench/20261120T133002Z/results.json` | Median detector ms/frame (FPS): nano@416 14.0 (69.1); tiny@416 32.4 (30.5); s@640 111.3 (8.9). Real-time factor incl. decoding: 0.10 / 0.19 / 0.59. Mean persons/frame at score ≥ 0.5 (descriptive, no ground truth): 0.9 / 1.4 / 8.5 | Fixed export input sizes only (see WORKFLOW Deviation log) |
