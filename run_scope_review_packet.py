from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / "code" / "05_analysis"))

from scope_review_audit import run_scope_review_packet  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="outputs/tables/enriched/scope_review_candidates.csv")
    parser.add_argument("--existing-packet", default="data/intermediate/scope_review/scope_review_packet.csv")
    parser.add_argument("--output-packet", default="data/intermediate/scope_review/scope_review_packet.csv")
    parser.add_argument("--output-completion", default="outputs/tables/enriched/scope_review_completion.csv")
    parser.add_argument("--output-form", default="data/intermediate/scope_review_forms/scope_review_packet.html")
    parser.add_argument("--output-guide", default="outputs/tables/enriched/scope_review_guide.csv")
    parser.add_argument("--output-guide-summary", default="outputs/tables/enriched/scope_review_guide_summary.csv")
    parser.add_argument("--guide-report", default="docs/scope_review_guide.md")
    parser.add_argument("--report", default="docs/scope_review_packet.md")
    args = parser.parse_args()
    run_scope_review_packet(
        candidates_path=Path(args.candidates),
        existing_packet_path=Path(args.existing_packet) if args.existing_packet else None,
        output_packet=Path(args.output_packet),
        output_completion=Path(args.output_completion),
        output_form=Path(args.output_form),
        output_guide=Path(args.output_guide) if args.output_guide else None,
        output_guide_summary=Path(args.output_guide_summary) if args.output_guide_summary else None,
        guide_report_path=Path(args.guide_report) if args.guide_report else None,
        report_path=Path(args.report),
    )


if __name__ == "__main__":
    main()
