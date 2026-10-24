# Upstream checkouts

Managed by `python3 scripts/deps.py fetch all`. Each dependency is an independent
Git checkout at the exact commit in `dependencies.lock.json`; upstream source,
license files and Git provenance remain separate from the Unity repository.
Initial fetches are shallow. Use `git -C external/<module> fetch --unshallow`
when full upstream history is needed. Never copy source into Assets.
