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
            self.assertEqual(data['max_output_tokens'],7800)
            self.assertIn('V13 EVIDENCE-SLOTTED PROSE',data['prompt'])
            self.assertIn('Gemini Run359同期',data['prompt'])
            self.assertIn('追加provider callの許可ではない',data['prompt'])
            self.assertIn('gemini_run359_provider_neutral',data['contract_version_v10'])
            self.assertGreater(pf['headroom'],10000)
            self.assertLess(pf['request_bytes'],24576)

    def test_run359_sync_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'w.json'
            p.write_text(json.dumps({'provider':'groq','stage':'article','model':'openai/gpt-oss-120b','rate_policy':'gpt_oss_120b','prompt':'base','max_output_tokens':2800,'reasoning_effort':'low','schema':None}),encoding='utf-8')
            first=route_compound_writer_v10(str(p))['prompt']
            second=route_compound_writer_v10(str(p))['prompt']
            self.assertEqual(first,second)
            self.assertEqual(second.count('Gemini Run359同期'),1)
            self.assertEqual(second.count('V13 EVIDENCE-SLOTTED PROSE'),1)

    def test_guard_rejects_unverified_benchmark_and_access_details(self):
        paras=[('簡単に言えば、測定条件と利用条件は別です。' * 25) for _ in range(8)]
        article=paras[0]+'\n\n'+paras[1]+'\n\n## Astraの100%を読む\n\n'+paras[2]+'\n\n'+paras[3]+'\n\n## zero-dayが示したこと\n\n'+paras[4]+'\n\n'+paras[5]+'\n\n## 利用条件を急いで決めない\n\n'+paras[6]+'\n\n'+paras[7]+' 認証プロセスを確認し、限定された脆弱性リスト全体を網羅したと判断する。'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'r.json'; p.write_text(json.dumps(report(article),ensure_ascii=False),encoding='utf-8')
            issues=inspect_compound_writer_v10(str(p))['issues']
            self.assertIn('unsupported_access_procedure',issues)
            self.assertIn('unsupported_exploitbench_structure',issues)

    def test_v12_real_failure_phrases_are_now_rejected_together(self):
        base='既知脆弱性からexploitを開発する評価です。簡単に言えば測定条件を区別します。'
        paras=[base*12 for _ in range(8)]
        paras[0]+=' 評価対象の脆弱性リスト全体に対して成功しました。'
        paras[1]+=' OpenAI内部で詳細に検証しました。'
        paras[2]+=' 他の環境で再現されない可能性があります。'
        paras[3]+=' Astraが高度な脆弱性分析能力を持つことを示します。'
        paras[4]+=' 安全策は名称が示す通りです。'
        article=paras[0]+'\n\n'+paras[1]+'\n\n## 100%をどう読むか\n\n'+paras[2]+'\n\n'+paras[3]+'\n\n## Daybreak Blueとの違い\n\n'+paras[4]+'\n\n'+paras[5]+'\n\n## 判断を急がない理由\n\n'+paras[6]+'\n\n私なら、一次情報で利用条件を確認し、新しい一次情報が出た時点で再評価します。'+paras[7]+'。'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'r.json'; p.write_text(json.dumps(report(article),ensure_ascii=False),encoding='utf-8')
            issues=inspect_compound_writer_v10(str(p))['issues']
            self.assertIn('unsupported_exploitbench_structure',issues)
            self.assertIn('unsupported_validation_detail',issues)
            self.assertIn('unsupported_environment_counterfactual',issues)
            self.assertIn('unsupported_generalized_capability_label',issues)
            self.assertIn('safeguard_name_to_function_inference',issues)

    def test_incomplete_terminal_surface_is_rejected(self):
        para='既知脆弱性からexploitを開発する評価です。簡単に言えば、測定条件と利用条件は別です。'*10
        article=para+'\n\n'+para+'\n\n## 100%の意味\n\n'+para+'\n\n'+para+'\n\n## 条件の違い\n\n'+para+'\n\n'+para+'\n\n## 判断の置き方\n\n'+para+'\n\n私なら、一次情報を確認して再評価するという判断を続ける具体'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'r.json'; p.write_text(json.dumps(report(article),ensure_ascii=False),encoding='utf-8')
            issues=inspect_compound_writer_v10(str(p))['issues']
            self.assertIn('article_terminal_punctuation_missing',issues)


if __name__=='__main__':
    unittest.main()
