# Synthetic / Adversarial Regression Suite v1.0

`regression_suite.py` is an offline, production-write-isolated test harness for AI Intelligence Factory evidence rules. It creates 500 deterministic local multi-document fixtures: 200 deterministic, 200 pairwise combinational, and 100 hidden holdout/adversarial cases.

Run:

```bash
python regression_suite.py --self-test
python regression_suite.py --bootstrap --smoke
python regression_suite.py --core
python regression_suite.py --full
```

Reports are written to `regression_suite_runs/<date>_<tier>_<id>/` as `regression_report.json` and `regression_summary.md`. No Notion, publishing, network, or Gemini calls occur.

To audit a model-produced draft instead of the conservative reference adapter, create `ARTICLE_DIR/<case_id>/article.md` and run:

```bash
python regression_suite.py --core --articles-dir ARTICLE_DIR
```

The next integration step is to have the production Deep Extraction → Evidence Store → Claim Ledger → Writer path emit that per-case draft directory while retaining this independent Ground Truth validator. This runner intentionally never adds prompt strings or fixture-specific rules to production code.
