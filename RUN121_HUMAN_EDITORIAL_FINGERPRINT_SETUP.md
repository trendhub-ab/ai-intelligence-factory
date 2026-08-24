# Run121 Human Editorial Fingerprint Setup

No new Secrets, Notion properties, databases, or API credentials are required.

## Deployment
1. Replace the current main baseline with the Run121 completed package.
2. Keep all existing Run120 Repository Variables / Secrets unchanged.
3. Run the normal regression workflow once after merge.
4. Resume the normal Daily pipeline. The article-style memory is automatically reset at the beginning of every production run.

## Operating behavior
- No extra Gemini request is made by the new detectors.
- Only a high-confidence combination becomes REVIEW.
- If a cross-article fingerprint triggers, the existing bounded Quality Retry may re-edit structure/order once.
- The fixed Reader-First header is not part of the cross-article comparison.
- Do not add more stylistic rules unless actual generated articles demonstrate a recurring defect; Run121 is the article-quality logic freeze baseline.
