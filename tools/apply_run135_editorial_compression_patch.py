from pathlib import Path

PIPELINE = Path("pipeline.py")
text = PIPELINE.read_text(encoding="utf-8")

replacements = [
    (
        "2,200〜3,000字、3,200字はSoft Ceiling。ただし3,200字を超えそうなら、Evidence・数値・制約・比較・反証・Decisionを残し、実装手順の網羅、固有技術名の列挙、二重説明、長いコード例、一般論を先に削って完成させる。『詳しく書けるから書く』は禁止",
        "最終公開稿の目標は2,200〜3,000字、3,200字はSoft Ceiling。『30秒でわかるこの記事』・元情報・Sources / Evidenceなどが後段で追加されるため、生成するARTICLE本文は原則1,800〜2,300字に収める。最終稿が3,200字を超えそうなら、Evidence・数値・制約・比較・反証・Decisionを残し、実装手順の網羅、固有技術名の列挙、二重説明、長いコード例、一般論を先に削って完成させる。ARTICLEは実装チュートリアルやリファレンスマニュアルではなく、読者が採用・試用・見送りを判断するための記事である。コードブロックは意思決定に不可欠な場合を除き出さず、手順・機能・注意点の列挙はそれぞれ最大3項目まで。『詳しく書けるから書く』は禁止"
    ),
    (
        "修正対象外の一次情報・数値・固有名詞は不用意に書き換えないでください。ただしARTICLEが3,200字を超えている場合は、局所修正だけで長文を温存せず、Evidence・数値・制約・比較・反証・Decisionを保持したまま、実装列挙・二重説明・一般論・長いコード例を削除または統合して2,200〜3,000字へ再編集してください。Retryで本文を長くすることは禁止です。根拠にない保証表現、業界標準との断定、時間・金額・性能などの数値を新たに補わないでください。",
        "修正対象外の一次情報・数値・固有名詞は不用意に書き換えないでください。ただしARTICLE本文が2,300字を超えている場合は、局所修正だけで長文を温存せず、Evidence・数値・制約・比較・反証・Decisionを保持したまま、実装列挙・二重説明・一般論・完全なコードブロック・実装チュートリアルを削除または統合して1,800〜2,300字へ再編集してください。Retryで本文を長くすることは禁止です。根拠にない保証表現、業界標準との断定、時間・金額・性能などの数値を新たに補わないでください。"
    ),
]

changed = 0
for old, new in replacements:
    count = text.count(old)
    if count == 0:
        raise SystemExit(f"required patch anchor not found: {old}")
    text = text.replace(old, new)
    changed += count

PIPELINE.write_text(text, encoding="utf-8")
print(f"Run135 wrapper-aware prompt patch applied: replacements={changed}")
