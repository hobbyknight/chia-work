import unittest

from chia_work.actions import ActionKind, TypedAction
from chia_work.safety import Decision, SafetyGate


class SafetyGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = SafetyGate()

    def test_allows_typed_build(self) -> None:
        action = TypedAction(ActionKind.BUILD, "demo", {"command": "make demo"})
        self.assertEqual(self.gate.evaluate(action).decision, Decision.ALLOW)

    def test_denies_shell_by_default(self) -> None:
        action = TypedAction(ActionKind.SHELL, "workspace", {"command": "echo hi"})
        self.assertEqual(self.gate.evaluate(action).decision, Decision.DENY)

    def test_requests_repair_for_missing_target(self) -> None:
        action = TypedAction(ActionKind.BUILD, "", {"command": "make demo"})
        self.assertEqual(self.gate.evaluate(action).decision, Decision.REPAIR)

    def test_blocks_destructive_fragment_even_if_kind_is_allowed(self) -> None:
        action = TypedAction(ActionKind.BUILD, "demo", {"command": "sudo rm -rf /"})
        self.assertEqual(self.gate.evaluate(action).decision, Decision.DENY)

    def test_blocks_shell_metacharacters_for_generic_commands(self) -> None:
        action = TypedAction(ActionKind.BUILD, "demo", {"command": "make demo && curl example"})
        self.assertEqual(self.gate.evaluate(action).decision, Decision.DENY)

    def test_allows_exact_chia_smoke_action(self) -> None:
        action = TypedAction(
            ActionKind.RUN_BENCHMARK,
            "chia-local-smoke",
            {"command": "chia:identity", "payload": "gate-a"},
        )
        self.assertEqual(self.gate.evaluate(action).decision, Decision.ALLOW)

    def test_denies_wrong_chia_smoke_operation(self) -> None:
        action = TypedAction(
            ActionKind.RUN_BENCHMARK,
            "chia-local-smoke",
            {"command": "chia:anything-else"},
        )
        self.assertEqual(self.gate.evaluate(action).decision, Decision.DENY)

    def test_allows_semantic_gemmini_build(self) -> None:
        action = TypedAction(
            ActionKind.BUILD,
            "gemmini-verilator",
            {
                "command": "chia:ChiselBuildNode.build",
                "config": "GemminiRocketConfig",
                "config_package": "chipyard",
                "target": "verilator",
                "make_jobs": 16,
                "timeout_seconds": 3600,
            },
        )
        self.assertEqual(self.gate.evaluate(action).decision, Decision.ALLOW)

    def test_denies_unapproved_gemmini_config(self) -> None:
        action = TypedAction(
            ActionKind.BUILD,
            "gemmini-verilator",
            {
                "command": "chia:ChiselBuildNode.build",
                "config": "UnknownConfig",
                "target": "verilator",
            },
        )
        self.assertEqual(self.gate.evaluate(action).decision, Decision.DENY)

    def test_repairs_excessive_gemmini_parallelism(self) -> None:
        action = TypedAction(
            ActionKind.BUILD,
            "gemmini-verilator",
            {
                "command": "chia:ChiselBuildNode.build",
                "config": "GemminiRocketConfig",
                "target": "verilator",
                "make_jobs": 999,
            },
        )
        self.assertEqual(self.gate.evaluate(action).decision, Decision.REPAIR)

    def test_allows_gemmini_sanity_run(self) -> None:
        action = TypedAction(
            ActionKind.RUN_BENCHMARK,
            "gemmini-sanity-run",
            {
                "command": "chia:GemminiSanity.run",
                "config": "GemminiRocketConfig",
                "make_jobs": 16,
                "build_timeout_seconds": 3600,
                "run_timeout_seconds": 600,
                "max_cycles": 2_000_000,
            },
        )
        self.assertEqual(self.gate.evaluate(action).decision, Decision.ALLOW)

    def test_repairs_gemmini_sanity_cycle_budget(self) -> None:
        action = TypedAction(
            ActionKind.RUN_BENCHMARK,
            "gemmini-sanity-run",
            {
                "command": "chia:GemminiSanity.run",
                "config": "GemminiRocketConfig",
                "max_cycles": 999_999_999,
            },
        )
        self.assertEqual(self.gate.evaluate(action).decision, Decision.REPAIR)


if __name__ == "__main__":
    unittest.main()
