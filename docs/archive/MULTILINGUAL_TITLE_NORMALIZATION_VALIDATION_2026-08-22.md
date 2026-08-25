# Multilingual Title Normalization Validation — 2026-08-22

## Trigger
Run 98でNotion Stockに `电商出图吧` が保存され、利用者から文字化けに見えるとの指摘。実際には簡体字原題であり、文字コード破損ではなかった。

## Implemented
1. Unicode script based language detection (0 Gemini API)
2. Original title / display title separation
3. Safe Japanese category label from existing English tagline/description keywords
4. Original title + language persistence in existing Source Summary
5. Existing Notion non-Latin row repair using already-fetched page index (no extra Notion read, max 25 patches/run)
6. Technology Intelligence `technology_name` uses displayName while entity resolution keeps original identity
7. Unicode-safe title matching so non-Latin titles never collapse to empty dedup keys
8. No new required Notion property; existing schema remains compatible

## Concrete regression
Input:
- Source: ProductHunt
- Original Title: `电商出图吧`
- Description: `AI product image generator for e-commerce listings`

Expected:
- Identity name: `电商出图吧`
- Language: `zh-CN`
- Notion display: `EC商品画像生成ツール「电商出图吧」`
- Source Summary preserves `Original Title: 电商出图吧`
- No Gemini request is introduced

## Validation
- Dedicated multilingual tests: 6/6 PASS
- Full unittest: 381/381 PASS
- Synthetic Regression Full: 500/500 PASS
- Critical failures: 0
- Production write isolation: true
- Python compile: PASS
- Existing Decision Intelligence migration logic unchanged
