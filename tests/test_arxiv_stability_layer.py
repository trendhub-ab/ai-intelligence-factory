from __future__ import annotations

import types

import arxiv_stability_layer as layer


class FakeClock:
    def __init__(self, start: float = 100.0):
        self.value = float(start)
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        seconds = float(seconds)
        self.sleeps.append(seconds)
        self.value += seconds


class FakeResponse:
    def __init__(self, status_code: int, body: bytes = b"<feed />"):
        self.status_code = int(status_code)
        self.content = body
        self.text = body.decode("utf-8", errors="replace")
        self.url = "https://export.arxiv.org/api/query"
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttp:
    def __init__(self, statuses: list[int]):
        self.statuses = list(statuses)
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params=None, timeout=None, headers=None):
        # These tests intentionally run process-local, so every GET here is an arXiv
        # transport call rather than runtime-state GitHub I/O.
        self.calls.append((str(url), dict(params or {})))
        status = self.statuses.pop(0) if self.statuses else 200
        return FakeResponse(status)


def make_controller(statuses: list[int], clock: FakeClock | None = None):
    clock = clock or FakeClock()
    http = FakeHttp(statuses)
    controller = layer.ArxivStabilityController(
        http=http,
        run_id="run-58",
        now_fn=clock.now,
        sleep_fn=clock.sleep,
    )
    return controller, http, clock


def test_required_delay_respects_four_second_floor():
    assert layer._required_delay(100.0, 102.0, 4.0) == 2.0
    assert layer._required_delay(100.0, 104.0, 4.0) == 0.0
    assert layer._required_delay(0.0, 101.0, 4.0) == 0.0


def test_successful_metadata_is_cached_and_duplicate_call_is_avoided(monkeypatch):
    monkeypatch.setenv("AIIF_ARXIV_MIN_INTERVAL_SECONDS", "4")
    controller, http, _clock = make_controller([200])
    params = {"id_list": "2609.01455", "start": 0, "max_results": 1}

    first = controller.fetch("https://export.arxiv.org/api/query", params)
    second = controller.fetch("https://export.arxiv.org/api/query", params)

    assert first is not None and first.status_code == 200
    assert second is not None and second.status_code == 200
    assert len(http.calls) == 1
    assert second.content == first.content


def test_429_opens_same_run_circuit_without_retry(monkeypatch):
    monkeypatch.setenv("AIIF_ARXIV_MIN_INTERVAL_SECONDS", "4")
    controller, http, _clock = make_controller([429, 200])

    first = controller.fetch(
        "https://export.arxiv.org/api/query",
        {"search_query": "cat:cs.AI OR cat:cs.LG", "max_results": 47},
    )
    second = controller.fetch(
        "https://export.arxiv.org/api/query",
        {"id_list": "2608.13505", "max_results": 1},
    )

    assert first is None
    assert second is None
    assert len(http.calls) == 1
    assert controller._state["circuit_status"] == 429
    assert controller._state["circuit_run_id"] == "run-58"


def test_503_also_opens_circuit_without_confirmation_retry(monkeypatch):
    monkeypatch.setenv("AIIF_ARXIV_MIN_INTERVAL_SECONDS", "4")
    controller, http, _clock = make_controller([503, 200])

    assert controller.fetch(
        "https://export.arxiv.org/api/query", {"id_list": "2608.19147"}
    ) is None
    assert len(http.calls) == 1
    assert controller._state["circuit_status"] == 503


def test_non_overload_transport_failure_has_only_one_bounded_retry(monkeypatch):
    monkeypatch.setenv("AIIF_ARXIV_MIN_INTERVAL_SECONDS", "4")
    monkeypatch.setenv("AIIF_ARXIV_TRANSIENT_RETRY_DELAY_SECONDS", "4")
    clock = FakeClock()

    class TimeoutThenSuccessHttp(FakeHttp):
        def __init__(self):
            super().__init__([])
            self.count = 0

        def get(self, url, params=None, timeout=None, headers=None):
            self.calls.append((str(url), dict(params or {})))
            self.count += 1
            if self.count == 1:
                raise TimeoutError("provider read timed out")
            return FakeResponse(200)

    http = TimeoutThenSuccessHttp()
    controller = layer.ArxivStabilityController(
        http=http,
        run_id="run-58",
        now_fn=clock.now,
        sleep_fn=clock.sleep,
    )

    response = controller.fetch(
        "https://export.arxiv.org/api/query", {"id_list": "2609.01455"}
    )

    assert response is not None and response.status_code == 200
    assert len(http.calls) == 2
    assert clock.sleeps == [4.0]


def test_fresh_cache_is_served_even_when_same_run_circuit_is_open(monkeypatch):
    monkeypatch.setenv("AIIF_ARXIV_MIN_INTERVAL_SECONDS", "4")
    controller, http, clock = make_controller([])
    url = "https://export.arxiv.org/api/query"
    params = {"id_list": "2609.01455"}
    key = layer._cache_key(url, params)
    controller._state["entries"][key] = {
        "fetched_at_epoch": clock.now(),
        "body_b64": "PGZlZWQgLz4=",  # <feed />
    }
    controller._state["circuit_run_id"] = "run-58"
    controller._state["circuit_status"] = 429
    controller._state_loaded = True

    response = controller.fetch(url, params)

    assert response is not None and response.status_code == 200
    assert response.content == b"<feed />"
    assert http.calls == []


def test_circuit_is_scoped_to_current_actions_run():
    state = {"circuit_run_id": "34964818527"}
    assert layer._circuit_open_for_run(state, "34964818527") is True
    assert layer._circuit_open_for_run(state, "34970000000") is False


def test_install_replaces_only_arxiv_helper_and_is_idempotent(monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GH_PAT", raising=False)

    def legacy(url, params):
        return "legacy"

    pipeline = types.SimpleNamespace(
        _fetch_arxiv_with_retry=legacy,
        requests=FakeHttp([200]),
        GH_PAT="",
        logger=None,
    )

    first = layer.install(pipeline)
    installed = first._fetch_arxiv_with_retry
    second = layer.install(pipeline)

    assert installed is not legacy
    assert second._fetch_arxiv_with_retry is installed
    assert first.ARXIV_STABILITY_MIN_INTERVAL_SECONDS >= 3.0
    assert first.ARXIV_STABILITY_STATE_PATH == layer.STATE_PATH
