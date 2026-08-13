"""
================================================================================
AI note事業：Notion DB蓄積データ -> note自動投稿スクリプト (notion_to_note.py)
================================================================================
目的: Notionに溜まった高スコアのレポートを抽出し、noteの有料記事フォーマットに
      自動整形してnote（下書き）へ投稿する。
================================================================================
"""

import os
import time
import requests
import logging
from google import genai
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("note_publisher")

# 1. 環境変数
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NOTE_EMAIL = os.environ.get("NOTE_EMAIL")
NOTE_PASSWORD = os.environ.get("NOTE_PASSWORD")

client = genai.Client(api_key=GEMINI_API_KEY)

# 2. Notionから「Notionに保存済みの未投稿データ」を取得
def fetch_unpublished_reports():
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    # スコア80点以上の優良記事を優先取得するフィルター（ROI最大化）
    payload = {
        "filter": {
            "property": "Decision Score",
            "number": {"greater_than_or_equal_to": 75}
        },
        "page_size": 3
    }
    res = requests.post(url, json=payload, headers=headers)
    if res.status_code != 200:
        logger.error(f"Notion取得失敗: {res.text}")
        return []

    results = res.json().get("results", [])
    reports = []
    for page in results:
        props = page["properties"]
        
        # 安全なテキスト抽出ヘルパー
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

# 3. Geminiによる「note有料記事用フォーマット」への再整形
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
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt
    )
    return response.text

# 4. Playwrightによるnote自動下書き保存（自動化エンジン）
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
        page.goto("https://note.com/login", wait_until="networkidle")
        
        # 1. ログインID / メールアドレス入力欄の多重指定（要素変化に対応）
        email_selector = 'input[type="email"], input[name="login"], input[name="email"], input[placeholder*="メール"], input[placeholder*="ID"]'
        page.wait_for_selector(email_selector, timeout=15000)
        page.fill(email_selector, NOTE_EMAIL)

        # 2. パスワード入力欄の指定
        password_selector = 'input[type="password"], input[name="password"]'
        page.wait_for_selector(password_selector, timeout=15000)
        page.fill(password_selector, NOTE_PASSWORD)

        # 3. ログインボタン押下
        submit_button = 'button[type="submit"], button:has-text("ログイン")'
        page.click(submit_button)
        
        # ログイン完了まで待機
        page.wait_for_timeout(5000)

        logger.info("エディタ画面へ移動して記事を書き込み...")
        page.goto("https://note.com/notes/new", wait_until="networkidle")
        
        # タイトル入力
        title_selector = 'textarea[placeholder*="タイトル"], textarea[data-testid="title-input"]'
        page.wait_for_selector(title_selector, timeout=15000)
        page.fill(title_selector, title)

        # 本文入力
        body_selector = 'div[data-placeholder*="本文"], div[role="textbox"]'
        page.wait_for_selector(body_selector, timeout=15000)
        page.click(body_selector)
        page.keyboard.type(body)

        # 下書き保存ボタン押下
        save_button = 'button:has-text("下書き保存")'
        page.wait_for_selector(save_button, timeout=15000)
        page.click(save_button)
        page.wait_for_timeout(3000)
        
        logger.info(f"[SUCCESS] note下書き作成完了: {title}")
        browser.close()

# 5. メイン実行
def main():
    logger.info("=== note自動投稿パイプライン起動 ===")
    reports = fetch_unpublished_reports()
    logger.info(f"投稿対象レポート: {len(reports)} 件")

    for report in reports:
        logger.info(f"整形中: {report['title']}")
        note_article = format_for_note(report)
        
        if NOTE_EMAIL and NOTE_PASSWORD:
            post_to_note_via_playwright(note_article)
        else:
            logger.info("NOTE_EMAIL / NOTE_PASSWORD が未設定のため、生成テキストのログ出力のみ行います:")
            print("\n" + "="*40 + "\n" + note_article + "\n" + "="*40)

if __name__ == "__main__":
    main()
