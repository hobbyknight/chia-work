import unittest

from chia_work.actions import ActionKind, TypedAction
from chia_work.agentic_loop import run_agentic_task
from chia_work.gemini_agent import AgentProposal


class _SequenceAgent:
    def __init__(self, actions):
        self.actions = list(actions)
        self.contexts = []

    def propose(self, task, *, context=""):
        self.contexts.append(context)
        action = self.actions.pop(0)
        return AgentProposal(
            action=action,
            model="fake-gemini",
            rationale="test",
            usage={"prompt_token_count": 10, "candidates_token_count": 5, "total_token_count": 15},
            raw_text="{}",
        )


class _CountingExecutor:
    mocked = False

    def __init__(self):
        self.calls = 0

    def execute(self, action):
        self.calls += 1
        return {
            "backend": "test",
            "status": "success",
            "exit_code": 0,
            "verified": True,
        }


def _good_action():
    return TypedAction(
        ActionKind.RUN_BENCHMARK,
        "gemmini-mvin-mvout",
        {
            "command": "chia:GemminiMvinMvout.run",
            "config": "GemminiRocketConfig",
            "make_jobs": 16,
            "build_timeout_seconds": 3600,
            "workload_build_timeout_seconds": 1800,
            "run_timeout_seconds": 900,
            "max_cycles": 20_000_000,
        },
    )


class AgenticLoopTests(unittest.TestCase):
    def test_s4_repairs_semantically_invalid_action_before_execution(self):
        bad = TypedAction(
            ActionKind.RUN_BENCHMARK,
            "gemmini-mvin-mvout",
            {"command": "chia:GemminiMvinMvout.run", "config": "UnknownConfig"},
        )
        agent = _SequenceAgent([bad, _good_action()])
        executor = _CountingExecutor()

        result = run_agentic_task(
            "run gemmini",
            variant="S4",
            task_id="repair-test",
            executor=executor,
            agent=agent,
            max_retries=2,
        ).final.record

        self.assertEqual(executor.calls, 1)
        self.assertEqual(result["retry_count"], 1)
        self.assertTrue(result["recovered"])
        self.assertEqual(result["verification"], "PASS")
        self.assertIn("rejected before execution", agent.contexts[1])
        self.assertEqual(result["agent_proposal_count"], 2)
        self.assertEqual(result["tool_call_count"], 1)
        self.assertEqual(result["api_token_usage"]["total_token_count"], 30)
        self.assertGreaterEqual(result["end_to_end_wall_time_seconds"], result["agent_wall_time_seconds"])

    def test_s2_does_not_retry(self):
        bad = TypedAction(
            ActionKind.RUN_BENCHMARK,
            "gemmini-mvin-mvout",
            {"command": "chia:GemminiMvinMvout.run", "config": "UnknownConfig"},
        )
        agent = _SequenceAgent([bad])
        executor = _CountingExecutor()
        result = run_agentic_task(
            "run gemmini",
            variant="S2",
            task_id="no-retry-test",
            executor=executor,
            agent=agent,
        ).final.record
        self.assertEqual(executor.calls, 0)
        self.assertEqual(result["retry_count"], 0)
        self.assertFalse(result["recovery_enabled"])
        self.assertEqual(result["tool_call_count"], 0)

    def test_controlled_seed_is_not_counted_as_agent_proposal(self):
        bad_seed = TypedAction(
            ActionKind.RUN_BENCHMARK,
            "gemmini-mvin-mvout",
            {
                "command": "chia:GemminiMvinMvout.run",
                "config": "GemminiRocketConfig",
                "make_jobs": 999,
            },
        )
        agent = _SequenceAgent([_good_action()])
        executor = _CountingExecutor()
        loop = run_agentic_task(
            "repair the approved workload",
            variant="S4",
            task_id="controlled-seed",
            executor=executor,
            agent=agent,
            initial_action=bad_seed,
        )
        result = loop.final.record
        self.assertEqual(loop.attempts[0]["action_source"], "controlled_seed")
        self.assertEqual(result["agent_proposal_count"], 1)
        self.assertEqual(result["tool_call_count"], 1)
        self.assertTrue(result["recovered"])


if __name__ == "__main__":
    unittest.main()
