"""
validate_agent_output.py
Usage: python validate_agent_output.py <path_to_agent_json>

Validates a subagent's tmp JSON output before the merge step.
Always exits 0. Prints a JSON report to stdout.

The main agent reads can_proceed to decide whether to retry.
"""

import json
import os
import sys

VALID_LEVELS = {"CRITICAL", "HIGH", "MED", "LOW", "DISCUSS", "UNCLEAR"}

KNOWN_AGENTS = {
    "master-reviewer",
    "security-auditor",
    "regression-hunter",
    "performance-scout",
    "code-usage-inspector",
    "test-critic",
    "code-quality-inspector",
}


def validate(filepath):
    report = {
        "file": filepath,
        "can_proceed": False,
        "critical_errors": [],
        "finding_issues": [],   # list of {index, critical: [], warnings: []}
        "warnings": [],
        "total_findings": 0,
        "valid_findings": 0,
    }

    # ── File-level checks ──────────────────────────────────────────────────────

    if not os.path.exists(filepath):
        report["critical_errors"].append(f"File not found: {filepath}")
        return report

    try:
        size = os.path.getsize(filepath)
    except OSError as e:
        report["critical_errors"].append(f"Cannot stat file: {e}")
        return report

    if size == 0:
        report["critical_errors"].append("File is empty (0 bytes)")
        return report

    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as e:
        report["critical_errors"].append(f"Invalid JSON: {e}")
        return report
    except OSError as e:
        report["critical_errors"].append(f"Cannot read file: {e}")
        return report

    if not isinstance(data, dict):
        report["critical_errors"].append("Root value is not a JSON object")
        return report

    # ── Top-level field checks ─────────────────────────────────────────────────

    if "agent" not in data:
        report["warnings"].append("Missing top-level 'agent' field (non-critical)")
    elif data["agent"] not in KNOWN_AGENTS:
        report["warnings"].append(
            f"Unknown agent name: '{data['agent']}' — expected one of {sorted(KNOWN_AGENTS)}"
        )

    if "findings" not in data:
        report["critical_errors"].append("Missing top-level 'findings' array")
        return report

    if not isinstance(data["findings"], list):
        report["critical_errors"].append(
            f"'findings' must be a JSON array, got {type(data['findings']).__name__}"
        )
        return report

    # ── Per-finding checks ────────────────────────────────────────────────────

    report["total_findings"] = len(data["findings"])

    for i, finding in enumerate(data["findings"]):
        label = f"Finding #{i + 1}"
        fi = {"index": i, "critical": [], "warnings": []}

        if not isinstance(finding, dict):
            fi["critical"].append(f"{label}: entry is not a JSON object")
            report["finding_issues"].append(fi)
            continue

        # --- Critical fields ---

        if "level" not in finding:
            fi["critical"].append(f"{label}: missing 'level'")
        elif finding["level"] not in VALID_LEVELS:
            fi["critical"].append(
                f"{label}: invalid level '{finding['level']}'"
                f" — must be one of {sorted(VALID_LEVELS)}"
            )

        if not str(finding.get("description") or "").strip():
            fi["critical"].append(f"{label}: 'description' is missing or empty")

        if not str(finding.get("location") or "").strip():
            fi["critical"].append(f"{label}: 'location' is missing or empty")

        # Validate current_code object if present
        cc = finding.get("current_code")
        if cc is not None:
            if not isinstance(cc, dict):
                fi["critical"].append(
                    f"{label}: 'current_code' must be a JSON object"
                )
            else:
                if not str(cc.get("content") or "").strip():
                    fi["critical"].append(
                        f"{label}: 'current_code.content' is missing or empty"
                    )
                for key in ("highlight_start", "highlight_end"):
                    if key in cc and not isinstance(cc[key], (int, type(None))):
                        fi["warnings"].append(
                            f"{label}: 'current_code.{key}' should be an integer or null"
                        )

        # Validate issue_flow if present (warnings only — never triggers retry)
        iflow = finding.get("issue_flow")
        if iflow is not None:
            if not isinstance(iflow, dict):
                fi["warnings"].append(
                    f"{label}: 'issue_flow' must be a JSON object (non-critical)"
                )
            else:
                if not str(iflow.get("summary") or "").strip():
                    fi["warnings"].append(
                        f"{label}: 'issue_flow.summary' is missing or empty (non-critical)"
                    )
                if not str(iflow.get("critical_point") or "").strip():
                    fi["warnings"].append(
                        f"{label}: 'issue_flow.critical_point' is missing or empty (non-critical)"
                    )
                steps = iflow.get("steps")
                if steps is None:
                    fi["warnings"].append(
                        f"{label}: 'issue_flow.steps' array is missing (non-critical)"
                    )
                elif not isinstance(steps, list):
                    fi["warnings"].append(
                        f"{label}: 'issue_flow.steps' must be an array (non-critical)"
                    )
                elif len(steps) > 6:
                    fi["warnings"].append(
                        f"{label}: 'issue_flow.steps' has {len(steps)} steps — maximum is 6 (non-critical)"
                    )
                else:
                    for si, step in enumerate(steps):
                        slabel = f"{label} flow step #{si + 1}"
                        if not isinstance(step, dict):
                            fi["warnings"].append(
                                f"{slabel}: must be a JSON object (non-critical)"
                            )
                            continue
                        if not str(step.get("action") or "").strip():
                            fi["warnings"].append(
                                f"{slabel}: 'action' is missing or empty (non-critical)"
                            )
                        # 'input' may be null — that is valid
                        # 'critical' is optional — no warning if absent

        # --- Non-critical warnings ---

        if not str(finding.get("suggestion") or "").strip():
            fi["warnings"].append(f"{label}: 'suggestion' is missing or empty (non-critical)")

        if not finding.get("found_by"):
            fi["warnings"].append(f"{label}: 'found_by' is missing (non-critical)")

        if "also_found_by" not in finding:
            fi["warnings"].append(
                f"{label}: 'also_found_by' is missing — will default to [] in merge (non-critical)"
            )

        # Append only if there are issues
        if fi["critical"] or fi["warnings"]:
            report["finding_issues"].append(fi)

        # Count finding as valid only if no critical issues
        if not fi["critical"]:
            report["valid_findings"] += 1

    # ── Final can_proceed decision ────────────────────────────────────────────
    # Proceed if: no file-level critical errors
    #             AND (empty findings list is OK, or at least one valid finding)
    has_file_critical = len(report["critical_errors"]) > 0
    report["can_proceed"] = (not has_file_critical) and (
        report["total_findings"] == 0 or report["valid_findings"] > 0
    )

    return report


def main():
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {"error": "Usage: python validate_agent_output.py <path_to_json>"},
                indent=2,
            )
        )
        sys.exit(0)

    filepath = sys.argv[1]
    report = validate(filepath)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
