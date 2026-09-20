from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import publication_contract as contract


ROOT = Path(__file__).resolve().parents[1]


def _copy_policy_tree(target: Path) -> None:
    for relative in contract.PUBLICATION_POLICY_FILES:
        source = ROOT / relative
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)


def test_comment_and_docstring_only_changes_do_not_invalidate_ready_policy():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _copy_policy_tree(root)
        baseline = contract.policy_sha256(root, style_name="classic")
        target = root / "canonical_article_contract.py"
        target.write_text(target.read_text(encoding="utf-8") + "\n# audit-only comment\n", encoding="utf-8")
        assert contract.policy_sha256(root, style_name="classic") == baseline


def test_material_python_change_still_invalidates_policy():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _copy_policy_tree(root)
        baseline = contract.policy_sha256(root, style_name="classic")
        target = root / "canonical_article_contract.py"
        target.write_text(target.read_text(encoding="utf-8") + "\nPUBLICATION_SEMANTIC_SENTINEL = 'changed'\n", encoding="utf-8")
        assert contract.policy_sha256(root, style_name="classic") != baseline


def test_adding_duo_only_rules_does_not_invalidate_classic_or_human_policy():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _copy_policy_tree(root)
        classic = contract.policy_sha256(root, style_name="classic")
        human = contract.policy_sha256(root, style_name="human_narrative")
        duo = contract.policy_sha256(root, style_name="duo_narrative")
        target = root / "content_generation_protocol.py"
        text = target.read_text(encoding="utf-8")
        text = text.replace(
            'def _duo_narrative_editorial_style_rules() -> str:',
            'def _duo_narrative_editorial_style_rules() -> str:\n    _duo_only_semantic_marker = "v2"\n',
            1,
        )
        target.write_text(text, encoding="utf-8")
        assert contract.policy_sha256(root, style_name="classic") == classic
        assert contract.policy_sha256(root, style_name="human_narrative") == human
        assert contract.policy_sha256(root, style_name="duo_narrative") != duo


def test_ready_caption_carries_style_and_validation_recomputes_that_style():
    body = "duo article"
    caption = contract.current_ready_caption(body, style_name="duo_narrative")
    assert "style=duo_narrative" in caption
    assert contract.is_current_ready_block(body, caption)
