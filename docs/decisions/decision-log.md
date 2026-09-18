# Decision log

This file records decisions that should not be silently reversed during the sprint.

## D001 — Dedicated repository

**Date:** 2026-09-18  
**Decision:** Use `ryandongic/chia-work` as the single working repository for CHIA Hackathon execution, experiments, paper scaffolding, and release preparation.  
**Reason:** Avoid scattering state across chats/repos and keep reproducibility artifacts together.

## D002 — Safety research scope

**Date:** 2026-09-18  
**Decision:** Focus on typed actions + pre-execution validation + post-execution verification + bounded recovery.  
**Reason:** This is measurable, fits the short sprint, and can be ablated as U0/S1/S2/S3/S4.

## D003 — No fake integration

**Date:** 2026-09-18  
**Decision:** Keep CHIA/Gemmini execution explicitly unimplemented until a real backend is connected. All local scaffolding outputs are marked `mocked=true`.  
**Reason:** Preserve scientific integrity and avoid accidentally treating plumbing tests as research evidence.

## D004 — Environment portability

**Date:** 2026-09-18  
**Decision:** GCP project IDs, keys, credentials, regions, and toolchain paths must come from environment/config, not source code.  
**Reason:** The funded account is a new account/project and must be swappable quickly.

## D005 — Scope lock until Gate A

**Date:** 2026-09-18  
**Decision:** Do not add dashboards, extra agents, or additional hardware targets until one real end-to-end CHIA-backed path passes.  
**Reason:** The project is implementation-late relative to the ideal timeline; end-to-end evidence is the critical path.
