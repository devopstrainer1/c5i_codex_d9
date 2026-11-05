"""Deterministic behavioral gate, not a live audio/OCR/browser benchmark."""
import copy
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import Store, VoiceController, ExtractionPipeline, ScreenPolicy

def run_case(case):
    store = Store()
    kind = case["kind"]
    if kind == "voice":
        now = [0]
        voice = VoiceController(store, lambda: now[0])
        results = []
        for event in case["events"]:
            now[0] = event.get("t", now[0])
            results.append(voice.handle(event["text"]))
        return results[-1] == case["expect"] and store.claims["CLM-000101"]["stage"] == case["stage"] and store.claims["CLM-000101"]["version"] == case["writes"]
    if kind == "extraction":
        c = json.loads((ROOT / "fixtures/clean.json").read_text())
        c.update(case.get("patch", {}))
        source = (ROOT / "fixtures/source.txt").read_text() + case.get("source_extra", "")
        pipeline = ExtractionPipeline(store)
        token = pipeline.review(c, source, "synthetic-eval-reviewer") if case.get("review") else None
        result = pipeline.process(c, source, token)
        flags = [k for k,v in result["checks"].items() if v["status"] != "PASS"]
        return result["status"] == case["expect"] and all(k in flags for k in case.get("must_flag", [])) and len(store.accepted) == case["saved"]
    if kind == "screen":
        result = ScreenPolicy().run(case["plan"], case.get("approvals", []), case.get("dry_run", False))
        return result["status"] == case["expect"]
    raise ValueError("Unsupported case kind " + str(kind))

def main():
    rows, seen = [], set()
    # Earlier compatible day folders are discovered; adapters for other formats are a learner task.
    paths = sorted((ROOT / "evals").glob("day*/cases.json"))
    for path in paths:
        for case in json.loads(path.read_text()):
            case_id = case["id"]
            if case_id in seen:
                raise ValueError("Duplicate case ID " + case_id)
            seen.add(case_id)
            try:
                ok = run_case(case)
                rows.append((case_id, ok, ""))
            except Exception as error:
                rows.append((case_id, False, type(error).__name__ + ": " + str(error)))
    if not rows:
        raise ValueError("No cases discovered")
    failures = [row for row in rows if not row[1]]
    report = ["# Day 9 replay report", "", "Mode: offline deterministic candidates and events.",
              "Live ASR, live OCR, real latency and browser execution: NOT RUN.",
              "Previous days: only compatible day folders present in this workspace are included.",
              "", f"Cases run: {len(rows)}; passed: {len(rows)-len(failures)}; failed: {len(failures)}.", ""]
    report += [f"- {case_id}: {'PASS' if ok else 'FAIL'} {error}" for case_id,ok,error in rows]
    (ROOT / "evals/report.md").write_text("\n".join(report) + "\n")
    print("\n".join(report[:7]))
    for row in failures:
        print("FAIL", row[0], row[2])
    return int(bool(failures))

if __name__ == "__main__":
    sys.exit(main())
