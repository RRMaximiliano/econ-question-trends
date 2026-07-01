from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))

from econqt_common import (  # noqa: E402
    contact_email,
    ensure_dirs,
    get_json,
    load_journals,
    openalex_source_id_short,
    project_root_from_arg,
    utc_now_iso,
    write_json,
    write_log,
)


def collect_openalex(project_root: Path, start_year: int, end_year: int, run_id: str) -> None:
    ensure_dirs(project_root)
    journals = load_journals(project_root)
    out_dir = project_root / "data" / "raw" / "openalex" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    log_lines = [
        f"source=openalex",
        f"run_id={run_id}",
        f"started_utc={utc_now_iso()}",
        f"start_year={start_year}",
        f"end_year={end_year}",
    ]

    email = contact_email()
    base_url = "https://api.openalex.org/works"

    for journal in journals:
        journal_short = journal["journal_short"]
        source_id = openalex_source_id_short(journal["openalex_source_id"])
        cursor = "*"
        page = 1
        total_items = 0

        while True:
            params = {
                "filter": (
                    f"primary_location.source.id:{source_id},"
                    f"from_publication_date:{start_year}-01-01,"
                    f"to_publication_date:{end_year}-12-31"
                ),
                "per-page": 200,
                "cursor": cursor,
                "sort": "publication_date:asc",
            }
            if email:
                params["mailto"] = email

            try:
                payload, query_url = get_json(base_url, params, source="openalex")
            except Exception as exc:  # noqa: BLE001
                error_path = out_dir / f"{journal_short}_page_{page:04d}_error.json"
                write_json(
                    error_path,
                    {
                        "metadata": {
                            "source": "openalex",
                            "journal_short": journal_short,
                            "journal": journal["journal"],
                            "openalex_source_id": journal["openalex_source_id"],
                            "start_year": start_year,
                            "end_year": end_year,
                            "run_id": run_id,
                            "page": page,
                            "collected_utc": utc_now_iso(),
                        },
                        "error": repr(exc),
                    },
                )
                log_lines.append(f"{journal_short}: ERROR page={page} error={repr(exc)}")
                break

            items = payload.get("results", [])
            total_items += len(items)
            page_path = out_dir / f"{journal_short}_page_{page:04d}.json"
            write_json(
                page_path,
                {
                    "metadata": {
                        "source": "openalex",
                        "journal_short": journal_short,
                        "journal": journal["journal"],
                        "openalex_source_id": journal["openalex_source_id"],
                        "start_year": start_year,
                        "end_year": end_year,
                        "run_id": run_id,
                        "page": page,
                        "query_url": query_url,
                        "collected_utc": utc_now_iso(),
                    },
                    "response": payload,
                },
            )

            next_cursor = payload.get("meta", {}).get("next_cursor")
            if not items or not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
            page += 1

        log_lines.append(f"{journal_short}: items={total_items}")

    write_json(
        out_dir / "run_metadata.json",
        {
            "source": "openalex",
            "run_id": run_id,
            "start_year": start_year,
            "end_year": end_year,
            "finished_utc": utc_now_iso(),
        },
    )
    write_log(project_root, f"openalex_{run_id}.log", log_lines + [f"finished_utc={utc_now_iso()}"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--run-id", default=os.environ.get("EQT_RUN_ID") or utc_now_iso().replace(":", ""))
    args = parser.parse_args()

    collect_openalex(
        project_root_from_arg(args.project_root),
        args.start_year,
        args.end_year,
        args.run_id,
    )


if __name__ == "__main__":
    main()
