"""Run224 — zero-model deterministic rescue for scoped performance multipliers.

Run223 intentionally blocks performance multipliers when a source-side benchmark/expectation
loses its attribution/condition scope or the article omits real-world variability.  Run224 closes
the corresponding rescue gap without spending another Gemini request.

Safety contract:
- activates only when the existing gate already diagnosed `performance_multiplier_scope_lost`;
- never changes/removes the multiplier, any other number, Evidence, Decision, score or URL;
- adds only a conservative scope qualifier immediately beside the diagnosed performance claim;
- never edits fenced code or Markdown headings;
- is idempotent and zero-model.
"""
from __future__ import annotations

import re

_FAILURE_PREFIX = "performance_multiplier_scope_lost:"
_MULTIPLIER_RE = re.compile(r"(?<![0-9.])(\d+(?:\.\d+)?)\s*(?:倍|x\s+(?:faster|speedup))", re.I)
_SPEED_RE = re.compile(r"高速|速度|性能|performance|faster|speedup", re.I)
_SCOPE_RE = re.compile(r"一次情報|ベンチマーク|測定|試算|期待|条件|ワークロード|source|benchmark|measured|estimated|expect|condition|workload", re.I)
_VARIABILITY_RE = re.compile(
    r"(?:実際|実運用|現実).{0,40}(?:変わ|異な|依存)|"
    r"(?:処理内容|実行環境|環境|条件|ワークロード).{0,40}(?:変わ|異な|依存)|"
    r"(?:vary|depend).{0,40}(?:workload|condition|environment)|"
    r"(?:workload|condition|environment).{0,40}(?:vary|depend)",
    re.I,
)
_QUALIFIER = "この倍率は一次情報で示された特定条件下の目安であり、実際の改善幅は処理内容・条件・実行環境によって変わります。"
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?])")


def _has_multiplier_scope_failure(reason_rows: list[dict] | None) -> bool:
    for row in reason_rows or []:
        if _FAILURE_PREFIX in str(row):
            return True
    return False


def _needs_scope_qualifier(sentence: str) -> bool:
    text = str(sentence or "")
    if not _MULTIPLIER_RE.search(text) or not _SPEED_RE.search(text):
        return False
    return not (_SCOPE_RE.search(text) and _VARIABILITY_RE.search(text))


def add_multiplier_scope_qualifier(markdown_text: str) -> tuple[str, int]:
    """Add a non-numeric qualifier next to uncovered performance-multiplier sentences.

    The function is deliberately source-agnostic because it is only called after Run223 has
    already proven that the same multiplier exists in source context and that the source wording
    is benchmark/expectation scoped.  The added sentence therefore weakens/generalizes nothing;
    it restores attribution/condition/variability that was lost during article generation.
    """
    text = str(markdown_text or "")
    if not text or _QUALIFIER in text and not any(
        _needs_scope_qualifier(part) for part in _SENTENCE_SPLIT_RE.split(text)
    ):
        return text, 0

    out: list[str] = []
    changed = 0
    in_fence = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence or stripped.startswith("#"):
            out.append(line)
            continue

        parts = _SENTENCE_SPLIT_RE.split(line)
        rebuilt: list[str] = []
        for part in parts:
            if _needs_scope_qualifier(part):
                # Never duplicate the qualifier if it is already adjacent in the same sentence.
                if _QUALIFIER not in part:
                    rebuilt.append(part + _QUALIFIER)
                    changed += 1
                else:
                    rebuilt.append(part)
            else:
                rebuilt.append(part)
        out.append("".join(rebuilt))
    return "\n".join(out), changed


def rescue_multiplier_scope(parsed: dict, reason_rows: list[dict] | None) -> tuple[dict, list[str]]:
    """Patch only a gate-proven multiplier-scope loss, preserving all original numerics."""
    if not _has_multiplier_scope_failure(reason_rows):
        return dict(parsed or {}), []
    rescued = dict(parsed or {})
    before = str(rescued.get("note_draft") or "")
    before_numbers = re.findall(r"(?<![\w.])\d+(?:\.\d+)?", before)
    after, count = add_multiplier_scope_qualifier(before)
    if not count or after == before:
        return rescued, []
    after_numbers = re.findall(r"(?<![\w.])\d+(?:\.\d+)?", after)
    if before_numbers != after_numbers:
        # The qualifier contains no numbers; any numeric drift means an unexpected transform.
        return dict(parsed or {}), []
    rescued["note_draft"] = after
    loss = dict(rescued.get("_rescue_loss") or {})
    loss.setdefault("removed_sentences", 0)
    loss.setdefault("important_numeric_removed", False)
    loss.setdefault("loss_exceeded", False)
    rescued["_rescue_loss"] = loss
    return rescued, [f"run224_multiplier_scope_qualifier:{count}"]


def install(pipeline_module):
    """Wrap the existing deterministic publication rescue without changing its other behavior."""
    if getattr(pipeline_module, "_run224_multiplier_deterministic_rescue_installed", False):
        return pipeline_module
    base_rescue = pipeline_module._apply_deterministic_publication_rescue

    def wrapped_rescue(parsed: dict, reason_rows: list[dict]):
        base_parsed, base_changes = base_rescue(parsed, reason_rows)
        scope_parsed, scope_changes = rescue_multiplier_scope(base_parsed, reason_rows)
        if not scope_changes:
            return base_parsed, base_changes
        changes = list(dict.fromkeys(list(base_changes or []) + scope_changes))
        return scope_parsed, changes

    pipeline_module._apply_deterministic_publication_rescue = wrapped_rescue
    pipeline_module._run224_multiplier_deterministic_rescue_installed = True
    return pipeline_module
