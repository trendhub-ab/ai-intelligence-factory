"""
================================================================================
AI note事業：Notion DB蓄積データ -> note自動投稿スクリプト (notion_to_note.py)
================================================================================
"""

import os
import re
import time
import requests
import logging
from google import genai
from google.genai.errors import APIError
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("note_publisher")

NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NOTE_EMAIL = os.environ.get("NOTE_EMAIL")
NOTE_PASSWORD = os.environ.get("NOTE_PASSWORD")

if not GEMINI_API_KEY:
    raise ValueError("エラー: GEMINI_API_KEY が設定されていません。")

client = genai.Client(api_key=GEMINI_API_KEY)

CANDIDATE_MODELS = os.environ.get(
    "GEMINI_MODEL_CANDIDATES",
    "gemini-3.1-flash-lite,gemini-3.5-flash"
).split(",")

# ==========================================
# 1. モデル解決 & スマートリトライ
# ==========================================
class NoAvailableModelError(RuntimeError): pass
class DailyQuotaExhaustedError(RuntimeError): pass

PING_MAX_RETRIES = 3
PING_RETRY_BACKOFF_SECONDS = 12

def _is_daily_quota_exhausted(exc: Exception) -> bool:
    text = str(exc)
    return "free_tier_requests" in text or "PerDay" in text or "Quota exceeded" in text

def _extract_retry_delay(exc: Exception, default: int = 20) -> int:
    match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+)", str(exc))
    return int(match.group(1)) if match else default

def resolve_model(candidates: list[str] = CANDIDATE_MODELS) -> str:
    last_error: Exception | None = None
    for model_name in candidates:
        model_name = model_name.strip()
        for attempt in range(PING_MAX_RETRIES + 1):
            try:
                client.models.generate_content(
                    model=model_name,
                    contents="ping",
                    config={"max_output_tokens": 8},
                )
                logger.info(f"モデル解決成功: {model_name}")
                return model_name
            except APIError as e:
                last_error = e
                if e.code == 404:
                    logger.warning(f"モデル利用不可(404)のため次候補へフォールバック: {model_name}")
                    break
                if e.code == 429 and _is_daily_quota_exhausted(e):
                    logger.warning(f"日次クォータ枯渇(429)のため次候補へフォールバック: {model_name}")
                    break
                if e.code in (503, 429):
                    if attempt < PING_MAX_RETRIES:
                        wait = PING_RETRY_BACKOFF_SECONDS * (attempt + 1)
                        logger.warning(
                            f"モデル疎通確認中に一時的なエラー(code={e.code}): {model_name} "
                            f"{wait}秒待機してリトライ ({attempt + 1}/{PING_MAX_RETRIES})"
                        )
                        time.sleep(wait)
                        continue
                    logger.error(f"{model_name}: リトライ上限({PING_MAX_RETRIES}回)到達。次候補へフォールバック")
                    break
                logger.error(f"モデル疎通確認中に想定外のAPIエラー(code={e.code}): {model_name}")
                raise NoAvailableModelError(f"想定外のAPIエラー(code={e.code})のため中断しました") from e
            except Exception as e:
                last_error = e
                raise NoAvailableModelError(f"想定外の例外のため中断しました") from e

    raise NoAvailableModelError(f"利用可能なモデルがありませんでした: {candidates}") from last_error

try:
    SELECTED_MODEL = resolve_model()
except NoAvailableModelError as e:
    logger.error(f"⚠️ Geminiモデル初期化失敗: {e}")
    raise SystemExit(1)

def call_gemini_with_smart_retry(prompt: str, max_retries: int = 5):
    for attempt in range(max_retries + 1):
        try:
            time.sleep(3)
            return client.models.generate_content(model=SELECTED_MODEL, contents=prompt)
        except APIError as e:
            if e.code == 503:
                if attempt < max_retries:
                    wait = 15 * (attempt + 1)
                    logger.warning(f"503(サーバー混雑)発生。{wait}秒待機してリトライ ({attempt + 1}/{max_retries})")
                    time.sleep(wait)
                    continue
                raise
            elif e.code == 429:
                if _is_daily_quota_exhausted(e):
                    raise DailyQuotaExhaustedError(str(e)) from e
                delay = _extract_retry_delay(e)
                if attempt < max_retries:
                    logger.warning(f"429(RPM)発生。指定のretryDelay={delay}秒待機してリトライ")
                    time.sleep(delay)
                    continue
                raise
            else:
                raise

# ==========================================
# 2. Notionから「未投稿」レポートを取得 & ステータス更新
# ==========================================
def fetch_unpublished_reports():
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        logger.error("NOTION_API_KEY または NOTION_DATABASE_ID が未設定です。")
        return []

    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    payload = {
        "filter": {
            "and": [
                {"property": "Decision Score", "number": {"greater_than_or_equal_to": 75}},
                {"property": "Status", "select": {"does_not_equal": "Published"}}
            ]
        },
        "page_size": 3
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code != 200:
            logger.warning("Status列が存在しないためスコアのみで抽出します。")
            payload = {
                "filter": {"property": "Decision Score", "number": {"greater_than_or_equal_to": 75}},
                "page_size": 3
            }
            res = requests.post(url, json=payload, headers=headers, timeout=10)

        results = res.json().get("results", [])
        reports = []
        for page in results:
            props = page["properties"]
            
            def get_text(prop_name):
                val = props.get(prop_name, {}).get("rich_text", [])
                return val[0]["text"]["content"] if val else ""

            title_val = props.get("Name", {}).get("title", [])
            title = title_val[0]["text"]["content"] if title_val else "無題"

            reports.append({
                "page_id": page["id"],
                "title": title,
                "url": props.get("URL", {}).get("url", ""),
                "score": props.get("Decision Score", {}).get("number", 0),
                "what": get_text("What"),
                "why_important": get_text("Why Important"),
                "why_not_important": get_text("Why NOT Important"),
                "action": get_text("Action")
            })
        return reports
    except Exception as e:
        logger.error(f"Notion通信エラー: {e}")
        return []

def mark_as_published(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    payload = {
        "properties": {
            "Status": {"select": {"name": "Published"}}
        }
    }
    try:
        requests.patch(url, json=payload, headers=headers, timeout=10)
        logger.info(f"[NOTION STATUS UPDATED] Page ID: {page_id} -> Published")
    except Exception as e:
        logger.error(f"Notionステータス更新失敗: {e}")

# ==========================================
# 3. note有料記事フォーマット生成
# ==========================================
def format_for_note(report):
    prompt = f"""
あなたは月刊数十万円を売り上げる技術系noteのトップWebライター・編集者です。
以下のレポートデータを元に、読者（エンジニア・PM）が思わずクリックして購入したくなる「note有料記事」の原稿を作成してください。

【元データ】
- タイトル/リポジトリ: {report['title']}
- 意思決定スコア: {report['score']}点
- What: {report['what']}
- Why Important: {report['why_important']}
- Why NOT Important: {report['why_not_important']}
- Action: {report['action']}

【出力構造ルール（厳守）】
1. 1行目: 読者の目を引くキャッチーな記事タイトル（【2026年最新】等のトレンド感を含める）
2. 無料表示エリア:
   - 記事の背景・要約（What）
   - なぜ今、日本のAI現場で重要なのか（Why Importantの冒頭）
   - 「---有料エリア---」という境界線テキストを入れる
3. 有料表示エリア:
   - 今すぐ導入・監視すべき理由（Why Important詳細）
   - スルーしてよい企業・チームの特徴（Why NOT Important）
   - 明日から現場で取るべきアクション（Action）
"""
    response = call_gemini_with_smart_retry(prompt)
    return response.text

# ==========================================
# 4. Playwrightによるnote自動下書き保存（究極の堅牢化）
# ==========================================
def post_to_note_via_playwright(article_text):
    lines = article_text.strip().split("\n")
    title = lines[0].replace("#", "").strip()
    body = "\n".join(lines[1:])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        logger.info("noteへログイン処理を開始...")
        page.goto("https://note.com/login", wait_until="domcontentloaded") # networkidleより早く次の処理へ
        
        email_selector = 'input[type="email"], input[name="login"], input[name="email"], input[placeholder*="メール"]'
        page.wait_for_selector(email_selector, timeout=30000)
        page.locator(email_selector).first.fill(NOTE_EMAIL)

        password_selector = 'input[type="password"], input[name="password"]'
        page.locator(password_selector).first.fill(NOTE_PASSWORD)

        submit_button = 'button[type="submit"], button:has-text("ログイン")'
        page.locator(submit_button).first.click()
        page.wait_for_timeout(5000)

        logger.info("エディタ画面へ移動して記事を書き込み...")
        page.goto("https://note.com/notes/new", wait_until="domcontentloaded")
        page.wait_for_timeout(3000) # エディタの非同期JS読み込みを確実に待つ
        
        # 修正: タイトル入力（複数パターンの冗長化 ＋ 見つからなければ最初のtextareaを指定）
        title_selector = 'textarea[placeholder*="タイトル"], [aria-label*="タイトル"], textarea'
        page.wait_for_selector(title_selector, timeout=30000)
        page.locator(title_selector).first.fill(title)

        # 修正: 本文入力（複数パターンの冗長化）
        body_selector = 'div[data-placeholder*="本文"], div[role="textbox"], .ProseMirror, [contenteditable="true"]'
        page.wait_for_selector(body_selector, timeout=30000)
        page.locator(body_selector).first.click()
        page.keyboard.type(body, delay=10)

        # 修正: 保存ボタン（複数パターンの冗長化）
        save_button = 'button:has-text("下書き保存"), button:has-text("保存")'
        page.wait_for_selector(save_button, timeout=30000)
        page.locator(save_button).first.click()
        page.wait_for_timeout(3000)
        
        logger.info(f"[SUCCESS] note下書き作成完了: {title}")
        browser.close()

# ==========================================
# 5. メイン実行
# ==========================================
def main():
    logger.info("=== note自動投稿パイプライン起動 ===")
    reports = fetch_unpublished_reports()
    logger.info(f"投稿対象未処理レポート: {len(reports)} 件")

    for report in reports:
        logger.info(f"整形中: {report['title']}")
        try:
            note_article = format_for_note(report)
            if NOTE_EMAIL and NOTE_PASSWORD:
                post_to_note_via_playwright(note_article)
                mark_as_published(report["page_id"])
            else:
                logger.info("NOTE_EMAIL / NOTE_PASSWORD 未設定のためログ出力のみ行います:")
                print("\n" + "="*40 + "\n" + note_article + "\n" + "="*40)
        except DailyQuotaExhaustedError:
            logger.error("日次クォータ枯渇のため処理を中断します。")
            break
        except Exception as e:
            logger.error(f"記事生成・投稿中にエラー発生 ({report['title']}): {e}")
            continue

if __name__ == "__main__":
    main()
