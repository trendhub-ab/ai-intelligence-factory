import inspect
import unittest

import editorial_quality_memory as memory


class EditorialQualityMemoryTests(unittest.TestCase):
    def test_memory_is_guidance_not_a_new_gate(self):
        text = memory.quality_memory_contract()
        self.assertIn(memory.QUALITY_MEMORY_MARKER, text)
        self.assertIn('Hard Gateや新しい事実源ではない', text)
        self.assertIn('SOURCE BOUNDARY / Evidence / 既存Decision', text)

    def test_memory_preserves_good_and_rejected_editorial_patterns(self):
        text = memory.quality_memory_contract()
        for token in (
            'GOOD PATTERNS',
            'REJECT PATTERNS',
            '記事固有の中心結論',
            'Evidence → 意味 → 読者の判断',
            '辞書説明から始める',
            '未確認は未確認のまま扱う',
            'Gateを通すこと自体を目的化',
        ):
            self.assertIn(token, text)

    def test_memory_has_no_provider_or_mutable_storage_surface(self):
        src = inspect.getsource(memory)
        for forbidden in (
            '_generate_via_chat(',
            'genai.Client(',
            'requests.',
            'httpx.',
            'notion',
            'open(',
            'Path(',
        ):
            self.assertNotIn(forbidden, src)


if __name__ == '__main__':
    unittest.main()
