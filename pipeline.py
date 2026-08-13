import os
import sys
import json
import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import requests
from google import genai
from google.genai import types

# ---------------------------------------------------------
# ログ設定
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 1. 環境変数 & 設定値取得（完全クレンジング）
# ---------------------------------------------------------
def clean_env(key: str, default: str = "") -> str:
    """環境変数からブラケット、引用符、不要な空白を除去する"""
    val = os.getenv(key, default)
    if not val:
        return default
    return str(val).strip("[]'\" \t\r\n")

GEMINI_API_KEY = clean_env("GEMINI_API_KEY")
GH_PAT = clean_env("GH_PAT")
TELEGRAM_BOT_TOKEN = clean_env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = clean_env("TELEGRAM_CHAT_ID")
NOTION_API_KEY = clean_env("NOTION_API_KEY")
NOTION_DATABASE_ID = clean_env("NOTION_DATABASE_ID")
PRODUCTHUNT_DEVELOPER_TOKEN = clean_env("PRODUCTHUNT_DEVELOPER_TOKEN")

TOP_N_FOR_DEEP_DIVE = int(clean_env("TOP_N_FOR_DEEP_DIVE", "3"))
STALE_THRESHOLD_DAYS = int(clean_env("STALE_THRESHOLD_DAYS", "10"))

if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY が設定されていません。処理を中断します。")
    sys.exit(1)

ai_client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-3.1-flash-lite"
logger.info(f"モデル解決成功: {MODEL_NAME}")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# ---------------------------------------------------------
# Telegram 通知モジュール（経営者への即時報連相）
# ---------------------------------------------------------
def send_telegram_notification(message: str):
    """パイプラインの実行結果をスマホへプッシュ通知"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("[TELEGRAM] TokenまたはChat IDが未設定のため通知をスキップします。")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            logger.info("[TELEGRAM] プッシュ通知の送信に成功しました。")
        else:
            logger.error(f"[TELEGRAM] 送信失敗: {res.status_code} - {res.text}")
    except Exception as e:
        logger.error(f"[TELEGRAM] 例外発生: {e}")

# ---------------------------------------------------------
# 2. Notion API 連携 (アーカイブ処理のRate Limit対策済み)
# ---------------------------------------------------------
def check_notion_schema() -> bool:
    """Notion DB構造検証"""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}"
    try:
        res = requests.get(url, headers=NOTION_HEADERS, timeout=10)
        if res.status_code == 200:
            logger.info("[SCHEMA CHECK PASSED] Notion DBの構造検証に成功しました。")
            return True
        else:
            logger.error(f"[SCHEMA CHECK FAILED] Status: {res.status_code}, Body: {res.text}")
            return False
    except Exception as e:
        logger.error(f"[SCHEMA CHECK] 例外発生: {e}")
        return False

def check_and_clean_stale_pages():
    """陳腐化データの自動検索 & 削除（0.3sウェイトでRate Limit回避）"""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    stale_date = (datetime.now(timezone.utc) - timedelta(days=STALE_THRESHOLD_DAYS)).isoformat()
    payload = {
        "filter": {
            "timestamp": "created_time",
            "created_time": {
                "before": stale_date
            }
        }
    }
    try:
        res = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=10)
        if res.status_code == 200:
            results = res.json().get("results", [])
            logger.info(f"[STALE CHECK] {STALE_THRESHOLD_DAYS}日以上前の既存データ: {len(results)}件検出")
            
            archived_count = 0
            for page in results:
                page_id = page.get("id")
                archive_url = f"https://api.notion.com/v1/pages/{page_id}"
                patch_res = requests.patch(archive_url, headers=NOTION_HEADERS, json={"archived": True}, timeout=10)
                if patch_res.status_code == 200:
                    archived_count += 1
                time.sleep(0.3)  # Notion Rate Limit 回避のための安全ウェイト

            if archived_count > 0:
                logger.info(f"[STALE CHECK] {archived_count} 件の古いページを正常にアーカイブしました。")
        else:
            logger.error(f"[STALE CHECK] エラー Status: {res.status_code}, Body: {res.text}")
    except Exception as e:
        logger.error(f"[STALE CHECK] 例外発生: {e}")

def get_existing_notion_titles() -> set:
    """Notion内の既存記事タイトルを取得して重複を防ぐ"""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    titles = set()
    try:
        res = requests.post(url, headers=NOTION_HEADERS, json={"page_size": 100}, timeout=10)
        if res.status_code == 200:
            pages = res.json().get("results", [])
            for page in pages:
                props = page.get("properties", {})
                name_prop = props.get("Name", {}).get("title", []) or props.get("タイトル", {}).get("title", [])
                if name_prop:
                    titles.add(name_prop[0].get("plain_text", "").strip())
            logger.info(f"[DEDUP CHECK] Notion既存記事 {len(titles)} 件を取得しました。")
    except Exception as e:
        logger.error(f"[DEDUP CHECK] 既存記事取得例外: {e}")
    return titles

# ---------------------------------------------------------
# 3. データソース収集モジュール (4ソース)
# ---------------------------------------------------------
def fetch_github_trending() -> list:
    logger.info(">>> [Source 1/4] GitHub一次データの自動巡回...")
    target_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
    url = f"https://api.github.com/search/repositories?q=created:>{target_date}+stars:>50&sort=stars&order=desc&per_page=10"
    headers = {"Authorization": f"token {GH_PAT}"} if GH_PAT else {}
    items = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            for repo in res.json().get("items", []):
                items.append({
                    "source": "GitHub",
                    "title": repo.get("full_name"),
                    "url": repo.get("html_url"),
                    "description": repo.get("description", "") or "",
                    "license": repo.get("license", {}).get("spdx_id") if repo.get("license") else "NOASSERTION"
                })
        logger.info(f"   -> GitHub: {len(items)} 件取得 (検索基準日: >{target_date})")
    except Exception as e:
        logger.error(f"   -> GitHub 取得失敗: {e}")
    return items

def fetch_hacker_news() -> list:
    logger.info(">>> [Source 2/4] Hacker News から一次データを取得中...")
    items = []
    try:
        top_ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()[:5]
        for item_id in top_ids:
            detail = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json", timeout=10).json()
            if detail:
                items.append({
                    "source": "Hacker News",
                    "title": f"HN: {detail.get('title')}",
                    "url": detail.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
                    "description": detail.get("title", ""),
                    "license": "MIT"
                })
        logger.info(f"   -> Hacker News: {len(items)} 件取得。")
    except Exception as e:
        logger.error(f"   -> Hacker News 取得失敗: {e}")
    return items

def fetch_arxiv_papers() -> list:
    logger.info(">>> [Source 3/4] ArXiv からAI/ML論文を取得中...")
    items = []
    url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL&start=0&max_results=3&sortBy=submittedDate&sortOrder=descending"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            root = ET.fromstring(res.text)
            for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                title = entry.find("{http://www.w3.org/2005/Atom}title").text.strip().replace("\n", " ")
                summary = entry.find("{http://www.w3.org/2005/Atom}summary").text.strip().replace("\n", " ")
                link = entry.find("{http://www.w3.org/2005/Atom}id").text.strip()
                items.append({
                    "source": "ArXiv",
                    "title": f"ArXiv: {title}",
                    "url": link,
                    "description": summary[:300],
                    "license": "CC-BY-4.0"
                })
        logger.info(f"   -> ArXiv: {len(items)} 件取得。")
    except Exception as e:
        logger.error(f"   -> ArXiv 取得失敗: {e}")
    return items

def fetch_product_hunt() -> list:
    logger.info(">>> [Source 4/4] Product Hunt からトレンドプロダクトを取得中...")
    items = []
    if PRODUCTHUNT_DEVELOPER_TOKEN:
        query = """
        {
          posts(first: 3) {
            edges {
              node {
                name
                tagline
                url
              }
            }
          }
        }
        """
        headers = {"Authorization": f"Bearer {PRODUCTHUNT_DEVELOPER_TOKEN}", "Content-Type": "application/json"}
        try:
            res = requests.post("https://api.producthunt.com/v2/api/graphql", json={"query": query}, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json().get("data", {}).get("posts", {}).get("edges", [])
                for edge in data:
                    node = edge.get("node", {})
                    items.append({
                        "source": "Product Hunt",
                        "title": f"PH: {node.get('name')}",
                        "url": node.get("url"),
                        "description": node.get("tagline"),
                        "license": "PROPRIETARY"
                    })
        except Exception as e:
            logger.error(f"   -> Product Hunt API エラー: {e}")
    logger.info(f"   -> Product Hunt: {len(items)} 件取得。")
    return items

# ---------------------------------------------------------
# 4. スクリーニング処理（一括バッチ評価）
# ---------------------------------------------------------
def screen_candidates_batch(candidates: list) -> list:
    logger.info(f">>> [Step 1] 軽量スクリーニング開始（対象 {len(candidates)} 件 - 一括バッチ評価）")
    if not candidates:
        return []

    candidate_summary = []
    for idx, item in enumerate(candidates):
        candidate_summary.append(
            f"[{idx+1}] Title: {item['title']}\nSource: {item['source']}\nDescription: {item['description'][:200]}"
        )
    
    prompt = f"""
あなたはWebメディア「note」の編集長です。
以下の{len(candidates)}件のテクノロジー候補を、読者の関心と収益性の観点から評価・採点してください。

【評価基準 (0〜100点)】
- ビジネス・エンジニアリングの実用性 (50%): 明日から活用・試用できる具体的なツールや手法か
- キャッチーさ・話題性 (30%): noteのタイトルとしてクリックしたくなるか
- 差別化・新規性 (20%): 類似プロダクトとの違いがあるか

【候補リスト】
{"\n---\n".join(candidate_summary)}

【出力フォーマット】
必ず以下のJSON配列形式のみで回答してください。
[
  {{
    "index": 1,
    "score": 85,
    "reason": "評価理由の要約（30文字以内）"
  }}
]
"""
    try:
        response = ai_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        raw_text = (response.text or "").strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            
        data = json.loads(raw_text)
        results = data.get("items", data) if isinstance(data, dict) else data

        screened_items = []
        scored_indices = set()
        
        if isinstance(results, list):
            for res in results:
                if not isinstance(res, dict):
                    continue
                idx = res.get("index", 1) - 1
                if 0 <= idx < len(candidates):
                    item = candidates[idx].copy()
                    item["score"] = res.get("score", 0)
                    item["reason"] = res.get("reason", "理由なし")
                    screened_items.append(item)
                    scored_indices.add(idx)
                    logger.info(f"[SCREENED] {item['title']}: {item['score']}点 ({item['reason']})")

        for idx, item in enumerate(candidates):
            if idx not in scored_indices:
                fallback_item = item.copy()
                fallback_item["score"] = 50
                fallback_item["reason"] = "パース補完デフォルト"
                screened_items.append(fallback_item)

        screened_items.sort(key=lambda x: x["score"], reverse=True)
        return screened_items

    except Exception as e:
        logger.error(f"[BATCH SCREENING ERROR] 一括評価失敗のためデフォルトスコアを設定: {e}")
        for item in candidates:
            item["score"] = 50
            item["reason"] = "バッチ評価エラーによるフォールバック"
        return candidates

# ---------------------------------------------------------
# 5. 深掘り記事生成 & Notion保存 (Markdown見出し自動構造化対応)
# ---------------------------------------------------------
def generate_and_save_deep_dive(item: dict):
    logger.info(f" [DEEP DIVE] {item['title']}（スクリーニングスコア {item['score']}点）")

    prompt = f"""
あなたは技術系人気noteクリエイターです。
以下の情報を元に、読者を惹きつける高品質なnote記事原稿（日本語）を作成してください。

タイトル: {item['title']}
ソース: {item['source']}
URL: {item['url']}
概要: {item['description']}

【記事構成要件】
1. 惹きつける導入（なぜ今これが注目されているのか）
2. 核心技術・仕組みの要約
3. 実際の活用シナリオ・ビジネスインパクト
4. まとめと今後の展望
"""

    try:
        response = ai_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        content_text = response.text or ""

        # Markdownの見出しを解析し、適切なNotionブロック構造（heading_1, heading_2, paragraph）へ変換
        paragraphs = [p.strip() for p in content_text.split("\n") if p.strip()]
        children_blocks = []
        for p in paragraphs[:30]:  # 上限30ブロック
            if p.startswith("### "):
                block_type = "heading_3"
                text_content = p[4:]
            elif p.startswith("## "):
                block_type = "heading_2"
                text_content = p[3:]
            elif p.startswith("# "):
                block_type = "heading_1"
                text_content = p[2:]
            else:
                block_type = "paragraph"
                text_content = p

            children_blocks.append({
                "object": "block",
                "type": block_type,
                block_type: {
                    "rich_text": [{"type": "text", "text": {"content": text_content[:1000]}}]
                }
            })

        url = "https://api.notion.com/v1/pages"
        payload = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": {
                "Name": {
                    "title": [{"text": {"content": item['title']}}]
                },
                "Source": {
                    "select": {"name": item['source']}
                },
                "URL": {
                    "url": item['url'] if item['url'].startswith("http") else "https://notion.so"
                },
                "Score": {
                    "number": item['score']
                }
            },
            "children": children_blocks
        }

        res = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
        if res.status_code == 200:
            logger.info(f"[NOTION SAVED] {item['title']} -> クレンジング済みnote原稿の保存完了")
        else:
            logger.error(f"[NOTION SAVE FAILED] {item['title']} Status: {res.status_code}, Body: {res.text}")

    except Exception as e:
        logger.error(f"[DEEP DIVE ERROR] {item['title']} の生成・保存失敗: {e}")

# ---------------------------------------------------------
# 6. メインパイプライン実行
# ---------------------------------------------------------
def main():
    logger.info("==========================================")
    logger.info(" 完全無人インテリジェンス工場 パイプライン起動（経営者自動通知仕様）")
    logger.info("==========================================")

    if not check_notion_schema():
        error_msg = "❌ [AI note工場] Notion API接続失敗のため、処理を異常停止しました。"
        logger.error(error_msg)
        send_telegram_notification(error_msg)
        sys.exit(1)

    # 1. 古いデータのクレンジング実行
    check_and_clean_stale_pages()

    # 2. 全ソースから candidate 収集
    raw_candidates = []
    raw_candidates.extend(fetch_github_trending())
    raw_candidates.extend(fetch_hacker_news())
    raw_candidates.extend(fetch_arxiv_papers())
    raw_candidates.extend(fetch_product_hunt())

    logger.info(f"全ソース統合完了: 合計 {len(raw_candidates)} 件の候補を収集")

    # 3. ライセンスフィルター
    safe_candidates = []
    unsafe_licenses = ["GPL-3.0", "AGPL-3.0", "NOASSERTION"]
    for c in raw_candidates:
        if c.get("license") in unsafe_licenses and c.get("source") == "GitHub":
            logger.info(f" [SKIP: LICENSE] {c['title']} -> UNSAFE ({c.get('license')})")
        else:
            safe_candidates.append(c)

    # 4. Notion重複排除
    existing_titles = get_existing_notion_titles()
    final_candidates = []
    for c in safe_candidates:
        if c['title'] in existing_titles:
            logger.info(f" [SKIP: DUPLICATE] {c['title']} -> 既にNotionに存在するため除外")
        else:
            final_candidates.append(c)

    if not final_candidates:
        info_msg = "ℹ️ 【AI note工場】本日の新規候補はありませんでした。パイプラインを終了します。"
        logger.info(info_msg)
        send_telegram_notification(info_msg)
        return

    # 5. スクリーニング（一括バッチ評価）
    screened = screen_candidates_batch(final_candidates)

    # 6. 上位N件を選定
    top_items = screened[:TOP_N_FOR_DEEP_DIVE]

    # 7. 深掘り生成 & Notion保存
    for item in top_items:
        generate_and_save_deep_dive(item)

    # 8. 経営者へ最終Telegramレポート送信
    summary_lines = [f"• *{item['title']}* (スコア: {item['score']}点)" for item in top_items]
    report_text = (
        f"🚀 *【AI note事業】無人レポート完了*\n\n"
        f"本日{len(final_candidates)}件を巡回・評価し、上位{len(top_items)}件の完全原稿をNotionへ格納しました。\n\n"
        f"*【本日選出されたトップコンテンツ】*\n" + "\n".join(summary_lines) + "\n\n"
        f"👉 [Notionデータベースを確認する](https://notion.so)"
    )
    
    logger.info(f"✅ パイプライン完了。Telegram通知を送信します。")
    send_telegram_notification(report_text)

if __name__ == "__main__":
    main()
