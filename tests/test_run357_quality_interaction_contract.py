from __future__ import annotations

import re
from types import SimpleNamespace

import runtime_layers


_GENERIC_MONITOR_RE = re.compile(r"(?:注視|様子を見)")
_CONCRETE_ACTION_RE = re.compile(
    r"(?:限定|小さく|検証環境|PoC|比較(?:テスト|検証)|試(?:す|したい)|"
    r"見送(?:る|り)|待(?:つ|ち)|導入を急がない|CI|回帰テスト|"
    r"profil(?:ing|e)|プロファイリング|計測|ベンチマーク)",
    re.I,
)


def _fake_pipeline():
    def base_polish(parsed: dict):
        out = dict(parsed or {})
        article = str(out.get("note_draft") or "")
        article, count = re.subn(
            r"(?<![A-Za-z])WATCH(?![A-Za-z])",
            "今後の動きを注視する",
            article,
        )
        out["note_draft"] = article
        return out, ([f"note_draft:decision_code:WATCH:{count}"] if count else [])

    return SimpleNamespace(_apply_final_japanese_polish=base_polish)


def test_watch_cleanup_cannot_manufacture_generic_monitoring_failure():
    pipeline = _fake_pipeline()
    runtime_layers.install_quality_interaction_contract(pipeline)

    out, changes = pipeline._apply_final_japanese_polish(
        {"note_draft": "## 判断\n現時点の判断は WATCH です。"}
    )
    article = out["note_draft"]

    assert "WATCH" not in article
    assert "今後の動きを注視する" not in article
    assert runtime_layers._PUBLIC_WATCH_DECISION_PHRASE in article
    assert not _GENERIC_MONITOR_RE.search(article)
    assert _CONCRETE_ACTION_RE.search(article)
    assert any("watch_quality_interaction_contract" in change for change in changes)


def test_contract_does_not_rewrite_normal_author_text_without_watch_leak():
    pipeline = _fake_pipeline()
    runtime_layers.install_quality_interaction_contract(pipeline)

    original = "今後の動きを注視する必要があります。"
    out, changes = pipeline._apply_final_japanese_polish({"note_draft": original})

    assert out["note_draft"] == original
    assert not any("watch_quality_interaction_contract" in change for change in changes)


def test_contract_does_not_treat_normal_english_watch_as_management_code():
    pipeline = _fake_pipeline()
    runtime_layers.install_quality_interaction_contract(pipeline)

    original = "We Watch metrics and maintain a watchlist."
    out, _changes = pipeline._apply_final_japanese_polish({"note_draft": original})

    assert out["note_draft"] == original


def test_contract_install_is_idempotent():
    pipeline = _fake_pipeline()
    runtime_layers.install_quality_interaction_contract(pipeline)
    wrapped_once = pipeline._apply_final_japanese_polish
    runtime_layers.install_quality_interaction_contract(pipeline)

    assert pipeline._apply_final_japanese_polish is wrapped_once
    assert pipeline.RUN357_QUALITY_INTERACTION_CONTRACT is True


def test_interaction_contract_is_after_final_surface_and_before_publication_contract():
    order = runtime_layers.RUNTIME_LAYER_ORDER
    interaction = order.index("runtime_layers.install_quality_interaction_contract")
    final_surface = order.index("run249_final_publication_surface_gate.install")
    publication_contract = order.index("run194_publication_contract.install")

    assert final_surface < interaction < publication_contract
