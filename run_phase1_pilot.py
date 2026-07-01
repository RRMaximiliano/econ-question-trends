from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_step(project_root: Path, script: str, start_year: int, end_year: int, run_id: str) -> None:
    cmd = [
        sys.executable,
        str(project_root / script),
        "--project-root",
        str(project_root),
        "--start-year",
        str(start_year),
        "--end-year",
        str(end_year),
        "--run-id",
        run_id,
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=project_root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--skip-collect", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve() if args.project_root else Path.cwd().resolve()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.environ["EQT_RUN_ID"] = run_id

    if not args.skip_collect:
        run_step(project_root, "code/01_collect/collect_crossref.py", args.start_year, args.end_year, run_id)
        run_step(project_root, "code/01_collect/collect_openalex.py", args.start_year, args.end_year, run_id)
    run_step(project_root, "code/02_clean/build_articles_pilot.py", args.start_year, args.end_year, run_id)
    run_step(project_root, "code/03_diagnostics/make_phase1_reports.py", args.start_year, args.end_year, run_id)

    print(f"Completed Phase 1 pilot run_id={run_id}")
    print("Main output: data/final/articles_pilot.csv")
    print("Coverage report: docs/coverage_report.md")


if __name__ == "__main__":
    main()
