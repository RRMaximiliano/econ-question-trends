from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "06_enrich"))

from evidence_tier_policy import (  # noqa: E402
    ACCEPTED_EVIDENCE_TIERS,
    EVIDENCE_TIER_OPTIONS,
    REJECTED_EVIDENCE_TIERS,
    evidence_tier_error_code,
    write_evidence_tier_policy,
)


class EvidenceTierPolicyTests(unittest.TestCase):
    def test_policy_defines_importable_and_rejected_tiers(self) -> None:
        self.assertEqual(
            ACCEPTED_EVIDENCE_TIERS,
            {"tier_a_formal_abstract", "tier_b_source_description", "tier_c_first_page_abstract_or_intro"},
        )
        self.assertEqual(REJECTED_EVIDENCE_TIERS, {"tier_d_title_only_triage", "tier_e_blocked"})
        self.assertEqual(EVIDENCE_TIER_OPTIONS[0]["value"], "")
        self.assertIn("tier_a_formal_abstract", [option["value"] for option in EVIDENCE_TIER_OPTIONS])

    def test_evidence_tier_error_codes_match_import_preflight_errors(self) -> None:
        self.assertEqual(evidence_tier_error_code(""), "missing_evidence_tier")
        self.assertEqual(evidence_tier_error_code("tier_d_title_only_triage"), "unimportable_evidence_tier")
        self.assertEqual(evidence_tier_error_code("unknown"), "invalid_evidence_tier")
        self.assertEqual(evidence_tier_error_code("tier_b_source_description"), "")

    def test_write_evidence_tier_policy_outputs_csv_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_csv = root / "policy.csv"
            report = root / "policy.md"

            policy = write_evidence_tier_policy(output_csv=output_csv, report_path=report)
            written = pd.read_csv(output_csv, dtype=str).fillna("")
            text = report.read_text(encoding="utf-8")

            self.assertEqual(len(policy), 5)
            self.assertEqual(len(written), 5)
            self.assertIn("tier_c_first_page_abstract_or_intro", set(written["evidence_tier"]))
            self.assertIn("Importable tiers", text)
            self.assertIn("tier_e_blocked", text)


if __name__ == "__main__":
    unittest.main()
