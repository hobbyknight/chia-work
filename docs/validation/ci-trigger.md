# Gate A local-harness validation

This file exists to create a pull-request-triggered CI run for the Sep 18 Gate A harness snapshot.

The PR is considered useful evidence only for the environment-independent layer:

- module imports under Python 3.10;
- unit tests for SafetyGate and runner behavior;
- S4 feedback/retry logic with test doubles;
- dry-run plumbing;
- counterfactual safety challenge invariants.

It does **not** prove real CHIA, Gemini, Docker, Chipyard, Gemmini, or Verilator execution. Those remain separate Gate A evidence requirements.
