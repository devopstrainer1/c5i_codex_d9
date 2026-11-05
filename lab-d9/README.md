# Day 9 offline starter

Run from this directory with Python 3.10 or newer. No third party dependencies are needed.

```sh
python3 -m unittest discover -s tests -v
python3 evals/run_all.py
python3 app.py
```

Open http://127.0.0.1:5050 manually. The legacy form is at /legacy. Stop with Ctrl+C. Restart resets all business state, review tokens, pending proposals and audit events. Python may be named python or py on your machine.

## What is supplied

- core.py: a working replay voice controller, deterministic claim validators, source and candidate bound review tokens, and a screen policy simulator.
- app.py: local synthetic UI and legacy HTML form, standard library only, bound to loopback. A form token rejects arbitrary cross site form submission. It is not authenticated and must remain a classroom app.
- screen_demo.py: dry run, denial and destination policy examples; no browser is launched.
- fixtures: clean and wrong extracted candidates, source text, sample PDF and scanned PDF, PNGs, CSV, independent truth and a screen plan.
- tests: 14 unit tests. evals/day9/cases.json: 40 deterministic behavior cases, 12 voice, 24 extraction and 4 screen policy.
- .github/workflows/day9.yml: local repository CI starter assuming this lab is the repository root. If nested in another repo, adjust working-directory or integrate into its existing workflow. Remote CI and branch protection have not been configured or run.

## What learners add

Follow Curriculum.md and Learner_Worksheet.md one checkpoint at a time. The live voice, model extraction, XLSX reader and actual browser execution adapters are extension tasks. The source and candidate are fixed fixtures; no ASR or OCR is hidden inside replay. ScreenPolicy validates a plan but cannot confine real browser traffic or produce actual screenshots. Source review in this app is a synthetic checkbox, not verified identity.

The starter already has expiry, stale version rejection and review hashing so the instructor can teach from visible working controls. If a prompt requests something already present, ask Codex to inspect it, add the missing proof or extend it rather than duplicate it. Currency validation, per validator UNRESOLVED reporting, review expiry, authenticated identity, durable audit, browser deadlines, baseline comparisons and the capstone cross channel acceptance rule are intentional learner tasks.

## Proof exercises

Voice: status; move Underwriting; yes but wait; verify Review. Then move Underwriting; confirm; confirm; verify only one version increment.

Documents: choose bad and check review; it must quarantine. Choose clean without review; it must await review. Check the original then choose clean with review; it saves. Repeating the save returns DUPLICATE.

Screen: `python3 screen_demo.py` prints DRY_RUN, DENIED and BLOCKED. These are simulator results. The local legacy form changes synthetic claim stage only after its explicit approval checkbox is selected. The capstone adds a shared document acceptance precondition for both voice and legacy changes.

Gate: first run checks green. Ask Codex to temporarily disable arithmetic rejection only. The amount mismatch cases should fail, even though their checksum and evidence pass. Restore the code and rerun green. Do not change expected outputs or truth.

## Known boundaries

Single process, synthetic identity and in memory state; not production secure storage or a concurrent transactional service. Store.move is a classroom primitive, not an authorization boundary. The action service is a learner refactor. There is no calibrated confidence score, no real audio fixture, no measured voice latency, no live model extraction, no screenshot driven model and no claimed earlier day coverage without supplied earlier sets. Model output records are intentionally exposed so the logic is inspectable.

## Current documentation for extensions

https://developers.openai.com/api/docs/guides/realtime
https://developers.openai.com/api/docs/guides/voice-webrtc
https://developers.openai.com/api/docs/guides/structured-outputs
https://developers.openai.com/api/docs/guides/file-inputs
https://developers.openai.com/api/docs/guides/tools-computer-use
https://playwright.dev/python/docs/intro

Check exact schemas and dependency versions before adding adapters. Standard API credentials remain server side. This starter never requests or uses an API credential.
