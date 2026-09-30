"""Write or check the olympiad API snapshot in the repository root."""

import argparse
import json
from pathlib import Path

from app.main import app


TARGET = Path(__file__).resolve().parents[1] / "olymp-openapi.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the snapshot differs from the app")
    args = parser.parse_args()
    schema = app.openapi()

    if args.check:
        if not TARGET.exists() or json.loads(TARGET.read_text()) != schema:
            parser.exit(1, f"Outdated OpenAPI snapshot: {TARGET}\n")
        print(f"Current OpenAPI snapshot: {TARGET}")
        return

    TARGET.write_text(json.dumps(schema, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Updated OpenAPI snapshot: {TARGET}")


if __name__ == "__main__":
    main()
