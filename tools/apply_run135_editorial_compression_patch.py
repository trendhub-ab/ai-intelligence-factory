from pathlib import Path

PIPELINE = Path("pipeline.py")
text = PIPELINE.read_text(encoding="utf-8")

replacements = [
    (
        "2,200〜3,000字、3,200字はSoft Ceiling",
        "2,200〜3,000字、3,200字はSoft Ceiling。ただし3,200字を超えそうなら、Evidence・数値・制約・比較・反証・Decisionを残し、実装手順の網羅、固有技術名の列挙、二重説明、長いコード例、一般論を先に削って完成させる。『詳しく書けるから書く』は禁止"
    ),
    (
        "一次情報に存在する技術名を全部ARTICLEへ転記することは禁止する。",
        "一次情報に存在する技術名を全部ARTICLEへ転記することは禁止する。ARTICLE本文で説明する中核概念は原則2〜3個、実装識別子・規格名・コマンド名は意思決定に必要なものだけに限定し、列挙で専門性を演出しない。"
    ),
    (
        "硬い説明が2段落続いたら次の段落では、既存文を「読者の経験／具体場面／平易な一言」のどれかへ書き換えて、人間の言葉へ戻す。新しい雑談段落は足さない。",
        "硬い説明が2段落続いたら次の段落では、追加説明を足さず、既存文を「読者の判断／具体場面／平易な一言」のどれかへ置き換えて人間の言葉へ戻す。ARTICLE全体が長い場合は段落追加ではなく削除・統合を優先する。"
    ),
    (
        "修正対象外の一次情報・数値・固有名詞・見出し構造は不用意に書き換えず、局所修正に限定してください。",
        "修正対象外の一次情報・数値・固有名詞は不用意に書き換えないでください。ただしARTICLEが3,200字を超えている場合は、局所修正だけで長文を温存せず、Evidence・数値・制約・比較・反証・Decisionを保持したまま、実装列挙・二重説明・一般論・長いコード例を削除または統合して2,200〜3,000字へ再編集してください。Retryで本文を長くすることは禁止です。根拠にない保証表現、業界標準との断定、時間・金額・性能などの数値を新たに補わないでください。"
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
print(f"Run135 prompt patch applied: replacements={changed}")
