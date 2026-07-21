# Release Process

00SWIFT uses semantic version tags (`vMAJOR.MINOR.PATCH`) and GitHub Releases.

## Preconditions

- The release commit is on `main`.
- Pull-request CI and CodeQL are green.
- The local/full suite passes on supported Python versions.
- Security-impacting changes have explicit tests and review notes.
- `backend/version.py`, `pyproject.toml`, `CHANGELOG.md`, and documentation agree on the version.
- No secrets, generated certificates, databases, coverage files, or research artifacts are tracked.

## Release steps

1. Prepare a focused release pull request.
2. Run `make check coverage security` and a Docker build.
3. Merge only after all required checks pass.
4. Verify the `main` commit checks.
5. Create and publish `vX.Y.Z` with curated notes.
6. The release workflow re-validates the tag and uploads a source archive and dependency manifest.
7. Verify assets, documentation links, and the clean-start procedure.
8. Announce known limitations and upgrade notes.

## Hotfixes

Branch from the affected supported tag or current `main`, add a regression test, increment PATCH, and follow the same CI/release path. Do not silently replace an existing tag or release asset.

## Deprecation

Document deprecation in the changelog and API guide. Keep compatibility for at least one minor line when feasible; security fixes may remove unsafe behavior immediately.
