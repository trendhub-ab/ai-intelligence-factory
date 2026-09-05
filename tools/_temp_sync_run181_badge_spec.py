from pathlib import Path

path = Path("AI_Intelligence_Factory_最終仕様書.md")
text = path.read_text(encoding="utf-8")

baseline_anchor = "Final Publication Surface Baseline: **Run249 — post-assembly public-surface revalidation / malformed title-summary fail-closed**\n"
baseline_line = "Eyecatch Impact Baseline: **Run181 current — diversified reader-purpose badges / fixed vector-style icons / approved background preserved**\n"
if baseline_line not in text:
    if text.count(baseline_anchor) != 1:
        raise SystemExit("baseline anchor mismatch")
    text = text.replace(baseline_anchor, baseline_anchor + baseline_line, 1)

section_marker = "### 4.8 Eyecatch Impact Hierarchy — Run181 current"
if section_marker not in text:
    anchor = "## 5. Production runtime layer\n"
    if text.count(anchor) != 1:
        raise SystemExit("runtime anchor mismatch")
    section = '''### 4.8 Eyecatch Impact Hierarchy — Run181 current

現行`run181_eyecatch_visual_balance.py`は、承認済みの白背景・右側network illustrationを維持したまま、note一覧での視認性を高めるcopy-led前景階層を担当する。今回のbadge改善は新しいRunを追加せず、既存Run181の責務として実装する。

- `初心者向け`を汎用fallbackにしない。明示的な初心者・入門cueがある記事だけに使用する。
- reader-purpose badgeは`初心者向け` / `比較で理解` / `安全性を確認` / `論文をやさしく` / `実務で判断` / `最新動向を理解` / `仕組みを理解` / `開発で使う` / `データを理解` / `要点を理解`から決定論で選ぶ。汎用fallbackは`要点を理解`とする。
- badge分類は表示メタデータだけであり、Fact / Evidence / Decision / score / article body / publication eligibilityを変更しない。
- 各badgeにはPillow primitiveだけで描く固定vector-style iconを割り当てる。外部SVG、画像生成API、icon生成API、追加Gemini requestは使わない。
- フォントauthorityはRun179を維持する。主タイトルはNoto Sans JP Black 900、日本語support copyはNoto Sans JP Medium 500、Latin UIはInter Bold 700を基本とし、既存system Noto/Lato fallbackを保持する。
- 主タイトルのlarge/lower hierarchy、Run182/183のorange `#F28C28` emphasis、source-bounded subheadline、category/date footerを維持する。
- 背景・右側illustration・brand・top tagsは既存`editorial_eyecatch` drawing functionを使い、`x >= 820`のapproved surfaceを変更しない。
- Run248 fallbackも同じ現行Run181 rendererへ戻るため、Semantic layout失敗時にも旧badge/旧foregroundへ逆戻りしない。
- Public releaseはhuman-only。追加provider/model callは0。

詳細: `docs/reference/RUN181_EYECATCH_IMPACT_HIERARCHY.md`

'''
    text = text.replace(anchor, section + anchor, 1)

path.write_text(text, encoding="utf-8")
