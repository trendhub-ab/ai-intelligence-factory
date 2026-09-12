"""Deterministic transport compiler for Groq article-generation prompts.

The canonical Production prompt remains the source of truth. Groq currently rejects the
full ~50KB article request with HTTP 413, so only verbose *editorial meta-guidance*
sections are replaced by compact, semantically equivalent contracts before transport.
Evidence, source boundary, fact discipline, structured evidence, freshness, target data,
management-data schema and candidate/source context are never modified here.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


class PromptCompileError(RuntimeError):
    pass


MAX_COMPILED_PROMPT_BYTES = 28000


@dataclass(frozen=True)
class CompileResult:
    prompt: str
    source_sha256: str
    compiled_sha256: str
    source_bytes: int
    compiled_bytes: int
    replaced_sections: tuple[str, ...]


# These sections are editorial guidance accumulated over many quality runs. The compact
# versions keep the same prohibitions and reader/editorial intent, but remove examples,
# repetition and explanatory prose. Factual/evidence contracts are intentionally absent
# from this map and therefore pass through byte-for-byte.
COMPACT_SECTIONS = {
    "Human Editorial Style｜最重要": """【Human Editorial Style｜最重要】
ARTICLEは管理帳票やAI調の整った説明文ではなく、人間のテック編集者が一次情報から最重要論点を選び、自然な順序で読ませる文章にする。
・重要論点を1つ軸にし、判断に不要な網羅説明は削る。段落・文・節を同じ型や長さへ揃えない。
・汎用見出し、定型導入、接着詞、対比構文、列挙テンプレート、同義反復を連発しない。記事固有の流れと語彙を選ぶ。
・架空の体験・感情・利用経験を作らない。筆者の主観はEvidenceと分離し、「私なら試す／待つ／見送る」等の判断として示す。
・営業コピー、煽り、過剰な疑問文を避ける。箇条書きは比較・条件・Actionなど一覧が速い箇所だけに使う。
・安全性のため記事全体を弱めず、根拠のない文だけを弱める。Security/Sandbox/Isolationは安全保証へ拡張せず、機構と残る制約を分ける。
・最終判断は「注視」で逃げず、試す／待つ／見送る／比較する等の具体的距離感を示す。
""",
    "Reader Experience｜知的エンタメ × Decision Intelligence": """【Reader Experience｜知的エンタメ × Decision Intelligence】
最上位目標は、Evidence・数値・制約・反証・Decisionを保ったまま、中学生〜非エンジニアでも楽しく一読でき、専門家にも判断材料が残る記事にすること。
・冒頭2〜4段落は発表要約や定義列挙にしない。取得済み一次情報にある、その記事固有の「意外な事実・数値・前提が変わる点」から1つだけ選び、最初の1100字以内で「なぜ読者に関係するか」まで平易につなぐ。Evidenceにない利用場面や効果は作らない。
・冒頭の読者ブリッジには、文脈に合う場合だけ「簡単に言えば」「たとえば」「仕事で言えば」「使う側から見ると」等に相当する自然な平易化を最低1回入れる。疑問形の連発やクリックベイトにはしない。
・英字略語・専門語・固有の技術概念は必要なものだけ残し、初出で必ず「普通の言葉で機能→正式名称」の順に説明する。略語だけを裸で置かず、「X（〜する仕組み）」または「Xとは〜する仕組み」のように日本語の意味を同じ文か直後に添える。
・1文に新しい専門概念を詰め込まない。専門語が多い段落の直後は、読者が意味を回収できる平易な一文・具体的比較・短い見出しのいずれかを置く。90字以上の説明段落を3つ以上連続させない。
・比喩は理解補助でEvidenceではない。必要な場合でも記事全体で少数にし、技術上の正式な意味へ戻す。正確さを落とす比喩や不釣り合いな軽さ、毎記事同じ比喩は使わない。
・面白さは笑いではなく、一次情報に根拠のある発見・比較・知的快感・自分とのつながり・常識が覆る感覚から作る。「すごい」等の形容詞だけで価値を説明しない。
・読者を抽象的なユーザーとして扱わず、AI/ITに詳しい友人が隣で面白い所を見せる距離感のです・ます調にする。ただし架空の読者体験や導入効果を事実のように書かない。
・初心者向けにEvidence、数値、制約、比較、一次情報、リスクを削らない。ニュース性は取得済みEvidenceにある公開/更新/採用/仕様変更等で示し、「最新」「急速に普及」等を捏造しない。
・本文は30秒要約をなぞる固定テンプレートにしない。各見出しは記事固有の意味と次を読む理由を持たせる。Decisionは事実・制約・適用条件から自然に導き、Evidenceと主観を混ぜない。
・読後には「何が変わったか」「何はまだ分からないか」「自分なら次に何を確かめるか」が残るようにする。同じCTAや勧誘文で閉じない。
""",
    "出典時点と理論→実務の境界 / Run176": """【出典時点と理論→実務の境界 / Run176】
・原資料の公開/更新時点と現在を混同しない。確認できない現在仕様は「原資料時点」と限定し、後続一次情報がある場合は新しい状態を優先する。
・研究・理論・デモ・preview・beta・開発版で示された能力を、stable/GA、production readiness、商用優位、ROI、低コスト、安全性へ自動変換しない。
・Capability→Business Outcomeの間に必要な検証条件を明示する。未検証の効果、費用、期間、人員、性能、将来予測を具体化しない。
・ActionはEvidenceの強さに合わせる。根拠不足なら限定PoC、比較テスト、評価項目追加、ログ可視化、見送り等に留め、全面導入を勧めない。
・断定・不在Claim・数値・主体帰属は、取得済みEvidenceのCoverage/条件/時点を越えない。
""",
    "実行優先順位": """【実行優先順位】
1. 指定フォーマット、SECTION_SPLIT_TOKEN、タイトル、ARTICLE本文の最終判断までを切らずに完走する。
2. MANAGEMENT DATAは指定項目だけを短く正確に返し、本文の品質を犠牲にして管理項目を増やさない。
3. Source Boundary、Structured Evidence、required_qualifiers、数値条件、時点、制約を最優先で守る。
4. 一般論・競合・背景・将来・費用を推測で埋めない。Evidenceにない具体性を作らない。
5. 読みやすさはEvidenceを削るのでなく、順序・言葉・具体場面・見出しで作る。
""",
    "ARTICLEの追加ルール": """【ARTICLEの追加ルール】
・本文は一次情報の核心→意味→制約/反証→読者が取れる具体Action→最終判断が自然につながる構成にし、固定章テンプレートへ押し込まない。
・事実、推論、筆者判断を読者が区別できるようにする。Evidenceにない比較、価格、導入効果、現在仕様、固有名詞を補完しない。
・数値は条件・対象・比較軸を落とさない。強い保証語は同等の一次根拠がある場合だけ使う。
・タイトル/見出し/導入は記事固有にし、誇張やAI常套句を避ける。本文はです・ます調を基本に自然なリズムで書く。
・最終判断はDecisionと矛盾させず、誰が何を試す/待つ/見送るかを具体化する。
""",
    "Production Yield Consistency Contract｜最終セルフチェック": """【Production Yield Consistency Contract｜最終セルフチェック】
出力前に自己検査する。
・Source Boundary違反、Evidence外の現在事実/数値/競合/価格/保証、required_qualifiers欠落がない。
・Decision Score、Decision、本文の温度、Action、最終判断が相互矛盾していない。
・記事が途中で切れておらず、指定フォーマットと管理項目を守っている。
・冒頭1100字以内に非エンジニアが意味をつかめる読者ブリッジがあり、専門語・略語の初出には平易な日本語説明がある。
・長い説明段落を連続させず、一次情報固有の発見→意味→制約→判断のリズムがある。
・AI定型句・同義反復・不自然な箇条書き・架空体験がない。
・Evidenceが弱い箇所だけを弱め、根拠のある面白さ・具体性・判断まで消していない。
""",
}

# Evidence/safety/output contracts that must survive compilation verbatim somewhere in
# the canonical prompt. Their absence indicates upstream drift and blocks compilation.
REQUIRED_CANONICAL_MARKERS = (
    "【SOURCE BOUNDARY — 最重要】",
    "【Structured Evidence / Required Qualifiers — 最優先】",
    "【Freshness Resolution】",
    "【全ソース共通 Fact Discipline】",
    "=== MANAGEMENT DATA ===",
    "Decision Score",
    "required_qualifiers",
    "Source Native Context",
)

REQUIRED_COMPILED_MARKERS = REQUIRED_CANONICAL_MARKERS + (
    "【Human Editorial Style｜最重要】",
    "【Reader Experience｜知的エンタメ × Decision Intelligence】",
    "中学生〜非エンジニア",
    "最初の1100字以内",
    "初出で必ず",
    "90字以上の説明段落を3つ以上連続させない",
    "架空",
    "最終判断",
    "Evidence",
)


def _replace_section(prompt: str, heading: str, replacement: str) -> str:
    pattern = re.compile(
        r"(?ms)^【" + re.escape(heading) + r"】\s*\n.*?(?=^【[^\n】]+】\s*$|\Z)"
    )
    matches = list(pattern.finditer(prompt))
    if len(matches) != 1:
        raise PromptCompileError(f"section_count:{heading}:{len(matches)}")
    return prompt[:matches[0].start()] + replacement.rstrip() + "\n\n" + prompt[matches[0].end():]


def compile_article_prompt(canonical_prompt: str) -> CompileResult:
    if not isinstance(canonical_prompt, str) or not canonical_prompt.strip():
        raise PromptCompileError("canonical_prompt_missing")
    for marker in REQUIRED_CANONICAL_MARKERS:
        if marker not in canonical_prompt:
            raise PromptCompileError("canonical_marker_missing:" + marker)

    compiled = canonical_prompt
    replaced = []
    for heading, replacement in COMPACT_SECTIONS.items():
        compiled = _replace_section(compiled, heading, replacement)
        replaced.append(heading)

    for marker in REQUIRED_COMPILED_MARKERS:
        if marker not in compiled:
            raise PromptCompileError("compiled_marker_missing:" + marker)

    source_bytes = len(canonical_prompt.encode("utf-8"))
    compiled_bytes = len(compiled.encode("utf-8"))
    if compiled_bytes >= source_bytes:
        raise PromptCompileError("compiler_did_not_reduce_prompt")
    if compiled_bytes > MAX_COMPILED_PROMPT_BYTES:
        raise PromptCompileError(f"compiled_prompt_too_large:{compiled_bytes}")

    return CompileResult(
        prompt=compiled,
        source_sha256=hashlib.sha256(canonical_prompt.encode("utf-8")).hexdigest(),
        compiled_sha256=hashlib.sha256(compiled.encode("utf-8")).hexdigest(),
        source_bytes=source_bytes,
        compiled_bytes=compiled_bytes,
        replaced_sections=tuple(replaced),
    )
