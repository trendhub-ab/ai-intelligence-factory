"""Zero-I/O screening/profit metadata protocol helpers extracted from pipeline.py (Run241)."""

import json


def round_robin_candidates(source_groups: dict[str, list[dict]], limit: int) -> list[dict]:
    result: list[dict] = []
    queues = {source: list(items) for source, items in source_groups.items()}
    while len(result) < limit and any(queues.values()):
        for source in source_groups:
            if len(result) >= limit:
                break
            if queues[source]:
                result.append(queues[source].pop(0))
    return result


def bounded_optional_score(value, candidate_id: str, field: str, invalid: list[str]) -> int | None:
    if value is None:
        invalid.append(f"missing_{field}:{candidate_id}")
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        invalid.append(f"invalid_{field}:{candidate_id}")
        return None
    if not 0 <= parsed <= 100:
        invalid.append(f"{field}_out_of_range:{candidate_id}")
        return None
    return parsed


def shelf_life_label(score: int | float | None, *, neutral_score: int) -> str:
    try:
        value = max(0, min(100, int(score)))
    except (TypeError, ValueError):
        value = neutral_score
    if value <= 34:
        return "FLASH"
    if value <= 69:
        return "TREND"
    return "EVERGREEN"


def deep_dive_priority_score(decision_score: int | float | None, commercial_score: int | float | None,
                             *, neutral_score: int, decision_weight: float, commercial_weight: float) -> float:
    try:
        decision = max(0.0, min(100.0, float(decision_score or 0)))
    except (TypeError, ValueError):
        decision = 0.0
    try:
        commercial = max(0.0, min(100.0, float(commercial_score)))
    except (TypeError, ValueError):
        commercial = float(neutral_score)
    decision_weight = max(0.0, decision_weight)
    commercial_weight = max(0.0, commercial_weight)
    total_weight = decision_weight + commercial_weight
    if total_weight <= 0:
        return round(decision, 2)
    return round((decision * decision_weight + commercial * commercial_weight) / total_weight, 2)


def attach_profit_metadata(item: dict, commercial_score: int | None, shelf_life_score: int | None, *,
                           neutral_score: int, decision_weight: float, commercial_weight: float) -> dict:
    try:
        commercial = neutral_score if commercial_score is None else max(0, min(100, int(commercial_score)))
    except (TypeError, ValueError):
        commercial = neutral_score
    try:
        shelf = neutral_score if shelf_life_score is None else max(0, min(100, int(shelf_life_score)))
    except (TypeError, ValueError):
        shelf = neutral_score
    item["commercial_score"] = commercial
    item["shelf_life_score"] = shelf
    item["shelf_life"] = shelf_life_label(shelf, neutral_score=neutral_score)
    item["deep_dive_priority_score"] = deep_dive_priority_score(
        item.get("score"), commercial, neutral_score=neutral_score,
        decision_weight=decision_weight, commercial_weight=commercial_weight,
    )
    return item


def normalize_portfolio_topic(value, *, portfolio_topics) -> str:
    topic = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "MODELS": "MODEL", "AI_MODEL": "MODEL", "AI_MODELS": "MODEL",
        "AGENTS": "AGENT", "AUTOMATION": "AGENT",
        "DEVTOOL": "DEVTOOLS", "DEVELOPER_TOOLS": "DEVTOOLS",
        "INFRASTRUCTURE": "INFRA", "PLATFORM": "INFRA", "MLOPS": "INFRA",
        "RETRIEVAL": "DATA", "RAG": "DATA", "DATA_RETRIEVAL": "DATA",
        "SAFETY": "SECURITY", "PRIVACY": "SECURITY", "GOVERNANCE": "SECURITY",
        "VISION": "MULTIMODAL", "AUDIO": "MULTIMODAL", "ROBOTICS": "MULTIMODAL",
        "BUSINESS": "PRODUCT", "SAAS": "PRODUCT",
        "RESEARCH": "OTHER", "UNKNOWN": "OTHER", "": "OTHER",
    }
    topic = aliases.get(topic, topic)
    return topic if topic in portfolio_topics else "OTHER"


def attach_portfolio_topic(item: dict, topic=None, raw_topic=None, *, portfolio_topics) -> dict:
    normalized = normalize_portfolio_topic(topic if topic is not None else item.get("portfolio_topic"), portfolio_topics=portfolio_topics)
    item["portfolio_topic"] = normalized
    if raw_topic is not None and "raw_portfolio_topic" not in item:
        item["raw_portfolio_topic"] = normalize_portfolio_topic(raw_topic, portfolio_topics=portfolio_topics)
    return item


def build_screening_prompt(name, desc, stars, source: str = "GitHub", *, engagement_labels) -> str:
    metric_label = engagement_labels.get(source, "Stars")
    metric_note = (
        "※このソースには人気指標が存在しないため無視し、内容のみで判断せよ。\n"
        if source == "ArXiv" else ""
    )
    return f"""
以下の{source}発の一次情報について、CTO/PM向け無料noteで読者を獲得し、
会員向け意思決定DBへ蓄積する題材としての価値を0〜100点で採点せよ。
判断基準: 技術的な新規性・実務への即効性・意思決定への影響・話題性。
COMMERCIALは品質スコアとは独立して、読者需要の見込み・会員DB転換可能性・継続的な実務需要を0〜100で保守的に推定する。
SHELFは情報価値の持続性を0〜100で推定し、0-34=FLASH、35-69=TREND、70-100=EVERGREENを目安とする。
TOPICは内容の主テーマを MODEL / AGENT / DEVTOOLS / INFRA / DATA / SECURITY / MULTIMODAL / PRODUCT / OTHER のいずれか1つで返す。
Source種別ではなく内容で分類し、論文だからRESEARCHのような分類はしない。
入力にないアクセス数・検索量・売上は捏造しない。
出所が異なる案件同士でも公平に比較できるよう、指標の絶対値ではなく
内容の質・インパクトを軸に採点すること。

・出所: {source}
・名前: {name}
・{metric_label}: {stars}
{metric_note}・概要: {desc}

出力は必ず次の1行形式のみ。説明文・Markdown・前置きは一切不要。
SCORE=<0-100> COMMERCIAL=<0-100> SHELF=<0-100> TOPIC=<上記9分類> REASON=<20文字以内の一言理由>
"""


def salvage_screening_json_rows(text: str) -> list[dict]:
    rows: list[dict] = []
    src = text or ""
    depth = 0
    start = None
    in_string = False
    escaped = False
    for i, ch in enumerate(src):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    row = json.loads(src[start:i + 1])
                    if isinstance(row, dict):
                        rows.append(row)
                except json.JSONDecodeError:
                    pass
                start = None
    return rows


def parse_batch_screening_response(text: str, expected_ids: set[str], include_diagnostic: bool = False, *,
                                   tracking_eligibility_min_score: int, portfolio_topics):
    diagnostic_parts: list[str] = []
    try:
        payload = json.loads(text or "[]")
    except json.JSONDecodeError as exc:
        payload = salvage_screening_json_rows(text or "")
        diagnostic_parts.append(f"json_decode_error:{exc.msg}")
        diagnostic_parts.append(f"salvaged={len(payload)}")
    parsed: dict[str, dict] = {}
    if not isinstance(payload, list):
        diagnostic_parts.append("response_not_list")
        payload = []
    invalid: list[str] = []
    for row in payload:
        if not isinstance(row, dict):
            invalid.append("row_not_object")
            continue
        candidate_id = str(row.get("id", ""))
        if candidate_id not in expected_ids:
            invalid.append(f"unknown_id:{candidate_id}")
            continue
        if candidate_id in parsed:
            invalid.append(f"duplicate_id:{candidate_id}")
            continue
        try:
            score = int(row.get("score"))
        except (TypeError, ValueError):
            invalid.append(f"invalid_score:{candidate_id}")
            continue
        if not 0 <= score <= 100:
            invalid.append(f"score_out_of_range:{candidate_id}")
            continue
        reason = str(row.get("reason", "取得失敗")).strip()[:120] or "取得失敗"
        commercial_score = bounded_optional_score(row.get("commercial_score"), candidate_id, "commercial_score", invalid)
        shelf_life_score = bounded_optional_score(row.get("shelf_life_score"), candidate_id, "shelf_life_score", invalid)
        tracking_raw = row.get("tracking_eligible")
        if isinstance(tracking_raw, bool):
            tracking_eligible = tracking_raw
        elif isinstance(tracking_raw, str) and tracking_raw.strip().lower() in {"true", "false"}:
            tracking_eligible = tracking_raw.strip().lower() == "true"
        else:
            tracking_eligible = score >= tracking_eligibility_min_score
            invalid.append(f"missing_tracking_eligible:{candidate_id}")
        tracking_reason = str(row.get("tracking_reason", "")).strip()[:160]
        raw_topic = row.get("topic")
        normalized_topic = normalize_portfolio_topic(raw_topic, portfolio_topics=portfolio_topics)
        topic_valid = raw_topic is not None
        if raw_topic is None:
            invalid.append(f"missing_topic:{candidate_id}")
            topic_valid = False
        elif normalized_topic == "OTHER" and str(raw_topic).strip().upper() not in {"OTHER", "RESEARCH", "UNKNOWN"}:
            invalid.append(f"invalid_topic:{candidate_id}")
            topic_valid = False
        parsed[candidate_id] = {
            "score": score, "reason": reason, "commercial_score": commercial_score,
            "shelf_life_score": shelf_life_score, "tracking_eligible": tracking_eligible,
            "tracking_reason": tracking_reason, "portfolio_topic": normalized_topic, "topic_valid": topic_valid,
        }
    if invalid:
        diagnostic_parts.extend(invalid)
    missing = sorted(expected_ids - set(parsed))
    diagnostic = ";".join(diagnostic_parts)
    return (parsed, missing, diagnostic) if include_diagnostic else (parsed, missing)


def batch_screening_prompt(batch: list[dict]) -> str:
    rows = []
    for item in batch:
        repo = item["repo"]
        rows.append({"id": item["screening_id"], "source": repo.get("source", "GitHub"),
                     "name": repo.get("nameWithOwner", ""), "description": repo.get("description", ""),
                     "engagement": repo.get("stargazerCount", 0), "published_at": repo.get("publishedAt"),
                     "url": repo.get("url", "")})
    return (
        "以下の候補を、CTO/PM向け無料noteで読者を獲得し、会員向け意思決定DBへ蓄積する題材として評価せよ。"
        "scoreは従来の品質・意思決定価値スコア（0〜100）で、技術的新規性、実務インパクト、"
        "導入・意思決定への影響、緊急性、市場波及性、情報源の信頼性を総合評価する。"
        "commercial_scoreは独立した商業価値スコア（0〜100）で、読者需要の見込み、意思決定の緊急性、"
        "会員DB転換可能性、継続的な実務需要、商業隣接性をmetadataだけから保守的に推定する。"
        "実アクセス数・検索量・売上など入力にない数値を捏造してはならない。"
        "shelf_life_scoreは0〜100で情報価値の持続性を推定する。"
        "0-34=FLASH(主に1-7日)、35-69=TREND(主に1-4週)、70-100=EVERGREEN(数か月以上)を目安とする。"
        "topicはSource種別ではなく内容の主テーマを MODEL, AGENT, DEVTOOLS, INFRA, DATA, SECURITY, MULTIMODAL, PRODUCT, OTHER のいずれか1つで返す。"
        "tracking_eligibleは記事化価値とは独立し、今後の導入判断・回避判断・成熟度変化を追う価値があるTechnologyならtrueとする。"
        "単に面白い記事という理由ではtrueにせず、逆に記事scoreが低くてもAVOID判断や将来の成熟監視に価値があればtrueにできる。"
        "tracking_reasonはその理由を40字以内で返す。"
        "Sourceが異なる候補間でEngagementの絶対値を直接比較してはならない。"
        "この段階ではURL本文・README・論文全文を推測して使わない。"
        "出力は必ずJSON配列だけ。各要素は id, score, commercial_score, shelf_life_score, topic, tracking_eligible(boolean), tracking_reason（40字以内）, reason（40字以内）とする。\n"
        + json.dumps(rows, ensure_ascii=False)
    )


def calibration_prompt(batch: list[dict]) -> str:
    rows = []
    for item in batch:
        repo = item["repo"]
        rows.append({"id": item["screening_id"], "source": repo.get("source", ""),
                     "name": repo.get("nameWithOwner", ""), "description": repo.get("description", ""),
                     "raw_score": item.get("raw_score"), "raw_commercial_score": item.get("raw_commercial_score", item.get("commercial_score")),
                     "raw_shelf_life_score": item.get("raw_shelf_life_score", item.get("shelf_life_score")),
                     "raw_topic": item.get("raw_portfolio_topic", item.get("portfolio_topic", "OTHER")),
                     "tracking_eligible": item.get("tracking_eligible", False), "tracking_reason": item.get("tracking_reason", ""),
                     "engagement": repo.get("stargazerCount", 0), "published_at": repo.get("publishedAt"), "url": repo.get("url", "")})
    return (
        "以下は一次Batch審査で55点以上だった候補である。候補群を横断比較し、"
        "Notion Stock候補としての一貫した最終Decision Scoreを返せ。"
        "scoreは技術的新規性、実務インパクト、意思決定への影響、緊急性、情報源の信頼性を評価する。"
        "commercial_scoreは品質スコアと独立して、読者需要の見込み、意思決定の緊急性、会員DB転換可能性、"
        "継続的な実務需要、商業隣接性をmetadataだけから保守的に再評価する。"
        "shelf_life_scoreは情報価値の持続性を0〜100で再評価する。入力にないアクセス数や売上を捏造しない。"
        "topicは主テーマを MODEL, AGENT, DEVTOOLS, INFRA, DATA, SECURITY, MULTIMODAL, PRODUCT, OTHER のいずれか1つで再判定する。"
        "tracking_eligibleは記事価値と独立したTechnology追跡価値で再判定し、tracking_reasonを40字以内で返す。"
        "異Source間でEngagementの絶対値を直接比較してはならない。"
        "出力はJSON配列のみ。各要素は id, score, commercial_score, shelf_life_score, topic, tracking_eligible, tracking_reason, reason（40字以内）。\n"
        + json.dumps(rows, ensure_ascii=False)
    )
