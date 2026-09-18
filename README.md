# CHIA Work — SafeAgent for Agentic HW/SW Co-Design

Private working repository for the A³ CHIA Hackathon 2026.

> Current phase (2026-09-18): recovery sprint before the funded compute window. The repository now contains a real CHIA smoke path and a real CHIA → Chipyard → Gemmini build path; execution evidence is the remaining Gate A requirement.

## Research thesis

Agentic HW/SW co-design becomes risky when an LLM can directly invoke build, simulation, configuration, and shell-like tools. This project evaluates whether a lightweight `SafetyGate` around typed actions can prevent unsafe or invalid tool calls while preserving task success and enabling recovery.

## Target loop

```mermaid
flowchart LR
    A[Task / Prompt] --> B[Gemini Agent]
    B --> C[Typed Action]
    C --> D{SafetyGate}
    D -->|ALLOW| E[CHIA Tool / Gemmini Tool]
    D -->|DENY| B
    D -->|REPAIR| B
    E --> F[Build / Simulate / Measure]
    F --> G[Post-execution Verification]
    G -->|pass| H[Result]
    G -->|fail| B
    H --> I[Structured Log + Metrics]
```

## Internal milestones

| Date | Gate | Required output |
|---|---|---|
| Sep 18 | Gate A | Non-mocked CHIA smoke + real Gemmini build path wired; capture first real evidence |
| Sep 19 | Experiment freeze | U0/S1/S2/S3/S4 matrix, metrics, fault cases |
| Sep 20 | Gate B | Reproducible setup, GCP credential swap ready, paper skeleton mostly written |
| Sep 21 | Compute day 1 | Migration smoke test + baseline runs |
| Sep 22 | Compute day 2 | Main SafeAgent runs + repetitions |
| Sep 23 | Compute day 3 | Missing cells, ablations, reruns |
| Sep 24 AoE | Submission | 4-page PDF + open-source release + results + HotCRP |

## Start here

```bash
# 1) Read project control-plane
cat CURRENT-PLAN.md
cat CHECKPOINT.md
cat PACKAGE-STATUS.md

# 2) Local scaffold checks (no CHIA required)
make test
make smoke

# 3) Bootstrap the pinned official CHIA revision (Python 3.10.19)
bash scripts/bootstrap_chia.sh

# 4) Gate A.1: real CHIA/Ray round trip; must write mocked=false
make real-chia

# 5) Gate A.2 prerequisites: Linux + Docker + SSH-to-self
export THIS_MACHINE=$(hostname -I | awk '{print $1}')
export CHIA_WORK_DIR=$(pwd)
export USER=$(id -un)
make gemmini-up

# 6) Real CHIA → Chipyard → GemminiRocketConfig Verilator build
make real-gemmini

# 7) Tear the local CHIA cluster down when done
make gemmini-down
```

Dry-run outputs are explicitly marked `mocked=true` and **must never be used as paper results**. `scripts/summarize_results.py` rejects mocked rows by default.

## Gate A implementation now in-tree

- `src/chia_work/chia_adapter.py`: real `@ChiaFunction`/Ray dispatch with SHA round-trip verification.
- `scripts/real_chia_smoke.py`: writes the first eligible non-mocked CHIA record when execution succeeds.
- `src/chia_work/gemmini_adapter.py`: calls upstream `ChiselBuildNode.build` with `GemminiRocketConfig`.
- `configs/chia-gemmini-local.yaml`: single-host CHIA cluster template with `chipyard` and `verilator_run` workers.
- `scripts/real_gemmini_build.py`: records the real simulator build result, binary size and SHA256.
- `.github/workflows/gate-a-real-chia.yml`: clean CI smoke against pinned CHIA commit `16c35e92aaaf9511c6453bf94cd5cf589698f4e3`.

## Repository map

```text
.
├── AGENTS.md                    # rules for ChatGPT/Codex/other assistants
├── CURRENT-PLAN.md              # current execution plan
├── CHECKPOINT.md                # exact current state / next gate
├── PACKAGE-STATUS.md            # file-by-file readiness
├── configs/                     # experiment and CHIA cluster definitions; no secrets
├── docs/
│   ├── architecture/            # SafeAgent design
│   ├── experiments/             # matrix + metrics
│   ├── gcp/                     # funded-account migration runbook
│   ├── hackathon/               # official requirements snapshot
│   ├── integration/             # CHIA/Gemmini integration plan
│   └── submission/              # HotCRP/release checklist
├── paper/                       # 4-page paper outline
├── scripts/                     # bootstrap, smoke, real CHIA/Gemmini entrypoints
├── src/chia_work/               # typed actions, safety, logging, runner, adapters
├── tests/                       # unit tests for local safety/runner logic
├── logs/                        # generated logs (ignored except .gitkeep)
└── results/                     # generated results (ignored except .gitkeep)
```

## Official references

- CHIA: https://github.com/ucb-bar/chia
- CHIA docs: https://docs.chialoops.ai/
- Hackathon: https://agentic-arch.org/hackathon.html
- HotCRP: https://a3-chia-hackathon-26.hotcrp.com/

The official CHIA quickstart documents Python 3.10.19 for the supplied environment. The final hackathon artifact must be released publicly; this working repository is private for now and must be made public (or released to a public repository) before final submission.
