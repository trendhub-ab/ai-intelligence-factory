"""Zero-API Groq writer contract hardening for article parity v4.

This module is Groq-only. It never mutates Gemini Production logic. It strengthens the
article-writer prompt after the two-pass fixture is built, then validates the returned
prose before the current Production gates run.
"""
from __future__ import annotations

import json
from pathlib import Path
import re


class GroqWriterV4Error(RuntimeError):
    pass


V4_CONTRACT = r"""

【V4 READER-FIRST CONTRACT — 追加必須条件】
- これは製品説明書ではなく「読んだ人の判断が変わる記事」です。機能一覧・安全策一覧を順番に説明しない。
- 冒頭は「100%」または「2件のzero-day」のどちらかをフックにし、1段落目で読者が『え、どういうこと？』と思う緊張を作る。ただし測定条件は同じ段落か直後で必ず限定する。
- 最初の900字以内に、日常のたとえを1つだけ入れる。比喩はFactではないことが明確な表現にし、例として「鍵のかかった研究室」「運転免許とレーシングカー」のように、能力と利用条件が別物だと理解できるものにする。
- Preparedness Framework / ExploitBench / zero-day / exploit chain は、初出時に中学生でも分かる日本語を同じ文か直後に添える。
- 安全策は名称の列挙にとどめ、名称から動作を推測して説明しない。個別機能を1項目ずつ解説しない。
- 段落の長さを意図的に変える。短い1〜2文の段落と、説明段落を混ぜ、90字以上の説明段落を3つ連続させない。
- 「〜されています」「〜となっています」「〜ことです」を連続させない。文末を混ぜる。
- 最後の2段落以内に、読者への明確な判断を1文入れる。Decisionコードは書かず、WATCHなら『私なら、今すぐ導入判断はせず、まず一次情報で利用条件を確認します。』のように、Planのdecision/actionを人間の言葉で言う。
- 結論を「まとめると」で始めない。記事全体の要約を繰り返さず、読者の次の判断で閉じる。
- 目安は1500〜2300日本語文字。Evidenceを増やして水増ししない。

【SOURCE BOUNDARY — 書いてはいけない具体化】
Ledgerに明記されていない限り、次を断定しない：
「最高レベル」「他のAIモデルは未到達」「サイバー作戦の最前線で使える」「特定の権限を持つユーザーのみ」「リアルタイムで評価」「利用状況を継続的にチェック」「自動的に介入」「一般的な本番環境での利用は想定されていない」「限定的な環境でのみ提供」「必要な認可を取得」。
安全策の名称は、その名称のまま紹介してよい。仕組み・対象・効果は推測しない。
"""

# High-precision phrases observed in the failed v3 artifact. They all add mechanics, scope,
# comparisons, or availability claims beyond the B0049 ALLOWED FACT LEDGER.
FORBIDDEN_UNSUPPORTED_PHRASES = (
    "最高レベル",
    "他のAIモデルがまだ到達",
    "他のAIモデルはまだ到達",
    "サイバー作戦の最前線で使える",
    "特定の権限を持つユーザーのみ",
    "リアルタイムで評価",
    "利用状況や異常な挙動を継続的にチェック",
    "自動的に介入",
    "一般的な本番環境での利用は想定されていません",
    "一般的な本番環境での利用は想定されていない",
    "限定的な環境でのみ提供",
    "必要な認可を取得",
)


def harden_writer_fixture(path: str) -> dict:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("provider") != "groq" or data.get("model") != "groq/compound-mini":
        raise GroqWriterV4Error("writer_fixture_provider_mismatch")
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise GroqWriterV4Error("writer_fixture_prompt_missing")
    if "V4 READER-FIRST CONTRACT" not in prompt:
        data["prompt"] = prompt.rstrip() + V4_CONTRACT
    data["contract_version"] = "groq_writer_v4_reader_first"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def _extract_article(text: str) -> str:
    match = re.fullmatch(r"\s*===TITLE===\s*\n.+?\n===ARTICLE===\s*\n(.+)\s*", text or "", re.S)
    if not match:
        raise GroqWriterV4Error("writer_output_format_invalid")
    return match.group(1).strip()


def validate_writer_report(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        text = data["result"]["text"]
    except (KeyError, TypeError):
        raise GroqWriterV4Error("writer_result_missing") from None
    article = _extract_article(text)

    unsupported = [phrase for phrase in FORBIDDEN_UNSUPPORTED_PHRASES if phrase in article]
    if unsupported:
        raise GroqWriterV4Error("writer_source_boundary_violation:" + "|".join(unsupported))

    # Additional mechanics that are unsafe when attached to named safeguards in this fixture.
    mechanics_patterns = (
        r"system safety classifier[^。！？\n]{0,80}(?:リアルタイム|自動|判定|評価)",
        r"misalignment detection[^。！？\n]{0,100}(?:自動|介入|停止|修正)",
        r"(?:監視|monitoring)[^。！？\n]{0,90}(?:ログ|継続的|リアルタイム|異常な挙動)",
        r"(?:アクセス制限)[^。！？\n]{0,100}(?:特定の権限|特定ユーザー|のみアクセス|認可取得)",
    )
    hits = [pattern for pattern in mechanics_patterns if re.search(pattern, article, re.I)]
    if hits:
        raise GroqWriterV4Error("writer_inferred_safeguard_mechanics")

    # Reader-first invariants: deterministic minimums before expensive Production gate analysis.
    if len(article) < 1300:
        raise GroqWriterV4Error("writer_reader_article_too_short")
    opening = article[:1000]
    if not re.search(r"(?:たとえば|例えば|簡単に言えば|使う側から見ると|似ています|ようなもの)", opening):
        raise GroqWriterV4Error("writer_reader_bridge_missing")
    if not re.search(r"(?:私なら|私たちなら|現時点では|まず一次情報|まず公式|判断)", article[-650:]):
        raise GroqWriterV4Error("writer_decision_voice_missing")
    if article.rstrip().startswith("まとめると") or re.search(r"(?:^|\n\n)まとめると[、,]", article):
        raise GroqWriterV4Error("writer_summary_ending_forbidden")

    data["v4_source_boundary_validated"] = True
    data["v4_reader_contract_validated"] = True
    return data
