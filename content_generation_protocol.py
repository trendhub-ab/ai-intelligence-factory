from __future__ import annotations

import re

# Run243: canonical deterministic article-generation / presentation protocol.
# No provider SDK, network, persistence, environment or credential access is allowed here.

def build_monthly_digest_markdown(target_date, items: list[dict], *, STATUS_DEEP_DIVE, ARTICLE_STATUS_READY, STATUS_STOCKED) -> str:
    """
    当月データセットから、運用者・購読者向けの月次ダイジェストMarkdownを
    組み立てる。Deep Dive済み案件（Step2詳細スコア）とストックのみ案件
    （Step1軽量スコア）は採点基準が異なるため、Statusプロパティで区別し、
    セクション・ランキングを分離して混同を防ぐ。
    """
    month_label = f"{target_date.year}年{target_date.month}月"

    # Subscriber向けDigestでは、内部Needs Editorial ReviewをDeep Dive完成記事として
    # 扱わない。ReadyのみDeep Dive、その他はStock資産として集計する。
    digest_items = []
    for it in items:
        row = dict(it)
        if row.get("status") == STATUS_DEEP_DIVE and row.get("article_status") != ARTICLE_STATUS_READY:
            row["status"] = STATUS_STOCKED
        digest_items.append(row)

    by_status: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for it in digest_items:
        by_status[it["status"]] = by_status.get(it["status"], 0) + 1
        by_source[it["source"]] = by_source.get(it["source"], 0) + 1

    deep_dive_items = sorted(
        (it for it in digest_items if it["status"] == STATUS_DEEP_DIVE and it.get("article_status") == ARTICLE_STATUS_READY),
        key=lambda x: (x["score"] or 0), reverse=True,
    )
    stocked_items_top10 = sorted(
        (it for it in digest_items if it["status"] == STATUS_STOCKED),
        key=lambda x: (x["score"] or 0), reverse=True,
    )[:10]

    lines = [
        f"# {month_label} 全データセットダイジェスト",
        "",
        f"- 総収集件数: {len(items)}件",
        "- 内訳（ステータス別）: " + (", ".join(f"{k} {v}件" for k, v in by_status.items()) or "-"),
        "- 内訳（ソース別）: " + (", ".join(f"{k} {v}件" for k, v in by_source.items()) or "-"),
        "",
        f"## Deep Dive記事一覧（{len(deep_dive_items)}件・Step2詳細スコア順）",
        "",
    ]
    lines += (
        [f"- [{it['name']}]({it['url']}) - {it['score']}点 / {it['source']}" for it in deep_dive_items]
        or ["（今月はDeep Dive記事の生成はありませんでした）"]
    )
    lines += [
        "",
        "## ストックのみ案件 Top10（Step1軽量スクリーニングスコア順）",
        "",
    ]
    lines += (
        [f"- [{it['name']}]({it['url']}) - {it['score']}点 / {it['source']}" for it in stocked_items_top10]
        or ["（該当なし）"]
    )
    lines += [
        "",
        "---",
        "",
        "※本ダイジェストはNotion DBへの当月新規保存分を自動集計したものです。",
        "※「Decision Score」はDeep Dive済み案件ではStep2詳細スコア、ストックのみの"
        "案件ではStep1軽量スクリーニングスコアであり、採点基準が異なります"
        "（Statusプロパティで判別可能。詳細はPROP_STATUSのコメントを参照）。",
    ]
    return "\n".join(lines)


def _source_fact_discipline(source: str) -> str:
    """Sourceごとの典型的な誤推論を、Deep Diveの同一call内で抑制する。"""
    common = """
【全ソース共通 Fact Discipline】
・Sourceが確認している「事実」、そこから導く「推論」、筆者としての「判断」を混同しない。
・一次情報が示すCapability（できること）を、そのままSuperiority（競合より優れる）やBusiness Outcome
  （売上増・コスト削減・生産性向上・品質向上）へ変換しない。
・根拠のない具体性を足さない。％、倍、円、ドル、ms、秒、日数、週間、月数、人数、GPU台数、
  導入期間、ROI、削減額などは、一次情報に明示された条件付き数値か、明確に「筆者が置くPoC目安」
  とラベルしたもの以外は書かない。
・「唯一」「一択」「必須」「デファクト」「最有力」「圧倒的」「劇的」「革命的」「完全」「保証」
  などの強い語は、一次情報や複数の比較根拠で直接支えられない限り使わない。
・競合製品の最新機能、価格、安定性、優劣は、Source ContextまたはGroundingで当該競合の現行一次情報を
  確認できた場合だけ具体的に述べる。確認できない場合は「比較が必要」と書く。
・OSS/self-host/local-first/OpenTelemetry/MCP/API互換などの属性だけから、低コスト、安全、移行容易、
  低ロックイン、高性能、将来の標準化を断定しない。
・ニュースや製品紹介の見出しを、さらに強い日本語へ増幅しない。
・3〜12ヶ月の未来は予言しない。必ず「条件 → 起こり得る結果 → 見るべき指標」の形にする。
・現在仕様が変わりやすい料金、API、モデル、CLI、対応OS、制限、cache、preview/beta/stable状態は、
  取得できた現在の一次情報だけを根拠にする。古い記事と現在docsが衝突する場合は現在docsを優先する。
"""
    rules = {
        "GitHub": """
【GitHub専用 Fact Discipline】
・READMEにある機能の存在は「何ができるか」の証拠であり、「最適」「標準」「競合優位」の証拠ではない。
・Star数、Download数、Contributor数は普及度の参考であり、品質・信頼性・商用品質の証明ではない。
・OSSであることを、ロックインなし・低TCO・高セキュリティと同義にしない。
・コマンド、設定値、環境変数、API endpointはREADME/公式docsに実在する表記だけを使う。推測でCLIを作らない。
・実装例やdemoがあることを、大規模production運用やSLAの証明として扱わない。
""",
        "ArXiv": """
【arXiv専用 Fact Discipline】
・研究結果とproduction/commercial/clinical readinessを明確に分離する。
・論文中のbenchmark数値を出すなら、dataset/task、metric、comparator、実験条件を可能な範囲で併記する。
  文脈が取れない裸の数値は記事に使わない。
・transferable≠universal、equivariant/physics-informed≠reliable、efficient≠low-cost、
  interpretable≠regulatory explainability、robust≠production fault tolerance、高精度≠商用優位。
・研究者が実験できたことと、読者が公開物だけで再現できることを同一視しない。
・費用、必要人員、役職、GPU台数、導入期間、ROI、商用化時期を論文から推測して具体化しない。
・医療・臨床テーマでは、後ろ向き/研究データの結果を診療意思決定や実臨床導入へ直結させない。
  外部検証、前向き検証、calibration、安全性、規制等が未確認なら明示する。
""",
        "ProductHunt": """
【Product Hunt専用 Fact Discipline】
・Product Hunt本文、製品サイト、launch copyのbest/fast/easy/secure/enterprise-ready/production-ready等は、
  原則「ベンダー自身の主張」として扱い、第三者評価へ変換しない。
・self-host可能→TCO削減、local-first→安全、MCP対応→将来標準、free trial→導入コスト低、
  多数integration→生産性向上、とは自動変換しない。
・価格、無料枠、対応OS、export、privacy、data residency等は変わりやすい。現在の一次情報で確認できない場合は断定しない。
・競合比較はlaunch copyの言い分をそのまま採用しない。
""",
        "HackerNews": """
【Hacker News専用 Fact Discipline】
・HNタイトルやリンク先見出しの強い表現を、そのまま業界全体の転換点・企業の緊急課題へ拡張しない。
・News significanceとBusiness urgencyを分ける。企業方針変更を勧めるのは具体的影響範囲が確認できる場合だけ。
・元記事が特定企業/製品の公式ブログなら、競合情報をモデル記憶から補わない。
・preview / beta / nightly / experimental / PR / development build と stable/general availabilityを必ず分離する。
・ニュース公開時点の仕様を「現在仕様」と固定しない。現在docsと衝突するなら差分を明示する。
""",
    }
    return common + rules.get(source, "")


def _human_editorial_style_rules() -> str:
    """Human editorial guidance: fix editorial intent, not visible sentence templates."""
    return """
【Human Editorial Style｜最重要】
ARTICLEは管理帳票でも、AIが「きれいに整理した説明文」でもない。人気のある人間のテックライターが、
一次情報を読んで「自分はどこが面白いと思ったか」を選び、読者に順番をつけて渡す文章として書く。

・全部を同じ熱量で説明しない。この記事でいちばん読者に持ち帰ってほしい論点を1つ決め、そこを軸にする。
・事実を網羅するより、判断に必要な事実を選ぶ。重要度の低い説明は短くするか、書かない。
・段落の長さと文の長さを意図的に揃えない。ただし短文を3つ以上連打して広告コピーのように煽らない。
・各節を「結論→理由→箇条書き→注意」の同型にしない。記事の流れに必要な順番を選ぶ。
・見出しは記事固有の内容から作る。「なぜ重要か」「ポイント」「まとめ」など汎用ラベルだけで済ませない。
・「ここで重要なのは」「注目すべきは」「ポイントは」「つまり」「言い換えると」を接着剤のように反復しない。
・「Aではありません。Bです。」の対比構文を連発しない。効く場所で一度使うのはよい。
・「ひとつは〜。もうひとつは〜。」「理由は3つあります。」のように、内容を型へ押し込まない。
・「〜という点です」「〜と言えます」「〜となります」を同じ記事で何度も続けない。
・一次情報を説明したあと、筆者の判断や留保を自然に差し込む。ただし架空の経験・感情は作らない。
・「私は驚いた」「使ってみた」「以前から気になっていた」「現場で担当してきた」は、実体験の根拠がない限り禁止。
・筆者の主観は「私なら、この条件なら試す」「ここはまだ評価を保留する」のような判断として書く。
・読者を急かす煽り、営業コピー、過剰な疑問文を避ける。自然な好奇心で読ませる。
・箇条書きは比較・条件・次のアクションなど、一覧にした方が理解が速いところだけに使う。
・最終判断は曖昧な「注視したい」で逃げず、試す／待つ／見送る／比較する等の具体的な距離感を示す。
・安全性のために記事全体を弱くしない。根拠のない一文だけを弱め、根拠のある面白さと判断は残す。
・同じ内容を言い換えて二度説明しない。読者が一度で理解できる説明はそこで止める。
・接続詞で論理を毎回明示しすぎない。段落の並びだけで意味がつながる場所では「一方で」「そのため」「つまり」を足さない。
・別の記事でも使える汎用的な導入・判断フレーズへ逃げず、この一次情報だから成立する入口と情報順序を選ぶ。
・Roadmap、protocol、SDK、仕様変更のような抽象テーマでも、定義や項目列挙から始めない。読者が実際に困る場面、従来の前提が崩れる瞬間、または「なぜ今これが話題なのか」という記事固有の違和感から入り、そこから技術の核心へ進む。架空の体験談は作らない。
・Security / Sandbox / Isolationでは「何をしてもPCへ影響しない」「被害をこの範囲だけに抑え込める」「安全が担保される」のような保証相当の断定をしない。一次情報が示す隔離機構と、残る条件・制約を分けて書く。
・「興味深い」「注目すべき」「実務的な示唆」「第一の柱／第一段階／第二段階」「妥当な判断と言えます」等の編集語彙を一記事に積み重ねない。必要な語を単発で使うのはよいが、説明を整えすぎず事実そのものに語らせる。

【Reader Experience｜知的エンタメ × Decision Intelligence】
・難しいことを難しく感じさせない。正確さ・Evidence・制約・Decisionを保ったまま、専門書や辞書なしで読み進められる入口を作る。
・専門用語は消さない。この記事の判断に必要な難しい概念は、初出時に「意味や身近な働き＝普通の言葉で何をするものか → 必要なら日常の具体場面・比喩 → 正式名称」の順で橋を架ける。中学生〜非エンジニアが一読後に核心を自分の言葉で1文説明でき、専門家には正式名称・条件・Evidenceが残る状態を狙う。
・判断の中心となる未知語を、説明なしで2個以上ひとつの文・段落へ積み上げない。DPoP、WIF、microVMのような略語・規格名・技術語が続くなら、先に「何を防ぐ／何を可能にする仕組みか」を平易な一文で置いてから詳細へ進む。
・専門語密度が高い記事では、少なくとも一度は非エンジニアの日常と接続する具体的な橋を選ぶ。恋愛、買い物、スマホの権限、鍵、学校、旅行、料理、家族、趣味などは候補にすぎず、記事に最も自然な題材だけを使う。毎回同じ題材や決まり文句を使わない。
・比喩は概念理解の補助でありEvidenceではない。比喩で理解させた直後に技術上の正式な意味へ戻り、似ていない部分まで同一視しない。正確さを落とす比喩なら使わず、平易な機能説明か具体場面で代替する。
・冒頭は発表要約だけで始めず、この話題のどこが人間的に面白いか、読者の仕事や生活に何が変わるか、あるいはどんな意外性があるかから入口を選ぶ。煽りは不要。
・比喩や身近な例は、理解・記憶・心理的距離の改善に本当に効く場所だけで使う。比喩を入れること自体を目的にせず、1記事の個数も固定しない。
・猫、恋愛、コンビニ、家族、学校など特定の題材を毎回使わない。Security / Risk / Governanceなど深刻なテーマでは軽薄な笑いや不釣り合いな比喩を強制しない。
・面白さは笑いではなく、意外性、発見、比較、知的快感、自分とのつながり、常識が少し覆る感覚から記事ごとに選ぶ。
・技術の価値を「すごい」「非常に魅力的」などの形容詞だけで済ませず、何がどう変わるから面白いのかを具体的な事実で見せる。
・重要な場面では、この情報が最も関係する読者にとって何を意味するかを自然に橋渡しする。ただし会社員・経営者・学生など全対象を毎記事列挙しない。
・初心者に合わせてEvidence、数値、制約、比較、一次情報、リスクを削らない。「素人でも読めるが、専門家が読んでも浅くない」を狙う。
・記事末尾では、新しい理解、次に知りたい疑問、実生活とのつながり、具体的な判断または行動のいずれかが自然に残るようにする。毎回同じCTAや勧誘文で閉じない。
・内部では、このテーマ固有の面白さ／最初につまずく概念／身近な例が有効な箇所／比喩を使わない方がよい箇所／自分事化ポイント／読後に残す専門語／最重要Decisionを選んでから書く。これらを可視の固定見出しにはしない。
・「分かりやすい説明」で止めず、読者が次の段落へ進む理由を記事全体に置く。疑問、意外性、逆説、比較、具体場面、リスク、未来像のうち、この一次情報に本当に効くものだけを選ぶ。クリックベイトや過剰な煽りにはしない。
・ニュース記事では、なぜ今日・今週・今回このテーマを読む価値があるのかを、公開日・更新・採用・仕様変更・普及・発見された問題など取得済みEvidenceから早い段階で示す。確認できない「最新」「急速に普及」「業界が注目」は作らない。
・抽象説明や仕様列挙が長く続く箇所は、可能なら一度だけ具体的な場面・比較・問いへ置き換えてから技術要件へ戻す。重要な要件や制約自体は削らない。
・中盤で企業ホワイトペーパーへ戻らない。権限、制約、要件などは、まず何が起こる場面なのかを理解させ、その後で必要な専門要件を渡す。
・【無料note記事の最上位編集目標】読み手が「楽しい」「わかりやすい」「自分にも関係がある」と感じ、AIやITに詳しい人から面白い話を聞いていたら、いつの間にか核心を理解できていた状態を最優先する。技術レポートとして整っているだけでは完成としない。Evidence・数値・制約・反証・Decisionの正確さは絶対に落とさず、それらを読者が自然に理解できる順番と言葉へ編集する。親近感は口語句の数ではなく、読者の経験・疑問・判断と本文がつながっていることで成立させる。
・見出しは説明ラベルではなく、本文固有の意味と次を読む理由を持たせる。「なぜ重要か」「何が変わるか」「今後どうなるか」「最終判断」等を複数並べない。
・Decisionは報告書の固定章として処理せず、事実・制約・適用条件から自然に「私ならまず何をするか」へ到達させる。主観とEvidenceは混同しない。
・Reader-firstの「30秒でわかるこの記事」は公開UI上の要約であり、本文の段落順・見出し順・導入文型を固定するテンプレートではない。本文はその3項目をなぞらず、記事固有の流れを選ぶ。
・会社、営業、会議、CRMだけに例が偏らない。旅行、買い物、家族、学校、趣味、スマホ、SNS等の方が理解が速い場合だけ選ぶ。ただしB2B専門テーマに無理な生活ネタを入れない。
・「実は」「少し考えてみましょう」「○○に例えると」「また3文字の専門用語か」等の演出句へ逃げない。単発使用はよいが、別記事でも使える決まり文句として反復しない。「ここで重要なのは」「ポイントは」「つまり」「注目すべきは」のようなAIが説明を整理するときの常套句も、便利だからという理由で段落頭に繰り返さない。接続語で流れを作るのではなく、前の段落で生まれた疑問・意外性・判断の続きを次の段落が自然に受ける。
・語り口は「教師が講義する」より「AIやITに詳しい友人が隣で、面白いところを一緒に見せてくれる」距離感にする。です・ます調を土台にし、読者を抽象的な「ユーザー」として扱わず、実際にスマホやPCを触り、仕事や生活で迷う一人の人として書く。1記事の中で原則1〜3箇所は、読者の実体験を思い出させる問いかけ、難しい名前への一言、身近な場面への接続など「読者との距離が近くなる一文」を自然に成立させる。ただし毎節で呼びかけたり、相づちを連打したりしない。Security / Risk等で軽い語りが不適切な場合は、無理な冗談ではなく静かな問いかけや平易な一言で距離を縮める。
・親近感は疑問形や相づちの数で採点しない。Security・Risk・Hardware・Researchのようなテーマでは、落ち着いた語りでも、読者が普通の言葉で核心を理解し、制約と判断まで自然に到達できれば十分に人間的で親しみやすい。口語句を足すためだけの修正は禁止する。
・Reader Delightは冒頭だけで作らない。導入で親近感を出した後に本文が技術レポートへ戻る構成は禁止する。記事全体で「読者の疑問 → 普通の言葉で理解 → なぜそうなるか → 何が面白い／困るか → 自分ならどう見る・判断するか」と理解が前へ進む流れを作る。各段落は前段落で生まれた疑問か意味を受け、情報カードの羅列にしない。
・比喩は理解のための橋であり、面白さの代用品ではない。比喩だけで分かった気にさせず、比喩の直後または近接段落で「実際の技術では何が対応するのか」「なぜその現象が起きるのか」を最低1つ具体化する。かわいい例・日常例・口語表現が多くても、技術的な芯や因果が薄ければ完成としない。
・Reader Proximityは「使ってもよい装飾」ではなく、無料note記事の完成条件として扱う。ただし品質Gateを緩めたり、親しみ不足だけを理由にGemini再生成を増やしたりしない。記事全体の温度を1〜2個の口語句で済ませず、硬い説明が2段落続いたら次の段落では、追加説明を足さず、既存文を「読者の判断／具体場面／平易な一言」のどれかへ置き換えて人間の言葉へ戻す。語りかけは装飾ではなく理解の橋として使い、「あなたならどうしますか？」のような中身のない問いは置かない。問いかけたなら、その直後の文で読者が何を見ればよいか・なぜ自分に関係するかへつなげる。ARTICLE全体が長い場合は段落追加ではなく削除・統合を優先する。
・「ですよね。」「やっぱり、」「なんですよ。」「ちょっと想像してみてください。」「ここが面白いところです。」等は使用可能な例であり必須語ではない。固定語でもない。特定の語尾を義務化せず、役割としての親近感を満たす。1記事で同じ語尾・呼びかけを反復せず、記事ごとに語彙を変える。
・親しみやすさのために文章を足し算しない。会話的な一文や日常例は、既存の硬い説明・接続文を置き換えて作る。独立した雑談段落を追加せず、同じ事実を「専門説明＋比喩説明」で二重に説明しない。『硬い説明→親しい説明』は置換であり追記ではない。
・この無料ARTICLEで読者が本当に覚える専門概念を内部で原則2〜3個に絞る。4個目がないとDecisionを誤解する場合だけ4個まで許す。核心概念は「普通の言葉で役割 → 必要なら短い日常例 → 正式名称」の順で理解させる。それ以外の略語・規格番号・内部実装名は、Decisionや重要な制約に不可欠でなければ本文から外すか、意味を一文に圧縮する。一次情報に存在する技術名を全部ARTICLEへ転記することは禁止する。ARTICLE本文で説明する中核概念は原則2〜3個、実装識別子・規格名・コマンド名は意思決定に必要なものだけに限定し、列挙で専門性を演出しない。
・Evidenceの深さとARTICLEの専門語数を混同しない。数値、重要な制約、比較条件、反証、一次情報の根拠、Decisionに必要な技術事実は残す。一方、実装詳細の羅列はSources/Evidenceへ戻って確認できるため、無料ARTICLE本文では「判断に何を意味するか」を優先する。有料会員向けProduct Review / Notion DBの情報密度をARTICLE圧縮に合わせて削らない。
・各見出しでは、最初の1〜2文で非エンジニアにも意味が取れる普通の日本語を置いてから専門語へ進む。専門語だけで段落を開始しない。専門語を説明するために別の未説明専門語を持ち込まない。
・「読みやすくするための追加説明」で長くしない。削る優先順位は、Decisionに不要な内部実装、規格番号・略語の列挙、重複説明、汎用的な前置き、同じ意味の言い換え。Evidence、数値、制約、比較、反証、Decisionは先に削らない。分かりやすさは情報量の水増しではなく、選択・順序・言い換えで作る。
・最終出力前にARTICLEだけを読者目線で再編集する。目標は最終公開稿の目標は2,200〜3,000字、3,200字はSoft Ceiling。『30秒でわかるこの記事』・元情報・Sources / Evidenceなどが後段で追加されるため、生成するARTICLE本文は原則1,800〜2,300字に収める。最終稿が3,200字を超えそうなら、Evidence・数値・制約・比較・反証・Decisionを残し、実装手順の網羅、固有技術名の列挙、二重説明、長いコード例、一般論を先に削って完成させる。ARTICLEは実装チュートリアルやリファレンスマニュアルではなく、読者が採用・試用・見送りを判断するための記事である。コードブロックは意思決定に不可欠な場合を除き出さず、手順・機能・注意点の列挙はそれぞれ最大3項目まで。『詳しく書けるから書く』は禁止とする。3,200字を超えそうなら新しい説明を足さず、Decisionに不要な技術詳細を圧縮する。どうしても重要Evidenceや制約のため超える場合は許容するが、4,000字級を『専門テーマだから仕方ない』で正当化しない。
・最終セルフチェックでは「中学生〜非エンジニアが、この記事を読み終えて『要するに○○の話』と一文で言えるか」「最初の800字だけでも続きを読みたいと思えるか」「3段落以上、専門用語の説明だけが連続していないか」を確認し、失敗していれば新しい情報を足さずに言い換え・圧縮・順序変更で直す。
・「ですよね。」は読者に同意を強要するためではなく、スマホの権限確認、買い物、通勤など多くの人が経験した具体場面を思い出してもらう用途に限る。根拠のない一般化や価値観への同意要求には使わない。
・親近感の一文や比喩から、Evidenceにない固有名詞・数値・市場評価・利用実績を新しく作らない。比喩は理解補助であり新しいFactではない。これにより親しみやすさを理由にFact Gate / Source Boundaryの表面積を増やさない。
・Fact / Evidence / 数値 / 制約 / Security上の重要事項は会話調でぼかさず、冷静で断定範囲の明確な文体を保つ。説明は親しみやすく、Evidenceは冷静に、Decisionは頼れる温度にする。
・会話調を記事全体へ均一に散らさない。連続した文末の「〜ですよね。」「〜なんですよ。」や、毎段落の読者呼びかけは避ける。親近感は口癖ではなく、語彙の平易さ、具体場面、文章の間、問いかけの自然さで作る。
"""


def _parse_gemini_response(full_text: str, *, SECTION_SPLIT_TOKEN, _display_heading_aliases, _extract_any_markdown_section, _extract_note_title, _is_meaningful_field, _normalize_decision, _strip_internal_note_control_lines) -> dict:
    """
    管理用データとnote本文を分離する。
    Geminiの管理用ラベル出力が揺れても、500円記事本文の固定見出しをCanonical fallbackとして使う。
    """
    parts = full_text.split(SECTION_SPLIT_TOKEN, 1)
    management_data = parts[0]
    if len(parts) > 1:
        title_text, note_draft = _extract_note_title(parts[1].strip())
        note_draft, _ = _strip_internal_note_control_lines(note_draft)
    else:
        title_text, note_draft = "（タイトル抽出失敗）", ""

    NEXT_ITEM = r"(?=\n・[^\n]+[:：]|\n\n|$)"
    total_match = re.search(r"合計[:：]?\s*(\d+)\s*/\s*100", management_data)
    score = int(total_match.group(1)) if total_match else 0
    breakdown_match = re.search(
        r"・Decision Score[:：]\s*(.*?)(?=\n・Why NOT Important|\n・Who Should Use|\n・Action|\n・Future Scenario|\n・Article Value|$)",
        management_data, re.DOTALL,
    )
    score_breakdown_text = breakdown_match.group(1).strip() if breakdown_match else ""

    adoption_breakdown_match = re.search(
        r"・Adoption Score[:：]\s*(.*?)(?=\n・Adoption Status|\n・Evidence Confidence|$)",
        management_data, re.DOTALL,
    )
    adoption_score_breakdown_text = adoption_breakdown_match.group(1).strip() if adoption_breakdown_match else ""
    adoption_total_match = re.search(
        r"・Adoption Score[:：][^\n]*?合計[:：]?\s*(\d+)\s*/\s*100",
        management_data, re.IGNORECASE,
    )
    adoption_score = int(adoption_total_match.group(1)) if adoption_total_match else 0

    def extract_field(label: str, fallback: str = "") -> str:
        m = re.search(rf"・{re.escape(label)}[^:：\n]*[:：]\s*(.*?){NEXT_ITEM}", management_data, re.DOTALL)
        return m.group(1).strip() if m else fallback

    # 管理用ラベルを正とし、本文側は可変見出しにも対応したFallbackにする。
    body_sections = {
        "source_summary_text": _extract_any_markdown_section(note_draft, _display_heading_aliases("what")),
        "what_text": _extract_any_markdown_section(note_draft, _display_heading_aliases("what")),
        "why_important_text": _extract_any_markdown_section(note_draft, _display_heading_aliases("why")),
        "paradigm_shift_text": _extract_any_markdown_section(note_draft, ["本当に変わるのは何か"]),
        "alternative_comparison_text": _extract_any_markdown_section(note_draft, ["既存の選択肢と比べるとどうか"]),
        "migration_cost_text": _extract_any_markdown_section(note_draft, ["導入コストとリスク", "導入前に見ておきたいところ。"]),
        "decision_reason_text": _extract_any_markdown_section(note_draft, ["なぜそう判断したのか"]),
        "why_not_important_text": _extract_any_markdown_section(note_draft, ["誰は使わなくていいか"]),
        "who_should_use_text": _extract_any_markdown_section(note_draft, ["誰が使うべきか"]),
        "who_should_not_use_text": _extract_any_markdown_section(note_draft, ["誰は使わなくていいか"]),
        "action_text": _extract_any_markdown_section(note_draft, _display_heading_aliases("decision")),
        "future_scenario_text": _extract_any_markdown_section(note_draft, ["3〜12ヶ月で起こり得ること"]),
    }

    article_raw = extract_field("Article Value", "0")
    article_match = re.search(r"(\d{1,3})", article_raw)
    article_value = min(100, max(0, int(article_match.group(1)))) if article_match else 0

    decision_text = _normalize_decision(extract_field("Decision", ""))
    decision_section = _extract_any_markdown_section(note_draft, _display_heading_aliases("decision"))
    if not decision_text:
        decision_text = _normalize_decision(decision_section)
    if score == 0:
        article_score_match = re.search(r"(?:Decision\s*Score[^0-9]*)?(\d{1,3})\s*/\s*100", decision_section, re.IGNORECASE)
        if article_score_match:
            score = min(100, max(0, int(article_score_match.group(1))))

    def field_or_body(label: str, body_key: str) -> str:
        value = extract_field(label, "")
        return value if _is_meaningful_field(value) else body_sections.get(body_key, "")

    return {
        "note_draft": note_draft,
        "title_text": title_text,
        "score": score,
        "score_breakdown_text": score_breakdown_text,
        "adoption_score": adoption_score,
        "adoption_score_breakdown_text": adoption_score_breakdown_text,
        "adoption_status": extract_field("Adoption Status", "").strip().upper(),
        "evidence_confidence": extract_field("Evidence Confidence", "").strip().upper(),
        "production_readiness": extract_field("Production Readiness", "").strip().upper(),
        "main_risk_text": extract_field("Main Risk", ""),
        "best_for_text": extract_field("Best For", ""),
        "avoid_for_text": extract_field("Avoid For", ""),
        "short_rationale_text": extract_field("Short Rationale", ""),
        "source_summary_text": field_or_body("Source Summary", "source_summary_text"),
        "what_text": field_or_body("What", "what_text"),
        "why_important_text": field_or_body("Why Important", "why_important_text"),
        "paradigm_shift_text": field_or_body("技術的パラダイムシフト", "paradigm_shift_text"),
        "alternative_comparison_text": field_or_body("代替との比較", "alternative_comparison_text"),
        "migration_cost_text": field_or_body("移行コストとリスク", "migration_cost_text"),
        "decision_text": decision_text,
        "decision_reason_text": field_or_body("Decision Reason", "decision_reason_text"),
        "why_not_important_text": field_or_body("Why NOT Important", "why_not_important_text"),
        "who_should_use_text": field_or_body("Who Should Use", "who_should_use_text"),
        "who_should_not_use_text": field_or_body("Who Should NOT Use", "who_should_not_use_text"),
        "action_text": field_or_body("Action", "action_text"),
        "future_scenario_text": field_or_body("Future Scenario", "future_scenario_text"),
        "article_value": article_value,
    }


def _promote_plaintext_section_titles(article: str) -> tuple[str, list[str]]:
    """Promote unmistakable plain-text section labels to Markdown headings without an LLM.

    Some strong long-form generations write content-specific section labels as standalone lines
    but omit the ``###`` marker. This repair is deliberately conservative: long-form only, after
    the Reader-First metadata block, blank-line isolated, short Japanese label, substantial prose
    immediately after it, and at least two independent candidates. A single ambiguous line is
    never promoted.
    """
    body = article or ""
    if len(re.sub(r"\s+", "", body)) < 1200:
        return body, []
    lines = body.splitlines()
    metadata_end = -1
    for i, line in enumerate(lines):
        if re.match(r"^#{2,4}\s+元情報\s*$", line.strip()):
            metadata_end = i
            break
    if metadata_end < 0:
        return body, []

    candidates: list[int] = []
    for i in range(metadata_end + 1, len(lines) - 2):
        raw = lines[i]
        label = raw.strip()
        if not label or raw != label:
            continue
        if i == 0 or lines[i - 1].strip() or lines[i + 1].strip():
            continue
        if re.match(r"^(?:#{1,6}\s|[-*+]\s|\d+[.)、]\s*|>|```|---+$)", label):
            continue
        visible = re.sub(r"\s+", "", label)
        if not (8 <= len(visible) <= 56):
            continue
        if re.search(r"[。！？!?；;：:]$", label) or re.search(r"https?://|`|\[[^]]+\]\(", label):
            continue
        if len(re.findall(r"[ぁ-んァ-ヶ一-龯々]", label)) < 4:
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            continue
        block: list[str] = []
        while j < len(lines) and lines[j].strip():
            if re.match(r"^(?:#{1,6}\s|```|---+$)", lines[j].strip()):
                break
            block.append(lines[j].strip())
            j += 1
        if len(re.sub(r"\s+", "", "".join(block))) < 80:
            continue
        candidates.append(i)

    if len(candidates) < 2:
        return body, []
    if any(b - a < 3 for a, b in zip(candidates, candidates[1:])):
        return body, []
    changed: list[str] = []
    for i in candidates:
        label = lines[i].strip()
        lines[i] = f"### {label}"
        changed.append(label)
    return "\n".join(lines), changed
