# Code Directory

The source tree is organized by workflow stage:

- `01_collect/`: public metadata collection.
- `02_clean/`: article-level panel construction.
- `03_diagnostics/`: coverage and data-quality reports.
- `04_classify/`: rule-based, LLM, and validation-sample workflows.
- `05_analysis/`: diagnostics, validation gate, status, scope review, and trends.
- `06_enrich/`: text enrichment, PDF/OCR recovery, recovery queues, and source-route scans.
- `lib/`: shared utility functions.

Top-level `run_*.py` scripts are the stable command-line entry points. Prefer those scripts or the `Makefile` targets over importing modules directly.

