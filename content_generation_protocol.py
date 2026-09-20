from __future__ import annotations

import json
import re

# Run243: canonical deterministic article-generation / presentation protocol.
# No provider SDK, network, persistence, environment or credential access is allowed here.

def build_monthly_digest_markdown(target_date, items: list[dict], *, STATUS_DEEP_DIVE, ARTICLE_STATUS_READY, STATUS_STOCKED) -> str:
    """
    当月データセットから、運用者・購読者向けの月次ダイジェストMarkdownを
    組み立てる。Deep Dive済み案件（Step2詳細スコア）とストックのみ案件
    （Step1軽量スコア）は採点基準が異なるため、Statusプロパティで区別し、
    セクション・ランキングを分離して混同を防ぐ。
    """
    month_label = f"{target_date.year}年{target_date.month}月"

    # Subscriber向けDigestでは、内部Needs Editorial ReviewをDeep Dive完成記事として
    # 扱わない。ReadyのみDeep Dive、その他はStock資産として集計する。
    digest_items = []
    for it in items:
        row = dict(it)
        if row.get("status") == STATUS_DEEP_DIVE and row.get("article_status") != ARTICLE_STATUS_READY:
            row["status"] = STATUS_STOCKED
        digest_items.append(row)

    by_status: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for it in digest_items:
        by_status[it["status"]] = by_status.get(it["status"], 0) + 1
        by_source[it["source"]] = by_source.get(it["source"], 0) + 1

    deep_dive_items = sorted(
        (it for it in digest_items if it["status"] == STATUS_DEEP_DIVE and it.get("article_status") == ARTICLE_STATUS_READY),
        key=lambda x: (x["score"] or 0), reverse=True,
    )
    stocked_items_top10 = sorted(
        (it for it in digest_items if it["status"] == STATUS_STOCKED),
        key=lambda x: (x["score"] or 0), reverse=True,
    )[:10]

    lines = [
        f"# {month_label} 全データセットダイジェスト",
        "",
        f"- 総収集件数: {len(items)}件",
        "- 内訳（ステータス別）: " + (", ".join(f"{k} {v}件" for k, v in by_status.items()) or "-"),
        "- 内訳（ソース別）: " + (", ".join(f"{k} {v}件" for k, v in by_source.items()) or "-"),
        "",
        f"## Deep Dive記事一覧（{len(deep_dive_items)}件・Step2詳細スコア順）",
        "",
    ]
    lines += (
        [f"- [{it['name']}]({it['url']}) - {it['score']}点 / {it['source']}" for it in deep_dive_items]
        or ["（今月はDeep Dive記事の生成はありませんでした）"]
    )
    lines += [
        "",
        "## ストックのみ案件 Top10（Step1軽量スクリーニングスコア順）",
        "",
    ]
    lines += (
        [f"- [{it['name']}]({it['url']}) - {it['score']}点 / {it['source']}" for it in stocked_items_top10]
        or ["（該当なし）"]
    )
    lines += [
        "",
        "---",
        "",
        "※本ダイジェストはNotion DBへの当月新規保存分を自動集計したものです。",
        "※「Decision Score」はDeep Dive済み案件ではStep2詳細スコア、ストックのみの"
        "案件ではStep1軽量スクリーニングスコアであり、採点基準が異なります"
        "（Statusプロパティで判別可能。詳細はPROP_STATUSのコメントを参照）。",
    ]
    return "\n".join(lines)


def _source_fact_discipline(source: str) -> str:
    """Sourceごとの典型的な誤推論を、Deep Diveの同一call内で抑制する。"""
    common = """
【全ソース共通 Fact Discipline】
・Sourceが確認している「事実」、そこから導く「推論」、筆者としての「判断」を混同しない。
・一次情報が示すCapability（できること）を、そのままSuperiority（競合より優れる）やBusiness Outcome
  （売上増・コスト削減・生産性向上・品質向上）へ変換しない。
・根拠のない具体性を足さない。％、倍、円、ドル、ms、秒、日数、週間、月数、人数、GPU台数、
  導入期間、ROI、削減額などは、一次情報に明示された条件付き数値か、明確に「筆者が置くPoC目安」
  とラベルしたもの以外は書かない。
・「唯一」「一択」「必須」「デファクト」「最有力」「圧倒的」「劇的」「革命的」「完全」「保証」
  などの強い語は、一次情報や複数の比較根拠で直接支えられない限り使わない。
・競合製品の最新機能、価格、安定性、優劣は、Source ContextまたはGroundingで当該競合の現行一次情報を
  確認できた場合だけ具体的に述べる。確認できない場合は「比較が必要」と書く。
・OSS/self-host/local-first/OpenTelemetry/MCP/API互換などの属性だけから、低コスト、安全、移行容易、
  低ロックイン、高性能、将来の標準化を断定しない。
・ニュースや製品紹介の見出しを、さらに強い日本語へ増幅しない。
・3〜12ヶ月の未来は予言しない。必ず「条件 → 起こり得る結果 → 見るべき指標」の形にする。
・現在仕様が変わりやすい料金、API、モデル、CLI、対応OS、制限、cache、preview/beta/stable状態は、
  取得できた現在の一次情報だけを根拠にする。古い記事と現在docsが衝突する場合は現在docsを優先する。
"""
    rules = {
        "GitHub": """
【GitHub専用 Fact Discipline】
・READMEにある機能の存在は「何ができるか」の証拠であり、「最適」「標準」「競合優位」の証拠ではない。
・Star数、Download数、Contributor数は普及度の参考であり、品質・信頼性・商用品質の証明ではない。
・OSSであることを、ロックインなし・低TCO・高セキュリティと同義にしない。
・コマンド、設定値、環境変数、API endpointはREADME/公式docsに実在する表記だけを使う。推測でCLIを作らない。
・実装例やdemoがあることを、大規模production運用やSLAの証明として扱わない。
""",
        "ArXiv": """
【arXiv専用 Fact Discipline】
・研究結果とproduction/commercial/clinical readinessを明確に分離する。
・論文中のbenchmark数値を出すなら、dataset/task、metric、comparator、実験条件を可能な範囲で併記する。
  文脈が取れない裸の数値は記事に使わない。
・transferable≠universal、equivariant/physics-informed≠reliable、efficient≠low-cost、
  interpretable≠regulatory explainability、robust≠production fault tolerance、高精度≠商用優位。
・研究者が実験できたことと、読者が公開物だけで再現できることを同一視しない。
・費用、必要人員、役職、GPU台数、導入期間、ROI、商用化時期を論文から推測して具体化しない。
・医療・臨床テーマでは、後ろ向き/研究データの結果を診療意思決定や実臨床導入へ直結させない。
  外部検証、前向き検証、calibration、安全性、規制等が未確認なら明示する。
""",
        "ProductHunt": """
【Product Hunt専用 Fact Discipline】
・Product Hunt本文、製品サイト、launch copyのbest/fast/easy/secure/enterprise-ready/production-ready等は、
  原則「ベンダー自身の主張」として扱い、第三者評価へ変換しない。
・self-host可能→TCO削減、local-first→安全、MCP対応→将来標準、free trial→導入コスト低、
  多数integration→生産性向上、とは自動変換しない。
・価格、無料枠、対応OS、export、privacy、data residency等は変わりやすい。現在の一次情報で確認できない場合は断定しない。
・競合比較はlaunch copyの言い分をそのまま採用しない。
""",
        "HackerNews": """
【Hacker News専用 Fact Discipline】
・HNタイトルやリンク先見出しの強い表現を、そのまま業界全体の転換点・企業の緊急課題へ拡張しない。
・News significanceとBusiness urgencyを分ける。企業方針変更を勧めるのは具体的影響範囲が確認できる場合だけ。
・元記事が特定企業/製品の公式ブログなら、競合情報をモデル記憶から補わない。
・preview / beta / nightly / experimental / PR / development build と stable/general availabilityを必ず分離する。
・ニュース公開時点の仕様を「現在仕様」と固定しない。現在docsと衝突するなら差分を明示する。
""",
    }
    return common + rules.get(source, "")


def _human_editorial_style_rules() -> str:
    """Surface guidance only; persona, story and self-edit have canonical owners."""
    return """
【Human Editorial Style｜最重要】
この節は表現の補助であり、Fact / Evidence / DecisionおよびCanonical Article Contractを優先する。
人格はSystem Instruction、Evidence / Fact制約はSOURCE BOUNDARYとFact Discipline、
Editorial Story設計とFinal Reader CheckはCanonical Article Contract、出力形式はOutput Contractに従う。
・です・ます調を土台に、読者を一人の人として扱う。教師の講義や監査報告書の距離感にしない。
・編集語彙を一記事に積み重ねない。必要な語を単発で使うのはよい。
・各節を同じ「結論→理由→箇条書き→注意」の型へ押し込まない。文や段落の長さを揃えない。
・見出しは記事固有の内容から作る。別の記事でも使える汎用的な導入・判断フレーズへ逃げない。
・接続詞で論理を毎回明示しすぎない。「ここで重要なのは」「つまり」「注目すべきは」等を反復しない。
・「Aではありません。Bです。」、機械的な列挙、同じ語尾、短文の連打で流れを演出しない。
・同じ内容を言い換えて二度説明しない。箇条書きは比較・条件・行動を一覧にした方が理解が速い場所に使う。
・架空の経験・感情は作らない。「私なら、この条件なら試す」は判断として書けるが、実体験として語らない。

【Reader Experience｜知的エンタメ × Decision Intelligence】
・難しいことを難しく感じさせない。意味や身近な働きから説明し、必要な正式名称・条件を残す。
・中学生〜非エンジニアが一読後に核心を自分の言葉で1文説明でき、専門家にも嘘がない入口を作る。
・未知語を未説明のまま積み重ねず、普通の言葉で役割を示す。専門語の固定個数制限は設けない。
・比喩は概念理解の補助でありEvidenceではない。必要なら使い、技術上の対応と限界へ戻す。
・比喩を入れること自体を目的にしない。生活の例は理解が速くなる時だけ選び、B2Bへ無理に持ち込まない。
・Security / Risk等では軽薄な冗談を強制しない。事実・数値・重要制約は会話調でぼかさない。
・【無料note記事の最上位編集目標】「楽しい」「わかりやすい」「自分にも関係がある」。
  技術レポートとして整っているだけでは完成としない。Evidence・数値・制約・反証・Decisionの正確さは絶対に落とさず、理解が進む順序で渡す。
・Reader Delightは導入だけでなく本文全体の発見と理解の進展で作る。かわいい比喩や口語で技術的な芯を代替しない。
・Reader Proximityは無料note記事の完成条件として扱う。「読者との距離が近くなる一文」は理解・疑問・判断に関係する時に置く。
  回数ノルマや必須の語尾は設けない。例示される口語も固定語でもない。落ち着いた語りでもよい。
・読者に同意を強要しない。語りかけは装飾ではなく理解の橋とし、中身のない問いを置かない。何を見ればよいか・なぜ自分に関係するかへつなぐ。
・親しみやすさのために文章を足し算しない。硬い説明の置換であり追記ではない。平易な判断の言葉へ戻す。
・Evidence、数値、制約、比較、反証、Decisionは先に削らない。Decisionに不要な内部実装、規格番号・略語の列挙、重複説明を整理する。
・一次情報に存在する技術名を全部ARTICLEへ転記することは禁止。有料会員向けProduct Review / Notion DBの情報密度をARTICLE圧縮に合わせて削らない。
・親近感から新しい固有名詞・利用実績・市場評価を補わず、Fact Gate / Source Boundaryの表面積を増やさない。
・親しみ不足だけを理由とする再生成callは追加しない。完成稿への内部編集はcanonical Final Reader Checkで一度行う。
"""

EDITORIAL_STYLE_CLASSIC = "classic"
EDITORIAL_STYLE_HUMAN_NARRATIVE = "human_narrative"
EDITORIAL_STYLE_CHOICES = (
    EDITORIAL_STYLE_CLASSIC,
    EDITORIAL_STYLE_HUMAN_NARRATIVE,
)


def _human_narrative_editorial_style_rules() -> str:
    """Narrative-forward surface guidance layered on top of the classic contract."""
    return _human_editorial_style_rules() + """

[AIIF_HUMAN_NARRATIVE_EDITORIAL_STYLE_V1]
【Human Narrative Editorial Style｜記事を最後まで読ませる編集】
このスタイルはFact / Evidence / Decision / Publication Gateを変更しない。既存のHuman Editorial Styleを土台に、
無料noteの記事本文だけを「正しい説明」から「人間が続きを読みたくなる説明」へ寄せる。追加Provider callは使わない。

・冒頭は製品名・論文名・機能一覧から始めず、Evidenceの範囲で人間が頭の中で場面を描ける入口を優先する。
  ただし架空の会話、架空の失敗、架空の実体験・利用経験を事実のように置かない。
・難しい仕組みは、役割や因果が理解しやすくなる場合だけ、仕事・日常・人の動きへ一度置き換えてよい。
  比喩やツッコミの直後は、何を説明している比喩かを明確にし、専門内容へ必ず戻る。
・ユーモアは理解の報酬として使う。強い語・悪口・擬人化・ネットスラングを重ねず、
  「1セクションに必ず1回笑わせる」をノルマにしない。笑いがなくても読者の理解が前進するならそれでよい。
・同じ比喩・会社員ネタ・擬人化を別記事へ使い回さない。記事固有のEvidence、制約、意外性から自然な表現を選ぶ。
・技術説明 → 人間にとっての意味 → 軽い一言、の流れは使えるが固定テンプレートにしない。
  段落の長短や見出しの温度を揃えず、記事固有のリズムを作る。
・事実・数値・制約・反証・Decisionを笑いのために弱めない。重要な条件や限界をオチ扱いにせず、
  読者が誤解しやすい箇所では「ただし」「ここは勘違いしない方がよい」等、自然な言葉で現実へ戻す。
・タイトルは面白さだけでなく「何の記事か」が分かることを優先する。一次情報で確認できない成功体験や、
  「うちの〜」「やってみた」「ビビった」等の実体験のように見える一人称を作らない。
・一人称は編集上の判断に限定する。「私なら比較する」「私なら小さく試す」はDecisionとして使えるが、
  実際に使った・壊した・驚いた・困った等の経験を創作しない。
・終盤は要約の言い直しだけで閉じず、Evidenceから導ける読者の現実的な判断へ着地する。
  日常への短い回帰や余韻は使えるが、新しい事実や架空の体験をオチとして追加しない。
・完成稿は「詳しい人が難しいことを面白く説明してくれ、気づけば核心を理解していた」距離感を目指す。
  面白さのために情報量を増やさず、説明文を人間の理解順へ置き換える。
"""


def editorial_style_rules(style_name: str | None = None) -> str:
    """Return one deterministic editorial style contract; unknown styles fail closed."""
    normalized = (style_name or EDITORIAL_STYLE_CLASSIC).strip().lower()
    if normalized == EDITORIAL_STYLE_CLASSIC:
        return _human_editorial_style_rules()
    if normalized == EDITORIAL_STYLE_HUMAN_NARRATIVE:
        return _human_narrative_editorial_style_rules()
    raise ValueError(f"unknown editorial style: {style_name!r}")



def _parse_gemini_response(full_text: str, *, SECTION_SPLIT_TOKEN, _display_heading_aliases, _extract_any_markdown_section, _extract_note_title, _is_meaningful_field, _normalize_decision, _strip_internal_note_control_lines) -> dict:
    """
    管理用データとnote本文を分離する。
    Geminiの管理用ラベル出力が揺れても、500円記事本文の固定見出しをCanonical fallbackとして使う。
    """
    parts = full_text.split(SECTION_SPLIT_TOKEN, 1)
    management_data = parts[0]
    if len(parts) > 1:
        title_text, note_draft = _extract_note_title(parts[1].strip())
        note_draft, _ = _strip_internal_note_control_lines(note_draft)
    else:
        title_text, note_draft = "（タイトル抽出失敗）", ""

    NEXT_ITEM = r"(?=\n・[^\n]+[:：]|\n\n|$)"
    total_match = re.search(r"合計[:：]?\s*(\d+)\s*/\s*100", management_data)
    score = int(total_match.group(1)) if total_match else 0
    breakdown_match = re.search(
        r"・Decision Score[:：]\s*(.*?)(?=\n・Why NOT Important|\n・Who Should Use|\n・Action|\n・Future Scenario|\n・Article Value|$)",
        management_data, re.DOTALL,
    )
    score_breakdown_text = breakdown_match.group(1).strip() if breakdown_match else ""

    adoption_breakdown_match = re.search(
        r"・Adoption Score[:：]\s*(.*?)(?=\n・Adoption Status|\n・Evidence Confidence|$)",
        management_data, re.DOTALL,
    )
    adoption_score_breakdown_text = adoption_breakdown_match.group(1).strip() if adoption_breakdown_match else ""
    adoption_total_match = re.search(
        r"・Adoption Score[:：][^\n]*?合計[:：]?\s*(\d+)\s*/\s*100",
        management_data, re.IGNORECASE,
    )
    adoption_score = int(adoption_total_match.group(1)) if adoption_total_match else 0

    def extract_field(label: str, fallback: str = "") -> str:
        m = re.search(rf"・{re.escape(label)}[^:：\n]*[:：]\s*(.*?){NEXT_ITEM}", management_data, re.DOTALL)
        return m.group(1).strip() if m else fallback

    # 管理用ラベルを正とし、本文側は可変見出しにも対応したFallbackにする。
    body_sections = {
        "source_summary_text": _extract_any_markdown_section(note_draft, _display_heading_aliases("what")),
        "what_text": _extract_any_markdown_section(note_draft, _display_heading_aliases("what")),
        "why_important_text": _extract_any_markdown_section(note_draft, _display_heading_aliases("why")),
        "paradigm_shift_text": _extract_any_markdown_section(note_draft, ["本当に変わるのは何か"]),
        "alternative_comparison_text": _extract_any_markdown_section(note_draft, ["既存の選択肢と比べるとどうか"]),
        "migration_cost_text": _extract_any_markdown_section(note_draft, ["導入コストとリスク", "導入前に見ておきたいところ。"]),
        "decision_reason_text": _extract_any_markdown_section(note_draft, ["なぜそう判断したのか"]),
        "why_not_important_text": _extract_any_markdown_section(note_draft, ["誰は使わなくていいか"]),
        "who_should_use_text": _extract_any_markdown_section(note_draft, ["誰が使うべきか"]),
        "who_should_not_use_text": _extract_any_markdown_section(note_draft, ["誰は使わなくていいか"]),
        "action_text": _extract_any_markdown_section(note_draft, _display_heading_aliases("decision")),
        "future_scenario_text": _extract_any_markdown_section(note_draft, ["3〜12ヶ月で起こり得ること"]),
    }

    article_raw = extract_field("Article Value", "0")
    article_match = re.search(r"(\d{1,3})", article_raw)
    article_value = min(100, max(0, int(article_match.group(1)))) if article_match else 0

    decision_text = _normalize_decision(extract_field("Decision", ""))
    decision_section = _extract_any_markdown_section(note_draft, _display_heading_aliases("decision"))
    if not decision_text:
        decision_text = _normalize_decision(decision_section)
    if score == 0:
        article_score_match = re.search(r"(?:Decision\s*Score[^0-9]*)?(\d{1,3})\s*/\s*100", decision_section, re.IGNORECASE)
        if article_score_match:
            score = min(100, max(0, int(article_score_match.group(1))))

    def field_or_body(label: str, body_key: str) -> str:
        value = extract_field(label, "")
        return value if _is_meaningful_field(value) else body_sections.get(body_key, "")

    return {
        "note_draft": note_draft,
        "title_text": title_text,
        "score": score,
        "score_breakdown_text": score_breakdown_text,
        "adoption_score": adoption_score,
        "adoption_score_breakdown_text": adoption_score_breakdown_text,
        "adoption_status": extract_field("Adoption Status", "").strip().upper(),
        "evidence_confidence": extract_field("Evidence Confidence", "").strip().upper(),
        "production_readiness": extract_field("Production Readiness", "").strip().upper(),
        "main_risk_text": extract_field("Main Risk", ""),
        "best_for_text": extract_field("Best For", ""),
        "avoid_for_text": extract_field("Avoid For", ""),
        "short_rationale_text": extract_field("Short Rationale", ""),
        "source_summary_text": field_or_body("Source Summary", "source_summary_text"),
        "what_text": field_or_body("What", "what_text"),
        "why_important_text": field_or_body("Why Important", "why_important_text"),
        "paradigm_shift_text": field_or_body("技術的パラダイムシフト", "paradigm_shift_text"),
        "alternative_comparison_text": field_or_body("代替との比較", "alternative_comparison_text"),
        "migration_cost_text": field_or_body("移行コストとリスク", "migration_cost_text"),
        "decision_text": decision_text,
        "decision_reason_text": field_or_body("Decision Reason", "decision_reason_text"),
        "why_not_important_text": field_or_body("Why NOT Important", "why_not_important_text"),
        "who_should_use_text": field_or_body("Who Should Use", "who_should_use_text"),
        "who_should_not_use_text": field_or_body("Who Should NOT Use", "who_should_not_use_text"),
        "action_text": field_or_body("Action", "action_text"),
        "future_scenario_text": field_or_body("Future Scenario", "future_scenario_text"),
        "article_value": article_value,
    }


def _promote_plaintext_section_titles(article: str) -> tuple[str, list[str]]:
    """Promote unmistakable plain-text section labels to Markdown headings without an LLM.

    Some strong long-form generations write content-specific section labels as standalone lines
    but omit the ``###`` marker. This repair is deliberately conservative: long-form only, after
    the Reader-First metadata block, blank-line isolated, short Japanese label, substantial prose
    immediately after it, and at least two independent candidates. A single ambiguous line is
    never promoted.
    """
    body = article or ""
    if len(re.sub(r"\s+", "", body)) < 1200:
        return body, []
    lines = body.splitlines()
    metadata_end = -1
    for i, line in enumerate(lines):
        if re.match(r"^#{2,4}\s+元情報\s*$", line.strip()):
            metadata_end = i
            break
    if metadata_end < 0:
        return body, []

    candidates: list[int] = []
    for i in range(metadata_end + 1, len(lines) - 2):
        raw = lines[i]
        label = raw.strip()
        if not label or raw != label:
            continue
        if i == 0 or lines[i - 1].strip() or lines[i + 1].strip():
            continue
        if re.match(r"^(?:#{1,6}\s|[-*+]\s|\d+[.)、]\s*|>|```|---+$)", label):
            continue
        visible = re.sub(r"\s+", "", label)
        if not (8 <= len(visible) <= 56):
            continue
        if re.search(r"[。！？!?；;：:]$", label) or re.search(r"https?://|`|\[[^]]+\]\(", label):
            continue
        if len(re.findall(r"[ぁ-んァ-ヶ一-龯々]", label)) < 4:
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            continue
        block: list[str] = []
        while j < len(lines) and lines[j].strip():
            if re.match(r"^(?:#{1,6}\s|```|---+$)", lines[j].strip()):
                break
            block.append(lines[j].strip())
            j += 1
        if len(re.sub(r"\s+", "", "".join(block))) < 80:
            continue
        candidates.append(i)

    if len(candidates) < 2:
        return body, []
    if any(b - a < 3 for a, b in zip(candidates, candidates[1:])):
        return body, []
    changed: list[str] = []
    for i in candidates:
        label = lines[i].strip()
        lines[i] = f"### {label}"
        changed.append(label)
    return "\n".join(lines), changed


def build_decision_prompt(name, url, stars, desc, quality_feedback: str='', source: str='GitHub', source_context: str='', grounding_status_hint: str=None, evidence_metadata: dict | None=None, freshness: dict | None=None, previous_article: str='', evidence_result: dict | None=None, *, engagement_labels, max_evidence_total_chars, truncate_source_context, source_fact_discipline, human_editorial_style_rules, article_display_variant, section_split_token, datetime_cls, jst):
    """無料ARTICLEと記事公開に必要な最小MANAGEMENT DATAだけを生成する。

    Adoption/Production Readiness等の会員向け評価はProduct Review経路へ完全分離し、
    無料記事の生成負荷・Hallucination面積を増やさない。parserは旧出力互換を維持する。
    """
    metric_label = engagement_labels.get(source, 'Engagement')
    metric_note = ''
    if source == 'ArXiv':
        metric_note = '※arXivにはStars/Votes相当の人気指標がないため、人気度を0とみなして価値判断しないこと。\n'
    feedback = f'\n【前回出力への編集フィードバック】\n{quality_feedback}\n事実違反は該当箇所だけを直す。全文を保守的に均さず、根拠付きの判断・具体的な行動・タイトルの引力は残す。具体的Actionを『注視する』だけに置き換えない。\n' if quality_feedback else ''
    previous = ''
    if previous_article:
        previous = '\n【局所修正の対象となる前回ARTICLE】\n以下の前回稿を基準に、編集フィードバックで指定された箇所だけを修正して、同じ出力形式の完全稿を返すこと。指定外の根拠付き判断・見出し・構成を一般論へ置換しない。\n' + previous_article[:max_evidence_total_chars] + '\n'
    context = truncate_source_context(source_context)
    fact_rules = source_fact_discipline(source)
    style_rules = human_editorial_style_rules()
    display = article_display_variant(name)
    evidence_json = json.dumps(evidence_metadata or {}, ensure_ascii=False, indent=2)
    freshness_context = (freshness or {}).get('context', '')
    evidence_result = evidence_result or {}
    evidence_guardrails = []
    if evidence_result.get('limitations_disclosed'):
        evidence_guardrails.append('一次資料で実運用上の制約は確認できないことをWhy NOTまたはCaveatに明記し、本番導入を強く推奨しない。')
    if evidence_result.get('freshness_scope_limited'):
        evidence_guardrails.append('現在仕様とは断定せず、『原資料公開時点では』『この研究で確認された範囲では』と時点を限定する。')
    if not evidence_result.get('numeric_claims_allowed', True):
        evidence_guardrails.append('条件を確認できない数値・性能値はARTICLEで使わない。')
    if not evidence_result.get('actor_attribution_allowed', True):
        evidence_guardrails.append('主体の帰属を確認できない固有名詞の断定はしない。')
    if evidence_result.get('action_risk_tier', 'LOW') == 'LOW' and evidence_result.get('evidence_gap_disclosed'):
        evidence_guardrails.append('Actionは『注視』だけで終わらせず、限定PoC、評価項目への追加、ログ可視化、比較テスト、見送りのいずれかを具体的に提案する。全面導入・本番移行は提案しない。')
    evidence_guardrail_text = '\n'.join(('・' + item for item in evidence_guardrails)) or '・取得済み一次情報の範囲を超える断定をしない。'
    return f"""\nSystem Instructionの編集思想に従い、下記のEvidence / Fact制約を厳守してください。\n以下の一次情報から、無料公開のnote記事として読者の判断を助ける記事と、記事公開に必要な最小管理データを作成してください。\n会員向けTechnology評価（Adoption Score / Adoption Status / Evidence Confidence / Production Readiness / Main Risk / Best For / Avoid For）は別工程で作るため、ここでは絶対に生成しないでください。\n\n【読者】主対象はCTO、テックリード、PM、AI/ソフトウェア導入の意思決定者。ただし専門知識を前提にせず、非エンジニアや一般読者でも入口から理解でき、専門家には判断材料が残る二層構造で書く。\n【最重要】ARTICLEは人が読む文章、MANAGEMENT DATAは機械が読む構造データ。両者を混ぜない。\nただし Source Summary / What / Why Important / Decision Reason / Action は、後段で公開Reader Summaryの入力候補にもなる。\n機械用だからと専門語を圧縮して詰め込まず、各項目だけ読んでも非専門読者が「何が起きた／なぜ重要／どう動く」を理解できる短い日本語にする。\n必要な正式名称・略語は、Reader Summaryに不可欠な場合だけ、役割が普通の日本語で分かる形にする。ARTICLEのFact/Evidence/Decisionと意味を一致させ、新しい事実は足さない。\n【出力を途中で切らないための優先順位】\n1. SECTION_SPLIT_TOKEN、記事タイトル、記事本文の最後の「最終判断」までを最優先で完走する。\n2. MANAGEMENT DATAは下記の8項目だけを簡潔に出す。記事本文を削って管理項目を増やさない。\n3. 無根拠な背景説明・一般論・競合列挙を追加しない。\n4. 不確かな比較・将来予測・導入コストを埋めるために推測しない。途中で省略記号を使わない。\n【事実優先順位】Source Native Context > Primary URL取得内容 > Google Search Grounding（有効時） > モデル内部知識。\n\n【SOURCE BOUNDARY — 最重要】\n・ARTICLEで「事実」として断定してよい技術仕様・対応状況・価格・数値・競合情報・固有名詞は、原則としてSource Native ContextまたはGroundingで確認できる内容だけ。\n・モデル内部知識から背景説明を補う場合は、製品固有の事実として書かず、「一般論として」「ここからは私の推論だが」など、読者が推論だと分かる形にする。\n・Source Contextにない企業向け管理製品、競合機能、API仕様、OS/ブラウザ管理方式などを、もっともらしい補足として追加しない。\n・ニュース公開時点の仕様と現在のStable仕様は同一視しない。現在仕様をGroundingで確認できなければ「元記事公開時点では」と限定する。\n・不明点は補完せず「一次情報からは確認できない」と書く。\n・「確認できない」「記載がない」「未公開」「不明」等の不在Claimは、Evidence Coverageが SEARCHED_NOT_FOUND または NOT_DISCLOSED の項目だけに限る。NOT_SEARCHEDまたはSource Depth不足では不在を断定しない。\nモデル内部知識だけで現在仕様、競合比較、数値、価格、対応状況を断定しない。\n\n【Evidence-to-Decisionの安全制約】\n{evidence_guardrail_text}\n\n{fact_rules}\n{style_rules}\n\n【対象】\n・出所: {source}\n・名前: {name}\n・Primary URL: {url}\n・{metric_label}: {stars}\n{metric_note}・概要: {desc}\n・事前Grounding: {grounding_status_hint}\n・Article generation date: {datetime_cls.now(jst).date().isoformat()}\n\n【Source Native Context】\n{context or '（source-native本文不足。Primary URLで確認できた範囲以外を現在事実として補完しないこと。）'}\n\n【Structured Evidence / Required Qualifiers — 最優先】\n{evidence_json}\n・required_qualifiers は自然な日本語に言い換えてよいが、ARTICLEから絶対に削除しない。\n・TOY_EXAMPLE相当の証拠は「原著の単純な例では」「著者が示したサンプルでは」等、例の範囲を必ず明示する。\n・「保証」「完全」「必ず」「安全」等の強い表現は、Structured EvidenceまたはSource Contextが同等以上の保証を明示する場合だけ使用できる。\n・一次情報に限界・未解決課題・"promising"・条件付きの性能値がある場合、ARTICLEにも必ず残す。性能値はデータセット、解像度、反復回数、ハードウェア等の条件を削らない。\n・Hacker News等は発見経路である。実験値・仕様の根拠となったPrimary URL/PDFは「参考情報」に出るため、HNだけを根拠として数値を説明しない。フォローアップに言及する場合はEvidenceにあるURLだけを使う。\n\n【Freshness Resolution】\n{freshness_context or '公式フォローアップは未検出。元資料の将来表現を現在完了の事実に書き換えない。'}\n・Follow-up Sourceがある場合、それより古い「今後予定」「これから議論」等の状態をARTICLEに残さない。\n{feedback}\n{previous}\n\n【Output Contract｜完成稿のみ】\nEditorial Story Brief、Narrative Questionの内部メモ、Self-Editの過程、初稿は出力しない。\n最初に必ず次の見出しをそのまま出す。\n=== MANAGEMENT DATA ===\nその下に以下の8項目だけを順序通り、各行「・ラベル: 値」で簡潔に出す。\n・Source Summary: 公開面の30秒要約にも使う。一次情報で確認できる事実を1〜2文で、技術名の羅列ではなく何が確認されたかが単独で分かる日本語にする。必要な正式名称・専門語は意味が変わる場合だけ残す。\n・What: 公開面の30秒要約にも使う。何が起きたかを普通の日本語1文で書き、Decisionに不要な実装識別子・略語・専門語の列挙を避ける。正式名がないと意味が変わる場合だけ必要最小限に残す。\n・Why Important: 公開面の30秒要約にも使う。技術の説明を繰り返すのではなく、読者の判断・コスト・運用・選択にどう関係するかを普通の日本語1文で書く。未検証効果は推論と明示。\n・Decision: NOW / TRY / WATCH / WAIT / AVOID の1つ。\n・Decision Reason: 最大3理由を簡潔に。公開Reader Summaryの旧互換fallbackにもなり得るため、技術名の列挙ではなくDecisionを支える意味が普通の日本語で分かる形にする。\n・Decision Score: Business Impact X/25; Technical Impact X/25; Urgency X/20; Market Impact X/15; Reliability X/15; 合計 X/100\n・Action: 次に検証する具体的行動。公開Reader Summaryの旧互換fallbackにもなり得るため、まず試す／比較する／待つ／見送る等の行動距離を普通の日本語で先に示し、必要な実装名は後置する。根拠のない日数・金額を作らない。\n・Article Value: 0〜100\n\n会員向け評価、競合比較、移行コスト、将来シナリオ、Who Should Use等をMANAGEMENT DATAへ追加しない。必要な実務上の対象読者・制約はARTICLE本文へ自然に書く。\n\n次に必ず専用行を出す。\n{section_split_token}\n\nその次の1行を記事タイトルにする。#は付けない。プロのコピーライターとして、技術の要点と読者の関心を結び、短く惹きつけるタイトルにすること。必ず「。」「？」のいずれかで終える。\n\n【ARTICLE】\n記事はすべて無料公開する。有料エリア、有料マーカー、無料部分／有料部分という区分を一切出力しない。\n\n導入候補のヒントは「{display['style']}」「{display['opening']}」「{display['tone']}」。採用義務はなく、Evidenceから形成するEditorial Story Briefを優先する。\nこれらは読者に見せるラベルでも見出しでもない。既成の見出し文や段落テンプレートを再現せず、記事固有の内容に合わせて自由に構成する。\n\nタイトル直後は、読者が「何の話か」「なぜ自分に関係するか」をつかめる自然なリードから始める。\nRoadmapやprotocolの話でも、冒頭を「〜とは」「主な変更点は」「今回のロードマップでは」の説明開始に固定しない。まず読者が引っかかる変化・困りごと・意外性を1つ置き、専門用語は理解が必要になった時点で名前を付ける。\nリードの段落数は固定しない。1〜3段落程度を目安に、必要な情報だけを書く。\n発見経路や「一次情報に基づく」という説明を義務的な定型文として毎回入れない。出典は公開稿の「元情報」で別途提示されるため、本文では話を理解するのに必要な場合だけ自然に触れる。\n\n本文の見出しは2〜6個程度を目安に、記事固有の内容から自分で作る。本文セクションの見出しは必ずMarkdownの `##` または `###` を付け、見出し文だけを裸の1行として置かない。以下は内部の意味役割であり、見出し名や順番を固定しない。\n・何が起きた／何が変わったのか\n・なぜ読者の判断に関係するのか\n・仕組みや条件のうち、判断に必要な部分\n・面白さと同時に見ておくべき制約\n・筆者なら次に何をするか\n\nすべての役割を毎回独立セクションにしない。内容が自然につながるなら統合する。\n一方で、記事の終盤には「読者が結局どう動けばよいか」が分かる判断セクションを必ず1つ置く。見出しは記事内容に合わせて自然な日本語で作り、管理用Decisionコードは書かない。\n\n【構成上の禁止】\n・Why → What → Key → Decision のような内部構造を、そのまま同じ順番・同じ粒度の見出しへ露出しない。\n・旧テンプレートの「先に判断を書くと。」「なぜ、この問題が残り続けるのか。」「今回の仕組みを見てみる。」「導入前に押さえたいポイント。」等をセットで再利用しない。\n・各セクションを同じ文字量にそろえない。\n・全セクションを同じ「説明→注意→結論」で閉じない。\n\n【ARTICLEの追加ルール】\n・NOW / TRY / WATCH / WAIT / AVOID は内部管理コードであり、ARTICLEには絶対に表示しない。括弧書き、英字併記、見出し内も禁止。\n・「私ならこう考える」では、管理用Decisionを読者向けの自然な判断文に翻訳する。目安は次の通り。\n  NOW → 「今すぐ動く価値がある」「今から着手してよい」\n  TRY → 「まずは小さく試す価値がある」「限定した環境で試したい」\n  WATCH → 「今は動かず、今後の動きを注視したい」「導入を急ぐ段階ではない」\n  WAIT → 「現時点では導入を急がない」「条件が整うまで待つのがよい」\n  AVOID → 「今は見送るのが妥当」「現時点では採用しない方がよい」\n・上の日本語は定型句として毎回そのまま使わず、記事の文脈に合わせて自然に言い換える。Decision ScoreやBusiness Impact等の内部採点もARTICLEへ一切出さない。採点はMANAGEMENT DATAだけに置く。\n・Adoption Score / Adoption Status / Evidence Confidence / Production Readiness も商品DB管理値であり、ARTICLEへラベルや点数をそのまま表示しない。\n・競合名を出す場合、Source Native Contextにその競合の比較根拠が存在する時だけ。なければ製品名を列挙しない。\n・Preview/Beta/Stableは必ず分離する。\n・ニュース公開時点の仕様を現在仕様として断定しない。現在確認できない場合は「元記事公開時点では」と書く。\n・根拠のない%・倍数・金額・期間・性能値を作らない。\n・「唯一」「一択」「必須」「デファクト」「圧倒的」「劇的」「完全に解決」等は、一次情報だけで立証できない限り使わない。\n・記事全体を箇条書き帳票にしない。導入を含め、読者が技術の背景から判断まで自然に追える流れにする。\n・「結局、どうするべきか」の結論は管理用Decisionと意味的に一致させる。ただし内部コードは書かない。\n・根拠に照らして限定検証、比較テスト、導入見送り、次版待ちなどの判断が妥当なら、理由と対象範囲を添えて明確に書く。安全性のためにすべてを「可能性がある」「注視したい」へ弱めない。\n・記事本文の文字数を品質目標にしない。同じ事実の言い換え反復、Decisionに不要な実装列挙、長いコード例、説明の二重化は削る。一方で、Evidence・数値条件・制約・比較・反証・Decisionを文字数のために削らない。長くても読者が迷わず読み進められる情報順序と温度変化を優先する。\n"""
