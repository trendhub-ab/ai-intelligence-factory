import unittest

from local_skills.evidence_boundary import _repair_numeric_deletion_residue
from local_skills.writer import _gloss


class Run153NonEngineerAccessRegressionTests(unittest.TestCase):
    def test_robotics_terms_receive_plain_language_first_use_bridges(self):
        seen = set()
        text = (
            "世界行動モデルでデノイズを制御サイクルへ分散し、"
            "再計画遅延を下げる。"
        )
        out = _gloss(text, seen)
        self.assertIn("世界行動モデル（ロボットの次の行動と、その後に見える状況をまとめて予測する仕組み）", out)
        self.assertIn("デノイズ（ノイズを少しずつ取り除きながら予測を整える処理）", out)
        self.assertIn("制御サイクル（状況を見て次の動きを決める一回分の流れ）", out)
        self.assertIn("再計画遅延（次の動きを計算し直すまでの待ち時間）", out)

    def test_numeric_deletion_residue_does_not_leave_from_to_fragment(self):
        self.assertEqual(
            "従来比で約4.5倍高速化した。",
            _repair_numeric_deletion_residue("従来比でからへ約4.5倍高速化した。"),
        )

    def test_numeric_deletion_residue_repairs_possessive_fragment(self):
        self.assertEqual(
            "単一A100 GPU上での高速化が確認された。",
            _repair_numeric_deletion_residue("単一A100 GPU上でからへの高速化が確認された。"),
        )


if __name__ == "__main__":
    unittest.main()
