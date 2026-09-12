import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline.py"


class ProductReviewProviderLockTests(unittest.TestCase):
    """Fail closed if Product Review is silently migrated away from Gemini.

    Candidate screening / Evidence / planning may evolve independently. Product Review is an
    explicit exception: changing its provider requires an intentional contract change and review.
    These tests are static and zero-API.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = PIPELINE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source, filename=str(PIPELINE))

    def _function(self, name: str) -> ast.FunctionDef:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        self.fail(f"required function missing: {name}")

    def test_product_review_pool_uses_gemini_generation_wrapper_only(self):
        node = self._function("_call_product_review_pool")
        segment = ast.get_source_segment(self.source, node) or ""
        self.assertIn("_generate_via_chat(", segment)
        self.assertIn("DEEP_DIVE_MODEL_POOL", segment)
        lowered = segment.lower()
        self.assertNotIn("groq", lowered)
        self.assertNotIn("openai", lowered)
        self.assertNotIn("anthropic", lowered)
        self.assertNotIn("provider_router", lowered)

    def test_product_review_model_pool_remains_gemini_named_configuration(self):
        self.assertIn('"GEMINI_DEEP_DIVE_MODEL_CANDIDATES"', self.source)
        self.assertIn('"gemini-3.6-flash"', self.source)

    def test_generation_wrapper_is_explicit_google_genai_path(self):
        node = self._function("_generate_via_chat")
        segment = ast.get_source_segment(self.source, node) or ""
        self.assertIn("client.chats.create", segment)
        self.assertIn("send_message", segment)
        self.assertIn("Gemini", segment)


if __name__ == "__main__":
    unittest.main()
