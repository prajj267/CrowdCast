"""Write the API's OpenAPI schema to frontend/src/api/openapi.json (WORKFLOW 4.5.2).

No server needed. Then, in frontend/: ``npm run gen:api`` regenerates src/api/schema.ts.
Usage (from backend/):  uv run python -m tools.export_openapi
"""

from __future__ import annotations

import json
import sys

from crowdcast.api.app import create_app
from crowdcast.common.config import REPO_ROOT

OUT = REPO_ROOT / "frontend" / "src" / "api" / "openapi.json"


def main() -> int:
    schema = create_app().openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"written {OUT} ({len(schema['paths'])} paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
