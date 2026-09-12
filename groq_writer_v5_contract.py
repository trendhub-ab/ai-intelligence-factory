"""Groq-only writer v5 contract: reader length without evidence inflation.

The contract is intentionally isolated from Gemini Production. It hardens the Compound
Mini article-only pass and validates the prose before the canonical Production gates.
"""
from __future__ import annotations

import json
from pathlib import Path
import re


class GroqWriterV5Error(RuntimeError):
    pass


V5_CONTRACT = r"""

【V5 READER-LENGTH + EVIDENCE PRECISION CONTRACT — 最優先】
これは製品説明書ではなく、非エンジニアが最後まで読めて判断が変わる記事です。以下を最優先し、前段の曖昧な表現よりこの契約を優先してください。

【長さと構成】
- 本文は1400〜2100日本語文字。1400字未満のまま返答してはいけない。返答直前に本文量を自己点検し、短ければ新Factを足さずに再展開する。
- 導入のあとに `##` で始まる記事固有の見出しを3個置く。太字だけを見出し代わりにしない。
- 本文全体は7〜10段落。段落長を揃えず、短い段落と説明段落を混ぜる。Markdown箇条書き・番号リストは禁止。
- 安全に広げてよい論点は次の4つだけ：①100%という数字と測定条件を分けて読む理由、②V8脆弱性20件の評価と2件のzero-day発見が一次資料で示されたこと、③安全策は名称が示されているが名称から動作を推測してはいけないこと、④能力の高さと実際の利用条件を分けて判断すること。
- 同じFactを言い換えて水増ししない。読者が「だから判断がどう変わるのか」を自然文で掘る。

【Reader First】
- 1段落目は「100%」または「2件のzero-day」をフックにする。ただし数字の対象・条件を同じ段落か次段落ですぐ限定する。
- 最初の900字以内に日常の比喩を1つだけ入れる。能力と利用条件が別物だと分かる比喩にし、比喩をFactとして扱わない。
- 最後の2段落以内に必ず一人称の判断を1文入れる。WATCHなら「私なら、今すぐ導入判断はせず、まず一次情報で利用条件を確認します。」と同等の強さで言う。
- 「まとめると」で終えない。最後は要約ではなく、読者が次に何を確認すべきかで閉じる。

【用語の安全な言い換え】
- Preparedness Framework：本文では「OpenAIのPreparedness Frameworkという評価枠組み」まで。『サイバー防御力を評価する枠組み』など用途を勝手に限定しない。
- Critical cybersecurity capability threshold：「重大なサイバー能力の基準」程度にとどめる。『防御能力』へ置き換えない。
- ExploitBench：一次資料どおり「既知脆弱性からexploitを開発する評価」と説明してよい。
- zero-day脆弱性：読者向けには「新たに見つかった未知の脆弱性」程度の短い補足にとどめる。
- exploit chain：「攻撃手順がつながる流れ」程度の短い補足にとどめ、具体的な攻撃方法を足さない。

【SOURCE BOUNDARY】
Ledgerにない比較優位、アクセス対象、将来提供、運用方法、安全策の動作・効果を推測しない。
次のような表現は禁止：
「最高レベル」「他のAIモデルは未到達」「サイバー作戦の最前線で使える」「特定権限ユーザーのみ」「リアルタイムで評価」「継続的に異常をチェック」「自動的に介入」「一般的な本番環境では使えない」「限定環境でのみ提供」「必要な認可を取得」「安全策が安心材料」「利用可能になるまでのハードル」「アクセス条件や運用方法は公開されていない」。
確認できないことは「この一次資料からは確認できません」と書く。『公開されていない』『存在しない』へ変換しない。
"""

FORBIDDEN_PHRASES = (
    "最高レベル",
    "他のAIモデルがまだ到達",
    "他のAIモデルはまだ到達",
    "サイバー作戦の最前線で使える",
    "特定の権限を持つユーザーのみ",
    "特定権限ユーザーのみ",
    "リアルタイムで評価",
    "利用状況や異常な挙動を継続的にチェック",
    "継続的に異常をチェック",
    "自動的に介入",
    "一般的な本番環境での利用は想定されていません",
    "一般的な本番環境での利用は想定されていない",
    "一般的な本番環境では使えない",
    "限定的な環境でのみ提供",
    "限定環境でのみ提供",
    "必要な認可を取得",
    "安心材料",
    "利用可能になるまでのハードル",
    "一般的な利用環境では同じ結果が得られるとは限りません",
)


def harden_writer_fixture(path: str) -> dict:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("provider") != "groq" or data.get("model") != "groq/compound-mini":
        raise GroqWriterV5Error("writer_fixture_provider_mismatch")
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise GroqWriterV5Error("writer_fixture_prompt_missing")
    if "V5 READER-LENGTH + EVIDENCE PRECISION CONTRACT" not in prompt:
        data["prompt"] = prompt.rstrip() + V5_CONTRACT
    data["contract_version"] = "groq_writer_v5_reader_length_precision"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def _extract(text: str) -> tuple[str, str]:
    match = re.fullmatch(r"\s*===TITLE===\s*\n(.+?)\n===ARTICLE===\s*\n(.+)\s*", text or "", re.S)
    if not match:
        raise GroqWriterV5Error("writer_output_format_invalid")
    return match.group(1).strip(), match.group(2).strip()


def validate_writer_report(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        text = data["result"]["text"]
    except (KeyError, TypeError):
        raise GroqWriterV5Error("writer_result_missing") from None
    title, article = _extract(text)

    unsupported = [phrase for phrase in FORBIDDEN_PHRASES if phrase in article]
    if unsupported:
        raise GroqWriterV5Error("writer_source_boundary_violation:" + "|".join(unsupported))

    patterns = (
        r"Preparedness\s*Framework[^。！？\n]{0,90}防御力",
        r"Critical\s*cybersecurity\s*capability\s*threshold[^。！？\n]{0,90}防御能力",
        r"system\s*safety\s*classifier[^。！？\n]{0,90}(?:リアルタイム|自動|判定|評価)",
        r"misalignment\s*detection[^。！？\n]{0,100}(?:自動|介入|停止|修正)",
        r"(?:監視|monitoring)[^。！？\n]{0,100}(?:ログ|継続的|リアルタイム|異常な挙動)",
        r"(?:アクセス条件|運用方法)[^。！？\n]{0,80}公開されてい(?:ない|ません)",
        r"(?:アクセス制限)[^。！？\n]{0,100}(?:特定の権限|特定ユーザー|のみアクセス|認可取得)",
    )
    if any(re.search(pattern, article, re.I) for pattern in patterns):
        raise GroqWriterV5Error("writer_inferred_or_mistranslated_claim")

    if len(article) < 1300:
        raise GroqWriterV5Error("writer_reader_article_too_short")
    if len(article) > 2600:
        raise GroqWriterV5Error("writer_reader_article_too_long")
    headings = re.findall(r"(?m)^##\s+\S.+$", article)
    if not 2 <= len(headings) <= 4:
        raise GroqWriterV5Error("writer_heading_contract_invalid")
    if re.search(r"(?m)^\s*\*\*[^\n]+\*\*\s*$", article):
        raise GroqWriterV5Error("writer_bold_heading_forbidden")
    if re.search(r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)", article):
        raise GroqWriterV5Error("writer_list_output_forbidden")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", article) if part.strip() and not part.strip().startswith("##")]
    if not 7 <= len(paragraphs) <= 12:
        raise GroqWriterV5Error("writer_paragraph_contract_invalid")
    opening = article[:1000]
    if not re.search(r"(?:たとえば|例えば|簡単に言えば|使う側から見ると|似ています|ようなもの)", opening):
        raise GroqWriterV5Error("writer_reader_bridge_missing")
    if not re.search(r"(?:私なら|私たちなら)", article[-650:]):
        raise GroqWriterV5Error("writer_decision_voice_missing")
    if re.search(r"(?:^|\n\n)まとめると[、,]", article):
        raise GroqWriterV5Error("writer_summary_ending_forbidden")
    if not title.endswith(("。", "？")):
        raise GroqWriterV5Error("writer_title_punctuation_invalid")

    data["v5_source_boundary_validated"] = True
    data["v5_reader_contract_validated"] = True
    data["v5_article_chars"] = len(article)
    data["v5_headings"] = len(headings)
    data["v5_paragraphs"] = len(paragraphs)
    return data
