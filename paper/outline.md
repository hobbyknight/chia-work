# 4-page paper working outline

Working title:

**SafeAgent: Guarded Agentic Hardware/Software Co-Design with CHIA**

## Abstract

Write last. Must state problem, SafeAgent mechanism, real CHIA/Gemmini setup, and the strongest measured result without overstating generality.

## 1. Introduction / Motivation

- Agentic co-design gives LLMs the ability to invoke expensive/stateful hardware design tools.
- Failures are not only wrong text: they can be invalid configurations, wasted compute, destructive operations, or silently accepted bad outputs.
- Thesis: typed actions + pre-execution validation + post-execution verification + bounded recovery improve reliability/safety at measurable overhead.
- Contributions: SafeAgent layer, CHIA integration, evaluation matrix, reproducible artifact.

## 2. SafeAgent design

Include compact architecture figure.

Describe:
- typed action interface;
- SafetyGate;
- CHIA execution adapter;
- verifier;
- bounded recovery loop;
- structured logging.

## 3. Experimental methodology

- target workload/platform;
- model/version;
- U0/S1/S2/S3/S4;
- tasks and fault injections;
- primary metrics;
- repetitions and limitations.

## 4. Results

Main table placeholder:

| Variant | Task success | Unsafe/invalid prevented | False rejects | Recovery | Runtime overhead |
|---|---:|---:|---:|---:|---:|
| U0 | TBD | TBD | TBD | TBD | 1.00× |
| S1 | TBD | TBD | TBD | TBD | TBD |
| S2 | TBD | TBD | TBD | TBD | TBD |
| S3 | TBD | TBD | TBD | TBD | TBD |
| S4 | TBD | TBD | TBD | TBD | TBD |

Do not fill any `TBD` from mocked runs.

## 5. Discussion / limitations

- SafetyGate is not a full sandbox/security proof.
- Results depend on task family/model/toolchain.
- Distinguish prevented invalid operations from broader adversarial security.
- Explain overhead/false-rejection tradeoff.

## 6. Conclusion

One paragraph: what was built, what was observed, what CHIA enables next.

## Acknowledgment of AI assistance

Required by hackathon instructions when AI assistance is used in writing. Final wording to be reviewed by human authors.
