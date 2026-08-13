import os
import re
import time
import requests
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from google import genai
from google.genai.errors import APIError

# ==========================================
# ログ設定
# ==========================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("gemini_pipeline")

# ==========================================
# 1. 環境変数の取得
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GH_PAT = os.environ.get("GH_PAT")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
PRODUCTHUNT_DEVELOPER_TOKEN = os.environ.get("PRODUCTHUNT_DEVELOPER_TOKEN")

if not GEMINI_API_KEY or not GH_PAT:
    raise ValueError("エラー: GEMINI_API_KEY または GH_PAT が設定されていません。")

client = genai.Client(api_key=GEMINI_API_KEY)

CANDIDATE_MODELS = os.environ.get(
    "GEMINI_MODEL_CANDIDATES",
    "gemini-3.1-flash-lite,gemini-3.5-flash"
).split(",")

# 深掘り（Step2フルレポート）に回す件数（Two-Stage化）
TOP_N_FOR_DEEP_DIVE = int(os.environ.get("TOP_N_FOR_DEEP_DIVE", "3"))

# 滞留検知: 最終記事生成からこの日数を超えたら運用者に通知
STALE_THRESHOLD_DAYS = int(os.environ.get("STALE_THRESHOLD_DAYS", "10"))

# ==========================================
# 2. Notion プロパティ定義 & トークン設定
# ==========================================
PROP_NAME = "Name"
PROP_URL = "URL"
PROP_SCORE = "Decision Score"
PROP_SCORE_BREAKDOWN = "Score Breakdown"
PROP_WHAT = "What"
PROP_WHY_IMPORTANT = "Why Important"
PROP_WHY_NOT_IMPORTANT = "Why NOT Important"
PROP_WHO = "Who"
PROP_ACTION = "Action"
PROP_LICENSE = "License"
PROP_PARADIGM_SHIFT = "Paradigm Shift"
PROP_ALTERNATIVE_COMPARISON = "Alternative Comparison"
PROP_MIGRATION_COST = "Migration Cost"

REQUIRED_NOTION_PROPERTIES = [
    PROP_NAME, PROP_URL, PROP_SCORE, PROP_SCORE_BREAKDOWN,
    PROP_WHAT, PROP_WHY_IMPORTANT, PROP_WHY_NOT_IMPORTANT,
    PROP_WHO, PROP_ACTION, PROP_LICENSE, PROP_PARADIGM_SHIFT,
    PROP_ALTERNATIVE_COMPARISON, PROP_MIGRATION_COST
]

SECTION_SPLIT_TOKEN = "===NOTE_DRAFT_START==="

PAID_AREA_PATTERN = re.compile(
    r"^[\s\-−ー―─━▼◆■●\*]{0,10}\s*有料エリア\s*[\s\-−ー―─━▼◆■●\*]{0,10}$",
    re.MULTILINE
)

NOTE_PAYWALL_LABEL = "\n\n▼▼▼ ここから先は有料エリアです ▼▼▼\n\n"
DIVIDER_LINE = "\n\n" + "─" * 24 + "\n"

NOTION_BLOCK_LIMIT = 1900
MIN_PAID_AREA_LENGTH = 1200
MAX_QUALITY_RETRIES = 2

# ==========================================
# 3. アラート & API/モデル制御
# ==========================================
class NoAvailableModelError(RuntimeError): pass
class DailyQuotaExhaustedError(RuntimeError): pass

def send_telegram_alert(message: str):
    """運用者(自分)宛のアラート通知。Telegram Bot API経由で送信する。"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_BOT_TOKEN または TELEGRAM_CHAT_ID が未設定のため通知をスキップします。")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message[:4000],
        "disable_web_page_preview": True,
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            logger.error(f"Telegram通知失敗: {res.status_code} {res.text}")
    except Exception as e:
        logger.error(f"Telegram通知失敗: {e}")

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
                    model=model_name, contents="ping", config={"max_output_tokens": 8}
                )
                logger.info(f"モデル解決成功: {model_name}")
                return model_name
            except APIError as e:
                last_error = e
                if e.code == 404: break
                if e.code == 429 and _is_daily_quota_exhausted(e): break
                if e.code in (503, 429):
                    if attempt < PING_MAX_RETRIES:
                        wait = PING_RETRY_BACKOFF_SECONDS * (attempt + 1)
                        time.sleep(wait)
                        continue
                    break
                raise NoAvailableModelError(f"想定外のAPIエラー: {e.code}") from e
            except Exception as e:
                last_error = e
                raise NoAvailableModelError("想定外の例外") from e
    raise NoAvailableModelError("利用可能なモデルがありません") from last_error

try:
    SELECTED_MODEL = resolve_model()
except NoAvailableModelError as e:
    send_telegram_alert(f"⚠️ 【緊急】Gemini初期化失敗: {e}")
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
                    time.sleep(wait)
                    continue
                raise
            elif e.code == 429:
                if _is_daily_quota_exhausted(e):
                    raise DailyQuotaExhaustedError(str(e)) from e
                delay = _extract_retry_delay(e)
                if attempt < max_retries:
                    time.sleep(delay)
                    continue
                raise
            else:
                raise

# ==========================================
# 4. Markdownクレンジング & note原稿整形
# ==========================================
def clean_markdown_for_note(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"```[a-zA-Z0-9]*\n?", "", text)
    text = text.replace("```", "")
    text = text.replace("`", "")
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"^\s*[-*]\s+", "・", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*([-*_]){3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def split_free_paid(note_draft: str, repo_name: str = ""):
    match = PAID_AREA_PATTERN.search(note_draft)
    if not match:
        logger.error(f"[PAID AREA MISSING] {repo_name} -> 有料エリア境界を検出できませんでした。")
        send_telegram_alert(
            f"🚨【要手動確認】{repo_name} の原稿で有料エリア境界を検出できませんでした。"
            f"全文が無料エリア扱いになっている可能性があるため、Notion側の原稿を確認してから公開してください。"
        )
        return note_draft.strip(), ""

    free_part = note_draft[:match.start()]
    paid_part = note_draft[match.end():]
    return free_part.strip(), paid_part.strip()

def build_clean_note_manuscript(note_draft: str, repo_name: str, repo_url: str, spdx_id: str) -> str:
    free_part, paid_part = split_free_paid(note_draft, repo_name)
    free_clean = clean_markdown_for_note(free_part)
    paid_clean = clean_markdown_for_note(paid_part)

    manuscript = free_clean
    if paid_clean:
        manuscript += NOTE_PAYWALL_LABEL + paid_clean

    source_block = (
        f"{DIVIDER_LINE}"
        f"出典元\n"
        f"情報源 / リポジトリ: {repo_name}\n"
        f"公式リンク: {repo_url}\n"
        f"ライセンス: {spdx_id}\n"
        f"※本記事はライセンスが公開・再利用可能な条件（MIT / Apache-2.0 / BSD / CC-BY-4.0等）"
        f"であることを確認した上で分析・要約しています。\n"
    )
    manuscript += source_block
    return manuscript.strip()

# ==========================================
# 5. Notion 保存 & 事前検証 (Fail-Closed)
# ==========================================
def verify_notion_schema() -> bool:
    """Gemini API呼び出し前にNotion DBのスキーマ構造を検証するFail-Closedガード"""
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        logger.error("NOTION_API_KEY または NOTION_DATABASE_ID が未設定です。")
        return False
    
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            logger.error(f"[SCHEMA CHECK] Notion DBアクセス失敗: {res.status_code} {res.text}")
            return False
        
        db_props = res.json().get("properties", {})
        missing_props = [p for p in REQUIRED_NOTION_PROPERTIES if p not in db_props]
        
        if missing_props:
            err_msg = f"🚨【Fail-Closed起動】Notion DBに必要なプロパティが見つかりません: {missing_props}"
            logger.error(err_msg)
            send_telegram_alert(err_msg)
            return False
        
        logger.info("[SCHEMA CHECK PASSED] Notion DBの構造検証に成功しました。")
        return True
    except Exception as e:
        logger.error(f"[SCHEMA CHECK FAILED] {e}")
        return False

def safe_chunk_text(text: str, limit: int = NOTION_BLOCK_LIMIT) -> list[str]:
    if not text:
        return []

    chunks: list[str] = []
    current = ""

    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(line) <= limit:
            current = line
            continue

        sentences = re.findall(r"[^。！？]*[。！？]|[^。！？]+$", line)
        buf = ""
        for sentence in sentences:
            cand = buf + sentence
            if len(cand) <= limit:
                buf = cand
                continue
            if buf:
                chunks.append(buf)
                buf = ""
            if len(sentence) <= limit:
                buf = sentence
            else:
                for i in range(0, len(sentence), limit):
                    chunks.append(sentence[i:i + limit])
        current = buf

    if current:
        chunks.append(current)

    return chunks

def build_notion_payload(repo_name, repo_url, score, score_breakdown_text, what_text,
                          why_important_text, why_not_important_text, action_text,
                          spdx_id, clean_manuscript, paradigm_shift_text="",
                          alternative_comparison_text="", migration_cost_text=""):

    chunks = safe_chunk_text(clean_manuscript)
    children_blocks = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}
        } for chunk in chunks
    ]

    return {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            PROP_NAME: {"title": [{"text": {"content": repo_name}}]},
            PROP_URL: {"url": repo_url},
            PROP_SCORE: {"number": score},
            PROP_SCORE_BREAKDOWN: {"rich_text": [{"text": {"content": score_breakdown_text[:2000]}}]},
            PROP_WHAT: {"rich_text": [{"text": {"content": what_text[:2000]}}]},
            PROP_WHY_IMPORTANT: {"rich_text": [{"text": {"content": why_important_text[:2000]}}]},
            PROP_WHY_NOT_IMPORTANT: {"rich_text": [{"text": {"content": why_not_important_text[:2000]}}]},
            PROP_WHO: {"rich_text": [{"text": {"content": "PM / テックリード / 開発チーム"}}]},
            PROP_ACTION: {"rich_text": [{"text": {"content": action_text[:2000]}}]},
            PROP_LICENSE: {"rich_text": [{"text": {"content": spdx_id}}]},
            PROP_PARADIGM_SHIFT: {"rich_text": [{"text": {"content": paradigm_shift_text[:2000]}}]},
            PROP_ALTERNATIVE_COMPARISON: {"rich_text": [{"text": {"content": alternative_comparison_text[:2000]}}]},
            PROP_MIGRATION_COST: {"rich_text": [{"text": {"content": migration_cost_text[:2000]}}]},
        },
        "children": children_blocks,
    }

def save_to_notion(repo_name, repo_url, score, score_breakdown_text, what_text,
                    why_important_text, why_not_important_text, action_text,
                    spdx_id, clean_manuscript, paradigm_shift_text="",
                    alternative_comparison_text="", migration_cost_text="") -> bool:
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        return False
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    payload = build_notion_payload(
        repo_name, repo_url, score, score_breakdown_text, what_text,
        why_important_text, why_not_important_text, action_text,
        spdx_id, clean_manuscript, paradigm_shift_text,
        alternative_comparison_text, migration_cost_text
    )
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            logger.info(f"[NOTION SAVED] {repo_name} -> クレンジング済みnote原稿の保存完了")
            return True
        logger.error(f"[NOTION ERROR] {repo_name} -> {res.text}")
        return False
    except Exception as e:
        logger.error(f"[NOTION EXCEPTION] {e}")
        return False

# ==========================================
# 6. 一次データ収集 (4ソース並行収集モジュール)
# ==========================================
def fetch_github_trending() -> list[dict]:
    logger.info(">>> [Source 1/4] GitHub一次データの自動巡回...")
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"Bearer {GH_PAT}", "Content-Type": "application/json"}
    since_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    query = f"""
    {{
      search(query: "topic:ai topic:machine-learning stars:>100 pushed:>{since_date}", type: REPOSITORY, first: 10) {{
        nodes {{
          ... on Repository {{
            nameWithOwner
            url
            description
            stargazerCount
            licenseInfo {{ spdxId }}
          }}
        }}
      }}
    }}
    """
    try:
        response = requests.post(url, json={"query": query}, headers=headers, timeout=10)
        if response.status_code == 200:
            nodes = response.json().get("data", {}).get("search", {}).get("nodes", [])
            for node in nodes:
                node["source"] = "GitHub"
            logger.info(f"   -> GitHub: {len(nodes)} 件取得。")
            return nodes
    except Exception as e:
        logger.error(f"GitHub APIエラー: {e}")
    return []

def fetch_hacker_news(limit: int = 5) -> list[dict]:
    logger.info(">>> [Source 2/4] Hacker News から一次データを取得中...")
    try:
        top_ids_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        res = requests.get(top_ids_url, timeout=10)
        if res.status_code != 200:
            return []
        
        story_ids = res.json()[:limit * 2]
        items = []
        
        for s_id in story_ids:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{s_id}.json"
            i_res = requests.get(item_url, timeout=5)
            if i_res.status_code == 200:
                data = i_res.json()
                url = data.get("url") or f"https://news.ycombinator.com/item?id={s_id}"
                items.append({
                    "nameWithOwner": f"HN: {data.get('title', 'No Title')}",
                    "url": url,
                    "description": f"Hacker News Score: {data.get('score', 0)} | By: {data.get('by', 'unknown')}",
                    "stargazerCount": data.get("score", 0),
                    "licenseInfo": {"spdxId": "MIT"},
                    "source": "HackerNews"
                })
                if len(items) >= limit:
                    break
        logger.info(f"   -> Hacker News: {len(items)} 件取得。")
        return items
    except Exception as e:
        logger.error(f"Hacker News API取得エラー: {e}")
        return []

def fetch_arxiv(limit: int = 3) -> list[dict]:
    logger.info(">>> [Source 3/4] ArXiv からAI/ML論文を取得中...")
    url = (
        "http://export.arxiv.org/api/query?"
        "search_query=cat:cs.AI+OR+cat:cs.CL&"
        "sortBy=submittedDate&sortOrder=descending&"
        f"max_results={limit}"
    )
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return []
        
        root = ET.fromstring(res.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = []
        
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
            arxiv_id_elem = entry.find("atom:id", ns)
            link = arxiv_id_elem.text if arxiv_id_elem is not None else ""
            
            items.append({
                "nameWithOwner": f"ArXiv: {title[:80]}...",
                "url": link,
                "description": f"概要: {summary[:200]}...",
                "stargazerCount": 100,
                "licenseInfo": {"spdxId": "CC-BY-4.0"},
                "source": "ArXiv"
            })
        logger.info(f"   -> ArXiv: {len(items)} 件取得。")
        return items
    except Exception as e:
        logger.error(f"ArXiv API取得エラー: {e}")
        return []

def fetch_product_hunt(limit: int = 3) -> list[dict]:
    if not PRODUCTHUNT_DEVELOPER_TOKEN:
        logger.warning("PRODUCTHUNT_DEVELOPER_TOKEN が未設定のためProduct Hunt取得をスキップします。")
        return []
        
    logger.info(">>> [Source 4/4] Product Hunt からトレンドプロダクトを取得中...")
    url = "https://api.producthunt.com/v2/api/graphql"
    headers = {
        "Authorization": f"Bearer {PRODUCTHUNT_DEVELOPER_TOKEN}",
        "Content-Type": "application/json"
    }
    query = """
    {
      posts(first: 10) {
        edges {
          node {
            name
            tagline
            url
            votesCount
          }
        }
      }
    }
    """
    try:
        res = requests.post(url, json={"query": query}, headers=headers, timeout=10)
        if res.status_code != 200:
            logger.error(f"Product Hunt APIエラー: {res.status_code} {res.text}")
            return []
            
        posts = res.json().get("data", {}).get("posts", {}).get("edges", [])
        items = []
        for post in posts:
            node = post.get("node", {})
            items.append({
                "nameWithOwner": f"PH: {node.get('name')}",
                "url": node.get("url"),
                "description": node.get("tagline", ""),
                "stargazerCount": node.get("votesCount", 0),
                "licenseInfo": {"spdxId": "MIT"},
                "source": "ProductHunt"
            })
            if len(items) >= limit:
                break
        logger.info(f"   -> Product Hunt: {len(items)} 件取得。")
        return items
    except Exception as e:
        logger.error(f"Product Hunt API取得エラー: {e}")
        return []

def fetch_all_sources() -> list[dict]:
    """全ソースを一括収集"""
    all_items = []
    all_items.extend(fetch_github_trending())
    all_items.extend(fetch_hacker_news(limit=5))
    all_items.extend(fetch_arxiv(limit=3))
    all_items.extend(fetch_product_hunt(limit=3))
    logger.info(f"全ソース統合完了: 合計 {len(all_items)} 件の候補を収集")
    return all_items

def legal_safety_gate(repo):
    """ライセンスチェック（NoneTypeクラッシュ対策防止）"""
    license_info = repo.get("licenseInfo")
    if not license_info: 
        return False, "NO_LICENSE"
    
    # AttributeError防止ガード (spdxIdがNoneの場合に対応)
    spdx_id = (license_info.get("spdxId") or "").upper()
    safe = ["MIT", "APACHE-2.0", "BSD-3-CLAUSE", "BSD-2-CLAUSE", "CC-BY-4.0"]
    return (True, spdx_id) if spdx_id in safe else (False, f"UNSAFE ({spdx_id})")

def get_existing_repo_urls() -> set:
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        return set()

    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    existing_urls = set()
    next_cursor = None

    try:
        while True:
            payload = {"page_size": 100}
            if next_cursor:
                payload["start_cursor"] = next_cursor

            res = requests.post(url, json=payload, headers=headers, timeout=10)
            if res.status_code != 200:
                logger.error(f"[DEDUP CHECK] Notion問い合わせ失敗: {res.text}")
                send_telegram_alert(
                    "⚠️ 重複チェックのためのNotion問い合わせに失敗しました。"
                    "今回は重複チェックをスキップして続行します（要確認）。"
                )
                return set()

            data = res.json()
            for page in data.get("results", []):
                url_prop = page.get("properties", {}).get(PROP_URL, {})
                page_url = url_prop.get("url")
                if page_url:
                    existing_urls.add(page_url.rstrip("/"))

            if data.get("has_more"):
                next_cursor = data.get("next_cursor")
            else:
                break

        logger.info(f"[DEDUP CHECK] Notion既存記事 {len(existing_urls)} 件を取得しました。")
        return existing_urls

    except Exception as e:
        logger.error(f"[DEDUP CHECK] 例外発生: {e}")
        send_telegram_alert(
            "⚠️ 重複チェック中に想定外のエラーが発生しました。"
            "今回は重複チェックをスキップして続行します（要確認）。"
        )
        return set()

# ==========================================
# 7. 「判断装置」プロンプト & 解析
# ==========================================
def build_decision_prompt(name, url, stars, desc, quality_feedback: str = ""):
    feedback_block = f"""
【重要・前回の生成に対する差し戻し】
前回の出力は有料エリアの分量・具体性が不足しており、有料記事として採用できませんでした。
{quality_feedback}
今回は上記を踏まえ、有料エリアの代替比較・移行コストとリスク・Decision Scoreの根拠を、
それぞれ具体的な固有名詞・数値・手順を交えてより深く掘り下げて書き直してください。
""" if quality_feedback else ""

    return f"""
{feedback_block}あなたは月額1,980円の有料購読者（CTO・テックリード・PM）が「読んで即・業務判断ができた」
と満足する、技術系note「判断装置（Decision Intelligence）」の専属アナリスト兼トップライターです。

読者は公式ドキュメントや概要を自分で読めます。読者が金を払うのは、単なる要約ではなく、
「このプロジェクトが既存の何を置き換えようとしているのか」「なぜ今のタイミングで
意味を持つのか」「導入した場合の移行コストとリスクは何か」という一段深い分析です。
以下の分析軸を必ず満たしてください。

- 技術的パラダイムシフト: このプロジェクトは既存のアプローチの何を否定・刷新しようと
  しているか。単なる機能追加ではなく、設計思想・アーキテクチャレベルの変化を特定すること。
- 代替との比較: 同じ課題を解決している既存ツール・製品を最低1つ具体名で挙げ、
  何が決定的に違うのかを名指しで説明すること（比較対象を挙げずに「優れている」と
  断定するのは禁止）。
- 移行コストとリスク: 既存システムから乗り換える場合に発生する作業・学習コスト・
  破壊的変更のリスクを具体的に見積もること。

【対象プロジェクト】
・名前: {name}
・URL: {url}
・Stars/Score: {stars}
・概要: {desc}

【出力ルール（厳守）】
・出力は以下のフォーマットに厳密に従うこと。項目の省略・順序変更は禁止。
・Markdownのコードブロック（```）、太字（**）、見出し記号（#）は一切使用しないこと。
・箇条書きは半角ハイフン「-」ではなく、全角中黒「・」を使うこと。
・数値は算用数字で、指定の満点内に収めること。
・管理用データの直後には、必ず改行してから "{SECTION_SPLIT_TOKEN}" という行だけを
  単独で挿入し、その後にnote原稿本文を続けること。
・note原稿本文中、無料エリアと有料エリアの境目には、必ず「---有料エリア---」という
  行だけを単独で挿入すること。
・有料エリアは合計1600字以上を必須とする。分量不足は差し戻し対象となる。

【出力フォーマット】

【管理用データ】
・What(概要): 日本語で2文以内。今、何が起きているかを事実ベースで説明する。
・Why Important(導入インパクト): なぜ実務チームが今これを見るべきか、具体的な業務・
  プロダクトへの影響を説明する。
・技術的パラダイムシフト: 既存アプローチの何を刷新しているか、設計思想レベルで説明する。
・代替との比較: 具体的な既存ツール名を挙げ、決定的な違いを説明する。
・移行コストとリスク: 乗り換える場合の作業量・学習コスト・破壊的変更リスクを具体的に見積もる。
・Decision Score:
  ・Business Impact(25点満点): X点 - 採用・非採用が事業やコストに与える影響の根拠
  ・Technical Impact(25点満点): X点 - 既存の技術スタックや開発プロセスへの影響の根拠
  ・Urgency(20点満点): X点 - 今週〜今月中に判断すべき緊急度の根拠
  ・Market Impact(15点満点): X点 - 競合・業界動向への影響の根拠
  ・Reliability(15点満点): X点 - 情報源・プロジェクトの信頼性（スター数、メンテ状況、ライセンス等）の根拠
  ・合計: X / 100点
・Why NOT Important(スルーしてよい理由): どのような業種・規模・技術スタックの企業や
  開発者には影響がなく、今は無視してよいか、その根拠を具体的に述べる。
・Action: 今週中に実務チームが取るべき最も具体的な次の一手（誰が何をするか）。

{SECTION_SPLIT_TOKEN}

（読者の興味を引くキャッチーな記事タイトル。1行）

（無料エリア：What、Why Important、技術的パラダイムシフトの要点を、記事として
自然に読める文章で構成する。読者に価値の全貌を感じさせつつ、続きへの期待を持たせる
分量で書く。）

---有料エリア---

（有料エリア：代替との比較、移行コストとリスク、Decision Scoreの各項目の詳細な根拠、
Why NOT Important、そして今週中に取るべきActionを、読者が「1980円払って良かった」と
思える深さと具体性で書く。目安として全体で1600字以上を目標とし、各項目とも
2〜3文の説明で終わらせず、具体的な固有名詞・数値・手順を交えて掘り下げること。）
"""

def _parse_gemini_response(full_text: str) -> dict:
    parts = full_text.split(SECTION_SPLIT_TOKEN)
    management_data = parts[0]
    note_draft = parts[1].strip() if len(parts) > 1 else "原稿生成に失敗しました。"

    NEXT_ITEM = r"(?=\n・|\n\n|$)"

    total_match = re.search(r"合計[:：]?\s*(\d+)\s*/\s*100", management_data)
    score = int(total_match.group(1)) if total_match else 0

    breakdown_match = re.search(
        r"Decision Score[:：]?\s*(.*?)(?=\n・Why NOT Important|\n・Action)",
        management_data, re.DOTALL
    )
    score_breakdown_text = breakdown_match.group(1).strip() if breakdown_match else "内訳取得失敗"

    def extract_field(label: str, fallback: str) -> str:
        m = re.search(rf"・{re.escape(label)}[^\:：]*[:：]\s*(.*?){NEXT_ITEM}", management_data, re.DOTALL)
        return m.group(1).strip() if m else fallback

    return {
        "note_draft": note_draft,
        "score": score,
        "score_breakdown_text": score_breakdown_text,
        "what_text": extract_field("What", "概要参照"),
        "why_important_text": extract_field("Why Important", "特記事項なし"),
        "paradigm_shift_text": extract_field("技術的パラダイムシフト", "特記事項なし"),
        "alternative_comparison_text": extract_field("代替との比較", "特記事項なし"),
        "migration_cost_text": extract_field("移行コストとリスク", "特記事項なし"),
        "why_not_important_text": extract_field("Why NOT Important", "特記事項なし"),
        "action_text": extract_field("Action", "アクション参照"),
    }

def _paid_area_length(note_draft: str, repo_name: str) -> int:
    _, paid_part = split_free_paid(note_draft, repo_name)
    return len(clean_markdown_for_note(paid_part))

def generate_intelligence_report(repo):
    name = repo.get("nameWithOwner")
    desc = repo.get("description", "説明なし")
    url = repo.get("url")
    stars = repo.get("stargazerCount", 0)
    is_safe, spdx_id = legal_safety_gate(repo)

    quality_feedback = ""
    parsed = None
    paid_len = 0

    try:
        for attempt in range(MAX_QUALITY_RETRIES + 1):
            prompt = build_decision_prompt(name, url, stars, desc, quality_feedback)
            response = call_gemini_with_smart_retry(prompt)
            parsed = _parse_gemini_response(response.text)
            paid_len = _paid_area_length(parsed["note_draft"], name)

            if paid_len >= MIN_PAID_AREA_LENGTH:
                break

            logger.warning(
                f"[QUALITY GATE] {name}: 有料エリア{paid_len}文字(閾値{MIN_PAID_AREA_LENGTH}) "
                f"-> 自動リトライ {attempt + 1}/{MAX_QUALITY_RETRIES}"
            )
            quality_feedback = (
                f"直近の出力はクレンジング後の有料エリアがわずか{paid_len}文字でした。"
                f"最低でも{MIN_PAID_AREA_LENGTH}文字以上を目安に、"
                f"固有名詞・数値・比較対象を増やして具体性を上げてください。"
            )

        if paid_len < MIN_PAID_AREA_LENGTH:
            logger.error(f"[QUALITY GATE FAILED] {name}: {MAX_QUALITY_RETRIES}回のリトライでも基準未達のためスキップ")
            send_telegram_alert(
                f"ℹ️ {name} は{MAX_QUALITY_RETRIES}回のAI自動リトライでも有料エリアの分量基準"
                f"（{MIN_PAID_AREA_LENGTH}文字）を満たせなかったため、今回は生成をスキップしました。"
            )
            return None

        clean_manuscript = build_clean_note_manuscript(parsed["note_draft"], name, url, spdx_id)

        save_to_notion(
            name, url, parsed["score"], parsed["score_breakdown_text"], parsed["what_text"],
            parsed["why_important_text"], parsed["why_not_important_text"], parsed["action_text"],
            spdx_id, clean_manuscript, parsed["paradigm_shift_text"],
            parsed["alternative_comparison_text"], parsed["migration_cost_text"]
        )
        return clean_manuscript

    except DailyQuotaExhaustedError:
        send_telegram_alert("⚠️ Gemini APIの日次クォータに到達しました。")
        raise
    except Exception as e:
        logger.error(f"Gemini解析エラー ({name}): {e}")
        return None

# ==========================================
# Step 1: 軽量スクリーニング
# ==========================================
def build_screening_prompt(name, desc, stars) -> str:
    return f"""
以下のプロダクト/技術情報について、CTO/PM向け有料note記事の題材としての価値を
0〜100点で採点せよ。判断基準: 技術的な新規性・実務への即効性・話題性。

・名前: {name}
・指標/Stars: {stars}
・概要: {desc}

出力は必ず次の1行形式のみ。説明文・Markdown・前置きは一切不要。
SCORE=<0-100の整数> REASON=<20文字以内の一言理由>
"""

def _parse_screening_response(text: str) -> dict:
    score_match = re.search(r"SCORE\s*=\s*(\d+)", text)
    reason_match = re.search(r"REASON\s*=\s*(.+)", text)
    return {
        "score": int(score_match.group(1)) if score_match else 0,
        "reason": reason_match.group(1).strip() if reason_match else "取得失敗",
    }

def screen_repo(repo) -> dict:
    name = repo.get("nameWithOwner")
    desc = repo.get("description", "説明なし")
    stars = repo.get("stargazerCount", 0)
    prompt = build_screening_prompt(name, desc, stars)

    # 1分あたりのレート制限(RPM)を安全回避するための4秒インターバル
    time.sleep(4)

    SCREENING_MAX_RETRIES = 1
    for attempt in range(SCREENING_MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=SELECTED_MODEL,
                contents=prompt,
                config={"max_output_tokens": 30},
            )
            parsed = _parse_screening_response(response.text)
            logger.info(f"[SCREENED] {name}: {parsed['score']}点 ({parsed['reason']})")
            return {"repo": repo, "score": parsed["score"], "reason": parsed["reason"]}
        except DailyQuotaExhaustedError:
            raise
        except APIError as e:
            if e.code == 503 and attempt < SCREENING_MAX_RETRIES:
                logger.warning(f"[SCREENING RETRY] {name}: 503のため再試行します。")
                time.sleep(10)
                continue
            logger.error(f"[SCREENING FAILED] {name}: {e}")
            send_telegram_alert(f"⚠️ スクリーニング失敗: {name} ({e.code if hasattr(e, 'code') else e})")
            return {"repo": repo, "score": 0, "reason": "スクリーニング失敗"}
        except Exception as e:
            logger.error(f"[SCREENING UNEXPECTED ERROR] {name}: {e}")
            send_telegram_alert(f"⚠️ スクリーニング中の想定外エラー: {name} ({e})")
            return {"repo": repo, "score": 0, "reason": "想定外エラー"}

# ==========================================
# 滞留検知
# ==========================================
def check_stale_content():
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        logger.warning("Notion未設定のため滞留検知をスキップします。")
        return

    url = f"[https://api.notion.com/v1/databases/](https://api.notion.com/v1/databases/){NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    payload = {
        "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        "page_size": 1,
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code != 200:
            logger.error(f"[STALE CHECK] Notion問い合わせ失敗: {res.text}")
            return

        results = res.json().get("results", [])
        if not results:
            logger.warning("[STALE CHECK] Notion DBにページが1件もありません。")
            return

        latest_created_str = results[0]["created_time"]
        latest_created = datetime.fromisoformat(latest_created_str.replace("Z", "+00:00"))
        days_since = (datetime.now(timezone.utc) - latest_created).days

        logger.info(f"[STALE CHECK] 最終記事生成から {days_since} 日経過（閾値 {STALE_THRESHOLD_DAYS} 日）")

        if days_since >= STALE_THRESHOLD_DAYS:
            send_telegram_alert(
                f"🟡【運用確認】最終記事生成から {days_since} 日が経過しています"
                f"（閾値: {STALE_THRESHOLD_DAYS}日）。\n"
                f"パイプラインの異常有無を確認し、必要であれば有料購読者への"
                f"説明を検討してください。"
            )
    except Exception as e:
        logger.error(f"[STALE CHECK] 例外発生: {e}")

# ==========================================
# 8. メイン実行パイプライン
# ==========================================
def main():
    logger.info("==========================================")
    logger.info(" 完全無人インテリジェンス工場 パイプライン起動（4ソース同時監視・Fail-Closed統合版）")
    logger.info("==========================================")

    # 0. 事前検証ガード（Notion DB構造チェック）
    if not verify_notion_schema():
        logger.error("Notion DB構造の検証に失敗したため、Gemini APIを呼ぶ前に処理を安全停止（Fail-Closed）します。")
        return

    check_stale_content()

    # 1. 4つの情報源から一括収集
    all_items = fetch_all_sources()

    # 2. ライセンスチェック（Fail-Closed & 安全処理）
    safe_repos = []
    for repo in all_items:
        is_safe, license_status = legal_safety_gate(repo)
        if not is_safe:
            logger.info(f" [SKIP: LICENSE] {repo.get('nameWithOwner')} -> {license_status}")
            continue
        safe_repos.append(repo)

    # 3. 重複防止: 既にNotionに存在するURLを除外
    existing_urls = get_existing_repo_urls()
    deduped_repos = []
    for repo in safe_repos:
        repo_url = (repo.get("url") or "").rstrip("/")
        if repo_url in existing_urls:
            logger.info(f" [SKIP: DUPLICATE] {repo.get('nameWithOwner')} -> 既にNotionに存在するため除外")
            continue
        deduped_repos.append(repo)

    if not deduped_repos:
        logger.info("本日は新規候補が0件でした（全候補が重複または対象外）。")
        return

    # 4. Step 1: 軽量スクリーニング
    logger.info(f">>> [Step 1] 軽量スクリーニング開始（対象 {len(deduped_repos)} 件）")
    screened = []
    try:
        for repo in deduped_repos:
            screened.append(screen_repo(repo))
    except DailyQuotaExhaustedError:
        send_telegram_alert("⚠️ Gemini APIの日次クォータに到達しました（スクリーニング中）。")
        logger.error("日次クォータ到達のため、スクリーニング段階で処理を打ち切ります。")
        return

    screened.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = screened[:TOP_N_FOR_DEEP_DIVE]

    logger.info(
        f">>> [Step 1 結果] 上位{len(top_candidates)}件を深掘り対象に選定: "
        + ", ".join(f"{c['repo'].get('nameWithOwner')}({c['score']}点)" for c in top_candidates)
    )

    # 5. Step 2: 上位N件のみフルレポート生成
    generated_count = 0
    for candidate in top_candidates:
        repo = candidate["repo"]
        name = repo.get("nameWithOwner")
        logger.info(f" [DEEP DIVE] {name}（スクリーニングスコア {candidate['score']}点）")
        try:
            report = generate_intelligence_report(repo)
            if report:
                generated_count += 1
        except DailyQuotaExhaustedError:
            send_telegram_alert("⚠️ Gemini APIの日次クォータに到達しました（深掘り生成中）。")
            break

    if generated_count > 0:
        msg = (
            f"✅ 【AI note事業】本日は{len(deduped_repos)}件をスクリーニングし、"
            f"上位{generated_count}件の完全原稿を生成しました。Notionを確認してください。\n"
            f"[https://notion.so/](https://notion.so/){NOTION_DATABASE_ID}"
        )
        send_telegram_alert(msg)
        logger.info(msg)
    else:
        logger.info("本日は生成条件を満たす記事がありませんでした。")

if __name__ == "__main__":
    main()
