import os
import re
import time
import requests
import json
import logging
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

if not GEMINI_API_KEY or not GH_PAT:
    raise ValueError("エラー: GEMINI_API_KEY または GH_PAT がSecretsに設定されていません。")

# 新SDKクライアントの初期化
client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 無料枠の広い軽量モデルを優先配置（無料での完走を担保）
# ==========================================
CANDIDATE_MODELS = os.environ.get(
    "GEMINI_MODEL_CANDIDATES",
    "gemini-3.1-flash-lite,gemini-1.5-flash,gemini-3.5-flash"
).split(",")

class NoAvailableModelError(RuntimeError):
    """許可リスト内のモデルが全て利用不可だった場合に送出"""

class DailyQuotaExhaustedError(RuntimeError):
    """1日あたりのクォータそのものを使い切った場合に送出"""

def resolve_model(candidates: list[str] = CANDIDATE_MODELS) -> str:
    last_error: Exception | None = None

    for model_name in candidates:
        model_name = model_name.strip()
        try:
            client.models.generate_content(
                model=model_name,
                contents="ping",
            )
            logger.info(f"モデル解決成功: {model_name}")
            return model_name

        except APIError as e:
            if e.code == 404:
                logger.warning(f"モデル利用不可(404)のためフォールバック: {model_name}")
                last_error = e
                continue
            else:
                logger.error(f"APIエラー発生のため中断: {model_name} ({e})")
                raise
        except Exception as e:
            logger.error(f"想定外のエラーのためフォールバックせず中断: {model_name} ({e})")
            raise

    raise NoAvailableModelError(f"許可リスト内の全モデルが利用不可でした: {candidates}") from last_error

def send_discord_alert(message: str):
    if DISCORD_WEBHOOK_URL:
        try:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
        except Exception as e:
            logger.error(f"Discord通知失敗: {e}")

# パイプライン起動時にモデルを動的解決
try:
    SELECTED_MODEL = resolve_model()
except NoAvailableModelError:
    alert_msg = "⚠️ 【緊急】全Geminiモデルが利用不可(404)。モデル設定の確認が必要です。"
    send_discord_alert(alert_msg)
    raise SystemExit(1)

# ==========================================
# 2. 429/503 スマートリトライ・ハンドラー
# ==========================================
def _extract_retry_delay(exc: Exception, default: int = 20) -> int:
    """429エラーレスポンスから指定待機時間(秒)を抽出"""
    match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+)", str(exc))
    return int(match.group(1)) if match else default

def _is_daily_quota_exhausted(exc: Exception) -> bool:
    """RPD（日次上限）枯渇か否かを判定"""
    text = str(exc)
    return "free_tier_requests" in text or "PerDay" in text or "Quota exceeded" in text

def call_gemini_with_smart_retry(prompt: str, max_retries: int = 3):
    """
    503: 固定バックオフ(10秒)で再試行
    429(RPM): Google指定のretryDelay待機で再試行
    429(RPD): 即時諦めてDailyQuotaExhaustedErrorを発生（Fail-Closed）
    """
    for attempt in range(max_retries + 1):
        try:
            time.sleep(3) # レート制限回避の基本ウェイト
            return client.models.generate_content(
                model=SELECTED_MODEL,
                contents=prompt,
            )
        except APIError as e:
            if e.code == 503:
                if attempt < max_retries:
                    wait = 10 * (attempt + 1)
                    logger.warning(f"503発生。{wait}秒待機してリトライ ({attempt + 1}/{max_retries})")
                    time.sleep(wait)
                    continue
                raise
            elif e.code == 429:
                if _is_daily_quota_exhausted(e):
                    logger.error("日次クォータ枯渇(RPD)を検知。即座に処理を中断します。")
                    raise DailyQuotaExhaustedError(str(e)) from e
                
                delay = _extract_retry_delay(e)
                if attempt < max_retries:
                    logger.warning(f"429(RPM)発生。指定のretryDelay={delay}秒待機してリトライ")
                    time.sleep(delay)
                    continue
                raise
            else:
                raise
        except Exception as e:
            raise

# ==========================================
# 3. 一次データ収集（GitHub GraphQL API）
# 歩留まり確保のため「上限10件」へ設定
# ==========================================
def fetch_github_trending():
    print(">>> [Step 1/4] GitHub一次データの自動巡回（上限10件）...")
    url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {GH_PAT}",
        "Content-Type": "application/json"
    }
    
    query = """
    {
      search(query: "topic:ai topic:machine-learning stars:>100 pushed:>2026-01-01", type: REPOSITORY, first: 10) {
        nodes {
          ... on Repository {
            nameWithOwner
            url
            description
            stargazerCount
            licenseInfo {
              spdxId
              name
            }
          }
        }
      }
    }
    """
    
    try:
        response = requests.post(url, json={"query": query}, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"GitHub API エラー: Status {response.status_code}")
            return []
        
        data = response.json()
        nodes = data.get("data", {}).get("search", {}).get("nodes", [])
        print(f"   -> {len(nodes)} 件の一次データ（候補）を取得しました。")
        return nodes
    except Exception as e:
        print(f"データ取得例外エラー: {e}")
        return []

# ==========================================
# 4. 法務安全ゲート（ライセンス判定 / Fail-Closed）
# ==========================================
def legal_safety_gate(repo):
    license_info = repo.get("licenseInfo")
    if not license_info:
        return False, "NO_LICENSE (Fail-Closed)"
    
    spdx_id = license_info.get("spdxId", "").upper()
    safe_licenses = ["MIT", "APACHE-2.0", "BSD-3-CLAUSE", "BSD-2-CLAUSE", "CC-BY-4.0"]
    
    if spdx_id in safe_licenses:
        return True, spdx_id
    else:
        return False, f"UNSAFE_LICENSE ({spdx_id})"

# ==========================================
# 5. 意思決定インテリジェンス生成
# ==========================================
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
        return response.text
    except DailyQuotaExhaustedError:
        print(f"   [Quota枯渇] {name} -> 本日のAPI上限に達したため解析を中断します。")
        send_discord_alert("⚠️ Gemini APIの日次クォータに到達しました。")
        raise
    except Exception as e:
        print(f"Gemini解析エラー ({name}): {e}")
        return None

# ==========================================
# 6. メイン実行パイプライン
# ==========================================
def main():
    print("==========================================")
    print(" 完全無人インテリジェンス工場 パイプライン起動")
    print("==========================================")
    
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
            
    print(f"\n>>> 解析完了: 計 {len(reports)} 件の「意思決定インテリジェンス」を生成しました。")
    
    print("\n================= 最終生成レポート（一部抜粋） =================")
    for r in reports[:3]:
        print(r)
        print("-" * 50)

    if reports:
        send_discord_alert(f"【インテリジェンス工場】本日の解析が完了しました（生成件数: {len(reports)}件）。")

if __name__ == "__main__":
    main()
