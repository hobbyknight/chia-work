# PACKAGE STATUS

Legend: `READY` = usable now; `SCAFFOLD` = structure exists but real integration is incomplete; `BLOCKED` = depends on external credentials/compute.

| Area | Status | Notes |
|---|---|---|
| Control-plane docs | READY | README, plan, checkpoint, status |
| Official requirements snapshot | READY | Final submission requirements recorded |
| SafeAgent architecture | READY | Research architecture and threat/failure model drafted |
| Typed actions | READY | Local Python dataclasses/enums |
| SafetyGate | READY | Experimental local policy logic; not a production sandbox |
| Structured logging | READY | JSONL schema with explicit mocked flag |
| Dry-run runner | READY | Useful only for plumbing/tests, not research results |
| Unit tests | READY | Local safety-policy checks |
| Experiment matrix | READY | U0–S4 definitions drafted; freeze required Sep 19 |
| Metrics schema | READY | Primary/secondary metrics specified |
| CHIA bootstrap | READY | Script prepared; execution still required on a real machine |
| CHIA adapter | SCAFFOLD | Import detection only; real ChiaFunction/ChiaTool path pending |
| Gemini agent | SCAFFOLD | Interface slot documented; no API call yet |
| Gemmini/Chipyard backend | SCAFFOLD | Integration plan exists; no real run yet |
| GCP migration | READY | Runbook + env-only credential strategy |
| Funded GCP credentials | BLOCKED | Organizers send Sep 20 PDT |
| Paper | SCAFFOLD | 4-page outline prepared, results empty |
| HotCRP submission | SCAFFOLD | Checklist prepared; browser submission still required |
| Public final release | BLOCKED | Working repo is currently private; publish before final submission |
