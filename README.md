# SafeAgent for Agentic HW/SW Co-Design

Public artifact for the A³ CHIA Hackathon 2026. SafeAgent combines typed actions, a policy gate, governance, execution observation, and a bounded repair loop for agentic hardware/software co-design.

## Release result

The frozen Safety-v3 result is **GROUNDED_NONPROPOSAL**. One valid controlled Safety-v3 run completed with proposal suppression and no unsupported execution-state claim observed. It is evidence of this bounded run only; it is not a formal safety proof or a universal hallucination-elimination claim.

Safety-v3 adds authoritative runtime/artifact grounding to L2 synthesis and L1 pre-proposal synthesis. A model narrative is never durable execution truth. Durable truth requires the corresponding indexed runtime lifecycle event and execution artifact.

## Architecture

`L0` sets direction and can prepare a typed execution request. `L1` governs through commit-reveal review and veto semantics. `L2` decomposes and synthesizes role evidence. `L3` performs bounded leaf analysis. The execution boundary is outside the model hierarchy: typed actions pass through `SafetyGate`, then CHIA/Ray and the executor, which create lifecycle events and artifacts. Verification observes those artifacts.

The SafetyGate remains an experimental policy layer, not a production sandbox. Safety-v3 does not change SafetyGate, governance, capability grants, action kinds, executor behavior, or CHIA semantics.

## Bootstrap and deterministic checks

Use Python 3.10.19. No command below makes a Gemini/Vertex model call.

```bash
git clone <release-url> safeagent
cd safeagent
bash scripts/bootstrap_chia.sh
make test
pytest -q tests/test_runtime_grounding.py tests/test_observability.py tests/safety_observability_campaign.py
pytest -q tests/test_agentic_loop.py tests/test_safety.py tests/test_safety_v2_prompt_semantics.py tests/test_takeover_gate.py tests/test_veto.py
```

For CHIA/Ray setup, use `configs/chia-gemmini-local.yaml` and `docs/integration/gate-a2-runbook.md`. GCP/Vertex configuration uses environment variables only; see `.env.example` and `docs/gcp/migration-runbook.md`. Never commit credentials, tokens, or service-account JSON.

## Evidence and recovery

The complete release evidence pack is in `docs/release/`. Begin with `CLAIM-EVIDENCE-MATRIX.md`, `EXPERIMENT-INDEX.md`, and `REPRODUCIBILITY-MATRIX.md`. Historical experiment bundles are immutable and must not be edited or rerun. `BUNDLE-INDEX.md` gives SHA256 verification and Git/source recovery procedures.

Scientific reruns are prohibited for H1, TAKEOVER, Safety-v1, Safety-v2, and Safety-v3. Recovery-v1 is not eligible: there is no real chain of ExecutionRequest → deterministic rejection → durable rejection observation.

Known limitations are recorded in `docs/release/REPRODUCIBILITY-MATRIX.md`: the single Safety-v3 controlled nonproposal does not exercise deterministic rejection and does not establish a universal guarantee.
