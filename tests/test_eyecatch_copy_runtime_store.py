"""Provider-free tests: no real GitHub calls or secrets."""
import base64

from cryptography.fernet import Fernet

from eyecatch_copy_runtime_store import EyecatchCopyStore


class Response:
    def __init__(self, status, data=None):
        self.status_code = status
        self.data = data or {}

    def json(self):
        return self.data


class FakeGithub:
    def __init__(self):
        self.files = {}
        self.get_calls = 0
        self.put_calls = 0
        self.get_status = None
        self.put_status = None

    def get(self, url, *, headers, params, timeout):
        assert params == {"ref": "runtime-state"}
        assert "Authorization" in headers
        self.get_calls += 1
        if self.get_status is not None:
            return Response(self.get_status)
        if url not in self.files:
            return Response(404)
        return Response(200, {"content": self.files[url], "sha": "blob-sha"})

    def put(self, url, *, headers, json, timeout):
        self.put_calls += 1
        assert json["branch"] == "runtime-state"
        assert "sha" not in json
        if self.put_status:
            return Response(self.put_status)
        if url in self.files:
            return Response(409)
        self.files[url] = json["content"]
        return Response(201)


def config():
    return {
        "GITHUB_REPOSITORY": "trendhub-ab/ai-intelligence-factory",
        "AIIF_RUNTIME_STATE_GITHUB_TOKEN": "test-token",
        "AIIF_EYECATCH_COPY_FERNET_KEY": Fernet.generate_key().decode(),
    }


def test_cross_run_encrypted_roundtrip_and_new_article_invalidation():
    env = config()
    http = FakeGithub()
    first = EyecatchCopyStore(env=env, http=http)
    plan = {"eyecatch_title": "独自の見出し", "title_lines": ["独自の見出し"]}
    assert first.save("非公開のタイトル", "非公開の要約", plan, "非公開の本文")
    assert http.put_calls == 1
    assert len(http.files) == 1
    uri, encoded = next(iter(http.files.items()))
    assert "非公開" not in uri
    assert "非公開".encode("utf-8") not in base64.b64decode(encoded)
    second = EyecatchCopyStore(env=env, http=http)
    assert second.load("非公開のタイトル", "非公開の要約", "非公開の本文") == plan
    assert second.load("非公開のタイトル", "非公開の要約", "変更された本文") is None
    assert second.load("変更されたタイトル", "非公開の要約", "非公開の本文") is None


def test_no_secret_or_protected_branch_never_calls_remote():
    http = FakeGithub()
    env = config()
    env.pop("AIIF_EYECATCH_COPY_FERNET_KEY")
    assert not EyecatchCopyStore(env=env, http=http).save("a", "b", {})
    env = config()
    env["AIIF_RUNTIME_STATE_BRANCH"] = "main"
    assert EyecatchCopyStore(env=env, http=http).load("a", "b") is None
    env = config()
    env["SYNTHETIC_REGRESSION_MODE"] = "true"
    assert EyecatchCopyStore(env=env, http=http).load("a", "b") is None
    assert http.get_calls == 0
    assert http.put_calls == 0


def test_wrong_key_and_corruption_do_not_return_unverified_copy():
    http = FakeGithub()
    env = config()
    store = EyecatchCopyStore(env=env, http=http)
    assert store.save("title", "summary", {"eyecatch_title": "approved"})
    assert EyecatchCopyStore(env=config(), http=http).load("title", "summary") is None
    url = next(iter(http.files))
    http.files[url] = base64.b64encode(b"malformed-encryption").decode()
    assert store.load("title", "summary") is None
    assert not store.save("title", "summary", {"eyecatch_title": "replacement"})
    assert http.put_calls == 1


def test_permission_error_blocks_write_and_no_blind_retry():
    http = FakeGithub()
    http.get_status = 403
    store = EyecatchCopyStore(env=config(), http=http)
    assert not store.save("title", "summary", {"eyecatch_title": "draft"})
    assert http.put_calls == 0


def test_409_competing_writer_uses_first_committed_copy():
    env = config()
    http = FakeGithub()
    store = EyecatchCopyStore(env=env, http=http)
    prior = {"eyecatch_title": "first"}
    assert store.save("title", "summary", prior)
    assert store.save("title", "summary", {"eyecatch_title": "second"})
    assert store.load("title", "summary") == prior
    assert http.put_calls == 1


def test_activation_proof_is_manual_main_only_and_uses_no_article_providers():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/eyecatch-copy-activation-proof.yml").read_text(encoding="utf-8")
    assert "  workflow_dispatch:" in workflow
    assert "\\n  pull_request:" not in workflow
    assert "\\n  push:" not in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "github.repository == 'trendhub-ab/ai-intelligence-factory'" in workflow
    assert "needs: encrypted-writer" in workflow
    assert "needs: [encrypted-writer, encrypted-reader]" in workflow
    assert "ACTIVATION_PROOF_WRITER=PASS" in workflow
    assert "ACTIVATION_PROOF_SEPARATE_RUNNER=PASS" in workflow
    assert "ACTIVATION_PROOF_CLEANUP=PASS" in workflow
    assert "secrets.AIIF_EYECATCH_COPY_FERNET_KEY" in workflow
    assert "os.environ[\"CANARY_RUN_ID\"]" in workflow
    assert "SYNTHETIC-ARTICLE-ONLY" in workflow
    assert "production_pipeline.py" not in workflow
    assert "gemini" not in workflow.lower()
