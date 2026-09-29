import json
import yaml
from app.main import app

schema = app.openapi()
with open("openapi.json", "w") as f:
    json.dump(schema, f, indent=2, ensure_ascii=False)
with open("openapi.yaml", "w") as f:
    yaml.safe_dump(schema, f, allow_unicode=True, sort_keys=False)