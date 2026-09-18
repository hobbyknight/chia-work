from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ActionKind(str, Enum):
    BUILD = "BUILD"
    SIMULATE = "SIMULATE"
    MODIFY_CONFIG = "MODIFY_CONFIG"
    RUN_BENCHMARK = "RUN_BENCHMARK"
    SHELL = "SHELL"


@dataclass(frozen=True)
class TypedAction:
    kind: ActionKind
    target: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TypedAction":
        return cls(
            kind=ActionKind(data["kind"]),
            target=str(data.get("target", "")),
            params=dict(data.get("params", {})),
        )
