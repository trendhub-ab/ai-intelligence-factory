import json
import tempfile
import unittest
from pathlib import Path

from groq_writer_v9_compound import route_compound_writer, preflight_compound_writer


class GroqWriterV9CompoundTests(unittest.TestCase):
    def test_route_switches_only_writer_to_compound_and_disables_tools(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'writer.json'
            p.write_text(json.dumps({
                'provider':'groq','stage':'article','model':'openai/gpt-oss-120b',
                'rate_policy':'gpt_oss_120b','prompt':'base prompt','max_output_tokens':2800,
                'reasoning_effort':'low','schema':None,
            }), encoding='utf-8')
            data = route_compound_writer(str(p))
            self.assertEqual(data['model'], 'groq/compound-mini')
            self.assertEqual(data['rate_policy'], 'compound_mini_article')
            self.assertEqual(data['max_output_tokens'], 4200)
            self.assertIn('V9 COMPOUND WRITER CONTRACT', data['prompt'])
            preflight = preflight_compound_writer(str(p))
            self.assertEqual(preflight['external_tools'], 'disabled')
            self.assertLessEqual(preflight['reserved_estimate'], preflight['safe_tpm'])
            self.assertGreater(preflight['headroom'], 10000)
            self.assertLess(preflight['request_bytes'], 24576)

    def test_v9_contract_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'writer.json'
            p.write_text(json.dumps({
                'provider':'groq','stage':'article','model':'openai/gpt-oss-120b',
                'rate_policy':'gpt_oss_120b','prompt':'base prompt','max_output_tokens':2800,
                'reasoning_effort':'low','schema':None,
            }), encoding='utf-8')
            route_compound_writer(str(p)); data = route_compound_writer(str(p))
            self.assertEqual(data['prompt'].count('V9 COMPOUND WRITER CONTRACT'), 1)


if __name__ == '__main__':
    unittest.main()
