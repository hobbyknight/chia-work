# Claim–evidence matrix

| Claim | Experiment | Artifact | Immutable bundle / verifier | Limitation |
|---|---|---|---|---|
| Safety-v2 exposed an unsupported execution-state claim despite zero durable execution evidence. | Safety-v2 | `SAFETY-V2-V3-COMPARISON.md` | Safety-v2 closeout referenced by Safety-v3 closeout historical verification | A root-cause result, not a general model claim. |
| Root-cause audit localized the first unsupported claim to L2 synthesis call 7 and proposal suppression upstream. | proposal-suppression root-cause audit | audit report and model-call ledger | `20260923T094000Z-safety-v3-closeout/historical-verification` | Localization applies to the frozen trace. |
| Safety-v3 introduced authoritative runtime/artifact grounding at L2 synthesis and L1 pre-proposal synthesis. | Safety-v3 engineering audit | `runtime_grounding.py`, `takeover_gate.py`, tests | `20260923T094000Z-safety-v3-closeout/base-to-safety-v3.patch`; SHA256 manifest | Implementation does not alter action authorization. |
| In one controlled Safety-v3 run, no unsupported execution-state claim was observed. | `20260923T093300Z-safety-v3` | prompt/response ledger, lifecycle and terminal artifacts | `20260923T094000Z-safety-v3-closeout`; 398/398 SHA256 PASS | One run; not a universal guarantee. |
| Proposal suppression remained. | `20260923T093300Z-safety-v3` | runner result, terminal artifact, model ledger | Safety-v3 closeout and deterministic replay | No deterministic rejection was exercised. |
| Model narrative is distinct from durable execution truth. | Safety-v3 grounding tests | lifecycle/indexed-artifact tests | grounding/observability 36/36 | Tests establish implementation behavior, not formal proof. |
