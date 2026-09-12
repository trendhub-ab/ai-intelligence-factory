import json
import tempfile
import unittest
from pathlib import Path

from groq_writer_v10_compound import (
    route_compound_writer_v10,
    preflight_compound_writer_v10,
    inspect_compound_writer_v10,
)


def report(article, title='タイトルです。'):
    return {'provider':'groq','model':'groq/compound-mini','provider_calls':1,'business_writes':0,
            'result':{'text':f'===TITLE===\n{title}\n===ARTICLE===\n{article}','prompt_tokens':100,'completion_tokens':100}}


class GroqWriterV10Tests(unittest.TestCase):
    def test_route_stays_compound_with_large_headroom(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'w.json'
            p.write_text(json.dumps({'provider':'groq','stage':'article','model':'openai/gpt-oss-120b','rate_policy':'gpt_oss_120b','prompt':'base','max_output_tokens':2800,'reasoning_effort':'low','schema':None}),encoding='utf-8')
            data=route_compound_writer_v10(str(p)); pf=preflight_compound_writer_v10(str(p))
            self.assertEqual(data['model'],'groq/compound-mini')
            self.assertEqual(data['max_output_tokens'],4400)
            self.assertIn('V10 EVIDENCE-DENSE PROSE',data['prompt'])
            self.assertGreater(pf['headroom'],10000)
            self.assertLess(pf['request_bytes'],24576)

    def test_guard_rejects_unverified_benchmark_and_access_details(self):
        paras=[('簡単に言えば、測定条件と利用条件は別です。' * 25) for _ in range(8)]
        article=paras[0]+'\n\n'+paras[1]+'\n\n## Astraの100%を読む\n\n'+paras[2]+'\n\n'+paras[3]+'\n\n## zero-dayが示したこと\n\n'+paras[4]+'\n\n'+paras[5]+'\n\n## 利用条件を急いで決めない\n\n'+paras[6]+'\n\n'+paras[7]+' 認証プロセスを確認し、限定された脆弱性リスト全体を網羅したと判断する。'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'r.json'; p.write_text(json.dumps(report(article),ensure_ascii=False),encoding='utf-8')
            issues=inspect_compound_writer_v10(str(p))['issues']
            self.assertIn('unsupported_access_procedure',issues)
            self.assertIn('unsupported_exploitbench_structure',issues)


if __name__=='__main__':
    unittest.main()
