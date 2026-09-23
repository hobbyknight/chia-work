from contextlib import contextmanager

from chia_work.council.artifacts import ArtifactError, ArtifactStore


@contextmanager
def raises(expected):
    try:
        yield
    except expected:
        return
    raise AssertionError(f"expected {expected.__name__}")


def test_artifacts_are_immutable_and_hashable(tmp_path):
    store = ArtifactStore(tmp_path / "runs" / "r")
    ref = store.write_text("x.txt", "x", artifact_id="x", cycle_id="c", creator="t")
    assert store.verify(ref)
    with raises(ArtifactError):
        store.write_text("x.txt", "changed", artifact_id="x2", cycle_id="c", creator="t")
