"""Private Telegram-keyed Fernet artifact handoff for P5, GitHub Actions only.

Runs AFTER explicitly opted-in manual P5 run. Never publish raw P5 drafts to
GitHub/Actions artifacts/logs or a Telegram channel/group. Telegram receives
only the random one-time decryption key, and only if the bot chat is private.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
import zipfile

from cryptography.fernet import Fernet

FILES = ("manifest.json", "KEY_OPEN_AFTER_SCORING.json")


class ConfidentialHandoffError(RuntimeError):
    pass


def _telegram_request(token: str, method: str, fields: dict[str, str]) -> dict:
    if not token or not token.replace(":", "").replace("-", "").replace("_", "").isalnum():
        raise ConfidentialHandoffError("Invalid Telegram credentials")
    endpoint = "https://api.telegram.org/bot" + token + "/" + method
    body = urllib.parse.urlencode(fields).encode("utf-8")
    try:
        request = urllib.request.Request(endpoint, data=body, method="POST")
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception:
        # Never leak the Telegram bot token through urllib HTTP error URL.
        raise ConfidentialHandoffError("Telegram delivery or verification unavailable") from None
    if result.get("ok") is not True:
        raise ConfidentialHandoffError("Telegram delivery was not accepted")
    return result.get("result") or {}


def assert_private_chat(token: str, chat_id: str) -> None:
    if not token or not chat_id:
        raise ConfidentialHandoffError("Telegram bot token and recipient are required")
    result = _telegram_request(token, "getChat", {"chat_id": chat_id})
    if result.get("type") != "private":
        raise ConfidentialHandoffError("Refusing group, channel or unknown Telegram recipient")
    if str(result.get("id")) != str(chat_id):
        raise ConfidentialHandoffError("Telegram private recipient ID mismatch")


def _private_files(root: Path) -> list[Path]:
    if not root.is_dir() or root.is_symlink():
        raise ConfidentialHandoffError("No private writer directory")
    required = [root / name for name in FILES]
    if any(not f.is_file() or f.is_symlink() for f in required):
        raise ConfidentialHandoffError("Missing or redirected P5 manifest/blind key")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "ALL_VALID_AWAITING_BLIND_HUMAN_REVIEW":
        raise ConfidentialHandoffError("P5 manuscript set incomplete, no artifact permitted")
    count = len(manifest.get("arms") or [])
    if count not in (4, 5) or manifest.get("gemini_requests") != count:
        raise ConfidentialHandoffError("P5 manuscript count/request count inconsistent")
    articles = sorted(root.glob("Candidate_*.md"))
    stages = sorted(root.glob("Stages_Candidate_*.json"))
    if len(articles) != count or len(stages) != count:
        raise ConfidentialHandoffError("Incomplete P5 article/stage archive")
    expected = {f.name for f in [*required, *articles, *stages]}
    actual = {x.name for x in root.iterdir()}
    if actual != expected or any(f.is_symlink() or not f.is_file() for f in [*articles, *stages]):
        raise ConfidentialHandoffError("Unapproved file in confidential P5 archive")
    return [*articles, *stages, *required]


def encrypt_and_deliver(
    source: Path, destination: Path, *,
    token: str, chat_id: str, run_id: str,
) -> None:
    assert_private_chat(token, chat_id)
    files = _private_files(source)
    if destination.exists() or destination.is_symlink():
        raise ConfidentialHandoffError("Encrypted artifact destination already exists")
    if source.resolve() == destination.resolve().parent:
        raise ConfidentialHandoffError("Encrypted artifact cannot be mixed with raw inputs")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for file in files:
            z.writestr(file.name, file.read_bytes())
    key = Fernet.generate_key()
    ciphertext = Fernet(key).encrypt(archive.getvalue())
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(ciphertext)
        message = (
            "AIIF P5 比較実験の復号鍵（暗号化成果物と別経路）\\n"
            "GitHub Actions Run: " + str(run_id) + "\\n"
            "Fernet key: " + key.decode("ascii") + "\\n"
            "この鍵は第三者に共有しないでください。"
        )
        _telegram_request(token, "sendMessage", {"chat_id": chat_id, "text": message})
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    print("P5_ENCRYPTED_HANDOFF_READY; private Telegram delivered; no plaintext artifact")


def main() -> None:
    if os.getenv("GITHUB_ACTIONS") != "true":
        raise ConfidentialHandoffError("Confidential handoff requires explicit Actions environment")
    if os.getenv("GITHUB_EVENT_NAME") != "workflow_dispatch":
        raise ConfidentialHandoffError("Only manual dispatch may deliver")
    if os.getenv("GITHUB_RUN_ATTEMPT") != "1":
        raise ConfidentialHandoffError("Reruns are prohibited")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat = os.getenv("TELEGRAM_CHAT_ID", "")
    assert_private_chat(token, chat)
    if os.getenv("AIIF_P5_HANDOFF_STAGE") == "preflight":
        print("P5_HANDOFF_PREFLIGHT_PASS_PRIVATE_CHAT; no Gemini calls")
        return
    if os.getenv("AIIF_P5_HANDOFF_STAGE") != "seal":
        raise ConfidentialHandoffError("Unknown P5 handoff stage")
    private = os.getenv("AIIF_P5_PRIVATE_DIRECTORY")
    artifact = os.getenv("AIIF_P5_ENCRYPTED_ARTIFACT")
    if not private or not artifact:
        raise ConfidentialHandoffError("Missing encrypted/private path")
    encrypt_and_deliver(
        Path(private), Path(artifact),
        token=token, chat_id=chat, run_id=os.getenv("GITHUB_RUN_ID", ""),
    )


if __name__ == "__main__":
    main()
