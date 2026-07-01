PYTHON ?= python3
CLASSIFIED ?= data/final/articles_classified_enriched_pilot.csv
VALIDATION ?= data/intermediate/manual_validation_sample.csv

.PHONY: help install test diagnostics validation-gate status refresh trends site-data reproduce-offline clean-local

help:
	@echo "Common targets:"
	@echo "  make install             Install Python dependencies from requirements.txt"
	@echo "  make test                Run unit tests"
	@echo "  make diagnostics         Refresh classification diagnostics"
	@echo "  make validation-gate     Refresh validation gate"
	@echo "  make status              Refresh project status and workboard"
	@echo "  make refresh             Refresh full human-review handoff"
	@echo "  make trends              Generate trend tables from enriched classified data"
	@echo "  make site-data           Export current trend tables for the static dashboard"
	@echo "  make reproduce-offline   Rebuild from saved raw API responses"
	@echo "  make clean-local         Remove Python and OS cache files"

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest discover -s tests

diagnostics:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) run_classification_diagnostics.py --classified $(CLASSIFIED) --validation $(VALIDATION) --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md

validation-gate:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) run_validation_gate.py

status: diagnostics validation-gate
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) run_project_status.py
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) run_human_review_workboard.py

refresh:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) run_human_review_refresh.py

trends:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) run_trend_summary.py --classified $(CLASSIFIED) --output-dir outputs/tables/enriched --report docs/recent_trend_summary_enriched.md

site-data:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/build_trend_site_data.py

reproduce-offline:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) run_phase1_pilot.py --start-year 1975 --end-year 2025 --run-id 1975_2025_yearly_crossref_20260628T --skip-collect

clean-local:
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	find . -name ".DS_Store" -type f -delete
	find . -name "*.pyc" -type f -delete
