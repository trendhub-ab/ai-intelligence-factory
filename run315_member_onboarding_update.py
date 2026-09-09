#!/usr/bin/env python3
"""Run315: rewrite and re-associate the exact member onboarding note.

Authorized target: note n284e428c80f4 only.
The existing Run314 title/body SHA are hard preconditions. The update replaces the obsolete
Proposal/Digest-era onboarding copy with the current Run307 generic use-decision onboarding,
then restores the article as a free benefit of the `AI Intelligence Factory` membership.

ZERO Gemini/model calls. No Notion writes. No other note/account settings are changed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud
import run310_public_lp_update as run310

CONFIRM_TOKEN = "UPDATE_MEMBER_ONBOARDING_N284E428C80F4_SHA4826AABC"
TARGET_NOTE_ID = "n284e428c80f4"
TARGET_PUBLIC_URL = f"https://note.com/trendhub_biz/n/{TARGET_NOTE_ID}"
TARGET_EDITOR_URL = f"https://editor.note.com/notes/{TARGET_NOTE_ID}/edit/"
TARGET_PUBLISH_URL = f"https://editor.note.com/notes/{TARGET_NOTE_ID}/publish/"
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_UPDATE_RESULT_FILE"

AUDITED_TITLE = "【最初にお読みください】AI Decision Intelligenceの利用方法"
AUDITED_BODY_SHA256 = "4826aabc101f5f5319e2ea441e0e929ce2e7ee382be10a5fd0a976583c49c9f4"
NEW_TITLE = "【最初にお読みください】「このAI、使える！」を判断するための使い方"
MEMBERSHIP_NAME = "AI Intelligence Factory"
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeI8NavNVr-a7s0Etwehf8j7kbBy-TEJ5DwCzlq0yoVld4sCA/viewform?usp=publish-editor"
BRIEF_URL = "https://app.notion.com/p/3d0479ffdca981deb614fef528d2f32c"
DB_URL = "https://app.notion.com/p/b2787ee05b584ca7b4eb774f60237f1f?v=3d0479ffdca98111a529000cba6d89b5"
MEMO_URL = "https://app.notion.com/p/3d3479ffdca98119b0d8c014b068fe82"

MANUSCRIPT = f"""AI Intelligence Factoryへのご参加ありがとうございます。

この会員サービスは、AIニュースを大量に読むための場所ではありません。
新しいAIや技術を見つけたときに、**「結局、これは使えるのか？」を根拠付きで判断するためのサービス**です。

自分の開発、業務利用、ツール選定、必要に応じた提案まで、同じ考え方で使えます。

## まず最初に：Notion利用登録

AI Decision IntelligenceはNotion上で提供しています。
まず、会員専用ページを見るための利用登録をお願いします。

Notionアカウントをお持ちの方は、普段Notionで使用しているメールアドレスをご登録ください。
Notionアカウントをお持ちでない方は、無料アカウントを作成してから、そのメールアドレスを登録してください。
**閲覧のためにNotionの有料プランへ加入する必要はありません。**

登録フォームでは、次の3点をご入力ください。

- noteユーザー名
- note会員番号
- Notionで使用するメールアドレス

登録内容とnoteメンバーシップへの加入状況を確認後、会員専用Notionへご案内します。

[**Notion利用登録フォームを開く**]({FORM_URL})

## 会員向けで使うものは3つだけ

### 1｜Decision Brief

今見るべき重要な変化を先に確認する入口です。
単なるニュース一覧ではなく、**その変化で「使う・試す・待つ・避ける」の判断を変える必要があるか**を確認します。

[**Decision Briefを開く**]({BRIEF_URL})

### 2｜AI意思決定DB

気になるAI・技術を見つけたら、DBで詳しく確認します。

- いま、使える？
- 使える場面
- なぜ今見る？
- 使う前に確認すること
- 試す・導入する次の一手
- 確認に使った公式・一次情報

まで、判断に必要な情報をまとめています。

[**AI意思決定DBを開く**]({DB_URL})

### 3｜判断メモ

実際に試す・導入する前に、利用条件・主なリスク・小さく試す条件・次の判断を整理するためのメモです。
自分の開発や業務利用にも、必要に応じた提案にも使えます。

[**判断メモを開く**]({MEMO_URL})

## 4つの判断だけ覚えてください

- **ADOPT｜使う候補** — 利用条件が合えば、導入候補として検討できる
- **TEST｜小さく試す** — 本番利用の前に、近い条件で小さく検証する
- **WATCH｜待つ** — 現時点では採用を急がず、条件や成熟度の変化を追う
- **AVOID｜避ける** — 現時点では採用候補から外し、代替案を比較する

AIに詳しくなること自体が目的ではありません。
**「じゃあ、自分はどうする？」を早く決めるために使ってください。**

## 迷ったら、この順番

**新しいAIを知った** → Decision Brief  
**使えるか詳しく確認したい** → AI意思決定DB  
**実際に試す・導入したい** → 判断メモ

全部を毎日読む必要はありません。
判断が必要になったときに戻ってくれば大丈夫です。

## 利用環境

**PCでの利用を推奨しています。**
スマートフォン向けには簡易ビューがあります。

## 会員資格が終了した場合

noteメンバーシップの会員資格が終了した時点で、AI Decision Intelligenceの会員向けアクセスも終了します。
再加入された場合は、あらためてアクセスをご案内します。

## 最初の一歩

まずNotion利用登録を済ませ、Decision Briefから気になる1件だけ選び、AI意思決定DBで確認してみてください。

**「情報を追う」のではなく、「このAI、使える？」を判断する。**
それが、この会員サービスの基本的な使い方です。"""

REQUIRED_MARKERS = (
    "このAI、使える？",
    "Decision Brief",
    "AI意思決定DB",
    "判断メモ",
    "ADOPT｜使う候補",
    "PCでの利用を推奨",
    "Notion利用登録フォームを開く",
)
FORBIDDEN_OLD_MARKERS = (
    "会員向けDigest",
    "Short Rationale",
    "Main Risk",
    "Best For / Avoid For",
    "実際に仕事で使える成熟度",
)


def _field_text(locator: Any) -> str:
    return run310._field_text(locator)


def _body_text(body: Any) -> str:
    try:
        return str(body.inner_text(timeout=10000) or "").strip()
    except Exception as exc:
        raise base.NoteDraftError("Run315 could not read current onboarding body") from exc


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_exact_editor(url: str) -> bool:
    return str(url or "").startswith("https://editor.note.com/") and TARGET_NOTE_ID in str(url) and "/edit" in str(url)


def _open_editor(context: Any, page: Any) -> None:
    page.goto(TARGET_EDITOR_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1400)
    if not _is_exact_editor(str(page.url or "")):
        seeded = cloud._seed_note_state(context, page)
        if seeded:
            page.goto(TARGET_EDITOR_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1400)
    if not _is_exact_editor(str(page.url or "")):
        raise base.NoteAuthenticationExpired("Run315 could not reach exact onboarding editor")


def _membership_add_button(page: Any) -> Any:
    buttons = page.locator("button:visible")
    matches: list[int] = []
    for idx in range(buttons.count()):
        button = buttons.nth(idx)
        try:
            text = " ".join(str(button.inner_text() or "").split())
        except Exception:
            continue
        if text != "追加":
            continue
        context_text = button.evaluate(
            """el => {
              let cur = el;
              for (let i=0; i<8 && cur; i++, cur=cur.parentElement) {
                const t = String(cur.innerText || '').replace(/\\s+/g, ' ').trim();
                if (t.includes('AI Intelligence Factory') && t.includes('メンバーシップ')) return t.slice(0,1200);
              }
              return '';
            }"""
        )
        if MEMBERSHIP_NAME in str(context_text or "") and "メンバーシップ" in str(context_text or ""):
            matches.append(idx)
    if len(matches) != 1:
        raise base.NoteDraftError(f"Run315 expected one membership 追加 button; got {len(matches)}")
    return buttons.nth(matches[0])


def _membership_visible_state(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """(membershipName) => {
          const visible = (el) => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
          };
          const buttons = Array.from(document.querySelectorAll('button')).filter(visible);
          const rows = [];
          for (const b of buttons) {
            let cur = b;
            for (let i=0; i<8 && cur; i++, cur=cur.parentElement) {
              const t = String(cur.innerText || '').replace(/\\s+/g,' ').trim();
              if (t.includes(membershipName) && t.includes('メンバーシップ')) {
                rows.push({button:String(b.innerText||'').replace(/\\s+/g,' ').trim(), context:t.slice(0,1200)});
                break;
              }
            }
          }
          return {rows};
        }""",
        MEMBERSHIP_NAME,
    )


def _choose_all_members_if_prompted(page: Any) -> bool:
    # note may open a scope selector after membership is added. Choose an all-members option only
    # when exactly one visible, exact option is observed. Otherwise leave the direct-add state alone.
    for label in ("すべてのメンバー", "全メンバー", "メンバー全員"):
        candidates = page.get_by_text(label, exact=True)
        visible = []
        for idx in range(candidates.count()):
            item = candidates.nth(idx)
            try:
                if item.is_visible():
                    visible.append(item)
            except Exception:
                pass
        if len(visible) == 1:
            visible[0].click()
            page.wait_for_timeout(600)
            # Some variants require a modal-local confirmation.
            for confirm_text in ("追加する", "決定", "完了"):
                buttons = page.locator("button:visible").filter(has_text=confirm_text)
                exact = []
                for idx in range(buttons.count()):
                    try:
                        if " ".join(str(buttons.nth(idx).inner_text() or "").split()) == confirm_text:
                            exact.append(buttons.nth(idx))
                    except Exception:
                        pass
                if len(exact) == 1:
                    exact[0].click()
                    page.wait_for_timeout(700)
                    break
            return True
    return False


def _ensure_membership_selected(page: Any) -> dict[str, Any]:
    before = _membership_visible_state(page)
    # The Run314 live audit showed the target membership with an exact visible `追加` control.
    try:
        add_button = _membership_add_button(page)
    except base.NoteDraftError:
        # Idempotent path: accept only a visible state that explicitly indicates membership association.
        text = " ".join(str(page.locator("body").inner_text(timeout=10000) or "").split())
        if MEMBERSHIP_NAME in text and any(marker in text for marker in ("追加済み", "削除", "メンバー全員", "すべてのメンバー")):
            return {"changed": False, "before": before, "scope_prompt_used": False}
        raise

    add_button.click()
    page.wait_for_timeout(900)
    scope_prompt_used = _choose_all_members_if_prompted(page)
    page.wait_for_timeout(500)
    after = _membership_visible_state(page)

    # Fail closed if the same target still exposes the exact Add control.
    try:
        _membership_add_button(page)
    except base.NoteDraftError:
        pass
    else:
        raise base.NoteDraftError("Run315 membership association did not leave the audited Add state")

    text = " ".join(str(page.locator("body").inner_text(timeout=10000) or "").split())
    if MEMBERSHIP_NAME not in text:
        raise base.NoteDraftError("Run315 membership name disappeared after association")
    return {"changed": True, "before": before, "after": after, "scope_prompt_used": scope_prompt_used}


def _verify_editor(body: Any) -> None:
    current = _body_text(body)
    for marker in REQUIRED_MARKERS:
        if marker not in current:
            raise base.NoteDraftError(f"Run315 rewritten onboarding missing marker: {marker}")
    for marker in FORBIDDEN_OLD_MARKERS:
        if marker in current:
            raise base.NoteDraftError(f"Run315 obsolete onboarding marker remains: {marker}")
    for url in (FORM_URL, BRIEF_URL, DB_URL, MEMO_URL):
        if body.locator(f'a[href="{url}"]').count() < 1:
            raise base.NoteDraftError(f"Run315 expected link missing from editor: {url}")


def _verify_public(page: Any) -> dict[str, Any]:
    page.goto(TARGET_PUBLIC_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1700)
    full = " ".join(str(page.locator("body").inner_text(timeout=10000) or "").split())
    if "この記事は現在販売されていません" in full or "この記事は現在販売していません" in full:
        raise base.NoteDraftError("Run315 public page still reports not-for-sale state")
    if NEW_TITLE not in full:
        raise base.NoteDraftError("Run315 public page does not expose the new onboarding title")
    return {"public_url": TARGET_PUBLIC_URL, "not_for_sale_removed": True, "new_title_verified": True}


def update() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_UPDATE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run315 exact onboarding update confirmation is missing or invalid")

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run315") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            _open_editor(context, page)
            title_field = base._find_title(page)
            current_title = _field_text(title_field)
            body = base._find_body(page, title_field)
            current_body = _body_text(body)
            staged_current = False

            if current_title == AUDITED_TITLE:
                if _sha256(current_body) != AUDITED_BODY_SHA256:
                    raise base.NoteDraftError("Run315 refuses onboarding body drift from Run314 audited SHA")
                title_field = base._set_title(page, NEW_TITLE)
                if _field_text(title_field) != NEW_TITLE:
                    raise base.NoteDraftError("Run315 new title did not persist in editor")
                body = base._find_body(page, title_field)
                base._paste_manuscript(page, body, MANUSCRIPT)
                base._verify_body_content(body, MANUSCRIPT)
                _verify_editor(body)
                page.wait_for_timeout(1200)
            elif current_title == NEW_TITLE:
                # note may have autosaved a prior staged rewrite; only continue if it matches the authorized copy.
                _verify_editor(body)
                staged_current = True
            else:
                raise base.NoteDraftError(f"Run315 refuses unexpected onboarding title: {current_title!r}")

            run310._unique_button(page, "公開に進む").click()
            try:
                page.wait_for_url(f"**/notes/{TARGET_NOTE_ID}/publish/**", timeout=15000)
            except PlaywrightTimeoutError as exc:
                raise base.NoteDraftError("Run315 did not reach exact onboarding publish settings") from exc
            if not str(page.url or "").startswith(TARGET_PUBLISH_URL):
                raise base.NoteDraftError("Run315 publish settings URL is not the exact onboarding note")
            page.wait_for_timeout(900)

            settings_text = "\n".join(str(page.locator("body").inner_text(timeout=10000) or "").splitlines())
            if "記事タイプ" not in settings_text or "無料" not in settings_text or MEMBERSHIP_NAME not in settings_text:
                raise base.NoteDraftError("Run315 publish settings no longer match the audited free membership article surface")

            membership = _ensure_membership_selected(page)
            page.wait_for_timeout(600)
            run310._unique_button(page, "更新する").click()
            page.wait_for_timeout(2300)

            verification = _verify_public(page)
            return {
                "status": "updated_and_verified",
                "target_note_id": TARGET_NOTE_ID,
                "public_mutation": True,
                "zero_gemini_calls": True,
                "title": NEW_TITLE,
                "source_body_sha256": AUDITED_BODY_SHA256,
                "staged_current": staged_current,
                "membership": membership,
                **verification,
            }
        finally:
            context.close()


def main() -> None:
    result = update()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN315_MEMBER_ONBOARDING_UPDATE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
