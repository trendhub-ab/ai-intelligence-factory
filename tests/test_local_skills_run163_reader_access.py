from __future__ import annotations

import pipeline
import reader_value_review_bridge as bridge
from local_skills.writer import render_body


def _run163_snapshot() -> dict:
    return {
        "schema": "aiif_local_writer_snapshot_v1",
        "case_id": "29540e03159f6aad43e07fa53a211a8d",
        "canonical_entity_id": "url:https://kristoff.it/blog/source-code-availability/",
        "name": "Who Should Pay for Source Code Availability?",
        "reader_title": "Who Should Pay for Source Code Availability?：いま何を判断材料にするべきか。",
        "source": "HackerNews",
        "source_summary": (
            "簡単に言えば、オープンソースの持続可能性を支えるリポジトリの可用性問題を、"
            "P2Pネットワーク「Radicle」を用いた分散共有と開発者間のコスト負担の観点から考察。"
        ),
        "what": (
            "中央集権的なプラットフォーム（GitHub等）に依存せず、開発者やユーザーが互いに"
            "リポジトリをホストし合うことで、ソースコードの永続的な利用可能性を確保する仕組み。"
        ),
        "why_important": (
            "コードをどこから取得するか（URL）ではなく、何を取得するか（ID）に基づく管理へ移行することで、"
            "特定のサービス停止がプロジェクト停止に直結するリスクを構造的に排除できる。"
        ),
        "decision": "WATCH",
        "decision_score": 67,
        "decision_reason": (
            "概念は強力だが、Zig等の言語ツールチェーンへの直接組み込みにはRadicleノードの常時稼働が"
            "必要になるなど、実務上の導入障壁が残っているため。"
        ),
        "action": (
            "限定的な検証として、自社の依存ライブラリの可用性リスクを棚卸しし、Radicle等の分散型"
            "プロトコルが既存のミラーリング（Fork/Vendor）の代替になり得るか概念実証を行う。"
        ),
        "primary_risk": "一次情報の対象範囲を越えて一般化せず、限定した検証で条件差を確認する必要があります。",
        "best_for": "導入を急がず、条件の変化を確認して再評価できるチーム。",
        "avoid_for": "追加確認を待たず、すぐ本番適用を前提にしたいチーム。",
        "evidence_urls": ["https://kristoff.it/blog/source-code-availability/"],
    }


def test_run163_local_writer_translates_dev_terms_for_non_engineers():
    article = render_body(_run163_snapshot())
    issues = bridge._material_reader_value_issues(pipeline, article)

    assert "リポジトリ（" in article
    assert "P2Pネットワーク（" in article
    assert "ノード（" in article
    assert "Fork/Vendor（" in article
    assert not any("non_engineer_access_failure" in issue for issue in issues), issues
    assert not any("multi_axis_reader_weakness" in issue for issue in issues), issues
