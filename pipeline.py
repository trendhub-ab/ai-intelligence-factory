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
# 1. 環境変数の取得（Secrets設定値と一致）
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GH_PAT = os.environ.get("GH_PAT")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")

if not GEMINI_API_KEY or not GH_PAT:
    raise ValueError("エラー: GEMINI_API_KEY または GH_PAT がSecretsに設定されていません。")

client = genai.Client(api_key=GEMINI_API_KEY)

CANDIDATE_MODELS = os.environ.get(
    "GEMINI_MODEL_CANDIDATES",
    "gemini-3.1-flash-lite,gemini-3.5-flash"
).split(",")

# ==========================================
# 2. Notion プロパティ名の一元管理
# ==========================================
PROP_NAME = "Name"
PROP_URL = "URL"
PROP_SCORE = "Decision Score"
PROP_WHAT = "What"
PROP_WHY_IMPORTANT = "Why Important"
PROP_WHY_NOT_IMPORTANT = "Why NOT Important"
PROP_WHO = "Who"
PROP_ACTION = "Action"

REQUIRED_PROPERTIES = {
    PROP_NAME: "title",
    PROP_URL: "url",
    PROP_SCORE: "number",
    PROP_WHAT: "rich_text",
    PROP_WHY_IMPORTANT: "rich_text",
    PROP_WHY_NOT_IMPORTANT: "rich_text",
    PROP_WHO: "rich_text",
    PROP_ACTION: "rich_text",
}


class NotionSchemaMismatchError(RuntimeError):
    """Notionデータベースのプロパティがコードの期待と一致しない場合に送出"""


def validate_notion_schema():
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        logger.warning("NOTION_API_KEY または NOTION_DATABASE_ID が未設定のためスキーマ検証をスキップします。")
        return

    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            raise NotionSchemaMismatchError(f"Notion DB取得失敗 (Status: {res.status_code}): {res.text}")

        actual_properties = res.json().get("properties", {})
        missing, type_mismatch = [], []

        for name, expected_type in REQUIRED_PROPERTIES.items():
            if name not in actual_properties:
                missing.append(name)
                continue
            actual_type = actual_properties[name]["type"]
            if actual_type != expected_type:
                type_mismatch.append((name, expected_type, actual_type))

        if missing or type_mismatch:
            details = []
            if missing:
                details.append(f"存在しない列: {missing}")
            if type_mismatch:
                details.append("型不一致: " + ", ".join(f"{n}(期待:{e}/実際:{a})" for n, e, a in type_mismatch))
            raise NotionSchemaMismatchError(" / ".join(details))

        logger.info(">>> [事前検証成功] Notionスキーマ検証OK。全プロパティが完全一致しています。")

    except Exception as e:
        error_msg = f"⚠️ 【Notionスキーマ不一致】APIコスト消費前に処理を中断しました: {e}"
        logger.error(error_msg)
        send_discord_alert(error_msg)
        raise SystemExit(1)


# ==========================================
# 3. エラー・モデル管理＆スマートリトライ
# ==========================================
class NoAvailableModelError(RuntimeError):
    """許可リスト内のモデルが全て利用不可だった場合に送出"""


class DailyQuotaExhaustedError(RuntimeError):
    """1日あたりのクォータそのものを使い切った場合に送出"""


def send_discord_alert(message: str):
    if DISCORD_WEBHOOK_URL:
        try:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
        except Exception as e:
            logger.error(f"Discord通知失敗: {e}")


PING_MAX_RETRIES = 3
PING_RETRY_BACKOFF_SECONDS = 12  # 指数バックオフの基準秒数[cite: 1]


def resolve_model(candidates: list[str] = CANDIDATE_MODELS) -> str:
    """
    モデル疎通確認関数。
    503および429(RPM)は同一モデルで最大PING_MAX_RETRIES回バックオフリトライ。[cite: 1]
    404および日次クォータ枯渇(429)は即座に次候補へフォールバック。[cite: 1]
    想定外エラー(401/403等)は即座に例外を送出して中断。[cite: 1]
    """
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
                raise NoAvailableModelError(
                    f"想定外のAPIエラー(code={e.code})のため中断しました: {candidates}"
                ) from e

            except Exception as e:
                last_error = e
                logger.error(f"モデル疎通確認中に想定外の例外: {model_name} ({e})")
                raise NoAvailableModelError(f"想定外の例外のため中断しました: {candidates}") from e

    raise NoAvailableModelError(
        f"リトライ・全候補フォールバックを試みましたが利用可能なモデルがありませんでした: {candidates}"
    ) from last_error


try:
    SELECTED_MODEL = resolve_model()
except NoAvailableModelError as e:
    send_discord_alert(f"⚠️ 【緊急】Geminiモデルの初期化に失敗しました: {e}")
    raise SystemExit(1)


def _extract_retry_delay(exc: Exception, default: int = 20) -> int:
    match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+)", str(exc))
    return int(match.group(1)) if match else default


def _is_daily_quota_exhausted(exc: Exception) -> bool:
    text = str(exc)
    return "free_tier_requests" in text or "PerDay" in text or "Quota exceeded" in text


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
# 4. Notion データベース保存モジュール
# ==========================================
def build_notion_payload(repo_name, repo_url, score, what_text, why_important_text,
                          why_not_important_text, action_text, report_text):
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
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": report_text[:2000]}}]},
            }
        ],
    }


def save_to_notion(repo_name, repo_url, score, what_text, why_important_text,
                    why_not_important_text, action_text, report_text) -> bool:
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        logger.info(f"[NOTION SKIP] {repo_name} -> NOTION_API_KEY/NOTION_DATABASE_ID が未設定です。")
        return False

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    payload = build_notion_payload(
        repo_name, repo_url, score, what_text, why_important_text,
        why_not_important_text, action_text, report_text
    )

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            logger.info(f"[NOTION SAVED] {repo_name} -> Notion DBへの格納完了")
            return True
        logger.error(f"[NOTION ERROR] {repo_name} -> Status: {res.status_code}, {res.text}")
        return False
    except Exception as e:
        logger.error(f"[NOTION EXCEPTION] {repo_name} -> {e}")
        return False


# ==========================================
# 5. 一次データ収集 & 法務ゲート
# ==========================================
def fetch_github_trending():
    print(">>> [Step 1/4] GitHub一次データの自動巡回（上限10件）...")
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
            licenseInfo {{ spdxId name }}
          }}
        }}
      }}
    }}
    """
    try:
        response = requests.post(url, json={"query": query}, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.error(f"GitHub API失敗: {response.status_code} {response.text}")
            return []
        nodes = response.json().get("data", {}).get("search", {}).get("nodes", [])
        print(f"   -> {len(nodes)} 件の一次データ（候補）を取得しました。")
        return nodes
    except Exception as e:
        logger.error(f"GitHub取得中に例外: {e}")
        return []


def legal_safety_gate(repo):
    license_info = repo.get("licenseInfo")
    if not license_info:
        return False, "NO_LICENSE (Fail-Closed)"
    spdx_id = license_info.get("spdxId", "").upper()
    safe_licenses = ["MIT", "APACHE-2.0", "BSD-3-CLAUSE", "BSD-2-CLAUSE", "CC-BY-4.0"]
    return (True, spdx_id) if spdx_id in safe_licenses else (False, f"UNSAFE_LICENSE ({spdx_id})")


def generate_intelligence_report(repo):
    name = repo.get("nameWithOwner")
    desc = repo.get("description", "説明なし")
    url = repo.get("url")
    stars = repo.get("stargazerCount", 0)

    prompt = f"""
あなたは日本のAIエンジニアおよびプロダクトマネージャー向けの「意思決定インテリジェンスアナリスト」です。
以下の海外一次情報を分析し、日本企業がどう判断すべきかに特化した構造化レポートを作成してください。

【対象プロジェクト】
- プロジェクト名: {name}
- URL: {url}
- Stars: {stars}
- 概要: {desc}

【出力フォーマット（Markdown厳守）】
### 【{name}】
- **What (概要)**: 日本語で2文以内で簡潔に説明。
- **Why Important (導入・監視インパクト)**: なぜ今、日本のAI開発現場が注目すべきか。
- **Why NOT Important (スルーしてよい理由)**: どういうチーム・企業は今は対応不要（無視）でよいか。
- **Decision Score**: 100点満点中の点数とその内訳（例: 85/100 - 技術的影響高、緊急性中）
- **Action**: 明日から開発現場やPMがとるべき具体アクション（例: 3ヶ月以内にPoC検証、または静観）。
"""

    try:
        response = call_gemini_with_smart_retry(prompt)
        report_text = response.text

        parse_warnings = []

        score_match = re.search(r"Decision Score[*\s]*:\s*(\d+)", report_text)
        score = int(score_match.group(1)) if score_match else 0
        if not score_match:
            parse_warnings.append("Decision Score抽出失敗(0点でフォールバック)")

        what_match = re.search(r"- \*\*What \(概要\)\*\*:\s*(.*?)(?=\n-|\n\n|$)", report_text, re.DOTALL)
        what_text = what_match.group(1).strip() if what_match else "概要参照"
        if not what_match:
            parse_warnings.append("What抽出失敗")

        why_imp_match = re.search(
            r"- \*\*Why Important \(導入・監視インパクト\)\*\*:\s*(.*?)(?=\n-|\n\n|$)", report_text, re.DOTALL
        )
        why_important_text = why_imp_match.group(1).strip() if why_imp_match else "特記事項なし"
        if not why_imp_match:
            parse_warnings.append("Why Important抽出失敗")

        why_not_imp_match = re.search(
            r"- \*\*Why NOT Important \(スルーしてよい理由\)\*\*:\s*(.*?)(?=\n-|\n\n|$)", report_text, re.DOTALL
        )
        why_not_important_text = why_not_imp_match.group(1).strip() if why_not_imp_match else "特記事項なし"
        if not why_not_imp_match:
            parse_warnings.append("Why NOT Important抽出失敗")

        action_match = re.search(r"- \*\*Action\*\*:\s*(.*?)(?=\n---|###|$)", report_text, re.DOTALL)
        action_text = action_match.group(1).strip() if action_match else "アクション参照"
        if not action_match:
            parse_warnings.append("Action抽出失敗")

        if parse_warnings:
            msg = f"⚠️ 【要人手確認】{name} のレポートでパースに失敗: {'; '.join(parse_warnings)}"
            logger.warning(msg)
            send_discord_alert(msg)

        save_to_notion(name, url, score, what_text, why_important_text,
                        why_not_important_text, action_text, report_text)
        return report_text

    except DailyQuotaExhaustedError:
        send_discord_alert("⚠️ Gemini APIの日次クォータに到達しました。")
        raise
    except Exception as e:
        logger.error(f"Gemini解析エラー ({name}): {e}")
        send_discord_alert(f"⚠️ 【解析失敗】{name} -> {e}")
        return None


# ==========================================
# 6. メイン実行パイプライン
# ==========================================
def main():
    print("==========================================")
    print(" 完全無人インテリジェンス工場 パイプライン起動")
    print("==========================================")

    validate_notion_schema()

    repos = fetch_github_trending()
    reports = []

    for repo in repos:
        name = repo.get("nameWithOwner")
        is_safe, license_status = legal_safety_gate(repo)

        if not is_safe:
            print(f" [SKIP] {name} -> {license_status}")
            continue

        print(f" [ANALYZING] {name} (License: {license_status})")
        try:
            report = generate_intelligence_report(repo)
            if report:
                reports.append(report)
        except DailyQuotaExhaustedError:
            break

    print(f"\n>>> 解析完了: 計 {len(reports)} 件の「意思決定インテリジェンス」を生成・Notion自動同期しました。")

    print("\n================= 最終生成レポート一覧 =================")
    for r in reports:
        print(r)
        print("-" * 50)

    if reports:
        send_discord_alert(f"【インテリジェンス工場】本日の解析およびNotion自動蓄積が完了しました（生成件数: {len(reports)}件）。")


if __name__ == "__main__":
    main()
