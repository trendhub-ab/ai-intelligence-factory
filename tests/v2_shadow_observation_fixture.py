from __future__ import annotations

from v2_live_shadow_acquisition import LiveAcquisitionConfig
from v2_shadow_observation import build_manual_observation
from tests.v2_live_shadow_acquisition_fixture import FIXED_NOW, fixture_http_get


FIXED_RUN_ID = "v2-003-fixture"


def build_fixture_report():
    return build_manual_observation(
        now=FIXED_NOW,
        run_id=FIXED_RUN_ID,
        config=LiveAcquisitionConfig(
            hn_limit=2,
            arxiv_limit=2,
            total_candidate_limit=4,
            timeout_seconds=2,
        ),
        http_get=fixture_http_get,
    )
