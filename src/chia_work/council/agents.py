"""Fixed L0/L1/L2/L3 templates and the optional ADK-backed model adapter."""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Iterable, TypeVar

from pydantic import BaseModel, ValidationError

from .schemas import Direction, L0Decision, RoleSpec, TaskSpec


T = TypeVar("T", bound=BaseModel)


class TemplateError(RuntimeError):
    pass


class OutputExtractionError(TemplateError):
    pass


class SchemaOutputError(TemplateError):
    pass


class TransientServiceError(TemplateError):
    pass


class AgentTemplate:
    level: str

    def __init__(self, instance_id: str, instruction: str, *, model: str | None = None):
        self.instance_id = instance_id
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
        self.instruction = instruction
        self.adk_agent = self.make_adk_agent()

    def make_adk_agent(self, output_schema: type[BaseModel] | None = None):
        try:
            from google.adk.agents import LlmAgent
            kwargs: dict[str, Any] = {
                "name": self.instance_id.replace("-", "_"),
                "model": self.model,
                "instruction": self.instruction,
                "mode": "task",
                "include_contents": "none",
            }
            if output_schema is not None:
                kwargs["output_schema"] = output_schema
            return LlmAgent(**kwargs)
        except Exception as exc:
            raise TemplateError(f"ADK agent template initialization failed: {exc}") from exc


class L0Template(AgentTemplate):
    level = "L0"

    def __init__(self, instance_id: str = "l0"):
        super().__init__(instance_id, "You are the single strategic L0. Return only the requested JSON schema. Never directly execute CHIA or invoke an executor, shell command, Ray execution, hardware, or any execution backend. You may propose or request a governed execution using the existing typed proposal/action interface. A proposal is not execution. Only the deterministic governed system may validate, authorize or deny, and execute an approved action after all existing governance and safety checks.")


class L1CoordinatorTemplate(AgentTemplate):
    level = "L1"

    def __init__(self, instance_id: str = "l1-coordinator"):
        super().__init__(instance_id, "You are a deterministic L1 coordinator. Manage state and artifacts; do not select science.")


class L1SynthesisTemplate(AgentTemplate):
    level = "L1"

    def __init__(self, instance_id: str = "l1-synthesis"):
        super().__init__(instance_id, "Summarize supplied reports and expose open questions. Do not choose the next scientific direction.")


class L2Template(AgentTemplate):
    level = "L2"

    def __init__(self, instance_id: str):
        super().__init__(instance_id, "You are an L2 specialist using only your RoleSpec and supplied artifacts. Return concise structured reports.")


class L3Template(AgentTemplate):
    level = "L3"

    def __init__(self, instance_id: str):
        super().__init__(instance_id, "You are an L3 leaf executor. Read only granted inputs and produce the required artifact bundle.")


class ADKJsonAgent:
    """Runs one isolated ADK LLM session with bounded retries and strict validation."""

    _last_call_at: float | None = None

    def __init__(
        self,
        template: AgentTemplate,
        *,
        call_interval_seconds: float = 5.0,
        service_backoffs: tuple[float, float] = (5.0, 10.0),
    ):
        self.template = template
        self._loop = asyncio.new_event_loop()
        self.call_interval_seconds = call_interval_seconds
        self.service_backoffs = service_backoffs

    def call(self, prompt: str, output_type: type[T], *, max_retries: int = 1) -> T:
        schema_attempts = 0
        service_retries = 0
        last_error: Exception | None = None
        while True:
            try:
                self._pace_calls()
                payload = self._loop.run_until_complete(self._call_async(prompt, output_type))
                return self.validate_output(payload, output_type)
            except (OutputExtractionError, SchemaOutputError, ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
                if schema_attempts >= max_retries:
                    raise TemplateError(f"Gemini output failed schema validation after {max_retries} retries: {last_error}") from last_error
                schema_attempts += 1
            except Exception as exc:
                if not self.is_transient_service_error(exc):
                    raise TemplateError(f"Gemini call failed without retry: {exc}") from exc
                last_error = exc
                if service_retries >= len(self.service_backoffs):
                    raise TransientServiceError(f"Gemini service retry limit exhausted after {service_retries} retries: {exc}") from exc
                time.sleep(self.service_backoffs[service_retries])
                service_retries += 1

    @staticmethod
    def validate_output(payload: Any, output_type: type[T]) -> T:
        """Validate ADK output without repairing or adding any fields."""
        if isinstance(payload, str):
            payload = json.loads(payload)
        try:
            return output_type.model_validate(payload)
        except ValidationError as exc:
            raise SchemaOutputError(str(exc)) from exc

    @staticmethod
    def extract_output(events: Iterable[Any]) -> Any:
        """Extract structured output first, then use content text only as fallback."""
        structured: Any = None
        found_structured = False
        fallback_text: str | None = None
        for event in events:
            event_output = getattr(event, "output", None)
            if event_output is not None:
                structured = event_output
                found_structured = True
            content = getattr(event, "content", None)
            parts = getattr(content, "parts", None) if content is not None else None
            if parts:
                for part in parts:
                    text = getattr(part, "text", None)
                    if text:
                        fallback_text = text
        if found_structured:
            return structured
        if fallback_text is not None:
            return json.loads(fallback_text)
        raise OutputExtractionError("ADK returned no output or content text")

    def _pace_calls(self) -> None:
        if self.call_interval_seconds <= 0:
            return
        now = time.monotonic()
        if ADKJsonAgent._last_call_at is not None:
            remaining = self.call_interval_seconds - (now - ADKJsonAgent._last_call_at)
            if remaining > 0:
                time.sleep(remaining)
        ADKJsonAgent._last_call_at = time.monotonic()

    @staticmethod
    def is_transient_service_error(exc: BaseException) -> bool:
        seen: set[int] = set()
        current: BaseException | None = exc
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            status = getattr(current, "status_code", None) or getattr(current, "code", None)
            if isinstance(status, int) and (status == 429 or 500 <= status <= 599):
                return True
            text = str(current).lower()
            if "429" in text or "resource_exhausted" in text or "resource exhausted" in text:
                return True
            if "internal" in text or "server error" in text or "service unavailable" in text:
                return True
            current = current.__cause__ or current.__context__
        return False

    async def _call_async(self, prompt: str, output_type: type[BaseModel]) -> Any:
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        agent = self.template.make_adk_agent(output_schema=output_type)
        runner = InMemoryRunner(agent=agent, app_name=f"safeagent-{self.template.instance_id}")
        await runner.session_service.create_session(
            app_name=runner.app_name, user_id=self.template.instance_id,
            session_id=f"session-{self.template.instance_id}",
        )
        message = types.Content(role="user", parts=[types.Part(text=prompt)])
        events: list[Any] = []
        try:
            async for event in runner.run_async(
                user_id=self.template.instance_id,
                session_id=f"session-{self.template.instance_id}",
                new_message=message,
            ):
                events.append(event)
        finally:
            await runner.close()
        return self.extract_output(events)
