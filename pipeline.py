import os
import time
import requests
import json
import google.generativeai as genai

# ==========================================
# 1. 環境変数の取得（Secrets設定値と一致）
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GH_PAT = os.environ.get("GH_PAT")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

if not GEMINI_API_KEY or not GH_PAT:
    raise ValueError("エラー: GEMINI_API_KEY または GH_PAT がSecretsに設定されていません。")

genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# 【2026年最新モデル指定】
# 安定稼働と高速処理を両立する最新のFlashモデル
# ==========================================
try:
    model = genai.GenerativeModel("models/gemini-2.5-flash")
except Exception:
    model = genai.GenerativeModel("gemini-2.5-flash")

# ==========================================
# 2. 一次データ収集（GitHub GraphQL API）
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
# 3. 法務安全ゲート（ライセンス判定 / Fail-Closed）
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
# 4. 意思決定インテリジェンス生成（Gemini API）
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
        # レート制限回避（RPM対策）のため必ず5秒待機
        time.sleep(5)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini解析エラー ({name}): {e}")
        return None

# ==========================================
# 5. メイン実行パイプライン
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
        report = generate_intelligence_report(repo)
        if report:
            reports.append(report)
            
    print(f"\n>>> 解析完了: 計 {len(reports)} 件の「意思決定インテリジェンス」を生成しました。")
    
    print("\n================= 最終生成レポート（一部抜粋） =================")
    for r in reports[:3]:
        print(r)
        print("-" * 50)

    if DISCORD_WEBHOOK_URL and reports:
        msg = {"content": f"【インテリジェンス工場】本日の解析が完了しました（生成件数: {len(reports)}件）。"}
        requests.post(DISCORD_WEBHOOK_URL, json=msg)

if __name__ == "__main__":
    main()
