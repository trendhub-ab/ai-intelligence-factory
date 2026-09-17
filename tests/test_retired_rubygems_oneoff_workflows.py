from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# These workflows were bounded, article-specific repair entry points for the
# historical RubyGems recovery.  They subscribed to every issue_comment event
# and could mutate Notion / an existing private note draft when their command
# matched.  The generic Production paths now own those responsibilities.
RETIRED_RUBYGEMS_ONEOFF_WORKFLOWS = (
    ".github/workflows/run413-oneoff-rubygems-manual-ready.yml",
    ".github/workflows/run414-rubygems-eyecatch.yml",
    ".github/workflows/run416-rubygems-zero-model-eyecatch.yml",
    ".github/workflows/run418-rubygems-canonical-eyecatch.yml",
    ".github/workflows/run425-rubygems-summary-restore.yml",
)


def test_retired_rubygems_oneoff_workflows_are_absent() -> None:
    leftovers = [
        path
        for path in RETIRED_RUBYGEMS_ONEOFF_WORKFLOWS
        if (ROOT / path).exists()
    ]
    assert leftovers == [], (
        "retired RubyGems one-off workflows must not be reintroduced as active "
        f"issue_comment entry points: {leftovers}"
    )
