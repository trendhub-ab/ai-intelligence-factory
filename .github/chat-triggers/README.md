# Chat-controlled GitHub Actions triggers

This directory is intentionally inert until one of the exact trigger files below is created or updated by the connected ChatGPT GitHub integration.

- `synthetic-full.txt` → run the full provider-free Synthetic Regression Suite.
- `real-article-fixed.txt` → run the fixed 3-article Real Article Regression.
- `real-article-fresh.txt` → run the fresh 3-article Real Article Regression.

Safety rules:

1. Ordinary source-code pushes do not trigger `Chat Automation Runner`.
2. Exactly one trigger file must change in a trigger commit. If multiple trigger files change together, the workflow fails closed before regression execution.
3. Real Article modes use the repository's existing Gemini quota controls and persistent counter configuration.
4. Synthetic Full does not intentionally call Gemini.
5. Trigger file contents are operational nonces/timestamps only; changing the selected file is the explicit run request.
