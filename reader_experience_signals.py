"""Canonical zero-API reader-experience diagnostics extracted from pipeline.py."""

from __future__ import annotations

import re


def reader_experience_signals(article: str, article_opening_excerpt_fn) -> dict:
    """0-API diagnostics for reader pull without creating new hard gates.

    Run140 treats delight as the combination of clarity, human proximity, and an article-specific
    reason to keep reading. Missing analogy, humor, or a particular catchphrase is never itself
    a failure; a plain but engaging explanation can still be GOOD.
    """
    body = article or ""
    headings = [re.sub(r"\s+", " ", h).strip() for h in re.findall(r"^#{2,3}\s+(.+)$", body, re.MULTILINE)]
    prose = re.sub(r"^#{1,6}\s+.*$", "", body, flags=re.MULTILINE)
    visible = re.sub(r"\s+", "", prose)
    sentences = [x.strip() for x in re.split(r"(?<=[。！？!?])", prose) if x.strip()]
    long_sentences = sum(len(re.sub(r"\s+", "", x)) >= 105 for x in sentences)

    common = {"AI", "API", "LLM", "OSS", "URL", "UI", "UX", "DB", "CPU", "GPU", "ID"}
    acronyms = []
    for m in re.finditer(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9-]{1,8})(?![A-Za-z0-9])", prose):
        token = m.group(1)
        if token in common or token in acronyms:
            continue
        near = prose[max(0, m.start()-90):m.end()+120]
        explained = bool(re.search(rf"(?:{re.escape(token)}\s*[（(].{{2,70}}[）)]|[（(].{{2,70}}[）)]\s*{re.escape(token)}|.{{3,90}}[（(]{re.escape(token)}[）)]|{re.escape(token)}(?:とは|は、|は){{1}}.{{4,80}}(?:仕組み|方式|規格|標準|ツール|モデル|プロトコル|ルール))", near, re.S))
        if not explained:
            acronyms.append(token)

    tech_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_.+/#-]{2,}|[ァ-ヴー]{5,}", prose)
    technical_density = len(tech_tokens) * 1000.0 / max(len(visible), 1)

    intro = article_opening_excerpt_fn(body, 700)
    announcement_only = bool(
        intro and re.match(r"^.{0,45}(?:発表|公開|リリース|更新)(?:しました|された|されました|した)", intro.strip())
        and not re.search(r"(?:なぜ|困|変わ|仕事|生活|使|意外|面白|気にな|身近|たとえば|例えば|もし|ところが|実際)", intro[:520])
    )
    self_relevance = bool(re.search(r"(?:あなた|私たち|現場|仕事|会社|チーム|利用者|ユーザー|開発者|担当者|日常|スマホ|生活|導入する側|使う側|旅行|買い物|学校|家族)", intro[:700] or prose[:700]))
    curiosity = bool(re.search(r"(?:意外|不思議|面白|なぜ|一見|ところが|変わる|違い|気になる|もし|何が|逆に|実際には)", intro[:700]))

    analogy_markers = re.findall(r"(?:たとえば|例えば|〜のような|ようなもの|たとえるなら|例えるなら|まるで|身近な|もし.+なら)", prose)
    analogy_used = bool(analogy_markers)
    playful_topics = re.findall(r"(?:猫|犬|恋愛|デート|コンビニ|家族|料理|ゲーム|旅行)", prose)
    analogy_overuse = len(analogy_markers) >= 4 or (len(playful_topics) >= 4 and len(set(playful_topics)) >= 2)
    serious_theme = bool(re.search(r"(?:security|risk|governance|cyber|脆弱性|攻撃|侵害|情報漏えい|規制|監査|ガバナンス|セキュリティ|リスク)", body, re.I))
    tone_mismatch = serious_theme and len(playful_topics) >= 2

    # Run127: narrative pull is weakened by long uninterrupted explanatory blocks.
    paragraphs = [re.sub(r"\s+", " ", x).strip() for x in re.split(r"\n\s*\n", prose) if re.sub(r"\s+", "", x)]
    explanatory_paras = 0
    max_explanatory_run = 0
    current_run = 0
    pull_markers_re = re.compile(r"(?:[？?]|たとえば|例えば|もし|ところが|一方|逆に|意外|実際|場面|朝\d{0,2}時|困る|怖い|変わる|比べ|なのに)")
    for para in paragraphs:
        is_explain = len(re.sub(r"\s+", "", para)) >= 90 and not pull_markers_re.search(para)
        if is_explain:
            explanatory_paras += 1
            current_run += 1
            max_explanatory_run = max(max_explanatory_run, current_run)
        else:
            current_run = 0
    scene_present = bool(re.search(r"(?:朝\d{1,2}時|会議を|予約を|店を探|予定を|メールを|カレンダー|スマホで|旅行|買い物|学校で|家で|電車で|もし[^。！？]{4,100}(?:頼|言|すると|なら))", prose))
    narrative_pull = curiosity or scene_present or max_explanatory_run <= 2

    # Headings should carry article-specific nouns, not mostly generic labels.
    generic_heading_re = re.compile(r"^(?:なぜ重要(?:なのか)?|何が変わる(?:のか)?|今後どうなる(?:のか)?|今すぐ導入すべき(?:なのか)?|最終判断|まとめ|結論|ポイント|要点|詳細)[。？?]?$" )
    generic_headings = [h for h in headings if generic_heading_re.fullmatch(h)]
    heading_pull = not (len(headings) >= 3 and len(generic_headings) >= 2)

    # Article-specific angle: avoid copy-pastable meta prose without topic-bearing nouns.
    generic_angle_hits = len(re.findall(r"(?:今回の発表|今回の変化|この技術|この仕組み|このニュース|今後に注目|動向を見ていき)", prose))
    specific_heading_chars = sum(len(re.sub(r"(?:なぜ|重要|今後|判断|まとめ|結論|ポイント|詳細|何が|変わる)", "", h)) for h in headings)
    article_specific_angle = generic_angle_hits <= 3 and (not headings or specific_heading_chars >= max(8, len(headings) * 3))

    # Run128: an everyday/plain-language bridge becomes recommended when jargon load is high.
    # This remains a soft diagnostic: Evidence/Fact/Decision gates are never weakened or blocked by it.
    everyday_terms = bool(re.search(r"(?:旅行|レストラン|買い物|家族|恋愛|デート|学校|趣味|猫|犬|ゲーム|SNS|スマホ|料理|引っ越し|電車|病院|天気|スポーツ|友人|会議|メール|カレンダー|鍵|合鍵|受付|店|財布|地図|図書館)", prose))
    plain_explanation = bool(re.search(
        r"(?:簡単に言えば|ひと言で言えば|一言で言えば|平たく言えば|要するに|言葉を変えると|"
        r"つまり[^。！？]{3,90}(?:仕組み|ルール|方法|考え方|役割)|"
        r"(?:これは|これはつまり|この仕組みは)[^。！？]{4,100}(?:ための|ような)(?:仕組み|ルール|方法|考え方|もの))",
        prose,
    ))
    bridge_needed = bool(acronyms) or technical_density >= 26.0
    plain_language_bridge_present = bool(everyday_terms or scene_present or analogy_used or plain_explanation)
    if plain_language_bridge_present:
        everyday_bridge = "PRESENT"
    elif bridge_needed:
        everyday_bridge = "REVIEW_NEEDED"
    else:
        everyday_bridge = "NOT_REQUIRED"

    # A dense paragraph with several technical tokens and no translation marker is a useful
    # zero-API signal for the exact failure mode seen in the Run127 real-article regression.
    jargon_dense_paragraphs = 0
    for para in paragraphs:
        pv = re.sub(r"\s+", "", para)
        if len(pv) < 70:
            continue
        p_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_.+/#-]{2,}|[ァ-ヴー]{5,}", para)
        p_density = len(p_tokens) * 1000.0 / max(len(pv), 1)
        has_translation = bool(re.search(r"(?:たとえば|例えば|簡単に言えば|ひと言で言えば|一言で言えば|平たく言えば|要するに|つまり|ようなもの|身近な|スマホ|買い物|恋愛|デート|鍵|学校|旅行|料理|家族)", para))
        if p_density >= 38.0 and not has_translation:
            jargon_dense_paragraphs += 1
    jargon_translation = "GOOD" if not (bridge_needed and not plain_language_bridge_present) and jargon_dense_paragraphs <= 1 else "REVIEW"
    non_engineer_core_clarity = "GOOD" if jargon_translation == "GOOD" and (not bridge_needed or plain_language_bridge_present) else "REVIEW"

    # News relevance must come from explicit temporal/event language, not fabricated freshness.
    news_relevance = bool(re.search(r"(?:今回|発表|公開|更新|リリース|対応を開始|採用|仕様変更|公開された|新たに|今週|今日|\d{4}[-年/]\d{1,2})", intro[:900]))

    last = prose[-1000:]
    return_pull = bool(re.search(r"(?:次に|次版|今後|試す|比較|検証|確かめ|判断|選択|待つ|見送|導入|変化|残る|問い|条件|自分なら|私なら)", last))

    # Run131: measure actual reader proximity, not merely the presence of an everyday noun.
    # Run129 was too permissive: a dry sentence containing "スマホ" could be labelled warm even
    # when no human conversational distance was created. We now require a functional proximity
    # moment while keeping it soft-only so warmth cannot consume retry budget or raise rejection.
    conversational_patterns = [
        r"ですよね[。！？!?]", r"なんですよ[。！？!?]", r"やっぱり[、,]",
        r"ちょっと想像してみてください", r"ここが面白いところ",
        r"思い出してみてください", r"ありますよね[。！？!?]",
        r"(?:使った|見た|聞かれた|困った|迷った)こと(?:は)?(?:ありませんか|ありますか|ありますよね)",
        r"(?:難しそう|大げさ|物々しい)(?:な名前|に見え|に聞こえ)[^。！？]{0,45}(?:ですが|けれど|ものの)",
        r"名前は難しそう[^。！？]{0,45}(?:ですが|でも)",
        r"(?:想像|思い浮かべ)して(?:みる|みて)",
    ]
    conversational_hits = sum(len(re.findall(p, prose)) for p in conversational_patterns)
    reader_question_hits = len(re.findall(r"(?:でしょうか|ませんか|ありますか|ありますよね|ですよね|感じませんか|思いませんか|考えたくなりますよね)[。！？!?]", prose))
    friendly_turn_hits = len(re.findall(r"(?:難しそう(?:ですが|でも)|名前は難し|意外と単純|やっていることは[^。！？]{0,35}(?:単純|シンプル)|身近な話にすると)", prose))
    reader_proximity_moments = conversational_hits + reader_question_hits + friendly_turn_hits
    repeated_conversational_phrase = any(len(re.findall(p, prose)) >= 3 for p in conversational_patterns)
    conversational_overuse = conversational_hits >= 7 or reader_question_hits >= 6 or repeated_conversational_phrase
    conversational_warmth = reader_proximity_moments >= 1

    # Run133: Reader-first rhythm and editorial compression diagnostics.
    # The goal is not to reward chatter. We measure whether a non-engineer gets an early foothold,
    # whether dense technical explanation runs too long, and whether the article exposes too many
    # implementation identifiers for a free reader-facing note article. All signals stay soft-only.
    opening_prose = re.sub(r"\s+", " ", prose[:900]).strip()
    opening_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_.+/#-]{2,}|[ァ-ヴー]{5,}", opening_prose)
    opening_density = len(opening_tokens) * 1000.0 / max(len(re.sub(r"\s+", "", opening_prose)), 1)
    opening_reader_bridge = bool(re.search(
        r"(?:[？?]|ありませんか|ありますよね|ですよね|たとえば|例えば|もし|スマホ|買い物|旅行|学校|家族|仕事で|使う側|普通の言葉|簡単に言えば|要するに|意外|困った|迷った)",
        opening_prose,
    ))
    opening_non_engineer_access = "GOOD" if opening_density < 42.0 and (opening_reader_bridge or not bridge_needed) else "REVIEW"

    # Count implementation-heavy identifiers. This is deliberately conservative: we do not claim
    # every token is jargon, only detect an overloaded surface area that often correlates with the
    # Run132 failure mode (RFC numbers, flags, acronyms, internal component names, etc.).
    implementation_identifiers = re.findall(
        r"\b(?:SEP-\d+|RFC\s?\d+|[A-Z]{2,8}-\d{2,}|[A-Z]{2,8}\d{2,}|[A-Z]{3,8}|[A-Za-z]+/[A-Za-z0-9_.-]+)\b",
        prose,
    )
    unique_implementation_identifiers = sorted(set(implementation_identifiers))
    implementation_detail_load = "REVIEW" if len(unique_implementation_identifiers) >= 8 else "GOOD"

    # A reader-friendly article should not stay in dense-explanation mode for three paragraphs in a row.
    # We reuse max_explanatory_run so this adds no model call and no second parsing pipeline.
    reader_temperature_rhythm = "GOOD" if max_explanatory_run <= 2 else "REVIEW"

    accessibility_issues = []
    if acronyms: accessibility_issues.append("unexplained_acronyms")
    if long_sentences >= 3: accessibility_issues.append("long_sentence_cluster")
    if technical_density >= 34: accessibility_issues.append("technical_term_concentration")
    if bridge_needed and not plain_language_bridge_present: accessibility_issues.append("plain_language_bridge_missing")
    if jargon_dense_paragraphs >= 2: accessibility_issues.append("jargon_translation_weak")
    if opening_non_engineer_access != "GOOD": accessibility_issues.append("opening_non_engineer_access_weak")
    if implementation_detail_load != "GOOD": accessibility_issues.append("implementation_detail_overload")
    if reader_temperature_rhythm != "GOOD": accessibility_issues.append("reader_temperature_rhythm_weak")
    enjoyment_issues = []
    if analogy_overuse: enjoyment_issues.append("analogy_overuse")
    if tone_mismatch: enjoyment_issues.append("serious_topic_tone_mismatch")
    if announcement_only: enjoyment_issues.append("announcement_summary_opening")
    if not self_relevance: enjoyment_issues.append("reader_bridge_weak")
    if max_explanatory_run >= 4: enjoyment_issues.append("explanation_run_long")
    if not heading_pull: enjoyment_issues.append("generic_heading_cluster")
    if not article_specific_angle: enjoyment_issues.append("article_specific_angle_weak")
    if not news_relevance: enjoyment_issues.append("news_relevance_weak")
    if not conversational_warmth: enjoyment_issues.append("reader_proximity_missing")
    if conversational_overuse: enjoyment_issues.append("conversational_tone_overuse")

    # Run142: Narrative Understanding Progression.
    # Reader Delight must reflect understanding that moves forward, not a checklist of warm words.
    _paras = [x.strip() for x in re.split(r"\n\s*\n", prose) if x.strip()]
    _body_after_opening = "\n\n".join(_paras[1:]) if len(_paras) > 1 else prose
    narrative_progression_hits = len(re.findall(
        r"(?:ところが|理由(?:の一つ)?が|なぜなら|その結果|だからこそ|だから|すると|そこで|一方で|でも|では導入すれば|つまり何が|何が困る|何を意味する|につながる|ためです|からです)",
        prose,
    ))
    causal_explanation_hits = len(re.findall(
        r"(?:理由|なぜ|ため|ので|その結果|だから|そこで|つまり|一方で|ところが|すると)", prose
    ))
    decision_or_implication_hits = len(re.findall(
        r"(?:私なら|判断|導入|安全性|意味|困る|価値|影響|使うなら|見るべき|確認|試して|比較)", prose
    ))
    factual_substance_hits = len(re.findall(
        r"(?:ニューロン|特徴|活性化|非直交|ベクトル|重み|回路|因果|制約|互換性|一次資料|"
        r"Sparse Autoencoder|Superposition|Polysemanticity|辞書学習|スパース|"
        r"権限|最小権限|アクセス|ログ|承認|監視|演算性能|メモリ|帯域|消費電力|ベンチマーク|"
        r"コスト|冷却|モデル|トークン|暗号|認証|脆弱性|API|プロトコル)",
        prose, re.I,
    ))
    analogy_hits = len(re.findall(
        r"(?:たとえば|例える|ような|みたい|押し入れ|収納|合鍵|家族|スマホ|料理|電車|棚|箱|引き出し)", prose
    ))
    report_style_body_hits = len(re.findall(
        r"(?:評価します|解析します|同定します|抽出します|確認します|検討します|必要があります|方式です|発生します|分布します)",
        _body_after_opening,
    ))
    body_reader_bridge_hits = len(re.findall(
        r"(?:ですよね|ませんか|感じませんか|思いませんか|難しそう|身近|困る|なぜ|だから|ところが|でも|そこで|私なら)",
        _body_after_opening,
    ))
    warm_hook_cold_body = (
        reader_proximity_moments >= 1
        and len(_paras) >= 3
        and report_style_body_hits >= 4
        and body_reader_bridge_hits <= 1
    )
    analogy_substance_thin = analogy_hits >= 3 and factual_substance_hits <= 3 and causal_explanation_hits <= 2
    # Run144: concise good prose can show progression through a concrete technical core + caveat/action,
    # without mandatory catchphrases or a fixed number of explicit causal connectors.
    caveat_or_concrete_action = bool(re.search(
        r"(?:ただし|とは限ら|わけではありません|保証されるわけでは|まず[^。！？]{0,80}(?:試|比較|確認|限定)|"
        r"小さ(?:く|な環境)|範囲を広げ|比較対象|見送|待つ|段階(?:的に)?導入)",
        prose, re.I,
    ))
    explicit_reader_decision_action = bool(re.search(
        r"(?:私なら|導入するなら|使うなら|判断(?:します|する|材料)|比較(?:します|する|対象)|"
        r"確認(?:します|する)|まず[^。！？]{0,80}(?:試|比べ|確認)|見送(?:ります|る)|追(?:います|う)|"
        r"検証(?:します|する)|段階(?:的に)?導入)",
        prose, re.I,
    ))
    practical_reader_progression = (
        len(_paras) >= 3
        and factual_substance_hits >= 2
        and opening_non_engineer_access == "GOOD"
        and (self_relevance or plain_language_bridge_present or reader_proximity_moments >= 1)
        and explicit_reader_decision_action
        and caveat_or_concrete_action
        and decision_or_implication_hits >= 1
    )
    narrative_understanding_progression = (
        (
            narrative_progression_hits >= 2
            and causal_explanation_hits >= 2
            and decision_or_implication_hits >= 1
            and factual_substance_hits >= 2
        )
        or practical_reader_progression
    )
    if warm_hook_cold_body:
        enjoyment_issues.append("warm_hook_cold_body")
    if analogy_substance_thin:
        enjoyment_issues.append("analogy_substance_thin")
    if not narrative_understanding_progression:
        enjoyment_issues.append("narrative_understanding_progression_weak")

    # Run140: composite reader outcome. This remains 0-API and soft-only: it does not trigger
    # an extra Gemini call by itself. The generation prompt is responsible for achieving it.
    reader_delight_good = (
        opening_non_engineer_access == "GOOD"
        and reader_proximity_moments >= 1
        and not conversational_overuse
        and article_specific_angle
        and self_relevance
        and (plain_language_bridge_present or not bridge_needed)
    )
    # Run144: Reader Delight is a balance, not an AND-list of conversational tokens.
    # Hard-negative patterns stay strict; positive quality may be demonstrated by independent signals.
    reader_delight_overclaim = bool(re.search(
        r"(?:完全に理解できれば|完全に整理できます|完全に取り出せ|ブラックボックス問題は解決|"
        r"危険な挙動も事前に見抜け|必須条件にします|すぐ全社導入|私なら今のうちに導入します)",
        prose, re.I,
    ))
    # Repetition is measured across distinct paragraphs, not by repeated technical nouns.
    _paragraph_fragment_counts = {}
    for _para in _paras:
        _compact = re.sub(r"https?://\S+|`[^`]+`|[A-Za-z0-9_.:/+-]+|[\s。、！？!?「」『』（）()【】#*_>・:：;；,，.-]+", "", _para)
        _seen = set()
        for _idx in range(max(0, len(_compact) - 6)):
            _piece = _compact[_idx:_idx + 7]
            if len(_piece) == 7:
                _seen.add(_piece)
        for _piece in _seen:
            _paragraph_fragment_counts[_piece] = _paragraph_fragment_counts.get(_piece, 0) + 1
    repeated_cross_paragraph_fragments = [k for k, v in _paragraph_fragment_counts.items() if v >= 3]
    repetitive_insight = len(repeated_cross_paragraph_fragments) >= 3
    if reader_delight_overclaim:
        enjoyment_issues.append("reader_delight_overclaim")
    if repetitive_insight:
        enjoyment_issues.append("repetitive_insight")

    positive_reader_signals = sum(bool(x) for x in (
        opening_non_engineer_access == "GOOD",
        article_specific_angle,
        plain_language_bridge_present or not bridge_needed,
        self_relevance or reader_proximity_moments >= 1 or everyday_terms or scene_present,
        factual_substance_hits >= 2,
        explicit_reader_decision_action and caveat_or_concrete_action,
        narrative_understanding_progression,
        curiosity or return_pull,
    ))
    reader_delight_base = (
        positive_reader_signals >= 6
        and opening_non_engineer_access == "GOOD"
        and article_specific_angle
        and (plain_language_bridge_present or not bridge_needed)
        and factual_substance_hits >= 2
        and explicit_reader_decision_action
    )
    reader_delight = "GOOD" if (
        reader_delight_base
        and narrative_understanding_progression
        and not conversational_overuse
        and not warm_hook_cold_body
        and not analogy_substance_thin
        and not reader_delight_overclaim
        and not repetitive_insight
    ) else "REVIEW"

    # Reader-value budget: length itself is never a defect. Diagnose only the patterns that make
    # an article *feel* long to a non-engineer: repeated dense explanation, duplicated analogy,
    # implementation overload, or long uninterrupted explanatory runs. Evidence/Decision depth may
    # legitimately require a longer article, so character count remains observability only.
    article_char_count = len(re.sub(r"\s+", "", prose))
    information_budget = "GOOD"
    if (
        jargon_dense_paragraphs >= 3
        or (len(analogy_markers) >= 3 and technical_density >= 30.0)
        or (max_explanatory_run >= 4 and technical_density >= 26.0)
        or (len(unique_implementation_identifiers) >= 10 and jargon_dense_paragraphs >= 2)
    ):
        information_budget = "REVIEW"

    accessibility = "GOOD" if not accessibility_issues else "REVIEW"
    curiosity_pull = "GOOD" if (curiosity or self_relevance) and not announcement_only else "REVIEW"
    reader_enjoyment = "GOOD" if not enjoyment_issues else "REVIEW"
    return_status = "GOOD" if return_pull else "REVIEW"
    return {
        "accessibility": accessibility,
        "curiosity_pull": curiosity_pull,
        "reader_enjoyment": reader_enjoyment,
        "return_pull": return_status,
        "narrative_pull": "GOOD" if narrative_pull and max_explanatory_run < 4 else "REVIEW",
        "article_specific_angle": "GOOD" if article_specific_angle else "REVIEW",
        "everyday_bridge": everyday_bridge,
        "plain_language_bridge": "GOOD" if plain_language_bridge_present or not bridge_needed else "REVIEW",
        "jargon_translation": jargon_translation,
        "non_engineer_core_clarity": non_engineer_core_clarity,
        "headline_pull": "GOOD" if heading_pull else "REVIEW",
        "news_relevance": "GOOD" if news_relevance else "REVIEW",
        "conversational_warmth": "GOOD" if conversational_warmth and not conversational_overuse else ("REVIEW_OVERUSE" if conversational_overuse else "REVIEW_MISSING"),
        "conversational_marker_count": conversational_hits,
        "reader_proximity_moment_count": reader_proximity_moments,
        "reader_proximity": "GOOD" if reader_proximity_moments >= 1 and not conversational_overuse else ("REVIEW_OVERUSE" if conversational_overuse else "REVIEW_MISSING"),
        "reader_delight": reader_delight,
        "reader_delight_positive_signals": positive_reader_signals,
        "reader_delight_overclaim": reader_delight_overclaim,
        "repetitive_insight": repetitive_insight,
        "caveat_or_concrete_action": caveat_or_concrete_action,
        "explicit_reader_decision_action": explicit_reader_decision_action,
        "narrative_understanding_progression": "GOOD" if narrative_understanding_progression else "REVIEW",
        "narrative_progression_hits": narrative_progression_hits,
        "causal_explanation_hits": causal_explanation_hits,
        "factual_substance_hits": factual_substance_hits,
        "analogy_hits": analogy_hits,
        "warm_hook_cold_body": warm_hook_cold_body,
        "analogy_substance_thin": analogy_substance_thin,
        "information_budget": information_budget,
        "opening_non_engineer_access": opening_non_engineer_access,
        "opening_technical_terms_per_1000_chars": round(opening_density, 1),
        "implementation_detail_load": implementation_detail_load,
        "implementation_identifier_count": len(unique_implementation_identifiers),
        "reader_temperature_rhythm": reader_temperature_rhythm,
        "article_char_count": article_char_count,
        "reader_proximity_per_1000_chars": round(reader_proximity_moments * 1000.0 / max(article_char_count, 1), 2),
        "conversational_overuse": conversational_overuse,
        "analogy_used": analogy_used,
        "analogy_necessary": "EDITORIAL_JUDGMENT" if analogy_used else ("BRIDGE_RECOMMENDED" if bridge_needed and not plain_language_bridge_present else "NOT_REQUIRED"),
        "unexplained_jargon": acronyms[:8],
        "accessibility_issues": accessibility_issues,
        "enjoyment_issues": enjoyment_issues,
        "technical_terms_per_1000_chars": round(technical_density, 1),
        "bridge_needed": bridge_needed,
        "plain_language_bridge_present": plain_language_bridge_present,
        "jargon_dense_paragraph_count": jargon_dense_paragraphs,
        "long_sentence_count": long_sentences,
        "max_explanatory_paragraph_run": max_explanatory_run,
        "generic_headings": generic_headings[:8],
        "scene_present": scene_present,
        "soft_only": True,
    }
