"""One-off manual v0.4 note DRAFT bridge, isolated from retired V1 Daily.

The manuscript is read from one trusted-owner issue in the PRIVATE Next repo
using GH_PAT. This public repository does not store the article. Only the
existing note.com UI is used; no private note API or public release actions.
A persistent fail-closed ledger prevents duplicate drafts on repeat dispatch.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import fcntl
from hashlib import sha256
import json
import os
import shutil
import sqlite3
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

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

    # The old note production browser path explicitly installed these UI/DOM
    # selectors and persistence guards. The isolated bridge must not bypass them.
    cloud.install()
    print("V04_NOTE_STAGE=BROWSER_SETUP", flush=True)
    body_text = base._body_manuscript_for_note(title, manuscript)
    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        print("V04_NOTE_STAGE=BROWSER_LAUNCHED", flush=True)
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

            print("V04_NOTE_STAGE=ACCOUNT_VERIFIED", flush=True)
            route._ensure_editor_route(page)
            if not readiness._is_editor_url(str(page.url or "")):
                raise base.NoteDraftError("V04_BRIDGE_NOTE_EDITOR_ROUTE_NOT_VERIFIED")
            print("V04_NOTE_STAGE=EDITOR_READY", flush=True)
            title_field = base._set_title(page, title)
            print("V04_NOTE_STAGE=TITLE_INSERTED", flush=True)
            body = base._find_body(page, title_field)
            base._paste_manuscript(page, body, body_text)
            body = base._find_body(page, title_field)
            base._verify_body_content(body, body_text)
            print("V04_NOTE_STAGE=BODY_VERIFIED", flush=True)
            url = base._save_draft_and_verify(
                page, title, body_text, image_required=False,
                on_stable_draft_url=on_url,
            )
            print("V04_NOTE_STAGE=PERSISTED_DOCUMENT_VERIFIED", flush=True)
            cloud._verify_draft_in_article_list(page, url, title)
            print("V04_NOTE_STAGE=ARTICLE_LIST_CONFIRMED", flush=True)
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




def _historical_editor_navigation(started_at: str | None) -> str:
    """Categorize *local* Chrome History near the failed attempt; no URLs emitted.

    Chrome history is supporting evidence only: visits may be missing, and an
    editor visit never proves that note persisted a draft. Not used to unblock
    the ATTEMPTING ledger or authorize any write.
    """
    if not started_at:
        return "NO_ATTEMPT_TIMESTAMP"
    try:
        began = datetime.fromisoformat(started_at)
        if began.tzinfo is None:
            return "HISTORY_UNAVAILABLE"
        lower = began.astimezone(timezone.utc) - timedelta(seconds=90)
        upper = began.astimezone(timezone.utc) + timedelta(minutes=4)
        epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
        lo = int((lower - epoch).total_seconds() * 1000000)
        hi = int((upper - epoch).total_seconds() * 1000000)
        import run190_note_persistent_cloud as cloud
        paths = sorted(
            p for p in cloud._profile_dir().rglob("History")
            if p.is_file() and p.stat().st_size < 100_000_000
        )[:12]
        inspected = False
        types: set[str] = set()
        with tempfile.TemporaryDirectory(prefix="v04-history-readonly-") as temp:
            for i, source in enumerate(paths):
                copied = Path(temp) / f"History-{i}.sqlite"
                try:
                    shutil.copy2(source, copied)
                    db = sqlite3.connect(f"file:{copied}?mode=ro", uri=True)
                    try:
                        rows = db.execute(
                            "SELECT u.url FROM visits v JOIN urls u ON u.id=v.url "
                            "WHERE v.visit_time BETWEEN ? AND ? LIMIT 1024",
                            (lo, hi),
                        ).fetchall()
                        inspected = True
                    finally:
                        db.close()
                except (OSError, sqlite3.Error):
                    continue
                for (raw_url,) in rows:
                    target = urlsplit(str(raw_url))
                    if (target.scheme != "https" or target.hostname not in
                            {"note.com", "editor.note.com"}):
                        continue
                    path = target.path.rstrip("/")
                    if path in {"/notes/new", "/new"}:
                        types.add("NEW")
                    elif re.fullmatch(r"/notes/[^/]+/edit", path):
                        types.add("EDIT")
        if not inspected:
            return "HISTORY_UNAVAILABLE"
        if types == {"NEW", "EDIT"}:
            return "NEW_AND_EDIT_ROUTES_VISITED"
        if types == {"EDIT"}:
            return "EDIT_ROUTE_VISITED"
        if types == {"NEW"}:
            return "NEW_ROUTE_VISITED"
        return "NO_EDITOR_NAVIGATION_SEEN"
    except Exception:
        # Never leak file paths, profile contents, URLs or browser exceptions.
        return "HISTORY_UNAVAILABLE"



def _read_only_browser_probe(title: str) -> dict:
    """Observe existing note account and article list; never enter an editor or write."""
    try:
        import note_draft_automation as base
        import run190_note_persistent_cloud as cloud
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            context = cloud._launch_persistent_context(playwright)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(12000)
                try:
                    cloud._assert_expected_note_account(page)
                except (base.NoteAuthenticationExpired, base.NoteDraftError):
                    return {"note_account": "NOT_VERIFIED", "matching_title": "NOT_CHECKED"}
                page.goto("https://note.com/notes", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1300)
                if (str(page.url or "").split("?")[0].rstrip("/") !=
                        "https://note.com/notes" or base._looks_logged_out(page)):
                    return {"note_account": "VERIFIED", "matching_title": "LIST_NOT_VERIFIED"}
                count = page.get_by_role(
                    "button", name=f"{title}を編集", exact=True
                ).count()
                # Matching a title is only a hint, not proof of exact manuscript or saved draft.
                return {
                    "note_account": "VERIFIED",
                    "matching_title": "NONE_VISIBLE" if count == 0 else
                        ("ONE_VISIBLE" if count == 1 else "MULTIPLE_VISIBLE"),
                }
            finally:
                context.close()
    except Exception:
        # Never expose browser errors, cookies, identifiers or title through Actions logs.
        return {"note_account": "BROWSER_UNAVAILABLE", "matching_title": "NOT_CHECKED"}


def inspect_existing_attempt(
    issue_number: int, expected_sha256: str, title: str,
    *, ledger_path: Path = DRAFT_LEDGER, browser_probe=_read_only_browser_probe,
    history_probe=_historical_editor_navigation,
) -> dict:
    """Read-only reconciliation; never clears the ledger or authorizes a retry."""
    if (type(issue_number) is not int or issue_number < 1
            or type(expected_sha256) is not str
            or SHA_PATTERN.fullmatch(expected_sha256) is None
            or type(title) is not str or not title):
        raise ValueError("V04_BRIDGE_INSPECT_INPUT_INVALID")
    identity = f"{NEXT_REPO}#{issue_number}:{expected_sha256}"
    if ledger_path.exists():
        data = json.loads(ledger_path.read_text("utf-8"))
        if type(data) is not dict:
            raise ValueError("V04_BRIDGE_INSPECT_LEDGER_INVALID")
        record = data.get(identity)
    else:
        record = None
    if record is not None and (
        type(record) is not dict
        or record.get("status") not in (
            "ATTEMPTING", "CREATED_PENDING_PERSISTENCE_PROOF", "DRAFT_SAVED"
        )
        or record.get("manuscript_sha256") != expected_sha256
        or record.get("issue_number") != issue_number
    ):
        raise ValueError("V04_BRIDGE_INSPECT_LEDGER_INVALID")
    evidence = {
        "status": "READ_ONLY_INSPECTION_COMPLETE",
        "ledger": record["status"] if record is not None else "NO_RECORD",
        "stable_draft_url_recorded": bool(record and record.get("draft_url")),
        "publication_approved": False,
        "note_mutations": 0,
        "gemini_calls": 0,
        "automatic_retry_allowed": False,
    }
    probe = browser_probe(title)
    if (type(probe) is not dict
        or probe.get("note_account") not in (
            "VERIFIED", "NOT_VERIFIED", "BROWSER_UNAVAILABLE"
        )
        or probe.get("matching_title") not in (
            "NOT_CHECKED", "LIST_NOT_VERIFIED", "NONE_VISIBLE",
            "ONE_VISIBLE", "MULTIPLE_VISIBLE"
        )):
        raise ValueError("V04_BRIDGE_INSPECT_PROBE_INVALID")
    evidence.update(probe)
    history = history_probe(record.get("started_at") if record else None)
    if history not in {
        "NO_ATTEMPT_TIMESTAMP", "HISTORY_UNAVAILABLE",
        "NEW_AND_EDIT_ROUTES_VISITED", "EDIT_ROUTE_VISITED",
        "NEW_ROUTE_VISITED", "NO_EDITOR_NAVIGATION_SEEN",
    }:
        raise ValueError("V04_BRIDGE_INSPECT_HISTORY_INVALID")
    evidence["historical_editor_navigation"] = history
    return evidence



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preflight", "create", "inspect"), required=True)
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
        if args.mode == "inspect":
            print(json.dumps(inspect_existing_attempt(
                args.issue_number, args.sha256, title
            ), ensure_ascii=False, sort_keys=True))
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
