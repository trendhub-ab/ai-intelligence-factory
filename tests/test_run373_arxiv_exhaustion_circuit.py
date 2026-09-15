from __future__ import annotations

import types

import arxiv_exhaustion_circuit as run373
import arxiv_stability_layer as arxiv


class FakeClock:
    def __init__(self):
        self.value = 100.0
        self.sleeps = []

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(float(seconds))
        self.value += float(seconds)


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = int(status_code)
        self.content = b""
        self.text = ""
        self.url = "https://export.arxiv.org/api/query"
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class TimeoutHttp:
    def __init__(self):
        self.calls = 0

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls += 1
        raise TimeoutError("read timed out")


class StatusHttp:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = 0

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls += 1
        status = self.statuses.pop(0)
        return FakeResponse(status)


def make_pipeline(http, run_id="run-60"):
    clock = FakeClock()
    controller = arxiv.ArxivStabilityController(
        http=http,
        run_id=run_id,
        now_fn=clock.now,
        sleep_fn=clock.sleep,
    )
    controller.retry_delay = 4.0
    controller.min_interval = 4.0
    pipeline = types.SimpleNamespace(
        _fetch_arxiv_with_retry=controller.fetch,
        _ARXIV_STABILITY_CONTROLLER=controller,
        logger=None,
    )
    run373.install(pipeline)
    return pipeline, controller, clock


def test_two_timeouts_open_same_run_circuit_and_third_call_never_hits_network():
    http = TimeoutHttp()
    pipeline, controller, _clock = make_pipeline(http)

    first = pipeline._fetch_arxiv_with_retry(
        "https://export.arxiv.org/api/query", {"search_query": "cat:cs.AI"}
    )

    assert first is None
    assert http.calls == 2
    assert controller._state["last_error_type"] == "TimeoutError"
    assert controller._state["circuit_run_id"] == "run-60"
    assert controller._state["circuit_status"] == 0

    second = pipeline._fetch_arxiv_with_retry(
        "https://export.arxiv.org/api/query", {"id_list": "2609.00001"}
    )
    assert second is None
    assert http.calls == 2


def test_two_transient_5xx_responses_open_same_run_circuit():
    http = StatusHttp([500, 502])
    pipeline, controller, _clock = make_pipeline(http)

    response = pipeline._fetch_arxiv_with_retry(
        "https://export.arxiv.org/api/query", {"search_query": "cat:cs.LG"}
    )

    assert response is None
    assert http.calls == 2
    assert controller._state["circuit_run_id"] == "run-60"
    assert controller._state["circuit_status"] == 502

    assert pipeline._fetch_arxiv_with_retry(
        "https://export.arxiv.org/api/query", {"id_list": "2609.00002"}
    ) is None
    assert http.calls == 2


def test_permanent_404_does_not_open_circuit():
    http = StatusHttp([404])
    pipeline, controller, _clock = make_pipeline(http)

    response = pipeline._fetch_arxiv_with_retry(
        "https://export.arxiv.org/api/query", {"id_list": "bad-id"}
    )

    assert response is None
    assert http.calls == 1
    assert controller._state["circuit_run_id"] == ""
    assert controller._state["circuit_status"] == 0


def test_existing_429_circuit_is_not_reopened_or_reclassified():
    http = StatusHttp([429])
    pipeline, controller, _clock = make_pipeline(http)

    assert pipeline._fetch_arxiv_with_retry(
        "https://export.arxiv.org/api/query", {"search_query": "cat:cs.AI"}
    ) is None
    assert controller._state["circuit_run_id"] == "run-60"
    assert controller._state["circuit_status"] == 429
    assert http.calls == 1


def test_install_is_idempotent():
    http = StatusHttp([404])
    pipeline, _controller, _clock = make_pipeline(http)
    installed = pipeline._fetch_arxiv_with_retry
    run373.install(pipeline)
    assert pipeline._fetch_arxiv_with_retry is installed
