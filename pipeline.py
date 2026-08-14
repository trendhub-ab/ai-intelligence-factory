import os
import re
import time
import base64
import requests
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw
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

def _generate_via_chat(model_name: str, prompt: str, config: dict | None = None,
                       request_kind: str = "other", reserve: int = 0):
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
    _consume_gemini_request(request_kind, reserve=reserve)
    chat = client.chats.create(model=model_name, config=config) if config else client.chats.create(model=model_name)
    return chat.send_message(prompt)

CANDIDATE_MODELS = os.environ.get(
    "GEMINI_MODEL_CANDIDATES",
    "gemini-3.1-flash-lite,gemini-3.5-flash"
).split(",")

# 深掘り（Step2フルレポート）に回す件数（Two-Stage化）
TOP_N_FOR_DEEP_DIVE = int(os.environ.get("TOP_N_FOR_DEEP_DIVE", "3"))

# ==========================================
# 構造改修: Notion保存とDeep Dive記事生成の分離
# ==========================================
# このスコア以上のスクリーニング済み案件は、Deep Dive記事化の対象外でも
# 「メタデータのみ」でNotion DBへ全件保存する（Notion DB自体を検索可能な
# ストック資産＝有料マガジンのコア資産として蓄積する設計）。
# TOP_N_FOR_DEEP_DIVEはこのストックの中から「詳細記事にするか」を決める
# 別軸のしきい値であり、両者は独立して調整できる。
NOTION_SAVE_THRESHOLD_SCORE = int(os.environ.get("NOTION_SAVE_THRESHOLD_SCORE", "60"))

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

# ---- Gemini無料枠のローカル安全予算 ----
# Google側のFree Tier上限そのものではなく、このpipeline 1実行内で絶対に超えない
# 独自Safety Cap。実際のRPM/RPD/TPMはAI Studioのcurrent limitsを運用者が確認し、
# 必要に応じて環境変数でさらに低く設定する。
GEMINI_DAILY_REQUEST_BUDGET = int(os.environ.get("GEMINI_DAILY_REQUEST_BUDGET", "50"))
GEMINI_SCREENING_RETRY_BUDGET = int(os.environ.get("GEMINI_SCREENING_RETRY_BUDGET", "4"))
GEMINI_DEEP_DIVE_RETRY_BUDGET = int(os.environ.get("GEMINI_DEEP_DIVE_RETRY_BUDGET", "1"))
GEMINI_RESERVED_DEEP_DIVE_REQUESTS = int(os.environ.get("GEMINI_RESERVED_DEEP_DIVE_REQUESTS", "3"))
GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS = int(os.environ.get("GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS", "6000"))
MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS = int(os.environ.get("MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS", "5"))

# Deep Dive一次情報補強。URL ContextはScreeningには使わず、source-native情報が
# 不足する候補（特にHN/PH）を中心に使用する。Google Searchは別枠利用条件が
# 変わり得るため、運用者がAI Studioで確認して明示的に有効化するまでOFF。
ENABLE_URL_CONTEXT = os.environ.get("ENABLE_URL_CONTEXT", "true").lower() in {"1", "true", "yes", "on"}
ENABLE_GOOGLE_SEARCH_GROUNDING = os.environ.get("ENABLE_GOOGLE_SEARCH_GROUNDING", "false").lower() in {"1", "true", "yes", "on"}
SOURCE_CONTEXT_MAX_CHARS = int(os.environ.get("SOURCE_CONTEXT_MAX_CHARS", "12000"))
SOURCE_CONTEXT_MIN_CHARS = int(os.environ.get("SOURCE_CONTEXT_MIN_CHARS", "300"))

# 記事タイトルから自動生成するアイキャッチ画像（PNG）の保存先ディレクトリ。
# note.comへのアップロードはAPI非対応のため自動化せず、ローカルに生成されたファイルを
# 運用者が手動でnoteの記事に添付する運用を想定する（詳細はgenerate_eyecatch_image参照）。
# 一方でNotion DBの「Eyecatch」プロパティ（ファイル＆メディア）にはURLが必要なため、
# 生成した画像はGitHubリポジトリへコミットし、raw.githubusercontent.comの
# 公開URLを取得した上でNotionへ紐付ける（詳細はupload_eyecatch_to_github参照）。
EYECATCH_OUTPUT_DIR = os.environ.get("EYECATCH_OUTPUT_DIR", "eyecatch_images")

# アイキャッチ画像をコミットするGitHubリポジトリ（"owner/repo"形式）。
# GitHub Actions上では GITHUB_REPOSITORY が自動的に注入されるため、通常は
# ワークフロー側での追加設定は不要。
EYECATCH_GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY")
# コミット先ブランチ。Actions実行時は GITHUB_REF_NAME（例: "main"）が
# 自動的に設定される。ローカル実行等で未設定の場合は "main" にフォールバックする。
EYECATCH_GITHUB_BRANCH = os.environ.get("GITHUB_REF_NAME") or "main"
# リポジトリ内でアイキャッチ画像を保存するディレクトリ（コミット先パスのプレフィックス）。
EYECATCH_GITHUB_DIR = os.environ.get("EYECATCH_GITHUB_DIR", "eyecatch_images")

# アイキャッチの背景画像（ソース別）を置くディレクトリ。運用者がリポジトリに
# コミットした画像ファイルをここから読み込んで合成する。ファイルが見つからない
# ソースは default.png にフォールバックし、それも無ければ従来のグラデーション
# 生成にフォールバックする（Fail-Safe、詳細はgenerate_eyecatch_image参照）。
EYECATCH_BACKGROUND_DIR = os.environ.get("EYECATCH_BACKGROUND_DIR", "assets/eyecatch_backgrounds")
# ソース名 -> 背景画像ファイル名（EYECATCH_BACKGROUND_DIR配下）のマッピング。
SOURCE_BACKGROUND_IMAGE = {
    "GitHub": "github.png",
    "HackerNews": "hackernews.png",
    "ArXiv": "arxiv.png",
    "ProductHunt": "producthunt.png",
}
EYECATCH_BACKGROUND_DEFAULT = "default.png"

# ==========================================
# 2. Notion プロパティ定義
# ==========================================
PROP_NAME = "Name"
PROP_URL = "URL"
PROP_SCORE = "Decision Score"
# Decision Scoreは「Deep Dive済みならStep2詳細スコア／ストックのみなら
# Step1軽量スクリーニングスコア」という、採点基準の異なる2種類の値が
# 同じ列に混在する（詳細はNOTION_SAVE_THRESHOLD_SCOREのコメントを参照）。
# Notion DB上でどちらの基準のスコアかを一目で判別できるよう、select型の
# Statusプロパティを追加する。Notion側では管理画面上でプロパティを
# 追加するだけでよく、コード側もこの定数と各プロパティ辞書への1行追加のみで
# 対応できる（新規プロパティ・値ともに事前にNotion側で用意しておくこと）。
PROP_STATUS = "Status"
STATUS_STOCKED = "Stocked"       # Decision Score = Step1軽量スクリーニングスコア
STATUS_DEEP_DIVE = "Deep Dive"   # Decision Score = Step2詳細スコア
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
# アイキャッチ画像（ファイル＆メディアプロパティ）。generate_eyecatch_imageで
# 生成したPNGをupload_eyecatch_to_githubでGitHubへコミットし、得られた
# raw.githubusercontent.comの公開URLをexternal fileとして紐付ける。
PROP_EYECATCH = "Eyecatch"
# 人気指標（GitHub Stars / HN Score / PH Votes）を横断的に数値として保持。
# ArXivは指標が存在しないため0を格納する（screen_repo/decision prompt側の
# ENGAGEMENT_LABELSと対応）。
PROP_ENGAGEMENT = "Engagement Score"
# 一次ソース側のオリジナル公開日時（GitHubのpushedAt、Hacker Newsの投稿日時、
# ArXivの論文公開日、Product Huntの投稿日）。「今まさに鮮度の高い情報か」を
# ユーザーが一目で判別できるようにするための日付プロパティ。normalize_item()で
# 各ソースの生データから抽出し、"publishedAt"キーとしてNormalizedItemに保持する。
# ソース側で取得できなかった場合はNoneのままとし、Notion側には未設定として送る
# （不正確な日付を捏造して埋めるよりは空欄の方が安全なため）。
PROP_PUBLISHED_AT = "Published At"
# 自社のAIインテリジェンス工場（Gemini）がスクリーニング・分析を実行した日付
# （＝Notion DBへの登録・更新日）。「いつのトレンドとして自社システムが捕捉したか」
# の記録であり、月次ダイジェスト集計やNotion側デフォルトソート軸（降順：最新順）
# として使う。Notionの組み込みcreated_time/last_edited_timeとは別に、
# アプリケーション側で明示的に管理する構造化プロパティとして持たせる。
PROP_ANALYZED_AT = "Analyzed At"

# Decision Intelligence / サブスク商品化のための追加プロパティ。
# 既存Statusはスコア種別互換のため絶対に意味変更せず、情報ライフサイクルは
# Content Status、記事ライフサイクルはArticle Statusで別管理する。
PROP_CONTENT_STATUS = "Content Status"
PROP_ARTICLE_STATUS = "Article Status"
PROP_SUBSCRIPTION_VISIBILITY = "Subscription Visibility"
PROP_SOURCE_SUMMARY = "Source Summary"
PROP_SCREENING_SCORE = "Screening Score"
PROP_SCREENING_REASON = "Screening Reason"
PROP_DECISION = "Decision"
PROP_DECISION_REASON = "Decision Reason"
PROP_WHO_SHOULD_USE = "Who Should Use"
PROP_WHO_SHOULD_NOT_USE = "Who Should NOT Use"
PROP_FUTURE_SCENARIO = "Future Scenario"
PROP_ARTICLE_VALUE = "Article Value"
PROP_GROUNDING_STATUS = "Grounding Status"
PROP_EVIDENCE_URLS = "Evidence URLs"

CONTENT_STATUS_STOCKED = "Stocked"
CONTENT_STATUS_DEEP_DIVE = "Deep Dive"
CONTENT_STATUS_QUALITY_FAILED = "Quality Failed"
ARTICLE_STATUS_NOT_PLANNED = "Not Planned"
ARTICLE_STATUS_READY = "Ready"
VISIBILITY_SUBSCRIBER_ONLY = "Subscriber Only"
VISIBILITY_PAID_ARTICLE = "Paid Article"
GROUNDING_METADATA_ONLY = "Metadata Only"
GROUNDING_SOURCE_NATIVE = "Source Native"
GROUNDING_URL_CONTEXT = "URL Context"
GROUNDING_URL_SEARCH = "URL + Search"
GROUNDING_FAILED = "Failed"
ALLOWED_DECISIONS = {"NOW", "TRY", "WATCH", "WAIT", "AVOID"}

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
MAX_QUALITY_RETRIES = 1

# ==========================================
# 3. エラー・モデル管理＆スマートリトライ
# ==========================================
class NoAvailableModelError(RuntimeError): pass
class DailyQuotaExhaustedError(RuntimeError): pass
class GeminiBudgetExceededError(RuntimeError): pass


class GeminiBudget:
    """1 pipeline実行内のGemini送信回数をFail-Closedで管理する軽量Budget。"""
    def __init__(self, daily_budget: int, screening_retry_budget: int, deep_dive_retry_budget: int):
        self.daily_budget = max(0, daily_budget)
        self.screening_retry_budget = max(0, screening_retry_budget)
        self.deep_dive_retry_budget = max(0, deep_dive_retry_budget)
        self.request_count = 0
        self.screening_retry_count = 0
        self.deep_dive_retry_count = 0
        self.by_kind: dict[str, int] = {}
        self._warned_80 = False

    @property
    def remaining(self) -> int:
        return max(0, self.daily_budget - self.request_count)

    def can_request(self, reserve: int = 0) -> bool:
        return self.request_count + 1 <= max(0, self.daily_budget - max(0, reserve))

    def can_screening_retry(self) -> bool:
        return self.screening_retry_count < self.screening_retry_budget

    def can_deep_dive_retry(self) -> bool:
        return self.deep_dive_retry_count < self.deep_dive_retry_budget

    def consume(self, kind: str, reserve: int = 0) -> None:
        if not self.can_request(reserve=reserve):
            raise GeminiBudgetExceededError(
                f"Gemini local budget exhausted: used={self.request_count}, "
                f"budget={self.daily_budget}, reserve={reserve}"
            )
        if kind == "screening_retry":
            if not self.can_screening_retry():
                raise GeminiBudgetExceededError("Screening retry budget exhausted")
            self.screening_retry_count += 1
        elif kind == "deep_dive_retry":
            if not self.can_deep_dive_retry():
                raise GeminiBudgetExceededError("Deep Dive transport retry budget exhausted")
            self.deep_dive_retry_count += 1

        self.request_count += 1
        self.by_kind[kind] = self.by_kind.get(kind, 0) + 1
        if self.daily_budget and not self._warned_80 and self.request_count >= max(1, int(self.daily_budget * 0.8)):
            self._warned_80 = True
            logger.warning(f"[GEMINI BUDGET] 80%到達: {self.request_count}/{self.daily_budget}")
            send_telegram_alert(f"⚠️ Gemini Budget 80%到達: {self.request_count}/{self.daily_budget}")

    def summary(self) -> str:
        details = ", ".join(f"{k}={v}" for k, v in sorted(self.by_kind.items())) or "none"
        return f"Gemini Requests Used: {self.request_count}/{self.daily_budget} ({details})"


GEMINI_BUDGET = GeminiBudget(
    GEMINI_DAILY_REQUEST_BUDGET,
    GEMINI_SCREENING_RETRY_BUDGET,
    GEMINI_DEEP_DIVE_RETRY_BUDGET,
)


def _consume_gemini_request(kind: str, reserve: int = 0) -> None:
    GEMINI_BUDGET.consume(kind, reserve=reserve)


def send_telegram_alert(message: str):
    """運用者(自分)宛のアラート通知。購読者向けではない。"""
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


PING_MAX_RETRIES = int(os.environ.get("PING_MAX_RETRIES", "1"))
PING_RETRY_BACKOFF_SECONDS = int(os.environ.get("PING_RETRY_BACKOFF_SECONDS", "12"))


def classify_gemini_quota_error(exc: Exception) -> str:
    """429の文字列から日次/RPM/TPMを保守的に分類する。曖昧ならUNKNOWN。"""
    text = str(exc)
    lower = text.lower()
    compact = re.sub(r"\s+", "", lower)

    # 日次系は明示的なPerDay/RequestsPerDay/Token...PerDay表現がある時だけ判定。
    if any(token in compact for token in (
        "requestsperday", "generaterequestsperday", "perdayperprojectpermodel",
        "free_tier_requests", "requests/day", "requestperday",
    )):
        return "RPD"
    if ("token" in lower or "input" in lower) and any(token in compact for token in (
        "tokensperday", "inputtokensperday", "perday",
    )):
        return "DAILY_TOKEN"
    if any(token in compact for token in (
        "requestsperminute", "requestperminute", "rpm", "perminuteperprojectpermodel",
    )):
        return "RPM"
    if ("token" in lower or "input" in lower) and any(token in compact for token in (
        "tokensperminute", "inputtokensperminute", "tpm", "perminute",
    )):
        return "TPM"
    return "UNKNOWN"


def _is_daily_quota_exhausted(exc: Exception) -> bool:
    return classify_gemini_quota_error(exc) in {"RPD", "DAILY_TOKEN"}


def _extract_retry_delay(exc: Exception, default: int = 20) -> int:
    text = str(exc)
    patterns = [
        r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+)",
        r"retry[_ ]?delay['\"]?\s*[:=]\s*['\"]?(\d+)",
        r"retry in\s+(\d+)\s*s",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return max(1, int(match.group(1)))
    return default


def resolve_model(candidates: list[str] = CANDIDATE_MODELS) -> str:
    """候補順=優先順位として軽量pingし、頻繁なGeminiモデル更新へ追随する。"""
    last_error: Exception | None = None
    for model_name in candidates:
        model_name = model_name.strip()
        if not model_name:
            continue
        for attempt in range(PING_MAX_RETRIES + 1):
            try:
                _generate_via_chat(
                    model_name,
                    "ping",
                    config={"max_output_tokens": 8},
                    request_kind="ping" if attempt == 0 else "ping_retry",
                )
                logger.info(f"モデル解決成功: {model_name}")
                return model_name
            except GeminiBudgetExceededError as e:
                raise NoAvailableModelError(str(e)) from e
            except APIError as e:
                last_error = e
                code = getattr(e, "code", None)
                if code == 404:
                    break
                if code == 429 and _is_daily_quota_exhausted(e):
                    raise DailyQuotaExhaustedError(str(e)) from e
                if code in (503, 429) and attempt < PING_MAX_RETRIES and GEMINI_BUDGET.can_request():
                    time.sleep(PING_RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                break
            except Exception as e:
                last_error = e
                raise NoAvailableModelError("想定外の例外") from e
    raise NoAvailableModelError("利用可能なモデルがありません") from last_error


try:
    SELECTED_MODEL = resolve_model()
except DailyQuotaExhaustedError as e:
    send_telegram_alert(f"⚠️ 【緊急】Gemini日次クォータ到達のため初期化停止: {e}")
    raise SystemExit(1)
except NoAvailableModelError as e:
    send_telegram_alert(f"⚠️ 【緊急】Gemini初期化失敗: {e}")
    raise SystemExit(1)


def call_gemini_with_smart_retry(prompt: str, max_retries: int = 1, request_kind: str = "deep_dive"):
    """非Groundedな既存互換call。無制限retryを禁止しLocal Budgetを必ず通す。"""
    for attempt in range(max_retries + 1):
        kind = request_kind if attempt == 0 else "deep_dive_retry"
        try:
            time.sleep(3)
            return _generate_via_chat(SELECTED_MODEL, prompt, request_kind=kind)
        except APIError as e:
            code = getattr(e, "code", None)
            if code == 429 and _is_daily_quota_exhausted(e):
                raise DailyQuotaExhaustedError(str(e)) from e
            if code in (429, 503) and attempt < max_retries and GEMINI_BUDGET.can_deep_dive_retry():
                time.sleep(_extract_retry_delay(e, default=15))
                continue
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
                                 spdx_id: str, source: str = "GitHub",
                                 evidence_urls: list[str] | None = None) -> str:
    """note投稿用Markdownを組み立て、一次出典と最大3件のEvidence URLを末尾へ付与する。"""
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

    unique_evidence = []
    for item in evidence_urls or []:
        if not item or item == repo_url or item in unique_evidence:
            continue
        if item.startswith(("http://", "https://")):
            unique_evidence.append(item)
        if len(unique_evidence) >= 3:
            break
    if unique_evidence:
        source_block += "\n### 参考情報\n" + "\n".join(f"- {u}" for u in unique_evidence) + "\n"

    manuscript += source_block
    return manuscript.strip()


# ==========================================
# 4.5. アイキャッチ画像生成モジュール（完全0円・外部API不使用）
# ==========================================
def _sanitize_filename(name: str) -> str:
    """
    リポジトリ名・記事名（例: "org/repo" のようにスラッシュを含みうる）を
    ファイルシステム上で安全なファイル名に変換する。
    英数字・アンダースコア・ハイフン以外は "_" に置換し、長すぎる場合は
    ファイル名長の上限に配慮して切り詰める。
    """
    safe = re.sub(r"[^\w\-]+", "_", name or "untitled", flags=re.UNICODE)
    return safe.strip("_")[:100] or "untitled"


def _load_eyecatch_background(source: str, width: int, height: int) -> Image.Image:
    """
    ソース別の背景画像を読み込み、指定サイズにcover方式（アスペクト比維持で
    はみ出た部分をトリミング）でリサイズして返す。

    画像が見つからない場合（未配置・ファイル名不一致等）はdefault.pngに
    フォールバックし、それも無ければNoneを返す（呼び出し側で従来の
    グラデーション生成にフォールバックする）。
    """
    filename = SOURCE_BACKGROUND_IMAGE.get(source, EYECATCH_BACKGROUND_DEFAULT)
    candidate_paths = [
        os.path.join(EYECATCH_BACKGROUND_DIR, filename),
        os.path.join(EYECATCH_BACKGROUND_DIR, EYECATCH_BACKGROUND_DEFAULT),
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            try:
                bg = Image.open(path).convert("RGB")
                src_w, src_h = bg.size
                target_ratio = width / height
                src_ratio = src_w / src_h
                if src_ratio > target_ratio:
                    # 元画像の方が横長 -> 高さを合わせてから左右をトリミング
                    new_h = height
                    new_w = int(src_ratio * new_h)
                else:
                    # 元画像の方が縦長 -> 幅を合わせてから上下をトリミング
                    new_w = width
                    new_h = int(new_w / src_ratio)
                bg = bg.resize((new_w, new_h))
                left = (new_w - width) // 2
                top = (new_h - height) // 2
                bg = bg.crop((left, top, left + width, top + height))
                return bg
            except Exception as e:
                logger.warning(f"[EYECATCH BG] {path} の読み込みに失敗しました: {e}")
                continue
    return None


def generate_eyecatch_image(title_text: str, output_path: str = "eyecatch.png",
                             source: str = "GitHub") -> str:
    """
    1280px x 670px のアイキャッチ画像を完全0円で自動生成するモジュール。

    【設計変更】テキスト合成（タグ・タイトル文字の描画）は廃止し、背景画像
    （ソース別、EYECATCH_BACKGROUND_DIR配下、SOURCE_BACKGROUND_IMAGEでマッピング）
    または従来のダークグラデーションのみを出力する。
    title_text引数は呼び出し互換性のために残しているが、画像生成には使用しない。
    """
    WIDTH, HEIGHT = 1280, 670

    img = _load_eyecatch_background(source, WIDTH, HEIGHT)
    if img is None:
        # 背景画像が用意されていない場合のフォールバック（ダークサイバー風グラデーション）。
        img = Image.new("RGB", (WIDTH, HEIGHT), color=(10, 15, 28))
        draw_bg = ImageDraw.Draw(img)
        for y in range(HEIGHT):
            r = int(10 + (y / HEIGHT) * 15)
            g = int(15 + (y / HEIGHT) * 25)
            b = int(28 + (y / HEIGHT) * 45)
            draw_bg.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    img.save(output_path, "PNG")
    return output_path


def upload_eyecatch_to_github(local_image_path: str, dest_filename: str) -> str | None:
    """
    生成したアイキャッチ画像をGitHub Contents API経由でリポジトリへコミットし、
    Notionの「Eyecatch」プロパティ（ファイル＆メディア）に設定可能な
    公開URL（raw.githubusercontent.com）を返す。

    【方針】
    GitHub Actions上で完結させるため、追加のホスティング先を用意せず、
    パイプライン自身が動いているリポジトリに画像をコミットする。
    GITHUB_REPOSITORY / GITHUB_REF_NAME はActions実行時に自動注入されるため、
    運用者側の追加設定なしに動作する。

    【Fail-Safe】
    Notion保存自体を止めないよう、失敗時は例外を投げずNoneを返す。
    呼び出し側はNoneの場合「Eyecatch」プロパティを空のまま保存する。
    """
    if not EYECATCH_GITHUB_REPO:
        logger.warning(
            "[EYECATCH UPLOAD SKIP] GITHUB_REPOSITORY が未設定のためアップロードをスキップします。"
        )
        return None

    dest_path = f"{EYECATCH_GITHUB_DIR}/{dest_filename}"
    api_url = f"https://api.github.com/repos/{EYECATCH_GITHUB_REPO}/contents/{dest_path}"
    headers = {
        "Authorization": f"Bearer {GH_PAT}",
        "Accept": "application/vnd.github+json",
    }

    try:
        with open(local_image_path, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode("utf-8")

        # 同名ファイルが既に存在する場合、GitHub Contents APIの更新には
        # 既存ファイルのshaが必須（sha無しでPUTすると409 Conflictになる）。
        # 同日再実行や同名案件の再生成に備え、まず既存shaの有無を確認する。
        existing_sha = None
        get_res = requests.get(
            api_url, headers=headers, params={"ref": EYECATCH_GITHUB_BRANCH}, timeout=15
        )
        if get_res.status_code == 200:
            existing_sha = get_res.json().get("sha")

        payload = {
            "message": f"chore: add eyecatch image {dest_filename}",
            "content": content_b64,
            "branch": EYECATCH_GITHUB_BRANCH,
        }
        if existing_sha:
            payload["sha"] = existing_sha

        put_res = requests.put(api_url, headers=headers, json=payload, timeout=30)
        if put_res.status_code not in (200, 201):
            logger.error(f"[EYECATCH UPLOAD FAILED] {dest_filename}: {put_res.text}")
            return None

        raw_url = (
            f"https://raw.githubusercontent.com/{EYECATCH_GITHUB_REPO}/"
            f"{EYECATCH_GITHUB_BRANCH}/{dest_path}"
        )
        logger.info(f"[EYECATCH UPLOAD] {dest_filename} -> {raw_url}")
        return raw_url
    except Exception as e:
        logger.error(f"[EYECATCH UPLOAD EXCEPTION] {dest_filename}: {e}")
        return None

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

def _notion_date_property(iso_datetime: str | None) -> dict:
    """Published At / Analyzed At用のNotion date型プロパティ値を組み立てる。
    値が取得できなかった場合（未実装ソース、パース失敗等）はNoneを渡すことで、
    不正確な日付を捏造せず「未設定」のまま安全にNotionへ送る。"""
    if not iso_datetime:
        return {"date": None}
    return {"date": {"start": iso_datetime}}


def build_notion_properties(repo_name, repo_url, score, score_breakdown_text, what_text,
                             why_important_text, why_not_important_text, action_text,
                             spdx_id, paradigm_shift_text="",
                             alternative_comparison_text="", migration_cost_text="",
                             source: str = "GitHub", engagement: int = 0, title_text: str = "",
                             eyecatch_url: str = "", published_at: str | None = None,
                             analyzed_at: str | None = None, report_meta: dict | None = None,
                             screening_score: int | None = None, screening_reason: str = "") -> dict:
    """Deep Dive用Notion properties。既存Statusの意味は維持し、新ライフサイクル列を併記。"""
    meta = report_meta or {}
    props = {
        PROP_NAME: {"title": [{"text": {"content": repo_name}}]},
        PROP_URL: {"url": repo_url},
        PROP_SOURCE: {"select": {"name": source}},
        PROP_ENGAGEMENT: {"number": engagement},
        PROP_SCORE: {"number": score},
        PROP_STATUS: {"select": {"name": STATUS_DEEP_DIVE}},
        PROP_CONTENT_STATUS: {"select": {"name": CONTENT_STATUS_DEEP_DIVE}},
        PROP_ARTICLE_STATUS: {"select": {"name": ARTICLE_STATUS_READY}},
        PROP_SUBSCRIPTION_VISIBILITY: {"select": {"name": VISIBILITY_PAID_ARTICLE}},
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
        PROP_EYECATCH: {
            "files": ([{"type": "external", "name": f"{repo_name}.png", "external": {"url": eyecatch_url}}]
                      if eyecatch_url else [])
        },
        PROP_PUBLISHED_AT: _notion_date_property(published_at),
        PROP_ANALYZED_AT: _notion_date_property(analyzed_at),
        PROP_SOURCE_SUMMARY: {"rich_text": [{"text": {"content": str(meta.get("source_summary_text", ""))[:2000]}}]},
        PROP_DECISION: {"select": {"name": meta.get("decision_text", "WATCH") if meta.get("decision_text") in ALLOWED_DECISIONS else "WATCH"}},
        PROP_DECISION_REASON: {"rich_text": [{"text": {"content": str(meta.get("decision_reason_text", ""))[:2000]}}]},
        PROP_WHO_SHOULD_USE: {"rich_text": [{"text": {"content": str(meta.get("who_should_use_text", ""))[:2000]}}]},
        PROP_WHO_SHOULD_NOT_USE: {"rich_text": [{"text": {"content": str(meta.get("who_should_not_use_text", ""))[:2000]}}]},
        PROP_FUTURE_SCENARIO: {"rich_text": [{"text": {"content": str(meta.get("future_scenario_text", ""))[:2000]}}]},
        PROP_ARTICLE_VALUE: {"number": int(meta.get("article_value", 0) or 0)},
        PROP_GROUNDING_STATUS: {"select": {"name": meta.get("grounding_status", GROUNDING_METADATA_ONLY)}},
        PROP_EVIDENCE_URLS: {"rich_text": [{"text": {"content": str(meta.get("evidence_urls_text", ""))[:2000]}}]},
    }
    # 既存ページPATCHでは省略すればStock時の値が保持される。新規Deep Diveページでは明示保存。
    if screening_score is not None:
        props[PROP_SCREENING_SCORE] = {"number": screening_score}
    if screening_reason:
        props[PROP_SCREENING_REASON] = {"rich_text": [{"text": {"content": screening_reason[:2000]}}]}
    return props



def build_notion_manuscript_children(clean_manuscript: str) -> list:
    """noteにそのままコピペできるよう、Markdown原稿を1つのcodeブロック
    （language: markdown）として保存するchildrenブロックを組み立てる。
    rich_text 1要素あたり2000字の上限があるため、safe_chunk_textで
    安全な区切り位置ごとに分割するが、複数のrich_text要素を同一の
    codeブロックへ連結することで、見た目上は1本の連続したMarkdown原稿
    として表示・コピーされる。"""
    chunks = safe_chunk_text(clean_manuscript)
    return [
        {
            "object": "block",
            "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": chunk}} for chunk in chunks],
                "language": "markdown",
            },
        }
    ]


def build_notion_payload(repo_name, repo_url, score, score_breakdown_text, what_text,
                          why_important_text, why_not_important_text, action_text,
                          spdx_id, clean_manuscript, paradigm_shift_text="",
                          alternative_comparison_text="", migration_cost_text="",
                          source: str = "GitHub", engagement: int = 0, title_text: str = "",
                          eyecatch_url: str = "", published_at: str | None = None,
                          analyzed_at: str | None = None, report_meta: dict | None = None,
                          screening_score: int | None = None, screening_reason: str = "") -> dict:
    return {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": build_notion_properties(
            repo_name, repo_url, score, score_breakdown_text, what_text,
            why_important_text, why_not_important_text, action_text,
            spdx_id, paradigm_shift_text, alternative_comparison_text,
            migration_cost_text, source, engagement, title_text, eyecatch_url,
            published_at, analyzed_at, report_meta, screening_score, screening_reason,
        ),
        "children": build_notion_manuscript_children(clean_manuscript),
    }


def save_to_notion(repo_name, repo_url, score, score_breakdown_text, what_text,
                    why_important_text, why_not_important_text, action_text,
                    spdx_id, clean_manuscript, paradigm_shift_text="",
                    alternative_comparison_text="", migration_cost_text="",
                    source: str = "GitHub", engagement: int = 0, title_text: str = "",
                    eyecatch_url: str = "", published_at: str | None = None,
                    analyzed_at: str | None = None, report_meta: dict | None = None,
                    screening_score: int | None = None, screening_reason: str = "") -> bool:
    """Deep Diveフル記事の新規Notionページ作成。"""
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
        source, engagement, title_text, eyecatch_url,
        published_at, analyzed_at, report_meta, screening_score, screening_reason,
    )
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            logger.info(f"[NOTION SAVED] {repo_name} -> Deep Dive原稿保存完了")
            return True
        logger.error(f"[NOTION ERROR] {repo_name} -> {res.text}")
        return False
    except Exception as e:
        logger.error(f"[NOTION EXCEPTION] {e}")
        return False



# ==========================================
# 5b. スクリーニング段階のメタデータ保存（全件ストック）＆ 深掘り時のページ更新
# ==========================================
def build_metadata_notion_properties(repo_name, repo_url, score, reason,
                                      source: str = "GitHub", engagement: int = 0,
                                      published_at: str | None = None,
                                      analyzed_at: str | None = None,
                                      source_summary: str = "") -> dict:
    """Screening通過時の購読者向けStock metadata。Step1評価を永久保存する。"""
    return {
        PROP_NAME: {"title": [{"text": {"content": repo_name}}]},
        PROP_URL: {"url": repo_url},
        PROP_SOURCE: {"select": {"name": source}},
        PROP_ENGAGEMENT: {"number": engagement},
        PROP_SCORE: {"number": score},
        PROP_STATUS: {"select": {"name": STATUS_STOCKED}},
        PROP_CONTENT_STATUS: {"select": {"name": CONTENT_STATUS_STOCKED}},
        PROP_ARTICLE_STATUS: {"select": {"name": ARTICLE_STATUS_NOT_PLANNED}},
        PROP_SUBSCRIPTION_VISIBILITY: {"select": {"name": VISIBILITY_SUBSCRIBER_ONLY}},
        PROP_SCREENING_SCORE: {"number": score},
        PROP_SCREENING_REASON: {"rich_text": [{"text": {"content": reason[:2000]}}]},
        PROP_SOURCE_SUMMARY: {"rich_text": [{"text": {"content": (source_summary or "")[:2000]}}]},
        PROP_GROUNDING_STATUS: {"select": {"name": GROUNDING_METADATA_ONLY}},
        PROP_SCORE_BREAKDOWN: {"rich_text": [{"text": {"content": reason[:2000]}}]},
        PROP_PUBLISHED_AT: _notion_date_property(published_at),
        PROP_ANALYZED_AT: _notion_date_property(analyzed_at),
    }



def save_screening_metadata_to_notion(repo, score: int, reason: str) -> str | None:
    """スクリーニングスコアがNOTION_SAVE_THRESHOLD_SCORE以上の案件を、
    詳細記事化するか否かに関わらずメタデータのみで全件Notion DBへ保存する。
    Notion DB自体を「検索可能なストック資産」として蓄積するための入口。

    戻り値: 作成に成功した場合はNotionページID（後で深掘り時にアップグレード
    更新するために使う）。失敗時・Notion未設定時はNone。"""
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        return None

    name = repo.get("nameWithOwner")
    repo_url = repo.get("url")
    source = repo.get("source", "GitHub")
    engagement = repo.get("stargazerCount", 0)
    published_at = repo.get("publishedAt")
    # Analyzed At = このスクリーニング（Step1軽量分析）を実行した「いま」。
    analyzed_at = _analyzed_at_now_iso()

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": build_metadata_notion_properties(
            name, repo_url, score, reason, source, engagement,
            published_at, analyzed_at, repo.get("description", ""),
        ),
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            page_id = res.json().get("id")
            logger.info(f"[NOTION STOCK SAVED] {name}: {score}点 -> メタデータのみでストックDBへ保存（page_id={page_id}）")
            return page_id
        logger.error(f"[NOTION STOCK ERROR] {name} -> {res.text}")
        return None
    except Exception as e:
        logger.error(f"[NOTION STOCK EXCEPTION] {name}: {e}")
        return None


def upgrade_notion_page_with_report(page_id: str, repo_name, repo_url, score, score_breakdown_text,
                                     what_text, why_important_text, why_not_important_text,
                                     action_text, spdx_id, clean_manuscript, paradigm_shift_text="",
                                     alternative_comparison_text="", migration_cost_text="",
                                     source: str = "GitHub", engagement: int = 0, title_text: str = "",
                                     eyecatch_url: str = "", published_at: str | None = None,
                                     analyzed_at: str | None = None, report_meta: dict | None = None,
                                     screening_score: int | None = None, screening_reason: str = "") -> bool:
    """Stock済みNotionページをDeep Diveへアップグレード。Step1履歴は保持する。"""
    if not NOTION_API_KEY:
        return False
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    properties = build_notion_properties(
        repo_name, repo_url, score, score_breakdown_text, what_text,
        why_important_text, why_not_important_text, action_text,
        spdx_id, paradigm_shift_text, alternative_comparison_text,
        migration_cost_text, source, engagement, title_text, eyecatch_url,
        published_at, analyzed_at, report_meta, screening_score, screening_reason,
    )
    try:
        res = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            json={"properties": properties}, headers=headers, timeout=10,
        )
        if res.status_code != 200:
            logger.error(f"[NOTION UPGRADE PROPERTIES ERROR] {repo_name} -> {res.text}")
            return False
        children = build_notion_manuscript_children(clean_manuscript)
        res2 = requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            json={"children": children}, headers=headers, timeout=10,
        )
        if res2.status_code != 200:
            logger.error(f"[NOTION UPGRADE CHILDREN ERROR] {repo_name} -> {res2.text}")
            return False
        logger.info(f"[NOTION UPGRADED] {repo_name} -> Deep Diveへアップグレード完了")
        return True
    except Exception as e:
        logger.error(f"[NOTION UPGRADE EXCEPTION] {repo_name}: {e}")
        return False


def update_notion_quality_failed(page_id: str, repo_name: str,
                                 grounding_status: str = GROUNDING_FAILED,
                                 evidence_urls: list[str] | None = None) -> bool:
    """記事生成に失敗してもStock資産を消さず、購読者DBへ残す。"""
    if not page_id or not NOTION_API_KEY:
        return False
    evidence_text = "\n".join((evidence_urls or [])[:3])[:2000]
    props = {
        PROP_CONTENT_STATUS: {"select": {"name": CONTENT_STATUS_QUALITY_FAILED}},
        PROP_ARTICLE_STATUS: {"select": {"name": ARTICLE_STATUS_NOT_PLANNED}},
        PROP_SUBSCRIPTION_VISIBILITY: {"select": {"name": VISIBILITY_SUBSCRIBER_ONLY}},
        PROP_GROUNDING_STATUS: {"select": {"name": grounding_status}},
        PROP_EVIDENCE_URLS: {"rich_text": [{"text": {"content": evidence_text}}]},
    }
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    try:
        res = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            json={"properties": props}, headers=headers, timeout=10,
        )
        if res.status_code == 200:
            logger.info(f"[NOTION QUALITY FAILED] {repo_name} -> Stock資産として保持")
            return True
        logger.error(f"[NOTION QUALITY FAILED ERROR] {repo_name} -> {res.text}")
    except Exception as e:
        logger.error(f"[NOTION QUALITY FAILED EXCEPTION] {repo_name}: {e}")
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

# Notion Date プロパティ・Analyzed At 用のタイムゾーン。
# パイプライン全体（月次ダイジェストの月末判定等）と統一してJST（UTC+9）を使う。
JST = timezone(timedelta(hours=9))


def _analyzed_at_now_iso() -> str:
    """『いま』をAnalyzed At用のISO8601文字列（JST）として返す。
    スクリーニング保存時・Deep Diveアップグレード時など、Geminiによる
    分析処理を実際に実行したタイミングで都度呼び出すことを想定している。"""
    return datetime.now(JST).isoformat()


def normalize_item(source: str, name: str, url: str, description: str,
                    engagement: int, license_info: dict | None = None,
                    published_at: str | None = None, source_context: str = "",
                    primary_url: str | None = None, source_details: dict | None = None) -> dict:
    """各ソースを既存互換キーへ正規化し、Deep Dive用一次コンテキストも保持する。"""
    return {
        "source": source,
        "nameWithOwner": (name or "無題").strip() or "無題",
        "url": (url or "").strip(),
        "description": (description or "説明なし").strip() or "説明なし",
        "stargazerCount": engagement or 0,
        "licenseInfo": license_info,
        "publishedAt": published_at,
        "sourceContext": (source_context or "").strip(),
        "primaryUrl": (primary_url or url or "").strip(),
        "sourceDetails": source_details or {},
    }


def _truncate_source_context(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    return text[:SOURCE_CONTEXT_MAX_CHARS]


def fetch_github_readme_context(repo_name: str) -> str:
    """Deep Dive候補だけREADMEを取得。失敗してもURL Contextへfallback可能。"""
    if not repo_name or "/" not in repo_name:
        return ""
    api_url = f"https://api.github.com/repos/{repo_name}/readme"
    headers = {
        "Authorization": f"Bearer {GH_PAT}",
        "Accept": "application/vnd.github.raw+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        res = requests.get(api_url, headers=headers, timeout=15)
        if res.status_code == 200:
            return _truncate_source_context(res.text)
        logger.warning(f"[SOURCE CONTEXT] GitHub README取得失敗 {repo_name}: HTTP {res.status_code}")
    except Exception as e:
        logger.warning(f"[SOURCE CONTEXT] GitHub README取得例外 {repo_name}: {e}")
    return ""


def prepare_source_context(repo: dict) -> dict:
    """Geminiを使わず一次情報を補強し、Deep Dive可能性を事前判定する。"""
    source = repo.get("source", "GitHub")
    name = repo.get("nameWithOwner", "")
    desc = repo.get("description", "")
    primary_url = repo.get("primaryUrl") or repo.get("url") or ""
    stored = repo.get("sourceContext") or ""
    details = repo.get("sourceDetails") or {}

    pieces = [f"Source: {source}", f"Name: {name}", f"Description: {desc}"]
    method = GROUNDING_METADATA_ONLY

    if source == "GitHub":
        readme = fetch_github_readme_context(name)
        if readme:
            pieces.append("README:\n" + readme)
            method = GROUNDING_SOURCE_NATIVE
    elif source == "ArXiv":
        if stored:
            pieces.append("Abstract:\n" + stored)
            method = GROUNDING_SOURCE_NATIVE
        authors = details.get("authors") or []
        categories = details.get("categories") or []
        if authors:
            pieces.append("Authors: " + ", ".join(authors[:20]))
        if categories:
            pieces.append("Categories: " + ", ".join(categories[:20]))
    elif source == "ProductHunt":
        if stored:
            pieces.append("Product Hunt details:\n" + stored)
            method = GROUNDING_SOURCE_NATIVE
    elif source == "HackerNews":
        hn_text = stored.strip()
        if hn_text:
            pieces.append("Hacker News post text:\n" + hn_text)
            method = GROUNDING_SOURCE_NATIVE
        hn_url = details.get("hn_url")
        if hn_url:
            pieces.append(f"HN discussion URL: {hn_url}")
    elif stored:
        pieces.append(stored)
        method = GROUNDING_SOURCE_NATIVE

    context = _truncate_source_context("\n\n".join(pieces))
    # title/descriptionだけを水増しして「十分」と判定しない。source-native本体が一定量必要。
    substantive = _truncate_source_context(stored)
    if source == "GitHub":
        substantive = readme if 'readme' in locals() else ""
    sufficient = len(substantive.strip()) >= SOURCE_CONTEXT_MIN_CHARS

    return {
        "context": context,
        "context_length": len(context),
        "method": method,
        "primary_url": primary_url,
        "sufficient": sufficient,
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
            pushedAt
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
                # pushedAtはGraphQL標準のISO8601文字列（例: "2026-08-10T03:21:00Z"）で
                # 返ってくるためそのままpublished_atとして使う。「直近のpush=一次情報として
                # 最新の動きがあった日」を鮮度の基準とする（検索クエリのpushed:>フィルタとも一致）。
                items.append(normalize_item(
                    source="GitHub",
                    name=node.get("nameWithOwner"),
                    url=node.get("url"),
                    description=node.get("description"),
                    engagement=node.get("stargazerCount", 0),
                    license_info=license_info,
                    published_at=node.get("pushedAt"),
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
    """HN APIから上位storyを取得し、外部URL・HN本文をDeep Dive用に保持する。"""
    logger.info(">>> [Step 1] Hacker News一次データの自動巡回...")
    items = []
    try:
        ids_res = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10)
        ids_res.raise_for_status()
        for story_id in ids_res.json()[:limit]:
            try:
                item_res = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=10)
                item_res.raise_for_status()
                data = item_res.json() or {}
                if data.get("type") != "story":
                    continue
                raw_time = data.get("time")
                published_at = None
                if raw_time:
                    try:
                        published_at = datetime.fromtimestamp(raw_time, tz=timezone.utc).isoformat()
                    except (OSError, OverflowError, ValueError):
                        pass
                external_url = data.get("url") or ""
                hn_url = f"https://news.ycombinator.com/item?id={story_id}"
                hn_text = re.sub(r"<[^>]+>", " ", data.get("text") or "")
                hn_text = re.sub(r"\s+", " ", hn_text).strip()
                items.append(normalize_item(
                    source="HackerNews",
                    name=data.get("title"),
                    url=external_url or hn_url,
                    description=data.get("title"),
                    engagement=data.get("score", 0),
                    published_at=published_at,
                    source_context=hn_text,
                    primary_url=external_url or hn_url,
                    source_details={"hn_id": story_id, "hn_url": hn_url, "external_url": external_url},
                ))
            except Exception as e:
                logger.warning(f"[HN ITEM SKIP] id={story_id}: {e}")
        logger.info(f"   -> Hacker News {len(items)} 件の候補を取得。")
    except Exception as e:
        logger.error(f"[FAULT ISOLATED] Hacker News APIエラー: {e}")
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
            response = requests.get(url, params=params, timeout=30)
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
    """arXiv APIからAI/ML最新論文を取得。Screening表示は短縮、Deep Diveにはabstract全文を保持。"""
    logger.info(">>> [Step 1] ArXiv一次データの自動巡回...")
    items = []
    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": "cat:cs.AI OR cat:cs.LG",
        "start": 0,
        "max_results": limit,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        response = _fetch_arxiv_with_retry(url, params)
        if response is None:
            logger.error("[FAULT ISOLATED] ArXiv APIエラー: リトライ後も取得に失敗しました。")
            return items
        root = ET.fromstring(response.content)
        for entry in root.findall("atom:entry", ns):
            try:
                title = re.sub(r"\s+", " ", entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
                summary_full = re.sub(r"\s+", " ", entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
                published_at = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip() or None
                link = ""
                for link_el in entry.findall("atom:link", ns):
                    if link_el.get("rel") == "alternate":
                        link = link_el.get("href", "")
                        break
                if not link:
                    link = entry.findtext("atom:id", default="", namespaces=ns) or ""
                authors = [
                    re.sub(r"\s+", " ", a.findtext("atom:name", default="", namespaces=ns) or "").strip()
                    for a in entry.findall("atom:author", ns)
                ]
                categories = [c.get("term", "") for c in entry.findall("atom:category", ns) if c.get("term")]
                items.append(normalize_item(
                    source="ArXiv", name=title, url=link.strip(),
                    description=summary_full[:500], engagement=0,
                    published_at=published_at, source_context=summary_full,
                    primary_url=link.strip(), source_details={"authors": authors, "categories": categories},
                ))
            except Exception as e:
                logger.warning(f"[ARXIV ENTRY SKIP] {e}")
        logger.info(f"   -> ArXiv {len(items)} 件の候補を取得。")
    except Exception as e:
        logger.error(f"[FAULT ISOLATED] ArXiv APIエラー: {e}")
    return items


def fetch_producthunt_trending(limit: int = 10):
    """Product Hunt GraphQLから注目プロダクトを取得し、tagline+descriptionを保持する。"""
    logger.info(">>> [Step 1] Product Hunt一次データの自動巡回...")
    if not PRODUCTHUNT_DEVELOPER_TOKEN:
        logger.warning("[PH SKIP] PRODUCTHUNT_DEVELOPER_TOKEN が未設定のためProduct Huntをスキップします。")
        return []
    items = []
    url = "https://api.producthunt.com/v2/api/graphql"
    headers = {"Authorization": f"Bearer {PRODUCTHUNT_DEVELOPER_TOKEN}", "Content-Type": "application/json"}
    query = """
    query TrendingPosts($first: Int!) {
      posts(order: VOTES, first: $first) {
        edges { node { name tagline description url website votesCount createdAt } }
      }
    }
    """
    try:
        response = requests.post(url, json={"query": query, "variables": {"first": limit}}, headers=headers, timeout=15)
        if response.status_code != 200:
            logger.error(f"[FAULT ISOLATED] Product Hunt APIエラー: HTTP {response.status_code} {response.text[:200]}")
            return []
        payload = response.json()
        if "errors" in payload:
            logger.error(f"[FAULT ISOLATED] Product Hunt GraphQLエラー: {payload['errors']}")
            return []
        for edge in payload.get("data", {}).get("posts", {}).get("edges", []):
            try:
                node = edge.get("node", {})
                tagline = (node.get("tagline") or "").strip()
                description = (node.get("description") or "").strip()
                source_context = "\n".join(x for x in [f"Tagline: {tagline}" if tagline else "", f"Description: {description}" if description else ""] if x)
                primary = node.get("website") or node.get("url") or ""
                items.append(normalize_item(
                    source="ProductHunt", name=node.get("name"), url=primary,
                    description=tagline or description, engagement=node.get("votesCount", 0),
                    published_at=node.get("createdAt"), source_context=source_context,
                    primary_url=primary, source_details={"producthunt_url": node.get("url") or ""},
                ))
            except Exception as e:
                logger.warning(f"[PH ITEM SKIP] {e}")
        logger.info(f"   -> Product Hunt {len(items)} 件の候補を取得。")
    except Exception as e:
        logger.error(f"[FAULT ISOLATED] Product Hunt APIエラー: {e}")
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
# 6b. 月末ダイジェスト: 当月の全データセットを集計・パッケージング
# ==========================================
# ダイジェストMarkdownのローカル保存先。GitHub Actions実行後はコミットまで
# 行うため、成果物として永続化される（詳細はupload_digest_to_github参照）。
MONTHLY_DIGEST_OUTPUT_DIR = os.environ.get("MONTHLY_DIGEST_OUTPUT_DIR", "monthly_digests")
MONTHLY_DIGEST_GITHUB_DIR = os.environ.get("MONTHLY_DIGEST_GITHUB_DIR", "monthly_digests")
# 月間の蓄積件数がこれを超える運用は現状想定していないが、超えた場合でも
# パイプライン自体は止めずに先頭N件のみを集計対象とする（安全弁）。
MONTHLY_DIGEST_MAX_ITEMS = int(os.environ.get("MONTHLY_DIGEST_MAX_ITEMS", "500"))


def _is_last_day_of_month(target_date) -> bool:
    """target_date（date型、JST想定）が月末日かどうかを判定する。"""
    return (target_date + timedelta(days=1)).month != target_date.month


def _month_range_utc(target_date):
    """
    target_date（JSTの日付）が属する月の [月初0:00, 翌月月初0:00) を
    Notion APIのcreated_timeフィルタに渡せるUTC ISO8601文字列として返す。
    """
    jst = timezone(timedelta(hours=9))
    first_day_jst = datetime(target_date.year, target_date.month, 1, tzinfo=jst)
    if target_date.month == 12:
        next_month_first_jst = datetime(target_date.year + 1, 1, 1, tzinfo=jst)
    else:
        next_month_first_jst = datetime(target_date.year, target_date.month + 1, 1, tzinfo=jst)
    start_utc = first_day_jst.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    end_utc = next_month_first_jst.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return start_utc, end_utc


def fetch_monthly_dataset(start_utc: str, end_utc: str) -> list[dict] | None:
    """
    [start_utc, end_utc) の期間にNotion DBへ新規作成された全ページを取得する。
    ページネーション対応。

    重複チェック（get_existing_repo_urls）と異なり、ここでの取得失敗は
    「過去記事の誤重複公開」のような事故には繋がらないため、Fail-Closedで
    パイプライン全体を止めることはしない。失敗時はNoneを返し、呼び出し元は
    今回のダイジェスト生成のみをスキップして日次パイプライン本体は継続する。
    """
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        return None

    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    items: list[dict] = []
    next_cursor = None
    while True:
        payload = {
            "filter": {
                "and": [
                    {"timestamp": "created_time", "created_time": {"on_or_after": start_utc}},
                    {"timestamp": "created_time", "created_time": {"before": end_utc}},
                ]
            },
            "page_size": 100,
        }
        if next_cursor:
            payload["start_cursor"] = next_cursor

        res = _query_notion_db_with_retry(url, headers, payload)
        if res is None:
            logger.error("[MONTHLY DIGEST] Notion問い合わせに失敗したため、当月データセットを取得できませんでした。")
            return None

        data = res.json()
        for page in data.get("results", []):
            props = page.get("properties", {})
            name = "".join(t.get("plain_text", "") for t in props.get(PROP_NAME, {}).get("title", []))
            page_url = props.get(PROP_URL, {}).get("url") or ""
            source = (props.get(PROP_SOURCE, {}).get("select") or {}).get("name", "Unknown")
            status = (props.get(PROP_STATUS, {}).get("select") or {}).get("name", "Unknown")
            score = props.get(PROP_SCORE, {}).get("number")
            items.append({
                "name": name or "(無題)",
                "url": page_url,
                "source": source,
                "status": status,
                "score": score,
            })

        if data.get("has_more") and len(items) < MONTHLY_DIGEST_MAX_ITEMS:
            next_cursor = data.get("next_cursor")
        else:
            if data.get("has_more"):
                logger.warning(
                    f"[MONTHLY DIGEST] 当月データが上限({MONTHLY_DIGEST_MAX_ITEMS}件)に達したため、"
                    "それ以降は集計対象から除外します（安全弁）。"
                )
            break

    return items


def build_monthly_digest_markdown(target_date, items: list[dict]) -> str:
    """
    当月データセットから、運用者・購読者向けの月次ダイジェストMarkdownを
    組み立てる。Deep Dive済み案件（Step2詳細スコア）とストックのみ案件
    （Step1軽量スコア）は採点基準が異なるため、Statusプロパティで区別し、
    セクション・ランキングを分離して混同を防ぐ。
    """
    month_label = f"{target_date.year}年{target_date.month}月"

    by_status: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for it in items:
        by_status[it["status"]] = by_status.get(it["status"], 0) + 1
        by_source[it["source"]] = by_source.get(it["source"], 0) + 1

    deep_dive_items = sorted(
        (it for it in items if it["status"] == STATUS_DEEP_DIVE),
        key=lambda x: (x["score"] or 0), reverse=True,
    )
    stocked_items_top10 = sorted(
        (it for it in items if it["status"] == STATUS_STOCKED),
        key=lambda x: (x["score"] or 0), reverse=True,
    )[:10]

    lines = [
        f"# {month_label} 全データセットダイジェスト",
        "",
        f"- 総収集件数: {len(items)}件",
        "- 内訳（ステータス別）: " + (", ".join(f"{k} {v}件" for k, v in by_status.items()) or "-"),
        "- 内訳（ソース別）: " + (", ".join(f"{k} {v}件" for k, v in by_source.items()) or "-"),
        "",
        f"## Deep Dive記事一覧（{len(deep_dive_items)}件・Step2詳細スコア順）",
        "",
    ]
    lines += (
        [f"- [{it['name']}]({it['url']}) - {it['score']}点 / {it['source']}" for it in deep_dive_items]
        or ["（今月はDeep Dive記事の生成はありませんでした）"]
    )
    lines += [
        "",
        "## ストックのみ案件 Top10（Step1軽量スクリーニングスコア順）",
        "",
    ]
    lines += (
        [f"- [{it['name']}]({it['url']}) - {it['score']}点 / {it['source']}" for it in stocked_items_top10]
        or ["（該当なし）"]
    )
    lines += [
        "",
        "---",
        "",
        "※本ダイジェストはNotion DBへの当月新規保存分を自動集計したものです。",
        "※「Decision Score」はDeep Dive済み案件ではStep2詳細スコア、ストックのみの"
        "案件ではStep1軽量スクリーニングスコアであり、採点基準が異なります"
        "（Statusプロパティで判別可能。詳細はPROP_STATUSのコメントを参照）。",
    ]
    return "\n".join(lines)


def upload_digest_to_github(local_path: str, dest_filename: str) -> str | None:
    """
    月次ダイジェストMarkdownをGitHub Contents API経由でリポジトリへコミットし、
    公開URL（raw.githubusercontent.com）を返す。アイキャッチ画像アップロード
    （upload_eyecatch_to_github）と同一のコミットパターンを踏襲する。
    Fail-Safe: 失敗時はNoneを返し、呼び出し元はTelegram通知のみで処理を継続する
    （ローカルファイルはリポジトリのワークスペース上に残っているため、
    Actions実行ログ・アーティファクトからも復旧可能）。
    """
    if not EYECATCH_GITHUB_REPO:
        logger.warning("[DIGEST UPLOAD SKIP] GITHUB_REPOSITORY が未設定のためアップロードをスキップします。")
        return None

    dest_path = f"{MONTHLY_DIGEST_GITHUB_DIR}/{dest_filename}"
    api_url = f"https://api.github.com/repos/{EYECATCH_GITHUB_REPO}/contents/{dest_path}"
    headers = {
        "Authorization": f"Bearer {GH_PAT}",
        "Accept": "application/vnd.github+json",
    }
    try:
        with open(local_path, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode("utf-8")

        existing_sha = None
        get_res = requests.get(api_url, headers=headers, params={"ref": EYECATCH_GITHUB_BRANCH}, timeout=15)
        if get_res.status_code == 200:
            existing_sha = get_res.json().get("sha")

        payload = {
            "message": f"chore: add monthly digest {dest_filename}",
            "content": content_b64,
            "branch": EYECATCH_GITHUB_BRANCH,
        }
        if existing_sha:
            payload["sha"] = existing_sha

        put_res = requests.put(api_url, headers=headers, json=payload, timeout=30)
        if put_res.status_code not in (200, 201):
            logger.error(f"[DIGEST UPLOAD FAILED] {dest_filename}: {put_res.text}")
            return None

        raw_url = f"https://raw.githubusercontent.com/{EYECATCH_GITHUB_REPO}/{EYECATCH_GITHUB_BRANCH}/{dest_path}"
        logger.info(f"[DIGEST UPLOAD] {dest_filename} -> {raw_url}")
        return raw_url
    except Exception as e:
        logger.error(f"[DIGEST UPLOAD EXCEPTION] {dest_filename}: {e}")
        return None


def generate_monthly_digest(target_date=None):
    """
    月末に、当月Notion DBへ保存された全データセット（Deep Dive＋ストックのみ
    双方）を集計し、Markdownダイジェストとしてパッケージング（ローカル保存＋
    GitHubコミット）した上で運用者へTelegram通知する。

    専用cronは設けず、毎日実行されるmain()の末尾から呼び出す設計とし、
    内部で「今日がJSTで月末日か」を判定して該当日のみ実際に集計を行う
    （月末日以外は即座に何もせず戻る）。
    """
    if target_date is None:
        target_date = datetime.now(timezone(timedelta(hours=9))).date()

    if not _is_last_day_of_month(target_date):
        return

    logger.info(f">>> [MONTHLY DIGEST] {target_date} は月末日のため、当月データセットのダイジェスト生成を開始します。")

    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        logger.warning("[MONTHLY DIGEST] Notion未設定のためダイジェスト生成をスキップします。")
        return

    start_utc, end_utc = _month_range_utc(target_date)
    items = fetch_monthly_dataset(start_utc, end_utc)
    if items is None:
        send_telegram_alert(
            "⚠️【月次ダイジェスト】Notion問い合わせに失敗したため、今月のダイジェスト生成をスキップしました。"
        )
        return

    if not items:
        logger.info("[MONTHLY DIGEST] 当月の新規データが0件のため、ダイジェスト生成をスキップします。")
        return

    digest_md = build_monthly_digest_markdown(target_date, items)

    os.makedirs(MONTHLY_DIGEST_OUTPUT_DIR, exist_ok=True)
    filename = f"{target_date.year}-{target_date.month:02d}_digest.md"
    local_path = os.path.join(MONTHLY_DIGEST_OUTPUT_DIR, filename)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(digest_md)
    logger.info(f"[MONTHLY DIGEST] ローカルにダイジェストを保存しました: {local_path}")

    digest_url = upload_digest_to_github(local_path, filename)

    deep_dive_count = sum(1 for it in items if it["status"] == STATUS_DEEP_DIVE)
    stocked_count = sum(1 for it in items if it["status"] == STATUS_STOCKED)
    msg = (
        f"📦【月次ダイジェスト】{target_date.year}年{target_date.month}月分を集計しました。\n"
        f"総件数: {len(items)}件（Deep Dive {deep_dive_count}件 / ストックのみ {stocked_count}件）\n"
    )
    msg += digest_url if digest_url else "（GitHubへのアップロードに失敗。リポジトリ内のローカル成果物を確認してください）"
    send_telegram_alert(msg)
    logger.info(msg)


# ==========================================
# 7. 「判断装置」プロンプト & 解析
# ==========================================
def build_decision_prompt(name, url, stars, desc, quality_feedback: str = "", source: str = "GitHub",
                          source_context: str = "", grounding_status_hint: str = GROUNDING_METADATA_ONLY):
    """500円noteを『要約』ではなくGrounded Decision Intelligenceとして生成する。"""
    metric_label = ENGAGEMENT_LABELS.get(source, "Engagement")
    metric_note = ""
    if source == "ArXiv":
        metric_note = "※arXivにはStars/Votes相当の人気指標がないため、人気度を0とみなして価値判断しないこと。\n"
    feedback = f"\n【前回出力の品質不足】\n{quality_feedback}\n不足点を必ず修正すること。\n" if quality_feedback else ""
    context = _truncate_source_context(source_context)

    return f"""
あなたはAI・ソフトウェア領域のシニアCTOアドバイザー兼テック編集者です。
以下の一次情報について、500円の有料noteとして『読者がどう判断し、次に何をすべきか』を
明確にするDecision Intelligence記事を作成してください。

【読者】CTO、テックリード、PM、AI/ソフトウェア導入の意思決定者。
【最重要原則】単純要約ではなく、採用/PoC/監視/見送りを判断できる状態を作ること。

【一次情報優先順位】
1. 下記Source Native Context
2. URL Context等で取得されたPrimary URLの内容
3. Google Search Grounding（有効な場合）
4. モデル内部知識（補助のみ）

【事実性ルール】
・一次情報にない性能値、ベンチマーク、導入企業、利用者数、売上、価格、コスト削減額、
  市場シェア、検証結果、移行期間、資金調達額等を事実として作らない。
・確認できないことは『一次情報からは確認できない』と明示する。
・推論は『〜と考えられる』『〜の可能性がある』等、推論と分かる表現にする。
・実際に利用していないのに『使ってみた』『検証した』と書かない。
・一次情報を長文引用せず、要約・分析・パラフレーズする。

【対象】
・出所: {source}
・名前: {name}
・Primary URL: {url}
・{metric_label}: {stars}
{metric_note}・概要: {desc}
・事前Grounding: {grounding_status_hint}

【Source Native Context】
{context or '（source-native本文は取得できていない。URL Contextが有効ならPrimary URLを優先して確認すること。）'}
{feedback}

【管理用データ】
各項目は必ず全角中黒『・』で開始し、順序を変更しない。
・Source Summary: 一次情報で何が発表・開発・提案されたかを日本語1〜3文で要約。
・What(概要): 日本語2文以内。何が起きているか。
・Why Important(導入インパクト): 実務・プロダクトへの具体的影響。
・技術的パラダイムシフト: 既存→新方式→何が変わるか。
・代替との比較: 比較可能な具体的代替を挙げ、最後に『結局どれを選ぶべきか』まで述べる。
・移行コストとリスク: 技術、学習、移行、運用、ロックイン、破壊的変更のうち該当項目。
・Decision: NOW / TRY / WATCH / WAIT / AVOID のいずれか1つ。
・Decision Reason: 最大3理由。Fact → Meaning → Decision implication が分かるようにする。
・Decision Score:
  ・Business Impact(25点満点): X点 - 根拠
  ・Technical Impact(25点満点): X点 - 根拠
  ・Urgency(20点満点): X点 - 根拠
  ・Market Impact(15点満点): X点 - 根拠
  ・Reliability(15点満点): X点 - Groundingの強さ・一次情報の鮮度/信頼性を含む根拠
  ・合計: X / 100点
・Why NOT Important(スルーしてよい理由): 誰には今不要かと根拠。
・Who Should Use: 今検討すべき具体的なユーザー/企業/チーム。
・Who Should NOT Use: 今は検討不要な具体的なユーザー/企業/チーム。
・Action: 今週中に取れる具体的な次の一手。
・Future Scenario: 3〜12ヶ月について最低2つ。Condition → Possible Result → Indicator to Watch。
・Article Value: 0〜100。このテーマを500円単品noteとして提供する価値。

管理用データ直後に必ず次の専用行を1行だけ出す。
{SECTION_SPLIT_TOKEN}

その次の1行を記事タイトルとし、#は付けない。誇張・煽りすぎを避けつつ、判断したくなるタイトルにする。

【note本文：必須構造】
## この記事の結論
## なぜ今、この情報を見るべきなのか
## What｜これは何か
## 何が従来と違うのか
## ここまでの要点

---有料エリア---

### 私の判定
Decision / Decision Score / 一言結論。

### なぜそう判断したのか
最大3理由。Fact → Meaning → Decision。

### 本当に変わるのは何か
Technical Paradigm Shift。

### 既存の選択肢と比べるとどうか
具体的Alternativeと『結局どれを選ぶべきか』。

### 誰が使うべきか
Who Should Use。

### 誰は使わなくていいか
Who Should NOT Use。

### 導入コストとリスク
技術/学習/移行/運用/ロックイン等を事実と推論を分けて記述。

### 私ならこう試す
STEP 1 / STEP 2 / STEP 3 の小規模PoC。

### 3〜12ヶ月で起こり得ること
未来を断定せず、条件付きシナリオを最低2つ。

### 最終判断
『私なら○○する』という明確な判断。

【Markdown】
・見出しは上記##/###を厳守。
・重要語は**太字**。括弧は太字の外側。
・箇条書きは '- '。
・コードブロック不要。
・境界以外の単独行 '---' は使わない。
・有料エリアは1800〜2500字程度を目標とし、最低でも1200字を下回らないこと。
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
    """管理用データとnote本文を分離し、Decision Intelligence項目を抽出する。"""
    parts = full_text.split(SECTION_SPLIT_TOKEN, 1)
    management_data = parts[0]
    if len(parts) > 1:
        title_text, note_draft = _extract_note_title(parts[1].strip())
    else:
        title_text, note_draft = "（タイトル抽出失敗）", ""

    NEXT_ITEM = r"(?=\n・[^\n]+[:：]|\n\n|$)"
    total_match = re.search(r"合計[:：]?\s*(\d+)\s*/\s*100", management_data)
    score = int(total_match.group(1)) if total_match else 0
    breakdown_match = re.search(
        r"・Decision Score[:：]\s*(.*?)(?=\n・Why NOT Important|\n・Who Should Use|\n・Action|\n・Future Scenario|\n・Article Value|$)",
        management_data, re.DOTALL,
    )
    score_breakdown_text = breakdown_match.group(1).strip() if breakdown_match else ""

    def extract_field(label: str, fallback: str = "") -> str:
        m = re.search(rf"・{re.escape(label)}[^:：\n]*[:：]\s*(.*?){NEXT_ITEM}", management_data, re.DOTALL)
        return m.group(1).strip() if m else fallback

    article_raw = extract_field("Article Value", "0")
    article_match = re.search(r"(\d{1,3})", article_raw)
    article_value = min(100, max(0, int(article_match.group(1)))) if article_match else 0
    decision_text = extract_field("Decision", "").strip().upper()

    return {
        "note_draft": note_draft,
        "title_text": title_text,
        "score": score,
        "score_breakdown_text": score_breakdown_text,
        "source_summary_text": extract_field("Source Summary"),
        "what_text": extract_field("What"),
        "why_important_text": extract_field("Why Important"),
        "paradigm_shift_text": extract_field("技術的パラダイムシフト"),
        "alternative_comparison_text": extract_field("代替との比較"),
        "migration_cost_text": extract_field("移行コストとリスク"),
        "decision_text": decision_text,
        "decision_reason_text": extract_field("Decision Reason"),
        "why_not_important_text": extract_field("Why NOT Important"),
        "who_should_use_text": extract_field("Who Should Use"),
        "who_should_not_use_text": extract_field("Who Should NOT Use"),
        "action_text": extract_field("Action"),
        "future_scenario_text": extract_field("Future Scenario"),
        "article_value": article_value,
    }


def _is_meaningful_field(value: str) -> bool:
    value = (value or "").strip()
    return bool(value) and value not in {"特記事項なし", "概要参照", "アクション参照", "内訳取得失敗"}


def validate_paid_article(parsed: dict, repo_name: str) -> tuple[bool, list[str]]:
    """文章の好みではなく、500円記事としての機械的最低条件だけを検証する。"""
    failures: list[str] = []
    draft = parsed.get("note_draft", "")
    marker = PAID_AREA_PATTERN.search(draft)
    paid_part = ""
    paid_len = 0
    if not marker:
        failures.append("paid marker missing")
    else:
        paid_part = draft[marker.end():].strip()
        paid_len = len(normalize_markdown_for_note(paid_part))
        if paid_len < MIN_PAID_AREA_LENGTH:
            failures.append(f"paid area {paid_len} chars < {MIN_PAID_AREA_LENGTH}")

    required_fields = {
        "Decision Reason": "decision_reason_text",
        "Paradigm Shift": "paradigm_shift_text",
        "Alternative Comparison": "alternative_comparison_text",
        "Migration Cost": "migration_cost_text",
        "Why NOT Important": "why_not_important_text",
        "Who Should Use": "who_should_use_text",
        "Who Should NOT Use": "who_should_not_use_text",
        "Action": "action_text",
        "Future Scenario": "future_scenario_text",
        "Source Summary": "source_summary_text",
    }
    decision = parsed.get("decision_text", "")
    if decision not in ALLOWED_DECISIONS:
        failures.append("Decision missing/invalid")
    if not parsed.get("score"):
        failures.append("Decision Score missing")
    for label, key in required_fields.items():
        if not _is_meaningful_field(str(parsed.get(key, ""))):
            failures.append(f"{label} missing")
    required_headings = {
        "この記事の結論": r"^##\s*この記事の結論\s*$",
        "なぜ今、この情報を見るべきなのか": r"^##\s*なぜ今、この情報を見るべきなのか\s*$",
        "What｜これは何か": r"^##\s*What｜これは何か\s*$",
        "何が従来と違うのか": r"^##\s*何が従来と違うのか\s*$",
        "ここまでの要点": r"^##\s*ここまでの要点\s*$",
        "私の判定": r"^###\s*私の判定\s*$",
        "なぜそう判断したのか": r"^###\s*なぜそう判断したのか\s*$",
        "本当に変わるのは何か": r"^###\s*本当に変わるのは何か\s*$",
        "既存の選択肢と比べるとどうか": r"^###\s*既存の選択肢と比べるとどうか\s*$",
        "誰が使うべきか": r"^###\s*誰が使うべきか\s*$",
        "誰は使わなくていいか": r"^###\s*誰は使わなくていいか\s*$",
        "導入コストとリスク": r"^###\s*導入コストとリスク\s*$",
        "私ならこう試す": r"^###\s*私ならこう試す\s*$",
        "3〜12ヶ月で起こり得ること": r"^###\s*3〜12ヶ月で起こり得ること\s*$",
        "最終判断": r"^###\s*最終判断\s*$",
    }
    for label, heading in required_headings.items():
        if not re.search(heading, draft, re.MULTILINE):
            failures.append(f"required heading missing: {label}")
    return (not failures, failures)


def _extract_usage_metadata(response) -> None:
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        return
    fields = ["prompt_token_count", "tool_use_prompt_token_count", "candidates_token_count", "total_token_count"]
    values = []
    for f in fields:
        v = getattr(usage, f, None)
        if v is not None:
            values.append(f"{f}={v}")
    if values:
        logger.info("[GEMINI USAGE] " + " ".join(values))


def extract_grounding_metadata(response, primary_url: str, source_native_sufficient: bool,
                               url_context_requested: bool, search_requested: bool) -> dict:
    """SDKのoptional metadataを壊れにくく抽出し、Notion用Grounding Statusを返す。"""
    evidence: list[str] = []
    if primary_url:
        evidence.append(primary_url)
    url_success = False
    search_used = False
    try:
        candidate = response.candidates[0]
        url_meta = getattr(candidate, "url_context_metadata", None)
        for item in (getattr(url_meta, "url_metadata", None) or []):
            retrieved = getattr(item, "retrieved_url", None)
            status = str(getattr(item, "url_retrieval_status", ""))
            if "SUCCESS" in status.upper():
                url_success = True
                if retrieved and retrieved not in evidence:
                    evidence.append(retrieved)
        grounding = getattr(candidate, "grounding_metadata", None)
        queries = getattr(grounding, "web_search_queries", None) or []
        chunks = getattr(grounding, "grounding_chunks", None) or []
        search_used = bool(queries or chunks)
        for chunk in chunks:
            web = getattr(chunk, "web", None)
            uri = getattr(web, "uri", None) if web else None
            if uri and uri not in evidence:
                evidence.append(uri)
    except Exception as e:
        logger.debug(f"[GROUNDING META] metadata抽出をスキップ: {e}")

    if not source_native_sufficient and url_context_requested and not url_success:
        status = GROUNDING_FAILED
    elif url_context_requested and url_success and search_requested and search_used:
        status = GROUNDING_URL_SEARCH
    elif url_context_requested and url_success:
        status = GROUNDING_URL_CONTEXT
    elif source_native_sufficient:
        status = GROUNDING_SOURCE_NATIVE
    else:
        status = GROUNDING_FAILED
    return {"grounding_status": status, "evidence_urls": evidence[:3]}


def _should_use_url_context(repo: dict, source_info: dict) -> bool:
    if not ENABLE_URL_CONTEXT:
        return False
    primary = source_info.get("primary_url", "")
    if not primary.startswith(("http://", "https://")):
        return False
    # HN/PHは外部ページ本文が商品価値に直結。GitHub README/arXiv abstractが十分なら
    # URL Contextを重ねず入力tokenを節約する。SearchをONにした場合はURLも併用。
    return ENABLE_GOOGLE_SEARCH_GROUNDING or not source_info.get("sufficient") or repo.get("source") in {"HackerNews", "ProductHunt"}


def call_gemini_grounded_deep_dive(prompt: str, repo: dict, source_info: dict,
                                    request_kind: str = "deep_dive"):
    """Deep Dive専用generateContent。URL Context/Searchを同一call内で使いBudgetを守る。"""
    use_url = _should_use_url_context(repo, source_info)
    use_search = ENABLE_GOOGLE_SEARCH_GROUNDING
    tools = []
    if use_url:
        tools.append({"url_context": {}})
    if use_search:
        tools.append({"google_search": {}})

    # source-nativeもURL Contextも無い候補は、タイトルだけで有料記事を生成しない。
    if not source_info.get("sufficient") and not use_url:
        raise ValueError("一次情報不足: source-native不十分かつURL Context利用不可")

    current_tools = tools
    for attempt in range(2):
        kind = request_kind if attempt == 0 else "deep_dive_retry"
        try:
            time.sleep(3)
            _consume_gemini_request(kind)
            config = {"max_output_tokens": GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS}
            if current_tools:
                config["tools"] = current_tools
            response = client.models.generate_content(
                model=SELECTED_MODEL,
                contents=prompt,
                config=config,
            )
            _extract_usage_metadata(response)
            meta = extract_grounding_metadata(
                response,
                source_info.get("primary_url", ""),
                bool(source_info.get("sufficient")),
                any("url_context" in t for t in current_tools),
                any("google_search" in t for t in current_tools),
            )
            return response, meta
        except GeminiBudgetExceededError:
            raise
        except APIError as e:
            code = getattr(e, "code", None)
            quota_type = classify_gemini_quota_error(e) if code == 429 else ""
            if code == 429 and quota_type in {"RPD", "DAILY_TOKEN"}:
                raise DailyQuotaExhaustedError(str(e)) from e
            if attempt == 0 and GEMINI_BUDGET.can_deep_dive_retry():
                # TPM時は巨大URL Contextを外し、十分なsource-nativeだけで救済。
                if code == 429 and quota_type == "TPM" and source_info.get("sufficient"):
                    current_tools = [t for t in current_tools if "url_context" not in t and "google_search" not in t]
                    logger.warning("[DEEP DIVE TPM] Grounding toolsを外してsource-nativeのみで1回救済")
                    time.sleep(_extract_retry_delay(e, 15))
                    continue
                if code in (429, 503):
                    time.sleep(_extract_retry_delay(e, 15))
                    continue
            raise

def _paid_area_length(note_draft: str, repo_name: str) -> int:
    """クレンジング後の有料エリアの文字数を返す（品質ゲートの判定基準）。"""
    _, paid_part = split_free_paid(note_draft, repo_name)
    return len(normalize_markdown_for_note(paid_part))

def generate_intelligence_report(repo, notion_page_id: str | None = None,
                                 screening_score: int | None = None,
                                 screening_reason: str = ""):
    """Grounded Deep Diveを生成し、構造Quality Gateで最大1回だけ救済する。"""
    name = repo.get("nameWithOwner")
    desc = repo.get("description", "説明なし")
    url = repo.get("url")
    stars = repo.get("stargazerCount", 0)
    source = repo.get("source", "GitHub")
    published_at = repo.get("publishedAt")
    _, spdx_id = legal_safety_gate(repo)

    source_info = prepare_source_context(repo)
    primary_url = source_info.get("primary_url") or url
    # APIを呼ぶ前に一次情報不足を判定できるならBackfillへ回す。
    if not source_info.get("sufficient") and not (ENABLE_URL_CONTEXT and primary_url.startswith(("http://", "https://"))):
        logger.warning(f"[GROUNDING FAILED] {name}: 一次情報不足のためGeminiを呼ばずスキップ")
        page_id = notion_page_id
        if not page_id and screening_score is not None:
            page_id = save_screening_metadata_to_notion(repo, screening_score, screening_reason or "Deep Dive候補")
        if page_id:
            update_notion_quality_failed(page_id, name, GROUNDING_FAILED, [primary_url] if primary_url else [])
        return None

    quality_feedback = ""
    last_grounding = {"grounding_status": source_info.get("method", GROUNDING_METADATA_ONLY), "evidence_urls": [primary_url] if primary_url else []}

    try:
        parsed = None
        for attempt in range(MAX_QUALITY_RETRIES + 1):
            request_kind = "deep_dive" if attempt == 0 else "quality_retry"
            prompt = build_decision_prompt(
                name, primary_url, stars, desc, quality_feedback, source,
                source_context=source_info.get("context", ""),
                grounding_status_hint=source_info.get("method", GROUNDING_METADATA_ONLY),
            )
            response, grounding = call_gemini_grounded_deep_dive(prompt, repo, source_info, request_kind=request_kind)
            last_grounding = grounding
            parsed = _parse_gemini_response(response.text or "")
            parsed.update({
                "grounding_status": grounding.get("grounding_status", GROUNDING_FAILED),
                "evidence_urls_text": "\n".join(grounding.get("evidence_urls", [])),
            })
            quality_ok, failures = validate_paid_article(parsed, name)
            # Grounding自体がFailedなら有料記事として不合格。
            if parsed["grounding_status"] == GROUNDING_FAILED:
                failures.append("Grounding failed")
                quality_ok = False
            if quality_ok:
                break
            if attempt >= MAX_QUALITY_RETRIES:
                logger.error(f"[QUALITY GATE FAILED] {name}: {', '.join(failures)}")
                page_id = notion_page_id
                if not page_id and screening_score is not None:
                    page_id = save_screening_metadata_to_notion(repo, screening_score, screening_reason or "Deep Dive候補")
                if page_id:
                    update_notion_quality_failed(page_id, name, parsed.get("grounding_status", GROUNDING_FAILED), grounding.get("evidence_urls", []))
                send_telegram_alert(f"ℹ️ Quality Failed: {name}\n" + " / ".join(failures)[:1500])
                return None
            quality_feedback = "前回出力の不足項目: " + "; ".join(failures)
            logger.warning(f"[QUALITY RETRY] {name}: {quality_feedback}")

        if not parsed:
            return None

        evidence_urls = last_grounding.get("evidence_urls", [])
        clean_manuscript = build_clean_note_manuscript(
            parsed["note_draft"], name, url, spdx_id, source, evidence_urls=evidence_urls,
        )

        eyecatch_url = ""
        try:
            os.makedirs(EYECATCH_OUTPUT_DIR, exist_ok=True)
            eyecatch_filename = f"{_sanitize_filename(name)}.png"
            eyecatch_path = os.path.join(EYECATCH_OUTPUT_DIR, eyecatch_filename)
            generate_eyecatch_image(parsed["title_text"], eyecatch_path, source)
            logger.info(f"[EYECATCH] {name} -> {eyecatch_path} を生成しました。")
            eyecatch_url = upload_eyecatch_to_github(eyecatch_path, eyecatch_filename) or ""
        except Exception as e:
            logger.warning(f"[EYECATCH SKIP] {name}: {e}")

        analyzed_at = _analyzed_at_now_iso()
        if notion_page_id:
            upgrade_notion_page_with_report(
                notion_page_id,
                name, url, parsed["score"], parsed["score_breakdown_text"], parsed["what_text"],
                parsed["why_important_text"], parsed["why_not_important_text"], parsed["action_text"],
                spdx_id, clean_manuscript, parsed["paradigm_shift_text"],
                parsed["alternative_comparison_text"], parsed["migration_cost_text"],
                source, stars, parsed["title_text"], eyecatch_url, published_at, analyzed_at,
                report_meta=parsed,
            )
        else:
            save_to_notion(
                name, url, parsed["score"], parsed["score_breakdown_text"], parsed["what_text"],
                parsed["why_important_text"], parsed["why_not_important_text"], parsed["action_text"],
                spdx_id, clean_manuscript, parsed["paradigm_shift_text"],
                parsed["alternative_comparison_text"], parsed["migration_cost_text"],
                source, stars, parsed["title_text"], eyecatch_url, published_at, analyzed_at,
                report_meta=parsed, screening_score=screening_score, screening_reason=screening_reason,
            )
        return clean_manuscript

    except DailyQuotaExhaustedError:
        raise
    except GeminiBudgetExceededError as e:
        logger.warning(f"[GEMINI BUDGET STOP] {name}: {e}")
        return None
    except Exception as e:
        logger.error(f"[DEEP DIVE FAILED] {name}: {e}")
        page_id = notion_page_id
        if not page_id and screening_score is not None:
            page_id = save_screening_metadata_to_notion(repo, screening_score, screening_reason or "Deep Dive候補")
        if page_id:
            update_notion_quality_failed(page_id, name, last_grounding.get("grounding_status", GROUNDING_FAILED), last_grounding.get("evidence_urls", []))
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
    """Step1軽量Screening。共有Retry BudgetとDeep Dive予約枠を必ず守る。"""
    name = repo.get("nameWithOwner")
    desc = repo.get("description", "説明なし")
    stars = repo.get("stargazerCount", 0)
    source = repo.get("source", "GitHub")
    prompt = build_screening_prompt(name, desc, stars, source)

    for attempt in range(2):
        if attempt > 0 and not GEMINI_BUDGET.can_screening_retry():
            break
        kind = "screening" if attempt == 0 else "screening_retry"
        try:
            time.sleep(SCREENING_PACING_SECONDS)
            response = _generate_via_chat(
                SELECTED_MODEL, prompt,
                config={"max_output_tokens": 30},
                request_kind=kind,
                reserve=GEMINI_RESERVED_DEEP_DIVE_REQUESTS,
            )
            parsed = _parse_screening_response(response.text)
            logger.info(f"[SCREENED] {name}: {parsed['score']}点 ({parsed['reason']})")
            return {"repo": repo, "score": parsed["score"], "reason": parsed["reason"]}
        except GeminiBudgetExceededError:
            logger.warning(f"[SCREENING BUDGET STOP] {name}: Deep Dive予約枠を保護して停止")
            return {"repo": repo, "score": 0, "reason": "Gemini予算保護で未審査"}
        except APIError as e:
            code = getattr(e, "code", None)
            if code == 429 and _is_daily_quota_exhausted(e):
                raise DailyQuotaExhaustedError(str(e)) from e
            if (code in (429, 503) and attempt == 0 and GEMINI_BUDGET.can_screening_retry()
                    and GEMINI_BUDGET.can_request(reserve=GEMINI_RESERVED_DEEP_DIVE_REQUESTS)):
                time.sleep(_extract_retry_delay(e, 10))
                continue
            logger.error(f"[SCREENING FAILED] {name}: {e}")
            return {"repo": repo, "score": 0, "reason": "スクリーニング失敗"}
        except Exception as e:
            logger.error(f"[SCREENING UNEXPECTED ERROR] {name}: {e}")
            return {"repo": repo, "score": 0, "reason": "想定外エラー"}
    return {"repo": repo, "score": 0, "reason": "Retry予算上限"}



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
    logger.info(" 完全無人インテリジェンス工場 パイプライン起動（Grounded Decision Intelligence版）")
    logger.info("==========================================")
    check_stale_content()

    github_items = fetch_github_trending()
    hackernews_items = fetch_hackernews_top()
    arxiv_items = fetch_arxiv_ai_ml()
    producthunt_items = fetch_producthunt_trending()
    repos = github_items + hackernews_items + arxiv_items + producthunt_items
    logger.info(
        f"[MULTI-SOURCE] GitHub:{len(github_items)} HN:{len(hackernews_items)} "
        f"ArXiv:{len(arxiv_items)} PH:{len(producthunt_items)} 合計:{len(repos)}"
    )

    safe_repos = []
    for repo in repos:
        is_safe, license_status = legal_safety_gate(repo)
        if not is_safe:
            logger.info(f" [SKIP: LICENSE] {repo.get('nameWithOwner')} -> {license_status}")
            continue
        safe_repos.append(repo)

    existing_urls = get_existing_repo_urls()
    if existing_urls is None:
        logger.error("[PIPELINE ABORTED] 重複チェック不能のためFail-Closed停止")
        logger.info(GEMINI_BUDGET.summary())
        return

    deduped_repos = []
    for repo in safe_repos:
        repo_url = (repo.get("url") or "").rstrip("/")
        if repo_url in existing_urls:
            logger.info(f" [SKIP: DUPLICATE] {repo.get('nameWithOwner')}")
            continue
        deduped_repos.append(repo)
    if not deduped_repos:
        logger.info("本日は新規候補が0件でした。")
        logger.info(GEMINI_BUDGET.summary())
        return

    if len(deduped_repos) > MAX_SCREENING_CANDIDATES:
        logger.warning(
            f"[SCREENING CAP] {len(deduped_repos)}件→先頭{MAX_SCREENING_CANDIDATES}件。"
            "無料枠保護のため残りは今回未審査。"
        )
        deduped_repos = deduped_repos[:MAX_SCREENING_CANDIDATES]

    logger.info(f">>> 軽量スクリーニング開始（最大 {len(deduped_repos)} 件）")
    screened = []
    daily_quota_stop = False
    try:
        for repo in deduped_repos:
            if not GEMINI_BUDGET.can_request(reserve=GEMINI_RESERVED_DEEP_DIVE_REQUESTS):
                logger.warning("[SCREENING STOP] Deep Dive予約枠を守るためScreening終了")
                break
            screened.append(screen_repo(repo))
    except DailyQuotaExhaustedError:
        send_telegram_alert("⚠️ Gemini APIの日次クォータに到達しました（Screening中）。部分結果はNotionへ保存します。")
        logger.error("日次クォータ到達。Gemini処理は止めるが、完了済みScreeningはStock保存する。")
        daily_quota_stop = True

    screened.sort(key=lambda x: (x["score"], x["repo"].get("stargazerCount", 0)), reverse=True)

    stocked_count = 0
    for item in screened:
        if item["score"] >= NOTION_SAVE_THRESHOLD_SCORE:
            item["notion_page_id"] = save_screening_metadata_to_notion(item["repo"], item["score"], item["reason"])
            if item["notion_page_id"]:
                stocked_count += 1
        else:
            item["notion_page_id"] = None

    logger.info(f">>> Screening {len(screened)}件 / Stock {stocked_count}件")

    if daily_quota_stop:
        logger.info(GEMINI_BUDGET.summary())
        generate_monthly_digest()
        return

    # TOP_Nは『候補数』ではなく『最大成功記事数』。失敗時は4位・5位へBackfillする。
    generated_count = 0
    attempted = 0
    candidates = [x for x in screened if x.get("score", 0) > 0]
    for candidate in candidates:
        if generated_count >= TOP_N_FOR_DEEP_DIVE:
            break
        if attempted >= MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS:
            break
        if not GEMINI_BUDGET.can_request():
            logger.warning("[DEEP DIVE STOP] Gemini local budget残量なし")
            break
        attempted += 1
        repo = candidate["repo"]
        name = repo.get("nameWithOwner")
        logger.info(f" [DEEP DIVE {attempted}] {name}（Screening {candidate['score']}点）")
        try:
            report = generate_intelligence_report(
                repo,
                notion_page_id=candidate.get("notion_page_id"),
                screening_score=candidate.get("score"),
                screening_reason=candidate.get("reason", ""),
            )
            if report:
                generated_count += 1
        except DailyQuotaExhaustedError:
            send_telegram_alert("⚠️ Gemini APIの日次クォータに到達しました（Deep Dive中）。")
            daily_quota_stop = True
            break

    if generated_count == 0:
        reason = "daily quota" if daily_quota_stop else "source/quality/API/budget"
        send_telegram_alert(f"⚠️ 本日のDeep Dive記事生成は0件でした。原因区分: {reason}")

    if generated_count > 0 or stocked_count > 0:
        msg = (
            f"✅ 【AI note事業】Screening {len(screened)}件、Stock {stocked_count}件、"
            f"Deep Dive Ready {generated_count}件（試行{attempted}件）。\n"
            f"{GEMINI_BUDGET.summary()}\nhttps://notion.so/{NOTION_DATABASE_ID}"
        )
        send_telegram_alert(msg)
        logger.info(msg)
    else:
        logger.info("本日は生成条件を満たす記事・Stockがありませんでした。")

    generate_monthly_digest()
    logger.info(GEMINI_BUDGET.summary())


if __name__ == "__main__":
    main()
