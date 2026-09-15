from __future__ import annotations

import arxiv_stability_layer as layer


class FakeHttp:
    def get(self, *args, **kwargs):
        raise AssertionError("network must not be used by prune tests")



def test_arxiv_runtime_cache_state_has_hard_total_size_bound():
    controller = layer.ArxivStabilityController(
        http=FakeHttp(),
        now_fn=lambda: 10_000.0,
        sleep_fn=lambda _seconds: None,
    )
    controller.cache_ttl = 100_000
    controller.cache_max_entries = 40
    controller.cache_state_max_bytes = 100_000
    controller._state_loaded = True

    for index in range(10):
        controller._state["entries"][f"key-{index}"] = {
            "fetched_at_epoch": 9_900.0 + index,
            "body_b64": "A" * 40_000,
        }

    controller._prune_entries()

    assert controller._state_size_bytes() <= controller.cache_state_max_bytes
    # Newest entries win when the byte budget cannot retain everything.
    kept = list(controller._state["entries"])
    assert "key-9" in kept
    assert "key-0" not in kept
    assert len(kept) < 10


def test_arxiv_runtime_cache_still_respects_entry_count_bound():
    controller = layer.ArxivStabilityController(
        http=FakeHttp(),
        now_fn=lambda: 10_000.0,
        sleep_fn=lambda _seconds: None,
    )
    controller.cache_ttl = 100_000
    controller.cache_max_entries = 4
    controller.cache_state_max_bytes = 900_000
    controller._state_loaded = True

    for index in range(8):
        controller._state["entries"][f"key-{index}"] = {
            "fetched_at_epoch": 9_900.0 + index,
            "body_b64": "QQ==",
        }

    controller._prune_entries()

    assert list(controller._state["entries"]) == ["key-7", "key-6", "key-5", "key-4"]
