"""One-shot Elastic C-only editorial proof. No retries, no A/B mutation."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .cases import READY_CASES
from .contract import validate_article_layout, validate_reader_facing_article
from .live import _parse_editorial_bundle
from .prompts import build_editorial_bundle_prompt

ELASTIC_CASE_ID = "3fa479ff-dca9-8194-a493-cb3a0d2b3a36"
MODEL = "gemini-3.8-flash"


def select_case():
    matches = [item for item in READY_CASES if item.case.case_id == ELASTIC_CASE_ID]
    if len(matches) != 1 or len(READY_CASES) != 3:
        raise RuntimeError("Elastic case identity or immutable three-case fixture changed")
    return matches[0]


def generate_once(*, client, output_dir: Path) -> dict:
    """Exactly one generate_content invocation; any error is terminal."""
    case = select_case().case
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "elastic_c_only.json"
    if target.exists():
        raise RuntimeError("Existing output; refuse repeat or overwrite")
    prompt = build_editorial_bundle_prompt(case)
    response = client.models.generate_content(model=MODEL, contents=prompt)
    raw = str(getattr(response, "text", "") or "").strip()
    if not raw:
        raise RuntimeError("Empty provider response")
    article, stages = _parse_editorial_bundle(raw)
    validate_article_layout(article)
    validate_reader_facing_article(article)
    payload = {
        "case_id": case.case_id,
        "source_title": case.title,
        "sources": list(case.sources),
        "model": MODEL,
        "provider_attempts": 1,
        "article": article,
        "stages": stages,
        "quality_verdict": "HUMAN_REVIEW_REQUIRED",
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    if datetime.now(ZoneInfo("Asia/Tokyo")).hour < 17:
        raise RuntimeError("Gemini use forbidden before 17:00 JST")
    if os.environ.get("AIIF_ELASTIC_ONE_SHOT_CONFIRM") != "ELASTIC_ONE_SHOT":
        raise RuntimeError("Explicit one-shot confirmation required")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing GEMINI_API_KEY")
    from google import genai

    result = generate_once(client=genai.Client(api_key=key), output_dir=Path("elastic_one_shot"))
    print(json.dumps({"case_id": result["case_id"], "provider_attempts": 1, "quality_verdict": result["quality_verdict"]}))


if __name__ == "__main__":
    main()
