# Run122 Setup

Run122 adds no Notion schema, GitHub Secret, Repository Variable, or Gemini budget setting.

Deployment sequence:

1. Replace main with the Run122 package contents.
2. Run `Synthetic Regression Suite` with `suite=full` on `main`.
3. Confirm the workflow passes.
4. Run `Real Article Regression Test` on `main`.
5. Inspect the three generated artifacts. In particular, confirm:
   - `Cobalt SDK` is not falsely rejected when Cobalt + SDK are both in primary evidence.
   - `Espressif IoT Development Framework` is not falsely rejected when primary evidence uses ESP-IDF.
   - exact NOTE_DRAFT transport control lines do not reach the article gate/output.
   - content-specific headings are accepted; long unsectioned prose is repaired/reviewed without requiring legacy `導入 / 結論 / 最終判断` labels.
   - genuine unsupported named products are still rejected.
6. Only after Real Article Regression inspection, re-enable/run the normal Daily pipeline for Production E2E.

No new settings are required.
