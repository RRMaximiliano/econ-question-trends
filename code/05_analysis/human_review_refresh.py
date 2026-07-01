from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class RefreshStep:
    step_id: str
    description: str
    command: tuple[str, ...]


DEFAULT_REPORT = Path("docs/human_review_refresh.md")
DEFAULT_LOG = Path("outputs/logs/human_review_refresh.log")


def refresh_steps(python_executable: str = "/usr/bin/python3") -> list[RefreshStep]:
    return [
        RefreshStep(
            "calibration",
            "Refresh calibration packet status, forms, guide, and disagreement/error reports.",
            (python_executable, "run_manual_validation_calibration.py"),
        ),
        RefreshStep(
            "evidence_tier_policy",
            "Refresh the shared insufficient-text recovery evidence-tier policy.",
            (python_executable, "run_evidence_tier_policy.py"),
        ),
        RefreshStep(
            "scope_review_audit",
            "Refresh scope-review candidates from the current classified file, recovery queue, active batch, and scope patterns.",
            (python_executable, "run_scope_review_audit.py"),
        ),
        RefreshStep(
            "scope_review_packet",
            "Refresh the scope-review packet, guide, completion summary, and bulk-fill browser form.",
            (python_executable, "run_scope_review_packet.py"),
        ),
        RefreshStep(
            "scope_review_apply_dry_run",
            "Refresh dry-run validation of completed scope-review decisions without applying them.",
            (python_executable, "run_apply_scope_review_decisions.py"),
        ),
        RefreshStep(
            "recent_recovery_pilot",
            "Refresh the recent 2023-2025 top-5 recovery triage packet before broad backfill work.",
            (python_executable, "run_recent_recovery_pilot.py"),
        ),
        RefreshStep(
            "recovery_batch_workplan",
            "Refresh R001 recovery workplan after current scope decisions and source-route blockers.",
            (python_executable, "run_recovery_batch_workplan.py"),
        ),
        RefreshStep(
            "recovery_batch_split",
            "Refresh R001 split packets from the current recovery workplan.",
            (python_executable, "run_recovery_batch_split.py"),
        ),
        RefreshStep(
            "recovery_review_queue",
            "Refresh R001 recovery queue, source guide, tiered packets, and guided forms.",
            (python_executable, "run_recovery_review_queue.py"),
        ),
        RefreshStep(
            "recovery_cell_targets",
            "Refresh balanced journal-decade recovery target cells and queue examples.",
            (python_executable, "run_recovery_cell_targets.py"),
        ),
        RefreshStep(
            "recovery_automation_audit",
            "Refresh the non-mutating recovery automation blocker audit.",
            (python_executable, "run_recovery_automation_audit.py"),
        ),
        RefreshStep(
            "recovery_cached_evidence",
            "Audit R001 recovery queue against local cached source metadata without network calls.",
            (python_executable, "run_recovery_cached_evidence.py"),
        ),
        RefreshStep(
            "recovery_tiered_stage",
            "Stage any completed tiered recovery exports without importing them.",
            (python_executable, "run_recovery_tiered_stage.py"),
        ),
        RefreshStep(
            "recovery_split_preflight",
            "Preflight staged recovery split files before any import.",
            (
                python_executable,
                "run_recovery_split_preflight.py",
                "--split-summary",
                "outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv",
            ),
        ),
        RefreshStep(
            "recovery_action_progress",
            "Refresh action-group progress across exports, staging, and preflight.",
            (python_executable, "run_recovery_action_progress.py"),
        ),
        RefreshStep(
            "recovery_kickoff_packet",
            "Refresh the target-aware first-session recovery packet and form.",
            (python_executable, "run_recovery_kickoff_packet.py"),
        ),
        RefreshStep(
            "manual_validation_readiness",
            "Refresh manual validation readiness, drift check, and reviewer portal.",
            (python_executable, "run_manual_validation_readiness.py"),
        ),
        RefreshStep(
            "validation_gate",
            "Refresh validation gate checks and report.",
            (python_executable, "run_validation_gate.py"),
        ),
        RefreshStep(
            "project_status",
            "Refresh project status summary and next actions.",
            (python_executable, "run_project_status.py"),
        ),
        RefreshStep(
            "human_review_workboard",
            "Refresh the combined human-review workboard.",
            (python_executable, "run_human_review_workboard.py"),
        ),
    ]


def run_step(step: RefreshStep, *, executor: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> subprocess.CompletedProcess[str]:
    return executor(
        step.command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def write_refresh_report(path: Path, results: list[tuple[RefreshStep, int, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Human Review Refresh",
        "",
        "This report is generated by `run_human_review_refresh.py`. The command refreshes review handoff artifacts, but does not apply labels, scope decisions, abstract imports, or trend outputs.",
        "",
        "## Steps",
        "",
        "| step | status | command |",
        "| --- | --- | --- |",
    ]
    for step, returncode, _ in results:
        status = "ok" if returncode == 0 else f"failed:{returncode}"
        command = " ".join(step.command)
        lines.append(f"| {step.step_id} | {status} | `{command}` |")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_refresh_log(path: Path, results: list[tuple[RefreshStep, int, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for step, returncode, output in results:
        lines.append(f"## {step.step_id} returncode={returncode}")
        lines.append(" ".join(step.command))
        lines.append(output.rstrip())
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_human_review_refresh(
    *,
    python_executable: str,
    report_path: Path,
    log_path: Path,
    executor: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[tuple[RefreshStep, int, str]]:
    results: list[tuple[RefreshStep, int, str]] = []
    for step in refresh_steps(python_executable):
        completed = run_step(step, executor=executor)
        output = completed.stdout or ""
        results.append((step, int(completed.returncode), output))
        print(f"{step.step_id}={completed.returncode}")
        if output.strip():
            print(output.strip())
        if completed.returncode != 0:
            break
    write_refresh_report(report_path, results)
    write_refresh_log(log_path, results)
    if results and results[-1][1] != 0:
        raise SystemExit(results[-1][1])
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default="/usr/bin/python3")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    args = parser.parse_args()
    run_human_review_refresh(
        python_executable=args.python,
        report_path=Path(args.report),
        log_path=Path(args.log),
    )


if __name__ == "__main__":
    main()
