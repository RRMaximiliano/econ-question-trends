# Data Directory

This directory is a local artifact store and is ignored by git by default.

Expected subdirectories:

- `raw/`: raw API responses from Crossref and OpenAlex.
- `intermediate/`: caches, validation packets, recovery packets, staged imports, and PDF/OCR artifacts.
- `final/`: analysis-ready article-level CSV files.

For GitHub, do not commit the full data tree. For replication, archive the required artifacts separately and restore them under these paths before running the commands in `REPLICATION.md`.

