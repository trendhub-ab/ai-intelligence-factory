import ast
import inspect
import unittest
from unittest.mock import patch

import candidate_identity
import gate_reasoning
import note_manuscript
import screening_protocol
import source_roi_policy
import pipeline


class Run241BatchedIntegrationTests(unittest.TestCase):
    def test_pipeline_is_physically_slimmed_and_heavy_bodies_left(self):
        src=inspect.getsource(pipeline)
        self.assertLessEqual(len(src.splitlines()),11497)
        self.assertNotIn('"""URL Dedup専用の正規化。意味のあるpath/queryは変更しない。"""',src)
        self.assertNotIn('"""Compute recency-weighted Source ROI and learning readiness."""',src)
        self.assertNotIn('def _salvage_screening_json_rows(text: str) -> list[dict]:\n    """Recover complete JSON',src)

    def test_candidate_canonicalizer_alias_is_exact_and_identity_uses_live_binding(self):
        self.assertIs(pipeline._canonicalize_url_impl, candidate_identity.canonicalize_url)
        with patch.object(pipeline,'canonicalize_url',side_effect=lambda u:'LIVE:'+u):
            self.assertEqual(pipeline.candidate_identity_urls({'url':'https://x.test'}), {'LIVE:https://x.test'})

    def test_subscription_wrapper_reads_live_enable_and_campaign(self):
        with patch.object(pipeline,'ENABLE_SUBSCRIPTION_ATTRIBUTION',False):
            self.assertEqual(pipeline.build_subscription_tracking_url('a','https://x.test'), '')
        with patch.object(pipeline,'ENABLE_SUBSCRIPTION_ATTRIBUTION',True), patch.object(pipeline,'SUBSCRIPTION_CAMPAIGN_ID','live-campaign'):
            url=pipeline.build_subscription_tracking_url('a','https://x.test')
            self.assertIn('utm_campaign=live-campaign',url)

    def test_gate_constants_and_mapping_are_canonical(self):
        self.assertEqual(pipeline.REASON_CODE_FACT_NUMERICAL_MISMATCH, gate_reasoning.REASON_CODE_FACT_NUMERICAL_MISMATCH)
        self.assertIs(pipeline._reason_code, gate_reasoning.reason_code)
        self.assertEqual(pipeline.classify_gate_reason_severity('human_appeal','headline_flattened'), gate_reasoning.GATE_SEVERITY_SOFT)

    def test_screening_wrapper_reads_live_profit_weights(self):
        with patch.object(pipeline,'DEEP_DIVE_DECISION_WEIGHT',1.0), patch.object(pipeline,'DEEP_DIVE_COMMERCIAL_WEIGHT',0.0):
            self.assertEqual(pipeline.deep_dive_priority_score(83,1),83.0)
        with patch.object(pipeline,'PORTFOLIO_TOPICS',('MODEL','OTHER')):
            self.assertEqual(pipeline.normalize_portfolio_topic('AGENT'),'OTHER')

    def test_source_roi_wrapper_reads_live_smoothed_rate_callback(self):
        with patch.object(pipeline,'_source_roi_smoothed_rate',side_effect=lambda *a:0.9):
            out=pipeline.compute_source_roi_profile({'runs':[]})
        self.assertTrue(out)
        first=next(iter(out.values()))
        self.assertEqual(first['stock_yield'],0.9)
        self.assertEqual(first['ready_yield'],0.9)
        self.assertEqual(first['generation_efficiency'],0.9)

    def test_no_run241_module_imports_provider_sdk(self):
        for module in (candidate_identity,note_manuscript,gate_reasoning,screening_protocol,source_roi_policy):
            tree=ast.parse(inspect.getsource(module))
            imported=[]
            for n in ast.walk(tree):
                if isinstance(n,ast.Import): imported.extend(a.name for a in n.names)
                if isinstance(n,ast.ImportFrom) and n.module: imported.append(n.module)
            self.assertFalse(any(x.startswith(('google','requests','notion')) for x in imported), imported)


if __name__ == '__main__':
    unittest.main()
