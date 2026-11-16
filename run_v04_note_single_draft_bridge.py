"""One-off manual v0.4 note DRAFT bridge, isolated from retired V1 Daily.

The manuscript is read from one trusted-owner issue in the PRIVATE Next repo
using GH_PAT. This public repository does not store the article. Only the
existing note.com UI is used; no private note API or public release actions.
A persistent fail-closed ledger prevents duplicate drafts on repeat dispatch.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

NEXT_REPO = "trendhub-ab/ai-intelligence-factory-next"
NOTE_IDENTITY = "trendhub_biz"
NEXT_API = "https://api.github.com/repos/" + NEXT_REPO
CONFIRM = "CREATE_V04_SINGLE_PRIVATE_NOTE_DRAFT"
SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
DRAFT_LEDGER = Path.home() / ".aiif-note" / "v04-private-drafts-v1.json"
MAX_SOURCE_BYTES = 65536


def _api(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    if (type(token) is not str or len(token) < 12 or
            not url.startswith(NEXT_API + "/") and url != NEXT_API):
        raise ValueError("V04_BRIDGE_GITHUB_SOURCE_UNTRUSTED")
    body = None if payload is None else json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    request = Request(url, data=body, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AIIF-v04-One-Note-Draft-Bridge",
        **({"Content-Type": "application/json"} if body is not None else {}),
    })
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read(MAX_SOURCE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ValueError("V04_BRIDGE_GITHUB_SOURCE_UNAVAILABLE") from exc
    if not raw or len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("V04_BRIDGE_GITHUB_RESPONSE_BOUNDS")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("V04_BRIDGE_GITHUB_RESPONSE_INVALID") from exc
    if type(data) is not dict:
        raise ValueError("V04_BRIDGE_GITHUB_RESPONSE_INVALID")
    return data


def validated_owner_manuscript(
    issue_number: int, expected_sha256: str, token: str, *,
    get=_api,
) -> tuple[str, str]:
    """Verify the private-repo source, owner issue, UTF-8 body and exact SHA."""
    if (type(issue_number) is not int or issue_number < 1 or issue_number > 99999999
            or type(expected_sha256) is not str
            or SHA_PATTERN.fullmatch(expected_sha256) is None):
        raise ValueError("V04_BRIDGE_INPUT_INVALID")
    repo = get("GET", NEXT_API, token)
    if (repo.get("full_name") != NEXT_REPO
            or repo.get("private") is not True
            or repo.get("archived") is True):
        raise ValueError("V04_BRIDGE_PRIVATE_REPO_REQUIRED")
    issue = get("GET", f"{NEXT_API}/issues/{issue_number}", token)
    user = issue.get("user")
    if (issue.get("number") != issue_number
            or issue.get("state") != "open"
            or type(user) is not dict or user.get("login") != "trendhub-ab"
            or "pull_request" in issue
            or issue.get("title") != "AIIF V04 PRIVATE NOTE DRAFT SOURCE — Agent Skills"
            or type(issue.get("body")) is not str):
        raise ValueError("V04_BRIDGE_OWNER_ISSUE_REQUIRED")
    manuscript = issue["body"]
    if (not 1500 <= len(manuscript) <= 30000
            or sha256(manuscript.encode("utf-8")).hexdigest() != expected_sha256):
        raise ValueError("V04_BRIDGE_MANUSCRIPT_HASH_MISMATCH")
    first = manuscript.splitlines()[0]
    if not first.startswith("# ") or not first[2:].strip():
        raise ValueError("V04_BRIDGE_TITLE_INVALID")
    title = first[2:].strip()
    if (len(title) > 150
            or manuscript.count("\n# ") != 0
            or "### Sources / Evidence" not in manuscript):
        raise ValueError("V04_BRIDGE_MANUSCRIPT_CONTRACT_INVALID")
    return title, manuscript


def _write_ledger(path: Path, records: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, mode="w", encoding="utf-8",
        prefix=".v04-draft-", suffix=".json", delete=False,
    ) as stream:
        tmp = Path(stream.name)
        stream.write(json.dumps(records, sort_keys=True, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    tmp.chmod(0o600)
    os.replace(tmp, path)


def _draft_from_browser(
    title: str, manuscript: str, *, on_url,
) -> str:
    """Use existing persistent Chrome, exact note profile proof and note editor."""
    import note_draft_automation as base
    import run190_note_persistent_cloud as cloud
    import run189_note_editor_route_gate as route
    import run187_note_editor_readiness as readiness
    from playwright.sync_api import sync_playwright

    body_text = base._body_manuscript_for_note(title, manuscript)
    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)
            try:
                cloud._assert_expected_note_account(page)
            except base.NoteAuthenticationExpired as first_error:
                if not cloud._seed_note_state(context, page):
                    raise base.NoteAuthenticationExpired(
                        "note persistent Chrome identity not authenticated"
                    ) from first_error
                page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
                cloud._assert_expected_note_account(page)

            route._ensure_editor_route(page)
            if not readiness._is_editor_url(str(page.url or "")):
                raise base.NoteDraftError("V04_BRIDGE_NOTE_EDITOR_ROUTE_NOT_VERIFIED")
            title_field = base._set_title(page, title)
            body = base._find_body(page, title_field)
            base._paste_manuscript(page, body, body_text)
            body = base._find_body(page, title_field)
            base._verify_body_content(body, body_text)
            url = base._save_draft_and_verify(
                page, title, body_text, image_required=False,
                on_stable_draft_url=on_url,
            )
            cloud._verify_draft_in_article_list(page, url, title)
            return url
        finally:
            context.close()


def save_once(
    issue_number: int, expected_sha256: str, manuscript: str, title: str,
    *, runner=_draft_from_browser, ledger_path: Path = DRAFT_LEDGER,
) -> dict:
    """Durably reserve BEFORE note editor write; block crash-window retries."""
    import note_publication_reconcile as reconcile
    identity = f"{NEXT_REPO}#{issue_number}:{expected_sha256}"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ledger_path.with_suffix(".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ledger = json.loads(ledger_path.read_text("utf-8")) if ledger_path.exists() else {}
        if type(ledger) is not dict:
            raise ValueError("V04_BRIDGE_LEDGER_INVALID")
        prior = ledger.get(identity)
        if prior is not None:
            if (type(prior) is dict and prior.get("status") == "DRAFT_SAVED"
                    and prior.get("manuscript_sha256") == expected_sha256):
                return {"status": "ALREADY_SAVED", "draft_url": prior["draft_url"]}
            raise ValueError("V04_BRIDGE_AMBIGUOUS_PRIOR_ATTEMPT")
        ledger[identity] = {
            "status": "ATTEMPTING", "manuscript_sha256": expected_sha256,
            "issue_number": issue_number,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_ledger(ledger_path, ledger)

        def record_url(url: str):
            draft_id = reconcile.draft_identity_from_url(
                url, error_type=ValueError
            )
            if not draft_id:
                raise ValueError("V04_BRIDGE_DRAFT_ID_INVALID")
            ledger[identity]["draft_url"] = url
            ledger[identity]["status"] = "CREATED_PENDING_PERSISTENCE_PROOF"
            _write_ledger(ledger_path, ledger)

        result_url = runner(title, manuscript, on_url=record_url)
        if result_url != ledger[identity].get("draft_url"):
            raise ValueError("V04_BRIDGE_STABLE_DRAFT_URL_DRIFT")
        ledger[identity]["status"] = "DRAFT_SAVED"
        ledger[identity]["completed_at"] = datetime.now(timezone.utc).isoformat()
        _write_ledger(ledger_path, ledger)
        return {"status": "DRAFT_SAVED", "draft_url": result_url}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preflight", "create"), required=True)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    if args.confirm != CONFIRM:
        raise SystemExit("V04_BRIDGE_EXPLICIT_CONFIRM_REQUIRED")
    try:
        token = os.environ["GH_PAT"]
        title, manuscript = validated_owner_manuscript(
            args.issue_number, args.sha256, token
        )
        if args.mode == "preflight":
            print(json.dumps({
                "status": "V04_SINGLE_DRAFT_PREFLIGHT_PASS",
                "source_hash_verified": True, "note_writes": 0,
                "publication_approved": False, "gemini_calls": 0,
            }))
            return
        result = save_once(args.issue_number, args.sha256, manuscript, title)
        try:
            _api("POST", f"{NEXT_API}/issues/{args.issue_number}/comments",
                 token, {"body":
                 "AIIF note draft delivery: **" + result["status"] +
                 "**\n\nPrivate note edit URL: " + result["draft_url"] +
                 "\n\nPublic release: **not performed**."})
        except ValueError:
            # The persistent ledger still holds the verified note URL.
            print("V04_BRIDGE_PRIVATE_NOTICE_FAILED")
        print(json.dumps({
            "status": result["status"], "note_draft_created":
                result["status"] == "DRAFT_SAVED",
            "human_publication_required": True, "gemini_calls": 0,
            "public_release": False, "source_issue": args.issue_number,
        }))
    except SystemExit:
        raise
    except Exception:
        # Never log private manuscript, cookies, note URL, PAT or browser dumps.
        raise SystemExit("V04_NOTE_DRAFT_BRIDGE_FAILED_CLOSED") from None


if __name__ == "__main__":
    main()
