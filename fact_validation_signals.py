from __future__ import annotations
import json, re, unicodedata

_RUNTIME_KEYS=set()
def bind_runtime(**deps):
    globals().update(deps); _RUNTIME_KEYS.update(deps)

def _normalize_numeric_evidence_text(text: str) -> str:
    """数値表現の表記揺れだけを正規化する。意味や条件は補完しない。"""
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    # 日本語分数「40分の1」= 1/40 を英数字表現と照合可能にする。
    normalized = re.sub(r"(\d+)\s*分の\s*(\d+)", lambda m: f"{m.group(2)}/{m.group(1)}", normalized)
    normalized = normalized.replace("ミリ秒", "ms").replace("秒", "s")
    normalized = re.sub(r"\bseconds?\b|\bsec\b", "s", normalized)
    normalized = normalized.replace("トークン", "tokens").replace("リクエスト", "requests")
    normalized = re.sub(r"\btoken\b", "tokens", normalized)
    normalized = re.sub(r"\brequest\b", "requests", normalized)
    normalized = re.sub(r"(?<=\d)分(?!\s*(?:野|割|布|類|岐|析))", "minutes", normalized)
    normalized = re.sub(r"(?<=\d)日", "days", normalized)
    normalized = normalized.replace("時間", "hours").replace("週間", "weeks").replace("週", "weeks")
    normalized = re.sub(r"\bminutes?\b|\bmins?\b", "minutes", normalized)
    normalized = re.sub(r"\bdays?\b", "days", normalized)
    normalized = normalized.replace("ヶ月", "months").replace("か月", "months")
    normalized = re.sub(r"\bhours?\b", "hours", normalized)
    normalized = re.sub(r"\bweeks?\b", "weeks", normalized)
    normalized = re.sub(r"\bmonths?\b", "months", normalized)
    normalized = normalized.replace("ドル", "usd")
    normalized = re.sub(r"\busd\b", "usd", normalized)
    normalized = normalized.replace("×", "x").replace("倍", "x")
    normalized = normalized.replace("パーセント", "%")
    normalized = re.sub(r"\bpercent(?:age)?\b", "%", normalized)
    normalized = normalized.replace("〜", "-").replace("～", "-").replace("–", "-").replace("—", "-").replace("−", "-")
    normalized = re.sub(r"\bto\b", "-", normalized)
    # 10-hour / 10 hours、50%-80% / 50-80%等を同じ表記へ寄せる。
    normalized = re.sub(r"(?<=\d)-(?=(?:hours|minutes|days|weeks|months|ms|s|tokens|requests)\b)", "", normalized)
    normalized = re.sub(r"%(?=-\d)", "", normalized)
    normalized = normalized.replace("約", "")
    return re.sub(r"[\s,，]", "", normalized)

def _numeric_claim_condition_tags(text: str) -> dict[str, set[str]]:
    """数値近傍の条件を粗くタグ化する。異なる条件の同一数値を誤Groundingしないための補助。"""
    raw = text or ""
    low = raw.lower()
    metric_map = {
        "speed": r"速度|高速|throughput|tokens?/s|tok/s|speed|latency|runtime|処理時間|レイテンシ",
        "memory": r"メモリ|memory|vram|ram",
        "accuracy": r"精度|accuracy|f1|auc|precision|recall",
        "cost": r"費用|コスト|cost|price|pricing|料金",
        "energy": r"電力|消費電力|energy|power",
    }
    metrics = {name for name, pattern in metric_map.items() if re.search(pattern, low, re.I)}
    hardware = set(re.findall(
        r"(?<![A-Za-z0-9])(?:A|H|V|L|T|P)\d{2,5}(?![A-Za-z0-9])|"
        r"(?<![A-Za-z0-9])RTX\s*\d{3,5}(?![A-Za-z0-9])|"
        r"(?<![A-Za-z0-9])M[1-9](?![A-Za-z0-9])", raw, re.I
    ))
    hardware = {re.sub(r"\s+", "", item).upper() for item in hardware}
    datasets = {item.lower() for item in re.findall(r"(?<![A-Za-z0-9])dataset\s+[A-Za-z0-9_.-]+", raw, re.I)}
    return {"metrics": metrics, "hardware": hardware, "datasets": datasets}

def _numeric_condition_compatible(claim_window: str, evidence_window: str) -> bool:
    claim = _numeric_claim_condition_tags(claim_window)
    evidence = _numeric_claim_condition_tags(evidence_window)
    # 両側に明示条件がある場合だけ矛盾をFailにする。Evidence側に条件記載が無い場合は
    # 文字列の存在だけで過剰Rejectしない（別行/表見出しに条件があるケースを考慮）。
    for key in ("metrics", "hardware", "datasets"):
        if claim[key] and evidence[key] and claim[key].isdisjoint(evidence[key]):
            return False
    return True

def _is_protocol_cardinality_expression(text: str, start: int, end: int, token: str) -> bool:
    """Return True only for schematic protocol cardinality, never quantitative performance.

    Human technical prose often contrasts a simple interaction shape such as
    ``1リクエスト・1レスポンス`` or ``1リクエスト・1ツール呼び出し`` with a more
    agentic flow.  The leading ``1`` is structural notation, not a measured limit.  Keep this
    exception fail-closed: require a paired interaction term in the same sentence, a clear
    structural/contrast cue, and no quota/rate/latency/cost/capacity cue.
    """
    normalized_token = unicodedata.normalize("NFKC", token or "").lower()
    if not re.search(r"\d[\d,]*(?:\.\d+)?\s*(?:リクエスト|requests?)\b", normalized_token, re.I):
        return False
    raw = text or ""
    prev_boundaries = [raw.rfind(ch, 0, start) for ch in ("。", "！", "？", "!", "?", "\n")]
    left = max(prev_boundaries) + 1
    following = [pos for ch in ("。", "！", "？", "!", "?", "\n") if (pos := raw.find(ch, end)) >= 0]
    right = min(following) if following else len(raw)
    window = raw[left:right]

    pair = re.search(
        r"\d[\d,]*(?:\.\d+)?\s*(?:リクエスト|requests?)\s*[・:/\-–—↔⇄とand ]+\s*"
        r"(?:\d[\d,]*(?:\.\d+)?\s*)?(?:レスポンス|responses?|ツール呼び出し|tool\s+calls?)(?![A-Za-z0-9_])",
        window, re.I,
    )
    if not pair:
        return False
    structural_cue = re.compile(
        r"(?:従来|単純|単なる|標準的|対話型|構成|パターン|通信|やり取り|interaction|request[- ]?response|"
        r"から.{0,80}(?:へ|に変化|に移行|を超え))",
        re.I,
    )
    if not structural_cue.search(window):
        return False
    performance_cue = re.compile(
        r"(?:毎秒|/s|per\s+second|秒間|分間|時間あたり|上限|最大|最低|平均|レート|rate|throughput|qps|rps|"
        r"料金|価格|cost|price|quota|制限|limit|同時|concurrent|latency|レイテンシ|処理回数|回まで|件まで)",
        re.I,
    )
    return not performance_cue.search(window)

def _find_unsupported_numeric_claims(draft: str, source_context: str, evidence_metadata: dict | None = None) -> list[str]:
    """記事中のセンシティブな具体値を一次情報の値+近傍条件で照合する。"""
    evidence_raw = source_context + "\n" + json.dumps(evidence_metadata or {}, ensure_ascii=False)
    evidence = _normalize_numeric_evidence_text(evidence_raw)
    failures: list[str] = []
    scrubbed = re.sub(r"Decision\s*Score[^\n]*", "", draft or "", flags=re.IGNORECASE)
    scrubbed = re.sub(r"\bScore[^\n]*", "", scrubbed, flags=re.IGNORECASE)
    scrubbed = scrubbed.replace("3〜12ヶ月", "").replace("3-12ヶ月", "")
    # 公開日などのカレンダー日付を「導入期間○日」と誤判定しない。
    scrubbed = re.sub(r"(?:20\d{2}年)?\d{1,2}月\d{1,2}日", "", scrubbed)
    # 「2026年8月」のような公開年月は導入期間ではなくカレンダー情報。
    # 月数の性能Claimと誤判定しない（年月の事実性はSource Boundary側で扱う）。
    scrubbed = re.sub(r"20\d{2}年\d{1,2}月", "", scrubbed)

    occupied_spans: list[tuple[int, int]] = []
    for pattern in _SENSITIVE_NUMERIC_PATTERNS:
        for m in re.finditer(pattern, scrubbed, re.IGNORECASE):
            # rangeを先に照合し、その内部の末尾80%等を別claimとして二重判定しない。
            if any(m.start() >= start and m.end() <= end for start, end in occupied_spans):
                continue
            occupied_spans.append((m.start(), m.end()))
            token = m.group(0).strip()
            if _is_protocol_cardinality_expression(scrubbed, m.start(), m.end(), token):
                continue
            normalized_token = _normalize_numeric_evidence_text(token)
            if normalized_token not in evidence:
                failures.append(f"unsupported numeric claim: {token}")
                continue

            # 同じ数値が別条件にだけ存在する事故を防ぐ。数値本体を手掛かりにEvidence近傍を比較。
            numbers = re.findall(r"\d+(?:\.\d+)?", token.replace(",", ""))
            claim_window = scrubbed[max(0, m.start() - 100): min(len(scrubbed), m.end() + 120)]
            evidence_windows: list[str] = []
            if numbers:
                anchor = numbers[-1]
                # 条件照合は一次本文だけを見る。metadata JSON中の数値コピーを候補にすると、
                # ハードウェア/データセット条件が消えて誤ってcompatibleになるため。
                condition_source = source_context or ""
                for em in re.finditer(re.escape(anchor), condition_source, re.I):
                    evidence_windows.append(condition_source[max(0, em.start() - 180): min(len(condition_source), em.end() + 220)])
            if evidence_windows and not any(_numeric_condition_compatible(claim_window, window) for window in evidence_windows):
                failures.append(f"numeric condition mismatch: {token}")

    def vague_supported(token: str) -> bool:
        normalized_evidence = _normalized_evidence_text(evidence_raw)
        if _normalized_evidence_text(token) in normalized_evidence:
            return True
        # 日本語の自然な期間表現と英語一次情報の表記差だけを吸収する。
        # 「半年」は six months / half a year が明示された場合のみ許可し、
        # 単なる coming months からの勝手な具体化は許可しない。
        temporal_map = {
            "半年": r"(?:half\s+(?:a\s+)?year|six\s+months|6\s+months)",
            "数日": r"(?:several|a\s+few)\s+days",
            "数週間": r"(?:several|a\s+few)\s+weeks",
            "数週": r"(?:several|a\s+few)\s+weeks",
            "数ヶ月": r"(?:coming|next|several|a\s+few)\s+months",
            "数か月": r"(?:coming|next|several|a\s+few)\s+months",
            "数月": r"(?:several|a\s+few)\s+months",
            "数年": r"(?:several|a\s+few)\s+years",
        }
        pattern = temporal_map.get(token)
        return bool(pattern and re.search(pattern, evidence_raw, re.I))

    for pattern in _VAGUE_QUANTIFIED_PATTERNS:
        for m in re.finditer(pattern, scrubbed):
            token = m.group(0)
            if not vague_supported(token):
                failures.append(f"unsupported vague quantified claim: {token}")
    return list(dict.fromkeys(failures))[:8]

def _claim_is_negated(text: str, start: int, end: int) -> bool:
    """Judge negation in the same sentence, not an arbitrary short character window.

    Japanese business prose often places the negating predicate far after an urgency/hype token
    (e.g. 「今すぐ…リアーキテクチャすることは推奨しません」). A fixed 40-char window
    creates false positives and destroys otherwise publishable articles. Sentence scope is still
    conservative: negation in another sentence cannot legalize the claim.
    """
    body = text or ""
    left_candidates = [body.rfind(mark, 0, start) for mark in ("。", "！", "？", "\n")]
    left = max(left_candidates) + 1
    rights = [pos for mark in ("。", "！", "？", "\n") if (pos := body.find(mark, end)) >= 0]
    right = min(rights) + 1 if rights else min(len(body), end + 220)
    sentence = body[left:right]
    return bool(re.search(
        r"(?:ではない|ではありません|わけではない|わけではありません|とは言えない|とは言えません|"
        r"とは限らない|とは限りません|断定できない|確認できない|保証しない|保証するものではない|"
        r"根拠(?:が|は)ない|未確認|未検証|避ける|使わない|禁止|推奨しない|推奨しません|推奨できない)",
        sentence, re.IGNORECASE
    ))

def _find_hype_claims(draft: str, source_context: str = "", evidence_metadata: dict | None = None) -> list[str]:
    failures: list[str] = []
    text = draft or ""
    evidence = source_context or ""
    strength = (evidence_metadata or {}).get("evidence_strength", "UNKNOWN")
    for pattern, label in _HYPE_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            if _claim_is_negated(text, m.start(), m.end()):
                continue
            strong_word = re.search(r"保証|完全|必ず|安全|ゼロコスト|準拠|最速|state-of-the-art", m.group(0), re.I)
            # 強い語自体ではなく、公式の同等保証があるかで判断する。
            if strong_word and (strength in {"SPEC_GUARANTEE", "OFFICIAL_GUARANTEE"} or re.search(r"guarantee[sd]?|保証", evidence, re.I)):
                continue
            failures.append(f"{label}: {m.group(0)}")
            break
    # Run145: 実記事で確認したsandbox/securityの絶対保証を個別に閉じる。
    # 「影響を狭めやすい」のような限定表現は対象外。何をしても影響なし／被害を特定範囲に
    # 抑え込める、といった保証相当の断定だけをHard Fact defectとして扱う。
    run145_security_overclaims = (
        (r"(?:AI|エージェント|サンドボックス|sandbox)[^。！？\n]{0,90}(?:どんな|いかなる|何をしても)[^。！？\n]{0,90}(?:PC|ホスト|端末|本体)[^。！？\n]{0,50}(?:影響が及びません|影響は及びません|影響しません)", "unsupported absolute isolation"),
        (r"(?:被害|影響)(?:の)?範囲を[^。！？\n]{0,80}(?:だけ|のみ|内|範囲内)[^。！？\n]{0,50}(?:に)?(?:抑え込める|封じ込められる|限定できる)", "unsupported containment guarantee"),
    )
    for pattern, label in run145_security_overclaims:
        for m in re.finditer(pattern, text, re.I):
            if not _claim_is_negated(text, m.start(), m.end()):
                failures.append(f"{label}: {m.group(0)}")
                break

    # 「保証」単独もHigh Risk Claimとして検査する。ただし公式の保証があれば許可する。
    for m in re.finditer(r"保証(?:される|した|する|された)", text):
        if _claim_is_negated(text, m.start(), m.end()):
            continue
        supported = strength in {"SPEC_GUARANTEE", "OFFICIAL_GUARANTEE"} or bool(re.search(r"guarantee[sd]?|保証", evidence, re.I))
        if not supported:
            failures.append(f"unsupported guarantee: {m.group(0)}")
    return failures

def _evidence_has_substantive_coverage(key: str, source_context: str, evidence_metadata: dict | None = None) -> bool:
    """Confirm that FOUND metadata represents substantive evidence, not a keyword hit.

    Run 99 showed that the word "benchmark" alone can mark coverage=FOUND and then falsely reject a
    sentence saying benchmark data are unavailable. For hard contradiction checks we require concrete
    result/condition signals in the source itself.
    """
    text = source_context or ""
    meta_found = ((evidence_metadata or {}).get("coverage", {}) or {}).get(key) == "FOUND"
    if not meta_found or not text.strip():
        return False
    if key == "benchmark":
        for m in re.finditer(r"\b(?:benchmark|evaluation|experiment|test|results?)\b|ベンチマーク|評価|実験|結果", text, re.I):
            window = text[max(0, m.start() - 180): min(len(text), m.end() + 260)]
            if re.search(r"\d+(?:\.\d+)?\s*(?:%|ms|s\b|sec|x\b|倍|MB|GB|RPS|req|score|points?)|p\d{2}|latency|throughput|faster|slower|improv", window, re.I):
                return True
        return False
    if key == "runtime":
        return bool(re.search(r"\d+(?:\.\d+)?\s*(?:ms|s\b|sec(?:onds?)?|minutes?|hours?|分|秒|時間)", text, re.I))
    if key == "hardware":
        return bool(re.search(r"\b(?:GPU|CPU|H100|A100|RTX\s?\d+|TPU|GB\s+(?:RAM|VRAM))\b", text, re.I))
    if key == "code_availability":
        return bool(re.search(r"github\.com|source code|repository|repo\b|コード|リポジトリ", text, re.I))
    return meta_found

def _find_false_negative_evidence_claims(draft: str, evidence_metadata: dict, source_context: str = "") -> list[str]:
    """Stop a false 'unknown/not published' statement only when the source concretely proves otherwise."""
    text = draft or ""
    if not re.search(r"確認できない|記載されていない|不明|未公開|未評価|データがない", text):
        return []
    mapping = {
        "GPU|ハードウェア|環境": "hardware",
        "処理時間|runtime|速度|秒": "runtime",
        "コード|ソースコード": "code_availability",
        "評価|ベンチマーク": "benchmark",
    }
    failures = []
    for sentence in re.split(r"(?<=[。！？])", text):
        if not re.search(r"確認できない|記載されていない|不明|未公開|未評価|データがない", sentence):
            continue
        for cue, key in mapping.items():
            if re.search(cue, sentence, re.I) and _evidence_has_substantive_coverage(key, source_context, evidence_metadata):
                failures.append("FALSE_NEGATIVE_EVIDENCE_CLAIM: " + key)
    return list(dict.fromkeys(failures))

def _find_unsupported_competitor_claims(parsed: dict, source_context: str) -> list[str]:
    """Groundingなしの具体的競合優劣を止める。一般的な比較軸の提示は許可する。"""
    text = str(parsed.get("alternative_comparison_text", "") or "")
    if not text:
        return []
    evidence = _normalized_evidence_text(source_context)
    # 優劣・一択・明示比較を表す語がなければ問題にしない。
    if not re.search(r"(?:より(?:優|劣|強|弱)|優位|劣る|一択|軍配|最適|圧倒|ほど.{0,10}(?:ない|少ない)|比較して.{0,12}(?:優|劣))", text):
        return []
    # 比較文に現れる英数製品名候補を拾う。Source Contextにない固有名があればFail。
    names = re.findall(r"\b[A-Z][A-Za-z0-9.+_-]{2,}(?:\s+[A-Z][A-Za-z0-9.+_-]{2,})?\b", text)
    ignore = {"Decision", "Source", "API", "URL", "AI", "LLM", "MCP", "GPU", "OSS"}
    unsupported = []
    for name in dict.fromkeys(names):
        if name in ignore:
            continue
        if _normalized_evidence_text(name) not in evidence:
            unsupported.append(name)
    if unsupported:
        return ["unsupported competitor comparison: " + ", ".join(unsupported[:4])]
    return []

def _relation_family_for_predicate(predicate: str) -> tuple[str | None, tuple[str, ...] | None]:
    for family, patterns in _RELATION_FAMILIES.items():
        if any(re.search(pattern, predicate or "", re.I) for pattern in patterns):
            return family, patterns
    return None, None

def _clean_relation_entity(value: str) -> str:
    text = re.sub(r"^[\s'\"「『（(]+|[\s'\"」』）),，、]+$", "", value or "").strip()
    text = re.sub(r"(?:社|氏|チーム|財団|プロジェクト)$", "", text).strip()
    # Keep the claim conservative. A full clause/list is not an entity.
    if len(text) > 64 or re.search(r"[,，、;；]|(?:および|ならびに|または)", text):
        return ""
    return text

def _looks_like_relation_entity(value: str) -> bool:
    text = _clean_relation_entity(value)
    if len(text) < 2:
        return False
    # At least one proper-name signal: Latin token/camel case, quoted Japanese name, or honorific/company marker
    # in the original expression. Generic concepts such as 「開発体制」 are intentionally excluded.
    return bool(
        re.search(r"[A-Za-z][A-Za-z0-9.+_-]+", text)
        or re.search(r"[「『][^」』]{2,}[」』]", value or "")
        or re.search(r"(?:社|氏|チーム|財団|プロジェクト)", value or "")
    )

def _extract_explicit_relation_claim(sentence: str) -> tuple[str, str, str, tuple[str, ...]] | None:
    """Extract only grammatically explicit actor→relation→object claims.

    This deliberately prefers precision over recall. Relation Gate is a hard-fail gate, so a bare noun
    such as 「開発」「提案」「採用」 or a list of product names must not be interpreted as a factual
    actor relationship. Unsupported claims that are not explicit relations remain covered by the other
    Fact/Source-Boundary gates.
    """
    sent = (sentence or "").strip()
    if not sent:
        return None

    # Japanese active voice: Timescale社がpgvectorを提供しています。
    # Keep actor/object windows small so headings and enumerations do not become pseudo-relations.
    jp_patterns = [
        re.compile(
            r"(?P<actor>[A-Za-z0-9_.+\-/一-龥ぁ-んァ-ヶ々ー・「『』」 ]{2,48}?(?:社|氏|チーム|財団|プロジェクト)?)"
            r"(?:が|は)\s*(?P<object>[A-Za-z0-9_.+\-/一-龥ぁ-んァ-ヶ々ー・「『』」 ]{2,64}?)を\s*"
            r"(?P<predicate>提供(?:する|した|している|される|された|しています|しており)|"
            r"提唱(?:する|した|しました|している|されています|しています|しており)|提案(?:する|した|しました|している|されています|しています|しており)|"
            r"採用(?:する|した|しました|している|される|された|されています|しています|しており)|"
            r"開発(?:する|した|しました|している|される|された|されています|しています|しており))"
        ),
        # Japanese passive voice: WidgetXはAcmeによって開発された。
        re.compile(
            r"(?P<object>[A-Za-z0-9_.+\-/一-龥ぁ-んァ-ヶ々ー・「『』」 ]{2,64}?)は\s*"
            r"(?P<actor>[A-Za-z0-9_.+\-/一-龥ぁ-んァ-ヶ々ー・「『』」 ]{2,48}?(?:社|氏|チーム|財団|プロジェクト)?)"
            r"によって\s*(?P<predicate>提供された|提唱された|提案された|採用された|開発された)"
        ),
    ]
    for pattern in jp_patterns:
        m = pattern.search(sent)
        if not m:
            continue
        actor_raw, object_raw, predicate = m.group("actor"), m.group("object"), m.group("predicate")
        actor, obj = _clean_relation_entity(actor_raw), _clean_relation_entity(object_raw)
        family, family_patterns = _relation_family_for_predicate(predicate)
        if family and family_patterns and _looks_like_relation_entity(actor_raw) and _looks_like_relation_entity(object_raw):
            return family, actor, obj, family_patterns

    # English active voice. Require proper-name-looking actor AND object; generic prose is ignored.
    english_relation = r"provides?|provided|offers?|offered|ships?|shipped|maintains?|maintained|proposes?|proposed|introduced?|adopts?|adopted|uses?|used|develops?|developed|creates?|created|builds?|built"
    m = re.search(
        rf"(?P<actor>[A-Z][A-Za-z0-9_.+/-]*(?:\s+[A-Z][A-Za-z0-9_.+/-]*){{0,2}})\s+"
        rf"(?P<predicate>{english_relation})\s+"
        rf"(?P<object>[A-Z][A-Za-z0-9_.+/-]*(?:\s+[A-Z][A-Za-z0-9_.+/-]*){{0,2}})",
        sent,
    )
    if m:
        actor, obj, predicate = m.group("actor"), m.group("object"), m.group("predicate")
        family, family_patterns = _relation_family_for_predicate(predicate)
        if family and family_patterns:
            return family, actor, obj, family_patterns

    # English passive voice: WidgetX was developed by Acme.
    m = re.search(
        rf"(?P<object>[A-Z][A-Za-z0-9_.+/-]*(?:\s+[A-Z][A-Za-z0-9_.+/-]*){{0,2}})\s+"
        rf"(?:is|was|are|were|has been|have been)\s+(?P<predicate>provided|offered|maintained|proposed|introduced|adopted|used|developed|created|built)\s+by\s+"
        rf"(?P<actor>[A-Z][A-Za-z0-9_.+/-]*(?:\s+[A-Z][A-Za-z0-9_.+/-]*){{0,2}})",
        sent,
        re.I,
    )
    if m:
        actor, obj, predicate = m.group("actor"), m.group("object"), m.group("predicate")
        family, family_patterns = _relation_family_for_predicate(predicate)
        if family and family_patterns:
            return family, actor, obj, family_patterns
    return None

def _evidence_supports_relation(actor: str, obj: str, family_patterns: tuple[str, ...], source_context: str) -> bool:
    actor_norm = _normalized_named_fact(actor)
    object_norm = _normalized_named_fact(obj)
    for ev in re.split(r"(?<=[。！？.!?])\s+|\n+", source_context or ""):
        if not ev.strip() or not any(re.search(pattern, ev, re.I) for pattern in family_patterns):
            continue
        normalized_ev = _normalized_named_fact(ev)
        if actor_norm and object_norm and actor_norm in normalized_ev and object_norm in normalized_ev:
            return True
    return False

def _find_entity_relation_violations(draft: str, source_context: str) -> list[str]:
    """High-precision hard gate for unsupported actor→object factual relationships.

    Only explicit grammatical claims are eligible for hard failure. Lists, co-occurring product names,
    headings, and nouns such as 「開発体制」 are ignored. This prevents Run-99-style false positives
    while still rejecting high-confidence attribution errors such as "Timescale provides pgvector".
    """
    if not draft or not source_context:
        return []
    failures: list[str] = []
    for sent in re.split(r"(?<=[。！？.!?])\s+|\n+", draft):
        if not sent or re.search(r"一次情報(?:では|からは)確認できない|未確認|推測|可能性|仮に|たとえば|例えば", sent):
            continue
        claim = _extract_explicit_relation_claim(sent)
        if not claim:
            continue
        family, actor, obj, family_patterns = claim
        if not _evidence_supports_relation(actor, obj, family_patterns, source_context):
            failures.append(f"unsupported entity relation ({family}): {actor} -> {obj}")
    return list(dict.fromkeys(failures))[:6]
