from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from run_manual_validation_overlap import overlap_packet_identity_errors  # noqa: E402


class ManualValidationOverlapRunnerTests(unittest.TestCase):
    def test_overlap_packet_identity_errors_accept_valid_packet(self) -> None:
        sample = pd.DataFrame(
            [
                {"validation_id": "VAL0001", "article_id": "a1"},
                {"validation_id": "VAL0002", "article_id": "a2"},
            ]
        )
        packet = pd.DataFrame(
            [
                {"overlap_id": "OV0001", "validation_id": "VAL0001", "article_id": "a1"},
                {"overlap_id": "OV0002", "validation_id": "VAL0002", "article_id": "a2"},
            ]
        )

        errors = overlap_packet_identity_errors(sample, packet, expected_rows=2)

        self.assertTrue(errors.empty)

    def test_overlap_packet_identity_errors_flag_duplicate_and_unknown_rows(self) -> None:
        sample = pd.DataFrame(
            [
                {"validation_id": "VAL0001", "article_id": "a1"},
                {"validation_id": "VAL0002", "article_id": "a2"},
            ]
        )
        packet = pd.DataFrame(
            [
                {"overlap_id": "OV0001", "validation_id": "VAL0001", "article_id": "a1"},
                {"overlap_id": "OV0001", "validation_id": "VAL0001", "article_id": "a1"},
                {"overlap_id": "OV0003", "validation_id": "VAL9999", "article_id": "missing"},
            ]
        )

        errors = overlap_packet_identity_errors(sample, packet, expected_rows=2)

        self.assertIn("overlap_packet_row_count_mismatch", set(errors["error"]))
        self.assertIn("duplicate_overlap_id", set(errors["error"]))
        self.assertIn("duplicate_overlap_sample_row", set(errors["error"]))
        self.assertIn("overlap_row_not_in_sample", set(errors["error"]))

    def test_overlap_packet_identity_errors_flag_missing_overlap_id(self) -> None:
        sample = pd.DataFrame([{"validation_id": "VAL0001", "article_id": "a1"}])
        packet = pd.DataFrame([{"overlap_id": "", "validation_id": "VAL0001", "article_id": "a1"}])

        errors = overlap_packet_identity_errors(sample, packet, expected_rows=1)

        self.assertEqual(errors.iloc[0]["error"], "missing_overlap_id")


if __name__ == "__main__":
    unittest.main()
