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


if __name__ == "__main__":
    unittest.main()
