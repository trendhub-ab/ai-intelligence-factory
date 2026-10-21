"""Provider-free contract: V1 public eyecatch cache is bound to final persisted manuscript.

This intentionally inspects the real Production callsite, not an isolated helper.
It protects against passing a summary, 6000-character excerpt, or intermediate draft.
"""
from __future__ import annotations

import ast
from pathlib import Path

from eyecatch_copy_runtime_store import EyecatchCopyStore


ROOT = Path(__file__).resolve().parents[1]


def test_production_eyecatch_receives_exact_final_manuscript():
    tree = ast.parse((ROOT / "pipeline.py").read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "generate_note_editorial_eyecatch"
    ]
    assert len(calls) == 1, "unexpected public-eyecatch caller changed; audit each caller"
    call = calls[0]
    body_kw = next((kw for kw in call.keywords if kw.arg == "article_text"), None)
    assert body_kw is not None, "Production call must bind the final saved manuscript"
    assert isinstance(body_kw.value, ast.Name)
    assert body_kw.value.id == "clean_manuscript", "partial text/intermediate draft cannot be cache identity"
    final_bodies = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "clean_manuscript"
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "build_clean_note_manuscript"
    ]
    assert len(final_bodies) == 1
    assert final_bodies[0].lineno < call.lineno, "render cannot precede finalized article"


def test_remote_identity_includes_manuscript_changes_beyond_excerpt():
    title, summary = "同一のタイトル", "同一の要約"
    prefix = "公開前の長い本文" * 850
    old = prefix + "以前の結論"
    changed = prefix + "改訂した結論"
    assert old[:6000] == changed[:6000]
    assert EyecatchCopyStore.source_digest(title, summary, old) != (
        EyecatchCopyStore.source_digest(title, summary, changed)
    )
    assert EyecatchCopyStore.source_digest(title, summary, old) != (
        EyecatchCopyStore.source_digest(title, summary)
    )
