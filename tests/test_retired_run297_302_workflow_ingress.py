"""Guard retired Run297-302 GenRec helpers from active workflow ingress.

The historical Python helpers are intentionally retained for auditability and
regression fixtures.  What must not return is an active GitHub Actions ingress
that can invoke the completed Netflix GenRec recovery chain.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"

RETIRED_ONE_SHOT_SCRIPTS = (
    "run297_genrec_run296_rebase.py",
    "run298_genrec_inplace_refresh.py",
    "run298_hover_header_final.py",
    "run298_header_readonly_diagnostics.py",
    "run299_genrec_body_structure_diagnostic.py",
    "run300_genrec_final_body_repair.py",
    "run301_genrec_summary_restore.py",
    "run302_genrec_publication_reconcile.py",
)


def test_retired_genrec_helpers_have_no_active_workflow_ingress() -> None:
    references: list[str] = []
    for pattern in ("*.yml", "*.yaml"):
        for workflow in WORKFLOW_DIR.glob(pattern):
            text = workflow.read_text(encoding="utf-8")
            for script in RETIRED_ONE_SHOT_SCRIPTS:
                if script in text:
                    references.append(f"{workflow.relative_to(ROOT)} -> {script}")

    assert references == [], (
        "completed Run297-302 helpers must not regain active workflow ingress: "
        f"{references}"
    )
