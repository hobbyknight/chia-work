import json
from types import SimpleNamespace

from pydantic import BaseModel

from chia_work.council.agents import (
    ADKJsonAgent,
    OutputExtractionError,
    SchemaOutputError,
    TransientServiceError,
)


class Output(BaseModel):
    value: int


def event(*, output=None, text=None):
    content = None if text is None else SimpleNamespace(parts=[SimpleNamespace(text=text)])
    return SimpleNamespace(output=output, content=content)


def test_event_output_dict_and_string_are_validated():
    assert ADKJsonAgent.validate_output({"value": 1}, Output).value == 1
    assert ADKJsonAgent.validate_output('{"value": 2}', Output).value == 2
    assert ADKJsonAgent.validate_output(ADKJsonAgent.extract_output([event(output='{"value": 3}')]), Output).value == 3


def test_event_output_has_priority_over_text_fallback():
    payload = ADKJsonAgent.extract_output([event(output={"value": 3}, text='{"value": 4}')])
    assert payload == {"value": 3}
    assert ADKJsonAgent.extract_output([event(text='{"value": 5}')]) == {"value": 5}


def test_missing_output_fails_and_bad_schema_is_not_repaired():
    try:
        ADKJsonAgent.extract_output([event()])
    except OutputExtractionError:
        pass
    else:
        raise AssertionError("missing output was accepted")
    try:
        ADKJsonAgent.validate_output({"value": "not-an-int"}, Output)
    except SchemaOutputError:
        pass
    else:
        raise AssertionError("bad schema was repaired or accepted")


def test_service_retry_is_bounded_without_waiting():
    class FakeAgent:
        def __init__(self):
            self.calls = 0

        def make_adk_agent(self, output_schema=None):
            return object()

    agent = ADKJsonAgent(FakeAgent(), call_interval_seconds=0, service_backoffs=(0, 0))
    attempts = []

    def fail(_prompt, _output_type):
        attempts.append(True)
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    agent._call_async = fail
    try:
        agent.call("x", Output, max_retries=0)
    except TransientServiceError:
        pass
    else:
        raise AssertionError("service retry was not bounded")
    assert len(attempts) == 3
