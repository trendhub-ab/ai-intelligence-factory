"""Regression for real Production E2E #39543411060: Run296 is the last public renderer.

Provider-free: only probe the outer wrapper and the final Run180 prompt, never render
a user article, reach Notion, or call Gemini. The full manuscript is the cache identity;
the existing bounded prompt excerpt uses only the first 6000 characters.
"""
from __future__ import annotations

from types import SimpleNamespace

import run180_eyecatch_semantic_layout as r180
import run181_eyecatch_visual_balance as r181
import run296_editorial_format_v2 as r296


def _installed_run296(monkeypatch):
    # Run306 typography is outside this argument-forwarding regression.
    monkeypatch.setattr(r296, "_install_run306_adaptive_typography", lambda _r181: None)
    # Restore every mutated global function after testing this in-process installer.
    monkeypatch.setattr(r180, "_layout_prompt", r180._layout_prompt)
    monkeypatch.setattr(r180, "_validate_layout_plan", r180._validate_layout_plan)
    monkeypatch.setattr(r181, "_subheadline_lines", r181._subheadline_lines)
    received = []

    def inner_renderer(title, summary, output_path, category=None, date_label=None, article_text=""):
        received.append({
            "title": title, "summary": summary, "output_path": output_path,
            "category": category, "date_label": date_label, "article_text": article_text,
        })
        return output_path

    pipeline = SimpleNamespace(generate_note_editorial_eyecatch=inner_renderer)
    r296._install_eyecatch_policy(pipeline)
    return pipeline, received


def test_run296_final_renderer_forwards_full_article_text(monkeypatch):
    pipeline, received = _installed_run296(monkeypatch)
    manuscript = "本文全体を同一ハッシュに結び付ける" * 370
    path = pipeline.generate_note_editorial_eyecatch(
        "新しい記事タイトル", "最新の要約", "/tmp/eyecatch.png",
        category="RESEARCH", date_label="2026-10-21", article_text=manuscript,
    )
    assert path == "/tmp/eyecatch.png"
    assert received == [{
        "title": "新しい記事タイトル", "summary": "最新の要約",
        "output_path": "/tmp/eyecatch.png", "category": "RESEARCH",
        "date_label": "2026-10-21", "article_text": manuscript,
    }]


def test_run296_prompt_keeps_full_article_excerpt_but_no_extra_request(monkeypatch):
    _installed_run296(monkeypatch)
    article = "PRECISE_SOURCE_FACTS_ON_PRIMARY_RECORD " * 200 + "TAIL_ONLY_MARKER_77777"
    prompt = r180._layout_prompt("精確な記事タイトル", "一次資料を読み解く", article)
    assert "PRECISE_SOURCE_FACTS_ON_PRIMARY_RECORD" in prompt
    assert "article_excerpt" in prompt
    assert "Run296追加条件" in prompt
    # The source excerpt stays capped at 6000, though cache identity covers all.
    assert article[:6000] in prompt
    assert "TAIL_ONLY_MARKER_77777" not in prompt
