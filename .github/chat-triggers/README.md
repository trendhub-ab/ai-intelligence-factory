# Chat-controlled GitHub Actions triggers

This directory is intentionally inert until one of the exact trigger files below is created or updated by the connected ChatGPT GitHub integration.

- `synthetic-full.txt` → run the full provider-free Synthetic Regression Suite.
- `real-article-fixed.txt` → run the fixed 3-article Real Article Regression.
- `real-article-fresh.txt` → run the fresh 3-article Real Article Regression.
- `inventory-plan.txt` → run Subscriber Inventory Bootstrap in 0-API/read-only plan mode.
- `inventory-apply.txt` → run Subscriber Inventory Bootstrap apply mode on `main` only.
- `gemini-quota-probe.txt` → send exactly one minimal request to the selected Gemini model and report whether it is available, rate-limited, locally budget-blocked, or failed for another reason.

## Gemini quota probe format

`gemini-quota-probe.txt` must contain an exact allowed model id:

```text
model=gemini-3.6-flash
```

Allowed probe models:

- `gemini-3.6-flash`
- `gemini-3.7-flash`
- `gemini-3.5-flash`
- `gemini-3.5-flash-lite`
- `gemini-3.1-flash-lite`

The probe uses the production Gemini quota wrapper so the single request participates in the repository's existing persistent daily counter and shared Gemini concurrency lock. It does not run article generation or Notion writes. A successful provider call is reported as `available`; a provider 429/RESOURCE_EXHAUSTED response is reported as `rate_limited`; a repository-local daily-budget refusal before provider access is reported as `local_budget_blocked`. Results are uploaded as `quota_probe_artifacts/quota_probe.json`.

## Inventory trigger format

`inventory-plan.txt` may contain:

```text
target_inventory=30
min_sellable=24
```

`inventory-apply.txt` may contain:

```text
target_inventory=30
min_sellable=24
max_reviews=4
product_request_budget=6
max_source_share=0.60
confirm=CONFIRM_BOOTSTRAP
```

Missing numeric values use the same safe defaults as the existing manual `Subscriber Inventory Bootstrap` workflow. Apply never defaults the confirmation token: `confirm=CONFIRM_BOOTSTRAP` must be present explicitly.

Safety rules:

1. Ordinary source-code pushes do not trigger Chat-controlled execution.
2. Exactly one main Chat Automation trigger file must change in a trigger commit. If multiple main runner trigger files change together, the workflow fails closed before execution.
3. Real Article, Inventory apply, and Gemini Quota Probe share the repository's existing `ai-intelligence-gemini-budget` concurrency lock.
4. Synthetic Full does not intentionally call Gemini.
5. Inventory plan is 0-API/read-only by design.
6. Inventory plan/apply are main-only in Chat Automation, matching the existing Bootstrap production boundary.
7. Inventory apply requires the exact explicit confirmation token `CONFIRM_BOOTSTRAP`.
8. Gemini Quota Probe makes exactly one selected-model request when it reaches the provider; it never falls back to another model.
9. Trigger files are operational requests. Creating or updating the selected file is the explicit run signal.
