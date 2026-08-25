# Run110 Inventory Bootstrap Operations

## First execution after upgrade
Run GitHub Actions → `Subscriber Inventory Bootstrap` with:

- mode: `plan`
- target_inventory: `30`
- min_sellable: `24`
- max_reviews: `4`
- product_request_budget: `6`
- max_source_share: `0.60`
- confirm: blank

Plan uses zero Gemini calls.

## What changed in the Plan artifact
The candidate table now shows:
- Portfolio priority
- Product utility score
- Base bootstrap score
- Candidate Lane (PRACTICAL / RESEARCH / RISK / DISCOVERY)
- Planning Category
- Source

Planning Category and Lane are zero-API review-order metadata only. They do not overwrite Notion Category or determine Adoption Status.

## Approval rule before apply
Review at least the first 4 and top 20. Reject the Plan if:
- the first apply batch is effectively one-source despite available alternatives,
- practical Technology is absent without a strong evidence-based reason,
- all Planning Categories collapse to OTHER,
- discovery/news/opinion items dominate, or
- the queue clearly optimizes research novelty rather than subscriber decision utility.

Only after review, run `apply` with `CONFIRM_BOOTSTRAP`, initially max_reviews=4.
