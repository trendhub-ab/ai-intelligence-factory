import os
import time
import requests
import json
import google.generativeai as genai

# ==========================================
# 1. 環境変数の取得と初期化
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_PAT = os.environ.get("GITHUB_PAT")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

if not GEMINI_API_KEY or not GITHUB_PAT:
    raise ValueError("エラー: GEMINI_API_KEY または GITHUB_PAT が設定されていません。")

genai.configure(api_key=GEMINI_API_KEY)

# 無料枠（Free Tier）のレート制限（RPM）を回避するためのモデル定義
# Step1: 高速スクリーニング / Step2: 構造化出力
model_flash = genai.GenerativeModel("gemini-1.5-flash")

# ==========================================
# 2. 一次データ収集（GitHub GraphQL API）
# ==========================================
def fetch_github_trending():
    print(">>> [Step 1/4] GitHubトレンドリポジトリの収集開始...")
    url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {GITHUB_PAT}",
        "Content-Type": "application/json"
    }
    
    # 直近の注目のAI/ML関連リポジトリを取得するクエリ
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
    
    response = requests.post(url, json={"query": query}, headers=headers)
    if response.status_code != 200:
        print(f"GitHub API Error: {response.status_code}")
        return []
    
    data = response.json()
    nodes = data.get("data", {}).get("search", {}).get("nodes", [])
    print(f"   -> {len(nodes)} 件の一次データを取得しました。")
    return nodes

# ==========================================
# 3. 法務安全ゲート（ライセンス判定）
# ==========================================
def legal_safety_gate(repo):
    """
    商用利用可能なライセンス（MIT, Apache-2.0, BSD, CC-BY等）かを機械判定
    判定不能・リスクありのものは Fail-Closed 設計により除外
    """
    license_info = repo.get("licenseInfo")
    if not license_info:
        return False, "NO_LICENSE"
    
    spdx_id = license_info.get("spdxId", "").upper()
    safe_licenses = ["MIT", "APACHE-2.0", "BSD-3-CLAUSE", "BSD-2-CLAUSE", "CC-BY-4.0"]
    
    if spdx_id in safe_licenses:
        return True, spdx_id
    else:
        return False, f"UNSAFE_LICENSE ({spdx_id})"

# ==========================================
# 4. 2段階 Gemini 処理（無料枠安全設計）
# ==========================================
def process_with_gemini(repo):
    """
    無料枠の429エラー（RPM制限）を回避するため、リクエスト間に time.sleep を挟む
    """
    name = repo.get("nameWithOwner")
    desc = repo.get("description", "説明なし")
    url = repo.get("url")
    
    prompt = f"""
あなたはプロのAI開発マネージャーです。以下のオープンソースプロジェクトを分析し、実務層向けに要約してください。

プロジェクト名: {name}
概要: {desc}
URL: {url}

以下の出力フォーマット（Markdown）に厳格に従って出力してください。

### 【件名】{name}
- **概要**: (2文で簡潔に)
- **Why Important (導入インパクト)**: (なぜ今注目すべきか)
- **Why NOT Important (無視してよい理由)**: (どういうチームには不要か)
- **Decision Score**: (1〜5点満点とその理由)
- **Action**: (明日からとるべき具体的なアクション)
"""
    try:
        # レート制限（RPM）回避のため、呼び出し前に必ず5秒ウェイト
        time.sleep(5)
        response = model_flash.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini API 呼び出しエラー ({name}): {e}")
        return None

# ==========================================
# 5. メイン実行パイプライン
# ==========================================
def main():
    print("==========================================")
    print(" 完全無人インテリジェンス工場 パイプライン開始")
    print("==========================================")
    
    repos = fetch_github_trending()
    processed_reports = []
    
    print("\n>>> [Step 2/4] 法務安全ゲートおよびGemini解析の実行...")
    for repo in repos:
        name = repo.get("nameWithOwner")
        is_safe, license_status = legal_safety_gate(repo)
        
        if not is_safe:
            print(f" [SKIP] {name} -> 法務リスク検出: {license_status}")
            continue
            
        print(f" [PROCESSING] {name} (License: {license_status})")
        report = process_with_gemini(repo)
        if report:
            processed_reports.append(report)
            
    print(f"\n>>> [Step 3/4] 解析完了: 計 {len(processed_reports)} 件の構造化レポートを生成。")
    
    # 成果物の簡易出力（コンソール表示）
    print("\n================= 生成レポート（一部抜粋） =================")
    for r in processed_reports[:2]:
        print(r)
        print("-" * 40)

    # Webhook通知（Discordが設定されている場合）
    if DISCORD_WEBHOOK_URL and processed_reports:
        print("\n>>> [Step 4/4] Discordへパイプライン完了通知を送信中...")
        msg = {"content": f"【インテリジェンス工場】本日の解析が完了しました。生成件数: {len(processed_reports)}件"}
        requests.post(DISCORD_WEBHOOK_URL, json=msg)

if __name__ == "__main__":
    main()
