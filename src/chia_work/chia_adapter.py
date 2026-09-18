from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChiaAvailability:
    available: bool
    detail: str


def detect_chia() -> ChiaAvailability:
    """Detect the upstream CHIA import without pretending integration is done."""
    try:
        from chia.base.ChiaFunction import ChiaFunction  # noqa: F401
    except Exception as exc:  # import/setup errors are useful during bootstrap
        return ChiaAvailability(False, f"CHIA import unavailable: {exc}")
    return ChiaAvailability(True, "CHIA import succeeded")


def execute_real_action(*_args, **_kwargs):
    raise NotImplementedError(
        "Real CHIA/Gemmini execution is Gate A work. Do not replace this with mocked research results."
    )
