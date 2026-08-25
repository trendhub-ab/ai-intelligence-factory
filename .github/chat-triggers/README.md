# Chat-controlled GitHub Actions triggers

This directory is intentionally inert until one of the exact trigger files below is created or updated by the connected ChatGPT GitHub integration.

- `synthetic-full.txt` → run the full provider-free Synthetic Regression Suite.
- `real-article-fixed.txt` → run the fixed 3-article Real Article Regression.
- `real-article-fresh.txt` → run the fresh 3-article Real Article Regression.
- `inventory-plan.txt` → run Subscriber Inventory Bootstrap in 0-API/read-only plan mode.
- `inventory-apply.txt` → run Subscriber Inventory Bootstrap apply mode on `main` only.

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

1. Ordinary source-code pushes do not trigger `Chat Automation Runner`.
2. Exactly one trigger file must change in a trigger commit. If multiple trigger files change together, the workflow fails closed before execution.
3. Real Article and Inventory apply modes use the repository's existing Gemini quota controls and shared `ai-intelligence-gemini-budget` concurrency lock.
4. Synthetic Full does not intentionally call Gemini.
5. Inventory plan is 0-API/read-only by design.
6. Inventory plan/apply are main-only in Chat Automation, matching the existing Bootstrap production boundary.
7. Inventory apply requires the exact explicit confirmation token `CONFIRM_BOOTSTRAP`.
8. Trigger files are operational requests. Updating the selected file is the explicit run signal.
