from pathlib import Path
import re


def replace_assignments(path: str, mapping: dict[str, str]) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    for var, new in mapping.items():
        pat = rf'(?m)(^|;\s*)({re.escape(var)}\s*=\s*)["\'][^"\']*["\']'
        text2, n = re.subn(pat, lambda m: m.group(1) + m.group(2) + repr(new), text, count=1)
        if n != 1:
            raise SystemExit(f'{path}: expected one assignment for {var}, found {n}')
        text = text2
    p.write_text(text, encoding='utf-8')


SUB = {
    'SUB_PROP_NAME':'技術・プロジェクト名',
    'SUB_PROP_JAPANESE_DISPLAY_LABEL':'日本語表示名',
    'SUB_PROP_PRIMARY_URL':'公式URL',
    'SUB_PROP_SOURCE':'情報源（内部）',
    'SUB_PROP_CATEGORY':'分野（内部）',
    'SUB_PROP_ADOPTION_SCORE':'採用スコア（内部）',
    'SUB_PROP_ADOPTION_STATUS':'採用判断（内部）',
    'SUB_PROP_EVIDENCE_CONFIDENCE':'根拠信頼度（内部）',
    'SUB_PROP_PRODUCTION_READINESS':'実用準備度（内部）',
    'SUB_PROP_MAIN_RISK':'主リスク（内部）',
    'SUB_PROP_BEST_FOR':'向いている用途（内部）',
    'SUB_PROP_AVOID_FOR':'向いていない用途（内部）',
    'SUB_PROP_SHORT_RATIONALE':'判断理由（内部）',
    'SUB_PROP_FIRST_SEEN':'初回発見日（内部）',
    'SUB_PROP_LAST_REVIEWED':'最終レビュー日（内部）',
    'SUB_PROP_SCORE_CHANGE':'スコア変化（内部）',
    'SUB_PROP_RELATED_ARTICLE':'関連記事（内部）',
    'SUB_PROP_EVIDENCE_URLS':'一次情報URL（内部）',
    'SUB_PROP_ENTITY_ID':'正規エンティティID',
}
replace_assignments('decision_intelligence.py', SUB)

# Optional context fields: Technology and Subscriber raw bridges.
p = Path('context_first_enrichment.py')
text = p.read_text(encoding='utf-8')
repls = {
    'TECH_PROP_PLAIN_SUMMARY = "Plain Summary"':'TECH_PROP_PLAIN_SUMMARY = "わかりやすい要約（内部）"',
    'TECH_PROP_TOPIC_TRIGGER = "Topic Trigger"':'TECH_PROP_TOPIC_TRIGGER = "今回の話題（内部）"',
    'SUB_PROP_PLAIN_SUMMARY = "Plain Summary"':'SUB_PROP_PLAIN_SUMMARY = "わかりやすい要約（内部）"',
    'SUB_PROP_TOPIC_TRIGGER = "Topic Trigger"':'SUB_PROP_TOPIC_TRIGGER = "今回の話題（内部）"',
}
for old, new in repls.items():
    if old not in text:
        raise SystemExit(f'context_first_enrichment.py missing: {old}')
    text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# Subscriber Decision Brief direct physical-property reads.
p = Path('subscriber_decision_brief.py')
text = p.read_text(encoding='utf-8')
subscriber_names = {
    'Technology / Project Name':'技術・プロジェクト名',
    'Japanese Display Label':'日本語表示名',
    'Category':'分野（内部）',
    'Adoption Score':'採用スコア（内部）',
    'Adoption Status':'採用判断（内部）',
    'Production Readiness':'実用準備度（内部）',
    'Evidence Confidence':'根拠信頼度（内部）',
    'Plain Summary':'わかりやすい要約（内部）',
    'Topic Trigger':'今回の話題（内部）',
    'Short Rationale':'判断理由（内部）',
    'Best For':'向いている用途（内部）',
    'Avoid For':'向いていない用途（内部）',
    'Main Risk':'主リスク（内部）',
    'Primary URL':'公式URL',
    'Primary Evidence URLs':'一次情報URL（内部）',
    'Last Reviewed':'最終レビュー日（内部）',
}
for old, new in subscriber_names.items():
    text = text.replace(f'p.get("{old}")', f'p.get("{new}")')
p.write_text(text, encoding='utf-8')

# Member presentation sync direct source reads.
p = Path('member_presentation_sync.py')
text = p.read_text(encoding='utf-8')
member_names = {
    'Canonical Entity ID':'正規エンティティID',
    'Technology / Project Name':'技術・プロジェクト名',
    'Japanese Display Label':'日本語表示名',
    'Adoption Status':'採用判断（内部）',
    'Adoption Score':'採用スコア（内部）',
    'Evidence Confidence':'根拠信頼度（内部）',
    'Production Readiness':'実用準備度（内部）',
    'Category':'分野（内部）',
    'Short Rationale':'判断理由（内部）',
    'Topic Trigger':'今回の話題（内部）',
    'Main Risk':'主リスク（内部）',
    'Plain Summary':'わかりやすい要約（内部）',
    'Best For':'向いている用途（内部）',
    'Avoid For':'向いていない用途（内部）',
    'Last Reviewed':'最終レビュー日（内部）',
    'First Seen':'初回発見日（内部）',
    'Primary Evidence URLs':'一次情報URL（内部）',
    'Related Article':'関連記事（内部）',
    'Primary URL':'公式URL',
    'Source':'情報源（内部）',
}
for old, new in member_names.items():
    text = text.replace(f'p.get("{old}")', f'p.get("{new}")')
p.write_text(text, encoding='utf-8')
