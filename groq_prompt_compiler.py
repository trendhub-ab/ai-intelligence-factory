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


# Groq transport-only compact contracts. Canonical Production remains untouched.
# Evidence/safety/output sections are deliberately not replaceable here.
COMPACT_SECTIONS = {
    "Human Editorial Style｜最重要": """【Human Editorial Style｜最重要】
ARTICLEは一次情報から重要論点を選ぶ人間のテック編集記事にする。管理帳票・AI定型文・同義反復・均一な段落を避ける。
・架空体験やEvidence外の効果を作らない。主観は「私なら試す／待つ／見送る」等の判断として事実と分ける。
・箇条書きは比較や条件など一覧が明らかに速い場合だけ。本文の説明、安全策、制約、Actionを箇条書きで連打しない。
・安全策や技術名は一次情報にある名称・説明だけを書く。名称から動作、適用範囲、リアルタイム性、ログ、保証を推測しない。
・最終判断は「注視」で逃げず、Evidenceに許された範囲で具体的距離感を示す。
""",
    "Reader Experience｜知的エンタメ × Decision Intelligence": """【Reader Experience｜知的エンタメ × Decision Intelligence】
Evidence・数値・制約・反証・Decisionを保ち、中学生〜非エンジニアにも一読でき、専門家にも判断材料が残る記事にする。
・冒頭2〜4段落は発表要約や定義列挙ではなく、一次情報で最も意外な事実・数値を1つ選ぶ。「簡単に言えば」「たとえば」「使う側から見ると」等の自然な読者ブリッジを最初の1100字以内に最低1回置き、なぜ関係するかまで平易につなぐ。
・専門語・略語は必要最小限にし、初出で必ず普通の日本語の意味を添える。名称にない仕組みを説明として補完しない。
・1文に新概念を詰め込まず、専門語が続いたら平易な回収文を置く。90字以上の説明段落を3つ以上連続させない。
・面白さは一次情報固有の発見・比較・意外性から作る。比喩は少数、Evidenceではないと分かる形で使う。
・固定見出しや30秒要約の焼き直しを避ける。記事固有の見出しと流れにし、説明の大半をリスト化しない。
・読後に「何が変わったか／何は未確認か／次に何を確かめるか」が残るようにする。
""",
    "出典時点と理論→実務の境界 / Run176": """【出典時点と理論→実務の境界 / Run176】
・公開/更新時点と現在を混同せず、確認できない現在仕様は原資料時点に限定する。
・研究、評価、preview、beta、特定アクセス条件の結果をstable/GA、本番性能、商用優位、ROI、安全保証、一般提供へ拡張しない。
・数値は必ず測定対象・条件・母集団・ベンチマーク名など一次情報にある限定と一体で書く。「100%」等の数値だけを一般性能へ広げない。
・ある評価条件に付く限定を、別の安全策・提供条件・ユーザー範囲へ横滑りさせない。
・Actionは入手可能性までEvidenceがある場合だけ実行を勧める。アクセス可否が未確認なら「条件を確認する」までに留める。
・未検証の効果、費用、期間、人員、性能、将来予測を具体化しない。
""",
    "実行優先順位": """【実行優先順位】
1. 指定フォーマット、SECTION_SPLIT_TOKEN、ARTICLE最終判断まで完走する。
2. Source Boundary、Structured Evidence、required_qualifiers、数値条件、時点、制約を最優先する。
3. Evidenceにない固有名詞、英訳名、機能説明、比較、価格、導入効果、提供条件を足さない。
4. 読みやすさはEvidenceを削らず、順序・平易語・見出し・短い回収文で作る。
""",
    "ARTICLEの追加ルール": """【ARTICLEの追加ルール】
・一次情報の核心→読者への意味→制約/反証→確認すべきAction→最終判断が自然につながる文章にする。
・数値は条件と分離しない。安全策・製品名・機能名はSource Native Contextの表記を優先し、Evidenceにない英訳・別名を作らない。
・名前しかEvidenceにない安全策は名前だけに留め、その仕組み、検知方法、適用対象、常時/リアルタイム動作、ログ収集などを推測しない。
・評価結果が特定access/configuration条件なら、その限定は評価結果にだけ掛ける。安全策の適用範囲や提供可否まで同じ条件だと推定しない。
・見出しは記事固有にし、「何が起きた／なぜ重要／仕組み／リスク／アクション」の固定テンプレートをそのまま並べない。
・Decisionと最終判断を一致させ、未確認のアクセス取得やPoC実施を既成事実にしない。
""",
    "Production Yield Consistency Contract｜最終セルフチェック": """【Production Yield Consistency Contract｜最終セルフチェック】
出力前に確認する。
・Evidence外の事実、英訳名、数値条件落ち、required_qualifiers欠落、評価条件の横滑りがない。
・安全策名から機能を推測していない。未確認アクセスでPoCを勧めていない。
・冒頭1100字以内に非エンジニア向け読者ブリッジがあり、専門語・略語の初出で意味を回収できる。
・90字以上の説明段落を3つ以上連続させず、説明の大半を箇条書きにしていない。
・Decision Score、Decision、Action、本文、最終判断が矛盾せず、記事が途中で切れていない。
""",
}


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
    "数値は必ず測定対象・条件",
    "評価条件の横滑り",
    "名称から動作",
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
