import os
import re
import time
import requests
import logging
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
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")

if not GEMINI_API_KEY or not GH_PAT:
    raise ValueError("エラー: GEMINI_API_KEY または GH_PAT が設定されていません。")

client = genai.Client(api_key=GEMINI_API_KEY)

CANDIDATE_MODELS = os.environ.get(
    "GEMINI_MODEL_CANDIDATES",
    "gemini-3.1-flash-lite,gemini-3.5-flash"
).split(",")

# ==========================================
# 2. Notion プロパティ定義
# ==========================================
PROP_NAME = "Name"
PROP_URL = "URL"
PROP_SCORE = "Decision Score"
PROP_WHAT = "What"
PROP_WHY_IMPORTANT = "Why Important"
PROP_WHY_NOT_IMPORTANT = "Why NOT Important"
PROP_WHO = "Who"
PROP_ACTION = "Action"

# ==========================================
# 3. エラー・モデル管理＆スマートリトライ
# ==========================================
class NoAvailableModelError(RuntimeError): pass
class DailyQuotaExhaustedError(RuntimeError): pass

def send_discord_alert(message: str):
    if DISCORD_WEBHOOK_URL:
        try:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
        except Exception as e:
            logger.error(f"Discord通知失敗: {e}")

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
    send_discord_alert(f"⚠️ 【緊急】Gemini初期化失敗: {e}")
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
# 4. Notion 保存モジュール（note原稿流し込み対応）
# ==========================================
def build_notion_payload(repo_name, repo_url, score, what_text, why_important_text,
                          why_not_important_text, action_text, note_draft):
    
    # note原稿が2000文字を超える場合のNotionブロック分割処理
    chunks = [note_draft[i:i+2000] for i in range(0, len(note_draft), 2000)]
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
            PROP_WHAT: {"rich_text": [{"text": {"content": what_text[:2000]}}]},
            PROP_WHY_IMPORTANT: {"rich_text": [{"text": {"content": why_important_text[:2000]}}]},
            PROP_WHY_NOT_IMPORTANT: {"rich_text": [{"text": {"content": why_not_important_text[:2000]}}]},
            PROP_WHO: {"rich_text": [{"text": {"content": "PM / テックリード / 開発チーム"}}]},
            PROP_ACTION: {"rich_text": [{"text": {"content": action_text[:2000]}}]},
        },
        "children": children_blocks,
    }

def save_to_notion(repo_name, repo_url, score, what_text, why_important_text,
                    why_not_important_text, action_text, note_draft) -> bool:
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        return False
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    payload = build_notion_payload(
        repo_name, repo_url, score, what_text, why_important_text,
        why_not_important_text, action_text, note_draft
    )
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            logger.info(f"[NOTION SAVED] {repo_name} -> note完全原稿の保存完了")
            return True
        logger.error(f"[NOTION ERROR] {repo_name} -> {res.text}")
        return False
    except Exception as e:
        logger.error(f"[NOTION EXCEPTION] {e}")
        return False

# ==========================================
# 5. 一次データ収集 & 法務ゲート & note原稿同時生成
# ==========================================
def fetch_github_trending():
    print(">>> [Step 1] GitHub一次データの自動巡回...")
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
            print(f"   -> {len(nodes)} 件の候補を取得。")
            return nodes
    except Exception as e:
        logger.error(f"GitHub APIエラー: {e}")
    return []

def legal_safety_gate(repo):
    license_info = repo.get("licenseInfo")
    if not license_info: return False, "NO_LICENSE"
    spdx_id = license_info.get("spdxId", "").upper()
    safe = ["MIT", "APACHE-2.0", "BSD-3-CLAUSE", "BSD-2-CLAUSE", "CC-BY-4.0"]
    return (True, spdx_id) if spdx_id in safe else (False, f"UNSAFE ({spdx_id})")

def generate_intelligence_report(repo):
    name = repo.get("nameWithOwner")
    desc = repo.get("description", "説明なし")
    url = repo.get("url")
    stars = repo.get("stargazerCount", 0)

    prompt = f"""
あなたは月刊数十万円を売り上げる技術系noteのトップWebライター兼アナリストです。
以下の対象プロジェクトを分析し、「データベース管理用の構造化データ」と「noteにそのままコピペできる有料記事の完全原稿」を生成してください。

【対象プロジェクト】
- 名前: {name}
- URL: {url}
- Stars: {stars}
- 概要: {desc}

【出力フォーマット（Markdown厳守）】
以下の構成で正確に出力してください。

### 【管理用データ】
- **What (概要)**: 日本語で2文以内で説明。
- **Why Important (導入インパクト)**: なぜ注目すべきか。
- **Why NOT Important (スルーしてよい理由)**: 対応不要な条件。
- **Decision Score**: 100点満点中の点数（例: 85）
- **Action**: 明日からとるべき具体アクション。

### 【note投稿用完全原稿】
（ここに目を引くキャッチーな記事タイトル）

（ここに無料エリアの文章：WhatとWhy Importantの冒頭を自然な記事調で構成）

---有料エリア---

（ここに有料エリアの文章：Why Importantの詳細、Why NOT Important、具体的なActionを読者が満足する深い記事調で構成）
"""

    try:
        response = call_gemini_with_smart_retry(prompt)
        full_text = response.text

        # データ分割（管理用データとnote原稿を分離）
        parts = full_text.split("### 【note投稿用完全原稿】")
        management_data = parts[0]
        note_draft = parts[1].strip() if len(parts) > 1 else "原稿生成に失敗しました。"

        score_match = re.search(r"Decision Score[*\s]*:\s*(\d+)", management_data)
        score = int(score_match.group(1)) if score_match else 0
        
        what_match = re.search(r"- \*\*What[^\:]*:\s*(.*?)(?=\n-|\n\n|$)", management_data, re.DOTALL)
        what_text = what_match.group(1).strip() if what_match else "概要参照"

        why_imp_match = re.search(r"- \*\*Why Important[^\:]*:\s*(.*?)(?=\n-|\n\n|$)", management_data, re.DOTALL)
        why_important_text = why_imp_match.group(1).strip() if why_imp_match else "特記事項なし"

        why_not_imp_match = re.search(r"- \*\*Why NOT Important[^\:]*:\s*(.*?)(?=\n-|\n\n|$)", management_data, re.DOTALL)
        why_not_important_text = why_not_imp_match.group(1).strip() if why_not_imp_match else "特記事項なし"

        action_match = re.search(r"- \*\*Action[^\:]*:\s*(.*?)(?=\n-|\n\n|$)", management_data, re.DOTALL)
        action_text = action_match.group(1).strip() if action_match else "アクション参照"

        save_to_notion(name, url, score, what_text, why_important_text, why_not_important_text, action_text, note_draft)
        return note_draft

    except DailyQuotaExhaustedError:
        send_discord_alert("⚠️ Gemini APIの日次クォータに到達しました。")
        raise
    except Exception as e:
        logger.error(f"Gemini解析エラー ({name}): {e}")
        return None

# ==========================================
# 6. メイン実行パイプライン
# ==========================================
def main():
    print("==========================================")
    print(" 完全無人インテリジェンス工場 パイプライン起動")
    print("==========================================")

    repos = fetch_github_trending()
    generated_count = 0

    for repo in repos:
        name = repo.get("nameWithOwner")
        is_safe, license_status = legal_safety_gate(repo)
        if not is_safe: continue

        print(f" [ANALYZING & WRITING] {name}")
        try:
            report = generate_intelligence_report(repo)
            if report: generated_count += 1
        except DailyQuotaExhaustedError:
            break

    if generated_count > 0:
        msg = f"✅ 【AI note事業】本日のnote用完全原稿が {generated_count} 件生成され、Notionに配置されました。コピペして公開してください。\nhttps://notion.so/{NOTION_DATABASE_ID}"
        send_discord_alert(msg)
        print(msg)

if __name__ == "__main__":
    main()
