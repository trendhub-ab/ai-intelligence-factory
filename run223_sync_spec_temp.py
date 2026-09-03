from pathlib import Path

# Patch two real Japanese/Markdown boundary cases discovered by the first regression run.
run223_path = Path('run223_technical_claim_precision.py')
run223_text = run223_path.read_text(encoding='utf-8')
replacements = {
    '_JOIN_RE = re.compile(r"\\bjoin\\b", re.I)': '_JOIN_RE = re.compile(r"join", re.I)',
    '_GROUP_BY_RE = re.compile(r"\\bgroup_by\\b", re.I)': '_GROUP_BY_RE = re.compile(r"group_by", re.I)',
    '_DATE_LINE_RE = re.compile(r"(?:公開・更新|公開日|一次情報(?:の)?公開日)\\s*[:：]\\s*(\\d{4}-\\d{2}-\\d{2})")': '_DATE_LINE_RE = re.compile(r"(?:\\*\\*)?(?:公開・更新|公開日|一次情報(?:の)?公開日)(?:\\*\\*)?\\s*[:：]\\s*(\\d{4}-\\d{2}-\\d{2})")',
}
for old, new in replacements.items():
    if old not in run223_text and new not in run223_text:
        raise SystemExit(f'Run223 patch anchor not found: {old}')
    run223_text = run223_text.replace(old, new, 1)
run223_path.write_text(run223_text, encoding='utf-8')

path = Path('AI_Intelligence_Factory_最終仕様書.md')
text = path.read_text(encoding='utf-8')

baseline = 'Article Technical Claim Precision Baseline: **Run223 — operation/API scope, performance modality, first-party date and typo precision**  \n'
if baseline not in text:
    anchor = 'Repository Organization Baseline: **Run201 — repository garbage cleanup without intended runtime behavior change**  \n'
    if anchor not in text:
        raise SystemExit('canonical spec baseline anchor not found')
    text = text.replace(anchor, baseline + anchor, 1)

runtime_line = '- `run223_technical_claim_precision.py`\n'
if runtime_line not in text:
    anchor = '- `run175_semantic_fact_precision.py`\n'
    if anchor not in text:
        raise SystemExit('canonical spec runtime anchor not found')
    text = text.replace(anchor, anchor + runtime_line, 1)

section = '''### 4.1 Technical Claim Precision — Run223

`run223_technical_claim_precision.py`は、初回note実機全文監査で露呈した技術Claimの狭い精度欠陥をzero-modelで防ぐ。

- 同名パラメータでもメソッドごとに値・意味が異なる場合、1つの設定値へ丸めない。
- 一部/特定/lossyなBreaking Changeを「全面禁止」「すべて廃止」へ一般化しない。
- x倍・%改善・レイテンシ等が期待値/ベンチマーク/測定例なら、主体・モダリティ・条件を保持し、workload/環境依存の留保を落とさない。
- 一次情報の`公開・更新`日はfirst-party本文/明示metadataだけを使い、収集日・分析日・発見元投稿日を代用しない。確認不能なら推測せず省略する。
- `によるな処理`等の既知の明白な日本語助詞崩れをPublication前に局所blockする。
- Evidence閾値、Decision Score、Gemini request budgetは変更しない。
- Run223はPublication Contract fingerprint対象であり、policy変更後の旧Ready原稿は現行policyで再構築・再stampされるまでfail-closedとする。

詳細: `docs/reference/RUN223_TECHNICAL_CLAIM_PRECISION.md`

'''
if '### 4.1 Technical Claim Precision — Run223' not in text:
    anchor = '## 5. Production runtime layer\n'
    if anchor not in text:
        raise SystemExit('canonical spec section anchor not found')
    text = text.replace(anchor, section + anchor, 1)

path.write_text(text, encoding='utf-8')
