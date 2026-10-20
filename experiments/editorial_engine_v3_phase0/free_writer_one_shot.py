"""Isolated one-call Gemini writing trial. No production, Notion or note side effects."""
from __future__ import annotations

import json
import os
from pathlib import Path

MODEL = "gemini-3.8-flash"
OUTPUT = Path("free_writer_review")
SOURCE = "https://arxiv.org/abs/2610.20588v1"
WRITER_BRIEF = """あなたは優秀な日本語の編集者・ライターです。
以下の研究素材だけを使い、AIの技術ニュースを大人の読者が思わず読み進める記事にしてください。
タイトル、冒頭、構成、比喩、リズムは自由。単なる研究要約にしないでください。
根拠のない事実・数字・体験談は作らず、論文の主張と確立した事実を区別してください。
自然で中性的な日本語を使い、記事内に出典URLを入れてください。
完成したMarkdown記事だけを出力してください。"""

# Research facts are the previously reviewed one-shot case summary, not a
# machine-verified extraction of the current arXiv page. Human review required.
SOURCE_SUMMARY = """研究名: Your Transformer Is Secretly Elastic
出典: https://arxiv.org/abs/2610.20588v1
研究が提案するのは、学習済みTransformerの構成要素を順位付けし、
推論時に使用するニューロンやアテンションヘッドの量を調整する手法。
複数サイズのモデルを個別に管理する代わりに、一つのモデルから計算予算に応じた動作を選ぶという着想。
元の実験要約には『計算量50%削減で精度低下0.8%』『最大60%削減』との数値があるが、
論文本文を今回の実行環境では再照合していない。数値の断定や他モデルへの一般化は禁止。
再学習不要や数分での変換も研究の主張として扱い、一般的な保証としない。
研究対象の範囲外への普遍化、実運用コスト削減の保証、実体験の創作は禁止。"""

def build_prompt() -> str:
    return f"{WRITER_BRIEF}\n\n研究素材:\n{SOURCE_SUMMARY}\n"

def check_article(article: str) -> list[str]:
    errors = []
    if not article.startswith("# "):
        errors.append("missing_markdown_h1")
    if SOURCE not in article:
        errors.append("missing_source_url")
    if len(article) < 450:
        errors.append("article_too_short")
    return errors

def generate_once(client) -> dict:
    if OUTPUT.exists():
        raise RuntimeError("Output exists: refusing repeat")
    response = client.models.generate_content(model=MODEL, contents=build_prompt())
    article = str(getattr(response, "text", "") or "").strip()
    if not article:
        raise RuntimeError("Empty Gemini response")
    errors = check_article(article)
    OUTPUT.mkdir(parents=True, exist_ok=False)
    (OUTPUT / "article.md").write_text(article + "\n", encoding="utf-8")
    result = {
        "model": MODEL,
        "source": SOURCE,
        "provider_attempts": 1,
        "local_checks": {"errors": errors},
        "factual_verification": "HUMAN_REVIEW_REQUIRED",
        "quality_verdict": "HUMAN_REVIEW_REQUIRED",
        "publication": "PROHIBITED",
    }
    (OUTPUT / "review.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result

def main() -> None:
    if os.environ.get("AIIF_FREE_WRITER_CONFIRM") != "FREE_WRITER_ONCE":
        raise RuntimeError("Explicit one-shot confirmation required")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing GEMINI_API_KEY")
    from google import genai
    print(json.dumps(generate_once(genai.Client(api_key=key)), ensure_ascii=False))

if __name__ == "__main__":
    main()
