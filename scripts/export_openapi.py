import json
from pathlib import Path
from pao.main import app

target = Path(__file__).resolve().parents[1] / 'packages/contracts/openapi.json'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('Exported OpenAPI; run npm run contracts')
