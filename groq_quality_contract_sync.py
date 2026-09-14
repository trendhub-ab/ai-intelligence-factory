"""Provider-neutral quality-contract parity for the isolated Groq validation lane.

This module ports only the provider-independent behavior proven by Gemini Production
Run357-359. It deliberately does NOT copy Gemini retry authorization, routing, quotas,
or provider recovery into Groq.

Run357: prevent deterministic WATCH cleanup from manufacturing a Human Appeal failure.
Run358: remove two reproduced Reader false positives without lowering any gate.
Run359: expose only the edit semantics (delete/compress jargon causes); Groq applies them
on its already-budgeted Writer call instead of creating a Gemini-style repair retry.
"""
from __future__ import annotations

import re


SYNC_VERSION = "gemini-run357-359-provider-neutral-v1"

_MANAGEMENT_WATCH_TOKEN_RE = re.compile(r"(?<![A-Za-z])WATCH(?![A-Za-z])")
_LEGACY_SELF_CONFLICTING_WATCH_PHRASE = "今後の動きを注視する"
_PUBLIC_WATCH_DECISION_PHRASE = "新しい一次情報が出るまで待ち、出た時点で再評価する"

_READER_PRECISION_COMMON_ACRONYMS = {
    "AI", "API", "LLM", "OSS", "URL", "UI", "UX", "DB", "CPU", "GPU", "ID", "SF",
}
_READER_PRECISION_ACRONYM_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9-]{1,8})(?![A-Za-z0-9])")
_READER_PRECISION_COMPOUND_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/.+-")
_READER_PRECISION_REPEAT_FRAGMENT_LEN = 9

# Run359 behavior only.  No retry authorization is copied from Gemini Production.
GROQ_READER_EXECUTION_CONTRACT = r"""
【Gemini Run359同期｜Reader実行契約 — Provider非依存部分のみ】
- 専門語密度の問題は、説明追加ではなく削除・意味カテゴリへの圧縮で直す。Decision、重要制約、一次Evidenceの意味を変えない専門名・略語・内部部品名・方式名は削る。
- 同じ段落に専門名・略語が3個以上残る場合、それぞれの名称の違いが読者のDecisionを変える根拠を本文中で示せないものは統合または削除する。
- 専門語を別の専門語で説明しない。必要な専門概念は普通の日本語1文で意味を置き、その後は新しい技術名ではなく、読者の判断・制約・Actionのどれが変わるかを書く。
- 冒頭、why、conclusion、final/actionに相当する要約候補文は、固有実装名や略語を列挙せず、「何が変わった／なぜ関係する／何をする」が非エンジニアにも一読できる完結文にする。
- 同じ核心説明を複数箇所に残さず1箇所へ統合し、後段はその事実が判断に与える意味へ進める。
- これはFact削減、Gate緩和、追加調査、追加provider callの許可ではない。Evidence境界、Decision、重要制約は保持する。
""".strip()


def _reader_precision_prose(article: str) -> str:
    return re.sub(r"^#{1,6}\s+.*$", "", str(article or ""), flags=re.MULTILINE)


def _reader_precision_compound(prose: str, start: int, end: int) -> str:
    left = start
    right = end
    while left > 0 and prose[left - 1] in _READER_PRECISION_COMPOUND_CHARS:
        left -= 1
    while right < len(prose) and prose[right] in _READER_PRECISION_COMPOUND_CHARS:
        right += 1
    return prose[left:right]


def reader_precision_unexplained_acronyms(article: str) -> list[str]:
    prose = _reader_precision_prose(article)
    unexplained: list[str] = []
    for match in _READER_PRECISION_ACRONYM_RE.finditer(prose):
        token = match.group(1)
        if token in _READER_PRECISION_COMMON_ACRONYMS or token in unexplained:
            continue
        compound = _reader_precision_compound(prose, match.start(1), match.end(1))
        near = prose[max(0, match.start() - 90):match.end() + 120]
        direct_explained = bool(re.search(
            rf"(?:{re.escape(token)}\s*[（(].{{2,70}}[）)]|"
            rf"[（(].{{2,70}}[）)]\s*{re.escape(token)}|"
            rf".{{3,90}}[（(]{re.escape(token)}[）)]|"
            rf"{re.escape(token)}(?:とは|は、|は){{1}}.{{4,80}}"
            rf"(?:仕組み|方式|規格|標準|ツール|モデル|プロトコル|ルール))",
            near,
            re.S,
        ))
        compound_glossed = bool(
            compound
            and compound != token
            and re.search(rf"{re.escape(compound)}\s*[（(][^）)\n]{{2,70}}[）)]", near)
        )
        if not (direct_explained or compound_glossed):
            unexplained.append(token)
    return unexplained


def reader_precision_repetitive_insight(article: str) -> bool:
    prose = _reader_precision_prose(article)
    paragraphs = [x.strip() for x in re.split(r"\n\s*\n", prose) if x.strip()]
    fragment_paragraphs: dict[str, set[int]] = {}
    n = _READER_PRECISION_REPEAT_FRAGMENT_LEN
    for paragraph_index, paragraph in enumerate(paragraphs):
        compact = re.sub(
            r"https?://\S+|`[^`]+`|[A-Za-z0-9_.:/+-]+|"
            r"[\s。、！？!?「」『』（）()【】#*_>・:：;；,，.-]+",
            "",
            paragraph,
        )
        if len(compact) < n:
            continue
        seen = {compact[index:index + n] for index in range(len(compact) - n + 1)}
        for fragment in seen:
            fragment_paragraphs.setdefault(fragment, set()).add(paragraph_index)
    repeated = [fragment for fragment, owners in fragment_paragraphs.items() if len(owners) >= 3]
    return len(repeated) >= 2


def install_quality_interaction_contract(pipeline_module):
    """Exact Run357 behavior, zero API and no gate bypass."""
    p = pipeline_module
    marker = "_groq_sync_run357_quality_interaction_installed"
    if bool(getattr(p, marker, False)):
        return p
    original = getattr(p, "_apply_final_japanese_polish", None)
    if not callable(original):
        return p

    def wrapped(parsed: dict):
        incoming = dict(parsed or {})
        original_article = str(incoming.get("note_draft") or "")
        had_management_watch_leak = bool(_MANAGEMENT_WATCH_TOKEN_RE.search(original_article))
        out, changes = original(parsed)
        out = dict(out or {})
        changes = list(changes or [])
        if had_management_watch_leak:
            article = str(out.get("note_draft") or "")
            rewritten, count = re.subn(
                re.escape(_LEGACY_SELF_CONFLICTING_WATCH_PHRASE),
                _PUBLIC_WATCH_DECISION_PHRASE,
                article,
            )
            if count:
                out["note_draft"] = rewritten
                changes.append(f"note_draft:watch_quality_interaction_contract:{count}")
        return out, changes

    p._apply_final_japanese_polish = wrapped
    setattr(p, marker, True)
    setattr(p, "GROQ_SYNC_RUN357_QUALITY_INTERACTION", True)
    return p


def install_reader_signal_precision_contract(pipeline_module):
    """Exact Run358 precision behavior; only proven false positives are demoted."""
    p = pipeline_module
    marker = "_groq_sync_run358_reader_precision_installed"
    if bool(getattr(p, marker, False)):
        return p
    target_name = "_reader_experience_signals"
    original = getattr(p, target_name, None)
    if not callable(original):
        target_name = "_reader_experience_signals_impl"
        original = getattr(p, target_name, None)
    if not callable(original):
        return p

    def wrapped(article: str, *args, **kwargs):
        signals = dict(original(article, *args, **kwargs) or {})
        precise_acronyms = reader_precision_unexplained_acronyms(article)
        signals["unexplained_jargon"] = precise_acronyms[:8]
        accessibility_issues = list(signals.get("accessibility_issues") or [])
        if not precise_acronyms and "unexplained_acronyms" in accessibility_issues:
            accessibility_issues = [x for x in accessibility_issues if x != "unexplained_acronyms"]
            signals["accessibility_issues"] = accessibility_issues
            if not accessibility_issues:
                signals["accessibility"] = "GOOD"
        if bool(signals.get("repetitive_insight")) and not reader_precision_repetitive_insight(article):
            signals["repetitive_insight"] = False
            enjoyment_issues = [x for x in list(signals.get("enjoyment_issues") or []) if x != "repetitive_insight"]
            signals["enjoyment_issues"] = enjoyment_issues
            if not enjoyment_issues:
                signals["reader_enjoyment"] = "GOOD"
        signals["reader_signal_precision_contract"] = "run358"
        return signals

    setattr(p, target_name, wrapped)
    setattr(p, marker, True)
    setattr(p, "GROQ_SYNC_RUN358_READER_SIGNAL_PRECISION", True)
    return p


def install_provider_neutral_quality_contracts(pipeline_module):
    """Install only provider-neutral Run357/358 behavior for Groq evaluation."""
    install_quality_interaction_contract(pipeline_module)
    install_reader_signal_precision_contract(pipeline_module)
    setattr(pipeline_module, "GROQ_QUALITY_SYNC_VERSION", SYNC_VERSION)
    return pipeline_module
