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

# 環境変数で「深掘りする件数」を調整可能にする
TOP_N_FOR_DEEP_DIVE = int(os.environ.get("TOP_N_FOR_DEEP_DIVE", "3"))

# ==========================================
# 2. Notion プロパティ定義
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

# 管理用データとnote原稿を分離するための構造トークン（Markdown記号ではない専用文字列にして
# clean_markdown_for_note による誤クレンジングや、Geminiによる表記揺れの影響を受けないようにする）
SECTION_SPLIT_TOKEN = "===NOTE_DRAFT_START==="

# 記事内の無料/有料エリアの境界検出。「---有料エリア---」を基本形としつつ、
# 記号の種類・全角半角・スペースの有無が多少ブレても検出できるよう正規表現で許容する。
PAID_AREA_PATTERN = re.compile(
    r"^[\s\-−ー―─━▼◆■●\*]{0,10}\s*有料エリア\s*[\s\-−ー―─━▼◆■●\*]{0,10}$",
    re.MULTILINE
)

# note原稿内に挿入する、コピペしてもそのまま読める有料エリア案内文
NOTE_PAYWALL_LABEL = "\n\n▼▼▼ ここから先は有料エリアです ▼▼▼\n\n"
DIVIDER_LINE = "\n\n" + "─" * 24 + "\n"

# Notionのrich_text 1ブロックあたりの上限(2000文字)に対し、安全マージンを持たせた実運用上限
NOTION_BLOCK_LIMIT = 1900

# 品質ゲート: 有料エリアがこの文字数未満の場合、「薄い記事」とみなし自動リトライする
MIN_PAID_AREA_LENGTH = 1200
# 自動リトライの最大回数（これを超えても閾値未達なら、その案件は生成を諦めて次に進む）
MAX_QUALITY_RETRIES = 2

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
# 4. Markdownクレンジング & note原稿整形
# ==========================================
def clean_markdown_for_note(text: str) -> str:
    """
    Geminiが出力する過剰なMarkdown記号（コードブロック、見出し、太字/斜体、
    箇条書き記号など）を除去し、noteエディタにそのまま貼れるプレーンテキストに変換する。
    """
    if not text:
        return ""

    # コードブロック（```lang ... ```）のバッククォートのみ除去し、中身は残す
    text = re.sub(r"```[a-zA-Z0-9]*\n?", "", text)
    text = text.replace("```", "")
    # インラインコードのバッククォート除去
    text = text.replace("`", "")
    # 見出し記号 (#, ##, ###...) を除去（テキスト自体は保持）
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    # 太字/斜体のアスタリスク・アンダースコアを除去
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    # 箇条書き記号（-, *）を全角中黒「・」に統一
    text = re.sub(r"^\s*[-*]\s+", "・", text, flags=re.MULTILINE)
    # 単独のMarkdown水平線（---, ***, ___）を除去（見出し用マーカーは事前に分離済みの前提）
    text = re.sub(r"^\s*([-*_]){3,}\s*$", "", text, flags=re.MULTILINE)
    # 連続する空行を1つに圧縮
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def split_free_paid(note_draft: str, repo_name: str = ""):
    """
    記事本文を無料エリアと有料エリアに分離する（クレンジング前に実行すること）。
    「---有料エリア---」の厳密一致ではなく、記号・スペースの表記ゆれを許容する
    PAID_AREA_PATTERN で検出する。境界が1件も見つからない場合、全文が無料公開扱いに
    なる（＝有料記事としての価値が消滅する）致命的な事故のため、検出せず出力せず
    Discordへ即時アラートを送る。
    """
    match = PAID_AREA_PATTERN.search(note_draft)
    if not match:
        logger.error(f"[PAID AREA MISSING] {repo_name} -> 有料エリア境界を検出できませんでした。")
        send_discord_alert(
            f"🚨【要手動確認】{repo_name} の原稿で有料エリア境界を検出できませんでした。"
            f"全文が無料エリア扱いになっている可能性があるため、Notion側の原稿を確認してから公開してください。"
        )
        return note_draft.strip(), ""

    free_part = note_draft[:match.start()]
    paid_part = note_draft[match.end():]
    return free_part.strip(), paid_part.strip()

def build_clean_note_manuscript(note_draft: str, repo_name: str, repo_url: str, spdx_id: str) -> str:
    """
    note投稿用の最終原稿を組み立てる:
      1. 無料エリア / 有料エリアを分離
      2. それぞれMarkdown記号をクレンジング
      3. 有料エリア境界に人間が読める案内文を挿入
      4. 出典元メタデータを末尾に自動挿入
    """
    free_part, paid_part = split_free_paid(note_draft, repo_name)
    free_clean = clean_markdown_for_note(free_part)
    paid_clean = clean_markdown_for_note(paid_part)

    manuscript = free_clean
    if paid_clean:
        manuscript += NOTE_PAYWALL_LABEL + paid_clean

    source_block = (
        f"{DIVIDER_LINE}"
        f"出典元\n"
        f"リポジトリ: {repo_name}\n"
        f"公式リンク: {repo_url}\n"
        f"ライセンス: {spdx_id}\n"
        f"※本記事はライセンスが公開・再利用可能な条件（MIT / Apache-2.0 / BSD / CC-BY-4.0等）"
        f"であることを確認した上で分析・要約しています。\n"
    )
    manuscript += source_block
    return manuscript.strip()

# ==========================================
# 5. Notion 保存モジュール（note原稿流し込み対応）
# ==========================================
def safe_chunk_text(text: str, limit: int = NOTION_BLOCK_LIMIT) -> list[str]:
    """
    Notionのrich_text 1ブロックあたりの文字数上限に収まるよう、テキストを分割する。
    単純な text[i:i+2000] のような文字数スライスは、文や単語の途中で強制的に
    ブロックを分断してしまい、note貼り付け時の可読性・見た目を損なうため使わない。
    優先順位: 1) 改行（段落）単位でまとめる → 2) 1行が上限を超える場合は文末
    （。！？）単位で分割 → 3) それでも1文が上限を超える場合のみ最終手段として
    文字数で分割する。
    """
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

        # 1行が上限を超える場合は文末記号（。！？）を優先して分割
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
                # 文末記号すら見つからない極端な長文のみ、最終手段として文字数で分割
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

    # noteに使う完全原稿を、文や段落の途中で切れないようNotionブロックへ安全分割
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
# 6. 一次データ収集 & 法務ゲート
# ==========================================
def fetch_github_trending():
    logger.info(">>> [Step 1] GitHub一次データの自動巡回...")
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
            logger.info(f"   -> {len(nodes)} 件の候補を取得。")
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

読者はGitHubのREADMEを自分で読めます。読者が金を払うのは、README要約ではなく、
「このプロジェクトが既存の何を置き換えようとしているのか」「なぜ今のタイミングで
意味を持つのか」「導入した場合の移行コストとリスクは何か」という一段深い分析です。
以下の分析軸を必ず満たしてください。

- 技術的パラダイムシフト: このプロジェクトは既存のアプローチの何を否定・刷新しようと
  しているか。単なる機能追加ではなく、設計思想・アーキテクチャレベルの変化を特定すること。
- 代替との比較: 同じ課題を解決している既存OSS・商用ツールを最低1つ具体名で挙げ、
  何が決定的に違うのかを名指しで説明すること（比較対象を挙げずに「優れている」と
  断定するのは禁止）。
- 移行コストとリスク: 既存システムから乗り換える場合に発生する作業・学習コスト・
  破壊的変更のリスクを具体的に見積もること。

【対象プロジェクト】
・名前: {name}
・URL: {url}
・Stars: {stars}
・概要: {desc}

【出力ルール（厳守）】
・出力は以下のフォーマットに厳密に従うこと。項目の省略・順序変更は禁止。
・Markdownのコードブロック（```）、太字（**）、見出し記号（#）は一切使用しないこと。
・箇条書きは半角ハイフン「-」ではなく、全角中黒「・」を使うこと（note貼り付け時に
  ハイフンが番号付きリストと誤認識されるのを防ぐため）。
・数値は算用数字で、指定の満点内に収めること。
・管理用データの直後には、必ず改行してから "{SECTION_SPLIT_TOKEN}" という行だけを
  単独で挿入し、その後にnote原稿本文を続けること。
・note原稿本文中、無料エリアと有料エリアの境目には、必ず「---有料エリア---」という
  行だけを単独で挿入すること（前後に他の文字を付けないこと）。

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
思える深さと具体性で書く。）
"""

def _parse_gemini_response(full_text: str) -> dict:
    """Geminiの応答を管理用データとnote原稿に分割し、各項目を抽出する。"""
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
    """クレンジング後の有料エリアの文字数を返す（品質ゲートの判定基準）。"""
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
            send_discord_alert(
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
        send_discord_alert("⚠️ Gemini APIの日次クォータに到達しました。")
        raise
    except Exception as e:
        logger.error(f"Gemini解析エラー ({name}): {e}")
        return None

# ==========================================
# Step 1: 軽量スクリーニング
# ==========================================
def build_screening_prompt(name, desc, stars) -> str:
    return f"""
以下のOSSプロジェクトについて、CTO/PM向け有料note記事の題材としての価値を
0〜100点で採点せよ。判断基準: 技術的な新規性・実務への即効性・話題性。

・名前: {name}
・Stars: {stars}
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
        logger.error(f"[SCREENING FAILED] {name}: {e}")
        send_discord_alert(f"⚠️ スクリーニング失敗: {name} ({e.code if hasattr(e, 'code') else e})")
        return {"repo": repo, "score": 0, "reason": "スクリーニング失敗"}
    except Exception as e:
        logger.error(f"[SCREENING UNEXPECTED ERROR] {name}: {e}")
        send_discord_alert(f"⚠️ スクリーニング中の想定外エラー: {name} ({e})")
        return {"repo": repo, "score": 0, "reason": "想定外エラー"}

# ==========================================
# 8. メイン実行パイプライン（Two-Stage版）
# ==========================================
def main():
    logger.info("==========================================")
    logger.info(" 完全無人インテリジェンス工場 パイプライン起動（Two-Stage版）")
    logger.info("==========================================")

    repos = fetch_github_trending()

    safe_repos = []
    for repo in repos:
        is_safe, license_status = legal_safety_gate(repo)
        if not is_safe:
            logger.info(f" [SKIP: LICENSE] {repo.get('nameWithOwner')} -> {license_status}")
            continue
        safe_repos.append(repo)

    logger.info(f">>> [Step 2] 軽量スクリーニング開始（対象 {len(safe_repos)} 件）")
    screened = []
    try:
        for repo in safe_repos:
            screened.append(screen_repo(repo))
    except DailyQuotaExhaustedError:
        send_discord_alert("⚠️ Gemini APIの日次クォータに到達しました（スクリーニング中）。")
        logger.error("日次クォータ到達のため、スクリーニング段階で処理を打ち切ります。")
        return

    screened.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = screened[:TOP_N_FOR_DEEP_DIVE]

    logger.info(
        f">>> [Step 2 結果] 上位{len(top_candidates)}件を深掘り対象に選定: "
        + ", ".join(f"{c['repo'].get('nameWithOwner')}({c['score']}点)" for c in top_candidates)
    )

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
            send_discord_alert("⚠️ Gemini APIの日次クォータに到達しました（深掘り生成中）。")
            break

    if generated_count > 0:
        msg = (
            f"✅ 【AI note事業】本日は{len(safe_repos)}件をスクリーニングし、"
            f"上位{generated_count}件の完全原稿を生成しました。Notionを確認してください。\n"
            f"[https://notion.so/](https://notion.so/){NOTION_DATABASE_ID}"
        )
        send_discord_alert(msg)
        logger.info(msg)
    else:
        logger.info("本日は生成条件を満たす記事がありませんでした。")

if __name__ == "__main__":
    main()
```[cite: 1]
