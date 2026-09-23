"""Immutable file-backed memory and SHA256 artifact indexing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .schemas import ArtifactRef, Record, utc_now


class ArtifactError(RuntimeError):
    pass


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "ledger").mkdir(exist_ok=True)
        self.index_path = self.root / "ledger" / "artifact-index.jsonl"

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _write_once(self, relpath: str, data: bytes) -> tuple[Path, str]:
        path = self.root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ArtifactError(f"locked artifact already exists: {relpath}")
        path.write_bytes(data)
        return path, self._sha256(data)

    def _index(self, ref: ArtifactRef) -> ArtifactRef:
        with self.index_path.open("a", encoding="utf-8") as handle:
            handle.write(ref.stable_json() + "\n")
        return ref

    def write_json(
        self,
        relpath: str,
        value: Record | dict[str, Any],
        *,
        artifact_id: str,
        cycle_id: str,
        creator: str,
        parent_id: str | None = None,
        lineage_refs: list[str] | None = None,
        kind: str = "json",
    ) -> ArtifactRef:
        if isinstance(value, Record):
            payload = value.model_dump(mode="json")
        else:
            payload = value
        data = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
        _, digest = self._write_once(relpath, data)
        ref = ArtifactRef(
            id=artifact_id,
            cycle_id=cycle_id,
            creator=creator,
            created_at=utc_now(),
            parent_id=parent_id,
            lineage_refs=lineage_refs or [],
            path=relpath,
            sha256=digest,
            kind=kind,
        )
        return self._index(ref)

    def write_text(
        self,
        relpath: str,
        text: str,
        *,
        artifact_id: str,
        cycle_id: str,
        creator: str,
        parent_id: str | None = None,
        lineage_refs: list[str] | None = None,
        kind: str = "text",
    ) -> ArtifactRef:
        data = text.encode("utf-8")
        _, digest = self._write_once(relpath, data)
        ref = ArtifactRef(
            id=artifact_id,
            cycle_id=cycle_id,
            creator=creator,
            created_at=utc_now(),
            parent_id=parent_id,
            lineage_refs=lineage_refs or [],
            path=relpath,
            sha256=digest,
            kind=kind,
        )
        return self._index(ref)

    def read_json(self, ref: ArtifactRef | str) -> dict[str, Any]:
        path = self.root / (ref.path if isinstance(ref, ArtifactRef) else ref)
        return json.loads(path.read_text(encoding="utf-8"))

    def verify(self, ref: ArtifactRef) -> bool:
        path = self.root / ref.path
        return path.exists() and self._sha256(path.read_bytes()) == ref.sha256

    def all_refs(self) -> list[ArtifactRef]:
        if not self.index_path.exists():
            return []
        return [ArtifactRef.model_validate(json.loads(line)) for line in self.index_path.read_text(encoding="utf-8").splitlines() if line]

