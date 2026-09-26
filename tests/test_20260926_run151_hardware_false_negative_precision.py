import unittest

from fact_validation_signals import _find_false_negative_evidence_claims


class Run151HardwareFalseNegativePrecisionTests(unittest.TestCase):
    def setUp(self):
        self.meta = {"coverage": {"hardware": "FOUND"}}
        self.source = (
            "TrackEverything tracks videos exceeding 1000 frames within 40 GB "
            "of GPU memory."
        )

    def test_run151_operational_uncertainty_does_not_negate_supported_gpu_fact(self):
        draft = (
            "1000フレームを超える長時間・高密度な3D追跡においてGPUメモリ内で"
            "動作することを示しているものの、実運用における制約や検証は"
            "一次資料からは確認できないため。"
        )
        self.assertEqual(
            [],
            _find_false_negative_evidence_claims(draft, self.meta, self.source),
        )

    def test_explicit_gpu_requirement_unknown_still_hard_blocks(self):
        draft = "GPU要件は一次資料では確認できない。"
        self.assertIn(
            "FALSE_NEGATIVE_EVIDENCE_CLAIM: hardware",
            _find_false_negative_evidence_claims(draft, self.meta, self.source),
        )

    def test_explicit_hardware_configuration_unpublished_still_hard_blocks(self):
        draft = "ハードウェア構成は未公開です。"
        self.assertIn(
            "FALSE_NEGATIVE_EVIDENCE_CLAIM: hardware",
            _find_false_negative_evidence_claims(draft, self.meta, self.source),
        )


if __name__ == "__main__":
    unittest.main()
