from types import SimpleNamespace
import unittest

import run222_note_presentation_integrity as run222


class Run222NotePresentationIntegrityTests(unittest.TestCase):
    def test_cta_moves_after_sources_and_disclaimer(self):
        manuscript = """# Sample title

本文です。

---

### 「自分はどうする？」まで判断したい方へ

無料note本文。

[AI Decision Intelligenceについて見る](https://example.com/)

---

### Sources / Evidence
- **主一次情報**: [Official](https://example.com/source)

※本記事に含まれる見解・提案は筆者個人の意見です。
"""
        actual = run222.move_subscription_cta_after_evidence(manuscript)
        self.assertLess(actual.index("### Sources / Evidence"), actual.index("※本記事"))
        self.assertLess(actual.index("※本記事"), actual.index("### 「自分はどうする？」まで判断したい方へ"))
        self.assertEqual(actual.count("### 「自分はどうする？」まで判断したい方へ"), 1)
        self.assertEqual(actual.count("### Sources / Evidence"), 1)

    def test_already_correct_footer_order_is_idempotent(self):
        manuscript = """本文

---

### Sources / Evidence
- source

免責

---

### 「自分はどうする？」まで判断したい方へ
CTA
"""
        self.assertEqual(run222.move_subscription_cta_after_evidence(manuscript), manuscript.strip())

    def test_note_editor_removes_duplicate_h1_and_never_exposes_raw_body_h1(self):
        title = "Polars 2.0が目指す「静かな進化」は、なぜ重要か。"
        manuscript = f"""# {title}

## 30秒でわかるこの記事
本文

# 追加の大見出し

```python
# code comment must stay untouched
print('ok')
```
"""
        actual = run222.prepare_note_editor_manuscript(manuscript, title)
        self.assertFalse(actual.startswith("# "))
        self.assertIn("## 30秒でわかるこの記事", actual)
        self.assertIn("## 追加の大見出し", actual)
        self.assertIn("# code comment must stay untouched", actual)

    def test_note_transform_runs_after_existing_prepare_guard(self):
        calls = []
        title = "Same title"
        stored = """# Same title

本文

---

### 「自分はどうする？」まで判断したい方へ
CTA

---

### Sources / Evidence
Source

Disclaimer
"""

        def guarded_prepare(requested_sync_id=""):
            calls.append(("guard", requested_sync_id, stored))
            return {"title": title, "manuscript": stored, "sync_id": "a" * 32}

        module = SimpleNamespace(_prepare_article=guarded_prepare)
        run222.install_note(module)
        article = module._prepare_article("a" * 32)
        self.assertEqual(calls[0][0], "guard")
        self.assertFalse(article["manuscript"].startswith("# "))
        self.assertLess(article["manuscript"].index("Sources / Evidence"), article["manuscript"].index("自分はどうする"))

    def test_pipeline_wrapper_moves_footer_without_touching_content_semantics(self):
        before = """# Title
本文

---

### 調査と判断の時間を減らしたい方へ
CTA

---

### Sources / Evidence
Source

Disclaimer
"""
        module = SimpleNamespace(build_clean_note_manuscript=lambda *args, **kwargs: before)
        run222.install_pipeline(module)
        actual = module.build_clean_note_manuscript()
        self.assertIn("本文", actual)
        self.assertLess(actual.index("Sources / Evidence"), actual.index("調査と判断の時間を減らしたい方へ"))


if __name__ == "__main__":
    unittest.main()
