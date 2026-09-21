from __future__ import annotations

import unittest

from chia_work.gemini_agent import _call_with_transient_retries


class FakeApiError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class GeminiApiRetryTests(unittest.TestCase):
    def test_retries_429_with_bounded_exponential_delays(self) -> None:
        outcomes = [
            FakeApiError(429, "RESOURCE_EXHAUSTED"),
            FakeApiError(429, "RESOURCE_EXHAUSTED"),
            "ok",
        ]
        delays: list[float] = []

        def call():
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        result, events = _call_with_transient_retries(
            call,
            max_retries=3,
            base_delay_seconds=5,
            max_delay_seconds=8,
            sleep=delays.append,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(delays, [5, 8])
        self.assertEqual([event["status_code"] for event in events], [429, 429])
        self.assertEqual([event["reason"] for event in events], ["RESOURCE_EXHAUSTED"] * 2)

    def test_retries_503_but_not_non_transient_errors(self) -> None:
        delays: list[float] = []
        outcomes = [FakeApiError(503, "UNAVAILABLE"), "ok"]

        def transient_call():
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        result, events = _call_with_transient_retries(
            transient_call,
            max_retries=1,
            base_delay_seconds=1,
            max_delay_seconds=1,
            sleep=delays.append,
        )
        self.assertEqual(result, "ok")
        self.assertEqual(events[0]["reason"], "UNAVAILABLE")

        with self.assertRaises(FakeApiError):
            _call_with_transient_retries(
                lambda: (_ for _ in ()).throw(FakeApiError(400, "INVALID_ARGUMENT")),
                max_retries=3,
                base_delay_seconds=1,
                max_delay_seconds=1,
                sleep=delays.append,
            )


if __name__ == "__main__":
    unittest.main()
