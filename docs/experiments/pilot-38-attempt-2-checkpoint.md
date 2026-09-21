# Gemini 3.8 hardware pilot — attempt 2 checkpoint

Frozen at: 2026-09-21T17:48:17Z  
Ray submission ID: `raysubmit_b6mbiNRazgcRB7PR`

```text
PILOT_38_ATTEMPT_2=FAILED
failure_layer=Gemini API
failure_code=429 RESOURCE_EXHAUSTED
completed_rows=0/5
warmup_rows=1
blocker=HUMAN_BLOCKER
```

Attempt 2 used new output filenames and did not overwrite or combine attempt 1. The deterministic warm-up completed. The first Gemini proposal for U0 then received HTTP 429. The bounded transient handler retried the same API operation three times with delays of 5, 10, and 20 seconds, logged each reason and delay, and stopped after the final 429. No comparative row or hardware variant execution began.

No H1 main, safety, or recovery job was submitted.

## Persistent evidence and hashes

| VM file | SHA256 |
|---|---|
| `results/hardware-pilot-gemini-3.8-flash-attempt-2-warmup.jsonl` | `b9af39bfdd4d85e808d86358e28ac8f3c647079802cc938bb16fc1d353442ac5` |
| `logs/raysubmit_b6mbiNRazgcRB7PR.log` | `5057d4d0a743b4b335ce85b547bf7c0d336ea79f2aa620eb0691727c80303969` |
| `logs/raysubmit_b6mbiNRazgcRB7PR-watcher.log` | `826b588ab16de143b360a561a5776ca43bb52a4391c46f2daf5a4e2e7c62943c` |
| `logs/pilot38-attempt2-vertex-ai-quota.json` | `7dd619e43ce71b11640975c4dfa162cc83434b6bac03de13788cd8c3fd198571` |
| `results/raysubmit_b6mbiNRazgcRB7PR-pilot38-attempt2-SHA256SUMS.txt` | `135d71f630b3fa9d5b75b13c71587d2f2d47be2bd6d95fe847ae62e1a29effe1` |
| `results/raysubmit_b6mbiNRazgcRB7PR-pilot38-attempt2-FULL-SHA256SUMS.txt` | `0288d013be4d95c43bcbadac32f18e312299ecdab66e87c1e8f6f7bca89327c5` |
| `PILOT_38_ATTEMPT_2_TERMINAL_ON_VM` | `f4fa6e455e0dee5a441e85e2a885beecffbc2c75908724ee74ff662788a549c0` |
| `HUMAN_BLOCKER` | `6f373810deb8627e7a491b6fc0141cf5d8dccef3a4e8e2abcfc66ce1217bdcac` |

All files above were copied to `/content/drive/MyDrive/CHIA-Hackathon/evidence/` under `results/`, `logs/`, or `manifests/`; every Drive hash matches the VM hash.

## Quota/capacity observation

The read-only Vertex AI quota query exposes a default effective limit of 5 global generate-content requests per minute per project/base model, but it has no model-specific `gemini-3.8-flash` bucket and reports no current usage. This evidence cannot distinguish a quota allocation issue from shared service capacity. The exact API response remains `429 RESOURCE_EXHAUSTED`, so external quota/capacity intervention is required before another complete pilot attempt.
