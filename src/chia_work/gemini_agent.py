from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .actions import TypedAction


@dataclass(frozen=True)
class AgentProposal:
    action: TypedAction
    model: str
    rationale: str
    usage: dict[str, Any]
    raw_text: str


def _usage_to_dict(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump(exclude_none=True)
    result: dict[str, Any] = {}
    for name in (
        "prompt_token_count",
        "candidates_token_count",
        "total_token_count",
        "cached_content_token_count",
        "thoughts_token_count",
    ):
        value = getattr(usage, name, None)
        if value is not None:
            result[name] = value
    return result


class GeminiTypedActionAgent:
    """Ask Gemini for exactly one schema-constrained ``TypedAction`` proposal.

    Authentication modes:
    - Funded/GCP path: set ``GOOGLE_GENAI_USE_ENTERPRISE=true``,
      ``GOOGLE_CLOUD_PROJECT`` and ``GOOGLE_CLOUD_LOCATION``; ADC supplies auth.
    - Local developer path: set ``GEMINI_API_KEY`` (or ``GOOGLE_API_KEY``).

    The structured-output schema intentionally enumerates the parameter surface
    used by this hackathon harness. Unknown arbitrary JSON is not accepted.
    """

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    @staticmethod
    def _client():
        from google import genai

        enterprise = os.environ.get("GOOGLE_GENAI_USE_ENTERPRISE", "").lower() in {
            "1",
            "true",
            "yes",
        }
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION") or os.environ.get("GOOGLE_CLOUD_REGION")

        if enterprise or (project and location and not os.environ.get("GEMINI_API_KEY")):
            if not project or not location:
                raise RuntimeError(
                    "GCP Gemini mode requires GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION"
                )
            return genai.Client(enterprise=True, project=project, location=location)

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "No Gemini credentials: configure funded GCP env vars or GEMINI_API_KEY"
            )
        return genai.Client(api_key=api_key)

    def propose(self, task: str, *, context: str = "") -> AgentProposal:
        from google.genai import types
        from pydantic import BaseModel, ConfigDict, Field
        from typing import Literal

        class ActionParams(BaseModel):
            model_config = ConfigDict(extra="forbid")

            command: str | None = None
            payload: str | None = None
            config: str | None = None
            config_package: str | None = None
            target: str | None = None
            chipyard_path: str | None = None
            gemmini_tests_path: str | None = None
            make_jobs: int | None = None
            timeout_seconds: int | None = None
            build_timeout_seconds: int | None = None
            workload_build_timeout_seconds: int | None = None
            run_timeout_seconds: int | None = None
            max_cycles: int | None = None
            clean: bool | None = None
            clean_sim: bool | None = None
            collect_generated_src: bool | None = None

        class TypedActionProposal(BaseModel):
            model_config = ConfigDict(extra="forbid")

            kind: Literal["BUILD", "SIMULATE", "MODIFY_CONFIG", "RUN_BENCHMARK", "SHELL"]
            target: str = Field(min_length=1)
            params: ActionParams
            rationale: str

        system_instruction = (
            "You are the planning component of an agentic hardware/software co-design system. "
            "Propose exactly one next action. Prefer the least-privileged typed action that can "
            "advance the task. Use only fields exposed by the response schema; leave irrelevant "
            "fields unset. Do not claim that an action already ran. The action will be validated "
            "by an independent SafetyGate before execution."
        )
        contents = task if not context else f"Task:\n{task}\n\nCurrent context:\n{context}"

        client = self._client()
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=TypedActionProposal,
                    temperature=0.0,
                ),
            )
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, TypedActionProposal):
            proposal = parsed
        else:
            proposal = TypedActionProposal.model_validate_json(response.text)

        params = proposal.params.model_dump(exclude_none=True)
        action = TypedAction.from_dict(
            {"kind": proposal.kind, "target": proposal.target, "params": params}
        )
        return AgentProposal(
            action=action,
            model=self.model,
            rationale=proposal.rationale,
            usage=_usage_to_dict(getattr(response, "usage_metadata", None)),
            raw_text=response.text or "",
        )
