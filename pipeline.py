import os
import sys
import json
import unicodedata

# Keep the synthetic suite isolated from all network, credential, DB, and
# publish side effects. It uses the installed production validation module so
# its assertions remain coupled to pipeline.py.
if os.environ.get("SYNTHETIC_REGRESSION_MODE", "false").lower() in {"1", "true", "yes", "on"} and __name__ == "__main__":
    from regression_suite import bootstrap, run, ROOT as _REGRESSION_ROOT
    _tier = os.environ.get("SYNTHETIC_REGRESSION_TIER", "smoke").lower()
    if _tier not in {"smoke", "core", "full"}:
        raise ValueError("SYNTHETIC_REGRESSION_TIER must be smoke, core, or full")
    _fixtures = _REGRESSION_ROOT / "regression_suite" / "fixtures"
    if not _fixtures.exists():
        bootstrap(_fixtures)
    _result = run(_fixtures, _tier)
    print(json.dumps({"tier": _result["tier"], "total": _result["total_cases"], "passed": _result["passed"], "critical_failures": _result["critical_failures"], "production_write_isolation": True}, ensure_ascii=False))
    sys.exit(1 if _result["critical_failures"] else 0)
import re
import time
import signal
from contextlib import contextmanager
import base64
import hashlib
import ipaddress
import socket
import requests
import logging
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urldefrag, parse_qsl, urlencode, urlunparse
from difflib import SequenceMatcher
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
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
NOTION_DATA_SOURCE_ID = os.environ.get("NOTION_DATA_SOURCE_ID")
NOTION_PUBLIC_DATABASE_ID = os.environ.get("NOTION_PUBLIC_DATABASE_ID")
NOTION_PUBLIC_DATA_SOURCE_ID = os.environ.get("NOTION_PUBLIC_DATA_SOURCE_ID")
NOTION_API_VERSION = os.environ.get("NOTION_API_VERSION", "2026-03-11")
ARTICLE_PUBLICATION_MODE = os.environ.get("ARTICLE_PUBLICATION_MODE", "free").strip().lower()
# This mode uses only the Notion API.  It never calls Gemini or source APIs.
PUBLIC_DB_SYNC_MODE = os.environ.get("PUBLIC_DB_SYNC_MODE", "false").lower() in {"1", "true", "yes", "on"}

# Product Huntのみ認証必須（Developer Token）。Hacker News / ArXivは認証不要。
# 未設定でもパイプライン全体は止めず、Product Hunt収集のみをスキップする
# （Fail-Safe設計。詳細はfetch_producthunt_trending内のガードを参照）。
PRODUCTHUNT_DEVELOPER_TOKEN = os.environ.get("PRODUCTHUNT_DEVELOPER_TOKEN")

# Synthetic regression is intentionally credential-free and must never touch the
# production DB/publish path. Ground Truth lives in regression_suite.py so it
# remains independent from production prompts and model calls.
SYNTHETIC_REGRESSION_MODE = os.environ.get("SYNTHETIC_REGRESSION_MODE", "false").lower() in {"1", "true", "yes", "on"}
SYNTHETIC_REGRESSION_TIER = os.environ.get("SYNTHETIC_REGRESSION_TIER", "smoke").lower()

# Importing this module must be side-effect free.  In particular, unit tests and
# the offline regression harness must not consume Gemini quota or require a
# GitHub repository simply by importing ``pipeline.py``.  Credential validation
# and model selection happen in initialize_runtime() immediately before a real
# production run.
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

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
    if client is None:
        raise NoAvailableModelError("GEMINI_API_KEY が設定されていません")
    _consume_gemini_request(request_kind, reserve=reserve, model_name=model_name)
    chat = client.chats.create(model=model_name, config=config) if config else client.chats.create(model=model_name)
    return chat.send_message(prompt)

SCREENING_MODEL_CANDIDATES = os.environ.get(
    "GEMINI_SCREENING_MODEL_CANDIDATES",
    "gemini-3.1-flash-lite"
).split(",")
SCREENING_MODEL_POOL = [m.strip() for m in SCREENING_MODEL_CANDIDATES if m.strip()]

DEEP_DIVE_MODEL_CANDIDATES = os.environ.get(
    "GEMINI_DEEP_DIVE_MODEL_CANDIDATES",
    "gemini-3.6-flash"
).split(",")
DEEP_DIVE_MODEL_POOL = [m.strip() for m in DEEP_DIVE_MODEL_CANDIDATES if m.strip()]

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
SCREENING_BATCH_SIZE = int(os.environ.get("SCREENING_BATCH_SIZE", "25"))
SCREENING_RECOVERY_BATCH_SIZE = int(os.environ.get("SCREENING_RECOVERY_BATCH_SIZE", "10"))
SCREENING_BATCH_MAX_OUTPUT_TOKENS = int(os.environ.get("SCREENING_BATCH_MAX_OUTPUT_TOKENS", "2500"))
SCREENING_BATCH_PACING_SECONDS = int(os.environ.get("SCREENING_BATCH_PACING_SECONDS", "10"))
ENABLE_GLOBAL_CALIBRATION = os.environ.get("ENABLE_GLOBAL_CALIBRATION", "true").lower() in {"1", "true", "yes", "on"}
GLOBAL_CALIBRATION_MIN_RAW_SCORE = int(os.environ.get("GLOBAL_CALIBRATION_MIN_RAW_SCORE", "55"))
GLOBAL_CALIBRATION_BATCH_SIZE = int(os.environ.get("GLOBAL_CALIBRATION_BATCH_SIZE", "50"))
GLOBAL_CALIBRATION_MAX_OUTPUT_TOKENS = int(os.environ.get("GLOBAL_CALIBRATION_MAX_OUTPUT_TOKENS", "4000"))
ENABLE_OBSERVED_HISTORY = os.environ.get("ENABLE_OBSERVED_HISTORY", "true").lower() in {"1", "true", "yes", "on"}
OBSERVED_HISTORY_DIR = os.environ.get("OBSERVED_HISTORY_DIR", "observed_history")
OBSERVED_HISTORY_GITHUB_DIR = os.environ.get("OBSERVED_HISTORY_GITHUB_DIR", OBSERVED_HISTORY_DIR).strip("/")

# 収集ソースが将来さらに増えてもRPD・RPMへの影響を一定範囲に抑え込むための
# スクリーニング対象数の上限（安全弁）。これを超えた分は「収集はしたが
# 審査対象からは除外」としてログに残す（黙って切り捨てない）。
# daily.yml と同じ既定値にして、ローカル／手動実行でも本番と同一の
# 収集・一括スクリーニング規模になるようにする。Geminiへの審査呼び出しは
# SCREENING_BATCH_SIZE（既定25）単位なので、200件でも通常は8リクエスト。
MAX_SCREENING_CANDIDATES = int(os.environ.get("MAX_SCREENING_CANDIDATES", "200"))
GITHUB_FETCH_LIMIT = int(os.environ.get("GITHUB_FETCH_LIMIT", "50"))
HN_FETCH_LIMIT = int(os.environ.get("HN_FETCH_LIMIT", "50"))
ARXIV_FETCH_LIMIT = int(os.environ.get("ARXIV_FETCH_LIMIT", "50"))
PRODUCTHUNT_FETCH_LIMIT = int(os.environ.get("PRODUCTHUNT_FETCH_LIMIT", "50"))

# ---- Gemini無料枠のローカル安全予算 ----
# Google側のFree Tier上限そのものではなく、このpipeline 1実行内で絶対に超えない
# 独自Safety Cap。実際のRPM/RPD/TPMはAI Studioのcurrent limitsを運用者が確認し、
# 必要に応じて環境変数でさらに低く設定する。
GEMINI_DAILY_REQUEST_BUDGET = int(os.environ.get("GEMINI_DAILY_REQUEST_BUDGET", "50"))
GEMINI_SCREENING_RETRY_BUDGET = int(os.environ.get("GEMINI_SCREENING_RETRY_BUDGET", "4"))
GEMINI_DEEP_DIVE_RETRY_BUDGET = int(os.environ.get("GEMINI_DEEP_DIVE_RETRY_BUDGET", "1"))
GEMINI_RESERVED_DEEP_DIVE_REQUESTS = int(os.environ.get("GEMINI_RESERVED_DEEP_DIVE_REQUESTS", "3"))
GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS = int(os.environ.get("GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS", "6000"))
GEMINI_DEEP_DIVE_DAILY_REQUEST_BUDGET = int(os.environ.get("GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET", os.environ.get("GEMINI_DEEP_DIVE_DAILY_REQUEST_BUDGET", "10")))
# 複数GitHub Actions Runをまたいで共有する永続Safety Cap。Googleの公式quota値ではなく、
# このプロジェクト独自の保守的な上限。RPDのリセット境界に合わせてAmerica/Los_Angeles日付で管理する。
GEMINI_PERSISTENT_DAILY_COUNTER = os.environ.get("GEMINI_PERSISTENT_DAILY_COUNTER", "true").lower() in {"1", "true", "yes", "on"}
GEMINI_PERSISTENT_DAILY_REQUEST_BUDGET = int(os.environ.get("GEMINI_PERSISTENT_DAILY_REQUEST_BUDGET", "18"))
GEMINI_PERSISTENT_COUNTER_PATH = os.environ.get("GEMINI_PERSISTENT_COUNTER_PATH", ".runtime/gemini_daily_usage.json")
GEMINI_COUNTER_BRANCH = os.environ.get("GEMINI_COUNTER_BRANCH", "").strip()
MODEL_DAILY_BUDGETS = {
    "gemini-3.5-flash-lite": int(os.environ.get("GEMINI_35_FLASH_LITE_DAILY_BUDGET", "450")),
    "gemini-3.1-flash-lite": int(os.environ.get("GEMINI_31_FLASH_LITE_DAILY_BUDGET", "450")),
    "gemini-3.6-flash": int(os.environ.get("GEMINI_36_FLASH_DAILY_BUDGET", "18")),
    "gemini-3.7-flash": int(os.environ.get("GEMINI_37_FLASH_DAILY_BUDGET", "18")),
    "gemini-3.5-flash": int(os.environ.get("GEMINI_35_FLASH_DAILY_BUDGET", "18")),
}
GEMINI_QUOTA_TIMEZONE = os.environ.get("GEMINI_QUOTA_TIMEZONE", "America/Los_Angeles")
MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS = int(os.environ.get("MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS", "5"))

# ---- 既存記事A/B比較用・再生成テストモード ----
# 通常運用では必ずFalse。TrueのときはNotion DB内の既存Deep Diveを読み出し、
# Screening / dedupe / Stock保存を通さず、現在のDeep Dive prompt + Quality Gateだけで
# 再生成する。Notionページの更新・新規作成、GitHubへのアイキャッチuploadは一切行わない。
# 生成稿はローカルのREGEN_TEST_OUTPUT_DIRへ保存するため、旧稿と安全に比較できる。
REGEN_TEST_MODE = os.environ.get("REGEN_TEST_MODE", "false").lower() in {"1", "true", "yes", "on"}
REGEN_TEST_LIMIT = int(os.environ.get("REGEN_TEST_LIMIT", "3"))
REGEN_TEST_SOURCE = os.environ.get("REGEN_TEST_SOURCE", "").strip()
REGEN_TEST_OUTPUT_DIR = os.environ.get("REGEN_TEST_OUTPUT_DIR", "regen_test_outputs")

# Deep Dive一次情報補強。URL ContextはScreeningには使わず、source-native情報が
# 不足する候補（特にHN/PH）を中心に使用する。Google Searchは別枠利用条件が
# 変わり得るため、運用者がAI Studioで確認して明示的に有効化するまでOFF。
ENABLE_URL_CONTEXT = os.environ.get("ENABLE_URL_CONTEXT", "true").lower() in {"1", "true", "yes", "on"}
ENABLE_GOOGLE_SEARCH_GROUNDING = os.environ.get("ENABLE_GOOGLE_SEARCH_GROUNDING", "false").lower() in {"1", "true", "yes", "on"}
SOURCE_CONTEXT_MAX_CHARS = int(os.environ.get("SOURCE_CONTEXT_MAX_CHARS", "12000"))
SOURCE_CONTEXT_MIN_CHARS = int(os.environ.get("SOURCE_CONTEXT_MIN_CHARS", "300"))
# HN / Product Huntの外部ページは、Gemini URL Contextより先にPythonで本文取得を試す。
# 外部HTTP取得はGemini quotaを消費しないため、URL Contextのtool token膨張を抑える。
WEB_CONTEXT_TIMEOUT_SECONDS = int(os.environ.get("WEB_CONTEXT_TIMEOUT_SECONDS", "12"))
WEB_CONTEXT_MAX_BYTES = int(os.environ.get("WEB_CONTEXT_MAX_BYTES", "750000"))
WEB_CONTEXT_USER_AGENT = os.environ.get(
    "WEB_CONTEXT_USER_AGENT",
    "Mozilla/5.0 (compatible; AI-Intelligence-Factory/1.0; +https://github.com/)"
)
DEEP_SOURCE_MAX_DOCUMENTS = int(os.environ.get("DEEP_SOURCE_MAX_DOCUMENTS", "4"))
DEEP_SOURCE_MAX_PDF_BYTES = int(os.environ.get("DEEP_SOURCE_MAX_PDF_BYTES", "12000000"))
FRESHNESS_MAX_LINKS = int(os.environ.get("FRESHNESS_MAX_LINKS", "8"))

# 記事タイトルから自動生成するアイキャッチ画像（PNG）の保存先ディレクトリ。
# note.comへのアップロードはAPI非対応のため自動化せず、ローカルに生成されたファイルを
# 運用者が手動でnoteの記事に添付する運用を想定する（詳細はgenerate_eyecatch_image参照）。
# 一方でNotion DBの「Eyecatch」プロパティ（ファイル＆メディア）にはURLが必要なため、
# 生成した画像はGitHubリポジトリへコミットし、raw.githubusercontent.comの
# 公開URLを取得した上でNotionへ紐付ける（詳細はupload_eyecatch_to_github参照）。
EYECATCH_OUTPUT_DIR = os.environ.get("EYECATCH_OUTPUT_DIR", "eyecatch_images")
EYECATCH_MIN_DECISION_SCORE = int(os.environ.get("EYECATCH_MIN_DECISION_SCORE", "60"))

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
PROP_REVIEW_STATUS = "Review Status"
REVIEW_STATUS_PUBLIC_APPROVED = "Public Approved"

CONTENT_STATUS_STOCKED = "Stocked"
CONTENT_STATUS_DEEP_DIVE = "Deep Dive"
CONTENT_STATUS_QUALITY_FAILED = "Quality Failed"
CONTENT_STATUS_PENDING_RETRY = "Pending Retry"
ARTICLE_STATUS_NOT_PLANNED = "Not Planned"
ARTICLE_STATUS_READY = "Ready"
ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW = "Needs Editorial Review"
VISIBILITY_SUBSCRIBER_ONLY = "Subscriber Only"
VISIBILITY_PAID_ARTICLE = "Paid Article"
VISIBILITY_FREE_ARTICLE = "Free Article"
GROUNDING_METADATA_ONLY = "Metadata Only"
GROUNDING_SOURCE_NATIVE = "Source Native"
GROUNDING_URL_CONTEXT = "URL Context"
GROUNDING_URL_SEARCH = "URL + Search"
GROUNDING_FAILED = "Failed"
ALLOWED_DECISIONS = {"NOW", "TRY", "WATCH", "WAIT", "AVOID"}


def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


def _notion_query_url(data_source_id: str | None = None, database_id: str | None = None) -> str:
    source_id = data_source_id if data_source_id is not None else NOTION_DATA_SOURCE_ID
    db_id = database_id if database_id is not None else NOTION_DATABASE_ID
    if source_id:
        return f"https://api.notion.com/v1/data_sources/{source_id}/query"
    return f"https://api.notion.com/v1/databases/{db_id}/query"


def _notion_schema_url(data_source_id: str | None = None, database_id: str | None = None) -> str:
    source_id = data_source_id if data_source_id is not None else NOTION_DATA_SOURCE_ID
    db_id = database_id if database_id is not None else NOTION_DATABASE_ID
    if source_id:
        return f"https://api.notion.com/v1/data_sources/{source_id}"
    return f"https://api.notion.com/v1/databases/{db_id}"


def _notion_parent(data_source_id: str | None = None, database_id: str | None = None) -> dict:
    source_id = data_source_id if data_source_id is not None else NOTION_DATA_SOURCE_ID
    db_id = database_id if database_id is not None else NOTION_DATABASE_ID
    return {"data_source_id": source_id} if source_id else {"database_id": db_id}

# 管理用データとnote原稿を分離するための構造トークン（Markdown記号ではない専用文字列にして
# normalize_markdown_for_note による処理や、Geminiによる表記揺れの影響を受けないようにする）
SECTION_SPLIT_TOKEN = "===NOTE_DRAFT_START==="

# 記事内の無料/有料エリアの境界検出。「---有料エリア---」を基本形としつつ、
# 記号の種類・全角半角・スペースの有無が多少ブレても検出できるよう正規表現で許容する。
# 「有料エリア」という文字列を必須にしているため、note.com対応Markdownとして
# 別途使われる素の水平線「---」（区切り線）と誤って衝突することはない。
PAID_AREA_PATTERN = re.compile(
    r"^[\s\-−ー―─━▼◆■●\*]{0,12}\s*(?:ここから先は\s*)?有料エリア(?:です)?\s*[\s\-−ー―─━▼◆■●\*]{0,12}$",
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


class PersistentGeminiDailyCounter:
    """モデル・APIキー単位で予約するGitHub永続Geminiカウンタ。

    旧版は全モデルを同じ18回に束ねていたため、Flash LiteのScreeningまで
    Deep Dive用の上限で停止していた。新形式はAPIキーの生値を保存せず、
    SHA-256短縮値をスコープとしてモデル別使用量だけを保存する。
    """
    def __init__(self, enabled: bool, model_budgets: int | dict[str, int], default_budget: int | str,
                 path: str | None = None, quota_timezone: str | None = None, api_key: str | None = None):
        # 旧4引数形式(enabled, budget, path, timezone)も壊さない。
        if isinstance(default_budget, str):
            quota_timezone, path, default_budget = path, default_budget, model_budgets
        self.enabled = enabled
        self.model_budgets = ({k: max(0, int(v)) for k, v in model_budgets.items()}
                              if isinstance(model_budgets, dict) else {})
        self.default_budget = max(0, int(default_budget))
        self.path = str(path or GEMINI_PERSISTENT_COUNTER_PATH).lstrip("/")
        self.quota_timezone = str(quota_timezone or GEMINI_QUOTA_TIMEZONE)
        self.repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
        self.branch = GEMINI_COUNTER_BRANCH or os.environ.get("GITHUB_REF_NAME", "").strip()
        self.key_scope = hashlib.sha256((api_key if api_key is not None else GEMINI_API_KEY or "").encode("utf-8")).hexdigest()[:16]
        self.session_used = 0

    def budget_for(self, model_name: str) -> int:
        return max(0, int(self.model_budgets.get(model_name, self.default_budget)))

    def _normalized_day(self, data: dict, quota_date: str) -> dict:
        # 旧形式(models/used/by_kind)は別APIキーの使用実績として引き継がない。
        if data.get("quota_date") != quota_date or not isinstance(data.get("key_scopes"), dict):
            return {"quota_date": quota_date, "key_scopes": {}}
        return data

    def _model_state(self, data: dict, model_name: str) -> dict:
        scopes = data.setdefault("key_scopes", {})
        scope = scopes.setdefault(self.key_scope, {"models": {}})
        models = scope.setdefault("models", {})
        return models.setdefault(model_name, {"used": 0, "by_kind": {}, "exhausted": False})

    def _quota_date(self) -> str:
        try:
            return datetime.now(ZoneInfo(self.quota_timezone)).date().isoformat()
        except Exception as e:
            raise GeminiBudgetExceededError(f"Persistent counter timezone error: {e}")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {GH_PAT}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _api_url(self) -> str:
        return f"https://api.github.com/repos/{self.repo}/contents/{self.path}"

    def _read_remote(self) -> tuple[dict, str | None]:
        if not self.repo or not GH_PAT:
            raise GeminiBudgetExceededError("Persistent Gemini counter requires GITHUB_REPOSITORY and GH_PAT")
        params = {"ref": self.branch} if self.branch else None
        try:
            res = requests.get(self._api_url(), headers=self._headers(), params=params, timeout=12)
        except Exception as e:
            raise GeminiBudgetExceededError(f"Persistent Gemini counter read failed: {e}")
        if res.status_code == 404:
            return {}, None
        if res.status_code != 200:
            raise GeminiBudgetExceededError(
                f"Persistent Gemini counter read failed: HTTP {res.status_code} {res.text[:300]}"
            )
        body = res.json()
        try:
            raw = base64.b64decode(body.get("content", "")).decode("utf-8")
            import json
            data = json.loads(raw) if raw.strip() else {}
        except Exception as e:
            raise GeminiBudgetExceededError(f"Persistent Gemini counter parse failed: {e}")
        return data, body.get("sha")

    def _write_remote(self, data: dict, sha: str | None) -> None:
        import json
        content = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        payload = {
            "message": f"chore: reserve Gemini request {data.get('quota_date','')} ({self.key_scope})",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        }
        if sha:
            payload["sha"] = sha
        if self.branch:
            payload["branch"] = self.branch
        try:
            res = requests.put(self._api_url(), headers=self._headers(), json=payload, timeout=15)
        except Exception as e:
            raise GeminiBudgetExceededError(f"Persistent Gemini counter write failed: {e}")
        if res.status_code not in (200, 201):
            raise GeminiBudgetExceededError(
                f"Persistent Gemini counter write failed: HTTP {res.status_code} {res.text[:300]}"
            )

    def reserve(self, kind: str, reserve: int = 0, model_name: str = "default") -> None:
        if not self.enabled:
            return
        budget = self.budget_for(model_name)
        if budget <= 0:
            raise GeminiBudgetExceededError("Persistent Gemini daily budget is 0")

        quota_date = self._quota_date()
        # SHA競合に備え、毎回最新値を取り直して最大3回だけ試す。
        for attempt in range(3):
            data, sha = self._read_remote()
            data = self._normalized_day(data, quota_date)
            sha_for_write = sha
            state = self._model_state(data, model_name)
            used = int(state.get("used", 0) or 0)
            effective_limit = max(0, budget - max(0, reserve))
            if used + 1 > effective_limit:
                raise GeminiBudgetExceededError(
                    f"Persistent Gemini daily budget exhausted: date={quota_date}, used={used}, "
                    f"budget={budget}, reserve={reserve}, model={model_name}, kind={kind}"
                )

            by_kind = state.get("by_kind") if isinstance(state.get("by_kind"), dict) else {}
            state["used"] = used + 1
            state["budget"] = budget
            state["by_kind"] = by_kind
            by_kind[kind] = int(by_kind.get(kind, 0) or 0) + 1
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            try:
                self._write_remote(data, sha_for_write)
                self.session_used += 1
                logger.info(
                    f"[GEMINI PERSISTENT BUDGET] reserved {state['used']}/{budget} "
                    f"quota_date={quota_date} model={model_name} kind={kind}"
                )
                return
            except GeminiBudgetExceededError as e:
                # 409/422の競合だけ再試行。それ以外はFail-Closed。
                msg = str(e)
                if attempt < 2 and ("HTTP 409" in msg or "HTTP 422" in msg):
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise

        raise GeminiBudgetExceededError("Persistent Gemini counter reservation failed after retries")

    def summary(self) -> str:
        if not self.enabled:
            return "Persistent Gemini Daily Counter: disabled"
        try:
            data, _ = self._read_remote()
            data = self._normalized_day(data, self._quota_date())
            models = data.get("key_scopes", {}).get(self.key_scope, {}).get("models", {})
            detail = ", ".join(f"{name}:{int(state.get('used', 0))}/{self.budget_for(name)}" for name, state in sorted(models.items())) or "0"
            return f"Persistent Gemini Daily Counter: {detail} ({data.get('quota_date')})"
        except Exception as e:
            return f"Persistent Gemini Daily Counter: unavailable ({e})"


PERSISTENT_GEMINI_COUNTER = PersistentGeminiDailyCounter(
    GEMINI_PERSISTENT_DAILY_COUNTER,
    MODEL_DAILY_BUDGETS,
    GEMINI_PERSISTENT_DAILY_REQUEST_BUDGET,
    GEMINI_PERSISTENT_COUNTER_PATH,
    GEMINI_QUOTA_TIMEZONE,
)


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
        if kind in {"screening_retry", "screening_recovery"}:
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


def _consume_gemini_request(kind: str, reserve: int = 0, model_name: str = "default") -> None:
    # 永続カウンタを先に予約する。ローカルBudget失敗時に1回過剰計上される可能性はあるが、
    # Free Tier保護では過少計上より安全なためFail-Closed側へ倒す。
    PERSISTENT_GEMINI_COUNTER.reserve(kind, reserve=reserve, model_name=model_name)
    GEMINI_BUDGET.consume(kind, reserve=reserve)


class DeepDiveModelBudget:
    """Deep Dive用上位モデルだけの1実行Safety Cap。永続Daily Counterとは別のローカル上限。"""
    def __init__(self, budget: int):
        self.budget = max(0, budget)
        self.used = 0

    def can_request(self) -> bool:
        return self.used + 1 <= self.budget

    def consume(self, kind: str) -> None:
        if not self.can_request():
            raise GeminiBudgetExceededError(
                f"Deep Dive model local budget exhausted: used={self.used}, budget={self.budget}, kind={kind}"
            )
        self.used += 1

    def summary(self) -> str:
        return f"Deep Dive Model Requests Used (per-run): {self.used}/{self.budget}"


DEEP_DIVE_MODEL_BUDGET = DeepDiveModelBudget(GEMINI_DEEP_DIVE_DAILY_REQUEST_BUDGET)


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

# Deep Dive Gemini 1回の最大待機時間。GitHub Actions上でSDK/networkが無応答に
# なった場合にジョブ全体が黙って止まるのを防ぐ。Linux runnerのmain threadで
# SIGALRMを使うため、待機中の同期SDK callもFail-Closedで中断できる。
GEMINI_DEEP_DIVE_CALL_TIMEOUT_SECONDS = int(os.environ.get("GEMINI_DEEP_DIVE_CALL_TIMEOUT_SECONDS", "120"))
GEMINI_DEEP_DIVE_CALL_PACING_SECONDS = int(os.environ.get("GEMINI_DEEP_DIVE_CALL_PACING_SECONDS", "20"))


class GeminiCallTimeoutError(TimeoutError):
    pass


@contextmanager
def _gemini_call_timeout(seconds: int):
    """main thread/Linux向けの同期Gemini call watchdog。"""
    seconds = max(1, int(seconds or 0))
    if not hasattr(signal, "SIGALRM"):
        # GitHub-hosted runnerはLinuxなので通常ここには来ない。
        yield
        return

    old_handler = signal.getsignal(signal.SIGALRM)

    def _handle_timeout(signum, frame):
        raise GeminiCallTimeoutError(f"Gemini call exceeded {seconds}s")

    signal.signal(signal.SIGALRM, _handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


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


def resolve_model(candidates: list[str], label: str = "Gemini", count_as_deep_dive: bool = False) -> str:
    """候補順=優先順位として軽量pingし、頻繁なGeminiモデル更新へ追随する。"""
    last_error: Exception | None = None
    for model_name in candidates:
        model_name = model_name.strip()
        if not model_name:
            continue
        for attempt in range(PING_MAX_RETRIES + 1):
            try:
                if count_as_deep_dive:
                    DEEP_DIVE_MODEL_BUDGET.consume("ping" if attempt == 0 else "ping_retry")
                _generate_via_chat(
                    model_name,
                    "ping",
                    config={"max_output_tokens": 8},
                    request_kind="ping" if attempt == 0 else "ping_retry",
                )
                logger.info(f"{label} モデル解決成功: {model_name}")
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


SELECTED_SCREENING_MODEL: str | None = None
SELECTED_DEEP_DIVE_MODEL: str | None = None
SESSION_EXHAUSTED_MODELS: set[str] = set()
SESSION_UNAVAILABLE_MODELS: set[str] = set()


def initialize_runtime() -> None:
    """Validate production-only requirements without spending quota on ping calls."""
    global SELECTED_SCREENING_MODEL, SELECTED_DEEP_DIVE_MODEL
    if PUBLIC_DB_SYNC_MODE or SYNTHETIC_REGRESSION_MODE:
        return
    if not GEMINI_API_KEY or not GH_PAT:
        raise ValueError("エラー: GEMINI_API_KEY または GH_PAT が設定されていません。")
    if not SCREENING_MODEL_POOL or not DEEP_DIVE_MODEL_POOL:
        raise ValueError("Gemini model candidate pool が空です。")
    # Availability is established by the first real request.  This avoids two
    # quota-consuming pings on every run and makes import/test completely safe.
    SELECTED_SCREENING_MODEL = SCREENING_MODEL_POOL[0]
    SELECTED_DEEP_DIVE_MODEL = DEEP_DIVE_MODEL_POOL[0]


def _mark_model_exhausted(model_name: str, reason: str = "") -> None:
    SESSION_EXHAUSTED_MODELS.add(model_name)
    logger.warning("[MODEL EXHAUSTED] %s %s", model_name, reason)


def _mark_model_unavailable(model_name: str, reason: str = "") -> None:
    SESSION_UNAVAILABLE_MODELS.add(model_name)
    logger.warning("[MODEL UNAVAILABLE] %s %s", model_name, reason)


def _call_model_pool(prompt: str, config: dict | None, kind: str, reserve: int,
                     pool: list[str], deep_dive: bool = False):
    """503 is run-local unavailable; RPD is model-local exhausted; both fall back.

    The loop is deliberately bounded by the configured pool.  It never retries
    indefinitely and never changes a transient 503 into a permanent quota mark.
    """
    last_error: Exception | None = None
    for model_name in pool:
        if model_name in SESSION_EXHAUSTED_MODELS or model_name in SESSION_UNAVAILABLE_MODELS:
            continue
        for attempt in range(2):
            try:
                if deep_dive:
                    DEEP_DIVE_MODEL_BUDGET.consume(kind if attempt == 0 else "deep_dive_retry")
                if deep_dive:
                    time.sleep(max(0, GEMINI_DEEP_DIVE_CALL_PACING_SECONDS))
                    with _gemini_call_timeout(GEMINI_DEEP_DIVE_CALL_TIMEOUT_SECONDS):
                        response = _generate_via_chat(
                            model_name, prompt, config=config,
                            request_kind=kind if attempt == 0 else "deep_dive_retry", reserve=reserve,
                        )
                else:
                    response = _generate_via_chat(
                        model_name, prompt, config=config,
                        request_kind=kind if attempt == 0 else "screening_retry", reserve=reserve,
                    )
                return response, model_name
            except APIError as exc:
                last_error = exc
                code = getattr(exc, "code", None)
                quota_type = classify_gemini_quota_error(exc) if code == 429 else ""
                if code == 429 and quota_type in {"RPD", "DAILY_TOKEN"}:
                    _mark_model_exhausted(model_name, quota_type)
                    break
                if code == 503 and attempt == 0:
                    time.sleep(_extract_retry_delay(exc, 10))
                    continue
                if code == 503:
                    _mark_model_unavailable(model_name, "503")
                    break
                if code == 404:
                    _mark_model_unavailable(model_name, "404")
                    break
                if code == 429 and quota_type in {"RPM", "TPM"} and attempt == 0:
                    time.sleep(_extract_retry_delay(exc, 15))
                    continue
                break
            except (GeminiBudgetExceededError, GeminiCallTimeoutError) as exc:
                last_error = exc
                break
    raise NoAvailableModelError("利用可能なGeminiモデルがありません") from last_error


def _call_screening_pool(prompt: str, config: dict | None = None, kind: str = "screening", reserve: int = 0):
    return _call_model_pool(prompt, config, kind, reserve, SCREENING_MODEL_POOL, deep_dive=False)


def _call_deep_dive_pool(prompt: str, config: dict | None = None, kind: str = "deep_dive"):
    return _call_model_pool(prompt, config, kind, 0, DEEP_DIVE_MODEL_POOL, deep_dive=True)


def call_gemini_with_smart_retry(prompt: str, max_retries: int = 1, request_kind: str = "deep_dive"):
    """非Groundedな既存互換call。無制限retryを禁止しLocal Budgetを必ず通す。"""
    for attempt in range(max_retries + 1):
        kind = request_kind if attempt == 0 else "deep_dive_retry"
        try:
            DEEP_DIVE_MODEL_BUDGET.consume(kind)
            time.sleep(3)
            return _generate_via_chat(SELECTED_DEEP_DIVE_MODEL, prompt, request_kind=kind)
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
    # 生成プロトコル用の制御文字がnote本文に残る事故を防ぐ。
    stripped = re.sub(r"(?mi)^\s*={3,}\s*NOTE_DRAFT_(?:START|END)\s*={0,}\s*$", "", stripped)
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
    if ARTICLE_PUBLICATION_MODE == "free":
        return PAID_AREA_PATTERN.sub("", note_draft).strip(), ""
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
        "- **発見経路**: Hacker News（記事タイトル・スコア等）。\n"
        "- **出典について**: 本文の技術的な事実・数値は、下記の公式リンクおよび参考情報で確認できる範囲を独自に分析・要約したものです。"
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

def _normalize_note_title(title: str) -> str:
    """noteのタイトル欄・本文先頭で共用する、短い完結タイトルに整える。"""
    title = re.sub(r"\s+", " ", (title or "").strip().lstrip("#").strip())
    title = title.strip('「」『』"')
    if title and not re.search(r"[。？]$", title):
        title += "。"
    return title


ARTICLE_DISCLAIMER = (
    "※本記事に含まれる見解・提案は筆者個人の意見であり、特定の効果・成果を保証するものではありません。"
    "導入・利用にあたっては、一次情報と自社の条件を確認してください。\n"
)

# 内部のDecision構造は固定したまま、noteで読者に見える見出しだけを記事ごとに変える。
# 名前から安定して選ぶため、Quality Retryで同じ記事の構成が無意味に揺れない。
ARTICLE_DISPLAY_VARIANTS = (
    {"intro": "はじめに", "conclusion": "まず、結論から", "why": "なぜ今、目を向けるのか。",
     "what": "何が起きている？", "key": "要点を整理すると。", "decision": "私なら今はこうする。", "final": "結局、どう見るか。",
     "opening": "reader_question", "intro_paragraphs": 3, "tone": "cautious_interest"},
    {"intro": "気になった背景", "conclusion": "先に判断を書くと。", "why": "地味だけれど、ここが大きい。",
     "what": "中身をざっくり見る。", "key": "見落としたくないポイント。", "decision": "実務で使うなら、私はこうする。", "final": "いま取るべき距離感。",
     "opening": "observation", "intro_paragraphs": 2, "tone": "practical_interest"},
    {"intro": "数字の前に見ておきたいこと", "conclusion": "この話をどう受け止めるか。", "why": "実務への影響はどこに出る？",
     "what": "仕組みは意外とシンプルです。", "key": "ここで判断が分かれる。", "decision": "私なら、まず小さく確かめる。", "final": "急がず、でも見逃さない。",
     "opening": "fact", "intro_paragraphs": 4, "tone": "skeptical_but_interesting"},
    {"intro": "現場で起きがちな課題から", "conclusion": "いま導入を急ぐべきか。", "why": "従来の前提と、どこが違うのか。",
     "what": "まずは何をしている技術なのか。", "key": "導入前に見ておきたいところ。", "decision": "私ならこの範囲で試す。", "final": "最後に、判断をまとめる。",
     "opening": "practical_problem", "intro_paragraphs": 3, "tone": "watch_and_wait"},
)


def _article_display_variant(name: str) -> dict:
    digest = hashlib.sha256((name or "article").encode("utf-8")).digest()[0]
    return ARTICLE_DISPLAY_VARIANTS[digest % len(ARTICLE_DISPLAY_VARIANTS)]


def build_clean_note_manuscript(note_draft: str, repo_name: str, repo_url: str,
                                 spdx_id: str, source: str = "GitHub",
                                 evidence_urls: list[str] | None = None,
                                 title_text: str = "", discovery_url: str = "") -> str:
    """note投稿用Markdownを組み立て、一次出典と最大3件のEvidence URLを末尾へ付与する。"""
    free_part, paid_part = split_free_paid(note_draft, repo_name)
    free_clean = normalize_markdown_for_note(free_part)
    paid_clean = normalize_markdown_for_note(paid_part)

    display_title = _normalize_note_title(title_text)
    manuscript = (f"# {display_title}\n\n" if display_title else "") + free_clean
    if paid_clean:
        manuscript += "\n\n" + paid_clean

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
        f"- **発見経路**: {source}\n"
        f"- **原資料**: リンク先の原著記事・技術報告\n"
        f"- **原資料URL**: [{repo_name}]({repo_url})\n"
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
    if discovery_url and discovery_url != repo_url:
        source_block += f"- **関連情報**: 発見元の[{source}投稿]({discovery_url})\n"

    manuscript += source_block + "\n" + ARTICLE_DISCLAIMER
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
                             source: str = "GitHub", decision_score: int | None = None,
                             technical_impact: int | None = None, urgency: int | None = None) -> str | None:
    """Preserve the source background and overlay the approved decision card."""
    if decision_score is not None and decision_score < EYECATCH_MIN_DECISION_SCORE:
        logger.info("[EYECATCH SKIP] score=%s < %s", decision_score, EYECATCH_MIN_DECISION_SCORE)
        return None
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

    # 80+ is red, 70s blue, and 60s teal.  Keep the background image visible.
    score = int(decision_score or 0)
    accent = (239, 68, 68) if score >= 80 else (59, 130, 246) if score >= 70 else (20, 184, 166)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((100, 285, 1180, 570), radius=24, fill=(5, 12, 28, 218), outline=accent + (255,), width=4)
    draw.rounded_rectangle((120, 325, 370, 382), radius=12, fill=accent + (255,))
    font_paths = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/truetype/lato/Lato-Bold.ttf"]
    def font(size: int):
        for path in font_paths:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
        return ImageFont.load_default()
    draw.text((137, 338), f"DECISION SCORE {score}/100", font=font(24), fill=(255, 255, 255, 255))
    title = (title_text or "AI Intelligence").replace("\n", " ")[:48]
    draw.text((125, 405), title, font=font(34), fill=(255, 255, 255, 255))
    draw.text((125, 485), f"Technical Impact  {technical_impact if technical_impact is not None else '—'}", font=font(21), fill=(220, 230, 245, 255))
    draw.text((610, 485), f"Urgency  {urgency if urgency is not None else '—'}", font=font(21), fill=(220, 230, 245, 255))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
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
        PROP_SUBSCRIPTION_VISIBILITY: {"select": {"name": VISIBILITY_FREE_ARTICLE if ARTICLE_PUBLICATION_MODE == "free" else VISIBILITY_PAID_ARTICLE}},
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
        "parent": _notion_parent(),
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
    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID):
        return False
    url = "https://api.notion.com/v1/pages"
    headers = _notion_headers()
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
    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID):
        return None

    name = repo.get("nameWithOwner")
    repo_url = repo.get("url")
    source = repo.get("source", "GitHub")
    engagement = repo.get("stargazerCount", 0)
    published_at = repo.get("publishedAt")
    # Analyzed At = このスクリーニング（Step1軽量分析）を実行した「いま」。
    analyzed_at = _analyzed_at_now_iso()

    url = "https://api.notion.com/v1/pages"
    headers = _notion_headers()
    payload = {
        "parent": _notion_parent(),
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
    headers = _notion_headers()
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
    headers = _notion_headers()
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


def update_notion_pending_retry(page_id: str, repo_name: str, reason: str = "") -> bool:
    """Transient provider failures must never be recorded as Quality Failed."""
    if not page_id or not NOTION_API_KEY:
        return False
    props = {
        PROP_CONTENT_STATUS: {"select": {"name": CONTENT_STATUS_PENDING_RETRY}},
        PROP_ARTICLE_STATUS: {"select": {"name": ARTICLE_STATUS_NOT_PLANNED}},
    }
    if reason:
        props[PROP_SCREENING_REASON] = {"rich_text": [{"text": {"content": reason[:2000]}}]}
    try:
        res = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", json={"properties": props}, headers=_notion_headers(), timeout=10)
        if res.status_code == 200:
            logger.info("[NOTION PENDING RETRY] %s", repo_name)
            return True
        logger.error("[NOTION PENDING RETRY ERROR] %s -> %s", repo_name, res.text)
    except Exception as exc:
        logger.error("[NOTION PENDING RETRY EXCEPTION] %s: %s", repo_name, exc)
    return False


def update_notion_needs_editorial_review(page_id: str, repo_name: str, reasons: list[str]) -> bool:
    """事実誤認とは分離し、公開だけを止めてStock資産を編集レビューへ回す。"""
    if not page_id or not NOTION_API_KEY:
        return False
    props = {
        PROP_ARTICLE_STATUS: {"select": {"name": ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW}},
        PROP_SCREENING_REASON: {"rich_text": [{"text": {"content": "Publication review: " + ", ".join(reasons)[:1900]}}]},
    }
    try:
        res = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", json={"properties": props}, headers=_notion_headers(), timeout=10)
        if res.status_code == 200:
            logger.info("[NOTION EDITORIAL REVIEW] %s", repo_name)
            return True
        logger.error("[NOTION EDITORIAL REVIEW ERROR] %s -> %s", repo_name, res.text)
    except Exception as exc:
        logger.error("[NOTION EDITORIAL REVIEW EXCEPTION] %s: %s", repo_name, exc)
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


class _ReadableHTMLTextParser(HTMLParser):
    """外部記事から本文候補を安全に抽出する標準ライブラリのみの軽量Parser。"""
    _SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "aside"}
    _BREAK_TAGS = {"title", "h1", "h2", "h3", "h4", "p", "li", "blockquote", "pre", "article", "main", "br"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth == 0 and tag in self._BREAK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self._SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth == 0 and tag in self._BREAK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0 and data:
            self._parts.append(data)

    def text(self) -> str:
        raw = unescape(" ".join(self._parts))
        lines = []
        previous = None
        for line in raw.splitlines():
            line = re.sub(r"\s+", " ", line).strip()
            if not line or line == previous:
                continue
            # ナビゲーション断片の大量混入を少し抑える。極端に短い断片は連続本文価値が低い。
            if len(line) < 2:
                continue
            lines.append(line)
            previous = line
        return "\n".join(lines)


class _ResearchLinkParser(HTMLParser):
    """本文とは別に、研究ページの一次資料リンクだけを安全に収集する。"""
    _KEYWORDS = re.compile(r"\b(pdf|paper|publication|full\s*paper|download|proceedings|arxiv|doi|supplement|appendix|technical\s*report)\b", re.I)

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._current_href = ""
        self._current_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href", "")
            self._current_href = urljoin(self.base_url, href) if href else ""
            self._current_text = []

    def handle_data(self, data):
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a" or not self._current_href:
            return
        href = urldefrag(self._current_href)[0]
        label = " ".join(self._current_text).strip()
        if href.startswith(("http://", "https://")) and (self._KEYWORDS.search(label) or self._KEYWORDS.search(href)):
            self.links.append((href, label))
        self._current_href, self._current_text = "", []


def _http_get_limited(url: str, accepted_types: tuple[str, ...], byte_limit: int) -> tuple[bytes, str, str]:
    """外部一次資料をGeminiなしで取得する共通処理。失敗は空で返し、crawlは行わない。"""
    if not (url or "").startswith(("http://", "https://")):
        return b"", "", ""
    try:
        _validate_public_http_url(url)
    except ValueError as exc:
        logger.warning("[SOURCE FETCH BLOCKED] %s", exc)
        return b"", "", ""
    try:
        with requests.get(url, headers={"User-Agent": WEB_CONTEXT_USER_AGENT, "Accept": "*/*"},
                          timeout=WEB_CONTEXT_TIMEOUT_SECONDS, allow_redirects=True, stream=True) as res:
            content_type = (res.headers.get("Content-Type") or "").lower()
            if res.status_code != 200 or (content_type and not any(t in content_type for t in accepted_types)):
                return b"", content_type, res.url
            chunks, total = [], 0
            for chunk in res.iter_content(chunk_size=32768):
                if not chunk:
                    continue
                chunk = chunk[:max(0, byte_limit - total)]
                chunks.append(chunk)
                total += len(chunk)
                if total >= byte_limit:
                    break
            return b"".join(chunks), content_type, res.url
    except Exception as e:
        logger.info(f"[SOURCE FETCH] failed {url}: {e}")
    return b"", "", ""


def _validate_public_http_url(url: str) -> None:
    """Reject non-HTTP and private/link-local destinations before source fetches."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("URL must be a plain public http(s) URL")
    host = parsed.hostname.rstrip(".")
    if host.lower() in {"localhost", "localhost.localdomain"}:
        raise ValueError("private destination blocked")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"host resolution failed: {host}") from exc
    for info in infos:
        address = info[4][0].split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise ValueError("invalid resolved address") from exc
        if not ip.is_global:
            raise ValueError("private destination blocked")


def _fetch_html_document(url: str) -> tuple[str, list[tuple[str, str]], str]:
    raw, content_type, final_url = _http_get_limited(url, ("text/html", "application/xhtml+xml", "text/plain"), WEB_CONTEXT_MAX_BYTES)
    if not raw:
        return "", [], ""
    html = raw.decode("utf-8", errors="replace")
    text = html
    if "html" in content_type or "<html" in html[:1000].lower():
        body = _ReadableHTMLTextParser()
        body.feed(html)
        text = body.text()
        links = _ResearchLinkParser(final_url or url)
        links.feed(html)
        return _truncate_source_context(text), list(dict.fromkeys(links.links)), final_url or url
    return _truncate_source_context(unescape(text)), [], final_url or url


def fetch_pdf_context(url: str) -> str:
    """PDFから本文を抽出する。PyPDFが無い実行環境ではFail Closed用に空を返す。"""
    raw, content_type, _ = _http_get_limited(url, ("application/pdf", "application/octet-stream"), DEEP_SOURCE_MAX_PDF_BYTES)
    if not raw or ("pdf" not in content_type and not raw.startswith(b"%PDF")):
        return ""
    try:
        from io import BytesIO
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(raw))
        pages = [(p.extract_text() or "") for p in reader.pages[:80]]
        text = "\n".join(pages)
        logger.info(f"[DEEP PDF] extracted {len(text)} chars <- {url}")
        return text
    except Exception as e:
        logger.info(f"[DEEP PDF] extraction failed {url}: {e}")
        return ""


def _compress_evidence(text: str) -> str:
    """論文末尾の表やLimitationsを落とさないよう、重要セクションを先頭優先でなく抽出する。"""
    lines = [x.strip() for x in (text or "").splitlines() if x.strip()]
    keywords = re.compile(r"abstract|method|experiment|table|hardware|gpu|runtime|second|sec\\b|dataset|benchmark|limitation|appendix|code|availability|status|supplement", re.I)
    selected = [line for line in lines if keywords.search(line)]
    # 抽出された行だけで意味が切れないよう、冒頭の要約も少量残す。
    merged = "\n".join((lines[:80] + selected)[:500])
    return _truncate_source_context(merged)


def _build_evidence_metadata(context: str, deep_scanned: bool) -> dict:
    text = context or ""
    def state(pattern: str) -> str:
        return "FOUND" if re.search(pattern, text, re.I) else ("SEARCHED_NOT_FOUND" if deep_scanned else "NOT_SEARCHED")
    qualifiers = []
    for m in re.finditer(r"(?:in|at least in) (simple|obvious)[^.\n]{0,100}(?:case|cases)|(?:単純な|明確に判定できる)[^。\n]{0,80}(?:例|ケース)", text, re.I):
        qualifiers.append(m.group(0).strip())
    return {
        "coverage": {
            "method": state(r"method|approach|stage\\s*[12]|方法"), "dataset": state(r"dataset|data set|データセット"),
            "hardware": state(r"hardware|gpu|rtx|nvidia|cpu|ハードウェア"), "runtime": state(r"runtime|latency|\\bsec(?:ond)?s?\\b|処理時間"),
            "benchmark": state(r"benchmark|evaluation|experiment|評価"), "limitations": state(r"limitation|limitat|constraint|制約|限界"),
            "code_availability": state(r"source code|code availability|github|code release|公開コード"),
        },
        "required_qualifiers": list(dict.fromkeys(qualifiers))[:8],
        "evidence_strength": "OFFICIAL_GUARANTEE" if re.search(r"guarantee[sd]?|保証", text, re.I) else "UNKNOWN",
    }


def fetch_webpage_context(url: str) -> str:
    """HN/PH外部URLをGeminiを使わず取得し、本文テキストだけを返す。失敗時は空文字。"""
    text, _, _ = _fetch_html_document(url)
    if len(text.strip()) >= SOURCE_CONTEXT_MIN_CHARS:
        logger.info(f"[WEB CONTEXT] Python取得成功: {len(text)} chars <- {url}")
        return text
    logger.info(f"[WEB CONTEXT FALLBACK] 本文不足: {url}")
    return ""


def prepare_source_context(repo: dict) -> dict:
    """Geminiを使わず一次情報を補強し、URL Contextより先にsource-native本文を確保する。"""
    source = repo.get("source", "GitHub")
    name = repo.get("nameWithOwner", "")
    desc = repo.get("description", "")
    primary_url = repo.get("primaryUrl") or repo.get("url") or ""
    stored = repo.get("sourceContext") or ""
    details = repo.get("sourceDetails") or {}

    pieces = [f"[DISCOVERY_SOURCE]\nSource: {source}\nName: {name}\nDescription: {desc}"]
    substantive_parts: list[str] = []
    method = GROUNDING_METADATA_ONLY

    if source == "GitHub":
        readme = fetch_github_readme_context(name)
        if readme:
            pieces.append("README:\n" + readme)
            substantive_parts.append(readme)
    elif source == "ArXiv":
        if stored:
            pieces.append("Abstract:\n" + stored)
            substantive_parts.append(stored)
        authors = details.get("authors") or []
        categories = details.get("categories") or []
        if authors:
            pieces.append("Authors: " + ", ".join(authors[:20]))
        if categories:
            pieces.append("Categories: " + ", ".join(categories[:20]))
        comment = details.get("comment") or ""
        if comment:
            pieces.append("ArXiv comment:\n" + comment)
            substantive_parts.append(comment)
        official_links = details.get("official_external_links") or []
        for official_url, official_ctx in _fetch_arxiv_official_link_context(official_links):
            pieces.append(f"Official linked resource ({official_url}):\n" + official_ctx)
            substantive_parts.append(official_ctx)
    elif source == "ProductHunt":
        if stored:
            pieces.append("Product Hunt metadata:\n" + stored)
            substantive_parts.append(stored)
        # Product Huntのtagline/descriptionだけでなく、製品サイト本文を無料HTTP取得して補強。
        webpage = fetch_webpage_context(primary_url)
        if webpage:
            pieces.append("Product website content:\n" + webpage)
            substantive_parts.append(webpage)
    elif source == "HackerNews":
        hn_text = stored.strip()
        if hn_text:
            pieces.append("Hacker News post text:\n" + hn_text)
            substantive_parts.append(hn_text)
        hn_url = details.get("hn_url")
        if hn_url:
            pieces.append(f"HN discussion URL: {hn_url}")
        external_url = details.get("external_url") or ""
        # HNの外部記事本文をまずPython側で取得。成功すればURL Contextを使わない。
        if external_url:
            primary_url = external_url
            webpage = fetch_webpage_context(external_url)
            if webpage:
                pieces.append("External article content:\n" + webpage)
                substantive_parts.append(webpage)
    elif stored:
        pieces.append(stored)
        substantive_parts.append(stored)

    # Landing/author pageから研究用の深い一次資料を取得する。文字数ではなく、検出された
    # Paper/PDF/Appendixが実際に走査済みかで記事化可否を決める。
    landing_text, research_links, final_primary_url = _fetch_html_document(primary_url)
    if final_primary_url:
        primary_url = final_primary_url
    if landing_text and landing_text not in substantive_parts:
        pieces.append("[REFERENCE_SOURCE]\n" + landing_text)
        substantive_parts.append(landing_text)
    deep_source_required = bool(research_links)
    deep_source_scanned = False
    deep_parts: list[str] = []
    deep_urls: list[str] = []
    for link, label in research_links[:DEEP_SOURCE_MAX_DOCUMENTS]:
        is_pdf = link.lower().split("?", 1)[0].endswith(".pdf") or "pdf" in label.lower()
        raw_text = fetch_pdf_context(link) if is_pdf else fetch_webpage_context(link)
        if raw_text:
            role = "[SUPPLEMENTAL_SOURCE]" if re.search(r"supplement|appendix", label, re.I) else "[PRIMARY_SOURCE]"
            deep_parts.append(f"{role}\nURL: {link}\n{_compress_evidence(raw_text)}")
            deep_urls.append(link)
    if deep_source_required:
        deep_source_scanned = bool(deep_parts)
        if deep_parts:
            pieces.extend(deep_parts)
            substantive_parts.extend(deep_parts)

    substantive = "\n\n".join(x for x in substantive_parts if x)
    text_sufficient = len(substantive.strip()) >= SOURCE_CONTEXT_MIN_CHARS
    evidence_sufficient = text_sufficient and (not deep_source_required or deep_source_scanned)
    if text_sufficient:
        method = GROUNDING_SOURCE_NATIVE
    # Deep evidence is already compressed section-wise, so retain it ahead of generic landing text.
    context = _truncate_source_context("\n\n".join(pieces[:1] + deep_parts + pieces[1:]))
    evidence_metadata = _build_evidence_metadata(context, deep_source_scanned)
    return {
        "context": context,
        "context_length": len(context),
        "method": method,
        "primary_url": primary_url,
        "sufficient": text_sufficient,  # backward-compatible: URL Context fallback only
        "text_sufficient": text_sufficient,
        "primary_source_resolved": bool(primary_url),
        "deep_source_required": deep_source_required,
        "deep_source_scanned": deep_source_scanned,
        "evidence_sufficient": evidence_sufficient,
        "deep_source_urls": deep_urls,
        "evidence_metadata": evidence_metadata,
    }


_FUTURE_SOURCE_PATTERN = re.compile(r"\b(will|future|planned|coming|next|expected|preview|beta|nightly)\b|予定|今後|開発中|対応予定", re.I)
_STALE_ARTICLE_PATTERN = re.compile(r"(?:今後|これから).{0,30}(?:予定|議論|対応)|(?:公開|対応|議論)予定", re.I)


def resolve_followup_freshness(source_info: dict) -> dict:
    """将来表現がある時だけ、同一公式ドメイン内の後続ページを必ず確認する独立Stage。"""
    context = source_info.get("context", "")
    primary_url = source_info.get("primary_url", "")
    if not _FUTURE_SOURCE_PATTERN.search(context) or not primary_url:
        return {"triggered": False, "followup_found": False, "context": ""}
    raw, content_type, final_url = _http_get_limited(primary_url, ("text/html", "application/xhtml+xml"), WEB_CONTEXT_MAX_BYTES)
    if not raw or "html" not in content_type:
        return {"triggered": True, "followup_found": False, "context": ""}
    html = raw.decode("utf-8", errors="replace")
    base = final_url or primary_url
    host = urlparse(base).netloc.lower()
    candidates = []
    for href, label in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        target = urldefrag(urljoin(base, unescape(href)))[0]
        clean_label = re.sub(r"<[^>]+>", " ", unescape(label))
        if urlparse(target).netloc.lower() == host and target != base and ("follow" in clean_label.lower() or "update" in clean_label.lower() or "clang" in clean_label.lower() or _FUTURE_SOURCE_PATTERN.search(clean_label) or "blog" in target.lower()):
            candidates.append(target)
    followups = []
    for target in list(dict.fromkeys(candidates))[:FRESHNESS_MAX_LINKS]:
        text = fetch_webpage_context(target)
        if text and not _FUTURE_SOURCE_PATTERN.search(text):
            followups.append(f"[FOLLOWUP_SOURCE]\nURL: {target}\n{text[:3000]}")
    resolved = "\n\n".join(followups)
    logger.info(f"[FRESHNESS] triggered=True followups={len(followups)} primary={primary_url}")
    return {"triggered": True, "followup_found": bool(followups), "context": resolved}

def fetch_github_trending(limit: int = GITHUB_FETCH_LIMIT):
    """GitHub GraphQL API から急上昇AI/MLリポジトリを取得する。"""
    logger.info(">>> [Step 1] GitHub一次データの自動巡回...")
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"Bearer {GH_PAT}", "Content-Type": "application/json"}
    since_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    query = f"""
    {{
      search(query: "topic:ai topic:machine-learning stars:>100 pushed:>{since_date}", type: REPOSITORY, first: {max(1, min(limit, 100))}) {{
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

def fetch_hackernews_top(limit: int = HN_FETCH_LIMIT):
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



def _normalize_title_for_match(title: str) -> str:
    title = re.sub(r"\s+", " ", (title or "").strip().lower())
    title = re.sub(r"[^a-z0-9]+", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def _extract_arxiv_id(url: str) -> str:
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?", url or "", re.I)
    return m.group(1) if m else ""


def _verify_arxiv_source_integrity(repo: dict) -> tuple[bool, str, dict]:
    """Deep Dive前にarXiv IDを再照会し、候補titleとURL先titleの対応を検証する。

    Geminiを使わないFail-ClosedなSource Integrity Gate。タイトル類似度が低い場合は
    記事生成を止める。合わせてcomment/公式外部リンク候補をsourceDetailsへ補強する。
    """
    if repo.get("source") != "ArXiv":
        return True, "not-arxiv", repo
    arxiv_id = _extract_arxiv_id(repo.get("primaryUrl") or repo.get("url") or "")
    if not arxiv_id:
        return False, "arXiv IDをURLから抽出できない", repo
    try:
        res = _fetch_arxiv_with_retry(
            "https://export.arxiv.org/api/query",
            {"id_list": arxiv_id, "start": 0, "max_results": 1},
        )
        if res is None:
            return False, "arXiv再照会に失敗", repo
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        root = ET.fromstring(res.content)
        entry = root.find("atom:entry", ns)
        if entry is None:
            return False, f"arXiv ID {arxiv_id} が再照会で見つからない", repo
        fetched_title = re.sub(r"\s+", " ", entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        candidate_title = repo.get("nameWithOwner", "")
        a = _normalize_title_for_match(candidate_title)
        b = _normalize_title_for_match(fetched_title)
        ratio = SequenceMatcher(None, a, b).ratio() if a and b else 0.0
        # version suffixや軽微な表記差は許容するが、別論文レベルの不一致は止める。
        if ratio < 0.78:
            return False, f"arXiv title mismatch: candidate='{candidate_title}' fetched='{fetched_title}' similarity={ratio:.2f}", repo

        details = dict(repo.get("sourceDetails") or {})
        comment = re.sub(r"\s+", " ", entry.findtext("arxiv:comment", default="", namespaces=ns) or "").strip()
        if comment:
            details["comment"] = comment
        external_links = []
        # comment/summary内の明示URLとAtom linkを候補化。arxiv.org自身は除く。
        raw_for_urls = " ".join([comment, repo.get("sourceContext", "")])
        for u in re.findall(r"https?://[^\s<>\]\)]+", raw_for_urls):
            u = u.rstrip(".,;:")
            if "arxiv.org" not in u.lower():
                external_links.append(u)
        for link_el in entry.findall("atom:link", ns):
            href = (link_el.get("href") or "").strip()
            if href and "arxiv.org" not in href.lower():
                external_links.append(href)
        # GitHub/Hugging Face/project page等、論文自身から辿れるリンクだけ保持。
        details["official_external_links"] = list(dict.fromkeys(external_links))[:6]
        details["verified_arxiv_title"] = fetched_title
        details["verified_arxiv_id"] = arxiv_id
        updated = dict(repo)
        updated["sourceDetails"] = details
        return True, f"verified:{arxiv_id}", updated
    except Exception as e:
        return False, f"arXiv source integrity check error: {e}", repo


def _fetch_arxiv_official_link_context(urls: list[str]) -> list[tuple[str, str]]:
    """arXiv自身が示した外部リンクだけを補助一次情報として取得する。"""
    results = []
    for url in (urls or [])[:4]:
        low = url.lower()
        if not low.startswith(("http://", "https://")):
            continue
        # 一般的な短縮・広告URLは避け、研究コード/モデル/プロジェクトでよく使われるhostを優先。
        if not any(host in low for host in ("github.com", "huggingface.co", "gitlab.com", "project", "research", "lab")):
            continue
        ctx = fetch_webpage_context(url)
        if ctx:
            results.append((url, ctx))
    return results

def fetch_arxiv_ai_ml(limit: int = ARXIV_FETCH_LIMIT):
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


def fetch_producthunt_trending(limit: int = PRODUCTHUNT_FETCH_LIMIT):
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
    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID):
        # Notion未設定の場合はそもそも保存自体が行われないため、
        # 重複チェック自体が意味を持たない（Fail-Closedの対象外）。
        return set()

    url = _notion_query_url()
    headers = _notion_headers()

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


def _notion_plain_text(prop: dict) -> str:
    """Notion title/rich_textプロパティから表示文字列を安全に取り出す。"""
    items = prop.get("title") or prop.get("rich_text") or []
    return "".join(x.get("plain_text") or x.get("text", {}).get("content", "") for x in items).strip()


def get_pending_retry_items(limit: int = 20) -> list[dict] | None:
    """Reconstruct transiently failed Deep Dive candidates before new collection."""
    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID):
        return []
    payload = {"filter": {"property": PROP_CONTENT_STATUS, "select": {"equals": CONTENT_STATUS_PENDING_RETRY}}, "page_size": min(100, limit)}
    res = _query_notion_db_with_retry(_notion_query_url(), _notion_headers(), payload)
    if res is None:
        return None
    items = []
    for page in res.json().get("results", []):
        props = page.get("properties", {})
        url = props.get(PROP_URL, {}).get("url")
        if not url:
            continue
        items.append({"notion_page_id": page.get("id"), "repo": normalize_item(
            props.get(PROP_SOURCE, {}).get("select", {}).get("name") or "GitHub",
            _notion_plain_text(props.get(PROP_NAME, {})), url,
            _notion_plain_text(props.get(PROP_SOURCE_SUMMARY, {})),
            props.get(PROP_ENGAGEMENT, {}).get("number") or 0,
            published_at=(props.get(PROP_PUBLISHED_AT, {}).get("date") or {}).get("start"),
        ), "screening_score": props.get(PROP_SCREENING_SCORE, {}).get("number") or 0,
           "screening_reason": _notion_plain_text(props.get(PROP_SCREENING_REASON, {}))})
    return items


def get_regen_test_items(limit: int = 3, source_filter: str = "") -> list[dict] | None:
    """
    Notionに既に保存されているDeep Diveを、A/B比較用の読み取り専用候補として取得する。

    - NotionはREAD ONLY。ページを更新しない。
    - 新しい順（Analyzed At降順）で取得。
    - source_filter指定時はSource selectで絞り込む。
    - 取得した最小限のメタデータからNormalizedItem互換dictを復元する。
      一次情報本文はprepare_source_context()がURLから改めて取得する。
    """
    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID):
        logger.error("[REGEN TEST] Notion設定がないため既存Deep Diveを読み出せません。")
        return None

    url = _notion_query_url()
    headers = _notion_headers()
    filters = [{"property": PROP_CONTENT_STATUS, "select": {"equals": CONTENT_STATUS_DEEP_DIVE}}]
    if source_filter:
        filters.append({"property": PROP_SOURCE, "select": {"equals": source_filter}})
    payload = {
        "page_size": min(max(limit, 1), 100),
        "filter": {"and": filters},
        "sorts": [{"property": PROP_ANALYZED_AT, "direction": "descending"}],
    }
    res = _query_notion_db_with_retry(url, headers, payload)
    if res is None:
        logger.error("[REGEN TEST] Notion既存Deep Dive取得に失敗しました。")
        return None

    items = []
    for page in res.json().get("results", []):
        props = page.get("properties", {})
        page_url = (props.get(PROP_URL, {}).get("url") or "").strip()
        name = _notion_plain_text(props.get(PROP_NAME, {}))
        source = (props.get(PROP_SOURCE, {}).get("select") or {}).get("name") or "HackerNews"
        engagement = props.get(PROP_ENGAGEMENT, {}).get("number") or 0
        screening_score = props.get(PROP_SCREENING_SCORE, {}).get("number")
        screening_reason = _notion_plain_text(props.get(PROP_SCREENING_REASON, {}))
        published = (props.get(PROP_PUBLISHED_AT, {}).get("date") or {}).get("start")
        license_text = _notion_plain_text(props.get(PROP_LICENSE, {}))
        if not page_url or not name:
            logger.warning(f"[REGEN TEST SKIP] page={page.get('id')}: Name/URL不足")
            continue
        items.append({
            "notion_page_id": page.get("id"),
            "screening_score": int(screening_score) if screening_score is not None else NOTION_SAVE_THRESHOLD_SCORE,
            "screening_reason": screening_reason or "既存Deep Dive再生成テスト",
            "repo": {
                "nameWithOwner": name,
                "description": _notion_plain_text(props.get(PROP_SOURCE_SUMMARY, {})) or "既存Deep Dive再生成テスト",
                "url": page_url,
                "stargazerCount": int(engagement or 0),
                "source": source,
                "publishedAt": published,
                "sourceContext": "",
                "primaryUrl": page_url,
                "sourceDetails": ({
                    "external_url": page_url,
                    "regen_note": "Notion既存Deep Diveから再構成",
                } if source == "HackerNews" else {
                    "regen_note": "Notion既存Deep Diveから再構成",
                }),
                "licenseInfo": ({"spdxId": license_text} if source == "GitHub" and license_text else None),
            },
        })
    logger.info(
        f"[REGEN TEST] 既存Deep Dive {len(items)}件を読み込み"
        + (f"（Source={source_filter}）" if source_filter else "")
    )
    return items


def save_regen_test_manuscript(repo: dict, manuscript: str, quality_status: str = "accepted",
                                 quality_failures: list[str] | None = None) -> str:
    """再生成稿をNotionへ書かず、ローカルMarkdownとして保存する。

    再生成テストではQuality Gate不合格稿も捨てない。accepted/rejectedをファイル名と
    先頭コメントで明示し、A/B比較とGate調整に使えるようにする。
    """
    os.makedirs(REGEN_TEST_OUTPUT_DIR, exist_ok=True)
    source = repo.get("source", "Unknown")
    name = repo.get("nameWithOwner", "untitled")
    status = "accepted" if quality_status == "accepted" else "rejected"
    filename = f"{_sanitize_filename(source)}__{_sanitize_filename(name)}__regen__{status}.md"
    path = os.path.join(REGEN_TEST_OUTPUT_DIR, filename)
    header = ""
    if status == "rejected":
        reasons = " / ".join(quality_failures or [])
        header = f"<!-- REGEN TEST: QUALITY GATE REJECTED\n{reasons}\n-->\n\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + manuscript)
    logger.info(f"[REGEN TEST SAVED:{status.upper()}] {name} -> {path}")
    return path

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
    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID):
        return None

    url = _notion_query_url()
    headers = _notion_headers()

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

    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID):
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
def _source_fact_discipline(source: str) -> str:
    """Sourceごとの典型的な誤推論を、Deep Diveの同一call内で抑制する。"""
    common = """
【全ソース共通 Fact Discipline】
・Sourceが確認している「事実」、そこから導く「推論」、筆者としての「判断」を混同しない。
・一次情報が示すCapability（できること）を、そのままSuperiority（競合より優れる）やBusiness Outcome
  （売上増・コスト削減・生産性向上・品質向上）へ変換しない。
・根拠のない具体性を足さない。％、倍、円、ドル、ms、秒、日数、週間、月数、人数、GPU台数、
  導入期間、ROI、削減額などは、一次情報に明示された条件付き数値か、明確に「筆者が置くPoC目安」
  とラベルしたもの以外は書かない。
・「唯一」「一択」「必須」「デファクト」「最有力」「圧倒的」「劇的」「革命的」「完全」「保証」
  などの強い語は、一次情報や複数の比較根拠で直接支えられない限り使わない。
・競合製品の最新機能、価格、安定性、優劣は、Source ContextまたはGroundingで当該競合の現行一次情報を
  確認できた場合だけ具体的に述べる。確認できない場合は「比較が必要」と書く。
・OSS/self-host/local-first/OpenTelemetry/MCP/API互換などの属性だけから、低コスト、安全、移行容易、
  低ロックイン、高性能、将来の標準化を断定しない。
・ニュースや製品紹介の見出しを、さらに強い日本語へ増幅しない。
・3〜12ヶ月の未来は予言しない。必ず「条件 → 起こり得る結果 → 見るべき指標」の形にする。
・現在仕様が変わりやすい料金、API、モデル、CLI、対応OS、制限、cache、preview/beta/stable状態は、
  取得できた現在の一次情報だけを根拠にする。古い記事と現在docsが衝突する場合は現在docsを優先する。
"""
    rules = {
        "GitHub": """
【GitHub専用 Fact Discipline】
・READMEにある機能の存在は「何ができるか」の証拠であり、「最適」「標準」「競合優位」の証拠ではない。
・Star数、Download数、Contributor数は普及度の参考であり、品質・信頼性・商用品質の証明ではない。
・OSSであることを、ロックインなし・低TCO・高セキュリティと同義にしない。
・コマンド、設定値、環境変数、API endpointはREADME/公式docsに実在する表記だけを使う。推測でCLIを作らない。
・実装例やdemoがあることを、大規模production運用やSLAの証明として扱わない。
""",
        "ArXiv": """
【arXiv専用 Fact Discipline】
・研究結果とproduction/commercial/clinical readinessを明確に分離する。
・論文中のbenchmark数値を出すなら、dataset/task、metric、comparator、実験条件を可能な範囲で併記する。
  文脈が取れない裸の数値は記事に使わない。
・transferable≠universal、equivariant/physics-informed≠reliable、efficient≠low-cost、
  interpretable≠regulatory explainability、robust≠production fault tolerance、高精度≠商用優位。
・研究者が実験できたことと、読者が公開物だけで再現できることを同一視しない。
・費用、必要人員、役職、GPU台数、導入期間、ROI、商用化時期を論文から推測して具体化しない。
・医療・臨床テーマでは、後ろ向き/研究データの結果を診療意思決定や実臨床導入へ直結させない。
  外部検証、前向き検証、calibration、安全性、規制等が未確認なら明示する。
""",
        "ProductHunt": """
【Product Hunt専用 Fact Discipline】
・Product Hunt本文、製品サイト、launch copyのbest/fast/easy/secure/enterprise-ready/production-ready等は、
  原則「ベンダー自身の主張」として扱い、第三者評価へ変換しない。
・self-host可能→TCO削減、local-first→安全、MCP対応→将来標準、free trial→導入コスト低、
  多数integration→生産性向上、とは自動変換しない。
・価格、無料枠、対応OS、export、privacy、data residency等は変わりやすい。現在の一次情報で確認できない場合は断定しない。
・競合比較はlaunch copyの言い分をそのまま採用しない。
""",
        "HackerNews": """
【Hacker News専用 Fact Discipline】
・HNタイトルやリンク先見出しの強い表現を、そのまま業界全体の転換点・企業の緊急課題へ拡張しない。
・News significanceとBusiness urgencyを分ける。企業方針変更を勧めるのは具体的影響範囲が確認できる場合だけ。
・元記事が特定企業/製品の公式ブログなら、競合情報をモデル記憶から補わない。
・preview / beta / nightly / experimental / PR / development build と stable/general availabilityを必ず分離する。
・ニュース公開時点の仕様を「現在仕様」と固定しない。現在docsと衝突するなら差分を明示する。
""",
    }
    return common + rules.get(source, "")


def _human_editorial_style_rules() -> str:
    """note本文を管理帳票から切り離し、人間の編集者が書いた読み物に寄せる。"""
    return """
【Human Editorial Style｜最重要】
ARTICLEはNotion管理帳票ではない。読者が自然に読み進められるテック記事として書く。

・同じ長さの段落、同じ語尾、同じ3点セットを繰り返さない。
・「第一に／第二に／第三に」を機械的に並べない。必要なら一度だけ使う。
・各節を結論→理由→箇条書きの同型にしない。短い段落と長めの段落を混ぜる。
・一次情報を説明したあと、筆者自身の判断や迷いを自然に差し込む。
・「ここまでは確認できる。一方で、ここはまだ分からない。だから今は導入を急がず、動向を見たい」のように、留保を自然な日本語で書く。
・煽り語、営業コピー、読者を急かす命令口調を避ける。
・架空の感情や体験を書かない。「私は驚いた」「使ってみた」「以前から気になっていた」は、根拠がない限り使わない。
・導入・見出し・結論を定型句で埋めず、テーマに合う自然な言葉を選ぶ。
・箇条書きは要点整理や検証項目にだけ使う。本文の半分以上は段落で読ませる。
・具体例は一次情報または明示した推論の範囲だけで使う。架空の導入効果や期間を作らない。
・「理由は3つあります」を根拠なしに使わない。項目数は事実上必要な数だけにする。
・最終段落は筆者なら次に何をするかを、事実→実務上の意味→リスク→判断の順で自然に締める。
・安全性のために記事全体を曖昧にしない。根拠のない主張だけを、その一文・その表現の範囲で修正する。
・根拠に基づく観察、比較、筆者の実務判断は残す。具体的な検証・見送り・比較を、単なる「今後注視する」に置き換えない。
・架空の感情や個人的体験は加えず、自然な好奇心と編集者としての視点で読ませる。
"""

def build_decision_prompt(name, url, stars, desc, quality_feedback: str = "", source: str = "GitHub",
                          source_context: str = "", grounding_status_hint: str = GROUNDING_METADATA_ONLY,
                          evidence_metadata: dict | None = None, freshness: dict | None = None):
    """上位モデルでARTICLEとMANAGEMENT DATAを同時生成する。記事と管理帳票は明確に分離する。"""
    metric_label = ENGAGEMENT_LABELS.get(source, "Engagement")
    metric_note = ""
    if source == "ArXiv":
        metric_note = "※arXivにはStars/Votes相当の人気指標がないため、人気度を0とみなして価値判断しないこと。\n"
    feedback = f"\n【前回出力への編集フィードバック】\n{quality_feedback}\n事実違反は該当箇所だけを直す。全文を保守的に均さず、根拠付きの判断・具体的な行動・タイトルの引力は残す。具体的Actionを『注視する』だけに置き換えない。\n" if quality_feedback else ""
    context = _truncate_source_context(source_context)
    fact_rules = _source_fact_discipline(source)
    style_rules = _human_editorial_style_rules()
    display = _article_display_variant(name)
    evidence_json = json.dumps(evidence_metadata or {}, ensure_ascii=False, indent=2)
    freshness_context = (freshness or {}).get("context", "")

    return f"""
あなたはAI・ソフトウェア領域のシニアCTOアドバイザーであり、商業メディア経験のある日本語テック編集者です。
以下の一次情報から、無料公開のnote記事として読者の判断を助ける記事と、Notion保存用の管理データを同時に作成してください。

【読者】CTO、テックリード、PM、AI/ソフトウェア導入の意思決定者。
【最重要】ARTICLEは人が読む文章、MANAGEMENT DATAは機械が読む構造データ。両者を混ぜない。
【事実優先順位】Source Native Context > Primary URL取得内容 > Google Search Grounding（有効時） > モデル内部知識。

【SOURCE BOUNDARY — 最重要】
・ARTICLEで「事実」として断定してよい技術仕様・対応状況・価格・数値・競合情報・固有名詞は、原則としてSource Native ContextまたはGroundingで確認できる内容だけ。
・モデル内部知識から背景説明を補う場合は、製品固有の事実として書かず、「一般論として」「ここからは私の推論だが」など、読者が推論だと分かる形にする。
・Source Contextにない企業向け管理製品、競合機能、API仕様、OS/ブラウザ管理方式などを、もっともらしい補足として追加しない。
・ニュース公開時点の仕様と現在のStable仕様は同一視しない。現在仕様をGroundingで確認できなければ「元記事公開時点では」と限定する。
・不明点は補完せず「一次情報からは確認できない」と書く。
・「確認できない」「記載がない」「未公開」「不明」等の不在Claimは、Evidence Coverageが SEARCHED_NOT_FOUND または NOT_DISCLOSED の項目だけに限る。NOT_SEARCHEDまたはSource Depth不足では不在を断定しない。
モデル内部知識だけで現在仕様、競合比較、数値、価格、対応状況を断定しない。

{fact_rules}
{style_rules}

【対象】
・出所: {source}
・名前: {name}
・Primary URL: {url}
・{metric_label}: {stars}
{metric_note}・概要: {desc}
・事前Grounding: {grounding_status_hint}
・Article generation date: {datetime.now(JST).date().isoformat()}

【Source Native Context】
{context or '（source-native本文不足。Primary URLで確認できた範囲以外を現在事実として補完しないこと。）'}

【Structured Evidence / Required Qualifiers — 最優先】
{evidence_json}
・required_qualifiers は自然な日本語に言い換えてよいが、ARTICLEから絶対に削除しない。
・TOY_EXAMPLE相当の証拠は「原著の単純な例では」「著者が示したサンプルでは」等、例の範囲を必ず明示する。
・「保証」「完全」「必ず」「安全」等の強い表現は、Structured EvidenceまたはSource Contextが同等以上の保証を明示する場合だけ使用できる。
・一次情報に限界・未解決課題・"promising"・条件付きの性能値がある場合、ARTICLEにも必ず残す。性能値はデータセット、解像度、反復回数、ハードウェア等の条件を削らない。
・Hacker News等は発見経路である。実験値・仕様の根拠となったPrimary URL/PDFは「参考情報」に出るため、HNだけを根拠として数値を説明しない。フォローアップに言及する場合はEvidenceにあるURLだけを使う。

【Freshness Resolution】
{freshness_context or '公式フォローアップは未検出。元資料の将来表現を現在完了の事実に書き換えない。'}
・Follow-up Sourceがある場合、それより古い「今後予定」「これから議論」等の状態をARTICLEに残さない。
{feedback}

最初に必ず次の見出しをそのまま出す。
=== MANAGEMENT DATA ===
その下に以下を順序通り、各行「・ラベル: 値」で出す。
・Source Summary: 一次情報で確認できる事実を1〜3文。
・What: 何が起きたかを2文以内。
・Why Important: 実務への意味。未検証効果は推論と明示。
・技術的パラダイムシフト: 変化が小さいなら小さいと書く。
・代替との比較: Grounding内で比較できる範囲だけ。根拠不足なら「比較根拠不足」と書く。
・移行コストとリスク: 確認できる事実と推論を分ける。
・Decision: NOW / TRY / WATCH / WAIT / AVOID の1つ。
・Decision Reason: 最大3理由を簡潔に。
・Decision Score: Business Impact X/25; Technical Impact X/25; Urgency X/20; Market Impact X/15; Reliability X/15; 合計 X/100
・Why NOT Important: 今は不要な読者と理由。
・Who Should Use: 検討価値のある読者。
・Who Should NOT Use: 今は不要な読者。
・Action: 次に検証する具体的行動。根拠のない日数・金額を作らない。
・Future Scenario: 3〜12ヶ月の条件付きシナリオを2つ以上。Condition → Possible Result → Indicator。
・Article Value: 0〜100

次に必ず専用行を出す。
{SECTION_SPLIT_TOKEN}

その次の1行を記事タイトルにする。#は付けない。プロのコピーライターとして、技術の要点と読者の関心を結び、短く惹きつけるタイトルにすること。必ず「。」「？」のいずれかで終える。

【ARTICLE】
記事はすべて無料公開する。有料エリア、有料マーカー、無料部分／有料部分という区分を一切出力しない。
タイトルの直後には、読者が「何についての記事か」「自分に関係があるか」をすぐ理解できる導入を置く。
導入見出しは次を使う。
## {display['intro']}

導入は2〜4段落で自然に構成する（今回は目安として{display['intro_paragraphs']}段落）。導入型は「{display['opening']}」、記事全体の温度感は「{display['tone']}」を参考にする。ただし型や段落数を機械的に再現せず、毎回「結論から言うと」「今回紹介するのは」「この記事では」で始めない。
1段落目は、読者の疑問・実務課題・数字や事実への留保・発見のいずれかから自然に入り、{source}で発見した『{name}』のリンク先原資料を参照して実務への意味を整理する記事であることを示す。
2段落目は、原資料の発表主体がSource Native Contextで確認できる場合だけ示し、「〜に関する一次情報に基づいています」と明記する。確認できない場合は主体を推測せず「リンク先原資料の一次情報に基づいています」と書く。
3段落目は、原資料で確認できる技術的背景・従来課題・今回の手法を、固有の数値や条件を落とさずに簡潔に説明する。推論や実務的な評価はこの段落に混ぜない。

その後、以下の見出しをこの順番で出す。
## {display['conclusion']}
## {display['why']}
## {display['what']}
## {display['key']}
### {display['decision']}
### {display['final']}

「{display['key']}」と「{display['decision']}」の間に、テーマに最も合う中見出しを必要な数だけ自分で自然な日本語で設計する。
「なぜそう判断したのか」「本当に変わるのは何か」「誰が使うべきか」等を毎回固定で全部出さない。
必要な論点だけを選び、文章の流れを優先する。

【ARTICLEの追加ルール】
・NOW / TRY / WATCH / WAIT / AVOID は内部管理コードであり、ARTICLEには絶対に表示しない。括弧書き、英字併記、見出し内も禁止。
・「私ならこう考える」では、管理用Decisionを読者向けの自然な判断文に翻訳する。目安は次の通り。
  NOW → 「今すぐ動く価値がある」「今から着手してよい」
  TRY → 「まずは小さく試す価値がある」「限定した環境で試したい」
  WATCH → 「今は動かず、今後の動きを注視したい」「導入を急ぐ段階ではない」
  WAIT → 「現時点では導入を急がない」「条件が整うまで待つのがよい」
  AVOID → 「今は見送るのが妥当」「現時点では採用しない方がよい」
・上の日本語は定型句として毎回そのまま使わず、記事の文脈に合わせて自然に言い換える。Decision ScoreやBusiness Impact等の内部採点もARTICLEへ一切出さない。採点はMANAGEMENT DATAだけに置く。
・競合名を出す場合、Source Native Contextにその競合の比較根拠が存在する時だけ。なければ製品名を列挙しない。
・Preview/Beta/Stableは必ず分離する。
・ニュース公開時点の仕様を現在仕様として断定しない。現在確認できない場合は「元記事公開時点では」と書く。
・根拠のない%・倍数・金額・期間・性能値を作らない。
・「唯一」「一択」「必須」「デファクト」「圧倒的」「劇的」「完全に解決」等は、一次情報だけで立証できない限り使わない。
・記事全体を箇条書き帳票にしない。導入を含め、読者が技術の背景から判断まで自然に追える流れにする。
・「結局、どうするべきか」の結論は管理用Decisionと意味的に一致させる。ただし内部コードは書かない。
・根拠に照らして限定検証、比較テスト、導入見送り、次版待ちなどの判断が妥当なら、理由と対象範囲を添えて明確に書く。安全性のためにすべてを「可能性がある」「注視したい」へ弱めない。
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
    return (_normalize_note_title(title) or "（タイトル生成失敗）"), remaining


def _extract_markdown_section(markdown_text: str, heading_text: str) -> str:
    """note本文の指定見出し直下を、次のMarkdown見出しまで抽出する。"""
    pattern = re.compile(
        rf"^#{{2,6}}\s*{re.escape(heading_text)}\s*$\n?(.*?)(?=^#{{2,6}}\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(markdown_text or "")
    return m.group(1).strip() if m else ""


def _extract_any_markdown_section(markdown_text: str, headings: list[str]) -> str:
    for heading in headings:
        section = _extract_markdown_section(markdown_text, heading)
        if section:
            return section
    return ""


def _display_heading_aliases(kind: str) -> list[str]:
    legacy = {
        "intro": ["はじめに"], "conclusion": ["この記事の結論"],
        "why": ["なぜ今、この情報を見るべきなのか"], "what": ["What｜これは何か"],
        "key": ["ここまでの要点"], "decision": ["私ならこう考える", "私の判定"],
        "final": ["結局、どうするべきか"],
    }
    return legacy.get(kind, []) + [variant[kind] for variant in ARTICLE_DISPLAY_VARIANTS]


def _normalize_decision(value: str) -> str:
    m = re.search(r"\b(NOW|TRY|WATCH|WAIT|AVOID)\b", (value or "").upper())
    return m.group(1) if m else ""


def _parse_gemini_response(full_text: str) -> dict:
    """
    管理用データとnote本文を分離する。
    Geminiの管理用ラベル出力が揺れても、500円記事本文の固定見出しをCanonical fallbackとして使う。
    """
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

    # 管理用ラベルを正とし、本文側は可変見出しにも対応したFallbackにする。
    body_sections = {
        "source_summary_text": _extract_any_markdown_section(note_draft, _display_heading_aliases("what")),
        "what_text": _extract_any_markdown_section(note_draft, _display_heading_aliases("what")),
        "why_important_text": _extract_any_markdown_section(note_draft, _display_heading_aliases("why")),
        "paradigm_shift_text": _extract_any_markdown_section(note_draft, ["本当に変わるのは何か"]),
        "alternative_comparison_text": _extract_any_markdown_section(note_draft, ["既存の選択肢と比べるとどうか"]),
        "migration_cost_text": _extract_any_markdown_section(note_draft, ["導入コストとリスク", "導入前に見ておきたいところ。"]),
        "decision_reason_text": _extract_any_markdown_section(note_draft, ["なぜそう判断したのか"]),
        "why_not_important_text": _extract_any_markdown_section(note_draft, ["誰は使わなくていいか"]),
        "who_should_use_text": _extract_any_markdown_section(note_draft, ["誰が使うべきか"]),
        "who_should_not_use_text": _extract_any_markdown_section(note_draft, ["誰は使わなくていいか"]),
        "action_text": _extract_any_markdown_section(note_draft, _display_heading_aliases("decision")),
        "future_scenario_text": _extract_any_markdown_section(note_draft, ["3〜12ヶ月で起こり得ること"]),
    }

    article_raw = extract_field("Article Value", "0")
    article_match = re.search(r"(\d{1,3})", article_raw)
    article_value = min(100, max(0, int(article_match.group(1)))) if article_match else 0

    decision_text = _normalize_decision(extract_field("Decision", ""))
    decision_section = _extract_any_markdown_section(note_draft, _display_heading_aliases("decision"))
    if not decision_text:
        decision_text = _normalize_decision(decision_section)
    if score == 0:
        article_score_match = re.search(r"(?:Decision\s*Score[^0-9]*)?(\d{1,3})\s*/\s*100", decision_section, re.IGNORECASE)
        if article_score_match:
            score = min(100, max(0, int(article_score_match.group(1))))

    def field_or_body(label: str, body_key: str) -> str:
        value = extract_field(label, "")
        return value if _is_meaningful_field(value) else body_sections.get(body_key, "")

    return {
        "note_draft": note_draft,
        "title_text": title_text,
        "score": score,
        "score_breakdown_text": score_breakdown_text,
        "source_summary_text": field_or_body("Source Summary", "source_summary_text"),
        "what_text": field_or_body("What", "what_text"),
        "why_important_text": field_or_body("Why Important", "why_important_text"),
        "paradigm_shift_text": field_or_body("技術的パラダイムシフト", "paradigm_shift_text"),
        "alternative_comparison_text": field_or_body("代替との比較", "alternative_comparison_text"),
        "migration_cost_text": field_or_body("移行コストとリスク", "migration_cost_text"),
        "decision_text": decision_text,
        "decision_reason_text": field_or_body("Decision Reason", "decision_reason_text"),
        "why_not_important_text": field_or_body("Why NOT Important", "why_not_important_text"),
        "who_should_use_text": field_or_body("Who Should Use", "who_should_use_text"),
        "who_should_not_use_text": field_or_body("Who Should NOT Use", "who_should_not_use_text"),
        "action_text": field_or_body("Action", "action_text"),
        "future_scenario_text": field_or_body("Future Scenario", "future_scenario_text"),
        "article_value": article_value,
    }

def _is_meaningful_field(value: str) -> bool:
    value = (value or "").strip()
    return bool(value) and value not in {"特記事項なし", "概要参照", "アクション参照", "内訳取得失敗"}


_HYPE_PATTERNS = [
    (r"(?:唯一|一択|必須インフラ|最後の砦|最後の防衛線)", "unsupported exclusivity/hype"),
    (r"(?:圧倒的|劇的|革命的|ゲームチェンジャー|パラダイムシフトと言える)", "unsupported hype"),
    (r"(?:デファクト(?:スタンダード)?|業界標準)", "unsupported market-standard claim"),
    (r"(?:完全に|完全な).{0,12}(?:解決|回避|保証|防止)", "unsupported guarantee"),
    (r"(?:品質|安全性|セキュリティ|再現性).{0,10}(?:を|が)(?:担保|保証)され", "unsupported guarantee"),
]

# 数字を使うこと自体は禁止しない。一次情報に存在しない「効果・費用・期間・性能」の具体値だけを拾う。
_SENSITIVE_NUMERIC_PATTERNS = [
    r"\d+(?:\.\d+)?\s*%",
    r"\d+(?:\.\d+)?\s*(?:倍|x|×)",
    r"(?:約|およそ|最大|最低|平均)?\s*\d[\d,]*(?:\.\d+)?\s*(?:円|万円|億円|ドル|USD|JPY)",
    r"\d+(?:\.\d+)?\s*(?:ms|ミリ秒|秒|分|時間)",
    r"\d+(?:\.\d+)?\s*(?:日|週間|週|ヶ月|か月|月)\b",
    r"\d+(?:\.\d+)?\s*(?:GB|MB|TB|GPU|台|人|件|行|リクエスト|requests?|tokens?|トークン)\b",
]

# 数字を使わずに「数倍」「数万円」等を作るケースも止める。
_VAGUE_QUANTIFIED_PATTERNS = [
    r"数倍",
    r"数十倍",
    r"数百倍",
    r"数千倍",
    r"数万円(?:単位)?",
    r"数十万円(?:単位)?",
    r"数百万円(?:単位)?",
]


def _normalized_evidence_text(text: str) -> str:
    return re.sub(r"[\s,，]", "", unicodedata.normalize("NFKC", text or "").lower())


def _normalized_named_fact(text: str) -> str:
    """固有名詞の空白・ハイフン・PDF抽出時の合字揺れを吸収する。"""
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", text or "").lower())


def _find_unsupported_numeric_claims(draft: str, source_context: str, evidence_metadata: dict | None = None) -> list[str]:
    """記事中のセンシティブな具体値が一次情報にも存在するかを簡易照合する。"""
    evidence = _normalized_evidence_text(source_context + "\n" + json.dumps(evidence_metadata or {}, ensure_ascii=False))
    failures: list[str] = []
    # Decision Score、見出しの3〜12ヶ月、STEP番号は業務効果の数値ではないので対象外。
    scrubbed = re.sub(r"Decision\s*Score[^\n]*", "", draft or "", flags=re.IGNORECASE)
    scrubbed = re.sub(r"\bScore[^\n]*", "", scrubbed, flags=re.IGNORECASE)
    scrubbed = scrubbed.replace("3〜12ヶ月", "").replace("3-12ヶ月", "")
    for pattern in _SENSITIVE_NUMERIC_PATTERNS:
        for m in re.finditer(pattern, scrubbed, re.IGNORECASE):
            token = m.group(0).strip()
            # source context中に同じ数値表現があれば、一次情報由来として許可。
            # sec/seconds/秒と約の表記揺れは同一の数値+単位として許容する。
            normalized_token = re.sub(r"(?:seconds?|sec|秒)", "s", _normalized_evidence_text(token), flags=re.I).replace("約", "")
            normalized_evidence = re.sub(r"(?:seconds?|sec|秒)", "s", evidence, flags=re.I).replace("約", "")
            if normalized_token not in normalized_evidence:
                failures.append(f"unsupported numeric claim: {token}")
    for pattern in _VAGUE_QUANTIFIED_PATTERNS:
        for m in re.finditer(pattern, scrubbed):
            token = m.group(0)
            if _normalized_evidence_text(token) not in evidence:
                failures.append(f"unsupported vague quantified claim: {token}")
    # 同一表現を何度も返さない。
    return list(dict.fromkeys(failures))[:8]


def _claim_is_negated(text: str, start: int, end: int) -> bool:
    window = (text or "")[max(0, start - 28): min(len(text or ""), end + 40)]
    return bool(re.search(
        r"(?:ではない|とは言えない|とは限らない|断定できない|確認できない|保証しない|保証するものではない|"
        r"根拠(?:が|は)ない|未確認|未検証|避ける|使わない|禁止|推奨しない)",
        window, re.IGNORECASE
    ))


def _find_hype_claims(draft: str, source_context: str = "", evidence_metadata: dict | None = None) -> list[str]:
    failures: list[str] = []
    text = draft or ""
    evidence = source_context or ""
    strength = (evidence_metadata or {}).get("evidence_strength", "UNKNOWN")
    for pattern, label in _HYPE_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            if _claim_is_negated(text, m.start(), m.end()):
                continue
            strong_word = re.search(r"保証|完全|必ず|安全|ゼロコスト|準拠|最速|state-of-the-art", m.group(0), re.I)
            # 強い語自体ではなく、公式の同等保証があるかで判断する。
            if strong_word and (strength in {"SPEC_GUARANTEE", "OFFICIAL_GUARANTEE"} or re.search(r"guarantee[sd]?|保証", evidence, re.I)):
                continue
            failures.append(f"{label}: {m.group(0)}")
            break
    # 「保証」単独もHigh Risk Claimとして検査する。ただし公式の保証があれば許可する。
    for m in re.finditer(r"保証(?:される|した|する|された)", text):
        if _claim_is_negated(text, m.start(), m.end()):
            continue
        supported = strength in {"SPEC_GUARANTEE", "OFFICIAL_GUARANTEE"} or bool(re.search(r"guarantee[sd]?|保証", evidence, re.I))
        if not supported:
            failures.append(f"unsupported guarantee: {m.group(0)}")
    return failures


def _find_false_negative_evidence_claims(draft: str, evidence_metadata: dict) -> list[str]:
    """深い一次資料にあるのに「不明」と書く誤りを止める。"""
    text = draft or ""
    if not re.search(r"確認できない|記載されていない|不明|未公開|未評価|データがない", text):
        return []
    coverage = (evidence_metadata or {}).get("coverage", {})
    mapping = {"GPU|ハードウェア|環境": "hardware", "処理時間|runtime|速度|秒": "runtime", "コード|ソースコード": "code_availability", "評価|ベンチマーク": "benchmark"}
    failures = []
    for sentence in re.split(r"(?<=[。！？])", text):
        if not re.search(r"確認できない|記載されていない|不明|未公開|未評価|データがない", sentence):
            continue
        for cue, key in mapping.items():
            if re.search(cue, sentence, re.I) and coverage.get(key) == "FOUND":
                failures.append("FALSE_NEGATIVE_EVIDENCE_CLAIM: " + key)
    return list(dict.fromkeys(failures))


def _find_final_wording_violations(draft: str, evidence_metadata: dict, freshness: dict | None = None) -> list[str]:
    failures = []
    qualifiers = (evidence_metadata or {}).get("required_qualifiers", [])
    if qualifiers and re.search(r"警告", draft or "") and not re.search(r"単純な|明確に判定|この例|サンプル", draft or ""):
        failures.append("REQUIRED_QUALIFIER_DROPPED")
    if re.search(r"(?:最適化される|高速になる|ゼロコスト)", draft or "") and re.search(r"toy example|simple example|単純な例", json.dumps(evidence_metadata or {}, ensure_ascii=False), re.I) and not re.search(r"この例|サンプル|単純な例", draft or ""):
        failures.append("EVIDENCE_CLASS_GENERALIZED")
    if (freshness or {}).get("followup_found") and _STALE_ARTICLE_PATTERN.search(draft or ""):
        failures.append("STALE_STATUS_CLAIM")
    if re.search(r"(?mi)^\s*={3,}\s*NOTE_DRAFT_(?:START|END)", draft or ""):
        failures.append("INTERNAL_DRAFT_DELIMITER_LEAKED")
    return failures


def _find_unsupported_competitor_claims(parsed: dict, source_context: str) -> list[str]:
    """Groundingなしの具体的競合優劣を止める。一般的な比較軸の提示は許可する。"""
    text = str(parsed.get("alternative_comparison_text", "") or "")
    if not text:
        return []
    evidence = _normalized_evidence_text(source_context)
    # 優劣・一択・明示比較を表す語がなければ問題にしない。
    if not re.search(r"(?:より(?:優|劣|強|弱)|優位|劣る|一択|軍配|最適|圧倒|ほど.{0,10}(?:ない|少ない)|比較して.{0,12}(?:優|劣))", text):
        return []
    # 比較文に現れる英数製品名候補を拾う。Source Contextにない固有名があればFail。
    names = re.findall(r"\b[A-Z][A-Za-z0-9.+_-]{2,}(?:\s+[A-Z][A-Za-z0-9.+_-]{2,})?\b", text)
    ignore = {"Decision", "Source", "API", "URL", "AI", "LLM", "MCP", "GPU", "OSS"}
    unsupported = []
    for name in dict.fromkeys(names):
        if name in ignore:
            continue
        if _normalized_evidence_text(name) not in evidence:
            unsupported.append(name)
    if unsupported:
        return ["unsupported competitor comparison: " + ", ".join(unsupported[:4])]
    return []


def _article_list_ratio(text: str) -> float:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        return 0.0
    list_lines = sum(1 for ln in lines if re.match(r"^(?:[-*]|\d+[.)]|STEP\s*\d+)", ln, re.IGNORECASE))
    return list_lines / len(lines)


def _explicit_decision_conflict(parsed: dict) -> str:
    """最終判断にNOW/TRY等が明記された場合だけ、安全に矛盾を検出する。"""
    draft = parsed.get("note_draft", "")
    final_text = _extract_markdown_section(draft, "結局、どうするべきか") or _extract_markdown_section(draft, "最終判断")
    final_decision = _normalize_decision(final_text)
    decision = parsed.get("decision_text", "")
    if final_decision and decision and final_decision != decision:
        return f"Decision conflict: management={decision}, final={final_decision}"
    return ""



def _find_decision_code_leak(draft: str) -> list[str]:
    """読者向けARTICLEに内部Decisionコードが漏れていないか検出する。"""
    text = draft or ""
    # 英単語として独立して現れる管理コードだけを対象にする。URL等の一部は除外。
    leaked = []
    for code in ("NOW", "TRY", "WATCH", "WAIT", "AVOID"):
        if re.search(rf"(?<![A-Za-z0-9_/-]){code}(?![A-Za-z0-9_/-])", text, re.IGNORECASE):
            leaked.append(code)
    return ["internal decision code leaked into ARTICLE: " + ", ".join(dict.fromkeys(leaked))] if leaked else []


def _find_management_score_leak(draft: str) -> list[str]:
    """Notion用の内部採点がnote本文へ漏れていないか検出する。"""
    text = draft or ""
    leaks = []
    if re.search(r"(?:Business Impact|Technical Impact|Market Impact|Reliability)\s*[:：]", text, re.IGNORECASE):
        leaks.append("management score breakdown leaked into ARTICLE")
    # Decision Score / 総合スコアの明示もARTICLEでは禁止。一般本文中の数値は別Gateで扱う。
    if re.search(r"(?:Decision Score|総合スコア|判定スコア|Score)\s*[:：]\s*\d+\s*(?:/\s*100)?", text, re.IGNORECASE):
        leaks.append("management decision score leaked into ARTICLE")
    return leaks


def _find_source_boundary_violations(draft: str, source_context: str) -> list[str]:
    """Source Context外の「固有製品/企業/モデルに関する事実補完」だけを止める補助Gate。

    一般技術用語・略語・固定見出し・Decision語は対象外。さらに、単に未知の英字語が
    出たという理由だけではFailにせず、現在仕様/導入/比較/価格/公開/サポート等を
    断定する文でのみ判定する。これにより Cursor/Copilot の無根拠補完は止めつつ、
    PoC / What / API / SaaS 等の誤検知を避ける。
    """
    evidence = _normalized_evidence_text(source_context)
    if not draft or not evidence:
        return []

    failures: list[str] = []
    sentences = re.split(r"(?<=[。！？])\s*", draft)
    factual_cue = re.compile(
        r"(?:比較|一方で|に比べ|よりも|公式|サポート|対応|提供|採用|導入|標準|管理|利用|使える|使えない|"
        r"必須|要求|実装|公開|料金|価格|シェア|市場|クラウド|オンプレ|セルフホスト|発売|リリース|"
        r"統合|搭載|廃止|終了|互換|移行|採用され|導入され|提供され|サポートされ)"
    )
    inference = re.compile(
        r"(?:一般論として|私の推論|ここからは.{0,20}推論|推論に基づ|可能性がある|可能性があります|"
        r"考えられる|考えられます|仮説|例として|たとえば|例えば|想定|元記事(?:の記述|公開時点|によれば)|"
        r"一次情報では確認できない|一次情報からは確認できない|未確認|不明|推測)"
    )

    # 固有製品名ではない一般用語・略語・記事テンプレート語。
    ignore = {
        "ARTICLE","MANAGEMENT","DATA","WATCH","TRY","NOW","WAIT","AVOID","What","Decision","Score",
        "GitHub","HackerNews","ProductHunt","ArXiv","Source","Summary","Action","Future","Scenario",
        "API","AI","LLM","MCP","GPU","CPU","OSS","URL","HTTP","HTTPS","PDF","HTML","JSON","XML",
        "Linux","Wayland","Python","Markdown","VAE","RAG","RLHF","SFT","PR","PoC","POC","CTO","PM",
        "SaaS","Web API","RPA","UI","UX","DOM","Webhook","Webhooks","Cookie","Cookies","ID","ACL","2FA","MFA",
        "CLI","SDK","REST","GraphQL","SQL","NoSQL","CI","CD","DevOps","MLOps","AIOps","VPS","VM",
        "AWS","GCP","Azure","KPI","ROI","TCO","SLA","SSO","RBAC","OAuth","JWT","TLS","SSH","TCP",
        "UDP","DNS","CDN","NAT","VPN","VPC","RAM","SSD","HDD","GB","MB","TB","ms","RPM","TPM",
        "RPD","VCS","IDE","OS","Web","Bot","Bots","Agent","Agents","Auditability","Inference"
    }

    def _is_name_candidate(name: str) -> bool:
        if name in ignore:
            return False
        parts = name.split()
        # ALL-CAPS略語は原則一般技術語扱い。固有名として厳格に見るのは通常語形の製品名。
        if len(parts) == 1 and name.isupper():
            return False
        # 3文字以下の単語はノイズが多い。
        if len(name) <= 3:
            return False
        return True

    for sent in sentences:
        if not factual_cue.search(sent) or inference.search(sent):
            continue
        # CamelCase/TitleCase製品名候補。2語製品名も拾う。
        names = re.findall(r"(?<![A-Za-z0-9_])[A-Z][A-Za-z0-9.+_-]{2,}(?:\s+[A-Z][A-Za-z0-9.+_-]{2,})?(?![A-Za-z0-9_])", sent)
        unsupported = []
        for name in dict.fromkeys(names):
            if not _is_name_candidate(name):
                continue
            # PDF抽出で ``DiffVG`` が ``Diff VG`` / ``DiﬀVG`` になるケースを
            # 文字列一致だけで一次資料外と誤判定しない。
            compact_name = _normalized_named_fact(name)
            compact_evidence = _normalized_named_fact(source_context)
            if _normalized_evidence_text(name) not in evidence and compact_name not in compact_evidence:
                unsupported.append(name)
        if unsupported:
            failures.append("source-boundary unsupported named fact: " + ", ".join(unsupported[:4]))
    return list(dict.fromkeys(failures))[:6]

def validate_fact_gate(parsed: dict, repo_name: str, source_context: str = "", source: str = "",
                       evidence_metadata: dict | None = None, source_info: dict | None = None,
                       freshness: dict | None = None, output_truncated: bool = False) -> tuple[bool, list[str]]:
    """公開可否を決めるFact Gate。事実・構造上の致命傷だけをFailにする。"""
    failures: list[str] = []
    draft = parsed.get("note_draft", "")
    marker = PAID_AREA_PATTERN.search(draft)

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
    if not (parsed.get("title_text") or "").strip() or parsed.get("title_text") == "（タイトル抽出失敗）":
        failures.append("title missing")
    elif not re.search(r"[。？]$", parsed.get("title_text", "")):
        failures.append("title must end with 。 or ？")
    for label, key in required_fields.items():
        if not _is_meaningful_field(str(parsed.get(key, ""))):
            failures.append(f"{label} missing")

    # 内部構造は固定だが、noteに表示する見出しは記事ごとに可変とする。
    required_headings = {
        "導入": _display_heading_aliases("intro"), "結論": _display_heading_aliases("conclusion"),
        "重要性": _display_heading_aliases("why"), "概要": _display_heading_aliases("what"),
        "要点": _display_heading_aliases("key"), "筆者判断": _display_heading_aliases("decision"),
        "最終判断": _display_heading_aliases("final"),
    }
    for label, heading in required_headings.items():
        pattern = r"^#{2,3}\s*(?:" + "|".join(re.escape(item) for item in heading) + r")\s*$"
        if not re.search(pattern, draft, re.MULTILINE):
            failures.append(f"required heading missing: {label}")

    structural_missing = sum(
        1 for headings in required_headings.values()
        if not re.search(r"^#{2,3}\s*(?:" + "|".join(re.escape(item) for item in headings) + r")\s*$", draft, re.MULTILINE)
    )
    if structural_missing >= 2:
        failures.append("ARTICLE_STRUCTURE_INCOMPLETE")
    if output_truncated:
        failures.append("OUTPUT_TRUNCATED")
    if source_info and source_info.get("deep_source_required") and not source_info.get("deep_source_scanned"):
        failures.append("SOURCE_DEPTH_INSUFFICIENT")

    failures.extend(_find_unsupported_numeric_claims(draft, source_context, evidence_metadata))
    failures.extend(_find_hype_claims(draft, source_context, evidence_metadata))
    failures.extend(_find_false_negative_evidence_claims(draft, evidence_metadata or {}))
    failures.extend(_find_final_wording_violations(draft, evidence_metadata or {}, freshness))
    failures.extend(_find_unsupported_competitor_claims(parsed, source_context))
    failures.extend(_find_management_score_leak(draft))
    failures.extend(_find_decision_code_leak(draft))
    failures.extend(_find_source_boundary_violations(draft, source_context))

    # 深い一次資料に明示された限界を記事から丸ごと落とすことを禁止する。
    limitation_present = re.search(r"limitation|limitations|issue|challenge|artifact|occlusion|noisy background|rough sketch|制約|限界|課題", source_context or "", re.I)
    limitation_retained = re.search(r"制約|限界|課題|注意|未検証|アーティファクト|オクルージョン|ノイズ|粗いスケッチ|promising|可能性", draft, re.I)
    if limitation_present and not limitation_retained:
        failures.append("LIMITATION_DROPPED")

    conflict = _explicit_decision_conflict(parsed)
    if conflict:
        failures.append(conflict)
    return (not failures, list(dict.fromkeys(failures)))


def validate_editorial_gate(parsed: dict, repo_name: str) -> tuple[bool, list[str]]:
    """Editorial Gate: 読みやすさ・機械的構成・AI的な文体傾向を診断する。"""
    warnings: list[str] = []
    draft = parsed.get("note_draft", "")
    if _article_list_ratio(draft) > 0.55:
        warnings.append("article too list-like; rewrite as natural prose")
    if len(re.findall(r"(?:第一に|第二に|第三に)", draft)) >= 3:
        warnings.append("mechanical ordinal structure")
    if len(re.findall(r"(?:意味します|と言えます|となります)[。\n]", draft)) >= 5:
        warnings.append("repetitive AI-like sentence endings")
    headings = re.findall(r"^#{2,3}\s+(.+)$", draft, re.MULTILINE)
    if len(headings) > 12:
        warnings.append(f"too many article headings: {len(headings)}")
    warnings.extend(_find_humanization_violations(draft))
    return (not warnings, list(dict.fromkeys(warnings)))


def validate_publication_readiness_gate(parsed: dict, source_context: str = "", source_info: dict | None = None) -> tuple[str, list[str]]:
    """Publication Readiness Gate: 公開完成度を横断確認し、根拠・判断の弱さはREVIEWへ分離する。"""
    article = parsed.get("note_draft", "")
    title = parsed.get("title_text", "")
    action = parsed.get("action_text", "") + "\n" + _extract_any_markdown_section(article, _display_heading_aliases("decision"))
    score = int(parsed.get("score") or 0)
    context = source_context or ""
    issues: list[str] = []
    strong = r"(?:革命的|圧倒的|ゲームチェンジャー|世界初|世界最速|必ず|完全に|従来技術を終わらせ|開発を変える)"
    weak_evidence = re.search(r"(?:abstract|要旨|experimental|prototype|proof of concept|demo|予備的|本番未検証|研究環境)", context, re.I)
    if re.search(strong, title) and weak_evidence:
        issues.append("headline_overclaim")
    intro = article[:1200]
    if re.search(strong, intro) and weak_evidence:
        issues.append("intro_overclaim")
    if weak_evidence and re.search(r"(?:本番(?:環境)?(?:へ|に)?(?:導入|投入)|全面(?:導入|移行)|既存(?:環境|システム)を置き換)", action):
        issues.append("research_to_production_leap")
    if score and score <= 69 and re.search(r"(?:今すぐ|直ちに|全面(?:導入|移行)|必ず導入)", article):
        issues.append("score_narrative_mismatch")
    if score >= 90 and re.search(r"(?:見る必要はない|検討不要|関心を持つ必要はない)", article):
        issues.append("score_narrative_mismatch")
    if re.search(r"(?:world'?s fastest|世界最速|revolutionary|革命的)", context, re.I) and re.search(r"(?:世界最速|革命的)", article) and not re.search(r"(?:開発元|原資料|説明)は", article):
        issues.append("marketing_claim_adoption")
    if re.search(r"(?:memory|メモリ).{0,30}(?:\+?80%|増)", context, re.I) and not re.search(r"(?:memory|メモリ|消費量|80%)", article, re.I):
        issues.append("negative_evidence_omission")
    if source_info and not source_info.get("sufficient"):
        issues.append("primary_evidence_insufficient")
    return ("REVIEW" if issues else "PASS", list(dict.fromkeys(issues)))


def _classify_article_claims(parsed: dict) -> dict[str, int]:
    """公開安全性と筆者判断を混同しないための、軽量な文種カウント。

    これは事実性を証明する分類器ではない。Publication修正で FACT 以外の
    観察・推論・判断まで消していないかを、LLM追加呼び出しなしで監視する。
    """
    article = (parsed.get("note_draft", "") or "")
    action = (parsed.get("action_text", "") or "")
    return {
        "fact": len(re.findall(r"(?:原資料|論文|著者|公式|公開|実験|データ|仕様|確認でき)", article)),
        "interpretation": len(re.findall(r"(?:と考えられる|と見える|私の推論|意味する|示唆)", article)),
        "observation": len(re.findall(r"(?:一方で|ただ|現時点では|注意|限界|課題|不明)", article)),
        "decision": len(re.findall(r"(?:私なら|試(?:す|したい)|検証(?:する|したい)|比較(?:する|したい)|見送(?:る|り)|待(?:つ|ち)|導入を急が)", article + "\n" + action)),
    }


def validate_human_appeal_gate(parsed: dict) -> tuple[str, list[str]]:
    """Human Appeal Gate: Humanizationとは別に、読ませる力と判断の具体性を診断する。

    WEAK は即時の事実エラーではない。具体的判断の消失など重要な場合だけ、
    最終リトライ後に Needs Editorial Review へ送る。
    """
    article = parsed.get("note_draft", "") or ""
    title = parsed.get("title_text", "") or ""
    action = parsed.get("action_text", "") or ""
    decision_section = _extract_any_markdown_section(article, _display_heading_aliases("decision"))
    decision_text = f"{action}\n{decision_section}"
    issues: list[str] = []

    # 「○○について。」のような説明だけの題は、過剰な安全化でタイトルの役割を
    # 失った可能性が高い。ただし短い固有名詞タイトルを一律に落とさない。
    if re.fullmatch(r".{1,45}(?:について|の紹介|を解説)[。？]", title.strip()):
        issues.append("headline_flattened")

    hedge_pattern = r"(?:可能性(?:がある|があります)|考えられ(?:る|ます)|注視(?:したい|する|すべき)|様子を見(?:る|たい)|かもしれない)"
    hedge_count = len(re.findall(hedge_pattern, article))
    concrete_action = re.search(r"(?:限定|小さく|検証環境|PoC|比較(?:テスト|検証)|試(?:す|したい)|見送(?:る|り)|待(?:つ|ち)|導入を急がない)", decision_text, re.I)
    generic_monitor = re.search(r"(?:注視|様子を見)", decision_text)
    if generic_monitor and not concrete_action:
        issues.append("action_collapsed_to_generic_monitoring")
    if hedge_count >= 5 and not concrete_action:
        issues.append("over_hedging_without_decision")

    claims = _classify_article_claims(parsed)
    if not concrete_action and claims["decision"] == 0:
        issues.append("decision_voice_missing")
    if claims["observation"] == 0 and claims["interpretation"] == 0:
        issues.append("no_editorial_observation")
    if len(re.findall(r"(?:ただ、ここは注意が必要です。|一方で、注意が必要です。)", article)) >= 2:
        issues.append("repeated_caveat_phrase")

    # 読み手への入口が説明文だけにならないかを軽く確認する。疑問符は必須にしない。
    intro = _extract_any_markdown_section(article, _display_heading_aliases("intro"))
    if intro and not re.search(r"(?:なぜ|どこ|何が|課題|現場|原資料|一見|数字|変わ)", intro[:500]):
        issues.append("opening_hook_weak")

    issues = list(dict.fromkeys(issues))
    return ("WEAK" if issues else "ACCEPTABLE", issues)


# Backward compatibility aliases. 正式な実装・Pipeline本体は *_gate 名を使用する。
validate_publication_readiness = validate_publication_readiness_gate
validate_human_appeal = validate_human_appeal_gate


def human_appeal_materially_degraded(before: dict, after: dict) -> bool:
    """再編集で具体的な筆者判断が一般論へ潰れた場合だけ劣化とみなす。"""
    before_claims = _classify_article_claims(before)
    after_claims = _classify_article_claims(after)
    before_action = (before.get("action_text", "") or "") + "\n" + _extract_any_markdown_section(before.get("note_draft", ""), _display_heading_aliases("decision"))
    after_action = (after.get("action_text", "") or "") + "\n" + _extract_any_markdown_section(after.get("note_draft", ""), _display_heading_aliases("decision"))
    concrete = r"(?:限定|小さく|検証環境|PoC|比較(?:テスト|検証)|試(?:す|したい)|見送(?:る|り)|待(?:つ|ち)|導入を急がない)"
    return bool(
        re.search(concrete, before_action, re.I)
        and not re.search(concrete, after_action, re.I)
        and re.search(r"(?:注視|様子を見)", after_action)
        or (before_claims["decision"] > 0 and after_claims["decision"] == 0)
    )


def _find_humanization_violations(draft: str) -> list[str]:
    """事実検証とは分離した、表現だけを再編集するための軽量Gate。"""
    warnings: list[str] = []
    text = draft or ""
    fixed_openings = ("結論から言うと", "今回紹介する", "この記事では", "〜について解説します")
    if sum(text.count(phrase) for phrase in fixed_openings) >= 2:
        warnings.append("repetitive fixed introduction")
    if re.search(r"(?:私は驚きました|正直ワクワクしました|使ってみ(?:て)?|以前から気になっていました)", text):
        warnings.append("unsupported personal experience")
    if not re.search(r"(?:ただ|一見すると|現時点では|注意(?:が必要|したい)|評価が分かれ|信用しすぎ)", text):
        warnings.append("missing observation or reservation")
    if len(re.findall(r"理由は(?:3|三)つ", text)) >= 1:
        warnings.append("mechanical three-reasons phrasing")
    if len(re.findall(r"[？?]", text)) > 5:
        warnings.append("too many reader questions")
    sentences = [s.strip() for s in re.split(r"(?<=[。！？])", text) if s.strip()]
    endings = ["ます" if re.search(r"ます[。！？]?$", s) else "です" if re.search(r"です[。！？]?$", s) else "other" for s in sentences]
    if len(endings) >= 8 and max(endings.count(kind) for kind in set(endings)) / len(endings) > 0.88:
        warnings.append("monotonous sentence endings")
    return warnings


def validate_paid_article(parsed: dict, repo_name: str, source_context: str = "", source: str = "") -> tuple[bool, list[str]]:
    """後方互換。公開可否はFact Gateのみで決める。"""
    return validate_fact_gate(parsed, repo_name, source_context=source_context, source=source)


def validate_synthetic_invariants(ground_truth: dict, article: str, evidence: str) -> list[dict]:
    """Offline adapter used by the synthetic suite to exercise production code.

    It deliberately remains credential-free, but it lives in pipeline.py so a
    change to production validation cannot leave the regression suite detached.
    """
    findings: list[dict] = []
    lowered = (article or "").lower()
    critical = {"INV-002", "INV-004", "INV-007", "INV-014", "INV-015", "INV-017", "INV-019", "INV-020"}
    def add(code: str, stage: str, message: str, severity: str = "major"):
        findings.append({"code": code, "severity": "critical" if code in critical else severity, "stage": stage, "message": message})
    for forbidden in ground_truth.get("forbidden_claims", []):
        if forbidden.lower() in lowered:
            add((ground_truth.get("expected_flags") or ["FORBIDDEN_CLAIM"])[0], "FINAL_WORDING", f"forbidden claim: {forbidden}")
    for qualifier in ground_truth.get("required_qualifiers", []):
        aliases = {"単純な例": ["単純な例", "原著の例", "simple case"], "原著の例": ["単純な例", "原著の例", "simple case"], "可能性": ["可能性", "may", "could"], "著者は": ["著者", "author"]}
        if not any(token.lower() in lowered for token in aliases.get(qualifier, [qualifier])):
            add("INV-006", "FINAL_WORDING", f"required qualifier dropped: {qualifier}")
    for label, value in ground_truth.get("numerical_truth", {}).items():
        if ("runtime" in label or "sample" in label) and str(value) not in (article or ""):
            add("INV-020", "NUMERICAL_VALIDATION", f"number missing: {value}", "moderate")
    if "hardwareは確認できない" in lowered and re.search(r"hardware:|RTX|H100", evidence or "", re.I):
        add("INV-004", "DEEP_EXTRACTION", "false absence claim")
    return findings

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


def _response_was_truncated(response) -> bool:
    """SDKが返すfinish_reasonを記録し、MAX_TOKENS等の途中終了を品質問題として扱う。"""
    try:
        candidate = response.candidates[0]
        reason = str(getattr(candidate, "finish_reason", "")).upper()
        logger.info(f"[GEMINI FINISH] reason={reason or 'UNKNOWN'}")
        return any(token in reason for token in ("MAX_TOKENS", "LENGTH", "TOKEN_LIMIT"))
    except Exception:
        return False


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
    # Python/GitHub/arXiv等で一次本文を十分確保できた場合はURL Contextを重ねない。
    # HN/PHもPython側本文取得が不足した場合だけURL Contextへfallbackする。
    # Google Searchを明示ONにした場合のみURL Contextも併用する。
    return ENABLE_GOOGLE_SEARCH_GROUNDING or not source_info.get("sufficient")


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

    config = {"max_output_tokens": GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS}
    if tools:
        config["tools"] = tools
    logger.info("[GEMINI DEEP DIVE CALL] kind=%s timeout=%ss", request_kind, GEMINI_DEEP_DIVE_CALL_TIMEOUT_SECONDS)
    response, selected_model = _call_deep_dive_pool(prompt, config, request_kind)
    global SELECTED_DEEP_DIVE_MODEL
    SELECTED_DEEP_DIVE_MODEL = selected_model
    _extract_usage_metadata(response)
    meta = extract_grounding_metadata(
        response,
        source_info.get("primary_url", ""),
        bool(source_info.get("sufficient")),
        any("url_context" in t for t in tools),
        any("google_search" in t for t in tools),
    )
    return response, meta

def _paid_area_length(note_draft: str, repo_name: str) -> int:
    """クレンジング後の有料エリアの文字数を返す（品質ゲートの判定基準）。"""
    _, paid_part = split_free_paid(note_draft, repo_name)
    return len(normalize_markdown_for_note(paid_part))

def generate_intelligence_report(repo, notion_page_id: str | None = None,
                                 screening_score: int | None = None,
                                 screening_reason: str = "",
                                 persist_results: bool = True):
    """Grounded Deep Diveを生成し、構造Quality Gateで最大1回だけ救済する。

    persist_results=False は既存記事A/B比較専用。Gemini生成・Quality Gateは通常どおり
    実行するが、Notionの新規作成/更新・Quality Failed更新・GitHub eyecatch uploadを
    行わず、生成稿だけをローカルへ返す。
    """
    name = repo.get("nameWithOwner")
    desc = repo.get("description", "説明なし")
    url = repo.get("url")
    stars = repo.get("stargazerCount", 0)
    source = repo.get("source", "GitHub")
    published_at = repo.get("publishedAt")
    _, spdx_id = legal_safety_gate(repo)

    if source == "ArXiv":
        integrity_ok, integrity_reason, verified_repo = _verify_arxiv_source_integrity(repo)
        if not integrity_ok:
            logger.error(f"[SOURCE INTEGRITY FAILED] {name}: {integrity_reason}")
            if persist_results:
                send_telegram_alert(f"ℹ️ Source Integrity Failed: {name}\n{integrity_reason[:1200]}")
            return None
        repo = verified_repo
        logger.info(f"[SOURCE INTEGRITY OK] {name}: {integrity_reason}")

    source_info = prepare_source_context(repo)
    primary_url = source_info.get("primary_url") or url
    # 研究ページに到達可能な論文/補足資料があるのに取得できなければ、landing page
    # の文章量だけで記事化しない。Gemini呼び出し前にFail Closedする。
    if source_info.get("deep_source_required") and not source_info.get("deep_source_scanned"):
        logger.warning(f"[SOURCE DEPTH INSUFFICIENT] {name}: deep primary source could not be scanned")
        if persist_results and notion_page_id:
            update_notion_quality_failed(notion_page_id, name, GROUNDING_FAILED, source_info.get("deep_source_urls", []))
        return None
    freshness = resolve_followup_freshness(source_info)
    if freshness.get("context"):
        source_info["context"] = _truncate_source_context(source_info.get("context", "") + "\n\n" + freshness["context"])
    # APIを呼ぶ前に一次情報不足を判定できるならBackfillへ回す。
    if not source_info.get("sufficient") and not (ENABLE_URL_CONTEXT and primary_url.startswith(("http://", "https://"))):
        logger.warning(f"[GROUNDING FAILED] {name}: 一次情報不足のためGeminiを呼ばずスキップ")
        page_id = notion_page_id
        if persist_results and not page_id and screening_score is not None and screening_score >= NOTION_SAVE_THRESHOLD_SCORE:
            page_id = save_screening_metadata_to_notion(repo, screening_score, screening_reason or "Deep Dive候補")
        if persist_results and page_id:
            update_notion_quality_failed(page_id, name, GROUNDING_FAILED, [primary_url] if primary_url else [])
        return None

    quality_feedback = ""
    last_grounding = {"grounding_status": source_info.get("method", GROUNDING_METADATA_ONLY), "evidence_urls": [primary_url] if primary_url else []}
    quality_gate_passed = False
    final_quality_failures: list[str] = []
    appeal_before_reedit: dict | None = None

    try:
        parsed = None
        for attempt in range(MAX_QUALITY_RETRIES + 1):
            request_kind = "deep_dive" if attempt == 0 else "quality_retry"
            prompt = build_decision_prompt(
                name, primary_url, stars, desc, quality_feedback, source,
                source_context=source_info.get("context", ""),
                grounding_status_hint=source_info.get("method", GROUNDING_METADATA_ONLY),
                evidence_metadata=source_info.get("evidence_metadata", {}), freshness=freshness,
            )
            response, grounding = call_gemini_grounded_deep_dive(prompt, repo, source_info, request_kind=request_kind)
            output_truncated = _response_was_truncated(response)
            last_grounding = grounding
            parsed = _parse_gemini_response(response.text or "")
            parsed.update({
                "grounding_status": grounding.get("grounding_status", GROUNDING_FAILED),
                "evidence_urls_text": "\n".join(grounding.get("evidence_urls", [])),
            })
            # Grounding失敗は文章構造の問題ではないため、Quality Retryを消費しない。
            # source-nativeもURL Contextも一次情報を確保できなかった候補は即Backfillへ回す。
            if parsed["grounding_status"] == GROUNDING_FAILED:
                failures = ["Grounding failed"]
                logger.error(f"[GROUNDING FAILED] {name}: 一次情報の取得を確認できないため記事化せずBackfill")
                page_id = notion_page_id
                if persist_results and not page_id and screening_score is not None and screening_score >= NOTION_SAVE_THRESHOLD_SCORE:
                    page_id = save_screening_metadata_to_notion(repo, screening_score, screening_reason or "Deep Dive候補")
                if persist_results and page_id:
                    update_notion_quality_failed(page_id, name, GROUNDING_FAILED, grounding.get("evidence_urls", []))
                if persist_results:
                    send_telegram_alert(f"ℹ️ Grounding Failed: {name}\n一次情報を確認できないため記事化せず次候補へ進みます。")
                return None

            fact_ok, fact_failures = validate_fact_gate(
                parsed, name, source_context=source_info.get("context", ""), source=source,
                evidence_metadata=source_info.get("evidence_metadata", {}), source_info=source_info,
                freshness=freshness, output_truncated=output_truncated,
            )
            editorial_ok, editorial_warnings = validate_editorial_gate(parsed, name)
            publication_state, publication_issues = validate_publication_readiness_gate(
                parsed, source_info.get("context", ""), source_info,
            )
            human_appeal, human_appeal_issues = validate_human_appeal_gate(parsed)
            logger.info("[PUBLICATION READINESS GATE] %s: %s", name, publication_state)
            logger.info("[HUMAN APPEAL GATE] %s: %s", name, human_appeal)
            if appeal_before_reedit is None:
                appeal_before_reedit = parsed.copy()
            elif human_appeal_materially_degraded(appeal_before_reedit, parsed):
                human_appeal_issues.append("human_appeal_materially_degraded_after_reedit")
                human_appeal = "WEAK"
            # Human AppealはHumanizationとは別の品質軸。安全なだけで無難な記事を
            # 自動Readyにしないが、軽微な文体警告をFact failureへ昇格させない。
            appeal_review_required = any(issue in {
                "action_collapsed_to_generic_monitoring", "decision_voice_missing",
                "headline_flattened", "human_appeal_materially_degraded_after_reedit",
            } for issue in human_appeal_issues)
            failures = fact_failures + editorial_warnings + publication_issues + human_appeal_issues
            final_quality_failures = failures
            if fact_ok and editorial_ok and publication_state == "PASS" and human_appeal == "ACCEPTABLE":
                quality_gate_passed = True
                break
            if (publication_state == "REVIEW" or appeal_review_required) and attempt >= MAX_QUALITY_RETRIES:
                review_issues = publication_issues + human_appeal_issues
                logger.warning("[PUBLICATION READINESS GATE] Needs Editorial Review: %s: %s", name, ", ".join(review_issues))
                if not persist_results:
                    break
                page_id = notion_page_id
                if not page_id and screening_score is not None and screening_score >= NOTION_SAVE_THRESHOLD_SCORE:
                    page_id = save_screening_metadata_to_notion(repo, screening_score, screening_reason or "Deep Dive候補")
                if page_id:
                    update_notion_needs_editorial_review(page_id, name, review_issues)
                send_telegram_alert(f"ℹ️ Needs Editorial Review: {name}\n" + " / ".join(review_issues)[:1200])
                return None
            # Human Appealの軽微な警告（入口の弱さ等）は記録して公開を妨げない。
            # 具体的Decisionの消失だけは上のReviewルートで人手確認に回す。
            if fact_ok and editorial_ok and publication_state == "PASS" and attempt >= MAX_QUALITY_RETRIES:
                logger.warning(f"[HUMAN APPEAL GATE] warning: {name}: {', '.join(human_appeal_issues)}")
                quality_gate_passed = True
                final_quality_failures = human_appeal_issues
                break
            # Editorialだけの問題は1回だけ書き直しを促す。2回目はFactが通っていれば公開可。
            if fact_ok and publication_state == "PASS" and not editorial_ok and attempt >= MAX_QUALITY_RETRIES:
                logger.warning(f"[EDITORIAL GATE WARN] {name}: {', '.join(editorial_warnings)}")
                quality_gate_passed = True
                final_quality_failures = editorial_warnings
                break
            if attempt >= MAX_QUALITY_RETRIES:
                logger.error(f"[FACT GATE FAILED] {name}: {', '.join(fact_failures)}")
                if not persist_results:
                    # 再生成テストはGate調整そのものが目的。落ちた稿も捨てず、
                    # REJECTEDとして保存・全文ログ表示できるところまで処理を継続する。
                    logger.warning(f"[REGEN TEST KEEP REJECTED] {name}: Quality Gate不合格稿を比較用に保持します。")
                    break
                page_id = notion_page_id
                if not page_id and screening_score is not None and screening_score >= NOTION_SAVE_THRESHOLD_SCORE:
                    page_id = save_screening_metadata_to_notion(repo, screening_score, screening_reason or "Deep Dive候補")
                if page_id:
                    update_notion_quality_failed(page_id, name, parsed.get("grounding_status", GROUNDING_FAILED), grounding.get("evidence_urls", []))
                send_telegram_alert(f"ℹ️ Quality Failed: {name}\n" + " / ".join(failures)[:1500])
                return None
            if "ARTICLE_STRUCTURE_INCOMPLETE" in failures or "OUTPUT_TRUNCATED" in failures:
                quality_feedback = "ARTICLE_STRUCTURE_INCOMPLETE: 記事が途中で終了している。前稿の文章を継ぎ足さず、指定フォーマットを最初から最後まで完全に再生成すること。"
            else:
                quality_feedback = "前回出力の不足項目: " + "; ".join(failures)
            gate_name = "FACT+EDITORIAL" if fact_failures and editorial_warnings else ("FACT" if fact_failures else "EDITORIAL/HUMAN_APPEAL")
            logger.warning(f"[QUALITY RETRY:{gate_name}] {name}: {quality_feedback}")

        if not parsed:
            return None

        evidence_urls = last_grounding.get("evidence_urls", [])
        clean_manuscript = build_clean_note_manuscript(
            parsed["note_draft"], name, url, spdx_id, source, evidence_urls=evidence_urls,
            title_text=parsed.get("title_text", ""),
            discovery_url=(repo.get("sourceDetails", {}) or {}).get("hn_url", ""),
        )

        eyecatch_url = ""
        if persist_results:
            try:
                os.makedirs(EYECATCH_OUTPUT_DIR, exist_ok=True)
                eyecatch_filename = f"{_sanitize_filename(name)}.png"
                eyecatch_path = os.path.join(EYECATCH_OUTPUT_DIR, eyecatch_filename)
                generated_path = generate_eyecatch_image(parsed["title_text"], eyecatch_path, source, decision_score=parsed.get("score"))
                if generated_path:
                    logger.info(f"[EYECATCH] {name} -> {eyecatch_path} を生成しました。")
                    eyecatch_url = upload_eyecatch_to_github(eyecatch_path, eyecatch_filename) or ""
            except Exception as e:
                logger.warning(f"[EYECATCH SKIP] {name}: {e}")
        else:
            logger.info(f"[REGEN TEST] eyecatch生成・GitHub uploadをスキップ: {name}")

        analyzed_at = _analyzed_at_now_iso()
        if persist_results:
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
        else:
            regen_status = "accepted" if quality_gate_passed else "rejected"
            save_regen_test_manuscript(
                repo, clean_manuscript,
                quality_status=regen_status,
                quality_failures=final_quality_failures,
            )
            # 再生成ランナーだけがACCEPTED/REJECTEDを正しく集計できるようstatusも返す。
            return clean_manuscript, regen_status
        return clean_manuscript

    except DailyQuotaExhaustedError:
        raise
    except (GeminiCallTimeoutError, NoAvailableModelError, APIError) as e:
        logger.error(f"[DEEP DIVE TRANSIENT FAILURE] {name}: {e}")
        page_id = notion_page_id
        if persist_results and not page_id and screening_score is not None and screening_score >= NOTION_SAVE_THRESHOLD_SCORE:
            page_id = save_screening_metadata_to_notion(repo, screening_score, screening_reason or "Deep Dive候補")
        if persist_results and page_id:
            update_notion_pending_retry(page_id, name, str(e))
        return None
    except GeminiBudgetExceededError as e:
        logger.warning(f"[GEMINI BUDGET STOP] {name}: {e}")
        if persist_results and notion_page_id:
            update_notion_pending_retry(notion_page_id, name, str(e))
        return None
    except Exception as e:
        logger.error(f"[DEEP DIVE FAILED] {name}: {e}")
        page_id = notion_page_id
        if persist_results and not page_id and screening_score is not None and screening_score >= NOTION_SAVE_THRESHOLD_SCORE:
            page_id = save_screening_metadata_to_notion(repo, screening_score, screening_reason or "Deep Dive候補")
        if persist_results and page_id:
            update_notion_pending_retry(page_id, name, str(e))
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
                SELECTED_SCREENING_MODEL, prompt,
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


def round_robin_candidates(source_groups: dict[str, list[dict]], limit: int) -> list[dict]:
    """Avoid source-order starvation when a cross-source cap is applied."""
    result: list[dict] = []
    queues = {source: list(items) for source, items in source_groups.items()}
    while len(result) < limit and any(queues.values()):
        for source in source_groups:
            if len(result) >= limit:
                break
            if queues[source]:
                result.append(queues[source].pop(0))
    return result


def _parse_batch_screening_response(text: str, expected_ids: set[str], include_diagnostic: bool = False):
    diagnostic = ""
    try:
        payload = json.loads(text or "[]")
    except json.JSONDecodeError as exc:
        parsed, diagnostic = {}, f"json_decode_error:{exc.msg}"
    else:
        parsed = {}
        if not isinstance(payload, list):
            diagnostic = "response_not_list"
        else:
            invalid = []
            for row in payload:
                if not isinstance(row, dict):
                    invalid.append("row_not_object")
                    continue
                candidate_id = str(row.get("id", ""))
                if candidate_id not in expected_ids:
                    invalid.append(f"unknown_id:{candidate_id}")
                    continue
                if candidate_id in parsed:
                    invalid.append(f"duplicate_id:{candidate_id}")
                    continue
                try:
                    score = int(row.get("score"))
                except (TypeError, ValueError):
                    invalid.append(f"invalid_score:{candidate_id}")
                    continue
                if not 0 <= score <= 100:
                    invalid.append(f"score_out_of_range:{candidate_id}")
                    continue
                reason = str(row.get("reason", "取得失敗")).strip()[:120] or "取得失敗"
                parsed[candidate_id] = {"score": score, "reason": reason}
            if invalid:
                diagnostic = ";".join(invalid)
    missing = sorted(expected_ids - set(parsed))
    return (parsed, missing, diagnostic) if include_diagnostic else (parsed, missing)


def call_screening_provider(prompt: str, kind: str = "screening_batch"):
    max_tokens = GLOBAL_CALIBRATION_MAX_OUTPUT_TOKENS if kind == "global_calibration" else SCREENING_BATCH_MAX_OUTPUT_TOKENS
    response, model_name = _call_screening_pool(
        prompt, {"response_mime_type": "application/json", "max_output_tokens": max_tokens}, kind,
        GEMINI_RESERVED_DEEP_DIVE_REQUESTS,
    )
    global SELECTED_SCREENING_MODEL
    SELECTED_SCREENING_MODEL = model_name
    return response


def _batch_screening_prompt(batch: list[dict]) -> str:
    rows = []
    for item in batch:
        repo = item["repo"]
        rows.append({"id": item["screening_id"], "source": repo.get("source", "GitHub"),
                     "name": repo.get("nameWithOwner", ""), "description": repo.get("description", ""),
                     "engagement": repo.get("stargazerCount", 0), "published_at": repo.get("publishedAt"),
                     "url": repo.get("url", "")})
    return (
        "以下の候補を、CTO/PM向け記事題材として0〜100点で公平に採点せよ。"
        "技術的新規性、実務インパクト、導入・意思決定への影響、緊急性、"
        "市場波及性、情報源の信頼性を簡潔に総合評価すること。"
        "Sourceが異なる候補間でEngagementの絶対値を直接比較してはならない。"
        "この段階ではURL本文・README・論文全文を推測して使わない。"
        "出力は必ずJSON配列だけ。各要素は id, score, reason（40字以内）とする。\n"
        + json.dumps(rows, ensure_ascii=False)
    )


def _calibration_prompt(batch: list[dict]) -> str:
    rows = []
    for item in batch:
        repo = item["repo"]
        rows.append({"id": item["screening_id"], "source": repo.get("source", ""),
                     "name": repo.get("nameWithOwner", ""), "description": repo.get("description", ""),
                     "raw_score": item.get("raw_score"), "engagement": repo.get("stargazerCount", 0),
                     "published_at": repo.get("publishedAt"), "url": repo.get("url", "")})
    return (
        "以下は一次Batch審査で55点以上だった候補である。候補群を横断比較し、"
        "Notion Stock候補としての一貫した最終スコアを返せ。"
        "技術的新規性、実務インパクト、意思決定への影響、緊急性、情報源の信頼性を評価し、"
        "異Source間でEngagementの絶対値を直接比較してはならない。"
        "出力はJSON配列のみ。各要素は id, score, reason（40字以内）。\n"
        + json.dumps(rows, ensure_ascii=False)
    )


def screen_batch(batch: list[dict], *_args, recovery: bool = False, **_kwargs):
    if not batch:
        return [], [], 0
    if not GEMINI_BUDGET.can_request(reserve=GEMINI_RESERVED_DEEP_DIVE_REQUESTS):
        return [], list(batch), 0
    try:
        response = call_screening_provider(_batch_screening_prompt(batch), "screening_recovery" if recovery else "screening_batch")
        parsed, missing, diagnostic = _parse_batch_screening_response(
            getattr(response, "text", ""), {item["screening_id"] for item in batch}, include_diagnostic=True,
        )
        if diagnostic:
            logger.warning("[BATCH SCREENING] %s", diagnostic)
        completed = []
        for item in batch:
            row = parsed.get(item["screening_id"])
            if row:
                completed.append({"repo": item["repo"], "screening_id": item["screening_id"],
                                  "raw_score": row["score"], "final_score": row["score"],
                                  "score": row["score"], "reason": row["reason"],
                                  "calibrated": False, "screening_status": "completed"})
        unresolved = [item for item in batch if item["screening_id"] in set(missing)]
        return completed, unresolved, 1
    except (NoAvailableModelError, GeminiBudgetExceededError) as exc:
        logger.warning("[BATCH SCREENING UNAVAILABLE] %s", exc)
        return [], list(batch), 1
    except APIError as exc:
        if getattr(exc, "code", None) == 429 and _is_daily_quota_exhausted(exc):
            raise DailyQuotaExhaustedError(str(exc)) from exc
        logger.warning("[BATCH SCREENING FAILED] %s", exc)
        return [], list(batch), 1


def screen_candidates_in_batches(candidates: list[dict]) -> tuple[list[dict], int]:
    completed: list[dict] = []
    calls = 0
    missing: list[dict] = []
    for start in range(0, len(candidates), SCREENING_BATCH_SIZE):
        if start and SCREENING_BATCH_PACING_SECONDS > 0:
            time.sleep(SCREENING_BATCH_PACING_SECONDS)
        rows, unresolved, used = screen_batch(candidates[start:start + SCREENING_BATCH_SIZE])
        completed.extend(rows); missing.extend(unresolved); calls += used
    # Only missing IDs are retried, in smaller batches.  Valid results are never
    # discarded merely because a single model response was truncated.
    if missing and GEMINI_BUDGET.can_screening_retry():
        for start in range(0, len(missing), SCREENING_RECOVERY_BATCH_SIZE):
            if start and SCREENING_BATCH_PACING_SECONDS > 0:
                time.sleep(SCREENING_BATCH_PACING_SECONDS)
            rows, unresolved, used = screen_batch(missing[start:start + SCREENING_RECOVERY_BATCH_SIZE], recovery=True)
            completed.extend(rows); calls += used
            for item in unresolved:
                completed.append({"repo": item["repo"], "screening_id": item["screening_id"],
                                  "raw_score": None, "final_score": None, "score": 0,
                                  "reason": "Screening APIで判定できなかった", "calibrated": False,
                                  "screening_status": "failed", "error_category": "quota_or_transport"})
    else:
        for item in missing:
            completed.append({"repo": item["repo"], "screening_id": item["screening_id"],
                              "raw_score": None, "final_score": None, "score": 0,
                              "reason": "Screening APIで判定できなかった", "calibrated": False,
                              "screening_status": "failed", "error_category": "quota_or_transport"})
    return completed, calls


def calibrate_candidates(items: list[dict]) -> tuple[list[dict], int]:
    """Raw 55点以上だけを再採点し、Batch間の評価基準差をFinal Scoreへ反映する。"""
    if not ENABLE_GLOBAL_CALIBRATION:
        return items, 0
    survivors = [item for item in items if item.get("screening_status") == "completed"
                 and (item.get("raw_score") or 0) >= GLOBAL_CALIBRATION_MIN_RAW_SCORE]
    calls = 0
    for start in range(0, len(survivors), GLOBAL_CALIBRATION_BATCH_SIZE):
        if start and SCREENING_BATCH_PACING_SECONDS > 0:
            time.sleep(SCREENING_BATCH_PACING_SECONDS)
        batch = survivors[start:start + GLOBAL_CALIBRATION_BATCH_SIZE]
        try:
            response = call_screening_provider(_calibration_prompt(batch), "global_calibration")
            parsed, missing, diagnostic = _parse_batch_screening_response(
                getattr(response, "text", ""), {item["screening_id"] for item in batch}, include_diagnostic=True,
            )
            calls += 1
            if diagnostic or missing:
                logger.warning("[CALIBRATION PARTIAL] diagnostic=%s missing=%s", diagnostic, len(missing))
            for item in batch:
                row = parsed.get(item["screening_id"])
                if row:
                    item["final_score"] = row["score"]
                    item["score"] = row["score"]
                    item["reason"] = row["reason"]
                    item["calibrated"] = True
        except DailyQuotaExhaustedError:
            raise
        except Exception as exc:
            # Calibrationは補正層。失敗しても有効なRaw Scoreを失わず処理を継続する。
            calls += 1
            logger.warning("[CALIBRATION FAILED] Raw Scoreを維持: %s", exc)
    logger.info("[CALIBRATION] raw_survivors=%s calibrated=%s calls=%s", len(survivors),
                sum(1 for item in survivors if item.get("calibrated")), calls)
    return items, calls


def upload_observed_history_to_github(local_path: str, dest_filename: str) -> str | None:
    """Observed履歴は補助資産としてGitHubへ保存し、失敗しても本処理を止めない。"""
    if not EYECATCH_GITHUB_REPO:
        logger.warning("[OBSERVED UPLOAD SKIP] GITHUB_REPOSITORY が未設定です。")
        return None
    dest_path = f"{OBSERVED_HISTORY_GITHUB_DIR}/{dest_filename}"
    api_url = f"https://api.github.com/repos/{EYECATCH_GITHUB_REPO}/contents/{dest_path}"
    try:
        with open(local_path, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode("utf-8")
        headers = {"Authorization": f"Bearer {GH_PAT}", "Accept": "application/vnd.github+json"}
        current = requests.get(api_url, headers=headers, params={"ref": EYECATCH_GITHUB_BRANCH}, timeout=15)
        payload = {"message": f"chore: save observed history {dest_filename}", "content": content_b64,
                   "branch": EYECATCH_GITHUB_BRANCH}
        if current.status_code == 200:
            payload["sha"] = current.json().get("sha")
        put_res = requests.put(api_url, headers=headers, json=payload, timeout=30)
        if put_res.status_code not in (200, 201):
            logger.error("[OBSERVED UPLOAD FAILED] %s: %s", dest_filename, put_res.text[:300])
            send_telegram_alert(f"⚠️ Observed履歴のGitHub保存に失敗しました: {dest_filename}")
            return None
        return f"https://raw.githubusercontent.com/{EYECATCH_GITHUB_REPO}/{EYECATCH_GITHUB_BRANCH}/{dest_path}"
    except Exception as exc:
        logger.error("[OBSERVED UPLOAD EXCEPTION] %s", exc)
        send_telegram_alert(f"⚠️ Observed履歴のGitHub保存で例外が発生しました: {dest_filename}")
        return None


def save_observed_history(items: list[dict], batch_calls: int, recovery_calls: int,
                          calibration_calls: int = 0, total_collected: int | None = None) -> str | None:
    if not ENABLE_OBSERVED_HISTORY:
        return None
    os.makedirs(OBSERVED_HISTORY_DIR, exist_ok=True)
    path = os.path.join(OBSERVED_HISTORY_DIR, f"screening_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
    observed_items = [{"id": item.get("screening_id"), "source": item["repo"].get("source"),
                       "name": item["repo"].get("nameWithOwner"), "url": item["repo"].get("url"),
                       "published_at": item["repo"].get("publishedAt"), "engagement": item["repo"].get("stargazerCount", 0),
                       "raw_screening_score": item.get("raw_score"), "final_screening_score": item.get("final_score"),
                       "screening_reason": item.get("reason"), "calibrated": item.get("calibrated", False),
                       "screening_status": item.get("screening_status"), "error_category": item.get("error_category"),
                       "stocked": (item.get("score") or 0) >= NOTION_SAVE_THRESHOLD_SCORE} for item in items]
    payload = {"run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
               "analyzed_at": datetime.now(timezone.utc).isoformat(), "total_collected": total_collected,
               "total_screened": len(items), "stock_threshold": NOTION_SAVE_THRESHOLD_SCORE,
               "batch_calls": batch_calls, "recovery_calls": recovery_calls, "calibration_calls": calibration_calls,
               "items": observed_items}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    upload_observed_history_to_github(path, os.path.basename(path))
    return path



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
    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID):
        logger.warning("Notion未設定のため滞留検知をスキップします。")
        return

    url = _notion_query_url()
    headers = _notion_headers()
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
def run_regen_test_mode():
    """
    既存Deep DiveのA/B比較専用ランナー。
    Notionは読み取りのみ。Screening・Stock・dedupe・monthly digest・stale alertを通さない。
    GeminiのDeep Dive/Quality Retry予算だけを通常どおり消費する。
    """
    logger.warning("==========================================")
    logger.warning(" REGEN TEST MODE: 既存Deep Dive再生成（READ ONLY）")
    logger.warning(" Notion/GitHubへの書き込みは行いません")
    logger.warning("==========================================")

    items = get_regen_test_items(REGEN_TEST_LIMIT, REGEN_TEST_SOURCE)
    if items is None:
        logger.error("[REGEN TEST ABORTED] 既存記事の読み出しに失敗しました。")
        logger.info(GEMINI_BUDGET.summary())
        logger.info(DEEP_DIVE_MODEL_BUDGET.summary())
        return
    if not items:
        logger.info("[REGEN TEST] 条件に一致する既存Deep Diveがありません。")
        logger.info(GEMINI_BUDGET.summary())
        logger.info(DEEP_DIVE_MODEL_BUDGET.summary())
        return

    accepted = 0
    rejected = 0
    generated = 0
    for idx, item in enumerate(items, start=1):
        if not GEMINI_BUDGET.can_request():
            logger.warning("[REGEN TEST STOP] Gemini local budget残量なし")
            break
        repo = item["repo"]
        name = repo.get("nameWithOwner")
        logger.info(f"[REGEN TEST {idx}/{len(items)}] {repo.get('source')} / {name}")
        is_safe, license_status = legal_safety_gate(repo)
        if not is_safe:
            logger.warning(f"[REGEN TEST SKIP: LICENSE] {name} -> {license_status}")
            continue
        try:
            regen_result = generate_intelligence_report(
                repo,
                notion_page_id=item.get("notion_page_id"),
                screening_score=item.get("screening_score"),
                screening_reason=item.get("screening_reason", ""),
                persist_results=False,
            )
        except DailyQuotaExhaustedError:
            logger.error("[REGEN TEST STOP] Gemini日次クォータ到達")
            break
        if not regen_result:
            continue
        if isinstance(regen_result, tuple):
            manuscript, regen_status = regen_result
        else:
            manuscript, regen_status = regen_result, "accepted"
        generated += 1
        if regen_status == "accepted":
            accepted += 1
        else:
            rejected += 1
        # GitHub Actionsでも成果物を即確認できるよう、全文をログにも出す。
        logger.info("\n" + "=" * 70)
        logger.info(f"[REGEN TEST ARTICLE START] {name}")
        logger.info("=" * 70 + "\n" + manuscript + "\n" + "=" * 70)
        logger.info(f"[REGEN TEST ARTICLE END] {name}")
        logger.info("=" * 70)

    logger.info(
        f"[REGEN TEST COMPLETE] ACCEPTED {accepted} / REJECTED {rejected} / "
        f"GENERATED {generated} / TOTAL {len(items)}"
    )
    logger.info(f"[REGEN TEST OUTPUT] {REGEN_TEST_OUTPUT_DIR}/")
    logger.info(GEMINI_BUDGET.summary())
    logger.info(DEEP_DIVE_MODEL_BUDGET.summary())
    logger.info(PERSISTENT_GEMINI_COUNTER.summary())


# ==========================================
def sync_public_approved_to_member_db() -> None:
    """Copy/update only human-approved internal records into the member DB.

    The member DB must contain the same named public properties (except that
    internal-only fields may be omitted).  The source page URL is stored in
    ``Internal Source URL`` when that property exists; matching is performed
    against the member DB's ``URL`` property, so the operation is idempotent.
    """
    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID) or not (NOTION_PUBLIC_DATA_SOURCE_ID or NOTION_PUBLIC_DATABASE_ID):
        raise ValueError("PUBLIC_DB_SYNC_MODEには NOTION_API_KEY / NOTION_DATA_SOURCE_ID（またはDATABASE_ID） / NOTION_PUBLIC_DATA_SOURCE_ID（またはDATABASE_ID）が必要です。")
    headers = _notion_headers()
    source_url = _notion_query_url()
    payload = {"filter": {"property": PROP_REVIEW_STATUS, "status": {"equals": REVIEW_STATUS_PUBLIC_APPROVED}}, "page_size": 100}
    approved = []
    while True:
        res = requests.post(source_url, json=payload, headers=headers, timeout=20)
        res.raise_for_status(); body = res.json(); approved.extend(body.get("results", []))
        if not body.get("has_more"): break
        payload["start_cursor"] = body.get("next_cursor")
    # Read the destination schema.  This deliberately lets the member DB grow
    # gradually: only properties that actually exist there are sent to Notion.
    schema_res = requests.get(_notion_schema_url(NOTION_PUBLIC_DATA_SOURCE_ID, NOTION_PUBLIC_DATABASE_ID), headers=headers, timeout=20)
    schema_res.raise_for_status()
    destination_properties = set(schema_res.json().get("properties", {}).keys())
    public_names = {PROP_NAME, PROP_URL, PROP_SOURCE, PROP_SCORE, PROP_DECISION, PROP_DECISION_REASON, PROP_WHAT, PROP_WHY_IMPORTANT, PROP_WHY_NOT_IMPORTANT, PROP_ACTION, PROP_PARADIGM_SHIFT, PROP_ALTERNATIVE_COMPARISON, PROP_MIGRATION_COST, PROP_WHO_SHOULD_USE, PROP_WHO_SHOULD_NOT_USE, PROP_FUTURE_SCENARIO, PROP_EVIDENCE_URLS, PROP_GROUNDING_STATUS, PROP_PUBLISHED_AT} & destination_properties
    if PROP_URL not in destination_properties:
        raise ValueError("会員公開DBにはURL（URL型）列が必要です。")
    for page in approved:
        props = page.get("properties", {}); record_url = props.get(PROP_URL, {}).get("url")
        if not record_url:
            logger.warning("[PUBLIC SYNC SKIP] URLなし: %s", page.get("id")); continue
        query = {"filter": {"property": PROP_URL, "url": {"equals": record_url}}, "page_size": 1}
        found = requests.post(_notion_query_url(NOTION_PUBLIC_DATA_SOURCE_ID, NOTION_PUBLIC_DATABASE_ID), json=query, headers=headers, timeout=20)
        found.raise_for_status(); existing = found.json().get("results", [])
        copied = {k: v for k, v in props.items() if k in public_names}
        if existing:
            response = requests.patch(f"https://api.notion.com/v1/pages/{existing[0]['id']}", json={"properties": copied}, headers=headers, timeout=20)
            action = "UPDATED"
        else:
            response = requests.post("https://api.notion.com/v1/pages", json={"parent": _notion_parent(NOTION_PUBLIC_DATA_SOURCE_ID, NOTION_PUBLIC_DATABASE_ID), "properties": copied}, headers=headers, timeout=20)
            action = "CREATED"
        response.raise_for_status(); logger.info("[PUBLIC SYNC %s] %s", action, record_url)

def main():
    if PUBLIC_DB_SYNC_MODE:
        sync_public_approved_to_member_db()
        logger.info("[PUBLIC SYNC COMPLETE] Gemini APIは使用していません。")
        return
    logger.info("==========================================")
    logger.info(" 完全無人インテリジェンス工場 パイプライン起動（Dual-Model Editorial Intelligence版）")
    logger.info("==========================================")
    if SYNTHETIC_REGRESSION_MODE:
        if SYNTHETIC_REGRESSION_TIER not in {"smoke", "core", "full"}:
            raise ValueError("SYNTHETIC_REGRESSION_TIER must be smoke, core, or full")
        from regression_suite import bootstrap, run, ROOT as REGRESSION_ROOT
        fixtures = REGRESSION_ROOT / "regression_suite" / "fixtures"
        if not fixtures.exists():
            bootstrap(fixtures)
        result = run(fixtures, SYNTHETIC_REGRESSION_TIER)
        logger.info("[SYNTHETIC REGRESSION] %s", json.dumps({
            "tier": result["tier"], "total": result["total_cases"], "passed": result["passed"],
            "critical_failures": result["critical_failures"], "production_write_isolation": True,
        }, ensure_ascii=False))
        # No DB, image, upload, or messaging call is reachable in this mode.
        return
    initialize_runtime()
    if REGEN_TEST_MODE:
        run_regen_test_mode()
        return
    retry_generated = 0
    pending_items = get_pending_retry_items(limit=TOP_N_FOR_DEEP_DIVE)
    if pending_items is None:
        logger.error("[PENDING RETRY] Notion読み出し失敗のため、重複防止を優先して本日停止")
        return
    for item in pending_items:
        logger.info("[PENDING RETRY] %s", item["repo"].get("nameWithOwner"))
        try:
            if generate_intelligence_report(item["repo"], item.get("notion_page_id"), item.get("screening_score"), item.get("screening_reason", "")):
                retry_generated += 1
        except DailyQuotaExhaustedError:
            logger.warning("[PENDING RETRY STOP] Gemini日次クォータ到達")
            return
    check_stale_content()

    github_items = fetch_github_trending()
    hackernews_items = fetch_hackernews_top()
    arxiv_items = fetch_arxiv_ai_ml()
    producthunt_items = fetch_producthunt_trending()
    source_groups = {
        "GitHub": github_items, "HackerNews": hackernews_items,
        "ArXiv": arxiv_items, "ProductHunt": producthunt_items,
    }
    repos = round_robin_candidates(source_groups, MAX_SCREENING_CANDIDATES)
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
        logger.info(DEEP_DIVE_MODEL_BUDGET.summary())
        return

    deduped_repos = []
    local_keys = set()
    for repo in safe_repos:
        parsed_url = urlparse(repo.get("url") or "")
        filtered_query = [(k, v) for k, v in parse_qsl(parsed_url.query, keep_blank_values=True)
                          if not k.lower().startswith(("utm_", "ref", "source", "fbclid", "gclid"))]
        repo_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path.rstrip("/"), "",
                               urlencode(filtered_query, doseq=True), ""))
        title_key = _normalize_title_for_match(repo.get("nameWithOwner", ""))
        identity_key = repo_url or f"{repo.get('source', '')}:{title_key}"
        if repo_url in existing_urls or identity_key in local_keys:
            logger.info(f" [SKIP: DUPLICATE] {repo.get('nameWithOwner')}")
            continue
        local_keys.add(identity_key)
        deduped_repos.append(repo)
    if not deduped_repos:
        logger.info("本日は新規候補が0件でした。")
        logger.info(GEMINI_BUDGET.summary())
        logger.info(DEEP_DIVE_MODEL_BUDGET.summary())
        return

    if len(deduped_repos) > MAX_SCREENING_CANDIDATES:
        logger.warning(
            f"[SCREENING CAP] {len(deduped_repos)}件→公平抽出{MAX_SCREENING_CANDIDATES}件。"
            "無料枠保護のため残りは今回未審査。"
        )
        deduped_repos = round_robin_candidates(
            {source: [r for r in deduped_repos if r.get("source") == source] for source in source_groups},
            MAX_SCREENING_CANDIDATES,
        )

    logger.info(f">>> 軽量スクリーニング開始（最大 {len(deduped_repos)} 件）")
    screening_candidates = [
        {"screening_id": f"B{idx:04d}", "repo": repo}
        for idx, repo in enumerate(deduped_repos, start=1)
    ]
    screened = []
    screening_calls = 0
    calibration_calls = 0
    daily_quota_stop = False
    try:
        screened, screening_calls = screen_candidates_in_batches(screening_candidates)
        screened, calibration_calls = calibrate_candidates(screened)
        if ENABLE_OBSERVED_HISTORY:
            observed_path = save_observed_history(
                screened, screening_calls,
                max(0, screening_calls - ((len(screening_candidates) + SCREENING_BATCH_SIZE - 1) // SCREENING_BATCH_SIZE)),
                calibration_calls=calibration_calls, total_collected=len(repos),
            )
            logger.info("[OBSERVED] saved=%s path=%s", len(screened), observed_path)
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

    logger.info(f"[STOCK] final_score>={NOTION_SAVE_THRESHOLD_SCORE} = {stocked_count}")
    logger.info(f">>> Screening {len(screened)}件 / Stock {stocked_count}件")

    if daily_quota_stop:
        logger.info(GEMINI_BUDGET.summary())
        logger.info(DEEP_DIVE_MODEL_BUDGET.summary())
        generate_monthly_digest()
        return

    # TOP_Nは『候補数』ではなく『最大成功記事数』。失敗時は4位・5位へBackfillする。
    generated_count = retry_generated
    attempted = 0
    # Backfillは「記事候補の質」を下げない。Stock基準未満をAPIで無理に記事化しない。
    candidates = [x for x in screened if x.get("score", 0) >= NOTION_SAVE_THRESHOLD_SCORE]
    if len(candidates) < TOP_N_FOR_DEEP_DIVE:
        logger.info(
            f"[DEEP DIVE POOL] Stock基準{NOTION_SAVE_THRESHOLD_SCORE}点以上は{len(candidates)}件。"
            "低スコア候補で本数を水増しせず、この範囲だけで記事生成します。"
        )
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
            f"✅ 【AI note事業】Collected {len(repos)} / Screened {len(screened)}件、"
            f"Screening API Calls {screening_calls}、Calibration {calibration_calls}回、Stock {stocked_count}件、"
            f"Deep Dive Ready {generated_count}件（試行{attempted}件）。\n"
            f"{GEMINI_BUDGET.summary()}\n{PERSISTENT_GEMINI_COUNTER.summary()}\nhttps://notion.so/{NOTION_DATABASE_ID}"
        )
        send_telegram_alert(msg)
        logger.info(msg)
    else:
        logger.info("本日は生成条件を満たす記事・Stockがありませんでした。")

    generate_monthly_digest()
    logger.info(GEMINI_BUDGET.summary())
    logger.info(DEEP_DIVE_MODEL_BUDGET.summary())
    logger.info(PERSISTENT_GEMINI_COUNTER.summary())


if __name__ == "__main__":
    main()
