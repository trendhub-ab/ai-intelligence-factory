"""One-shot free-form Gemini writer experiment; no publication side effects."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from experiments.editorial_engine_v3_phase0.cases import READY_CASES
from experiments.editorial_engine_v3_phase0.contract import (
    validate_article_layout,
    validate_reader_facing_article,
)

CASE_ID = "3fa479ff-dca9-8194-a493-cb3a0d2b3a36"
MODEL = "gemini-3.8-flash"
OUTPUT = Path("free_writer_review")

WRITER_BRIEF = """あなたは優秀な日本語の編集者・ライターです。
以下の検証済み素材だけを使い、AIの技術ニュースを大人の読者が思わず読み進める記事にしてください。
タイトル、冒頭、構成、会話、比喩、リズムは自由です。単なる研究要約にしないでください。
根拠のない事実・数字・体験談は作らず、不明点は不明と伝えてください。
自然で中性的な日本語を使ってください。完成したMarkdown記事だけを出力してください。
"""

def build_prompt() -> str:
    matches = [item.case for item in READY_CASES if item.case.case_id == CASE_ID]
    if len(matches) != 1:
        raise RuntimeError("Immutable experiment case not found")
    case = matches[0]
    evidence = "\n".join(f"- {item}" for item in case.evidence)
    facts = "\n".join(f"- {item}" for item in case.facts)
    sources = "\n".join(f"- {item}" for item in case.sources)
    return (
        f"{WRITER_BRIEF}\n\n対象読者: {case.target_reader}\n"
        f"テーマ: {case.title}\n\nEvidence:\n{evidence}\n"
        f"\nFacts:\n{facts}\n\nSources:\n{sources}\n"
    )

def generate_once(client) -> dict:
    if OUTPUT.exists():
        raise RuntimeError("Output already exists; refuse overwrite or repeat")
    prompt = build_prompt()
    response = client.models.generate_content(model=MODEL, contents=prompt)
    article = str(getattr(response, "text", "") or "").strip()
    if not article:
        raise RuntimeError("Empty Gemini response")
    errors = []
    for validator in (validate_article_layout, validate_reader_facing_article):
        try:
            validator(article)
        except (ValueError, TypeError) as exc:
            errors.append(f"{validator.__name__}: {exc}")
    OUTPUT.mkdir(parents=True, exist_ok=False)
    (OUTPUT / "article.md").write_text(article + "\n", encoding="utf-8")
    result = {
        "case_id": CASE_ID,
        "model": MODEL,
        "provider_attempts": 1,
        "local_checks": {"layout_and_reader_contract_errors": errors},
        "factual_verification": "NOT_AUTOMATICALLY_PROVEN",
        "quality_verdict": "HUMAN_REVIEW_REQUIRED",
        "publication": "PROHIBITED",
    }
    (OUTPUT / "review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result

def main() -> None:
    if datetime.now(ZoneInfo("Asia/Tokyo")).hour < 17:
        raise RuntimeError("Gemini API forbidden before 17:00 JST")
    if os.environ.get("AIIF_FREE_WRITER_CONFIRM") != "FREE_WRITER_ONCE":
        raise RuntimeError("Explicit one-shot confirmation required")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing GEMINI_API_KEY")
    from google import genai
    print(json.dumps(generate_once(genai.Client(api_key=key)), ensure_ascii=False))

if __name__ == "__main__":
    main()
