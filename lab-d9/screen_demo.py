import json
from pathlib import Path
from core import ScreenPolicy

plan = json.loads((Path(__file__).parent / "fixtures/screen_plan.json").read_text())
policy = ScreenPolicy()
print("POLICY SIMULATOR ONLY: no browser created; no screen execution.")
print(json.dumps(policy.run(plan, dry_run=True), indent=2))
print("Deny submit after permitting fill:")
print(json.dumps(policy.run(plan, approvals=[True, False]), indent=2))
print("Unexpected origin:")
print(json.dumps(policy.run([{"action": "open", "url": "https://example.com"}]), indent=2))
