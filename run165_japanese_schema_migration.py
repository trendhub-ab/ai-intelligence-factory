from pathlib import Path
import re


def replace_assignments(path: str, mapping: dict[str, str]) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    for var, new in mapping.items():
        pat = rf'(?m)(^|;\s*)({re.escape(var)}\s*=\s*)["\'][^"\']*["\']'
        text2, n = re.subn(pat, lambda m: m.group(1) + m.group(2) + repr(new), text, count=1)
        if n != 1:
            raise SystemExit(f"{path}: expected one assignment for {var}, found {n}")
        text = text2
    p.write_text(text, encoding="utf-8")


CONTENT = {
    "PROP_NAME":"記事名","PROP_URL":"元情報URL","PROP_SCORE":"判断スコア","PROP_STATUS":"評価状態",
    "PROP_SCORE_BREAKDOWN":"スコア内訳","PROP_WHAT":"これは何？","PROP_WHY_IMPORTANT":"なぜ重要？",
    "PROP_WHY_NOT_IMPORTANT":"なぜ重要ではない？","PROP_WHO":"対象","PROP_ACTION":"次にやること",
    "PROP_LICENSE":"ライセンス","PROP_PARADIGM_SHIFT":"パラダイム変化","PROP_ALTERNATIVE_COMPARISON":"代替比較",
    "PROP_MIGRATION_COST":"移行コスト","PROP_TITLE":"note記事タイトル","PROP_SOURCE":"情報源",
    "PROP_EYECATCH":"アイキャッチ","PROP_ENGAGEMENT":"注目度","PROP_PUBLISHED_AT":"公開日","PROP_ANALYZED_AT":"分析日",
    "PROP_CONTENT_STATUS":"コンテンツ状態","PROP_ARTICLE_STATUS":"記事状態","PROP_SUBSCRIPTION_VISIBILITY":"公開範囲",
    "PROP_SOURCE_SUMMARY":"元情報要約","PROP_SCREENING_SCORE":"選別スコア","PROP_SCREENING_REASON":"選別理由",
    "PROP_DECISION":"判断","PROP_DECISION_REASON":"判断理由","PROP_WHO_SHOULD_USE":"向いている人",
    "PROP_WHO_SHOULD_NOT_USE":"向いていない人","PROP_FUTURE_SCENARIO":"今後の見通し","PROP_ARTICLE_VALUE":"記事価値",
    "PROP_GROUNDING_STATUS":"根拠取得状態","PROP_EVIDENCE_URLS":"一次情報URL","PROP_REVIEW_STATUS":"レビュー状態",
}

TECH_HISTORY_MONTHLY = {
    "TECH_PROP_NAME":"技術・プロジェクト名","TECH_PROP_JAPANESE_DISPLAY_LABEL":"日本語表示名","TECH_PROP_PRIMARY_URL":"公式URL",
    "TECH_PROP_SOURCE":"情報源","TECH_PROP_CATEGORY":"分野（内部）","TECH_PROP_ADOPTION_SCORE":"採用スコア（内部）",
    "TECH_PROP_ADOPTION_STATUS":"採用判断（内部）","TECH_PROP_EVIDENCE_CONFIDENCE":"根拠信頼度（内部）",
    "TECH_PROP_PRODUCTION_READINESS":"実用準備度（内部）","TECH_PROP_MAIN_RISK":"主リスク（内部）",
    "TECH_PROP_BEST_FOR":"向いている用途（内部）","TECH_PROP_AVOID_FOR":"向いていない用途（内部）",
    "TECH_PROP_SHORT_RATIONALE":"判断理由（内部）","TECH_PROP_FIRST_SEEN":"初回発見日（内部）",
    "TECH_PROP_LAST_REVIEWED":"最終レビュー日（内部）","TECH_PROP_PREVIOUS_SCORE":"前回スコア",
    "TECH_PROP_SCORE_CHANGE":"スコア変化","TECH_PROP_LAST_CHANGE_AT":"最終変化日","TECH_PROP_RELATED_ARTICLE":"関連記事（内部）",
    "TECH_PROP_EVIDENCE_URLS":"一次情報URL（内部）","TECH_PROP_ENTITY_ID":"正規エンティティID",
    "TECH_PROP_ENTITY_STATUS":"エンティティ解決状態","TECH_PROP_ENTITY_ALIASES":"エンティティ別名",
    "TECH_PROP_TRACKING_STATUS":"追跡状態","TECH_PROP_TRACKING_ELIGIBILITY":"追跡対象","TECH_PROP_TRACKING_REASON":"追跡理由",
    "TECH_PROP_ASSESSMENT_STATE":"評価状態","TECH_PROP_LAST_EVIDENCE_UPDATE":"最終根拠更新日","TECH_PROP_NEXT_REVIEW":"次回レビュー日",
    "TECH_PROP_PIPELINE_STATUS":"パイプライン状態","TECH_PROP_CONTENT_STATUS":"コンテンツ状態","TECH_PROP_ARTICLE_STATUS":"記事状態",
    "TECH_PROP_SCREENING_SCORE":"選別スコア","TECH_PROP_SCREENING_REASON":"選別理由","TECH_PROP_SOURCE_SUMMARY":"元情報要約",
    "TECH_PROP_PUBLISHED_AT":"公開日","TECH_PROP_ANALYZED_AT":"分析日",
    "HISTORY_PROP_TITLE":"履歴名","HISTORY_PROP_TECHNOLOGY":"技術","HISTORY_PROP_REVIEWED_AT":"レビュー日",
    "HISTORY_PROP_ADOPTION_SCORE":"採用スコア","HISTORY_PROP_ADOPTION_STATUS":"採用判断",
    "HISTORY_PROP_PRODUCTION_READINESS":"実用準備度","HISTORY_PROP_EVIDENCE_CONFIDENCE":"根拠信頼度",
    "HISTORY_PROP_MAIN_RISK":"主なリスク","HISTORY_PROP_CHANGE_REASON":"変更理由","HISTORY_PROP_EVIDENCE_ADDED":"追加根拠",
    "HISTORY_PROP_PREVIOUS_SCORE":"前回スコア","HISTORY_PROP_SCORE_DELTA":"スコア差分","HISTORY_PROP_PREVIOUS_STATUS":"前回採用判断",
    "HISTORY_PROP_STATUS_CHANGED":"判断変更","HISTORY_PROP_SNAPSHOT_TYPE":"スナップショット種別",
    "HISTORY_PROP_ENTITY_ID":"正規エンティティID","HISTORY_PROP_EVENT_ID":"履歴イベントID",
    "MONTHLY_PROP_TITLE":"月次ダイジェスト","MONTHLY_PROP_PERIOD_ID":"対象期間ID","MONTHLY_PROP_GENERATED_AT":"生成日",
    "MONTHLY_PROP_CHANGE_COUNT":"変化件数","MONTHLY_PROP_SUMMARY":"要約",
}

EVIDENCE = {
    "P_TITLE":"根拠レコード","P_ENTITY":"技術エンティティID","P_TECH_PAGE":"技術ページID","P_URL":"根拠URL",
    "P_IMMUTABLE":"不変根拠URL","P_RESOLVED":"解決済みURL","P_VERSION":"ソース版","P_SOURCE":"ソース種別","P_ROLE":"根拠役割",
    "P_RETRIEVED":"取得日","P_VERIFIED":"最終検証日","P_HEALTH":"ソース状態","P_DOC_HASH":"文書ハッシュ",
    "P_EXTRACT_HASH":"抽出ハッシュ","P_EXTRACT":"根拠抜粋","P_ID":"根拠ID","P_ACTIVE":"有効スナップショット",
    "P_TRIGGER":"再レビュー対象","P_AUTHORITY":"権威性クラス","P_ELIGIBLE":"判断根拠利用可","P_AUTH_REASON":"権威性理由",
    "P_BINDING":"エンティティ紐付け","P_BIND_REASON":"紐付け理由",
}

if __name__ == "__main__":
    replace_assignments("pipeline.py", CONTENT)
    replace_assignments("decision_intelligence.py", TECH_HISTORY_MONTHLY)
    replace_assignments("evidence_ledger.py", EVIDENCE)
