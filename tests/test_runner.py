import unittest

from chia_work.actions import ActionKind, TypedAction
from chia_work.runner import run_action


class _RealSuccessExecutor:
    mocked = False

    def execute(self, action):
        return {"backend": "test-real", "status": "success", "exit_code": 0, "verified": True}


class _RealFailureExecutor:
    mocked = False

    def execute(self, action):
        raise RuntimeError("boom")


class RunnerTests(unittest.TestCase):
    def test_real_executor_produces_non_mocked_pass(self):
        action = TypedAction(ActionKind.BUILD, "demo", {"command": "build"})
        result = run_action(
            action,
            variant="S2",
            task_id="real-success",
            safety_enabled=True,
            executor=_RealSuccessExecutor(),
        ).record
        self.assertFalse(result["mocked"])
        self.assertEqual(result["verification"], "PASS")
        self.assertEqual(result["safety_decision"], "ALLOW")
        self.assertTrue(result["executed"])
        self.assertEqual(result["tool_call_count"], 1)
        self.assertEqual(result["backend"], "test-real")

    def test_executor_exception_is_preserved_as_failed_record(self):
        action = TypedAction(ActionKind.BUILD, "demo", {"command": "build"})
        result = run_action(
            action,
            variant="S2",
            task_id="real-failure",
            safety_enabled=True,
            executor=_RealFailureExecutor(),
        ).record
        self.assertFalse(result["mocked"])
        self.assertEqual(result["verification"], "FAIL")
        self.assertEqual(result["tool_result"]["error_type"], "RuntimeError")
        self.assertEqual(result["tool_result"]["error_message"], "boom")
        self.assertTrue(result["executed"])

    def test_blocked_action_has_zero_tool_calls(self):
        action = TypedAction(ActionKind.SHELL, "workspace", {"command": "echo hi"})
        result = run_action(
            action,
            variant="S1",
            task_id="blocked",
            safety_enabled=True,
            executor=_RealSuccessExecutor(),
        ).record
        self.assertEqual(result["safety_decision"], "DENY")
        self.assertFalse(result["executed"])
        self.assertEqual(result["tool_call_count"], 0)


if __name__ == "__main__":
    unittest.main()
