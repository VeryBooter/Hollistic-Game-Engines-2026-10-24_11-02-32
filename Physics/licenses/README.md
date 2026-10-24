# Upstream license records

`index.json` records the pinned commit, upstream filename and SHA-256 of each copied
top-level license/copyright file. Originals are also retained in the independent
upstream checkouts, including nested component notices. The copies here are license
text, not copied solver source.

`dependencies.lock.json` contains short license labels for discovery; the original
texts and component-specific notices govern. This inventory is not a complete
redistribution bundle for every optional backend or transitive native library.
Python wheel distributions retain their own `.dist-info` notices in `.venv`.
No license for the pre-existing Unity project is changed by this integration.
