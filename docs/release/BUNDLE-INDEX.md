# Immutable bundle index

| Bundle | Purpose | Verification |
|---|---|---|
| `20260923T094000Z-safety-v3-closeout` | Safety-v3 closeout, source, diff, tests, replay, historical-verification records | `sha256sum -c SHA256SUMS.txt` (398 files) |
| `20260923T101417Z-colab-shutdown-handoff` | shutdown handoff: Ray idle state and release handoff | `sha256sum -c SHA256SUMS.txt` |
| `<UTC>-final-release-closeout` | this release's source snapshot, Git recovery bundle, regression logs and indexes | `sha256sum -c SHA256SUMS.txt` |

To recover a release repository, clone the Git bundle: `git clone safeagent-final-release.bundle recovered`, then run `git -C recovered fsck --full` and compare its `HEAD` to `branch-head.txt`. To recover a source snapshot, extract `source-snapshot.tar.gz`, enter it, and run `sha256sum -c SOURCE-SNAPSHOT-SHA256SUMS.txt`.

Bundles are immutable evidence. Verify them in place; never regenerate a historical manifest.
