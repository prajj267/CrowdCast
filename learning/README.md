# Learning notes

Plain-language explanations of the ideas used in CROWDCAST. Each note explains a concept from
scratch, points to where it lives in this repository, and ends with questions an examiner might
ask in the viva and short answers.

These notes explain; they are not the specification. If a note and a document in
`DOCUMENTATION/` disagree, the document wins (see `CLAUDE.md` §1).

| # | Note | What it covers | Used in |
|---|---|---|---|
| 01 | [Python tooling](01_python_tooling.md) | uv, virtual environments, `pyproject.toml`, ruff, mypy, pytest, pre-commit | Phase 1.2 |
| 02 | [Docker and PostgreSQL](02_docker_and_postgres.md) | Containers, images, volumes, ports, why the database runs in Docker | Phase 1.3 |
| 03 | [Database design and constraints](03_database_constraints.md) | Tables, keys, CHECK/UNIQUE, partial indexes, enums: letting the database reject bad data | Phase 1.3 |
| 04 | [SQLAlchemy and Alembic](04_sqlalchemy_and_alembic.md) | ORM models, sessions, transactions, migrations | Phase 1.3 |
| 05 | [Time handling](05_time_handling.md) | UTC, time zones, minute buckets, event time vs wall-clock time | Phase 1.2 |
| 06 | [Object detection with YOLOX](06_object_detection_yolox.md) | What a detector outputs, COCO, letterbox, anchor points and strides, scores, NMS, ONNX | Phase 1.4 |

Suggested reading order: 05 → 03 → 02 → 04 → 01 → 06.
