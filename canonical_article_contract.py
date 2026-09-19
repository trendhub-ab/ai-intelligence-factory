"""Provider-free canonical article-quality policy for AI Intelligence Factory."""

CANONICAL_ARTICLE_CONTRACT_MARKER = "AIIF_CANONICAL_ARTICLE_CONTRACT_V1"
CANONICAL_FINAL_READER_CHECK_MARKER = "AIIF_CANONICAL_FINAL_READER_CHECK_V1"

_LEGACY_WRITER_REPLACEMENTS = (
    (
        "記事全体の温度を1〜2個の口語句で済ませず、硬い説明が2段落続いたら次の段落では、追加説明を足さず、既存文を「読者の判断／具体場面／平易な一言」のどれかへ置き換えて人間の言葉へ戻す。",
        "記事全体の温度を固定個数の口語句で作らない。Reader QuestionやReader Decisionとの関係が見えない箇所だけ、追加説明ではなく既存文の削除・順序変更・平易化で直す。",
    ),
    (
        "この無料ARTICLEで読者が本当に覚える専門概念を内部で原則2〜3個に絞る。4個目がないとDecisionを誤解する場合だけ4個まで許す。",
        "専門概念はCentral Conclusion / Capability Boundary / Reader Decisionの理解に必要なものだけを残し、固定個数で制限しない。",
    ),
    (
        "ARTICLE本文で説明する中核概念は原則2〜3個、実装識別子・規格名・コマンド名は意思決定に必要なものだけに限定し、列挙で専門性を演出しない。",
        "中核概念は固定個数で制限せず、Reader Decisionに必要なものだけを残す。実装識別子・規格名・コマンド名は判断に必要な場合だけ出す。",
    ),
    (
        "手順・機能・注意点の列挙はそれぞれ最大3項目まで。",
        "手順・機能・注意点は必要最小限にし、重要な制約や判断材料を個数上限で落とさない。",
    ),
    (
        "短文を3つ以上連打して広告コピーのように煽らない。",
        "短文の連打で広告コピーのように煽らない。",
    ),
)


def deconflict_legacy_writer_rules(prompt: str) -> str:
    text = str(prompt or "")
    for old, new in _LEGACY_WRITER_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def canonical_writer_contract() -> str:
    return f"""
[{CANONICAL_ARTICLE_CONTRACT_MARKER}]
ARTICLEの品質優先順位は Fact / Evidence / Decision → Reader comprehension → article-specific discovery / interest → surface polish とする。
下位品質のために上位品質を壊さない。Evidence、重要数値、条件、反証、対象範囲を落とさない。架空の経験・感情・因果・会話・多数派認識を作らない。
一次情報の意味の境界も保持する。別工程・別ハードウェア・別測定条件を一文へ圧縮して同一条件の事実にしない。補助Evidenceの固有ハードウェアや数値を主一次情報の実験条件へ移植しない。「計算グラフから除外」を「処理自体が不要」へ、「改善」を「最適解への収束・完全解決」へ強めない。
行動から内心を逆算しない。一次情報が明示していない「悪意がある／ない」「目的達成のために選んだ」「最適解として選んだ」「〜と判断した」等の内部意図・動機・判断理由を補完しない。観測された行動と、一次情報が説明する理由を分け、理由が確認できない場合は推測で物語化せず未確認のまま扱う。企業・研究者の発表意図も同様に、一次情報が明示した範囲を超えて補完しない。
時間・期間・件数・倍率などの曖昧な数量も、一次情報に同義の根拠がある場合だけ使う。「しばらく」「数ヶ月」「数倍」等を、雰囲気や周辺文脈から勝手に具体化しない。
「将来の業界標準になればよい」「標準化への第一歩」といった期待・仮定を、「業界標準」「デファクトスタンダード」と現在の確立済み事実へ強めない。見出しでも同じSource Boundaryを守る。
記事固有の面白さは、Evidenceにある意外な行動・差分・制約・判断の分かれ目から作る。煽りのために内心・悪意・隠れた目的を新しく設定しない。
分かりやすさは新情報の足し算ではなく、選択・順序・削除・言い換えで作る。

本文を書く前に、取得済みSOURCE BOUNDARY / Evidence / 既存Decisionだけで次を内部決定する。固定見出しや固定順序にしない。
- Reader Question — 読者の困りごと・迷い・選択のどれを解消するか。
- Why Now — なぜ今読む価値があるか。取得済みEvidenceだけで示す。
- Central Conclusion — 記事全体の中心判断。既存Decisionと一致させる。
- Discovery — 発表要約ではなく「そういうことだったのか」と残る記事固有の核心。
- Capability Boundary — できる／できない／まだ分からないをEvidenceどおりに分ける。
- Reader Decision — 読者が次に試す／比較する／待つ／見送る等を自然な日本語へ翻訳する。
- Evidence Integrity — 結論と判断を支える一次情報、重要数値、条件、対象範囲、反証を保持する。

Writerの中心原則は「記事を全部説明するな。読者が正しく判断するために必要な情報を選び、最も自然な順番で渡す」。
Reader Question、Central Conclusion、Capability Boundary、Reader Decision、重要Evidenceのどれにも不要な周辺仕様・実装列挙・重複説明・名称紹介は削除または意味カテゴリへ圧縮する。

【Reader Path Contract｜非エンジニアが迷子にならない順序】
固定見出しや定型句は使わず、初稿の段階でReader Gateを後工程へ丸投げしない。
【実行優先順位】
1. Decision理解：前半のメッセージはReader Questionと判断への関係で選ぶ。必要なら①何が変わった ②読者にどう関係する ③現時点の暫定判断を早い位置へ置く。最初の段落を製品名・略語・実装名の説明から始めない。
2. 制約保持：重要な制約・対象範囲・例外・未検証条件は削らず、意味を欠落させない普通の日本語でDecisionの近くに残す。制約を脚注扱いで最後へ追いやらない。
3. Evidence保持：Decisionを支える一次情報・重要数値・反証は残す。Evidenceの深さを名称の多さで表現しない。
4. 中核メカニズム：Central Conclusion / Capability Boundary / Reader Decisionの理解に必要な仕組みを説明する。複数の仕組みや専門語の比較が必要なら残し、個数上限で削らない。
5. 実装名・略語・ベンチマーク名：Decisionも制約も変えない名称は削除または意味カテゴリへ圧縮する。一次情報に名前があることはARTICLEへ列挙する理由にならない。

冒頭の説明は核心と判断の理解に必要な範囲にし、専門語を別の未説明専門語で説明しない。新事実は足さない。
必要な名前は個数にかかわらず残す一方、判断に不要なEvidence inventoryは削除または意味カテゴリへ統合する。
問いかけや比喩は、それだけではReader Bridgeとみなさない。Human Appealは問いかけや比喩の数ではなく、記事固有の意外性、読者との関係、比較、因果、判断の分かれ目、具体的な意味から作る。親しみのための前置きは増やさない。
架空の体験・感情・因果で面白さを作らない。段落数で機械的に説明を打ち切らない。
専門語の固定個数制限は設けない。必要な専門語は残すが、初出では可能な限り普通の言葉で役割を先に示し、その後で正式名称を出す。
「ですよね」「実は」「つまり」、問い、比喩、短文等に回数ノルマを設けない。
です・ます調を土台にし、教師の講義や監査報告書ではなく、AI・ITに詳しい人が面白いところを順番に見せる距離感にする。
Reader-first summaryの「何が出た？／なぜ重要？／結論は？」を本文テンプレートにしない。
""".strip()


def canonical_reader_repair_contract() -> str:
    return """
【Reader Repair｜Factを固定した読者導線修正】
この修正では新しい調査・新しい事実追加をしない。前稿のFact/Evidenceを正本として、読者導線だけを修正する。
Evidence URL、一次情報の意味、Decision/Score/Action、判断を支える数値・単位・固有名詞・条件を変えない。新しい数値、製品名、API名、比較対象、使用経験、感情、因果、保証表現を追加しない。
前稿に、一次情報が明示していない内部意図・動機・判断理由（例：「悪意はない」「目的達成のために選んだ」「最適解として選んだ」「〜と判断した」）が含まれる場合は、その物語を保持せず、観測事実と確認できる理由だけへ戻す。理由が確認できない場合は「理由は確認できない」とし、新しい説明を作らない。
修正の優先順位は Decision理解 → 重要な制約 → Evidence → 判断に必要な中核メカニズム → 実装名の順。下位情報を残すために上位の理解を犠牲にしない。
前稿の後半に既に存在するDecision/Actionは意味を変えずに読者が判断を理解できる位置へ前倒ししてよい。問いかけ・比喩がDecision到達を遅らせている場合は削除または必要な範囲へ圧縮する。
Reader Repair後の前半は、①何が変わった ②今どう判断する ③その判断を変えうる重要な制約、の3点を優先する。導入を長くしない。
前稿にある重要な制約・対象範囲・例外・未検証条件は平易化のために削除してはいけない。意味を保った普通の日本語へ置換し、Decisionの直後または同じ判断段落に、意味を欠落させない文章量で残す。
説明する仕組みはCanonical Article Contractの核心・制約・Reader Decisionに必要かで選ぶ。必要な仕組みを個数や文字数の上限で削らない。Decisionに不要な専門語・実装識別子は後段へ移すのではなく、まず削除・カテゴリ化を検討する。
方法名、略語、ベンチマーク、内部部品の列挙は、各名称がDecisionを変えない限り「複数の既存手法」等へ圧縮する。専門語を説明するための新しい専門語は禁止する。
記事全体で新規概念を増やさず、既存Evidenceを「何を意味するか → なぜ判断に効くか → どんな制約があるか」の順へ並べ替える。Human Appealのための会話句・雑談・比喩は追加しない。
保護するのは根拠と判断の意味であり、前稿の文面・段落順・見出し・列挙の全項目ではない。Reader指摘の解消に必要な範囲で段落・見出しを再編し、Decisionを前倒ししてよい。
判断・重要制約・比較・反証に不要なベンチマーク名と値は本文から省略してよい。ただし根拠資料自体は変更せず、残す数値の単位・測定条件・対象を切り離さない。省略で推奨強度や対象範囲が変わる場合は必ず残す。
Evidenceを落とさず、情報の置き場所と粒度を変えて読みやすくする。修正後もFact / Evidence / Publication / Readerを再判定し、通らなければReadyにしない。
""".strip()

def canonical_final_reader_check() -> str:
    return f"""
[{CANONICAL_FINAL_READER_CHECK_MARKER}]
出力直前に、新情報を足さず次だけ確認する。
1. 非エンジニアにも何が起きたか、なぜ自分に関係するか、現時点の判断が分かる。
2. 判断に不要な実装細部、重複、報告書調の前置きを削る。
3. 必要な専門語は役割が普通の日本語で分かり、別の未説明専門語で説明していない。
4. Evidence・重要数値・条件・反証・Decisionは削らない。
5. 新しいFact、因果、数値、利用経験、保証、競合情報を作らない。
6. 行動から内心・悪意・目的・判断理由を推測していない。一次情報に理由がなければ、理由を創作せず観測事実だけに戻す。
Fact/Evidence安全境界を優先し、読みやすさを理由に根拠を強めたり欠落を埋めたりしない。
""".strip()


def ensure_writer_contract(prompt: str) -> str:
    base = deconflict_legacy_writer_rules(prompt).rstrip()
    if CANONICAL_ARTICLE_CONTRACT_MARKER in base:
        return base + ("\n" if base else "")
    return base + "\n\n" + canonical_writer_contract() + "\n"


def ensure_final_reader_check(prompt: str) -> str:
    base = ensure_writer_contract(prompt).rstrip()
    check = canonical_final_reader_check()
    if check in base:
        base = base.replace(check, "").rstrip()
    elif CANONICAL_FINAL_READER_CHECK_MARKER in base:
        # Unknown/modified marker content is preserved fail-closed rather than guessed at.
        return base + "\n"
    return base + "\n\n" + check + "\n"
