from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

sys.path.append(str(PROJECT_ROOT / "code" / "04_classify"))

from run_manual_validation_calibration import (  # noqa: E402
    calibration_guide,
    calibration_kickoff_checklist,
    calibration_packet_profile,
    calibration_packet_identity_errors,
    calibration_row_progress,
    calibration_submission_identity_errors,
    load_calibration_submissions,
    remaining_calibration_packet,
    remaining_calibration_summary,
    remaining_calibration_submission_template,
    packet_with_calibration_guide,
    write_calibration_dashboard,
    write_calibration_guide_report,
    write_calibration_kickoff_report,
)
from validation_sample import reviewer_form_html  # noqa: E402


class ManualValidationCalibrationRunnerTests(unittest.TestCase):
    def test_calibration_guide_uses_only_packet_text_for_flags(self) -> None:
        packet = pd.DataFrame(
            [
                {
                    "calibration_id": "CAL0001",
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                    "title": "Forecasting Treatment Effects",
                    "abstract": "We estimate treatment effects and evaluate out-of-sample forecast accuracy for policy targeting.",
                },
                {
                    "calibration_id": "CAL0002",
                    "validation_id": "VAL0002",
                    "article_id": "a2",
                    "title": "A Title Without Abstract",
                    "abstract": "",
                },
            ]
        )
        rules = {
            "text_fields": ["title", "abstract"],
            "minimum_usable_text_chars": 120,
            "scoring": {"strong_weight": 2, "moderate_weight": 1, "dominance_margin": 2},
            "causal": {"strong_phrases": ["treatment effects"], "moderate_phrases": []},
            "predictive": {"strong_phrases": ["out-of-sample"], "moderate_phrases": ["forecast"]},
        }

        guide, summary = calibration_guide(packet, rules)
        indexed = guide.set_index("calibration_id")

        self.assertEqual(indexed.loc["CAL0001", "cue_profile"], "causal_and_predictive_cues")
        self.assertEqual(indexed.loc["CAL0001", "review_difficulty"], "high")
        self.assertIn("primary-focus", indexed.loc["CAL0001", "reviewer_focus"])
        self.assertEqual(indexed.loc["CAL0002", "text_status"], "no_abstract")
        self.assertIn("insufficient_text", indexed.loc["CAL0002", "reviewer_focus"])
        self.assertIn("cue_profile", set(summary["section"]))

    def test_packet_with_calibration_guide_adds_form_context_without_model_predictions(self) -> None:
        packet = pd.DataFrame(
            [
                {
                    "calibration_id": "CAL0001",
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                    "title": "Forecasting Treatment Effects",
                    "abstract": "Short abstract",
                    "manual_label": "",
                    "manual_confidence": "",
                    "manual_notes": "",
                    "reviewer_id": "",
                    "review_date": "",
                }
            ]
        )
        guide = pd.DataFrame(
            [
                {
                    "calibration_id": "CAL0001",
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                    "text_status": "usable_text",
                    "cue_profile": "causal_and_predictive_cues",
                    "review_difficulty": "high",
                    "reviewer_focus": "Apply the primary-focus rule.",
                    "classification_text_chars": "250",
                    "causal_cue_terms": "treatment effects",
                    "predictive_cue_terms": "forecast",
                }
            ]
        )

        form_packet = packet_with_calibration_guide(packet, guide)
        html = reviewer_form_html(form_packet, title="Calibration")

        self.assertNotIn("validation_category", form_packet.columns)
        self.assertNotIn("classification_reason", form_packet.columns)
        self.assertIn("cue_profile", form_packet.columns)
        self.assertIn("causal_and_predictive_cues", html)
        self.assertIn("Reviewer focus", html)
        self.assertNotIn("classification_reason", html)

    def test_calibration_packet_profile_counts_abstracts(self) -> None:
        packet = pd.DataFrame(
            [
                {"calibration_id": "CAL0001", "abstract": "This is an abstract."},
                {"calibration_id": "CAL0002", "abstract": ""},
            ]
        )

        profile = calibration_packet_profile(packet)
        lookup = dict(zip(profile["metric"], profile["value"]))

        self.assertEqual(lookup["packet_rows"], 2)
        self.assertEqual(lookup["rows_with_abstract"], 1)
        self.assertEqual(lookup["rows_without_abstract"], 1)

    def test_calibration_packet_identity_errors_accept_valid_packet(self) -> None:
        sample = pd.DataFrame(
            [
                {"validation_id": "VAL0001", "article_id": "a1"},
                {"validation_id": "VAL0002", "article_id": "a2"},
            ]
        )
        packet = pd.DataFrame(
            [
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1"},
                {"calibration_id": "CAL0002", "validation_id": "VAL0002", "article_id": "a2"},
            ]
        )

        errors = calibration_packet_identity_errors(sample, packet, expected_rows=2)

        self.assertTrue(errors.empty)

    def test_calibration_packet_identity_errors_flag_stale_and_duplicate_rows(self) -> None:
        sample = pd.DataFrame(
            [
                {"validation_id": "VAL0001", "article_id": "a1"},
                {"validation_id": "VAL0002", "article_id": "a2"},
            ]
        )
        packet = pd.DataFrame(
            [
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1"},
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1"},
                {"calibration_id": "CAL0003", "validation_id": "VAL9999", "article_id": "missing"},
            ]
        )

        errors = calibration_packet_identity_errors(sample, packet, expected_rows=2)

        self.assertIn("calibration_packet_row_count_mismatch", set(errors["error"]))
        self.assertIn("duplicate_calibration_id", set(errors["error"]))
        self.assertIn("duplicate_calibration_sample_row", set(errors["error"]))
        self.assertIn("calibration_row_not_in_sample", set(errors["error"]))

    def test_calibration_packet_identity_errors_flag_missing_calibration_id(self) -> None:
        sample = pd.DataFrame([{"validation_id": "VAL0001", "article_id": "a1"}])
        packet = pd.DataFrame([{"calibration_id": "", "validation_id": "VAL0001", "article_id": "a1"}])

        errors = calibration_packet_identity_errors(sample, packet, expected_rows=1)

        self.assertEqual(errors.iloc[0]["error"], "missing_calibration_id")

    def test_calibration_submission_identity_errors_flag_rows_outside_packet(self) -> None:
        packet = pd.DataFrame(
            [
                {
                    "calibration_id": "CAL0001",
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                }
            ]
        )
        submissions = pd.DataFrame(
            [
                {
                    "calibration_id": "CAL9999",
                    "validation_id": "VAL9999",
                    "article_id": "a999",
                    "manual_label": "other",
                    "manual_confidence": "high",
                    "reviewer_id": "reviewer_a",
                    "review_date": "2026-06-29",
                }
            ]
        )

        errors = calibration_submission_identity_errors(packet, submissions)

        self.assertEqual(errors.loc[0, "error"], "calibration_row_not_in_packet")
        self.assertEqual(errors.loc[0, "value"], "CAL9999|VAL9999|a999")

    def test_calibration_submission_identity_errors_allow_multiple_reviewers_but_reject_same_reviewer_duplicate(self) -> None:
        packet = pd.DataFrame(
            [
                {
                    "calibration_id": "CAL0001",
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                }
            ]
        )
        submissions = pd.DataFrame(
            [
                {
                    "calibration_id": "CAL0001",
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                    "manual_label": "causal",
                    "manual_confidence": "high",
                    "reviewer_id": "reviewer_a",
                    "review_date": "2026-06-29",
                },
                {
                    "calibration_id": "CAL0001",
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                    "manual_label": "other",
                    "manual_confidence": "medium",
                    "reviewer_id": "reviewer_b",
                    "review_date": "2026-06-29",
                },
            ]
        )

        no_errors = calibration_submission_identity_errors(packet, submissions)
        self.assertTrue(no_errors.empty)

        duplicate = pd.concat([submissions, submissions.iloc[[0]]], ignore_index=True)
        errors = calibration_submission_identity_errors(packet, duplicate)

        self.assertEqual(set(errors["error"]), {"duplicate_calibration_reviewer_row"})
        self.assertEqual(len(errors), 2)

    def test_load_calibration_submissions_audits_no_files_without_error(self) -> None:
        packet = pd.DataFrame([{"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "manual_label": ""}])
        with tempfile.TemporaryDirectory() as tmp:
            submissions, audit, errors = load_calibration_submissions(Path(tmp) / "missing", packet)

        self.assertEqual(len(submissions), 1)
        self.assertEqual(audit.loc[0, "status"], "no_submission_files")
        self.assertTrue(errors.empty)

    def test_load_calibration_submissions_flags_blank_template_in_submissions(self) -> None:
        packet = pd.DataFrame([{"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "manual_label": ""}])
        with tempfile.TemporaryDirectory() as tmp:
            submissions_dir = Path(tmp) / "submissions"
            submissions_dir.mkdir()
            pd.DataFrame(
                [
                    {
                        "calibration_id": "CAL0001",
                        "validation_id": "VAL0001",
                        "article_id": "a1",
                        "manual_label": "",
                        "manual_confidence": "",
                        "manual_notes": "",
                        "reviewer_id": "",
                        "review_date": "",
                    }
                ]
            ).to_csv(submissions_dir / "blank_template.csv", index=False)

            submissions, audit, errors = load_calibration_submissions(submissions_dir, packet)

        self.assertEqual(len(submissions), 1)
        self.assertEqual(audit.loc[0, "status"], "blank_no_completed_labels")
        self.assertIn("calibration_submission_file_has_no_completed_labels", set(errors["error"]))

    def test_load_calibration_submissions_audits_valid_submission_file(self) -> None:
        packet = pd.DataFrame([{"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "manual_label": ""}])
        with tempfile.TemporaryDirectory() as tmp:
            submissions_dir = Path(tmp) / "submissions"
            submissions_dir.mkdir()
            pd.DataFrame(
                [
                    {
                        "calibration_id": "CAL0001",
                        "validation_id": "VAL0001",
                        "article_id": "a1",
                        "manual_label": "causal",
                        "manual_confidence": "high",
                        "manual_notes": "clear effect language",
                        "reviewer_id": "reviewer_a",
                        "review_date": "2026-06-29",
                    }
                ]
            ).to_csv(submissions_dir / "reviewer_a.csv", index=False)

            submissions, audit, errors = load_calibration_submissions(submissions_dir, packet)

        self.assertEqual(submissions.loc[0, "manual_label"], "causal")
        self.assertEqual(audit.loc[0, "status"], "ready_for_calibration_refresh")
        self.assertEqual(int(audit.loc[0, "completed_labels"]), 1)
        self.assertEqual(audit.loc[0, "reviewer_ids"], "reviewer_a")
        self.assertTrue(errors.empty)

    def test_calibration_kickoff_checklist_marks_gate_step_blocked_until_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            html_dir = root / "forms"
            submissions_dir = root / "submissions"
            html_dir.mkdir()
            submissions_dir.mkdir()
            (html_dir / "manual_validation_review_packet_batch_001.html").write_text("form", encoding="utf-8")
            codebook = root / "manual_validation_codebook.md"
            codebook.write_text("codebook", encoding="utf-8")
            guide = root / "manual_validation_calibration_guide.md"
            guide.write_text("guide", encoding="utf-8")
            summary = pd.DataFrame(
                [
                    {"metric": "calibration_rows", "value": 20},
                    {"metric": "completed_calibration_labels", "value": 0},
                ]
            )

            checklist = calibration_kickoff_checklist(
                summary=summary,
                errors=pd.DataFrame(),
                disagreements=pd.DataFrame(),
                packet_path=root / "packet.csv",
                html_dir=html_dir,
                submissions_dir=submissions_dir,
                codebook_path=codebook,
                guide_path=guide,
            )
            gate_step = checklist.set_index("step").loc["Recheck validation gate"]
            guide_step = checklist.set_index("step").loc["Read the calibration guide"]

            self.assertEqual(gate_step["status"], "blocked")
            self.assertIn("run_validation_gate.py", gate_step["path_or_command"])
            self.assertEqual(guide_step["status"], "ready")

    def test_write_calibration_kickoff_report_includes_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "docs" / "kickoff.md"
            checklist = pd.DataFrame(
                [
                    {
                        "step_order": 1,
                        "step": "Read the codebook",
                        "status": "ready",
                        "action": "Review labels.",
                        "path_or_command": "docs/manual_validation_codebook.md",
                        "note": "Use title and abstract.",
                    }
                ]
            )
            profile = pd.DataFrame([{"metric": "packet_rows", "value": 20}])

            write_calibration_kickoff_report(
                report,
                checklist,
                profile,
                packet_path="packet.csv",
                html_dir="forms",
                submissions_dir="submissions",
                guide_path="docs/manual_validation_calibration_guide.md",
            )

            text = report.read_text(encoding="utf-8")
            self.assertIn("Manual Validation Calibration Kickoff", text)
            self.assertIn("manual_validation_calibration_guide.md", text)
            self.assertIn("Label Decision Cheat Sheet", text)
            self.assertIn("primary-focus rule", text)
            self.assertIn("After Export Commands", text)
            self.assertIn("run_validation_gate.py", text)
            self.assertIn("Read the codebook", text)
            self.assertIn("packet_rows", text)

    def test_write_calibration_guide_report_marks_blindness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "docs" / "guide.md"
            guide = pd.DataFrame(
                [
                    {
                        "calibration_id": "CAL0001",
                        "title": "A Paper",
                        "abstract_chars": 100,
                        "text_status": "short_text",
                        "cue_profile": "no_keyword_cues",
                        "review_difficulty": "medium",
                        "reviewer_focus": "Check text.",
                    }
                ]
            )
            summary = pd.DataFrame([{"section": "text_status", "value": "short_text", "rows": 1}])

            write_calibration_guide_report(report, guide, summary, rules_path="config/classification_rules.yml", minimum_chars=250)

            text = report.read_text(encoding="utf-8")
            self.assertIn("Manual Validation Calibration Guide", text)
            self.assertIn("blind to model predictions", text)
            self.assertIn("short_text", text)

    def test_write_calibration_dashboard_links_form_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            forms = root / "forms"
            forms.mkdir()
            form = forms / "manual_validation_review_packet_batch_001.html"
            form.write_text("form", encoding="utf-8")
            remaining_form = forms / "manual_validation_calibration_remaining.html"
            remaining_form.write_text("remaining", encoding="utf-8")
            remaining_template = root / "manual_validation_calibration_remaining_submission_template.csv"
            remaining_template.write_text("template", encoding="utf-8")
            dashboard = forms / "manual_validation_calibration_dashboard.html"
            summary = pd.DataFrame(
                [
                    {"metric": "calibration_rows", "value": "20"},
                    {"metric": "completed_calibration_labels", "value": "0"},
                    {"metric": "calibration_reviewers", "value": "0"},
                ]
            )
            checklist = pd.DataFrame(
                [
                    {
                        "step_order": 1,
                        "step": "Open the calibration form",
                        "status": "ready",
                        "action": "Open form.",
                        "path_or_command": str(form),
                        "note": "Use the form.",
                    }
                ]
            )
            packet_profile = pd.DataFrame([{"metric": "packet_rows", "value": "20"}])
            guide_summary = pd.DataFrame(
                [
                    {"section": "text_status", "value": "no_abstract", "rows": "5"},
                    {"section": "review_difficulty", "value": "high", "rows": "7"},
                ]
            )
            progress = pd.DataFrame(
                [
                    {
                        "calibration_id": "CAL0001",
                        "validation_id": "VAL0001",
                        "article_id": "a1",
                        "title": "Paper",
                        "text_status": "no_abstract",
                        "review_difficulty": "high",
                        "completed_labels": 0,
                        "completed_reviewers": 0,
                        "reviewer_labels": "",
                        "label_set": "",
                        "error_rows": 0,
                        "row_status": "needs_label",
                        "next_step": "Complete manual label.",
                    }
                ]
            )

            write_calibration_dashboard(
                dashboard,
                summary=summary,
                checklist=checklist,
                packet_profile=packet_profile,
                errors=pd.DataFrame(),
                submission_audit=pd.DataFrame(
                    [
                        {
                            "file": "",
                            "rows": 0,
                            "completed_labels": 0,
                            "completed_rows": 0,
                            "reviewer_ids": "",
                            "missing_required_columns": "",
                            "status": "no_submission_files",
                            "note": "No reviewer CSV files found.",
                        }
                    ]
                ),
                disagreements=pd.DataFrame(),
                guide_summary=guide_summary,
                progress=progress,
                packet_path=str(root / "packet.csv"),
                html_dir=str(forms),
                submissions_dir=str(root / "submissions"),
                codebook_path=str(root / "codebook.md"),
                report_path=str(root / "calibration.md"),
                kickoff_report_path=str(root / "kickoff.md"),
                guide_report_path=str(root / "guide.md"),
                remaining_report_path=str(root / "remaining.md"),
                remaining_form_path=str(root / "forms" / "manual_validation_calibration_remaining.html"),
                remaining_template_path=str(remaining_template),
            )

            text = dashboard.read_text(encoding="utf-8")
            self.assertIn("Calibration Dashboard", text)
            self.assertIn("blocked_calibration", text)
            self.assertIn("0 / 20", text)
            self.assertIn("Open remaining calibration form", text)
            self.assertIn("Open spreadsheet template", text)
            self.assertIn("manual_validation_calibration_remaining.html", text)
            self.assertIn("manual_validation_calibration_remaining_submission_template.csv", text)
            self.assertIn("manual_validation_review_packet_batch_001.html", text)
            self.assertIn(f'<li><a href="manual_validation_review_packet_batch_001.html">Open calibration form</a></li>', text)
            self.assertIn("High difficulty", text)
            self.assertIn("No abstract rows", text)
            self.assertIn("Submission Files", text)
            self.assertIn("no_submission_files", text)
            self.assertIn("needs_label", text)

    def test_calibration_row_progress_marks_row_level_actions(self) -> None:
        packet = pd.DataFrame(
            [
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "title": "Agreement"},
                {"calibration_id": "CAL0002", "validation_id": "VAL0002", "article_id": "a2", "title": "Single label"},
                {"calibration_id": "CAL0003", "validation_id": "VAL0003", "article_id": "a3", "title": "Disagreement"},
                {"calibration_id": "CAL0004", "validation_id": "VAL0004", "article_id": "a4", "title": "Needs label"},
                {"calibration_id": "CAL0005", "validation_id": "VAL0005", "article_id": "a5", "title": "Error row"},
            ]
        )
        submissions = pd.DataFrame(
            [
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "manual_label": "causal", "manual_confidence": "high", "reviewer_id": "r1", "manual_notes": ""},
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "manual_label": "causal", "manual_confidence": "medium", "reviewer_id": "r2", "manual_notes": ""},
                {"calibration_id": "CAL0002", "validation_id": "VAL0002", "article_id": "a2", "manual_label": "predictive", "manual_confidence": "high", "reviewer_id": "r1", "manual_notes": ""},
                {"calibration_id": "CAL0003", "validation_id": "VAL0003", "article_id": "a3", "manual_label": "causal", "manual_confidence": "high", "reviewer_id": "r1", "manual_notes": ""},
                {"calibration_id": "CAL0003", "validation_id": "VAL0003", "article_id": "a3", "manual_label": "other", "manual_confidence": "low", "reviewer_id": "r2", "manual_notes": ""},
            ]
        )
        guide = pd.DataFrame(
            [
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "text_status": "usable_text", "review_difficulty": "low"},
                {"calibration_id": "CAL0004", "validation_id": "VAL0004", "article_id": "a4", "text_status": "no_abstract", "review_difficulty": "high"},
            ]
        )
        errors = pd.DataFrame(
            [
                {
                    "validation_id": "VAL0005",
                    "article_id": "a5",
                    "row_number": 2,
                    "field": "manual_label",
                    "value": "",
                    "error": "invalid_manual_label",
                }
            ]
        )

        progress = calibration_row_progress(packet=packet, submissions=submissions, guide=guide, errors=errors)
        indexed = progress.set_index("calibration_id")

        self.assertEqual(indexed.loc["CAL0001", "row_status"], "multi_reviewer_agreement")
        self.assertEqual(indexed.loc["CAL0002", "row_status"], "labeled")
        self.assertEqual(indexed.loc["CAL0003", "row_status"], "disagreement")
        self.assertEqual(indexed.loc["CAL0004", "row_status"], "needs_label")
        self.assertEqual(indexed.loc["CAL0005", "row_status"], "fix_errors")
        self.assertEqual(indexed.loc["CAL0004", "text_status"], "no_abstract")

    def test_remaining_calibration_packet_filters_to_rows_needing_action(self) -> None:
        packet = pd.DataFrame(
            [
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "title": "Error"},
                {"calibration_id": "CAL0002", "validation_id": "VAL0002", "article_id": "a2", "title": "Disagreement"},
                {"calibration_id": "CAL0003", "validation_id": "VAL0003", "article_id": "a3", "title": "Needs label"},
                {"calibration_id": "CAL0004", "validation_id": "VAL0004", "article_id": "a4", "title": "Done"},
            ]
        )
        guide = pd.DataFrame(
            [
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "text_status": "usable_text", "review_difficulty": "routine"},
                {"calibration_id": "CAL0002", "validation_id": "VAL0002", "article_id": "a2", "text_status": "usable_text", "review_difficulty": "high"},
                {"calibration_id": "CAL0003", "validation_id": "VAL0003", "article_id": "a3", "text_status": "no_abstract", "review_difficulty": "high"},
                {"calibration_id": "CAL0004", "validation_id": "VAL0004", "article_id": "a4", "text_status": "usable_text", "review_difficulty": "routine"},
            ]
        )
        progress = pd.DataFrame(
            [
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "row_status": "fix_errors", "next_step": "Fix errors.", "completed_labels": "1"},
                {"calibration_id": "CAL0002", "validation_id": "VAL0002", "article_id": "a2", "row_status": "disagreement", "next_step": "Discuss.", "completed_labels": "2"},
                {"calibration_id": "CAL0003", "validation_id": "VAL0003", "article_id": "a3", "row_status": "needs_label", "next_step": "Label.", "completed_labels": "0"},
                {"calibration_id": "CAL0004", "validation_id": "VAL0004", "article_id": "a4", "row_status": "labeled", "next_step": "Done.", "completed_labels": "1"},
            ]
        )

        remaining = remaining_calibration_packet(packet, guide, progress)
        summary = remaining_calibration_summary(remaining).set_index("metric")
        html = reviewer_form_html(remaining, title="Remaining")

        self.assertEqual(remaining["calibration_id"].tolist(), ["CAL0001", "CAL0002", "CAL0003"])
        self.assertIn("calibration_row_status", remaining.columns)
        self.assertIn("calibration_next_step", remaining.columns)
        self.assertEqual(int(summary.loc["remaining_rows", "value"]), 3)
        self.assertEqual(int(summary.loc["status_needs_label", "value"]), 1)
        self.assertIn("Calibration status", html)
        self.assertIn("fix_errors", html)

    def test_remaining_calibration_submission_template_keeps_only_review_context_and_blank_manual_fields(self) -> None:
        remaining = pd.DataFrame(
            [
                {
                    "calibration_id": "CAL0001",
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                    "title": "Needs Review",
                    "abstract": "Short abstract.",
                    "manual_label": "causal",
                    "manual_confidence": "high",
                    "manual_notes": "old value",
                    "reviewer_id": "r1",
                    "review_date": "2026-06-29",
                    "calibration_row_status": "needs_label",
                    "calibration_next_step": "Complete fields.",
                    "text_status": "usable_text",
                    "cue_profile": "causal_cues",
                    "review_difficulty": "routine",
                    "reviewer_focus": "Check focus.",
                    "classification_reason": "model-only context should not be exported",
                }
            ]
        )

        template = remaining_calibration_submission_template(remaining)

        self.assertEqual(template["calibration_id"].tolist(), ["CAL0001"])
        self.assertNotIn("classification_reason", template.columns)
        for column in ["manual_label", "manual_confidence", "manual_notes", "reviewer_id", "review_date"]:
            self.assertEqual(template.loc[0, column], "")
        self.assertEqual(template.loc[0, "calibration_row_status"], "needs_label")
        self.assertEqual(template.loc[0, "reviewer_focus"], "Check focus.")


if __name__ == "__main__":
    unittest.main()
