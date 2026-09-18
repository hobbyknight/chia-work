# GCP funded-account migration runbook

The organizers stated that the short-term account is a **new GCP account/project**, so the project must tolerate a credential/project swap without code edits.

## Before Sep 21

- [ ] No project ID hard-coded in source.
- [ ] No key/token in git history.
- [ ] `.env.example` lists all required variables without values.
- [ ] Tool images/dependencies can be rebuilt or pulled from the new account.
- [ ] Any GCS bucket names, regions, quotas, and service APIs are documented.
- [ ] A smoke test exists that is cheap and finishes quickly.
- [ ] Run manifests can be resumed after failure.

## When credentials arrive

1. Store credentials outside the repository.
2. Export/inject:

```bash
export GOOGLE_CLOUD_PROJECT="..."
export GOOGLE_APPLICATION_CREDENTIALS="/secure/path/account.json"
export GOOGLE_CLOUD_REGION="us-central1"
export GEMINI_API_KEY="..."   # only if the provided setup actually requires a key
```

3. Confirm active identity/project with the relevant GCP CLI/API.
4. Enable only required APIs/services.
5. Run the smallest smoke test.
6. Confirm logs record the project/run identity but do **not** record secrets.
7. Freeze environment after a successful smoke test.
8. Start U0 baseline before expensive variants.

## Failure policy

If migration breaks, prioritize restoring one known-good benchmark path. Do not use compute-day time for architecture refactors unless the existing path is fundamentally unusable.
