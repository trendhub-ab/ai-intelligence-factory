from __future__ import annotations

import fact_validation_signals as fact
from local_skills.evidence_boundary import apply_evidence_boundary


EVIDENCE = """
The method trains visual locomotion policies in simulation on a single GPU.
Training runs on a single GPU with differentiable simulation.
For hardware deployment, the learned policy is distilled before zero-shot transfer
to a real Unitree Go2 robot. The hardware deployment is a separate stage from
simulation training.
"""

FUSED_REASON = "source-fidelity stage fusion: single-GPU training merged with hardware deployment"


def _snapshot() -> dict:
    return {
        "source_summary": (
            "1台のGPUで視覚制御を学習し、実機へのゼロショット移植に成功した。"
        ),
        "what": "シミュレーションで視覚制御方策を学習する手法です。",
        "why_important": (
            "本手法により単一のGPUで、かつ実機での追加訓練なしに動く制御モデルを"
            "効率よく作れるようになる。"
        ),
        "decision_reason": (
            "単一GPUという低リソースで学習でき、実機へのゼロショット移植実績がある。"
        ),
        "action": "シミュレータ上で限定検証する。",
        "primary_risk": "学習条件と実機展開条件を混同しない。",
        "best_for": "限定検証するチーム。",
        "avoid_for": "すぐ本番導入するチーム。",
    }


def test_stage_boundary_repairs_local_skills_fusion_before_fact_gate():
    bounded, meta = apply_evidence_boundary(_snapshot(), EVIDENCE)

    assert "単一GPUはシミュレーション上の学習条件" in bounded["why_important"]
    assert "実機" in bounded["why_important"]
    assert "別工程" in bounded["why_important"]
    assert FUSED_REASON not in fact._find_source_semantic_fidelity_violations(
        bounded["why_important"], EVIDENCE
    )
    assert FUSED_REASON not in fact._find_source_semantic_fidelity_violations(
        bounded["source_summary"], EVIDENCE
    )
    assert meta["repaired_stage_fusion_count"] >= 2


def test_fact_gate_still_blocks_true_single_gpu_hardware_fusion():
    dangerous = "単一のGPUだけで実機ロボットを動かせる。"
    failures = fact._find_source_semantic_fidelity_violations(dangerous, EVIDENCE)

    assert FUSED_REASON in failures
