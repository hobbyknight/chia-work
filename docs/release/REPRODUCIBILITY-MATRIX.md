# Reproducibility matrix

| Item | Deterministic command / method | Expected result | Restriction |
|---|---|---|---|
| Unit suite | `pytest -q` | 96 passed on release validation | no model call |
| Grounding/observability | `pytest -q tests/test_runtime_grounding.py tests/test_observability.py tests/safety_observability_campaign.py` | 36 passed | no model call |
| Policy/prompt preservation | `pytest -q tests/test_safety.py tests/test_safety_v2_prompt_semantics.py tests/test_takeover_gate.py tests/test_veto.py` | 44 passed | no model call |
| Replay | closeout deterministic replay verifier | 13/13 passed | read-only historical evidence |
| Corruption probes | closeout corruption verifier | 5/5 passed | read-only historical evidence |
| Hashes | `sha256sum -c SHA256SUMS.txt` | every listed file OK | do not alter bundle |
| Source recovery | extract source snapshot and compare manifest | byte-level manifest match | release snapshot only |
| Git recovery | `git clone safeagent-final-release.bundle recovered && git -C recovered fsck --full` | clone and fsck pass | release bundle only |

Known limitations: Safety-v3 is a single controlled nonproposal run. No challenged Safety-v1/v2/v3 action exercised deterministic rejection, and no claim is made that SafetyGate rejected it. No formal proof, universal safety guarantee, or universal hallucination-elimination claim is supported.
