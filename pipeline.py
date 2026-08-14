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

# Product Huntのみ認証必須（Developer Token）。Hacker News / ArXivは認証不要。
# 未設定でもパイプライン全体は止めず、Product Hunt収集のみをスキップする
# （Fail-Safe設計。詳細はfetch_producthunt_trending内のガードを参照）。
PRODUCTHUNT_DEVELOPER_TOKEN = os.environ.get("PRODUCTHUNT_DEVELOPER_TOKEN")

if not GEMINI_API_KEY or not GH_PAT:
    raise ValueError("エラー: GEMINI_API_KEY または GH_PAT が設定されていません。")

client = genai.Client(api_key=GEMINI_API_KEY)

def _generate_via_chat(model_name: str, prompt: str, config: dict | None = None):
    """
    google-genai SDK推奨のChat.send_message経由でGeminiを呼び出す薄いラッパー。

    【背景】
    Models.generate_content を直接呼び出すと、SDK側から
    "Direct use of automatic function calling (AFC) in Models.generate_content
    is not recommended. Instead, we recommend to use AFC in Chat.send_message."
    という非推奨警告が毎回出力される。これは単なるログ汚れではなく、
    SDKの将来のバージョンアップでModels.generate_content周りの挙動・互換性が
    変わった場合に、無人運用中のパイプラインが予告なく停止するリスクを孕む。

    【方針】
    本パイプラインの各呼び出しは、それぞれ独立した1問1答（前ターンの文脈を
    引き継がない）であるため、呼び出しのたびに使い捨てのChatセッションを
    生成し、1回だけsend_messageする形に統一する。これにより会話継続の状態を
    一切持たせず、既存の「呼び出し単位で完結する」という挙動を変えないまま、
    SDK推奨のエントリーポイントへ置き換える。
    """
    chat = client.chats.create(model=model_name, config=config) if config else client.chats.create(model=model_name)
    return chat.send_message(prompt)

CANDIDATE_MODELS = os.environ.get(
    "GEMINI_MODEL_CANDIDATES",
    "gemini-3.1-flash-lite,gemini-3.5-flash"
).split(",")

# 深掘り（Step2フルレポート）に回す件数（Two-Stage化）
TOP_N_FOR_DEEP_DIVE = int(os.environ.get("TOP_N_FOR_DEEP_DIVE", "3"))

# 滞留検知: 最終記事生成からこの日数を超えたら運用者に通知
STALE_THRESHOLD_DAYS = int(os.environ.get("STALE_THRESHOLD_DAYS", "10"))

# ---- Gemini無料枠(RPM)保護のためのチューニングパラメータ ----
# マルチソース化により1回の実行でスクリーニング対象がGitHub単独時より
# 大幅に増える（最大4ソース分）。スクリーニングは深掘り生成と異なり
# 出力トークンが極小(30 tokens)で1件あたりのレイテンシが短いため、
# 間隔を空けずに連続実行するとRPM上限を容易に超過してしまう。
# そのため、1件ごとに最低限のペーシングを強制する。
SCREENING_PACING_SECONDS = int(os.environ.get("SCREENING_PACING_SECONDS", "4"))

# 収集ソースが将来さらに増えてもRPD・RPMへの影響を一定範囲に抑え込むための
# スクリーニング対象数の上限（安全弁）。これを超えた分は「収集はしたが
# 審査対象からは除外」としてログに残す（黙って切り捨てない）。
MAX_SCREENING_CANDIDATES = int(os.environ.get("MAX_SCREENING_CANDIDATES", "40"))

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
# note記事タイトル（コピーライター調のキャッチータイトル）を独立プロパティとして
# 構造化保存するためのキー。以前はnote_draft本文の先頭行に埋め込まれたまま
# 扱われており、Notion側でタイトルだけを抽出・一覧表示・ソートすることが
# できなかった。_extract_note_title()で本文から分離した上でここに保存する。
PROP_TITLE = "Note Title"
# マルチソース化に伴い追加: Notion側でソース別の絞り込み・ビュー分割を
# 可能にするための構造化プロパティ。従来はsourceがnote本文末尾の
# テキストにしか埋め込まれておらず、フィルタ・ソートができなかった。
PROP_SOURCE = "Source"
# 人気指標（GitHub Stars / HN Score / PH Votes）を横断的に数値として保持。
# ArXivは指標が存在しないため0を格納する（screen_repo/decision prompt側の
# ENGAGEMENT_LABELSと対応）。
PROP_ENGAGEMENT = "Engagement Score"

# 管理用データとnote原稿を分離するための構造トークン（Markdown記号ではない専用文字列にして
# normalize_markdown_for_note による処理や、Geminiによる表記揺れの影響を受けないようにする）
SECTION_SPLIT_TOKEN = "===NOTE_DRAFT_START==="

# 記事内の無料/有料エリアの境界検出。「---有料エリア---」を基本形としつつ、
# 記号の種類・全角半角・スペースの有無が多少ブレても検出できるよう正規表現で許容する。
# 「有料エリア」という文字列を必須にしているため、note.com対応Markdownとして
# 別途使われる素の水平線「---」（区切り線）と誤って衝突することはない。
PAID_AREA_PATTERN = re.compile(
    r"^[\s\-−ー―─━▼◆■●\*]{0,10}\s*有料エリア\s*[\s\-−ー―─━▼◆■●\*]{0,10}$",
    re.MULTILINE
)

# note原稿内に挿入する、コピペしてもそのまま読める有料エリア案内文。
# note.comのMarkdownペースト対応により太字（**）がそのまま強調表示される。
NOTE_PAYWALL_LABEL = "\n\n**▼▼▼ ここから先は有料エリアです ▼▼▼**\n\n"
# note.com公式Markdown（--- で区切り線）としてそのまま反映される水平線
DIVIDER_LINE = "\n\n---\n\n"

# Notionのrich_text 1ブロックあたりの上限(2000文字)に対し、安全マージンを持たせた実運用上限
NOTION_BLOCK_LIMIT = 1900

# 品質ゲート: 有料エリアがこの文字数未満の場合、「薄い記事」とみなし自動リトライする
# プロンプト側の目標を1600字に引き上げたため、閾値1200字には十分なバッファがある。
MIN_PAID_AREA_LENGTH = 1200
# 自動リトライの最大回数（これを超えても閾値未達なら、その案件は生成を諦めて次に進む）
MAX_QUALITY_RETRIES = 2

# ==========================================
# 3. エラー・モデル管理＆スマートリトライ
# ==========================================
class NoAvailableModelError(RuntimeError): pass
class DailyQuotaExhaustedError(RuntimeError): pass

def send_telegram_alert(message: str):
    """運用者(自分)宛のアラート通知。Telegram Bot API経由で送信する。
    購読者向けの通知ではなく、あくまで運用監視用。"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_BOT_TOKEN または TELEGRAM_CHAT_ID が未設定のため通知をスキップします。")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message[:4000],  # Telegramのメッセージ長上限(4096)に対する安全マージン
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
                _generate_via_chat(model_name, "ping", config={"max_output_tokens": 8})
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
            return _generate_via_chat(SELECTED_MODEL, prompt)
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
# 4. Markdown整形 & note原稿組み立て
# ==========================================
# note.com公式ヘルプで案内されている新エディタのMarkdownショートカット
# （## 見出し、**太字**、- 箇条書き、--- 区切り線 等）に対応しているため、
# 従来のように記号を全部剥がしてプレーンテキスト化するのではなく、
# 正規のMarkdownとしてそのまま保持する方針に変更している。
# ここでは「Geminiが稀に混入させる崩れ（全体を```で包む等）」だけを
# 安全に取り除く、軽量な正規化のみを行う。

# 【note.comの太字（**）認識に関する既知の癖】
# note.comのMarkdownペースト機能は、**の直後・直前が「」『』（）等の括弧記号や
# 引用符である場合に、太字として正しく認識できないことがある
# （例: **「重要な用語」** は太字化されず記号がそのまま残ることがある一方、
# 括弧を外側に出した 「**重要な用語**」 は正しく太字化される）。
# プロンプト側でもこのパターンを避けるよう明示的に指示しているが、
# 生成AIの出力ゆれに対する保険として、太字が括弧付きの語を丸ごと囲んで
# いるだけの単純なケースに限り、括弧を太字の外側へ機械的に移動させる。
_BOLD_BOUNDARY_BRACKET_FIXES = [
    (re.compile(r"\*\*「([^「」]+)」\*\*"), r"「**\1**」"),
    (re.compile(r"\*\*『([^『』]+)』\*\*"), r"『**\1**』"),
    (re.compile(r"\*\*（([^（）]+)）\*\*"), r"（**\1**）"),
    (re.compile(r'\*\*"([^"]+)"\*\*'), r'"**\1**"'),
    (re.compile(r"\*\*'([^']+)'\*\*"), r"'**\1**'"),
]

def _fix_bold_boundary_brackets(text: str) -> str:
    """
    太字（**）が括弧・引用符付きの語を丸ごと囲んでいる場合、
    note.com側で太字として認識されるよう、括弧を太字の外側へ移動する。
    括弧が太字全体の先頭と末尾を完全に囲んでいる単純なケースのみを対象とし、
    太字の一部だけに括弧が掛かっている複雑なケースは誤変換を避けるため対象外とする。
    """
    for pattern, repl in _BOLD_BOUNDARY_BRACKET_FIXES:
        text = pattern.sub(repl, text)
    return text

def normalize_markdown_for_note(text: str) -> str:
    """
    note.comのMarkdownペースト機能にそのまま乗せられる形へ軽く正規化する。
    Markdown記法（見出し・太字・箇条書き・区切り線）は一切除去せず保持する。
    """
    if not text:
        return ""

    stripped = text.strip()
    # Geminiが応答全体を1個の```（コードフェンス）で誤って包んでしまう
    # ケースのみ、外側のフェンスだけを安全に剥がす（中身のMarkdownは保持）。
    fence_match = re.match(r"^```[a-zA-Z0-9]*\n(.*)\n```$", stripped, re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1)

    # 万一Geminiが箇条書きに全角中黒「・」を使ってしまった場合の保険として、
    # note.comが公式対応する「- ＋半角スペース」記法に変換する。
    stripped = re.sub(r"^\s*・\s*", "- ", stripped, flags=re.MULTILINE)

    # 太字の内側先頭・末尾が括弧記号のケースを補正（note.com側の太字認識対策）。
    stripped = _fix_bold_boundary_brackets(stripped)

    # 連続する空行を1つに圧縮（Markdownの段落区切りとしては空行1つで十分なため）
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.strip()

def split_free_paid(note_draft: str, repo_name: str = ""):
    """
    記事本文を無料エリアと有料エリアに分離する（正規化前に実行すること）。
    「---有料エリア---」の厳密一致ではなく、記号・スペースの表記ゆれを許容する
    PAID_AREA_PATTERN で検出する。境界が1件も見つからない場合、全文が無料公開扱いに
    なる（＝有料記事としての価値が消滅する）致命的な事故のため、検出せず出力せず
    Telegramへ即時アラートを送る。
    """
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

# GitHub以外のソース向け「出典についての注記」。
# 「ライセンス確認済み」という事実と異なる主張（=存在しない審査の主張）はせず、
# 各ソースの性質に即した権利表記のみを行う。これにより、note記事の出典元
# ブロックがソースによって行数が変わる不自然さ（読者から見た「記載漏れ疑惑」）を防ぎ、
# かつ内容としても正確な表記を維持する。
SOURCE_RIGHTS_NOTE = {
    "HackerNews": (
        "- **出典について**: 本記事はHacker Newsで話題となった公開情報"
        "（記事タイトル・スコア等）を基に独自に分析・要約したものです。"
        "リンク先記事本文の著作権は原著作者に帰属します。\n"
    ),
    "ArXiv": (
        "- **出典について**: 本記事はarXivで公開されている論文の要旨・情報を基に"
        "独自に分析・要約したものです。論文本文の著作権は著者に帰属します。\n"
    ),
    "ProductHunt": (
        "- **出典について**: 本記事はProduct Huntで公開されているプロダクト情報を基に"
        "独自に分析・要約したものです。製品名・商標等は各権利者に帰属します。\n"
    ),
}

def build_clean_note_manuscript(note_draft: str, repo_name: str, repo_url: str,
                                 spdx_id: str, source: str = "GitHub") -> str:
    """
    note投稿用の最終原稿をMarkdown形式で組み立てる:
      1. 無料エリア / 有料エリアを分離
      2. それぞれをnote.com対応Markdownへ軽量正規化（記法は保持）
      3. 有料エリア境界に人間が読める案内文を挿入
      4. 出典元メタデータ（ソース種別込み）をMarkdownの箇条書きで末尾に自動挿入

    こうして生成された文字列はMarkdownとしてNotionに保存され、
    note.comの新エディタへそのまま貼り付けるだけで見出し・太字・箇条書き・
    区切り線が自動的に反映される（note.com公式のMarkdownペースト対応による）。

    source（GitHub/HackerNews/ArXiv/ProductHunt）により、末尾の権利表記を出し分ける。
    GitHubは「ライセンス確認済み」という審査結果を表記する一方、OSSライセンスの
    概念を持たないソースには同じ文言を使い回さず、SOURCE_RIGHTS_NOTEで定義した
    ソース固有の出典注記を必ず1行以上出す（事実と異なる主張を避けつつ、
    出典元ブロックの構造をソース間で揃えるため）。
    """
    free_part, paid_part = split_free_paid(note_draft, repo_name)
    free_clean = normalize_markdown_for_note(free_part)
    paid_clean = normalize_markdown_for_note(paid_part)

    manuscript = free_clean
    if paid_clean:
        manuscript += NOTE_PAYWALL_LABEL + paid_clean

    if source == "GitHub":
        rights_line = (
            f"- **ライセンス**: {spdx_id}\n\n"
            f"※本記事はライセンスが公開・再利用可能な条件（MIT / Apache-2.0 / BSD / CC-BY-4.0等）"
            f"であることを確認した上で分析・要約しています。\n"
        )
    else:
        rights_line = SOURCE_RIGHTS_NOTE.get(source, "")

    source_block = (
        f"{DIVIDER_LINE}"
        f"### 出典元\n"
        f"- **ソース**: {source}\n"
        f"- **名称**: {repo_name}\n"
        f"- **公式リンク**: [{repo_name}]({repo_url})\n"
        f"{rights_line}"
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
                          alternative_comparison_text="", migration_cost_text="",
                          source: str = "GitHub", engagement: int = 0, title_text: str = ""):

    # noteにそのままコピペできるよう、Markdown原稿を1つのcodeブロック
    # （language: markdown）として保存する。paragraphブロックに分割していた
    # 旧実装と異なり、Notion UI上でブロック単位の「コピー」ボタン1回で
    # 原稿全体をMarkdownの生テキストとして丸ごとコピーできる。
    # rich_text 1要素あたり2000字の上限があるため、これまで通り
    # safe_chunk_textで安全な区切り位置ごとに分割するが、複数の
    # rich_text要素を同一のcodeブロックへ連結することで、見た目上は
    # 1本の連続したMarkdown原稿として表示・コピーされる。
    chunks = safe_chunk_text(clean_manuscript)
    children_blocks = [
        {
            "object": "block",
            "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": chunk}} for chunk in chunks],
                "language": "markdown",
            },
        }
    ]

    return {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            PROP_NAME: {"title": [{"text": {"content": repo_name}}]},
            PROP_URL: {"url": repo_url},
            PROP_SOURCE: {"select": {"name": source}},
            PROP_ENGAGEMENT: {"number": engagement},
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
            PROP_TITLE: {"rich_text": [{"text": {"content": (title_text or "（タイトル抽出失敗）")[:2000]}}]},
        },
        "children": children_blocks,
    }

def save_to_notion(repo_name, repo_url, score, score_breakdown_text, what_text,
                    why_important_text, why_not_important_text, action_text,
                    spdx_id, clean_manuscript, paradigm_shift_text="",
                    alternative_comparison_text="", migration_cost_text="",
                    source: str = "GitHub", engagement: int = 0, title_text: str = "") -> bool:
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
        alternative_comparison_text, migration_cost_text,
        source, engagement, title_text
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
# 6. 一次データ収集（マルチソース） & 法務ゲート
# ==========================================
#
# 【アーキテクチャ方針】
# GitHub / Hacker News / ArXiv / Product Hunt はレスポンス形式が
# JSON（構造バラバラ） / JSON / XML(Atom) / GraphQL と全く異なる。
# これをソースごとの fetch_* 関数の「出口」で必ず normalize_item() に通し、
# 統一フォーマット NormalizedItem（辞書型）に変換してから返す。
# これ以降のメイン処理（法務ゲート・重複排除・Two-Stageスクリーニング・
# 深掘り生成）は、この NormalizedItem のキーだけを見て動作し、
# データの出所を一切意識しない。
#
# 【障害の局所化】
# 各 fetch_* 関数は内部で例外を個別にキャッチし、失敗時はログを出して
# 空リストを返す（Fail-Safe）。1ソースがダウンしても他ソースの収集・
# 以降のパイプライン全体には一切影響しない。main() 側は各関数の戻り値を
# 単純にリスト結合するだけでよく、try/exceptで囲む必要がない。

# ソースごとの「人気指標」のラベル。GitHubのStars相当が存在しないソース
# （ArXiv）もあるため、スクリーニング/深掘りプロンプト側で正しく文脈を
# 伝えるために使う。
ENGAGEMENT_LABELS = {
    "GitHub": "Stars",
    "HackerNews": "HN Score",
    "ArXiv": "N/A(人気指標なし)",
    "ProductHunt": "Votes",
}

def normalize_item(source: str, name: str, url: str, description: str,
                    engagement: int, license_info: dict | None = None) -> dict:
    """
    データ正規化層（Normalized Gateway）の中核関数。
    全ソースのレスポンスをこの1関数だけを通して共通フォーマットに変換する。

    キー名はGitHub GraphQLレスポンスの語彙（nameWithOwner, stargazerCount等）
    に合わせている。これは既存のTwo-Stageスクリーニング処理・Notion保存処理
    が既にこの語彙に依存しているため、メイン処理側を一切変更せずに
    他ソースを差し込めるようにするための互換性維持策であり、他意はない。

    - source: "GitHub" | "HackerNews" | "ArXiv" | "ProductHunt"
    - license_info: GitHub以外は None（＝ライセンスの概念が存在しないソース）。
      legal_safety_gate() 側で source を見て、GitHub以外は自動的に
      ライセンスゲートの対象外として通過させる。
    """
    return {
        "source": source,
        "nameWithOwner": (name or "無題").strip() or "無題",
        "url": (url or "").strip(),
        "description": (description or "説明なし").strip() or "説明なし",
        "stargazerCount": engagement or 0,
        "licenseInfo": license_info,
    }

def fetch_github_trending():
    """GitHub GraphQL API から急上昇AI/MLリポジトリを取得する。"""
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
    items = []
    try:
        response = requests.post(url, json={"query": query}, headers=headers, timeout=10)
        if response.status_code == 200:
            nodes = response.json().get("data", {}).get("search", {}).get("nodes", [])
            for node in nodes:
                license_info = node.get("licenseInfo")
                items.append(normalize_item(
                    source="GitHub",
                    name=node.get("nameWithOwner"),
                    url=node.get("url"),
                    description=node.get("description"),
                    engagement=node.get("stargazerCount", 0),
                    license_info=license_info,
                ))
            logger.info(f"   -> GitHub {len(items)} 件の候補を取得。")
        else:
            logger.error(f"[FAULT ISOLATED] GitHub APIエラー: HTTP {response.status_code}")
    except Exception as e:
        # 障害の局所化: GitHub側の障害・仕様変更が起きても、
        # 他ソースの収集を止めないよう空リストで握りつぶす。
        logger.error(f"[FAULT ISOLATED] GitHub APIエラー: {e}")
    return items

def fetch_hackernews_top(limit: int = 10):
    """
    Hacker News API（Firebase公式・認証不要）から上位ストーリーを取得する。
    まずtopstories.jsonでID一覧を取得し、各IDの詳細を個別取得する2段構成。
    ストーリー1件単位の取得失敗は個別に握りつぶし、他の取得は継続する。
    """
    logger.info(">>> [Step 1] Hacker News一次データの自動巡回...")
    items = []
    try:
        ids_res = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
        )
        ids_res.raise_for_status()
        story_ids = ids_res.json()[:limit]

        for story_id in story_ids:
            try:
                item_res = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                    timeout=10,
                )
                item_res.raise_for_status()
                data = item_res.json() or {}
                if data.get("type") != "story":
                    continue
                items.append(normalize_item(
                    source="HackerNews",
                    name=data.get("title"),
                    url=data.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
                    description=data.get("title"),
                    engagement=data.get("score", 0),
                ))
            except Exception as e:
                logger.warning(f"[HN ITEM SKIP] id={story_id}: {e}")
                continue

        logger.info(f"   -> Hacker News {len(items)} 件の候補を取得。")
    except Exception as e:
        # 障害の局所化: Hacker News側の障害でも他ソースの収集は継続する。
        logger.error(f"[FAULT ISOLATED] Hacker News APIエラー: {e}")
        items = []
    return items

# ArXiv取得用の軽量リトライ設定。export.arxiv.orgは他ソース（GitHub/HN: timeout=10）
# より低速・不安定な傾向があり、timeout延長（15s→25s）だけでは「25秒でも
# 間に合わないほど遅い/詰まっている」瞬間的な障害を救えない。
# Notion問い合わせ（_query_notion_db_with_retry）と同様のパターンで、
# 短い間隔を空けて数回だけ再試行してから最終的な失敗と判定する。
# ArXivはFail-Safe対象（0件でも他ソースでパイプラインは継続する）ため、
# Notion側のFail-Closedほど粘る必要はなく、回数・間隔とも控えめにする。
ARXIV_FETCH_MAX_RETRIES = 2
ARXIV_FETCH_RETRY_BACKOFF_SECONDS = 5


def _fetch_arxiv_with_retry(url: str, params: dict):
    """
    ArXiv APIへのGETリクエストを実行し、一時的な失敗（タイムアウト・接続エラー・
    HTTPエラー）には短い間隔で数回だけ再試行する。全て失敗した場合はNoneを返す。
    XMLパース自体はここでは行わない（呼び出し元でraw responseを見る前提）。
    """
    last_error_text = ""
    for attempt in range(ARXIV_FETCH_MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=25)
            response.raise_for_status()
            return response
        except Exception as e:
            last_error_text = str(e)
            logger.warning(
                f"[ARXIV FETCH RETRY] 取得失敗"
                f"（試行{attempt + 1}/{ARXIV_FETCH_MAX_RETRIES + 1}）: {e}"
            )

        if attempt < ARXIV_FETCH_MAX_RETRIES:
            time.sleep(ARXIV_FETCH_RETRY_BACKOFF_SECONDS * (attempt + 1))

    logger.error(f"[ARXIV FETCH FAILED] リトライ上限到達。最終エラー: {last_error_text}")
    return None


def fetch_arxiv_ai_ml(limit: int = 10):
    """
    ArXiv API（認証不要・XML/Atom形式）からAI/ML分野
    （cs.AI, cs.LG）の最新論文を取得する。
    レスポンスはJSONではなくAtom XMLのため、他ソースと異なり
    xml.etree.ElementTreeでパースしてからnormalize_item()に通す。
    エントリ単位のパース失敗は個別に握りつぶす。
    HTTPリクエスト自体の一時的な失敗（タイムアウト等）は
    _fetch_arxiv_with_retry内で数回リトライしてから諦める。

    【既知の落とし穴・search_queryへの生の"+"埋め込み禁止】
    以前の実装では search_query の値に "cat:cs.AI+OR+cat:cs.LG" のように
    論理演算子の区切りとして生の"+"を直接埋め込んでいた。requestsのparams
    辞書経由でリクエストを送ると、値の中に含まれる生の"+"は本来のスペース
    ("+"はURLエンコード上スペースを表す特殊文字)と区別するため"%2B"へ
    二重エスケープされてしまう。結果としてarXiv側には
    "search_query=cat%3Acs.AI%2BOR%2Bcat%3Acs.LG" が送信され、
    AND/OR演算子として認識されない不正なクエリとなり、
    エラーにはならないままヒット0件（空のAtomフィード）が返っていた
    （この現象はarxiv.py等の外部ライブラリでも既知の不具合として報告されている）。
    対策として、区切りには生の"+"ではなく通常の半角スペースを使う。
    これによりrequestsが自動でスペースを"+"へエンコードし、
    arXiv APIが期待する "cat:cs.AI+OR+cat:cs.LG" という正しい形が
    実際のHTTPリクエストとして送信される。
    """
    logger.info(">>> [Step 1] ArXiv一次データの自動巡回...")
    items = []
    url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": "cat:cs.AI OR cat:cs.LG",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": limit,
    }
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        response = _fetch_arxiv_with_retry(url, params)
        if response is None:
            # リトライ上限到達。ArXivはFail-Safe対象なので、ここで例外を上げず
            # 空リストのまま呼び出し元（main）へ返し、他ソースでの続行を優先する。
            logger.error("[FAULT ISOLATED] ArXiv APIエラー: リトライ後も取得に失敗しました。")
            return items

        root = ET.fromstring(response.content)

        for entry in root.findall("atom:entry", ns):
            try:
                title = (entry.findtext("atom:title", default="", namespaces=ns) or "")
                summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "")

                link = ""
                for link_el in entry.findall("atom:link", ns):
                    if link_el.get("rel") == "alternate":
                        link = link_el.get("href", "")
                        break
                if not link:
                    link = entry.findtext("atom:id", default="", namespaces=ns) or ""

                items.append(normalize_item(
                    source="ArXiv",
                    name=re.sub(r"\s+", " ", title).strip(),
                    url=link.strip(),
                    description=re.sub(r"\s+", " ", summary).strip()[:500],
                    engagement=0,  # ArXivにはStars/Votes相当の人気指標が存在しないため0固定
                ))
            except Exception as e:
                logger.warning(f"[ARXIV ENTRY SKIP] {e}")
                continue

        logger.info(f"   -> ArXiv {len(items)} 件の候補を取得。")
    except Exception as e:
        # 障害の局所化: XMLパース失敗・HTTPエラーいずれもここで吸収する。
        logger.error(f"[FAULT ISOLATED] ArXiv APIエラー: {e}")
        items = []
    return items

def fetch_producthunt_trending(limit: int = 10):
    """
    Product Hunt GraphQL API（無料枠）から注目プロダクトを取得する。
    Hacker News / ArXivと異なり Developer Token による認証が必須。
    未設定の場合は取得自体を安全にスキップし（クラッシュさせない）、
    他3ソースでのパイプライン続行を優先する。
    """
    logger.info(">>> [Step 1] Product Hunt一次データの自動巡回...")
    if not PRODUCTHUNT_DEVELOPER_TOKEN:
        logger.warning(
            "[PH SKIP] PRODUCTHUNT_DEVELOPER_TOKEN が未設定のため、"
            "Product Huntの取得をスキップします（他ソースは継続します）。"
        )
        return []

    items = []
    url = "https://api.producthunt.com/v2/api/graphql"
    headers = {
        "Authorization": f"Bearer {PRODUCTHUNT_DEVELOPER_TOKEN}",
        "Content-Type": "application/json",
    }
    query = """
    query TrendingPosts($first: Int!) {
      posts(order: VOTES, first: $first) {
        edges {
          node {
            name
            tagline
            description
            url
            website
            votesCount
          }
        }
      }
    }
    """
    try:
        response = requests.post(
            url,
            json={"query": query, "variables": {"first": limit}},
            headers=headers,
            timeout=15,
        )
        if response.status_code != 200:
            logger.error(
                f"[FAULT ISOLATED] Product Hunt APIエラー: "
                f"HTTP {response.status_code} {response.text[:200]}"
            )
            return []

        payload = response.json()
        if "errors" in payload:
            logger.error(f"[FAULT ISOLATED] Product Hunt GraphQLエラー: {payload['errors']}")
            return []

        edges = payload.get("data", {}).get("posts", {}).get("edges", [])
        for edge in edges:
            try:
                node = edge.get("node", {})
                items.append(normalize_item(
                    source="ProductHunt",
                    name=node.get("name"),
                    url=node.get("website") or node.get("url"),
                    description=node.get("tagline") or node.get("description"),
                    engagement=node.get("votesCount", 0),
                ))
            except Exception as e:
                logger.warning(f"[PH ITEM SKIP] {e}")
                continue

        logger.info(f"   -> Product Hunt {len(items)} 件の候補を取得。")
    except Exception as e:
        # 障害の局所化: 認証エラー・レート制限・仕様変更いずれもここで吸収する。
        logger.error(f"[FAULT ISOLATED] Product Hunt APIエラー: {e}")
        items = []
    return items

def legal_safety_gate(repo):
    """
    OSSライセンスの法務ゲート。
    GitHub以外（Hacker News / ArXiv / Product Hunt）はそもそも
    「OSSライセンス」という概念を持たないソースのため、
    source を見てゲート対象外として自動的に通過させる（"N/A"扱い）。
    誤ってライセンス欄が空のGitHubリポジトリを通過させないよう、
    GitHub由来の判定ロジック自体は従来通り厳格に維持する。
    """
    source = repo.get("source", "GitHub")
    if source != "GitHub":
        return True, "N/A"

    license_info = repo.get("licenseInfo")
    if not license_info: return False, "NO_LICENSE"
    spdx_id = license_info.get("spdxId", "").upper()
    safe = ["MIT", "APACHE-2.0", "BSD-3-CLAUSE", "BSD-2-CLAUSE", "CC-BY-4.0"]
    return (True, spdx_id) if spdx_id in safe else (False, f"UNSAFE ({spdx_id})")

# ==========================================
# 重複防止: Notion DBに既に存在するリポジトリURLを取得
# ==========================================
# 重複チェック用の軽量リトライ設定。Notion側の一時的なタイムアウト等だけで
# 毎回パイプラインが止まると運用が疲弊するため、短い間隔で数回だけ再試行して
# から最終的な失敗（＝重複チェック不能）と判定する。
DEDUP_CHECK_MAX_RETRIES = 2
DEDUP_CHECK_RETRY_BACKOFF_SECONDS = 10


def _query_notion_db_with_retry(url: str, headers: dict, payload: dict):
    """
    Notion DBクエリ（1ページ分）を実行し、一時的な失敗（HTTPエラー・例外）には
    短い間隔で数回だけ再試行する。全て失敗した場合はNoneを返す。
    """
    last_error_text = ""
    for attempt in range(DEDUP_CHECK_MAX_RETRIES + 1):
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                return res
            last_error_text = f"HTTP {res.status_code}: {res.text}"
            logger.warning(
                f"[DEDUP CHECK] Notion問い合わせ失敗"
                f"（試行{attempt + 1}/{DEDUP_CHECK_MAX_RETRIES + 1}）: {last_error_text}"
            )
        except Exception as e:
            last_error_text = str(e)
            logger.warning(
                f"[DEDUP CHECK] Notion問い合わせ例外"
                f"（試行{attempt + 1}/{DEDUP_CHECK_MAX_RETRIES + 1}）: {e}"
            )

        if attempt < DEDUP_CHECK_MAX_RETRIES:
            time.sleep(DEDUP_CHECK_RETRY_BACKOFF_SECONDS * (attempt + 1))

    logger.error(f"[DEDUP CHECK] リトライ上限到達。最終エラー: {last_error_text}")
    return None


def get_existing_repo_urls():
    """
    Notion DB内の全ページからURLプロパティを収集し、集合として返す。
    Step1のスクリーニング対象からこれらを除外することで、
    同一リポジトリの重複生成・重複投稿を防ぐ。

    ページネーション対応: DB件数が100件を超えても全件走査する。

    【Fail-Closed方針】
    重複チェックは「過去配信済みの記事を誤って重複公開しない」ための
    安全装置である。失敗時に処理を続行（Fail-Safe）すると、既配信の案件が
    スクリーニング〜深掘り生成〜Notion保存まで素通りし、最悪の場合そのまま
    有料記事として重複公開されてしまう。これは購読者の信頼を損なう重大な
    経営リスクのため、短い再試行を挟んだ上でなお失敗する場合は、重複チェック
    不能としてNoneを返し、呼び出し元（main）でその日のパイプラインを
    安全停止させる。

    戻り値:
      - set: 既存URLの集合（0件でも正常時はset()）
      - None: リトライしても取得できず、重複チェック不能と判定された場合
              （呼び出し元はこれをFail-Closedのトリガーとして扱うこと）
    """
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        # Notion未設定の場合はそもそも保存自体が行われないため、
        # 重複チェック自体が意味を持たない（Fail-Closedの対象外）。
        return set()

    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    existing_urls = set()
    next_cursor = None

    while True:
        payload = {"page_size": 100}
        if next_cursor:
            payload["start_cursor"] = next_cursor

        res = _query_notion_db_with_retry(url, headers, payload)
        if res is None:
            logger.error(
                "[DEDUP CHECK FAILED] リトライ後もNotion問い合わせに失敗したため、"
                "重複チェック不能と判定します（Fail-Closed）。"
            )
            send_telegram_alert(
                "🚨【緊急停止】重複チェック（Notion問い合わせ）が"
                f"{DEDUP_CHECK_MAX_RETRIES + 1}回の試行後も失敗したため、"
                "本日のパイプラインを安全停止しました。"
                "過去配信済み記事の重複公開を防ぐためのFail-Closed動作です。"
                "Notion側の状態を確認の上、再実行してください。"
            )
            return None

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

# ==========================================
# 7. 「判断装置」プロンプト & 解析
# ==========================================
def build_decision_prompt(name, url, stars, desc, quality_feedback: str = "", source: str = "GitHub"):
    feedback_block = f"""
【重要・前回の生成に対する差し戻し】
前回の出力は有料エリアの分量・具体性が不足しており、有料記事として採用できませんでした。
{quality_feedback}
今回は上記を踏まえ、有料エリアの代替比較・移行コストとリスク・Decision Scoreの根拠を、
それぞれ具体的な固有名詞・数値・手順を交えてより深く掘り下げて書き直してください。
""" if quality_feedback else ""

    metric_label = ENGAGEMENT_LABELS.get(source, "Stars")
    metric_note = (
        "※このソースには人気指標が存在しないため、この数値は無視し、"
        "内容そのものの新規性・実務インパクトのみで判断すること。\n"
        if source == "ArXiv" else ""
    )

    tone_instruction = """
【文体のルール（重要）】
・海外ソースの翻訳・要約であることを感じさせない、こなれた自然な日本語で書くこと。
　直訳調（「〜ということができるだろう」「〜であると言える」等の硬い言い回し）は避ける。
・一人称視点の語り口を使ってよい（例：「正直、最初に見たとき驚いた」
　「個人的に気になったのはここ」）。ただし、実際に検証・導入していない操作や
　体験を「自分でやってみた」「実際に使ってみたところ」のように断定的に書くことは禁止。
　あくまで原文・一次情報から読み取れる事実の範囲で、驚き・関心・違和感といった
　感想レベルの一人称表現にとどめること（体験の捏造は不可）。
・読者に語りかける口語表現を適度に使う（「〜と思いませんか」「ここ、地味に大事です」等）。
　ただし乱用せず、分析としての説得力・具体性を落とさない範囲にとどめること。
・段落の冒頭を「これは」「つまり」等の紋切り型ではなく、自然な会話の出だしのように
　変化させること。
"""

    title_instruction = """
【タイトルのルール（重要）】
・タイトルは、プロのコピーライターが書いたようなキャッチーさ・インパクトを持たせること。
　テック系ブログの見出しをそのまま翻訳したような、説明的で平板なタイトルは禁止。
・以下のいずれかの型を、内容に合わせて使い分けること（機械的な使い回しは避ける）。
  - ギャップ・意外性型：常識と結論のズレを見せる（例：「◯◯を捨てた企業が増えている理由」）
  - 具体数字型：スコアや規模感を数字で見せる（例：「たった1行で、◯◯が変わった」）
  - 当事者への問いかけ型：読者自身に判断を迫る（例：「その乗り換え、今週決めていいですか」）
  - 断定・警句型：短く言い切る（例：「◯◯はもう、選択肢ではない」）
・誇張・釣りタイトル（内容が伴わない煽り）は禁止。本文の分析内容と矛盾しない
　範囲でのインパクトに留めること。
・句読点や記号を使いすぎず、1行で読める長さ（目安20〜32文字程度）に収めること。
"""

    return f"""
{feedback_block}あなたは月額1,980円の有料購読者（CTO・テックリード・PM）が「読んで即・業務判断ができた」
と満足する、技術系note「判断装置（Decision Intelligence）」の専属アナリスト兼トップライターです。

読者は一次情報（{source}の原文・投稿・論文本体）を自分で読めます。読者が金を払うのは、
その要約ではなく、「これが既存の何を置き換えようとしているのか」「なぜ今のタイミングで
意味を持つのか」「導入・追随した場合のコストとリスクは何か」という一段深い分析です。
以下の分析軸を必ず満たしてください。

- 技術的パラダイムシフト: この対象は既存のアプローチの何を否定・刷新しようと
  しているか。単なる機能追加ではなく、設計思想・アーキテクチャレベルの変化を特定すること。
- 代替との比較: 同じ課題を解決している既存の手段（OSS・商用ツール・競合プロダクト・
  先行研究等）を最低1つ具体名で挙げ、何が決定的に違うのかを名指しで説明すること
  （比較対象を挙げずに「優れている」と断定するのは禁止）。
- 移行コストとリスク: 既存の手段から乗り換える／追随する場合に発生する作業・学習コスト・
  破壊的変更のリスクを具体的に見積もること。
{tone_instruction}{title_instruction}
【対象案件】
・出所: {source}
・名前: {name}
・URL: {url}
・{metric_label}: {stars}
{metric_note}・概要: {desc}

【出力ルール（厳守）】
・出力は以下のフォーマットに厳密に従うこと。項目の省略・順序変更は禁止。
・数値は算用数字で、指定の満点内に収めること。
・管理用データの直後には、必ず改行してから "{SECTION_SPLIT_TOKEN}" という行だけを
  単独で挿入し、その後にnote原稿本文を続けること。

【管理用データのルール】
・管理用データ内の各項目は、全角中黒「・」で始めること（Notionのプロパティへの
  自動抽出に使うための機械可読フォーマットであり、note本文としては使われない）。

【note原稿本文のルール（重要）】
・note原稿本文は、note.com公式の新エディタが対応しているMarkdown記法で出力すること
  （そのままnote.comの編集画面へ貼り付けるだけで見出し・強調・箇条書き・区切り線が
  自動的に反映される）。
・小見出しには "### " を使うこと（有料エリア内の主要項目の区切りに活用する）。
・重要な固有名詞・数値・結論は "**太字**" で強調すること。
・太字にする際、括弧記号「」『』（）や引用符は太字の内側に含めないこと
  （note.comのMarkdownペースト機能は、**の直後・直前が括弧記号の場合に
  太字として認識できないことがあるため）。括弧付きの用語を強調する場合は、
  括弧を太字の外側に出すこと。
  誤: **「重要な用語」**　→　正: 「**重要な用語**」
・箇条書きは半角ハイフン「- 」（ハイフン＋半角スペース）を使うこと（note.comの
  Markdownペースト機能が公式対応している記法のため、全角中黒は使わないこと）。
・note原稿本文中、無料エリアと有料エリアの境目には、必ず「---有料エリア---」という
  行だけを単独で挿入すること（前後に他の文字を付けないこと）。
・この境界マーカー以外の目的で、単独行の「---」（水平線）を使わないこと
  （境界検出処理との誤衝突を避けるため）。
・コードブロック（```）は本記事の性質上不要なため使わないこと。
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

（読者の興味を引くキャッチーな記事タイトル。1行。上記【タイトルのルール】に
従い、プロのコピーライター水準のインパクトを持たせること。note.comのタイトル欄に
別途貼り付けることを想定し、見出し記号「#」は付けないこと。）

（無料エリア：What、Why Important、技術的パラダイムシフトの要点を、記事として
自然に読める文章で構成する。読者に価値の全貌を感じさせつつ、続きへの期待を持たせる
分量で書く。キーワードは適宜「**太字**」で強調してよい。）

---有料エリア---

（有料エリア：代替との比較、移行コストとリスク、Decision Scoreの各項目の詳細な根拠、
Why NOT Important、そして今週中に取るべきActionを、読者が「1980円払って良かった」と
思える深さと具体性で書く。「### 」小見出しで項目ごとに区切り、箇条書きが適切な
情報は「- 」で列挙すること。目安として全体で1600字以上を目標とし、各項目とも
2〜3文の説明で終わらせず、具体的な固有名詞・数値・手順を交えて掘り下げること。
分量が不足する内容の薄い書き方は禁止。）
"""

def _extract_note_title(note_draft_raw: str) -> tuple[str, str]:
    """
    note原稿の先頭行を記事タイトルとして抽出し、残りの本文と分離する。

    プロンプト側の出力フォーマットでは、SECTION_SPLIT_TOKEN直後に
    「タイトル行 → 空行 → 無料エリア本文 → ---有料エリア--- → 有料エリア本文」
    という構成を指示している。以前はこのタイトル行を本文から分離しておらず、
    build_clean_note_manuscript側でもそのまま「無料エリアの一部」として
    扱われてしまい、Notionの独立プロパティとして構造化できなかった
    （またタイトルが実質的に記事本文の1行目として二重表示される形になっていた）。

    ここでタイトル行を切り出し、残りの本文（無料エリア〜有料エリア）だけを
    後続処理（split_free_paid等）に渡すことで、
    - Notion側にタイトルだけを独立プロパティとして保存できる
    - note本文側にタイトルが重複して出力されない
    の両方を実現する。
    """
    lines = note_draft_raw.split("\n")
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1

    if idx >= len(lines):
        # タイトル行を含め本文が実質空だったケース。管理用データのパースは
        # 継続できるよう、ここでは例外を投げずフォールバック値を返す。
        return "（タイトル生成失敗）", note_draft_raw

    # 万一Geminiが見出し記号やクォート・カギ括弧でタイトルを囲んでしまった
    # 場合の軽い保険（プロンプト側では明示的に禁止しているが、出力ゆれに備える）。
    title = lines[idx].strip().lstrip("#").strip().strip('"「」『』').strip()
    remaining = "\n".join(lines[idx + 1:]).strip()
    return (title or "（タイトル生成失敗）"), remaining


def _parse_gemini_response(full_text: str) -> dict:
    """Geminiの応答を管理用データとnote原稿に分割し、各項目を抽出する。"""
    # データ分割（管理用データとnote原稿を分離）。Markdown非依存の専用トークンで分割するため、
    # Geminiが見出し記号を出力ゆれさせてもパースが壊れない。
    parts = full_text.split(SECTION_SPLIT_TOKEN)
    management_data = parts[0]

    if len(parts) > 1:
        title_text, note_draft = _extract_note_title(parts[1].strip())
    else:
        title_text, note_draft = "（タイトル抽出失敗）", "原稿生成に失敗しました。"

    # 項目間の区切りは全角中黒「・」の次の項目、または文末までとする
    NEXT_ITEM = r"(?=\n・|\n\n|$)"

    # 合計スコア抽出
    total_match = re.search(r"合計[:：]?\s*(\d+)\s*/\s*100", management_data)
    score = int(total_match.group(1)) if total_match else 0

    # 各サブスコアをまとめて保存（Notionのブレークダウン列用）
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
        "title_text": title_text,
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
    return len(normalize_markdown_for_note(paid_part))

def generate_intelligence_report(repo):
    name = repo.get("nameWithOwner")
    desc = repo.get("description", "説明なし")
    url = repo.get("url")
    stars = repo.get("stargazerCount", 0)
    source = repo.get("source", "GitHub")
    is_safe, spdx_id = legal_safety_gate(repo)

    quality_feedback = ""
    parsed = None
    paid_len = 0

    try:
        # 品質ゲート: 有料エリアがMIN_PAID_AREA_LENGTH未満なら、不足点を明示して
        # Geminiに自動で書き直させる。人間の手作業を挟まない前提のため、
        # 「警告」は人間向けの通知ではなく、次の生成へのフィードバックとして使う。
        for attempt in range(MAX_QUALITY_RETRIES + 1):
            prompt = build_decision_prompt(name, url, stars, desc, quality_feedback, source)
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
            # AIによる自動リトライを使い切っても基準を満たせなかった案件。
            # 人間に「直して」とは言わず、パイプラインの健全性を可視化するための運用ログとして通知する。
            logger.error(f"[QUALITY GATE FAILED] {name}: {MAX_QUALITY_RETRIES}回のリトライでも基準未達のためスキップ")
            send_telegram_alert(
                f"ℹ️ {name} は{MAX_QUALITY_RETRIES}回のAI自動リトライでも有料エリアの分量基準"
                f"（{MIN_PAID_AREA_LENGTH}文字）を満たせなかったため、今回は生成をスキップしました。"
            )
            return None

        # note用のクリーンな最終原稿（無料/有料分離 + 出典元メタデータ付き）を生成
        clean_manuscript = build_clean_note_manuscript(parsed["note_draft"], name, url, spdx_id, source)

        save_to_notion(
            name, url, parsed["score"], parsed["score_breakdown_text"], parsed["what_text"],
            parsed["why_important_text"], parsed["why_not_important_text"], parsed["action_text"],
            spdx_id, clean_manuscript, parsed["paradigm_shift_text"],
            parsed["alternative_comparison_text"], parsed["migration_cost_text"],
            source, stars, parsed["title_text"]
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
def build_screening_prompt(name, desc, stars, source: str = "GitHub") -> str:
    # 出力を極小に抑えるため、フォーマットを1行に固定する。
    # ここでMarkdown記号や長文説明を許すと出力トークンが無駄に膨らむため厳禁。
    metric_label = ENGAGEMENT_LABELS.get(source, "Stars")
    metric_note = (
        "※このソースには人気指標が存在しないため無視し、内容のみで判断せよ。\n"
        if source == "ArXiv" else ""
    )
    return f"""
以下の{source}発の一次情報について、CTO/PM向け有料note記事の題材としての価値を
0〜100点で採点せよ。判断基準: 技術的な新規性・実務への即効性・話題性。
出所が異なる案件同士でも公平に比較できるよう、指標の絶対値ではなく
内容の質・インパクトを軸に採点すること。

・出所: {source}
・名前: {name}
・{metric_label}: {stars}
{metric_note}・概要: {desc}

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
    """Step1: 軽量スコアリングのみ行う。失敗しても例外を外に投げず0点扱いにする
    （1件のスクリーニング失敗でパイプライン全体を止めないため）。
    503（一時的な過負荷）のみ、深掘り側と同様に軽くリトライする。"""
    name = repo.get("nameWithOwner")
    desc = repo.get("description", "説明なし")
    stars = repo.get("stargazerCount", 0)
    source = repo.get("source", "GitHub")
    prompt = build_screening_prompt(name, desc, stars, source)

    # マルチソース化でスクリーニング対象が増えたため、429(RPM超過)にも
    # 再試行の余地を持たせる（503のみ対応の旧実装から拡張）。
    SCREENING_MAX_RETRIES = 2
    for attempt in range(SCREENING_MAX_RETRIES + 1):
        try:
            # RPM上限保護: 候補が多いソース構成でも一定間隔を空けてから呼び出す。
            time.sleep(SCREENING_PACING_SECONDS)
            response = _generate_via_chat(
                SELECTED_MODEL,
                prompt,
                config={"max_output_tokens": 30},  # 1行しか返させないため極小に固定
            )
            parsed = _parse_screening_response(response.text)
            logger.info(f"[SCREENED] {name}: {parsed['score']}点 ({parsed['reason']})")
            return {"repo": repo, "score": parsed["score"], "reason": parsed["reason"]}
        except DailyQuotaExhaustedError:
            raise  # これだけは呼び出し元に伝播させ、当日の処理を打ち切らせる
        except APIError as e:
            if e.code == 503 and attempt < SCREENING_MAX_RETRIES:
                logger.warning(f"[SCREENING RETRY] {name}: 503のため再試行します。")
                time.sleep(10)
                continue
            if e.code == 429:
                if _is_daily_quota_exhausted(e):
                    raise DailyQuotaExhaustedError(str(e)) from e
                if attempt < SCREENING_MAX_RETRIES:
                    # Googleが返すretryDelayに従って待機してから再試行する。
                    # ここを503と同じ「即0点扱い」にしてしまうと、RPM超過が
                    # 起きただけの正常な候補を誤って「価値なし」と切り捨てて
                    # しまうため、深掘り生成側と同じ待機付きリトライを行う。
                    delay = _extract_retry_delay(e)
                    logger.warning(f"[SCREENING RATE LIMIT] {name}: 429のため{delay}秒待機して再試行します。")
                    time.sleep(delay)
                    continue
            # スクリーニング1件のAPIエラーは致命的ではないため0点扱いでスキップし、
            # ただし可視化のためログとTelegramには残す。
            logger.error(f"[SCREENING FAILED] {name}: {e}")
            send_telegram_alert(f"⚠️ スクリーニング失敗: {name} ({e.code if hasattr(e, 'code') else e})")
            return {"repo": repo, "score": 0, "reason": "スクリーニング失敗"}
        except Exception as e:
            logger.error(f"[SCREENING UNEXPECTED ERROR] {name}: {e}")
            send_telegram_alert(f"⚠️ スクリーニング中の想定外エラー: {name} ({e})")
            return {"repo": repo, "score": 0, "reason": "想定外エラー"}


# ==========================================
# 滞留検知: N日間新記事が0件なら運用者に通知
# ==========================================
def check_stale_content():
    """
    Notion DBの最新ページ作成日を確認し、STALE_THRESHOLD_DAYS日以上
    新規ページが作成されていなければ運用者(Telegram)に通知する。

    注意: これは購読者への告知ではない。運用者が「そろそろ購読者への
    説明を検討すべきか」を判断するためのトリガーに過ぎない。
    """
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        logger.warning("Notion未設定のため滞留検知をスキップします。")
        return

    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
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

        latest_created_str = results[0]["created_time"]  # 例: "2026-08-01T09:00:00.000Z"
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
# 8. メイン実行パイプライン（Two-Stage版・重複防止対応）
# main()はファイル内でこの1箇所のみに定義すること
# ==========================================
def main():
    logger.info("==========================================")
    logger.info(" 完全無人インテリジェンス工場 パイプライン起動（Two-Stage版・マルチソース対応）")
    logger.info("==========================================")

    check_stale_content()

    # ---- マルチソース一次データ収集 ----
    # 各fetch_*関数は内部で例外を個別にキャッチし、失敗時は空リストを返す
    # Fail-Safe構造になっているため、ここでは単純にリスト結合するだけでよい。
    # 1ソースがダウン・仕様変更していても、他ソースの収集と後続処理は継続する。
    github_items = fetch_github_trending()
    hackernews_items = fetch_hackernews_top()
    arxiv_items = fetch_arxiv_ai_ml()
    producthunt_items = fetch_producthunt_trending()

    repos = github_items + hackernews_items + arxiv_items + producthunt_items
    logger.info(
        f"[MULTI-SOURCE] 収集内訳 -> GitHub:{len(github_items)}件 "
        f"HackerNews:{len(hackernews_items)}件 ArXiv:{len(arxiv_items)}件 "
        f"ProductHunt:{len(producthunt_items)}件 (合計 {len(repos)}件)"
    )

    # ライセンスNGは最初に弾く（Step1のAPI呼び出し自体を無駄にしないため）
    # GitHub以外のソースはlegal_safety_gate内で自動的に"N/A"として通過する。
    safe_repos = []
    for repo in repos:
        is_safe, license_status = legal_safety_gate(repo)
        if not is_safe:
            logger.info(f" [SKIP: LICENSE] {repo.get('nameWithOwner')} -> {license_status}")
            continue
        safe_repos.append(repo)

    # ---- 重複防止: 既にNotionに存在する案件を除外（ソース横断で判定） ----
    # Fail-Closed方針: 重複チェックが不能（None）の場合、安全性を保証できないため
    # ここでパイプラインを打ち切る。Telegram通知は get_existing_repo_urls() 内で
    # 既に送信済みのため、ここでは処理の打ち切りのみを行う。
    existing_urls = get_existing_repo_urls()
    if existing_urls is None:
        logger.error(
            "[PIPELINE ABORTED] 重複チェック不能のため、本日のパイプラインを安全停止します（Fail-Closed）。"
        )
        return

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

    # ---- Gemini無料枠保護: スクリーニング対象数に安全弁を設ける ----
    # ソースが増えるほどdeduped_reposは増加しうるため、無制限にスクリーニングへ
    # 流し込むとRPM/RPDへの影響が読めなくなる。上限を超えた分は黙って切り捨てず、
    # ログに残した上で審査対象から除外する。
    if len(deduped_repos) > MAX_SCREENING_CANDIDATES:
        logger.warning(
            f"[SCREENING CAP] 候補が{len(deduped_repos)}件あり上限"
            f"({MAX_SCREENING_CANDIDATES}件)を超過。先頭{MAX_SCREENING_CANDIDATES}件のみ"
            f"スクリーニング対象とし、残り{len(deduped_repos) - MAX_SCREENING_CANDIDATES}件は"
            f"今回スキップします（無料枠保護のための安全弁）。"
        )
        deduped_repos = deduped_repos[:MAX_SCREENING_CANDIDATES]

    # ---- Step 1: 軽量スクリーニング ----
    logger.info(f">>> [Step 2] 軽量スクリーニング開始（対象 {len(deduped_repos)} 件）")
    screened = []
    try:
        for repo in deduped_repos:
            screened.append(screen_repo(repo))
    except DailyQuotaExhaustedError:
        send_telegram_alert("⚠️ Gemini APIの日次クォータに到達しました（スクリーニング中）。")
        logger.error("日次クォータ到達のため、スクリーニング段階で処理を打ち切ります。")
        return

    # 並び替え: スクリーニングスコア（主キー）降順。
    # 【タイブレークルール】スコアが同点の場合は、engagement（Stars / HN Score /
    # Votes等、ソースごとの人気指標をstargazerCountに正規化済み）の降順を
    # 副キーとして使う。これにより「内容の質は同等と評価されたが、より注目度の
    # 高い（＝読者の関心を引きやすい）案件」を優先的に深掘り対象へ回す。
    # ArXivはengagementが常に0固定（人気指標が存在しないソースのため）なので、
    # 他ソースと同点だった場合は自動的に劣後する。これは意図した挙動であり、
    # 論文ソースを機械的に排除するものではなく、「同点なら注目度で決める」
    # という一貫したルールの自然な帰結である。
    screened.sort(
        key=lambda x: (x["score"], x["repo"].get("stargazerCount", 0)),
        reverse=True,
    )
    top_candidates = screened[:TOP_N_FOR_DEEP_DIVE]

    logger.info(
        f">>> [Step 2 結果] 上位{len(top_candidates)}件を深掘り対象に選定: "
        + ", ".join(
            f"{c['repo'].get('nameWithOwner')}({c['score']}点, "
            f"engagement={c['repo'].get('stargazerCount', 0)})"
            for c in top_candidates
        )
    )

    # ---- Step 2: 上位N件のみフルレポート生成 ----
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
            f"https://notion.so/{NOTION_DATABASE_ID}"
        )
        send_telegram_alert(msg)
        logger.info(msg)
    else:
        logger.info("本日は生成条件を満たす記事がありませんでした。")

if __name__ == "__main__":
    main()
