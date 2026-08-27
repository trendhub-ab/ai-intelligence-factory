import os
import sys
import json
import atexit
import unicodedata
from collections import Counter

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
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
# Synthetic regression is intentionally provider-free. On an offline CI/dev machine the
# regression re-imports pipeline.py as a module, so allow a minimal SDK stub only in that mode.
# Production still fails loudly if google-genai is missing.
if os.environ.get("SYNTHETIC_REGRESSION_MODE", "false").lower() in {"1", "true", "yes", "on"}:
    try:
        from google import genai
        from google.genai.errors import APIError
    except ImportError:
        import types as _types
        _google = sys.modules.get("google") or _types.ModuleType("google")
        _google.__path__ = getattr(_google, "__path__", [])
        _genai = _types.ModuleType("google.genai")
        _errors = _types.ModuleType("google.genai.errors")
        class _SyntheticClient:
            def __init__(self, *args, **kwargs):
                self.chats = _types.SimpleNamespace(create=lambda **_kwargs: None)
        class APIError(Exception):
            pass
        _genai.Client = _SyntheticClient
        _errors.APIError = APIError
        _google.genai = _genai
        sys.modules["google"] = _google
        sys.modules["google.genai"] = _genai
        sys.modules["google.genai.errors"] = _errors
        genai = _genai
else:
    from google import genai
    from google.genai.errors import APIError
import decision_intelligence as decision_intelligence
import evidence_ledger
from evidence_authority import classify_evidence, authority_rank

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

# ---- Free Article -> Subscription Attribution ----
# 無料noteは集客チャネル、有料商品は「会員向け意思決定DB + 月次サマリー」。
# 記事単体課金の売上を追わず、無料記事ごとに安定article_idとCTA tracking URLを付与し、
# 後からサブスク転換実績を紐付けられる土台だけを持つ。実績がない段階では
# Commercial/Source ROIへ自動学習させず、推定と実績を混ぜない。
ENABLE_SUBSCRIPTION_ATTRIBUTION = os.environ.get("ENABLE_SUBSCRIPTION_ATTRIBUTION", "true").lower() in {"1", "true", "yes", "on"}
SUBSCRIPTION_LANDING_URL = os.environ.get("SUBSCRIPTION_LANDING_URL", "").strip()
SUBSCRIPTION_CAMPAIGN_ID = os.environ.get("SUBSCRIPTION_CAMPAIGN_ID", "ai_intelligence_factory_subscription").strip() or "ai_intelligence_factory_subscription"
SUBSCRIPTION_ATTRIBUTION_DIR = os.environ.get("SUBSCRIPTION_ATTRIBUTION_DIR", "subscription_attribution/articles")
SUBSCRIPTION_ATTRIBUTION_GITHUB_DIR = os.environ.get("SUBSCRIPTION_ATTRIBUTION_GITHUB_DIR", "subscription_attribution/articles").strip("/")

# This mode uses only the Notion API.  It never calls Gemini or source APIs.
PUBLIC_DB_SYNC_MODE = os.environ.get("PUBLIC_DB_SYNC_MODE", "false").lower() in {"1", "true", "yes", "on"}

# GitHub / Hacker News / arXiv / Product Hunt は日次観測の同格な必須4 Source。
# Product Huntだけ認証Tokenが必要なため、欠落はproduction preflightでGemini消費前に検出する。
# これはtransport上の要件であり、Source ROI・優先順位・最低枠・最大枠で特別扱いしない。
PRODUCTHUNT_DEVELOPER_TOKEN = os.environ.get("PRODUCTHUNT_DEVELOPER_TOKEN")
PRODUCTHUNT_LOOKBACK_HOURS = max(24, int(os.environ.get("PRODUCTHUNT_LOOKBACK_HOURS", "72")))

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
                       request_kind: str = "other", reserve: int = 0,
                       request_context: str = "", count_as_deep_dive: bool = False,
                       request_origin: str = "new"):
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
    audit_id = _consume_gemini_request(
        request_kind, reserve=reserve, model_name=model_name, request_context=request_context,
        count_as_deep_dive=count_as_deep_dive, request_origin=request_origin,
    )
    try:
        chat = client.chats.create(model=model_name, config=config) if config else client.chats.create(model=model_name)
        response = chat.send_message(prompt)
    except Exception as exc:
        GEMINI_USAGE_AUDIT.record_outcome(audit_id, "error", exc)
        raise
    GEMINI_USAGE_AUDIT.record_outcome(audit_id, "success")
    GEMINI_USAGE_AUDIT.record_response_usage(audit_id, response)
    return response

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
SCREENING_BATCH_MAX_OUTPUT_TOKENS = int(os.environ.get("SCREENING_BATCH_MAX_OUTPUT_TOKENS", "5000"))
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

# ---- 収益最適化スコア（品質スコアから完全分離） ----
# Decision Scoreは情報品質・意思決定価値の基準として従来どおりStock閾値/Gateに使用する。
# Commercial Value Scoreは「読者獲得・会員DB転換に寄与しそうか」の推定値であり、
# 低品質候補を押し上げないようDeep Dive候補の順位付けにのみ使用する。
ENABLE_PROFIT_PRIORITY = os.environ.get("ENABLE_PROFIT_PRIORITY", "true").lower() in {"1", "true", "yes", "on"}
DEEP_DIVE_DECISION_WEIGHT = float(os.environ.get("DEEP_DIVE_DECISION_WEIGHT", "0.65"))
DEEP_DIVE_COMMERCIAL_WEIGHT = float(os.environ.get("DEEP_DIVE_COMMERCIAL_WEIGHT", "0.35"))
EVERGREEN_PORTFOLIO_MIN = int(os.environ.get("EVERGREEN_PORTFOLIO_MIN", "1"))
EVERGREEN_PRIORITY_TOLERANCE = float(os.environ.get("EVERGREEN_PRIORITY_TOLERANCE", "8"))
# Content Portfolio Balance: 収益性が僅差ならTOP3が単一テーマへ偏りすぎないようにする。
# 品質・収益Priority差が大きい候補を無理に押し上げず、TOP3内で最低2テーマを目安にする。
ENABLE_PORTFOLIO_BALANCE = os.environ.get("ENABLE_PORTFOLIO_BALANCE", "true").lower() in {"1", "true", "yes", "on"}
PORTFOLIO_MIN_DISTINCT_TOPICS = int(os.environ.get("PORTFOLIO_MIN_DISTINCT_TOPICS", "2"))
PORTFOLIO_TOPIC_PRIORITY_TOLERANCE = float(os.environ.get("PORTFOLIO_TOPIC_PRIORITY_TOLERANCE", "6"))
# Free Article Delivery Reliability: TOP_Nのうち最低1枠を「一次情報が明確で
# 公開まで到達しやすい候補」に寄せる。品質閾値は下げず、Stock済み候補の順序だけを調整する。
ENABLE_PUBLICATION_RELIABILITY_SLOT = os.environ.get("ENABLE_PUBLICATION_RELIABILITY_SLOT", "true").lower() in {"1", "true", "yes", "on"}
PUBLICATION_RELIABILITY_SLOTS = max(0, int(os.environ.get("PUBLICATION_RELIABILITY_SLOTS", "1")))
PUBLICATION_RELIABILITY_MIN_DECISION_SCORE = max(0, min(100, int(os.environ.get("PUBLICATION_RELIABILITY_MIN_DECISION_SCORE", "65"))))
PUBLICATION_RELIABILITY_MIN_ADVANTAGE = float(os.environ.get("PUBLICATION_RELIABILITY_MIN_ADVANTAGE", "8"))
ENABLE_DETERMINISTIC_PUBLICATION_RESCUE = os.environ.get("ENABLE_DETERMINISTIC_PUBLICATION_RESCUE", "true").lower() in {"1", "true", "yes", "on"}
PORTFOLIO_TOPICS = (
    "MODEL", "AGENT", "DEVTOOLS", "INFRA", "DATA",
    "SECURITY", "MULTIMODAL", "PRODUCT", "OTHER",
)
PROFIT_SCORE_NEUTRAL = 50
GITHUB_FETCH_LIMIT = int(os.environ.get("GITHUB_FETCH_LIMIT", "50"))
HN_FETCH_LIMIT = int(os.environ.get("HN_FETCH_LIMIT", "50"))
ARXIV_FETCH_LIMIT = int(os.environ.get("ARXIV_FETCH_LIMIT", "50"))
PRODUCTHUNT_FETCH_LIMIT = int(os.environ.get("PRODUCTHUNT_FETCH_LIMIT", "50"))

# ---- Source ROI Learning（必須Sourceを維持した動的配分） ----
# 各Sourceは最低枠を保証し、過去RunのScreened→Stock→Ready歩留まりと
# Deep Dive生成効率が十分に蓄積した場合だけ残り枠を動的配分する。
# 冷開始・データ不足・状態ファイル破損時は従来の50件/SourceへFail-Safeする。
ENABLE_SOURCE_ROI_LEARNING = os.environ.get("ENABLE_SOURCE_ROI_LEARNING", "true").lower() in {"1", "true", "yes", "on"}
SOURCE_ROI_SOURCES = ("GitHub", "HackerNews", "ArXiv", "ProductHunt")
SOURCE_ROI_STATE_PATH = os.environ.get("SOURCE_ROI_STATE_PATH", "source_roi_history/source_roi_state.json")
SOURCE_ROI_GITHUB_DIR = os.environ.get("SOURCE_ROI_GITHUB_DIR", "source_roi_history").strip("/")
SOURCE_ROI_HISTORY_RUNS = int(os.environ.get("SOURCE_ROI_HISTORY_RUNS", "30"))
SOURCE_ROI_RECENCY_DECAY = float(os.environ.get("SOURCE_ROI_RECENCY_DECAY", "0.93"))
SOURCE_ROI_MIN_SCREENED = int(os.environ.get("SOURCE_ROI_MIN_SCREENED", "50"))
SOURCE_ROI_MIN_DEEP_DIVE_ATTEMPTS = int(os.environ.get("SOURCE_ROI_MIN_DEEP_DIVE_ATTEMPTS", "2"))
SOURCE_ROI_MIN_MATURE_SOURCES = int(os.environ.get("SOURCE_ROI_MIN_MATURE_SOURCES", "2"))
SOURCE_ROI_MIN_FETCH_PER_SOURCE = int(os.environ.get("SOURCE_ROI_MIN_FETCH_PER_SOURCE", "25"))
SOURCE_ROI_EXPLORATION_WEIGHT = float(os.environ.get("SOURCE_ROI_EXPLORATION_WEIGHT", "0.15"))
SOURCE_ROI_STOCK_WEIGHT = float(os.environ.get("SOURCE_ROI_STOCK_WEIGHT", "0.35"))
SOURCE_ROI_READY_WEIGHT = float(os.environ.get("SOURCE_ROI_READY_WEIGHT", "0.45"))
SOURCE_ROI_EFFICIENCY_WEIGHT = float(os.environ.get("SOURCE_ROI_EFFICIENCY_WEIGHT", "0.20"))
# Source ROI上は4 Sourceを完全に同格として扱う。必須性・floor・cap・ROI式に
# Source固有の優先度を持ち込まない。APIごとの取得実装差はtransport layerの責務。
SOURCE_ROI_MAX_FETCH_PER_SOURCE = int(os.environ.get("SOURCE_ROI_MAX_FETCH_PER_SOURCE", "75"))
SOURCE_ROI_MAX_FETCH_BY_SOURCE = {
    src: SOURCE_ROI_MAX_FETCH_PER_SOURCE for src in SOURCE_ROI_SOURCES
}

# ---- Revenue Product Phase 2 ----
ENABLE_REVENUE_PRODUCT_PHASE2 = os.environ.get("ENABLE_REVENUE_PRODUCT_PHASE2", "true").lower() in {"1", "true", "yes", "on"}
# Run109: manual subscriber-inventory bootstrap. This is intentionally not scheduled by Daily.
INVENTORY_BOOTSTRAP_ACTIVE = os.environ.get("INVENTORY_BOOTSTRAP_ACTIVE", "false").lower() in {"1", "true", "yes", "on"}
INVENTORY_BOOTSTRAP_ENTITY_IDS = tuple(
    x.strip() for x in os.environ.get("INVENTORY_BOOTSTRAP_ENTITY_IDS", "").split(",") if x.strip()
)
TRACKING_ELIGIBILITY_MIN_SCORE = max(0, min(100, int(os.environ.get("TRACKING_ELIGIBILITY_MIN_SCORE", "55"))))
TRACKING_REVIEW_DAYS = max(1, int(os.environ.get("TRACKING_REVIEW_DAYS", "14")))
PRODUCT_REVIEW_MAX_PER_RUN = max(0, int(os.environ.get("PRODUCT_REVIEW_MAX_PER_RUN", "2")))
LEGACY_BOOTSTRAP_MAX_PER_RUN = max(0, int(os.environ.get("LEGACY_BOOTSTRAP_MAX_PER_RUN", "1")))
# Run113: manual Bootstrap may inspect more candidates with 0 Gemini so that Evidence-unresolvable
# rows do not consume the paid-review slots. Normal Daily still selects only PRODUCT_REVIEW_MAX_PER_RUN.
PRODUCT_REVIEW_PREFLIGHT_SCAN_LIMIT = max(
    PRODUCT_REVIEW_MAX_PER_RUN,
    int(os.environ.get("PRODUCT_REVIEW_PREFLIGHT_SCAN_LIMIT", str(max(8, PRODUCT_REVIEW_MAX_PER_RUN * 4)))),
)
GEMINI_PRODUCT_REVIEW_PER_RUN_REQUEST_BUDGET = max(0, int(os.environ.get("GEMINI_PRODUCT_REVIEW_PER_RUN_REQUEST_BUDGET", "3")))
DEFERRED_DEEP_DIVE_MAX_PER_RUN = max(0, int(os.environ.get("DEFERRED_DEEP_DIVE_MAX_PER_RUN", "1")))
DEFERRED_DEEP_DIVE_MAX_QUEUE = max(1, int(os.environ.get("DEFERRED_DEEP_DIVE_MAX_QUEUE", "20")))
DEFERRED_DEEP_DIVE_STATE_PATH = os.environ.get("DEFERRED_DEEP_DIVE_STATE_PATH", "deferred_deep_dive/deferred_queue.json")
DEFERRED_DEEP_DIVE_GITHUB_DIR = os.environ.get("DEFERRED_DEEP_DIVE_GITHUB_DIR", "deferred_deep_dive").strip("/")
DEFERRED_FLASH_TTL_DAYS = max(1, int(os.environ.get("DEFERRED_FLASH_TTL_DAYS", "2")))
DEFERRED_TREND_TTL_DAYS = max(1, int(os.environ.get("DEFERRED_TREND_TTL_DAYS", "14")))
DEFERRED_EVERGREEN_TTL_DAYS = max(1, int(os.environ.get("DEFERRED_EVERGREEN_TTL_DAYS", "60")))

# ---- Gemini無料枠のローカル安全予算 ----
# Google側のFree Tier上限そのものではなく、このpipeline 1実行内で絶対に超えない
# 独自Safety Cap。実際のRPM/RPD/TPMはAI Studioのcurrent limitsを運用者が確認し、
# 必要に応じて環境変数でさらに低く設定する。
GEMINI_DAILY_REQUEST_BUDGET = int(os.environ.get("GEMINI_DAILY_REQUEST_BUDGET", "50"))
GEMINI_SCREENING_RETRY_BUDGET = int(os.environ.get("GEMINI_SCREENING_RETRY_BUDGET", "4"))
GEMINI_DEEP_DIVE_RETRY_BUDGET = int(os.environ.get("GEMINI_DEEP_DIVE_RETRY_BUDGET", "1"))
GEMINI_RESERVED_DEEP_DIVE_REQUESTS = int(os.environ.get("GEMINI_RESERVED_DEEP_DIVE_REQUESTS", "3"))
# Deep Diveは無料記事＋最小限の記事管理データだけを返す。Product Reviewは別callへ分離済み。
# 旧版との互換と長文Evidence記事の余白のため9,000 tokens上限は維持するが、
# Prompt負荷を減らして途中切れ・管理項目由来のHallucinationを抑える。
GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS = int(os.environ.get("GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS", "9000"))
GEMINI_DEEP_DIVE_DAILY_REQUEST_BUDGET = int(os.environ.get("GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET", os.environ.get("GEMINI_DEEP_DIVE_DAILY_REQUEST_BUDGET", "12")))
GEMINI_PENDING_RETRY_REQUEST_BUDGET = max(0, int(os.environ.get("GEMINI_PENDING_RETRY_REQUEST_BUDGET", "2")))
# 複数GitHub Actions Runをまたいで共有する永続Safety Cap。Googleの公式quota値ではなく、
# このプロジェクト独自の保守的な上限。RPDのリセット境界に合わせてAmerica/Los_Angeles日付で管理する。
GEMINI_PERSISTENT_DAILY_COUNTER = os.environ.get("GEMINI_PERSISTENT_DAILY_COUNTER", "true").lower() in {"1", "true", "yes", "on"}
GEMINI_PERSISTENT_DAILY_REQUEST_BUDGET = int(os.environ.get("GEMINI_PERSISTENT_DAILY_REQUEST_BUDGET", "18"))
GEMINI_PERSISTENT_COUNTER_PATH = os.environ.get("GEMINI_PERSISTENT_COUNTER_PATH", ".runtime/gemini_daily_usage.json")
GEMINI_COUNTER_BRANCH = os.environ.get("GEMINI_COUNTER_BRANCH", "").strip()
# Gemini provider側のRPD/RPM等はGoogle Cloud / AI Studio Project単位だが、
# このPersistent Counter自体は「このGitHub repositoryが送った試行」しか観測できない。
# したがってCounter identityは、API keyやProject IDではなくrepository単位の安定scopeに固定する。
# Project IDは任意の監査メタデータとして受け取り、未設定でもDailyを停止しない。
GEMINI_QUOTA_PROJECT_ID = (
    os.environ.get("GEMINI_QUOTA_PROJECT_ID")
    or os.environ.get("GOOGLE_CLOUD_PROJECT")
    or ""
).strip()
GEMINI_QUOTA_FALLBACK_ID = (
    os.environ.get("GEMINI_QUOTA_FALLBACK_ID")
    or os.environ.get("GITHUB_REPOSITORY")
    or ""
).strip()
GEMINI_COUNTER_SCOPE_ID = (
    os.environ.get("GEMINI_COUNTER_SCOPE_ID")
    or GEMINI_QUOTA_FALLBACK_ID
    or GEMINI_QUOTA_PROJECT_ID
    or ""
).strip()
MODEL_DAILY_BUDGETS = {
    "gemini-3.5-flash-lite": int(os.environ.get("GEMINI_35_FLASH_LITE_DAILY_BUDGET", "450")),
    "gemini-3.1-flash-lite": int(os.environ.get("GEMINI_31_FLASH_LITE_DAILY_BUDGET", "450")),
    "gemini-3.6-flash": int(os.environ.get("GEMINI_36_FLASH_DAILY_BUDGET", "18")),
    "gemini-3.7-flash": int(os.environ.get("GEMINI_37_FLASH_DAILY_BUDGET", "18")),
    "gemini-3.5-flash": int(os.environ.get("GEMINI_35_FLASH_DAILY_BUDGET", "18")),
}
GEMINI_QUOTA_TIMEZONE = os.environ.get("GEMINI_QUOTA_TIMEZONE", "America/Los_Angeles")
# 3本成功を目標にしつつ、途中切れ・一次情報不足・品質Gate不合格後の
# Backfill余地を確保する。TOP_N自体は3のまま増やさない。
MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS = int(os.environ.get("MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS", "7"))

# ---- 既存記事A/B比較用・再生成テストモード ----
# 通常運用では必ずFalse。TrueのときはNotion DB内の既存Deep Diveを読み出し、
# Screening / dedupe / Stock保存を通さず、現在のDeep Dive prompt + Quality Gateだけで
# 再生成する。Notionページの更新・新規作成、GitHubへのアイキャッチuploadは一切行わない。
# 生成稿はローカルのREGEN_TEST_OUTPUT_DIRへ保存するため、旧稿と安全に比較できる。
REGEN_TEST_MODE = os.environ.get("REGEN_TEST_MODE", "false").lower() in {"1", "true", "yes", "on"}
REGEN_TEST_LIMIT = int(os.environ.get("REGEN_TEST_LIMIT", "3"))
REGEN_TEST_SOURCE = os.environ.get("REGEN_TEST_SOURCE", "").strip()
REGEN_TEST_OUTPUT_DIR = os.environ.get("REGEN_TEST_OUTPUT_DIR", "regen_test_outputs")
# Run130: Real Article Regression can keep the historical fixed/A-B set or collect
# genuinely new candidates without adding Gemini screening calls.  "fixed" preserves
# the previous behavior exactly.  "fresh" performs source-native collection + legal/dedupe
# checks + deterministic 0-API metadata ranking, then sends only the selected articles to
# the existing Deep Dive/Quality pipeline with persist_results=False.
REGEN_TEST_ARTICLE_SET = os.environ.get("REGEN_TEST_ARTICLE_SET", "fixed").strip().lower()
REGEN_FRESH_FETCH_PER_SOURCE = int(os.environ.get("REGEN_FRESH_FETCH_PER_SOURCE", "12"))

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
# Evidence補強はGeminiを使わないが、無制限の外部取得は行わない。文字数は判定基準ではなく、
# 取得・保持量の安全弁としてのみ使う。
MAX_EVIDENCE_SUPPLEMENT_ATTEMPTS = int(os.environ.get("MAX_EVIDENCE_SUPPLEMENT_ATTEMPTS", "2"))
MAX_EVIDENCE_DOCUMENTS = int(os.environ.get("MAX_EVIDENCE_DOCUMENTS", "3"))
MAX_EVIDENCE_TOTAL_CHARS = int(os.environ.get("MAX_EVIDENCE_TOTAL_CHARS", str(SOURCE_CONTEXT_MAX_CHARS)))
# Gemini prompt用contextとは別に、Fact/Evidence Gateだけが参照する広い一次資料本文を保持する。
# PDF/HTMLを12k文字へ切った後にFact照合すると、実在する数値・条件をunsupportedと誤判定するため。
VERIFICATION_CONTEXT_MAX_CHARS = int(os.environ.get("VERIFICATION_CONTEXT_MAX_CHARS", "180000"))
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
# Quality Gate PASS後、Notion保存/アップグレードに失敗した内部状態を示すための値。
# Notion側のContent Status選択肢を書き換えるものではなく、Gate History/Funnel等の
# 内部記録（final_status）でのみ使用する。Readyの定義（Quality Gate PASS AND
# Notion Persistence SUCCESS）を満たさない経路をQuality Failedと混同しないための識別子。
CONTENT_STATUS_PERSISTENCE_FAILED = "Persistence Failed"
ARTICLE_STATUS_NOT_PLANNED = "Not Planned"
ARTICLE_STATUS_READY = "Ready"
ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW = "Needs Editorial Review"
MANUSCRIPT_CAPTION_READY = "AIIF_MANUSCRIPT:READY"
MANUSCRIPT_CAPTION_REVIEW = "AIIF_MANUSCRIPT:NEEDS_EDITORIAL_REVIEW"
VISIBILITY_SUBSCRIBER_ONLY = "Subscriber Only"
VISIBILITY_PAID_ARTICLE = "Paid Article"
VISIBILITY_FREE_ARTICLE = "Free Article"
GROUNDING_METADATA_ONLY = "Metadata Only"
GROUNDING_SOURCE_NATIVE = "Source Native"
GROUNDING_URL_CONTEXT = "URL Context"
GROUNDING_URL_SEARCH = "URL + Search"
GROUNDING_FAILED = "Failed"
ALLOWED_DECISIONS = {"NOW", "TRY", "WATCH", "WAIT", "AVOID"}

# Gate可視化・レビュー用の内部成果物。公開Repositoryへ未公開記事本文を出さないため、
# GitHub Contents APIではなくActions実行環境のprivate artifact領域だけに保存する。
REVIEW_CANDIDATES_DIR = os.environ.get("REVIEW_CANDIDATES_DIR", "review_candidates")
QUALITY_FAILURES_DIR = os.environ.get("QUALITY_FAILURES_DIR", "quality_failures")
GATE_HISTORY_DIR = os.environ.get("GATE_HISTORY_DIR", "gate_history")
REGRESSION_CASES_DIR = os.environ.get("REGRESSION_CASES_DIR", "regression_cases_pending")
ARTICLE_AUDIT_DIR = os.environ.get("ARTICLE_AUDIT_DIR", "article_audit")

# Run121: run-local article style memory. It contains only generated prose fingerprints and
# is reset before each production run; it is never persisted to Notion or used as evidence.
_RUN_ARTICLE_STYLE_MEMORY: list[dict] = []

GATE_STATUS_NOT_RUN = "NOT_RUN"
GATE_STATUS_PASS = "PASS"
GATE_STATUS_FAIL = "FAIL"
GATE_STATUS_WARNING = "WARNING"
GATE_STATUS_REVIEW = "REVIEW"

# Run 102: Gate名・既存statusは互換維持しつつ、公開停止強度を別軸で明示する。
# HARD_BLOCK = 読者信頼/Fact/Evidence/Decision整合を壊すため公開不可。
# REVIEW = 事実安全性ではなく「で、どうするか」という商品価値が欠け、1回の修正価値がある。
# SOFT_QUALITY = 読める記事の美観・引力・文体改善。観測するが原則公開を止めない。
GATE_SEVERITY_HARD = "HARD_BLOCK"
GATE_SEVERITY_REVIEW = "REVIEW"
GATE_SEVERITY_SOFT = "SOFT_QUALITY"
GATE_SEVERITY_OPERATIONAL = "OPERATIONAL"
GATE_DISPOSITION_PASS = "PASS"
GATE_DISPOSITION_PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
GATE_DISPOSITION_REVIEW = "REVIEW"
GATE_DISPOSITION_BLOCK = "BLOCK"

REASON_CODE_MAX_TOKENS = "MAX_TOKENS"
REASON_CODE_STRUCTURE_MISSING = "STRUCTURE_MISSING"
REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT = "PRIMARY_EVIDENCE_INSUFFICIENT"
REASON_CODE_PRIMARY_SOURCE_UNRESOLVED = "PRIMARY_SOURCE_UNRESOLVED"
REASON_CODE_TECHNICAL_CLAIMS_INSUFFICIENT = "TECHNICAL_CLAIMS_INSUFFICIENT"
REASON_CODE_NUMERIC_CONDITIONS_INSUFFICIENT = "NUMERIC_CONDITIONS_INSUFFICIENT"
REASON_CODE_FRESHNESS_REQUIRED_BUT_UNRESOLVED = "FRESHNESS_REQUIRED_BUT_UNRESOLVED"
REASON_CODE_HIGH_RISK_ACTION_UNSUPPORTED = "HIGH_RISK_ACTION_UNSUPPORTED"
REASON_CODE_EVIDENCE_GAP_DISCLOSURE_REQUIRED = "EVIDENCE_GAP_DISCLOSURE_REQUIRED"
REASON_CODE_FACT_UNSUPPORTED_CLAIM = "FACT_UNSUPPORTED_CLAIM"
REASON_CODE_FACT_NUMERICAL_MISMATCH = "FACT_NUMERICAL_MISMATCH"
REASON_CODE_FACT_ACTOR_MISMATCH = "FACT_ACTOR_MISMATCH"
REASON_CODE_FACT_UNSUPPORTED_NAMED_FACT = "FACT_UNSUPPORTED_NAMED_FACT"
REASON_CODE_FACT_CONDITIONALITY_LOSS = "FACT_CONDITIONALITY_LOSS"
REASON_CODE_EDITORIAL_STRUCTURE_ERROR = "EDITORIAL_STRUCTURE_ERROR"
REASON_CODE_PUB_HEADLINE_OVERCLAIM = "PUB_HEADLINE_OVERCLAIM"
REASON_CODE_PUB_INTRO_OVERCLAIM = "PUB_INTRO_OVERCLAIM"
REASON_CODE_PUB_UNSUPPORTED_CONCLUSION = "PUB_UNSUPPORTED_CONCLUSION"
REASON_CODE_PUB_ACTION_EVIDENCE_MISMATCH = "PUB_ACTION_EVIDENCE_MISMATCH"
REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH = "PUB_SCORE_NARRATIVE_MISMATCH"
REASON_CODE_PUB_SOURCE_SUFFICIENCY = "PUB_SOURCE_SUFFICIENCY"
REASON_CODE_PUB_NEGATIVE_EVIDENCE_OMISSION = "PUB_NEGATIVE_EVIDENCE_OMISSION"
REASON_CODE_APPEAL_OVER_HEDGING = "APPEAL_OVER_HEDGING"
REASON_CODE_APPEAL_ACTION_COLLAPSE = "APPEAL_ACTION_COLLAPSE"
REASON_CODE_APPEAL_TITLE_FLATTENING = "APPEAL_TITLE_FLATTENING"
REASON_CODE_APPEAL_DECISION_VOICE_LOSS = "APPEAL_DECISION_VOICE_LOSS"
REASON_CODE_APPEAL_FABRICATED_EXPERIENCE = "APPEAL_FABRICATED_EXPERIENCE"
REASON_CODE_APPEAL_AI_STYLE_COMPOSITE = "APPEAL_AI_STYLE_COMPOSITE"
REASON_CODE_APPEAL_CROSS_ARTICLE_FINGERPRINT = "APPEAL_CROSS_ARTICLE_FINGERPRINT"
REASON_CODE_PENDING_RETRY = "PENDING_RETRY"
REASON_CODE_MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
REASON_CODE_DEEP_DIVE_RUN_BUDGET_EXHAUSTED = "DEEP_DIVE_RUN_BUDGET_EXHAUSTED"
# Quality Gateは通過したが、Notion永続化層（ページ作成/アップグレード）が失敗した場合の理由コード。
# 記事品質の問題ではなく永続保存層の障害であるため、Quality Failedとは明確に区別する。
REASON_CODE_NOTION_PERSISTENCE_FAILED = "NOTION_PERSISTENCE_FAILED"


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
class DeepDiveRunBudgetExceededError(GeminiBudgetExceededError): pass
class PendingRetryBudgetExceededError(GeminiBudgetExceededError): pass
class ProductReviewBudgetExceededError(GeminiBudgetExceededError): pass


class PersistentGeminiDailyCounter:
    """Repository-local safety counter for Gemini requests.

    Google provider quota is Project-wide, but this state file lives inside one GitHub repository
    and cannot observe manual AI Studio calls or another repository.  Therefore the durable identity
    is a stable repository/counter scope, not an API-key hash and not a claimed provider-wide total.

    Legacy same-day ``key_scopes`` and ``project_scopes`` are conservatively merged into the new
    counter scope once.  This intentionally prefers over-counting to under-counting during migration.
    Raw repository / Project IDs are never stored; only a SHA-256 shortened scope is persisted.
    """
    def __init__(self, enabled: bool, model_budgets: int | dict[str, int], default_budget: int | str,
                 path: str | None = None, quota_timezone: str | None = None,
                 quota_project_id: str | None = None, api_key: str | None = None,
                 quota_scope_id: str | None = None):
        # Legacy 4-argument form (enabled, budget, path, timezone) remains supported.
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
        # api_key and quota_project_id remain accepted for backward compatibility / audit metadata,
        # but neither is the durable local-counter identity.
        del api_key
        project_id = (quota_project_id if quota_project_id is not None else GEMINI_QUOTA_PROJECT_ID or "").strip()
        self.provider_project_scope = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:16] if project_id else ""
        scope_id = (quota_scope_id if quota_scope_id is not None else GEMINI_COUNTER_SCOPE_ID or self.repo or project_id).strip()
        self.counter_scope = hashlib.sha256(scope_id.encode("utf-8")).hexdigest()[:16] if scope_id else ""
        # Compatibility alias used by older tests / helper code.
        self.project_scope = self.counter_scope
        self.session_used = 0

    def budget_for(self, model_name: str) -> int:
        return max(0, int(self.model_budgets.get(model_name, self.default_budget)))

    @staticmethod
    def _merge_model_state(target: dict, source: dict) -> None:
        target["used"] = int(target.get("used", 0) or 0) + int(source.get("used", 0) or 0)
        target["exhausted"] = bool(target.get("exhausted", False) or source.get("exhausted", False))
        target_by_kind = target.get("by_kind") if isinstance(target.get("by_kind"), dict) else {}
        source_by_kind = source.get("by_kind") if isinstance(source.get("by_kind"), dict) else {}
        for kind, count in source_by_kind.items():
            target_by_kind[kind] = int(target_by_kind.get(kind, 0) or 0) + int(count or 0)
        target["by_kind"] = target_by_kind
        if source.get("budget") is not None:
            target["budget"] = source.get("budget")

    def _merge_legacy_scopes(self, target: dict, scopes: dict) -> None:
        for legacy_scope in (scopes or {}).values():
            if not isinstance(legacy_scope, dict):
                continue
            for model_name, state in (legacy_scope.get("models") or {}).items():
                if not isinstance(state, dict):
                    continue
                model_target = target["models"].setdefault(
                    model_name, {"used": 0, "by_kind": {}, "exhausted": False}
                )
                self._merge_model_state(model_target, state)

    def _normalized_day(self, data: dict, quota_date: str) -> dict:
        if data.get("quota_date") != quota_date:
            return {"schema_version": 3, "quota_date": quota_date, "counter_scopes": {}}

        normalized = dict(data)
        normalized["schema_version"] = 3
        scopes = normalized.get("counter_scopes")
        if not isinstance(scopes, dict):
            scopes = {}
        normalized["counter_scopes"] = scopes

        # Same-day migration from API-key and Project-keyed state.  Because the state file is
        # repository-local, merging all legacy scopes is the safest migration and cannot hide usage.
        if self.counter_scope:
            target = scopes.setdefault(self.counter_scope, {"models": {}})
            legacy_key_scopes = normalized.get("key_scopes")
            legacy_project_scopes = normalized.get("project_scopes")
            if isinstance(legacy_key_scopes, dict) and legacy_key_scopes:
                self._merge_legacy_scopes(target, legacy_key_scopes)
                normalized["legacy_key_scopes_migrated"] = True
            if isinstance(legacy_project_scopes, dict) and legacy_project_scopes:
                self._merge_legacy_scopes(target, legacy_project_scopes)
                normalized["legacy_project_scopes_migrated"] = True
        normalized.pop("key_scopes", None)
        normalized.pop("project_scopes", None)
        return normalized

    def _scope_state(self, data: dict) -> dict:
        if not self.counter_scope:
            raise GeminiBudgetExceededError(
                "Persistent Gemini counter requires a stable repository/counter scope"
            )
        scopes = data.setdefault("counter_scopes", {})
        return scopes.setdefault(self.counter_scope, {"models": {}})

    def _project_state(self, data: dict) -> dict:
        # Backward-compatible helper name.
        return self._scope_state(data)

    def _model_state(self, data: dict, model_name: str) -> dict:
        scope = self._scope_state(data)
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
            "message": f"chore: reserve Gemini request {data.get('quota_date','')} ({self.counter_scope})",
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
        if not self.counter_scope:
            raise GeminiBudgetExceededError("Persistent Gemini counter has no stable scope")
        quota_date = self._quota_date()
        budget = self.budget_for(model_name)
        for attempt in range(3):
            data, sha = self._read_remote()
            data = self._normalized_day(data, quota_date)
            state = self._model_state(data, model_name)
            used = int(state.get("used", 0) or 0)
            exhausted = bool(state.get("exhausted", False))
            if exhausted or used + 1 + max(0, reserve) > budget:
                raise GeminiBudgetExceededError(
                    f"Persistent Gemini model budget exhausted: {model_name} {used}/{budget} "
                    f"quota_date={quota_date}"
                )

            by_kind = state.get("by_kind") if isinstance(state.get("by_kind"), dict) else {}
            state["used"] = used + 1
            state["budget"] = budget
            state["by_kind"] = by_kind
            by_kind[kind] = int(by_kind.get(kind, 0) or 0) + 1
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            data["scope_kind"] = "repository_local"
            if self.provider_project_scope:
                data["provider_project_fingerprint"] = self.provider_project_scope
            try:
                self._write_remote(data, sha)
                self.session_used += 1
                logger.info(
                    f"[GEMINI PERSISTENT BUDGET] reserved {state['used']}/{budget} "
                    f"quota_date={quota_date} counter_scope={self.counter_scope[:8]} model={model_name} kind={kind}"
                )
                return
            except GeminiBudgetExceededError as e:
                msg = str(e)
                if attempt < 2 and ("HTTP 409" in msg or "HTTP 422" in msg):
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise

        raise GeminiBudgetExceededError("Persistent Gemini counter reservation failed after retries")

    def summary(self) -> str:
        if not self.enabled:
            return "Persistent Gemini Daily Counter: disabled"
        if not self.counter_scope:
            return "Persistent Gemini Daily Counter: unavailable (stable scope missing)"
        try:
            data, _ = self._read_remote()
            data = self._normalized_day(data, self._quota_date())
            models = data.get("counter_scopes", {}).get(self.counter_scope, {}).get("models", {})
            detail = ", ".join(
                f"{name}:{int(state.get('used', 0))}/{self.budget_for(name)}"
                for name, state in sorted(models.items())
            ) or "0"
            return (
                f"Persistent Gemini Daily Counter(scope={self.counter_scope[:8]}): "
                f"{detail} ({data.get('quota_date')})"
            )
        except Exception as e:
            return f"Persistent Gemini Daily Counter: unavailable ({e})"


PERSISTENT_GEMINI_COUNTER = PersistentGeminiDailyCounter(
    GEMINI_PERSISTENT_DAILY_COUNTER,
    MODEL_DAILY_BUDGETS,
    GEMINI_PERSISTENT_DAILY_REQUEST_BUDGET,
    GEMINI_PERSISTENT_COUNTER_PATH,
    GEMINI_QUOTA_TIMEZONE,
    GEMINI_QUOTA_PROJECT_ID,
    quota_scope_id=GEMINI_COUNTER_SCOPE_ID,
)


class GeminiUsageAudit:
    """1 Run内のGemini API試行をmodel / kind / context単位で監査する。

    Provider dashboardと完全一致する課金台帳ではなく、このPipelineが実際に送信を
    試みた回数の内部監査ログ。429/503等もattemptとして残し、success/errorを分離する。
    Prompt本文や未公開記事本文は保存せず、候補名・Batch IDなど短いcontextだけを保持する。
    """
    def __init__(self):
        self.records: list[dict] = []

    @staticmethod
    def _safe_context(context: str | None) -> str:
        value = re.sub(r"[\r\n\t]+", " ", str(context or "")).strip()
        return value[:160]

    def record_attempt(self, model_name: str, kind: str, context: str | None = None) -> int:
        self.records.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": str(model_name or "default"),
            "kind": str(kind or "other"),
            "context": self._safe_context(context),
            "outcome": "attempted",
            "error_type": "",
        })
        return len(self.records) - 1

    def record_outcome(self, record_id: int | None, outcome: str, error: Exception | None = None) -> None:
        if record_id is None or not (0 <= record_id < len(self.records)):
            return
        row = self.records[record_id]
        row["outcome"] = outcome
        if error is not None:
            row["error_type"] = type(error).__name__[:80]

    def record_response_usage(self, record_id: int | None, response) -> None:
        if record_id is None or not (0 <= record_id < len(self.records)):
            return
        usage = getattr(response, "usage_metadata", None)
        if not usage:
            return
        fields = (
            "prompt_token_count", "candidates_token_count", "total_token_count",
            "tool_use_prompt_token_count", "cached_content_token_count", "thoughts_token_count",
        )
        payload = {}
        for field in fields:
            value = getattr(usage, field, None)
            if isinstance(value, (int, float)):
                payload[field] = int(value)
        if payload:
            self.records[record_id]["tokens"] = payload

    def aggregate(self) -> dict:
        by_model: dict[str, dict] = {}
        by_kind: dict[str, int] = {}
        by_context: dict[str, int] = {}
        success = error = 0
        prompt_tokens = output_tokens = total_tokens = 0
        for row in self.records:
            model = row["model"]
            state = by_model.setdefault(
                model, {"attempts": 0, "success": 0, "error": 0, "by_kind": {}, "total_tokens": 0}
            )
            state["attempts"] += 1
            state["by_kind"][row["kind"]] = state["by_kind"].get(row["kind"], 0) + 1
            by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1
            if row.get("context"):
                by_context[row["context"]] = by_context.get(row["context"], 0) + 1
            tokens = row.get("tokens") if isinstance(row.get("tokens"), dict) else {}
            row_prompt = int(tokens.get("prompt_token_count", 0) or 0)
            row_output = int(tokens.get("candidates_token_count", 0) or 0)
            row_total = int(tokens.get("total_token_count", 0) or 0)
            prompt_tokens += row_prompt
            output_tokens += row_output
            total_tokens += row_total
            state["total_tokens"] += row_total
            if row["outcome"] == "success":
                state["success"] += 1
                success += 1
            elif row["outcome"] == "error":
                state["error"] += 1
                error += 1
        return {
            "attempts": len(self.records), "success": success, "error": error,
            "prompt_tokens": prompt_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens,
            "by_model": by_model, "by_kind": by_kind, "by_context": by_context,
        }

    def summary(self, include_contexts: bool = False, max_contexts: int = 8) -> str:
        agg = self.aggregate()
        model_parts = []
        for model, state in sorted(agg["by_model"].items()):
            kinds = "/".join(f"{k}:{v}" for k, v in sorted(state["by_kind"].items()))
            token_text = f" tokens:{state['total_tokens']}" if state.get("total_tokens") else ""
            model_parts.append(
                f"{model}={state['attempts']} (ok:{state['success']} err:{state['error']}{token_text}; {kinds or 'none'})"
            )
        token_summary = (
            f" tokens(prompt={agg['prompt_tokens']}, output={agg['output_tokens']}, total={agg['total_tokens']})"
            if agg.get("total_tokens") else ""
        )
        lines = [
            f"Gemini API Attempts: {agg['attempts']} (success={agg['success']}, error={agg['error']}){token_summary}",
            "Models: " + (" | ".join(model_parts) if model_parts else "none"),
        ]
        if include_contexts and agg["by_context"]:
            contexts = sorted(agg["by_context"].items(), key=lambda x: (-x[1], x[0]))[:max_contexts]
            lines.append("Contexts: " + " | ".join(f"{name}={count}" for name, count in contexts))
        return "\n".join(lines)

    def write_private_report(self, output_dir: str = "gate_history") -> str | None:
        if not self.records:
            return None
        try:
            os.makedirs(output_dir, exist_ok=True)
            path = os.path.join(
                output_dir,
                f"gemini_usage_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json",
            )
            payload = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "quota_timezone": GEMINI_QUOTA_TIMEZONE,
                "quota_project_scope": PERSISTENT_GEMINI_COUNTER.project_scope[:8],
                "aggregate": self.aggregate(),
                "records": self.records,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return path
        except Exception as exc:
            logger.warning("[GEMINI USAGE AUDIT SAVE FAILED] %s", exc)
            return None


GEMINI_USAGE_AUDIT = GeminiUsageAudit()
_GEMINI_USAGE_FINALIZED = False
_GEMINI_USAGE_ATEXIT_REGISTERED = False


def finalize_gemini_usage_observability(send_alert: bool = False) -> str:
    global _GEMINI_USAGE_FINALIZED
    summary = GEMINI_USAGE_AUDIT.summary(include_contexts=True)
    if _GEMINI_USAGE_FINALIZED:
        return summary
    _GEMINI_USAGE_FINALIZED = True
    if not GEMINI_USAGE_AUDIT.records:
        return summary
    logger.info("[GEMINI USAGE AUDIT]\n%s", summary)
    report_path = GEMINI_USAGE_AUDIT.write_private_report()
    if report_path:
        logger.info("[GEMINI USAGE AUDIT SAVED] %s", report_path)
    if send_alert:
        send_telegram_alert("📊 Gemini API Usage\n" + summary[:3200])
    return summary


def _register_gemini_usage_atexit() -> None:
    global _GEMINI_USAGE_ATEXIT_REGISTERED
    if _GEMINI_USAGE_ATEXIT_REGISTERED:
        return
    atexit.register(finalize_gemini_usage_observability)
    _GEMINI_USAGE_ATEXIT_REGISTERED = True


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


def _consume_gemini_request(kind: str, reserve: int = 0, model_name: str = "default",
                            request_context: str = "", count_as_deep_dive: bool = False,
                            request_origin: str = "new") -> int:
    # 送信前Budgetの順序は重要。
    # 1) process内Budgetを「確認のみ」
    # 2) Pending Retry専用枠 / Deep Dive枠を「確認のみ」
    # 3) Persistent Counterをreserve（ここでmodel RPD Safety Capを確定）
    # 4) 実送信が可能になった要求だけlocal Deep Dive/Pending/Run Budgetをconsume
    # これにより、Persistent上限で拒否されたmodel試行がDeep Dive 12枠を空費しない。
    if not GEMINI_BUDGET.can_request(reserve=reserve):
        raise GeminiBudgetExceededError(
            f"Gemini local budget exhausted: used={GEMINI_BUDGET.request_count}, "
            f"budget={GEMINI_BUDGET.daily_budget}, reserve={reserve}"
        )
    if kind in {"screening_retry", "screening_recovery"} and not GEMINI_BUDGET.can_screening_retry():
        raise GeminiBudgetExceededError("Screening retry budget exhausted")
    if kind == "deep_dive_retry" and not GEMINI_BUDGET.can_deep_dive_retry():
        raise GeminiBudgetExceededError("Deep Dive transport retry budget exhausted")
    if count_as_deep_dive and not DEEP_DIVE_MODEL_BUDGET.can_request():
        raise DeepDiveRunBudgetExceededError(
            f"Deep Dive run budget exhausted: used={DEEP_DIVE_MODEL_BUDGET.used}, "
            f"budget={DEEP_DIVE_MODEL_BUDGET.budget}, kind={kind}"
        )
    if count_as_deep_dive and request_origin == "pending_retry" and not PENDING_RETRY_REQUEST_BUDGET.can_request():
        raise PendingRetryBudgetExceededError(
            f"Pending Retry Gemini request budget exhausted: "
            f"used={PENDING_RETRY_REQUEST_BUDGET.used}, budget={PENDING_RETRY_REQUEST_BUDGET.budget}"
        )
    if request_origin == "product_review" and not PRODUCT_REVIEW_REQUEST_BUDGET.can_request():
        raise ProductReviewBudgetExceededError(
            f"Product Review request budget exhausted: used={PRODUCT_REVIEW_REQUEST_BUDGET.used}, "
            f"budget={PRODUCT_REVIEW_REQUEST_BUDGET.budget}"
        )

    # Persistent reserveが失敗した場合、以下のlocal countersは一切consumeしない。
    PERSISTENT_GEMINI_COUNTER.reserve(kind, reserve=reserve, model_name=model_name)
    if count_as_deep_dive:
        DEEP_DIVE_MODEL_BUDGET.consume(kind)
        if request_origin == "pending_retry":
            PENDING_RETRY_REQUEST_BUDGET.consume(kind)
    if request_origin == "product_review":
        PRODUCT_REVIEW_REQUEST_BUDGET.consume(kind)
    GEMINI_BUDGET.consume(kind, reserve=reserve)
    # Funnelの「Deep Dive Generation Called」は、candidate intentではなく
    # Persistent/Local Budgetを全て通過して実際にprovider送信へ進む試行だけを数える。
    funnel = globals().get("DEEP_DIVE_GATE_FUNNEL")
    if count_as_deep_dive and funnel is not None:
        funnel.incr("deep_dive_generation_called")
    return GEMINI_USAGE_AUDIT.record_attempt(model_name, kind, request_context)


class DeepDiveModelBudget:
    """Deep Dive用上位モデルだけの1実行Safety Cap。永続Daily Counterとは別のローカル上限。"""
    def __init__(self, budget: int):
        self.budget = max(0, budget)
        self.used = 0

    def can_request(self) -> bool:
        return self.used + 1 <= self.budget

    def consume(self, kind: str) -> None:
        if not self.can_request():
            raise DeepDiveRunBudgetExceededError(
                f"Deep Dive run budget exhausted: used={self.used}, budget={self.budget}, kind={kind}"
            )
        self.used += 1

    def summary(self) -> str:
        return f"Deep Dive Model Requests Used (per-run): {self.used}/{self.budget}"


DEEP_DIVE_MODEL_BUDGET = DeepDiveModelBudget(GEMINI_DEEP_DIVE_DAILY_REQUEST_BUDGET)


class PendingRetryRequestBudget:
    """旧Pending Retryが当日のFresh Deep Dive枠を食い潰さないための専用実送信上限。"""
    def __init__(self, budget: int):
        self.budget = max(0, int(budget))
        self.used = 0
        self.by_kind: dict[str, int] = {}

    @property
    def remaining(self) -> int:
        return max(0, self.budget - self.used)

    def can_request(self) -> bool:
        return self.used + 1 <= self.budget

    def consume(self, kind: str) -> None:
        if not self.can_request():
            raise PendingRetryBudgetExceededError(
                f"Pending Retry Gemini request budget exhausted: used={self.used}, budget={self.budget}"
            )
        self.used += 1
        self.by_kind[kind] = self.by_kind.get(kind, 0) + 1

    def summary(self) -> str:
        details = ", ".join(f"{k}={v}" for k, v in sorted(self.by_kind.items())) or "none"
        return f"Pending Retry Gemini Requests Used: {self.used}/{self.budget} ({details})"


PENDING_RETRY_REQUEST_BUDGET = PendingRetryRequestBudget(GEMINI_PENDING_RETRY_REQUEST_BUDGET)


class ProductReviewRequestBudget:
    """Dedicated product-side budget so free-note generation cannot starve subscriber DB reviews."""
    def __init__(self, budget: int):
        self.budget = max(0, int(budget)); self.used = 0; self.by_kind: dict[str, int] = {}
    def can_request(self) -> bool:
        return self.used + 1 <= self.budget
    def consume(self, kind: str) -> None:
        if not self.can_request():
            raise ProductReviewBudgetExceededError(f"Product Review request budget exhausted: {self.used}/{self.budget}")
        self.used += 1; self.by_kind[kind] = self.by_kind.get(kind, 0) + 1
    def summary(self) -> str:
        details = ", ".join(f"{k}={v}" for k, v in sorted(self.by_kind.items())) or "none"
        return f"Product Review Gemini Requests Used: {self.used}/{self.budget} ({details})"


PRODUCT_REVIEW_REQUEST_BUDGET = ProductReviewRequestBudget(GEMINI_PRODUCT_REVIEW_PER_RUN_REQUEST_BUDGET)


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

# Gemini 1回の最大待機時間。Screening/Calibrationもnetwork hangでjob全体を
# 食い潰さないようwatchdogを持つ。Deep Diveは長文生成のため別上限を使う。
# Linux runnerのmain threadではSIGALRMで同期SDK callをFail-Closed中断する。
GEMINI_SCREENING_CALL_TIMEOUT_SECONDS = int(os.environ.get("GEMINI_SCREENING_CALL_TIMEOUT_SECONDS", "60"))
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
                _generate_via_chat(
                    model_name,
                    "ping",
                    config={"max_output_tokens": 8},
                    request_kind="ping" if attempt == 0 else "ping_retry",
                    request_context=f"model_resolve:{label}:{model_name}",
                    count_as_deep_dive=count_as_deep_dive,
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


NOTION_REQUIRED_PROPERTY_TYPES = {
    PROP_NAME: "title", PROP_URL: "url", PROP_SOURCE: "select", PROP_ENGAGEMENT: "number",
    PROP_SCORE: "number", PROP_STATUS: "select", PROP_CONTENT_STATUS: "select",
    PROP_ARTICLE_STATUS: "select", PROP_SUBSCRIPTION_VISIBILITY: "select",
    PROP_SCORE_BREAKDOWN: "rich_text", PROP_WHAT: "rich_text", PROP_WHY_IMPORTANT: "rich_text",
    PROP_WHY_NOT_IMPORTANT: "rich_text", PROP_WHO: "rich_text", PROP_ACTION: "rich_text",
    PROP_LICENSE: "rich_text", PROP_PARADIGM_SHIFT: "rich_text", PROP_ALTERNATIVE_COMPARISON: "rich_text",
    PROP_MIGRATION_COST: "rich_text", PROP_TITLE: "rich_text", PROP_EYECATCH: "files",
    PROP_PUBLISHED_AT: "date", PROP_ANALYZED_AT: "date", PROP_SOURCE_SUMMARY: "rich_text",
    PROP_DECISION: "select", PROP_DECISION_REASON: "rich_text", PROP_WHO_SHOULD_USE: "rich_text",
    PROP_WHO_SHOULD_NOT_USE: "rich_text", PROP_FUTURE_SCENARIO: "rich_text", PROP_ARTICLE_VALUE: "number",
    PROP_GROUNDING_STATUS: "select", PROP_EVIDENCE_URLS: "rich_text",
    PROP_SCREENING_SCORE: "number", PROP_SCREENING_REASON: "rich_text", PROP_REVIEW_STATUS: "status",
}


def preflight_notion_schema() -> None:
    """Gemini消費前に内部Notion DBの必須列と型を確認する。

    人手で列名/型を変更した状態でScreeningやDeep Diveを走らせ、最後の永続化で
    全件失敗するコスト事故を防ぐ。select optionの増減までは拘束せず、Schema互換性
    （property名とtype）だけをFail-Closedで検証する。
    """
    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID):
        raise ValueError("Notion内部DB設定（NOTION_API_KEY + DATA_SOURCE_ID/DATABASE_ID）が必要です。")
    try:
        res = requests.get(_notion_schema_url(), headers=_notion_headers(), timeout=15)
        res.raise_for_status()
        properties = res.json().get("properties", {})
    except Exception as exc:
        raise RuntimeError(f"Notion schema preflight failed: {exc}") from exc
    missing = [name for name in NOTION_REQUIRED_PROPERTY_TYPES if name not in properties]
    mismatched = []
    for name, expected in NOTION_REQUIRED_PROPERTY_TYPES.items():
        actual = (properties.get(name) or {}).get("type")
        if actual and actual != expected:
            mismatched.append(f"{name}:{actual}!={expected}")
    if missing or mismatched:
        detail = []
        if missing:
            detail.append("missing=" + ", ".join(missing))
        if mismatched:
            detail.append("type_mismatch=" + ", ".join(mismatched))
        raise ValueError("Notion schema incompatible: " + " / ".join(detail))
    logger.info("[NOTION PREFLIGHT OK] required_properties=%d", len(NOTION_REQUIRED_PROPERTY_TYPES))


def initialize_runtime() -> None:
    """Validate production-only requirements without spending Gemini quota."""
    global SELECTED_SCREENING_MODEL, SELECTED_DEEP_DIVE_MODEL
    if PUBLIC_DB_SYNC_MODE or SYNTHETIC_REGRESSION_MODE:
        return
    if not GEMINI_API_KEY or not GH_PAT:
        raise ValueError("エラー: GEMINI_API_KEY または GH_PAT が設定されていません。")
    if not REGEN_TEST_MODE and not PRODUCTHUNT_DEVELOPER_TOKEN:
        raise ValueError("エラー: Product Huntは必須ソースのため PRODUCTHUNT_DEVELOPER_TOKEN が必要です。")
    if ENABLE_SUBSCRIPTION_ATTRIBUTION and not SUBSCRIPTION_LANDING_URL:
        logger.warning("[ATTRIBUTION PREFLIGHT] SUBSCRIPTION_LANDING_URL未設定。記事生成は継続しますがサブスクCTA/転換計測は無効です。")
    if GEMINI_PERSISTENT_DAILY_COUNTER and not GEMINI_COUNTER_SCOPE_ID:
        raise ValueError(
            "エラー: Gemini永続Safety Counterの安定scopeを決定できません。"
            "GitHub ActionsではGITHUB_REPOSITORYが自動設定されます。"
        )
    if GEMINI_PERSISTENT_DAILY_COUNTER:
        if GEMINI_QUOTA_PROJECT_ID:
            logger.info("[GEMINI QUOTA PREFLIGHT] repository-local counter active; provider Project fingerprint available")
        else:
            logger.warning(
                "[GEMINI QUOTA PREFLIGHT] GEMINI_QUOTA_PROJECT_IDはWorkflowから取得できませんでした。"
                "Repository-local counterへ自動フォールバックします。AI StudioのProject-wide使用量が最終的な正です。"
            )
    if not SCREENING_MODEL_POOL or not DEEP_DIVE_MODEL_POOL:
        raise ValueError("Gemini model candidate pool が空です。")
    preflight_notion_schema()
    # 商品DB side-pathを有効化した場合だけ、Gemini消費前に新2DBのSchemaも検証する。
    # Runtime書込み失敗は記事Pipelineへ波及させないが、設定ミスで無駄な生成をしない。
    decision_intelligence.preflight_decision_intelligence_schema()
    evidence_ledger.preflight(decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY)
    _register_gemini_usage_atexit()
    # Availability is established by the first real request.  This avoids two
    # quota-consuming pings on every run and makes import/test completely safe.
    SELECTED_SCREENING_MODEL = SCREENING_MODEL_POOL[0]
    SELECTED_DEEP_DIVE_MODEL = DEEP_DIVE_MODEL_POOL[0]


def initialize_inventory_bootstrap_runtime() -> None:
    """Validate only dependencies required by manual Product Review bootstrap.

    Unlike normal Daily, this mode does not collect sources, screen articles, generate note drafts,
    or write Article Audit artifacts. It therefore must not fail on unrelated article-DB or
    Product Hunt configuration. Decision Intelligence + History + Subscriber schemas remain
    fail-closed because Product Review writes through those authoritative paths.
    """
    global SELECTED_DEEP_DIVE_MODEL
    if not GEMINI_API_KEY:
        raise ValueError("Inventory Bootstrap requires GEMINI_API_KEY")
    if GEMINI_PERSISTENT_DAILY_COUNTER and not GEMINI_COUNTER_SCOPE_ID:
        raise ValueError("Inventory Bootstrap persistent counter requires a stable repository/counter scope")
    if GEMINI_PERSISTENT_DAILY_COUNTER and (not GH_PAT or not os.environ.get("GITHUB_REPOSITORY", "").strip()):
        raise ValueError("Inventory Bootstrap persistent counter requires GH_PAT and GITHUB_REPOSITORY")
    if not DEEP_DIVE_MODEL_POOL:
        raise ValueError("Inventory Bootstrap requires a non-empty product-review model pool")
    decision_intelligence.preflight_decision_intelligence_schema()
    evidence_ledger.preflight(decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY)
    _register_gemini_usage_atexit()
    SELECTED_DEEP_DIVE_MODEL = DEEP_DIVE_MODEL_POOL[0]
    logger.info("[INVENTORY BOOTSTRAP PREFLIGHT OK] Product Review / History / Subscriber only")


def _mark_model_exhausted(model_name: str, reason: str = "") -> None:
    SESSION_EXHAUSTED_MODELS.add(model_name)
    logger.warning("[MODEL EXHAUSTED] %s %s", model_name, reason)


def _mark_model_unavailable(model_name: str, reason: str = "") -> None:
    SESSION_UNAVAILABLE_MODELS.add(model_name)
    logger.warning("[MODEL UNAVAILABLE] %s %s", model_name, reason)


def _call_model_pool(prompt: str, config: dict | None, kind: str, reserve: int,
                     pool: list[str], deep_dive: bool = False, request_context: str = "",
                     request_origin: str = "new"):
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
                    # Deep Dive run/Pending Retry budgets are checked BEFORE pacing.
                    # Once 12/12 is reached, do not sleep, iterate fallback models, or
                    # misclassify a local safety stop as provider MODEL_UNAVAILABLE.
                    if not DEEP_DIVE_MODEL_BUDGET.can_request():
                        raise DeepDiveRunBudgetExceededError(
                            f"Deep Dive run budget exhausted: used={DEEP_DIVE_MODEL_BUDGET.used}, "
                            f"budget={DEEP_DIVE_MODEL_BUDGET.budget}, kind={kind}"
                        )
                    if request_origin == "pending_retry" and not PENDING_RETRY_REQUEST_BUDGET.can_request():
                        raise PendingRetryBudgetExceededError(
                            f"Pending Retry Gemini request budget exhausted: "
                            f"used={PENDING_RETRY_REQUEST_BUDGET.used}, budget={PENDING_RETRY_REQUEST_BUDGET.budget}"
                        )
                    time.sleep(max(0, GEMINI_DEEP_DIVE_CALL_PACING_SECONDS))
                    with _gemini_call_timeout(GEMINI_DEEP_DIVE_CALL_TIMEOUT_SECONDS):
                        response = _generate_via_chat(
                            model_name, prompt, config=config,
                            request_kind=kind if attempt == 0 else "deep_dive_retry", reserve=reserve,
                            request_context=request_context, count_as_deep_dive=True,
                            request_origin=request_origin,
                        )
                else:
                    with _gemini_call_timeout(GEMINI_SCREENING_CALL_TIMEOUT_SECONDS):
                        response = _generate_via_chat(
                            model_name, prompt, config=config,
                            request_kind=kind if attempt == 0 else "screening_retry", reserve=reserve,
                            request_context=request_context,
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
            except (PendingRetryBudgetExceededError, DeepDiveRunBudgetExceededError):
                # Local safety stops are terminal for this request.  Never convert them
                # to NoAvailableModelError and never walk the rest of the model pool.
                raise
            except GeminiBudgetExceededError as exc:
                last_error = exc
                if "Persistent Gemini model budget exhausted" in str(exc):
                    _mark_model_exhausted(model_name, "persistent safety cap")
                break
            except GeminiCallTimeoutError as exc:
                last_error = exc
                break
    raise NoAvailableModelError("利用可能なGeminiモデルがありません") from last_error


def _model_pool_has_session_candidate(pool: list[str]) -> bool:
    """Return False when every configured model is already exhausted/unavailable this run."""
    return any(
        model_name and model_name not in SESSION_EXHAUSTED_MODELS and model_name not in SESSION_UNAVAILABLE_MODELS
        for model_name in (str(model).strip() for model in pool)
    )


def _call_screening_pool(prompt: str, config: dict | None = None, kind: str = "screening", reserve: int = 0,
                         request_context: str = ""):
    return _call_model_pool(
        prompt, config, kind, reserve, SCREENING_MODEL_POOL, deep_dive=False, request_context=request_context
    )


def _call_deep_dive_pool(prompt: str, config: dict | None = None, kind: str = "deep_dive",
                         request_context: str = "", request_origin: str = "new"):
    return _call_model_pool(
        prompt, config, kind, 0, DEEP_DIVE_MODEL_POOL, deep_dive=True,
        request_context=request_context, request_origin=request_origin
    )


def call_gemini_with_smart_retry(prompt: str, max_retries: int = 1, request_kind: str = "deep_dive",
                                 request_context: str = ""):
    """非Groundedな既存互換call。無制限retryを禁止しLocal Budgetを必ず通す。"""
    for attempt in range(max_retries + 1):
        kind = request_kind if attempt == 0 else "deep_dive_retry"
        try:
            time.sleep(3)
            return _generate_via_chat(
                SELECTED_DEEP_DIVE_MODEL, prompt, request_kind=kind, request_context=request_context,
                count_as_deep_dive=True
            )
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



def _strip_internal_note_control_lines(text: str) -> tuple[str, int]:
    """Remove exact transport-control lines before quality gates.

    These markers are generation protocol, not article content. Exact standalone markers are
    deterministically removable; marker-like prose remains untouched and can still be flagged.
    """
    cleaned, count = re.subn(r"(?mi)^\s*={3,}\s*NOTE_DRAFT_(?:START|END)\s*={0,}\s*$\n?", "", text or "")
    return cleaned.strip(), count

def normalize_markdown_for_note(text: str) -> str:
    """
    note.comのMarkdownペースト機能にそのまま乗せられる形へ軽く正規化する。
    Markdown記法（見出し・太字・箇条書き・区切り線）は一切除去せず保持する。
    """
    if not text:
        return ""

    stripped = text.strip()
    # 生成プロトコル用の制御文字がnote本文に残る事故を防ぐ。
    stripped, _ = _strip_internal_note_control_lines(stripped)
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
        "- **出典について**: 本文の技術的な事実・数値は、上記の公式リンクおよび参考情報で確認できる範囲を独自に分析・要約したものです。"
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

# 旧稿との後方互換・section fallback用の見出しalias。Run108以降は生成プロンプトの可視テンプレートとしては使わない。
# 名前から安定して選ぶため、Quality Retryで同じ記事の構成が無意味に揺れない。
ARTICLE_DISPLAY_VARIANTS = (
    # 問題提起型
    {"style": "problem", "intro": "現場の困りごとから", "conclusion": "先に判断を書くと。",
     "why": "なぜ、この問題が残り続けるのか。", "what": "今回の仕組みを見てみる。",
     "key": "導入前に押さえたいポイント。", "decision": "私なら、この範囲から試す。",
     "final": "結論として、いま取る距離感。", "opening": "practical_problem", "intro_paragraphs": 3, "tone": "practical_interest"},
    # 実験型
    {"style": "experiment", "intro": "まず、何を確かめればいい？", "conclusion": "試す価値はあるのか。",
     "why": "検証したい仮説はここです。", "what": "仕組みを分解してみる。",
     "key": "PoCで見るべき条件。", "decision": "私なら、こう検証する。",
     "final": "本番投入は、その結果を見てから。", "opening": "observation", "intro_paragraphs": 2, "tone": "experimental"},
    # 数字型
    {"style": "numbers", "intro": "数字から見えるもの", "conclusion": "その数字をどう読むか。",
     "why": "条件を外すと意味が変わる。", "what": "数字の裏側にある仕組み。",
     "key": "再現するときの注意点。", "decision": "私なら、数字をこう確かめる。",
     "final": "数字は魅力的。でも条件付きです。", "opening": "fact", "intro_paragraphs": 4, "tone": "skeptical_but_interesting"},
    # 意外性型
    {"style": "surprise", "intro": "一見すると地味。でも気になる。", "conclusion": "見逃したくない理由。",
     "why": "従来の前提が少し揺らぐ。", "what": "何が違うのか。",
     "key": "面白さとリスクを分けて見る。", "decision": "私なら、ここまでは踏み込む。",
     "final": "面白いからこそ、急がない。", "opening": "discovery", "intro_paragraphs": 3, "tone": "cautious_interest"},
    # 比較型
    {"style": "comparison", "intro": "従来のやり方と比べると", "conclusion": "置き換える価値はある？",
     "why": "比較軸を先にそろえる。", "what": "違いはどこにあるのか。",
     "key": "得るもの、失うもの。", "decision": "私なら、全面移行はまだしない。",
     "final": "勝ち負けではなく、適用範囲で決める。", "opening": "comparison", "intro_paragraphs": 3, "tone": "balanced_comparison"},
)


# Run-local heading diversity.  The same article keeps the same profile across Quality Retry,
# while new articles are balanced across the available profiles so two hash collisions do not
# make a Daily run look template-generated.  Nothing is persisted across runs.
_ARTICLE_DISPLAY_ASSIGNMENTS: dict[str, int] = {}
_ARTICLE_DISPLAY_USAGE: list[int] = [0] * len(ARTICLE_DISPLAY_VARIANTS)


def _article_display_variant(name: str) -> dict:
    key = (name or "article").strip() or "article"
    if key in _ARTICLE_DISPLAY_ASSIGNMENTS:
        return ARTICLE_DISPLAY_VARIANTS[_ARTICLE_DISPLAY_ASSIGNMENTS[key]]

    preferred = hashlib.sha256(key.encode("utf-8")).digest()[0] % len(ARTICLE_DISPLAY_VARIANTS)
    minimum_use = min(_ARTICLE_DISPLAY_USAGE) if _ARTICLE_DISPLAY_USAGE else 0
    # Among the least-used profiles, pick the one nearest the article-specific hash preference.
    # This preserves stable variety without allowing consecutive hash collisions to dominate a run.
    candidates = [i for i, used in enumerate(_ARTICLE_DISPLAY_USAGE) if used == minimum_use]
    chosen = min(candidates, key=lambda i: ((i - preferred) % len(ARTICLE_DISPLAY_VARIANTS), i))
    _ARTICLE_DISPLAY_ASSIGNMENTS[key] = chosen
    _ARTICLE_DISPLAY_USAGE[chosen] += 1
    return ARTICLE_DISPLAY_VARIANTS[chosen]


def _reset_article_display_variant_rotation() -> None:
    """Test/support hook; normal process startup already creates a fresh run-local rotation."""
    _ARTICLE_DISPLAY_ASSIGNMENTS.clear()
    for i in range(len(_ARTICLE_DISPLAY_USAGE)):
        _ARTICLE_DISPLAY_USAGE[i] = 0


def _evidence_trace_url_key(url: str) -> str:
    """Evidence監査用の重複キー。

    Stock dedupeではarXiv abs/pdf/versionを同一論文資産として統合するが、Evidence
    traceでは「実際にPDFを取得した」事実を残す必要があるためabsとpdfは分離する。
    それ以外はtracking差等を通常のcanonicalizationで除去する。
    """
    if not url:
        return ""
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower()
    path = parsed.path.rstrip("/")
    if host in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        match = re.fullmatch(r"/(abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?", path, re.I)
        if match:
            kind = match.group(1).lower()
            return f"https://arxiv.org/{kind}/{match.group(2)}"
    return canonicalize_url(url) or url.strip()


def _collect_final_evidence_urls(source_info: dict, grounding: dict | None = None) -> list[str]:
    """最終成果物へ残すEvidence URLを、実取得資料を含めて安定順で集約する。

    Gemini grounding metadataだけに依存すると、Evidence Supplementで実際に読んだ
    PDF/DocsがNotion Evidence URLsや記事末尾から落ちる。Primary → retrieved documents
    → grounding metadataの順にcanonical dedupeし、Evidence document上限まで保持する。
    """
    candidates: list[str] = []
    primary = source_info.get("primary_url") or ""
    if isinstance(primary, str) and primary:
        candidates.append(primary)
    for doc in source_info.get("evidence_documents", []) or []:
        if doc.get("retrieved") and isinstance(doc.get("url"), str):
            candidates.append(doc["url"])
    for url in (grounding or {}).get("evidence_urls", []) or []:
        if isinstance(url, str):
            candidates.append(url)
    for url in source_info.get("deep_source_urls", []) or []:
        if isinstance(url, str):
            candidates.append(url)

    out: list[str] = []
    seen: set[str] = set()
    for url in candidates:
        if not url.startswith(("http://", "https://")):
            continue
        key = _evidence_trace_url_key(url)
        if key in seen:
            continue
        seen.add(key)
        out.append(url)
        if len(out) >= MAX_EVIDENCE_DOCUMENTS:
            break
    return out


def build_article_attribution_id(source: str, repo_url: str) -> str:
    """Create a stable, non-PII article identifier from source + canonical primary URL.

    Tracking/query differences in the source URL must not create a new attribution identity.
    The identifier is intentionally opaque so it can be placed in CTA query parameters without
    exposing internal scores or subscriber information.
    """
    raw_url = (repo_url or "").strip()
    try:
        identity_url = canonicalize_url(raw_url) or raw_url
    except Exception:
        identity_url = raw_url
    # Primary URL is the stable business identity. Discovery source must not split attribution
    # when the same underlying item is found through HN/Product Hunt/GitHub on a later run.
    identity = identity_url or f"source:{(source or 'Unknown').strip().lower()}"
    return "aif-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def build_subscription_tracking_url(article_id: str, landing_url: str | None = None) -> str:
    """Build a public CTA URL carrying only aggregate attribution identifiers.

    Existing non-attribution query parameters are preserved. Existing UTM/aif keys are replaced
    deterministically to avoid duplicate parameters. Invalid/non-http(s) URLs fail closed to an
    empty string so a broken or unsafe CTA is never inserted into a public article.
    """
    if not ENABLE_SUBSCRIPTION_ATTRIBUTION:
        return ""
    base = (landing_url if landing_url is not None else SUBSCRIPTION_LANDING_URL).strip()
    if not base or not article_id:
        return ""
    try:
        parsed = urlparse(base)
    except Exception:
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    reserved = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "aif_article_id"}
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in reserved]
    query.extend([
        ("utm_source", "note"),
        ("utm_medium", "free_article"),
        ("utm_campaign", SUBSCRIPTION_CAMPAIGN_ID),
        ("utm_content", article_id),
        ("aif_article_id", article_id),
    ])
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query, doseq=True), parsed.fragment))


def build_subscription_cta(article_id: str, tracking_url: str = "") -> str:
    """Return the free-article CTA for the subscriber DB + monthly summary offer.

    If no configured landing URL is available, return an empty string rather than publishing a
    placeholder/broken link. The article remains fully free either way.
    """
    url = tracking_url or build_subscription_tracking_url(article_id)
    if not url:
        return ""
    return (
        f"{DIVIDER_LINE}"
        "### 調査と判断の時間を減らしたい方へ\n\n"
        "無料記事では重要テーマを最後まで公開しています。会員向けには、"
        "意思決定DBと月次サマリーで、追うべき情報・Evidence・Actionを継続的に整理します。\n\n"
        f"[会員向け意思決定DB＋月次サマリーを見る]({url})\n"
    )


def _upload_subscription_attribution_to_github(local_path: str, article_id: str) -> str | None:
    """Persist aggregate attribution metadata. No subscriber PII is ever stored here."""
    if not EYECATCH_GITHUB_REPO or not GH_PAT:
        logger.warning("[ATTRIBUTION UPLOAD SKIP] GITHUB_REPOSITORY/GH_PAT が未設定です。")
        return None
    dest_path = f"{SUBSCRIPTION_ATTRIBUTION_GITHUB_DIR}/{article_id}.json"
    api_url = f"https://api.github.com/repos/{EYECATCH_GITHUB_REPO}/contents/{dest_path}"
    headers = {"Authorization": f"Bearer {GH_PAT}", "Accept": "application/vnd.github+json"}
    try:
        sha = None
        existing = requests.get(api_url, headers=headers, timeout=30)
        if existing.status_code == 200:
            sha = existing.json().get("sha")
        elif existing.status_code != 404:
            logger.warning("[ATTRIBUTION LOOKUP FAILED] %s: %s", article_id, existing.text[:300])
            return None
        content = base64.b64encode(Path(local_path).read_bytes()).decode("ascii")
        payload = {
            "message": f"chore: update subscription attribution {article_id}",
            "content": content,
            "branch": EYECATCH_GITHUB_BRANCH,
        }
        if sha:
            payload["sha"] = sha
        res = requests.put(api_url, headers=headers, json=payload, timeout=30)
        if res.status_code not in (200, 201):
            logger.warning("[ATTRIBUTION UPLOAD FAILED] %s: %s", article_id, res.text[:300])
            return None
        return dest_path
    except Exception as exc:
        logger.warning("[ATTRIBUTION UPLOAD EXCEPTION] %s: %s", article_id, exc)
        return None


def save_subscription_attribution_record(repo: dict, parsed: dict, analyzed_at: str,
                                         notion_page_id: str | None = None,
                                         attribution_context: dict | None = None) -> str | None:
    """Save a Ready-only, aggregate attribution manifest for later conversion measurement.

    This is telemetry, not a publication gate: a telemetry write failure must never turn a valid
    Ready article into a failure. No email, name, member ID, payment ID, or other subscriber PII
    belongs in this record.
    """
    if not ENABLE_SUBSCRIPTION_ATTRIBUTION:
        return None
    source = repo.get("source", "GitHub")
    source_url = repo.get("url", "")
    article_id = build_article_attribution_id(source, source_url)
    tracking_url = build_subscription_tracking_url(article_id)
    if not tracking_url:
        logger.warning("[ATTRIBUTION SKIP] SUBSCRIPTION_LANDING_URLが未設定/不正のためReady manifestを保存しません: %s", article_id)
        return None
    context = attribution_context or {}
    record = {
        "schema_version": 1,
        "article_id": article_id,
        "channel": "note_free_article",
        "offer": "subscriber_decision_db_plus_monthly_summary",
        "source": source,
        "source_url": source_url,
        "note_title": parsed.get("title_text", ""),
        "ready_at": analyzed_at,
        "notion_page_id": notion_page_id or "",
        "tracking_url": tracking_url,
        "cta_enabled": bool(tracking_url),
        "decision_score": parsed.get("score"),
        "screening_score": context.get("score"),
        "commercial_value_score": context.get("commercial_score"),
        "shelf_life_score": context.get("shelf_life_score"),
        "shelf_life": context.get("shelf_life"),
        "portfolio_topic": context.get("portfolio_topic"),
        "deep_dive_priority_score": context.get("deep_dive_priority_score"),
        "measurement_status": "awaiting_external_metrics",
    }
    try:
        os.makedirs(SUBSCRIPTION_ATTRIBUTION_DIR, exist_ok=True)
        path = os.path.join(SUBSCRIPTION_ATTRIBUTION_DIR, f"{article_id}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=2)
        _upload_subscription_attribution_to_github(path, article_id)
        return path
    except Exception as exc:
        logger.warning("[ATTRIBUTION SAVE FAILED] %s: %s", article_id, exc)
        return None


_READER_SOURCE_LABELS = {
    "GitHub": "GitHub",
    "HackerNews": "Hacker News",
    "ArXiv": "arXiv",
    "ProductHunt": "Product Hunt",
}


def _reader_plain_text(text: str) -> str:
    """Gate通過済みテキストから冒頭サマリー用のプレーン文だけを安全に取り出す。"""
    value = normalize_markdown_for_note(str(text or ""))
    if not value:
        return ""
    value = re.sub(r"!\[([^]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"(?m)^#{1,6}\s*", "", value)
    value = re.sub(r"(?m)^\s*[-*+]\s+", "", value)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    value = re.sub(r"https?://\S+", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _compact_reader_summary(text: str, max_chars: int = 110) -> str:
    """冒頭で一目で読める長さへ縮める。新しい事実は生成せず、完結文を優先する。"""
    value = _reader_plain_text(text)
    if not value:
        return ""
    sentences = [m.group(0).strip() for m in re.finditer(r"[^。！？!?]+[。！？!?]?", value) if m.group(0).strip()]
    if sentences:
        first = sentences[0]
        if len(first) <= max_chars:
            return first
    if len(value) <= max_chars:
        return value
    cut = value[:max_chars]
    # Reader-first要約では、専門語の長い列挙を途中で切って見せない。
    # 完全文が収まらない場合は、意味が壊れにくい句読点まで戻す。
    for sep in ("。", "；", ";", "、", "，", ","):
        pos = cut.rfind(sep)
        if pos >= max_chars // 2:
            candidate = cut[:pos + 1].strip()
            if candidate.endswith(("され、", "して、", "おり、", "ため、", "ので、")):
                continue
            return candidate
    return cut.rstrip("、，, ") + "…"


def _reader_summary_complexity(text: str) -> tuple[int, int]:
    """同じGate通過情報の候補から、冒頭向けに専門語密度の低い文を選ぶための順位。"""
    value = _reader_plain_text(text)
    if not value:
        return (10_000, 10_000)
    technical_ids = len(re.findall(r"\b(?:SEP|RFC|CVE)-?\d+\b|`[^`]+`|/[a-z][a-z0-9_-]+", value, re.I))
    # AI/LLM/API/MCP/OSS/GitHubは本媒体の読者に許容する基本語。それ以外の英字列挙を重くする。
    ascii_terms = [
        token for token in re.findall(r"\b[A-Za-z][A-Za-z0-9.-]{2,}\b", value)
        if token.upper() not in {"AI", "LLM", "API", "MCP", "OSS", "GITHUB"}
    ]
    list_density = max(0, value.count("、") - 2)
    paren_density = len(re.findall(r"[（(][^）)]{8,}[）)]", value))
    return (technical_ids * 8 + len(ascii_terms) * 2 + list_density * 2 + paren_density, len(value))


def _pick_reader_summary_candidate(candidates: list[str]) -> str:
    """追加生成せず、既存のGate通過候補から最も読みやすい完結文を選ぶ。"""
    usable = []
    for candidate in candidates:
        compact = _compact_reader_summary(candidate)
        if compact:
            usable.append(compact)
    if not usable:
        return ""
    return min(usable, key=_reader_summary_complexity)


def _find_reader_intro_fact_sentence(intro: str) -> str:
    """導入から『何が出たか』を示す文だけを候補化する。事実の言い換えは行わない。"""
    value = _reader_plain_text(intro)
    if not value:
        return ""
    for m in re.finditer(r"[^。！？!?]+[。！？!?]?", value):
        sentence = m.group(0).strip()
        if re.search(r"公開|発表|公表|リリース|登場|策定|提示|示され", sentence):
            return sentence
    return ""


def _reader_decision_fallback(decision_text: str) -> str:
    """内部Decision codeを公開せず、最小限の読者向け判断へ変換する。"""
    return {
        "NOW": "現時点で、具体的な導入・検証判断を進める価値があります。",
        "TRY": "まずは限定した環境で小さく試し、条件を確かめる価値があります。",
        "WATCH": "今は導入を急がず、追加Evidenceと今後の動きを追うのが妥当です。",
        "WAIT": "現時点では導入を急がず、条件とEvidenceが整うまで待つのが妥当です。",
        "AVOID": "現時点では採用を見送り、代替手段を優先するのが妥当です。",
    }.get((decision_text or "").strip().upper(), "")


def build_reader_first_summary(parsed: dict) -> dict[str, str]:
    """追加Gemini呼び出しなしで、Gate通過済みARTICLE/MANAGEMENT DATAから30秒要約を作る。"""
    parsed = parsed or {}
    draft = str(parsed.get("note_draft") or "")
    intro = _extract_any_markdown_section(draft, _display_heading_aliases("intro"))
    conclusion = _extract_any_markdown_section(draft, _display_heading_aliases("conclusion"))
    final = _extract_any_markdown_section(draft, _display_heading_aliases("final"))

    # Reader-firstの冒頭は「網羅性」より「理解速度」を優先する。
    # what_textが仕様IDや認証方式の列挙になった場合でも、新規生成はせず、
    # source_summary / 導入中の公開事実 / what_textの中から最も読みやすい既存文を選ぶ。
    what = _pick_reader_summary_candidate([
        parsed.get("source_summary_text", ""),
        _find_reader_intro_fact_sentence(intro),
        parsed.get("what_text", ""),
    ])
    why = _compact_reader_summary(parsed.get("why_important_text") or conclusion)
    decision = _compact_reader_summary(
        final or parsed.get("action_text") or parsed.get("decision_reason_text")
    )
    if not decision:
        decision = _reader_decision_fallback(str(parsed.get("decision_text") or ""))

    # Quality Retry等で内部コードが混入しても、公開ヘッダーには露出させない。
    decision_code_phrases = {
        "NOW": "今すぐ着手する", "TRY": "限定的に試す", "WATCH": "今後の動きを注視する",
        "WAIT": "条件が整うまで待つ", "AVOID": "現時点では採用を見送る",
    }
    if decision:
        decision, _ = _replace_public_decision_code_leaks(decision, decision_code_phrases)
        # 30秒要約は管理データと隣接するため、本文Gateより厳格に standalone code も全置換する。
        # 通常英単語の小文字/Title Caseは対象にせず、内部管理値と同じ大文字コードだけを扱う。
        for code, phrase in decision_code_phrases.items():
            decision = re.sub(rf"\b{code}\b", phrase, decision)
        decision = re.sub(r"\s{2,}", " ", decision).strip()

    return {"what": what, "why": why, "decision": decision}


def _reader_published_date(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(JST)
        return dt.date().isoformat()
    except ValueError:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
        return m.group(1) if m else ""


def build_reader_first_header(reader_summary: dict | None, repo_name: str, repo_url: str,
                              source: str = "GitHub", published_at: str | None = None) -> str:
    """タイトル直下へ置くReader-first header。詳細Evidence/権利表記は末尾に残す。"""
    summary = reader_summary or {}
    rows = [
        ("何が出た？", _compact_reader_summary(summary.get("what", ""))),
        ("なぜ重要？", _compact_reader_summary(summary.get("why", ""))),
        ("結論は？", _compact_reader_summary(summary.get("decision", ""))),
    ]
    rows = [(label, value) for label, value in rows if value]
    if not rows and not repo_url:
        return ""

    lines: list[str] = []
    if rows:
        lines.extend(["## 30秒でわかるこの記事", ""])
        for idx, (label, value) in enumerate(rows):
            if idx:
                lines.append("")
            lines.extend([f"**{label}**  ", value])

    if repo_url:
        if lines:
            lines.append("")
        lines.extend(["### 元情報", f"- **主一次情報**: [{repo_name}]({repo_url})"])
        lines.append(f"- **発見経路**: {_READER_SOURCE_LABELS.get(source, source)}")
        published = _reader_published_date(published_at)
        if published:
            lines.append(f"- **公開・更新**: {published}")
    return "\n".join(lines).strip()


def _remove_markdown_sections(markdown_text: str, headings: list[str]) -> str:
    """Reader-firstヘッダーと役割が重なる本文セクションだけを公開稿から除く。"""
    if not markdown_text or not headings:
        return markdown_text or ""
    alternatives = "|".join(re.escape(h) for h in sorted(set(headings), key=len, reverse=True))
    pattern = re.compile(
        rf"(?ms)^#{{2,6}}\s*(?:{alternatives})\s*$\n?.*?(?=^#{{2,6}}\s+|\Z)"
    )
    return pattern.sub("", markdown_text).strip()


def _remove_reader_redundant_provenance(markdown_text: str) -> str:
    """冒頭の元情報カードと重複する『本記事は一次情報に基づく』だけを削る。"""
    if not markdown_text:
        return ""
    pattern = re.compile(
        r"(?m)^[ \t]*(?:本記事|本稿|この記事)は、?[^\n。！？]{0,220}"
        r"(?:一次情報|公開情報|公式(?:ブログ|資料|ドキュメント|リポジトリ|情報))[^\n。！？]{0,160}"
        r"(?:基づいて|基づき|もとに)[^\n。！？]*[。！？][ \t]*$"
    )
    cleaned = pattern.sub("", markdown_text)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _prepare_reader_first_body(markdown_text: str, reader_summary: dict | None) -> str:
    """30秒ヘッダー導入時だけ、二重の出典説明と二重結論を公開本文から除く。"""
    body = markdown_text or ""
    if not reader_summary:
        return body
    body = _remove_reader_redundant_provenance(body)
    # 「先に判断」は30秒欄の『結論は？』と役割が完全に重なる。
    # 最終結論・Actionは残すため、情報価値を落とさず冒頭の反復だけを削る。
    body = _remove_markdown_sections(body, _display_heading_aliases("conclusion"))
    return body.strip()


def build_clean_note_manuscript(note_draft: str, repo_name: str, repo_url: str,
                                 spdx_id: str, source: str = "GitHub",
                                 evidence_urls: list[str] | None = None,
                                 title_text: str = "", discovery_url: str = "",
                                 reader_summary: dict | None = None,
                                 published_at: str | None = None) -> str:
    """note投稿用MarkdownをReader-first構造にし、詳細Evidenceは末尾へ二層化する。"""
    free_part, paid_part = split_free_paid(note_draft, repo_name)
    free_clean = normalize_markdown_for_note(free_part)
    paid_clean = normalize_markdown_for_note(paid_part)
    free_clean = _prepare_reader_first_body(free_clean, reader_summary)
    paid_clean = _prepare_reader_first_body(paid_clean, reader_summary)

    display_title = _normalize_note_title(title_text)
    manuscript_parts: list[str] = []
    if display_title:
        manuscript_parts.append(f"# {display_title}")
    reader_header = build_reader_first_header(reader_summary, repo_name, repo_url, source, published_at)
    if reader_header:
        manuscript_parts.append(reader_header)
    if free_clean:
        manuscript_parts.append(free_clean)
    if paid_clean:
        manuscript_parts.append(paid_clean)
    manuscript = "\n\n".join(manuscript_parts)

    if source == "GitHub":
        rights_line = (
            f"- **ライセンス**: {spdx_id}\n\n"
            f"※本記事はライセンスが公開・再利用可能な条件（MIT / Apache-2.0 / BSD / CC-BY-4.0等）"
            f"であることを確認した上で分析・要約しています。\n"
        )
    else:
        rights_line = SOURCE_RIGHTS_NOTE.get(source, "")

    source_label = _READER_SOURCE_LABELS.get(source, source)
    source_block = (
        f"{DIVIDER_LINE}"
        f"### Sources / Evidence\n"
        f"- **発見経路**: {source_label}\n"
        f"- **主一次情報**: [{repo_name}]({repo_url})\n"
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
        source_block += "\n### 補助Evidence\n" + "\n".join(f"- {u}" for u in unique_evidence) + "\n"
    if discovery_url and discovery_url != repo_url:
        source_block += f"- **関連情報**: 発見元の[{source}投稿]({discovery_url})\n"

    article_id = build_article_attribution_id(source, repo_url)
    tracking_url = build_subscription_tracking_url(article_id)
    subscription_cta = build_subscription_cta(article_id, tracking_url)
    if subscription_cta:
        manuscript += "\n\n" + subscription_cta
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


def _extract_eyecatch_score_components(score_breakdown_text: str) -> tuple[int | None, int | None]:
    """Extract the two approved eyecatch sub-scores from MANAGEMENT DATA.

    The Deep Dive rubric is the source of truth:
      Technical Impact X/25; Urgency X/20
    No extra model call or score recomputation is allowed. Missing/malformed values return None.
    """
    text = str(score_breakdown_text or "")
    tech = re.search(r"Technical\s*Impact\s*[:：]?\s*(\d{1,2})\s*/\s*25", text, re.IGNORECASE)
    urgency = re.search(r"Urgency\s*[:：]?\s*(\d{1,2})\s*/\s*20", text, re.IGNORECASE)
    tech_value = int(tech.group(1)) if tech else None
    urgency_value = int(urgency.group(1)) if urgency else None
    if tech_value is not None and not 0 <= tech_value <= 25:
        tech_value = None
    if urgency_value is not None and not 0 <= urgency_value <= 20:
        urgency_value = None
    return tech_value, urgency_value


def _eyecatch_score_color(score: int | float | None) -> tuple[int, int, int]:
    """Return the approved Decision Score band color (RGB).

    Color is a visual intensity cue, not Adoption Status semantics. Red is
    intentionally reserved for future AVOID / warning communication.
    """
    try:
        value = max(0, min(100, int(score or 0)))
    except (TypeError, ValueError):
        value = 0
    if value <= 59:
        return (100, 116, 139)  # Slate Gray #64748B
    if value <= 69:
        return (34, 211, 238)   # Cyan       #22D3EE
    if value <= 79:
        return (59, 130, 246)   # Blue       #3B82F6
    if value <= 89:
        return (139, 92, 246)   # Purple     #8B5CF6
    return (245, 185, 66)       # Gold       #F5B942


def _eyecatch_vertical_center_shift(container_bounds: tuple[int, int],
                                    content_bounds: tuple[int, int]) -> int:
    """Return the integer Y shift that optically centers content in a container.

    Bounds are visual top/bottom coordinates, not font baselines.  This keeps
    eyecatch placement stable across CJK/Lato font metric differences.
    """
    container_top, container_bottom = container_bounds
    content_top, content_bottom = content_bounds
    container_center = (float(container_top) + float(container_bottom)) / 2.0
    content_center = (float(content_top) + float(content_bottom)) / 2.0
    return int(round(container_center - content_center))


def _draw_eyecatch_text_stack_centered(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
                                        rows: list[tuple[str, object, tuple[int, int, int, int]]],
                                        gaps: tuple[int, ...]) -> tuple[int, int, int, int]:
    """Draw a multi-line text group centered by its *visible* glyph bounds.

    Pillow's text origin is a font baseline/anchor reference and differs between
    Noto CJK and Lato.  Centering each line by its origin therefore makes the
    lower score cards look vertically low.  This helper measures each line with
    ``textbbox`` first, then centers the complete visible stack inside ``box``.
    """
    if len(gaps) != max(0, len(rows) - 1):
        raise ValueError("gaps must contain exactly len(rows)-1 values")
    if not rows:
        return box

    metrics = []
    for text, font, fill in rows:
        bbox = draw.textbbox((0, 0), text, font=font)
        metrics.append((text, font, fill, bbox, bbox[2] - bbox[0], bbox[3] - bbox[1]))

    total_height = sum(item[5] for item in metrics) + sum(gaps)
    box_center_y = (box[1] + box[3]) / 2.0
    cursor_top = box_center_y - total_height / 2.0
    box_center_x = (box[0] + box[2]) / 2.0

    visible_bounds = []
    for index, (text, font, fill, bbox, width, height) in enumerate(metrics):
        x = int(round(box_center_x - (bbox[0] + bbox[2]) / 2.0))
        y = int(round(cursor_top - bbox[1]))
        draw.text((x, y), text, font=font, fill=fill)
        visible_bounds.append((x + bbox[0], y + bbox[1], x + bbox[2], y + bbox[3]))
        cursor_top += height
        if index < len(gaps):
            cursor_top += gaps[index]

    return (
        min(b[0] for b in visible_bounds),
        min(b[1] for b in visible_bounds),
        max(b[2] for b in visible_bounds),
        max(b[3] for b in visible_bounds),
    )


def _eyecatch_centered_pair_boxes(container: tuple[int, int, int, int],
                                  top: int, bottom: int, box_width: int, gap: int) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Return two equal-width lower metric boxes centered as a pair inside ``container``.

    The previous implementation hard-coded x coordinates, which left the pair
    6px right of the card center.  This helper derives both boxes from the
    container center so the left/right margins are always equal.
    """
    container_center_x = (container[0] + container[2]) / 2.0
    group_width = box_width * 2 + gap
    left_x0 = int(round(container_center_x - group_width / 2.0))
    left_x1 = left_x0 + box_width
    right_x0 = left_x1 + gap
    right_x1 = right_x0 + box_width
    return (left_x0, top, left_x1, bottom), (right_x0, top, right_x1, bottom)


def generate_eyecatch_image(title_text: str, output_path: str = "eyecatch.png",
                             source: str = "GitHub", decision_score: int | None = None,
                             technical_impact: int | None = None, urgency: int | None = None,
                             article_ready: bool = True) -> str | None:
    """Generate the approved 1280x670 Decision Score card over the source background.

    Final visual contract (2026-08-22):
    - article title is intentionally NOT rendered; note already shows it separately
    - main KPI: 意思決定スコア (Decision Score) X/100
    - lower cards: 技術的破壊力 (Technical Impact) X/25 and 緊急度 (Urgency) X/20
    - all numeric scores use Google Font Lato Bold (fonts-lato installed in GitHub Actions)
    - outer content group is centered from actual visible glyph bounds, not font baselines
    - lower metric text stacks are vertically centered inside each frame by measured textbbox bounds
    - progress color follows five Decision Score bands (gray/cyan/blue/purple/gold)
    - eligibility is Article Ready, never a score threshold
    """
    if not article_ready:
        logger.info("[EYECATCH SKIP] article is not Ready")
        return None
    WIDTH, HEIGHT = 1280, 670

    img = _load_eyecatch_background(source, WIDTH, HEIGHT)
    if img is None:
        img = Image.new("RGB", (WIDTH, HEIGHT), color=(10, 15, 28))
        draw_bg = ImageDraw.Draw(img)
        for y in range(HEIGHT):
            r = int(10 + (y / HEIGHT) * 15)
            g = int(15 + (y / HEIGHT) * 25)
            b = int(28 + (y / HEIGHT) * 45)
            draw_bg.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    score = max(0, min(100, int(decision_score or 0)))
    tech = None if technical_impact is None else max(0, min(25, int(technical_impact)))
    urg = None if urgency is None else max(0, min(20, int(urgency)))

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Larger card and wider breathing room than the first implementation.
    # The content block below is vertically balanced around the card's optical center.
    card = (60, 78, 770, 592)
    draw.rounded_rectangle(card, radius=27, fill=(3, 13, 28, 205), outline=(205, 220, 239, 225), width=2)

    japanese_font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    lato_bold_paths = [
        "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
        "/usr/share/fonts/truetype/lato/Lato-Heavy.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]

    def text_font(size: int):
        for path in japanese_font_paths:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def number_font(size: int):
        for path in lato_bold_paths:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
        return ImageFont.load_default()

    white = (250, 252, 255, 255)
    soft = (235, 241, 250, 255)
    border = (190, 207, 229, 225)
    accent = (*_eyecatch_score_color(score), 255)
    bar_bg = (56, 70, 91, 235)

    def centered(text: str, cx: int, y: int, fnt, fill=white):
        b = draw.textbbox((0, 0), text, font=fnt)
        # Account for non-zero left bearing so the *visible* glyphs are centered.
        draw.text((cx - (b[0] + b[2]) / 2, y), text, font=fnt, fill=fill)

    # Build the original composition, then calculate the shift from the actual
    # visible title top to the lower-card bottom.  Noto CJK's top bearing makes
    # the previous baseline-based layout appear about 10px too low.
    title_label = "意思決定スコア  (Decision Score)"
    title_fnt = text_font(35)
    title_bbox = draw.textbbox((0, 0), title_label, font=title_fnt)
    nominal_title_y = 132
    nominal_lower_box_bottom = 548
    content_shift_y = _eyecatch_vertical_center_shift(
        (card[1], card[3]),
        (nominal_title_y + title_bbox[1], nominal_lower_box_bottom),
    )

    centered(title_label, 415, nominal_title_y + content_shift_y, title_fnt)

    score_text = f"{score}/100"
    centered(score_text, 415, 204 + content_shift_y, number_font(88))

    # Progress bar with generous vertical separation from the main number.
    bx0, by0, bx1, by1 = 108, 318 + content_shift_y, 722, 360 + content_shift_y
    draw.rounded_rectangle((bx0, by0, bx1, by1), radius=11, fill=bar_bg)
    progress_x = bx0 + int((bx1 - bx0) * score / 100)
    if progress_x > bx0:
        draw.rounded_rectangle((bx0, by0, progress_x, by1), radius=11, fill=accent)

    # Lower metric cards move with the outer content group.  Their text is not
    # placed at fixed baselines: each three-line stack is measured and centered
    # by visible glyph bounds inside its own card.
    left_box, right_box = _eyecatch_centered_pair_boxes(
        card,
        395 + content_shift_y,
        548 + content_shift_y,
        box_width=314,
        gap=18,
    )
    draw.rounded_rectangle(left_box, radius=18, fill=(2, 13, 29, 126), outline=border, width=2)
    draw.rounded_rectangle(right_box, radius=18, fill=(2, 13, 29, 126), outline=border, width=2)

    _draw_eyecatch_text_stack_centered(
        draw, left_box,
        [
            ("技術的破壊力", text_font(29), white),
            ("(Technical Impact)", text_font(19), soft),
            (f"{tech if tech is not None else '—'}/25", number_font(50), white),
        ],
        gaps=(8, 16),
    )
    _draw_eyecatch_text_stack_centered(
        draw, right_box,
        [
            ("緊急度", text_font(29), white),
            ("(Urgency)", text_font(19), soft),
            (f"{urg if urg is not None else '—'}/20", number_font(50), white),
        ],
        gaps=(8, 16),
    )

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
        # note本文の無料/有料区分と、会員向けNotion DBの可視性は別責務。
        # Readyでも内部Notion資産はSubscriber Onlyを維持する。
        PROP_SUBSCRIPTION_VISIBILITY: {"select": {"name": VISIBILITY_SUBSCRIBER_ONLY}},
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



def build_notion_manuscript_children(clean_manuscript: str, caption: str = MANUSCRIPT_CAPTION_READY) -> list:
    """Markdown原稿を1つのcodeブロックとして保存するchildrenを組み立てる。

    captionでReady原稿とNeeds Editorial Review原稿を識別する。旧版でcaptionが
    付いていないMarkdown codeブロックはReady互換として扱う。
    """
    chunks = safe_chunk_text(clean_manuscript)
    return [
        {
            "object": "block",
            "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": chunk}} for chunk in chunks],
                "language": "markdown",
                "caption": [{"type": "text", "text": {"content": caption}}],
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
                                      source_summary: str = "",
                                      spdx_id: str = "") -> dict:
    """Screening通過時の購読者向けStock metadata。Step1評価を永久保存する。

    GitHub案件はspdx_idをPROP_LICENSEへ保存しておくことで、Pending Retry後の
    normalize_item()復元時にlicenseInfoが失われ、既に安全確認済みのGitHub案件が
    NO_LICENSE扱いへ変化することを防ぐ（Legal Safety Gate自体は変更しない）。"""
    props = {
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
    if spdx_id:
        props[PROP_LICENSE] = {"rich_text": [{"text": {"content": spdx_id[:2000]}}]}
    return props



def save_screening_metadata_to_notion(repo, score: int, reason: str) -> str | None:
    """スクリーニングスコアがNOTION_SAVE_THRESHOLD_SCORE以上の案件を、
    詳細記事化するか否かに関わらずメタデータのみで全件Notion DBへ保存する。
    Notion DB自体を「検索可能なストック資産」として蓄積するための入口。

    戻り値: 作成に成功した場合はNotionページID（後で深掘り時にアップグレード
    更新するために使う）。失敗時・Notion未設定時はNone。"""
    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID):
        return None

    name = repo.get("nameWithOwner")
    display_name = _notion_display_name(repo)
    repo_url = repo.get("url")
    source = repo.get("source", "GitHub")
    engagement = repo.get("stargazerCount", 0)
    published_at = repo.get("publishedAt")
    # Analyzed At = このスクリーニング（Step1軽量分析）を実行した「いま」。
    analyzed_at = _analyzed_at_now_iso()
    # GitHub案件のみLegal Safety Gateで確認済みのSPDX IDを保持する。
    spdx_id = (repo.get("licenseInfo") or {}).get("spdxId", "") if source == "GitHub" else ""

    url = "https://api.notion.com/v1/pages"
    headers = _notion_headers()
    payload = {
        "parent": _notion_parent(),
        "properties": build_metadata_notion_properties(
            display_name, repo_url, score, reason, source, engagement,
            published_at, analyzed_at, _source_summary_with_original(repo, repo.get("description", "")),
            spdx_id,
        ),
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            page_id = res.json().get("id")
            logger.info(f"[NOTION STOCK SAVED] {display_name}: {score}点 -> メタデータのみでストックDBへ保存（page_id={page_id}）")
            return page_id
        logger.error(f"[NOTION STOCK ERROR] {name} -> {res.text}")
        return None
    except Exception as e:
        logger.error(f"[NOTION STOCK EXCEPTION] {name}: {e}")
        return None


def _notion_code_caption(block: dict) -> str:
    code = block.get("code") or {}
    parts = []
    for item in code.get("caption") or []:
        parts.append(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
    return "".join(parts)


def _notion_page_manuscript_blocks(page_id: str, headers: dict) -> list[dict]:
    """ページ直下のMarkdown manuscript blockを取得。取得失敗時は空配列。"""
    try:
        res = requests.get(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=headers, timeout=10,
        )
        if res.status_code != 200:
            return []
        return [
            block for block in res.json().get("results", [])
            if block.get("type") == "code" and (block.get("code") or {}).get("language") == "markdown"
        ]
    except Exception:
        return []


def _notion_page_has_manuscript_child(page_id: str, headers: dict) -> bool:
    """Ready manuscriptの二重append防止。Review原稿はReady原稿とみなさない。

    caption無しの旧Markdown manuscriptは後方互換のためReady扱いする。
    """
    for block in _notion_page_manuscript_blocks(page_id, headers):
        caption = _notion_code_caption(block)
        if caption != MANUSCRIPT_CAPTION_REVIEW:
            return True
    return False


def _notion_review_manuscript_block_ids(page_id: str, headers: dict) -> list[str]:
    return [
        block.get("id") for block in _notion_page_manuscript_blocks(page_id, headers)
        if block.get("id") and _notion_code_caption(block) == MANUSCRIPT_CAPTION_REVIEW
    ]


def _rollback_notion_manuscript_children(block_ids: list[str], repo_name: str, headers: dict) -> None:
    """children PATCH成功後にproperties PATCHが失敗した場合のbest-effort後始末。

    今回のPhase 1で新規追加したblockだけをarchive（削除）し、次回試行が
    冪等性チェック（_notion_page_has_manuscript_child）と矛盾しないようにする。
    archiveに失敗しても例外は上げない。ここが失敗しても、
    _notion_page_has_manuscript_childによる次回appendスキップが最後の砦として
    二重化を防ぐ。"""
    for block_id in block_ids:
        try:
            res = requests.delete(
                f"https://api.notion.com/v1/blocks/{block_id}",
                headers=headers, timeout=10,
            )
            if res.status_code != 200:
                logger.error(f"[NOTION UPGRADE ROLLBACK ERROR] {repo_name} block={block_id} -> {res.text}")
        except Exception as e:
            logger.error(f"[NOTION UPGRADE ROLLBACK EXCEPTION] {repo_name} block={block_id}: {e}")


def _mark_pending_retry_or_escalate(page_id: str, repo_name: str, reason: str) -> None:
    """properties commit失敗後にPending Retryへ更新するが、その更新自体が
    失敗した場合はNotion側の状態が中途半端（children rollbackは試行済みだが
    Content/Article Statusは更新前のまま）になり得るため、Telegramで
    運用者へ即エスカレーションする。ここではQuality Failed/Readyへの変更は
    一切行わない（upgrade_notion_page_with_report自体は引き続きFalseを返す）。"""
    pending_retry_saved = update_notion_pending_retry(page_id, repo_name, reason)
    if not pending_retry_saved:
        logger.error(
            f"[NOTION PERSISTENCE RECOVERY FAILED] {repo_name} -> "
            f"Notion persistence失敗後、Pending Retry状態への保存にも失敗（page_id={page_id}）"
        )
        send_telegram_alert(
            f"🔴 Notion persistence失敗後、Pending Retry状態への保存にも失敗したため要手動確認: {repo_name}"
        )


def upgrade_notion_page_with_report(page_id: str, repo_name, repo_url, score, score_breakdown_text,
                                     what_text, why_important_text, why_not_important_text,
                                     action_text, spdx_id, clean_manuscript, paradigm_shift_text="",
                                     alternative_comparison_text="", migration_cost_text="",
                                     source: str = "GitHub", engagement: int = 0, title_text: str = "",
                                     eyecatch_url: str = "", published_at: str | None = None,
                                     analyzed_at: str | None = None, report_meta: dict | None = None,
                                     screening_score: int | None = None, screening_reason: str = "") -> bool:
    """Stock済みNotionページをDeep Diveへアップグレード。Step1履歴は保持する。

    Phase 1で記事本文(children)を先に保存し、Phase 2でchildren保存成功後にのみ
    properties（Content/Article Status = Deep Dive/Readyを含む）をcommitする。
    これにより「properties成功・children失敗」による
    『Article Status = Ready なのに本文がNotionに存在しない』不整合を防ぐ。
    children保存に失敗した場合はpropertiesへ一切触れず、ページは更新前の
    安全な状態（既存のContent/Article Status）のまま残る。

    Phase 1成功後にPhase 2（properties）が失敗した場合（= 本文だけ追加されて
    しまいステータスがReady/Deep Diveに更新されない不整合状態）は、
    (1) 今回追加したchildren blockをbest-effortでrollback（archive）し、
    (2) ページをPending Retryへ更新し、次回get_pending_retry_items()から
        自動的に復元・再試行されるようにする。
    rollbackが失敗した場合に備え、Phase 1の冒頭で「既にmanuscript child
    （markdown codeブロック）が存在するか」を確認し、存在すればre-appendを
    スキップする冪等性チェックを入れており、Retry時の本文二重化を防ぐ。"""
    if not NOTION_API_KEY:
        return False
    headers = _notion_headers()

    # Phase 1: 記事children（本文）を先に保存する。
    # 冪等性チェック: 前回試行でrollbackに失敗し、既にmanuscript childが
    # 残っている場合はre-appendしない（本文の二重化防止）。
    appended_block_ids: list[str] = []
    if _notion_page_has_manuscript_child(page_id, headers):
        logger.info(f"[NOTION UPGRADE CHILDREN SKIPPED] {repo_name} -> 既にmanuscript childが存在するためre-appendをスキップ")
    else:
        children = build_notion_manuscript_children(clean_manuscript)
        try:
            res_children = requests.patch(
                f"https://api.notion.com/v1/blocks/{page_id}/children",
                json={"children": children}, headers=headers, timeout=10,
            )
            if res_children.status_code != 200:
                logger.error(f"[NOTION UPGRADE CHILDREN ERROR] {repo_name} -> {res_children.text}")
                return False
            appended_block_ids = [b["id"] for b in res_children.json().get("results", []) if b.get("id")]
        except Exception as e:
            logger.error(f"[NOTION UPGRADE CHILDREN EXCEPTION] {repo_name}: {e}")
            return False

    # Phase 2: children保存成功（またはスキップ）後にのみ、
    # properties（Deep Dive / Readyへのcommit）を行う。
    properties = build_notion_properties(
        repo_name, repo_url, score, score_breakdown_text, what_text,
        why_important_text, why_not_important_text, action_text,
        spdx_id, paradigm_shift_text, alternative_comparison_text,
        migration_cost_text, source, engagement, title_text, eyecatch_url,
        published_at, analyzed_at, report_meta, screening_score, screening_reason,
    )
    try:
        res_props = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            json={"properties": properties}, headers=headers, timeout=10,
        )
        if res_props.status_code != 200:
            logger.error(f"[NOTION UPGRADE PROPERTIES ERROR] {repo_name} -> {res_props.text}")
            if appended_block_ids:
                _rollback_notion_manuscript_children(appended_block_ids, repo_name, headers)
            _mark_pending_retry_or_escalate(page_id, repo_name, "Notion properties commit failed after children saved")
            return False
        logger.info(f"[NOTION READY COMMITTED] {repo_name} -> Deep Diveへアップグレード完了")
        # Readyへ昇格した後は、過去のNeeds Editorial Review原稿だけをbest-effortで整理する。
        review_block_ids = _notion_review_manuscript_block_ids(page_id, headers)
        if review_block_ids:
            _rollback_notion_manuscript_children(review_block_ids, repo_name, headers)
        return True
    except Exception as e:
        logger.error(f"[NOTION UPGRADE PROPERTIES EXCEPTION] {repo_name}: {e}")
        if appended_block_ids:
            _rollback_notion_manuscript_children(appended_block_ids, repo_name, headers)
        _mark_pending_retry_or_escalate(page_id, repo_name, "Notion properties commit exception after children saved")
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
    """Transient provider failures must never be recorded as Quality Failed.

    Screening ReasonはStep1 Screening評価の永久保存値であり、Pending Retryの
    理由で上書きしてはならない。Retry理由はログにのみ残し、Notionプロパティは
    Content/Article Statusのみ更新する。"""
    if not page_id or not NOTION_API_KEY:
        return False
    props = {
        PROP_CONTENT_STATUS: {"select": {"name": CONTENT_STATUS_PENDING_RETRY}},
        PROP_ARTICLE_STATUS: {"select": {"name": ARTICLE_STATUS_NOT_PLANNED}},
    }
    if reason:
        logger.info("[NOTION PENDING RETRY REASON] %s: %s", repo_name, reason[:500])
    try:
        res = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", json={"properties": props}, headers=_notion_headers(), timeout=10)
        if res.status_code == 200:
            logger.info("[NOTION PENDING RETRY] %s", repo_name)
            return True
        logger.error("[NOTION PENDING RETRY ERROR] %s -> %s", repo_name, res.text)
    except Exception as exc:
        logger.error("[NOTION PENDING RETRY EXCEPTION] %s: %s", repo_name, exc)
    return False


def persist_notion_needs_editorial_review(page_id: str, repo_name: str, clean_manuscript: str,
                                             properties: dict, reasons: list[str]) -> bool:
    """Needs Editorial Review原稿を内部Notion DBへ保存する。公開はしない。

    Review原稿childrenを先に保存し、その後にStatus=Deep Dive / Content Status=Deep Dive /
    Article Status=Needs Editorial Review / Subscription Visibility=Subscriber Onlyをcommitする。
    Review StatusはPublic Approvedへ変更しないためpublic-db-sync対象にはならない。
    """
    if not page_id or not NOTION_API_KEY:
        return False
    headers = _notion_headers()
    existing_review_ids = _notion_review_manuscript_block_ids(page_id, headers)
    appended_block_ids: list[str] = []
    # Review再生成では古い本文を使い回さない。新稿を先にappendし、properties commit成功後に
    # 旧Review blockをarchiveすることで、append/commit失敗時にも旧原稿を失わない。
    try:
        res_children = requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            json={"children": build_notion_manuscript_children(clean_manuscript, MANUSCRIPT_CAPTION_REVIEW)},
            headers=headers, timeout=10,
        )
        if res_children.status_code != 200:
            logger.error(f"[NOTION EDITORIAL REVIEW CHILDREN ERROR] {repo_name} -> {res_children.text}")
            return False
        appended_block_ids = [b["id"] for b in res_children.json().get("results", []) if b.get("id")]
    except Exception as exc:
        logger.error(f"[NOTION EDITORIAL REVIEW CHILDREN EXCEPTION] {repo_name}: {exc}")
        return False

    review_props = dict(properties)
    review_props[PROP_STATUS] = {"select": {"name": STATUS_DEEP_DIVE}}
    review_props[PROP_CONTENT_STATUS] = {"select": {"name": CONTENT_STATUS_DEEP_DIVE}}
    review_props[PROP_ARTICLE_STATUS] = {"select": {"name": ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW}}
    review_props[PROP_SUBSCRIPTION_VISIBILITY] = {"select": {"name": VISIBILITY_SUBSCRIBER_ONLY}}
    review_props.pop(PROP_REVIEW_STATUS, None)  # Public Approvedへは絶対に変更しない
    if reasons:
        logger.info("[NOTION EDITORIAL REVIEW REASON] %s: %s", repo_name, ", ".join(reasons)[:500])
    try:
        res_props = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            json={"properties": review_props}, headers=headers, timeout=10,
        )
        if res_props.status_code == 200:
            # 新Review稿のcommit後に旧Review稿だけをbest-effortで整理する。
            if existing_review_ids:
                _rollback_notion_manuscript_children(existing_review_ids, repo_name, headers)
            logger.info("[NOTION EDITORIAL REVIEW STORED] %s -> manuscript + internal review state", repo_name)
            return True
        logger.error("[NOTION EDITORIAL REVIEW PROPERTIES ERROR] %s -> %s", repo_name, res_props.text)
    except Exception as exc:
        logger.error("[NOTION EDITORIAL REVIEW PROPERTIES EXCEPTION] %s: %s", repo_name, exc)
    if appended_block_ids:
        _rollback_notion_manuscript_children(appended_block_ids, repo_name, headers)
    _mark_pending_retry_or_escalate(page_id, repo_name, "Notion editorial review persistence failed")
    return False


def update_notion_needs_editorial_review(page_id: str, repo_name: str, reasons: list[str]) -> bool:
    """事実誤認とは分離し、公開だけを止めてStock資産を編集レビューへ回す。

    Screening ReasonはStep1 Screening評価の永久保存値であり、Publication Review
    理由で上書きしてはならない。Review理由はログにのみ残す。"""
    if not page_id or not NOTION_API_KEY:
        return False
    props = {
        PROP_STATUS: {"select": {"name": STATUS_DEEP_DIVE}},
        PROP_CONTENT_STATUS: {"select": {"name": CONTENT_STATUS_DEEP_DIVE}},
        PROP_ARTICLE_STATUS: {"select": {"name": ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW}},
        PROP_SUBSCRIPTION_VISIBILITY: {"select": {"name": VISIBILITY_SUBSCRIBER_ONLY}},
    }
    if reasons:
        logger.info("[NOTION EDITORIAL REVIEW REASON] %s: %s", repo_name, ", ".join(reasons)[:500])
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


def _detect_title_language(title: str) -> str:
    """追加APIなしでDB表示用の大まかな原文言語を判定する。

    Entity ResolutionやDedupには使わない。日本語かなを含む場合はja、
    Hanのみはzh-CN、Hangulはko、Cyrillicはru系として扱い、英数字中心はen。
    """
    text = unicodedata.normalize("NFKC", title or "")
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh-CN"
    if re.search(r"[\u0400-\u04ff]", text):
        return "ru"
    if re.search(r"[A-Za-z]", text):
        return "en"
    return "und"


def _japanese_product_descriptor(description: str, source: str) -> str:
    """英語tagline/descriptionから0 APIで短い日本語カテゴリ名を付ける。

    翻訳を捏造せず、十分なキーワードがある場合だけ具体化する。
    """
    text = unicodedata.normalize("NFKC", description or "").casefold()
    rules = [
        (("ecommerce", "e-commerce", "product photo", "product image", "listing image"), "EC商品画像生成ツール"),
        (("image generator", "generate images", "image generation", "photo generator"), "AI画像生成ツール"),
        (("video generator", "video generation", "generate videos"), "AI動画生成ツール"),
        (("agent", "agentic", "multi-agent", "ai agent"), "AIエージェントツール"),
        (("developer tool", "devtool", "coding", "code generation", "api"), "開発支援ツール"),
        (("analytics", "analysis", "dashboard", "business intelligence"), "データ分析ツール"),
        (("voice", "speech", "text-to-speech", "tts"), "音声AIツール"),
    ]
    for keywords, label in rules:
        if any(k in text for k in keywords):
            return label
    return "海外プロダクト" if source == "ProductHunt" else "海外技術情報"


def _multilingual_display_name(original_title: str, description: str = "", source: str = "") -> tuple[str, str]:
    """原題を壊さず、人間がDB一覧で判別しやすい表示名を返す。

    英語・日本語タイトルは従来表示を維持する。中国語/韓国語/Cyrillic等だけ、
    日本語カテゴリ + 原題の形にするため、誤訳によるEntity誤マージを防ぐ。
    """
    original = unicodedata.normalize("NFKC", (original_title or "無題").strip()) or "無題"
    lang = _detect_title_language(original)
    if lang in {"ja", "en"} or lang == "und":
        return original, lang
    descriptor = _japanese_product_descriptor(description, source)
    return f"{descriptor}「{original}」", lang


def _notion_display_name(repo: dict) -> str:
    return (repo.get("displayName") or repo.get("nameWithOwner") or "無題").strip() or "無題"


def _source_summary_with_original(repo: dict, summary: str) -> str:
    """非英語タイトルの原題・言語を既存Source Summaryへ非破壊で残す。"""
    original = (repo.get("originalTitle") or repo.get("nameWithOwner") or "").strip()
    lang = (repo.get("sourceLanguage") or _detect_title_language(original)).strip()
    body = (summary or "").strip()
    if lang in {"ja", "en", "und", ""}:
        return body
    prefix = f"Original Title: {original}\nLanguage: {lang}"
    return (prefix + ("\n" + body if body else ""))[:2000]


def normalize_item(source: str, name: str, url: str, description: str,
                    engagement: int, license_info: dict | None = None,
                    published_at: str | None = None, source_context: str = "",
                    primary_url: str | None = None, source_details: dict | None = None) -> dict:
    """各ソースを既存互換キーへ正規化し、Deep Dive用一次コンテキストも保持する。

    nameWithOwnerは原題のまま保持し、Entity Resolution/Dedupの正本とする。
    displayNameだけをNotion等の人間向け表示に利用する。
    """
    original = unicodedata.normalize("NFKC", (name or "無題").strip()) or "無題"
    desc = (description or "説明なし").strip() or "説明なし"
    display_name, language = _multilingual_display_name(original, desc, source)
    return {
        "source": source,
        "nameWithOwner": original,
        "originalTitle": original,
        "displayName": display_name,
        "sourceLanguage": language,
        "url": (url or "").strip(),
        "description": desc,
        "stargazerCount": engagement or 0,
        "licenseInfo": license_info,
        "publishedAt": published_at,
        "sourceContext": (source_context or "").strip(),
        "primaryUrl": (primary_url or url or "").strip(),
        "sourceDetails": source_details or {},
    }


def _truncate_text_context(text: str, max_chars: int) -> str:
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    return text[:max(0, int(max_chars or 0))]


def _truncate_source_context(text: str) -> str:
    return _truncate_text_context(text, SOURCE_CONTEXT_MAX_CHARS)


def _verification_excerpt(text: str, max_chars: int) -> str:
    """長い一次資料の冒頭だけでなく末尾のLimitations/Appendixも残す。"""
    normalized = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    limit = max(0, int(max_chars or 0))
    if len(normalized) <= limit:
        return normalized
    if limit <= 64:
        return normalized[:limit]
    marker = "\n\n[...verification context omitted...]\n\n"
    payload = max(0, limit - len(marker))
    # Method/Abstractを厚めに残しつつ、末尾のLimitations/Appendixも必ず監査対象へ入れる。
    head = int(payload * 0.68)
    tail = payload - head
    return normalized[:head] + marker + normalized[-tail:]


def _truncate_verification_context(text: str) -> str:
    """Fact/Evidence照合専用。Geminiへ送るprompt contextとは分離して広く保持する。"""
    return _verification_excerpt(text, VERIFICATION_CONTEXT_MAX_CHARS)


def _merge_verification_context(existing: str, new_evidence: str) -> str:
    """既存Evidenceが長くても、後から取得したPDF/Docsをverificationから落とさない。

    単純な `existing + new` の先頭truncateでは、Landing pageが上限を埋めた時に
    後取得の論文PDFが丸ごと消える。新Evidenceへ最低限の監査枠を確保し、双方の
    冒頭/末尾を残してFact Gateへ渡す。
    """
    old = re.sub(r"\n{3,}", "\n\n", (existing or "").strip())
    new = re.sub(r"\n{3,}", "\n\n", (new_evidence or "").strip())
    if not old:
        return _truncate_verification_context(new)
    if not new:
        return _truncate_verification_context(old)
    separator = "\n\n"
    limit = VERIFICATION_CONTEXT_MAX_CHARS
    if len(old) + len(separator) + len(new) <= limit:
        return old + separator + new
    payload = max(0, limit - len(separator))
    # 後取得のPDF/Docsは一次根拠として重要なため60%まで優先。ただし短い場合は
    # 余った枠を既存Landing/Abstractへ戻す。
    new_budget = min(len(new), int(payload * 0.60))
    old_budget = payload - new_budget
    if len(old) < old_budget:
        extra = old_budget - len(old)
        old_budget = len(old)
        new_budget = min(len(new), new_budget + extra)
    return _verification_excerpt(old, old_budget) + separator + _verification_excerpt(new, new_budget)


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


def _github_repo_name_from_url(url: str) -> str:
    """Return owner/repo only for a concrete GitHub repository URL."""
    try:
        parsed = urlparse(url or "")
    except Exception:
        return ""
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    if host not in {"github.com", "www.github.com"}:
        return ""
    parts = [x for x in (parsed.path or "").split("/") if x]
    if len(parts) < 2:
        return ""
    if parts[0].lower() in {"features", "enterprise", "pricing", "solutions", "marketplace", "topics", "collections", "sponsors", "login", "signup", "settings", "organizations"}:
        return ""
    return f"{parts[0]}/{parts[1]}"


def _github_repo_identity(repo: dict) -> str:
    entity_id = str(repo.get("canonicalEntityId") or repo.get("canonical_entity_id") or "")
    if entity_id.lower().startswith("github:") and "/" in entity_id.split(":", 1)[1]:
        return entity_id.split(":", 1)[1]
    for value in (repo.get("primaryUrl"), repo.get("url")):
        name = _github_repo_name_from_url(str(value or ""))
        if name:
            return name
    name = str(repo.get("nameWithOwner") or "").strip()
    return name if "/" in name and not name.startswith(("http://", "https://")) else ""


def _is_github_global_navigation_url(url: str) -> bool:
    """Reject GitHub site-wide navigation that can be mistaken for project evidence."""
    try:
        parsed = urlparse(url or "")
    except Exception:
        return False
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    if host not in {"github.com", "www.github.com"}:
        return False
    path = (parsed.path or "/").lower()
    blocked = (
        "/features/", "/enterprise", "/pricing", "/solutions/", "/marketplace",
        "/topics/", "/collections/", "/sponsors", "/login", "/signup", "/settings",
        "/organizations/enterprise", "/customer-stories/",
    )
    return any(path == x.rstrip("/") or path.startswith(x) for x in blocked)


def _extract_markdown_evidence_links(text: str) -> list[tuple[str, str]]:
    """Extract only explicit docs/source links from README-like Markdown.

    Badge destinations, social links and arbitrary dependency repositories are intentionally
    ignored. This is a zero-API candidate list; retrieval still happens later under the
    evidence-document caps.
    """
    if not text:
        return []
    keywords = re.compile(r"\b(?:docs?|documentation|guide|reference|api|website|homepage|source\s*code|repository|github)\b", re.I)
    out: list[tuple[str, str]] = []
    for m in re.finditer(r"(?<!!)\[([^\]]{1,120})\]\((https?://[^\s\)]+)", text):
        label, url = m.group(1).strip(), urldefrag(m.group(2).strip())[0]
        if not keywords.search(label) and not keywords.search(urlparse(url).path or ""):
            continue
        host = (urlparse(url).netloc or "").lower()
        if any(x in host for x in ("shields.io", "badge", "twitter.com", "x.com", "discord.gg", "linkedin.com")):
            continue
        if _is_github_global_navigation_url(url):
            continue
        out.append((url, label))
    return list(dict.fromkeys(out))[:12]


def fetch_github_repository_metadata_context(repo_name: str) -> tuple[str, dict]:
    """Fetch current repository metadata from the GitHub REST API without Gemini."""
    if not repo_name or "/" not in repo_name:
        return "", {}
    api_url = f"https://api.github.com/repos/{repo_name}"
    headers = {
        "Authorization": f"Bearer {GH_PAT}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        res = requests.get(api_url, headers=headers, timeout=15)
        if res.status_code != 200:
            logger.warning("[SOURCE CONTEXT] GitHub repo metadata取得失敗 %s: HTTP %s", repo_name, res.status_code)
            return "", {}
        data = res.json() or {}
        license_info = data.get("license") or {}
        text = "\n".join(filter(None, [
            f"Repository: {data.get('full_name') or repo_name}",
            f"Description: {data.get('description') or ''}",
            f"Homepage: {data.get('homepage') or ''}",
            f"Archived: {bool(data.get('archived'))}",
            f"Disabled: {bool(data.get('disabled'))}",
            f"Visibility: {data.get('visibility') or ''}",
            f"Default branch: {data.get('default_branch') or ''}",
            f"Pushed at: {data.get('pushed_at') or ''}",
            f"Updated at: {data.get('updated_at') or ''}",
            f"License: {license_info.get('spdx_id') or license_info.get('name') or ''}",
            "Topics: " + ", ".join(data.get("topics") or []),
        ]))
        details = {
            "homepage": data.get("homepage") or "",
            "pushed_at": data.get("pushed_at") or "",
            "updated_at": data.get("updated_at") or "",
            "html_url": data.get("html_url") or "",
            "default_branch": data.get("default_branch") or "",
        }
        return _truncate_source_context(text), details
    except Exception as exc:
        logger.warning("[SOURCE CONTEXT] GitHub repo metadata取得例外 %s: %s", repo_name, exc)
        return "", {}


def fetch_arxiv_api_context(arxiv_id: str) -> tuple[str, dict]:
    """Rehydrate official arXiv metadata for legacy Technology rows.

    Legacy Notion rows do not retain the original sourceDetails. Re-querying the exact arXiv ID
    is safer and cheaper than treating a migrated summary as verified evidence.
    """
    if not arxiv_id:
        return "", {}
    try:
        res = _fetch_arxiv_with_retry(
            "https://export.arxiv.org/api/query",
            {"id_list": arxiv_id, "start": 0, "max_results": 1},
        )
        if res is None:
            return "", {}
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        root = ET.fromstring(res.content)
        entry = root.find("atom:entry", ns)
        if entry is None:
            return "", {}
        title = re.sub(r"\s+", " ", entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        summary = re.sub(r"\s+", " ", entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
        authors = [re.sub(r"\s+", " ", a.findtext("atom:name", default="", namespaces=ns) or "").strip()
                   for a in entry.findall("atom:author", ns)]
        authors = [x for x in authors if x]
        categories = [c.get("term", "") for c in entry.findall("atom:category", ns) if c.get("term")]
        comment = re.sub(r"\s+", " ", entry.findtext("arxiv:comment", default="", namespaces=ns) or "").strip()
        external_links: list[str] = []
        for link in entry.findall("atom:link", ns):
            href = (link.get("href") or "").strip()
            if href.startswith(("http://", "https://")) and "arxiv.org" not in urlparse(href).netloc.lower():
                external_links.append(href)
        text = "\n".join(filter(None, [
            f"Title: {title}",
            "Authors: " + ", ".join(authors[:30]) if authors else "",
            "Categories: " + ", ".join(categories[:30]) if categories else "",
            f"Abstract: {summary}",
            f"Comment: {comment}" if comment else "",
        ]))
        entry_id = entry.findtext("atom:id", default="", namespaces=ns) or ""
        version_match = re.search(r"v(\d+)$", entry_id)
        arxiv_version = f"v{version_match.group(1)}" if version_match else ""
        return _truncate_verification_context(text), {
            "authors": authors,
            "categories": categories,
            "comment": comment,
            "official_external_links": list(dict.fromkeys(external_links))[:8],
            "arxiv_version": arxiv_version,
            "arxiv_versioned_url": f"https://arxiv.org/abs/{arxiv_id}{arxiv_version}" if arxiv_version else "",
        }
    except Exception as exc:
        logger.warning("[SOURCE CONTEXT] arXiv API context失敗 %s: %s", arxiv_id, exc)
        return "", {}


def _effective_evidence_source(repo: dict) -> str:
    """Promote HN/legacy discovery rows to the durable primary-source type when explicit."""
    entity_id = str(repo.get("canonicalEntityId") or repo.get("canonical_entity_id") or "").lower()
    primary = str(repo.get("primaryUrl") or repo.get("url") or "")
    if entity_id.startswith("github:") or _github_repo_name_from_url(primary):
        return "GitHub"
    if entity_id.startswith("arxiv:") or _extract_arxiv_id(primary):
        return "ArXiv"
    return str(repo.get("source") or "GitHub")


def _is_redundant_arxiv_doi(url: str, arxiv_id: str) -> bool:
    if not arxiv_id:
        return False
    parsed = urlparse(url or "")
    if (parsed.netloc or "").lower() not in {"doi.org", "dx.doi.org"}:
        return False
    return f"arxiv.{arxiv_id}" in (parsed.path or "").lower()


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


def _is_low_value_arxiv_url(url: str) -> bool:
    """arXivのナビゲーション/補助URLをEvidence・Freshness候補から除外する。"""
    try:
        parsed = urlparse(url or "")
    except Exception:
        return False
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    if host not in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        return False
    path = (parsed.path or "/").rstrip("/") or "/"
    lowered = path.lower()
    if lowered == "/":
        return True
    blocked_prefixes = (
        "/prevnext", "/ignoreme", "/search", "/list", "/help",
        "/login", "/format", "/catchup", "/multi", "/show-email",
    )
    return lowered.startswith(blocked_prefixes)


class _ResearchLinkParser(HTMLParser):
    """本文とは別に、研究ページの一次資料リンクだけを安全に収集する。"""
    _KEYWORDS = re.compile(r"\b(pdf|paper|publication|full\s*paper|download|proceedings|doi|supplement|appendix|technical\s*report|docs?|documentation|github|gitlab|repository|source\s*code)\b", re.I)

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
        parsed = urlparse(href)
        # host名の "arxiv" だけで全リンクを研究資料扱いしない。path/queryとラベルだけを見る。
        href_signal = f"{parsed.path}?{parsed.query}"
        if (
            href.startswith(("http://", "https://"))
            and not _is_low_value_arxiv_url(href)
            and (self._KEYWORDS.search(label) or self._KEYWORDS.search(href_signal))
        ):
            self.links.append((href, label))
        self._current_href, self._current_text = "", []


def _http_get_limited(url: str, accepted_types: tuple[str, ...], byte_limit: int) -> tuple[bytes, str, str]:
    """外部一次資料をGeminiなしで取得する共通処理。

    redirect先も毎回public URL検証する。requestsの自動redirectを許すと、公開URLから
    localhost/private IPへ転送されるSSRF経路ができるため、最大4 hopを手動追跡する。
    """
    if not (url or "").startswith(("http://", "https://")):
        return b"", "", ""
    current_url = url
    max_redirects = 4
    for redirect_count in range(max_redirects + 1):
        try:
            _validate_public_http_url(current_url)
        except ValueError as exc:
            logger.warning("[SOURCE FETCH BLOCKED] %s", exc)
            return b"", "", ""
        try:
            with requests.get(
                current_url,
                headers={"User-Agent": WEB_CONTEXT_USER_AGENT, "Accept": "*/*"},
                timeout=WEB_CONTEXT_TIMEOUT_SECONDS,
                allow_redirects=False,
                stream=True,
            ) as res:
                status = int(getattr(res, "status_code", 0) or 0)
                if status in {301, 302, 303, 307, 308}:
                    location = (getattr(res, "headers", {}) or {}).get("Location")
                    if not location or redirect_count >= max_redirects:
                        return b"", "", current_url
                    next_url = urljoin(current_url, location)
                    # 次のrequestを送る前にprivate/link-local/credential URLを拒否する。
                    try:
                        _validate_public_http_url(next_url)
                    except ValueError as exc:
                        logger.warning("[SOURCE FETCH REDIRECT BLOCKED] %s -> %s", current_url, exc)
                        return b"", "", ""
                    current_url = next_url
                    continue

                content_type = ((getattr(res, "headers", {}) or {}).get("Content-Type") or "").lower()
                final_url = getattr(res, "url", None) or current_url
                # Adapter/proxy等でurlが変わって返る場合も最終URLを再確認する。
                try:
                    _validate_public_http_url(final_url)
                except ValueError as exc:
                    logger.warning("[SOURCE FETCH FINAL URL BLOCKED] %s", exc)
                    return b"", "", ""
                if status != 200 or (content_type and not any(t in content_type for t in accepted_types)):
                    return b"", content_type, final_url
                chunks, total = [], 0
                for chunk in res.iter_content(chunk_size=32768):
                    if not chunk:
                        continue
                    chunk = chunk[:max(0, byte_limit - total)]
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= byte_limit:
                        break
                return b"".join(chunks), content_type, final_url
        except Exception as e:
            logger.info(f"[SOURCE FETCH] failed {current_url}: {e}")
            return b"", "", ""
    return b"", "", ""


def _http_get_health_limited(url: str, byte_limit: int = 1_500_000) -> tuple[int, str, str]:
    """Status-preserving sibling of _http_get_limited for evidence health checks.

    Unlike the content helper, transient 5xx/429 must never be collapsed into 404/MISSING.
    Redirects are manually validated at every hop to preserve the existing SSRF boundary.
    """
    if not (url or "").startswith(("http://", "https://")):
        return 0, "", ""
    current_url = url
    for redirect_count in range(5):
        try:
            _validate_public_http_url(current_url)
        except ValueError:
            return 0, "", current_url
        try:
            with requests.get(current_url, headers={"User-Agent": WEB_CONTEXT_USER_AGENT, "Accept": "*/*"},
                              timeout=WEB_CONTEXT_TIMEOUT_SECONDS, allow_redirects=False, stream=True) as res:
                status = int(getattr(res, "status_code", 0) or 0)
                if status in {301,302,303,307,308}:
                    location=(getattr(res,"headers",{}) or {}).get("Location")
                    if not location or redirect_count >= 4:
                        return status, "", current_url
                    next_url=urljoin(current_url,location)
                    try:
                        _validate_public_http_url(next_url)
                    except ValueError:
                        return 0, "", next_url
                    current_url=next_url
                    continue
                final_url=getattr(res,"url",None) or current_url
                try:
                    _validate_public_http_url(final_url)
                except ValueError:
                    return 0, "", final_url
                if status != 200:
                    return status, "", final_url
                chunks=[]; total=0
                for chunk in res.iter_content(chunk_size=32768):
                    if not chunk: continue
                    chunk=chunk[:max(0, byte_limit-total)]; chunks.append(chunk); total+=len(chunk)
                    if total>=byte_limit: break
                return status, b"".join(chunks).decode("utf-8",errors="replace"), final_url
        except requests.RequestException:
            return 0, "", current_url
    return 0, "", current_url


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


def _fetch_html_document(url: str, max_chars: int = SOURCE_CONTEXT_MAX_CHARS) -> tuple[str, list[tuple[str, str]], str]:
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
        return _truncate_text_context(text, max_chars), list(dict.fromkeys(links.links)), final_url or url
    return _truncate_text_context(unescape(text), max_chars), [], final_url or url


def _resolve_producthunt_official_url(url: str) -> str:
    """Product Huntの/r/リダイレクトを一度だけ追い、公式一次情報URLを返す。"""
    parsed = urlparse(url or "")
    if "producthunt.com" not in parsed.netloc.lower() or not parsed.path.startswith("/r/"):
        return ""
    _, _, final_url = _http_get_limited(
        url, ("text/html", "application/xhtml+xml", "text/plain"), WEB_CONTEXT_MAX_BYTES,
    )
    final = final_url or ""
    final_host = urlparse(final).netloc.lower()
    if final.startswith(("http://", "https://")) and "producthunt.com" not in final_host:
        logger.info("[PH OFFICIAL URL] %s -> %s", url, final)
        return final
    return ""


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
    keywords = re.compile(r"abstract|method|experiment|table|hardware|gpu|runtime|second|sec\b|dataset|benchmark|limitation|appendix|code|availability|status|supplement", re.I)
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
    metadata = {
        "coverage": {
            "method": state(r"\b(?:method|approach)\b|stage\s*[12]|方法"), "dataset": state(r"\b(?:dataset|data set)\b|データセット"),
            "hardware": state(r"\b(?:hardware|gpu|rtx|nvidia|cpu)\b|ハードウェア"), "runtime": state(r"\b(?:runtime|latency|sec|second|seconds)\b|処理時間"),
            "benchmark": state(r"benchmark|evaluation|experiment|評価"), "limitations": state(r"limitation|limitat|constraint|制約|限界"),
            "code_availability": state(r"source code|code availability|github|code release|公開コード"),
        },
        "required_qualifiers": list(dict.fromkeys(qualifiers))[:8],
        "evidence_strength": "OFFICIAL_GUARANTEE" if re.search(r"guarantee[sd]?|保証", text, re.I) else "UNKNOWN",
    }
    # 公式リリースノートは研究用のMethod見出しを持たない。本文に実在する
    # API / package / function / implementation 記述も技術根拠として拾う。
    # 英単語は必ずword boundaryで判定する。`API`が`rapid/capital`に、`test`が`latest`に
    # 部分一致してEvidenceを誤ってFOUND扱いするFalse Negativeを防ぐ。
    metadata["coverage"]["method"] = state(r"\b(?:method|approach|implementation|architecture|algorithm|api|package|function|interface)\b|stage\s*[12]|方法|実装|関数|パッケージ")
    metadata["coverage"]["benchmark"] = state(r"\b(?:benchmark|evaluation|experiment|test|release notes?)\b|評価|テスト|ベンチマーク")
    metadata["coverage"]["limitations"] = state(r"\b(?:limitation|limitations|constraint|constraints|WIP|experimental|unsupported)\b|work in progress|not supported|not implemented|does not support|制約|限界")
    # 抽出元は常に本文。存在しない固有名を補完する用途には使わない。
    metadata["named_technical_entities"] = list(dict.fromkeys(re.findall(
        r"(?<![A-Za-z0-9_])(?:[A-Z][A-Za-z0-9_]{2,}|[a-z][A-Za-z0-9_]*[A-Z][A-Za-z0-9_]*)\b", text
    )))[:80]
    metadata["numeric_claims"] = list(dict.fromkeys(re.findall(
        r"\b\d+(?:\.\d+)?(?:\s*(?:[-–—〜～]|to)\s*\d+(?:\.\d+)?)?\s*"
        r"(?:%|percent|ms|s|sec(?:onds?)?|minutes?|hours?|days?|weeks?|months?|KB|MB|GB|TB|x|倍|時間|分|日|週|ヶ月|か月)\b",
        text, re.I
    )))[:120]
    return metadata


def fetch_webpage_context(url: str) -> str:
    """HN/PH外部URLをGeminiを使わず取得し、本文テキストだけを返す。失敗時は空文字。"""
    text, _, _ = _fetch_html_document(url)
    if len(text.strip()) >= SOURCE_CONTEXT_MIN_CHARS:
        logger.info(f"[WEB CONTEXT] Python取得成功: {len(text)} chars <- {url}")
        return text
    logger.info(f"[WEB CONTEXT FALLBACK] 本文不足: {url}")
    return ""


def prepare_source_context(repo: dict) -> dict:
    """Resolve first-party evidence with zero Gemini calls across all four discovery sources.

    Run113 separates *discovery source* from *evidence source*. A Hacker News row whose durable
    Primary URL is a GitHub repository is evaluated as GitHub evidence, while HN remains an
    accumulated discovery source in Technology Intelligence. This prevents migrated rows from
    losing source-native recovery simply because sourceDetails were not persisted in legacy DBs.
    """
    discovery_source = str(repo.get("source") or "GitHub")
    source = _effective_evidence_source(repo)
    name = repo.get("nameWithOwner", "")
    desc = repo.get("description", "")
    primary_url = repo.get("primaryUrl") or repo.get("url") or ""
    stored = repo.get("sourceContext") or ""
    stored_verified = bool(repo.get("sourceContextVerified", True))
    details = dict(repo.get("sourceDetails") or {})
    github_repo_name = _github_repo_identity(repo) if source == "GitHub" else ""
    arxiv_id = _extract_arxiv_id(primary_url) if source == "ArXiv" else ""
    if source == "ArXiv" and not arxiv_id:
        entity_id = str(repo.get("canonicalEntityId") or repo.get("canonical_entity_id") or "")
        if entity_id.lower().startswith("arxiv:"):
            arxiv_id = entity_id.split(":", 1)[1]
            primary_url = primary_url or f"https://arxiv.org/abs/{arxiv_id}"

    # Product Hunt redirect aliases may survive even when the official URL was not persisted.
    if source == "ProductHunt":
        redirect_url = details.get("producthunt_url") or primary_url
        resolved_official_url = _resolve_producthunt_official_url(redirect_url)
        if resolved_official_url:
            details["official_url"] = resolved_official_url
            primary_url = resolved_official_url

    pieces = [
        f"[DISCOVERY_SOURCE]\nSource: {discovery_source}\nEvidence Source: {source}\nName: {name}\nDescription: {desc}"
    ]
    substantive_parts: list[str] = []
    ledger_primary_snapshot_text = ""
    method = GROUNDING_METADATA_ONLY
    primary_material_retrieved = False
    primary_fetch_failed = False
    freshness_status_available = False
    source_native_links: list[tuple[str, str]] = []
    research_links: list[tuple[str, str]] = []

    if source == "GitHub":
        if not github_repo_name:
            primary_fetch_failed = True
        else:
            readme = fetch_github_readme_context(github_repo_name)
            metadata_context, repo_meta = fetch_github_repository_metadata_context(github_repo_name)
            if readme:
                pieces.append("README:\n" + readme)
                substantive_parts.append(readme)
                ledger_primary_snapshot_text = readme
                source_native_links.extend(_extract_markdown_evidence_links(readme))
                primary_material_retrieved = True
            if metadata_context:
                pieces.append("GitHub repository metadata:\n" + metadata_context)
                substantive_parts.append(metadata_context)
                primary_material_retrieved = True
                freshness_status_available = True  # REST metadata was fetched at this run.
            details.update({k: v for k, v in repo_meta.items() if v})
            if not readme and not metadata_context:
                primary_fetch_failed = True

    elif source == "ArXiv":
        # Direct daily collection sourceContext is official Atom data. Reconstructed legacy context
        # is explicitly marked unverified and must be rehydrated from the exact arXiv ID instead.
        if stored:
            pieces.append(("Abstract:\n" if stored_verified else "Stored discovery summary (unverified):\n") + stored)
            if stored_verified:
                substantive_parts.append(stored)
                primary_material_retrieved = True
        if arxiv_id and (INVENTORY_BOOTSTRAP_ACTIVE or not primary_material_retrieved):
            api_context, api_details = fetch_arxiv_api_context(arxiv_id)
            if api_context:
                pieces.append("Official arXiv metadata:\n" + api_context)
                substantive_parts.append(api_context)
                ledger_primary_snapshot_text = api_context
                primary_material_retrieved = True
                # Merge, never discard collection-time metadata.
                for key, value in api_details.items():
                    if isinstance(value, list):
                        details[key] = list(dict.fromkeys((details.get(key) or []) + value))
                    elif value and not details.get(key):
                        details[key] = value
            elif not primary_material_retrieved:
                primary_fetch_failed = True
        authors = details.get("authors") or []
        categories = details.get("categories") or []
        if authors:
            pieces.append("Authors: " + ", ".join(authors[:20]))
        if categories:
            pieces.append("Categories: " + ", ".join(categories[:20]))
        comment = details.get("comment") or ""
        if comment and comment not in "\n".join(substantive_parts):
            pieces.append("ArXiv comment:\n" + comment)
            if stored_verified:
                substantive_parts.append(comment)
        # The arXiv HTML page is never treated as the substantive primary document here; Atom/PDF
        # remain authoritative. We only harvest explicitly labelled research/code links so an
        # implementation repository linked by the paper can be inspected. This preserves useful
        # first-party linkage without reintroducing GitHub site-wide navigation contamination.
        if primary_url:
            _arxiv_landing, arxiv_page_links, _arxiv_final = _fetch_html_document(
                primary_url, max_chars=min(12000, VERIFICATION_CONTEXT_MAX_CHARS)
            )
            research_links.extend(arxiv_page_links)

    elif source == "HackerNews":
        hn_text = stored.strip()
        if hn_text:
            pieces.append("Hacker News discovery text:\n" + hn_text)
            if stored_verified:
                substantive_parts.append(hn_text)
        hn_url = details.get("hn_url")
        if hn_url:
            pieces.append(f"HN discussion URL: {hn_url}")
        external_url = details.get("external_url") or ""
        if external_url:
            primary_url = external_url
        elif primary_url and "news.ycombinator.com" not in (urlparse(primary_url).netloc or "").lower():
            details["external_url"] = primary_url
        elif hn_text and stored_verified:
            primary_material_retrieved = True

    elif source == "ProductHunt":
        if stored:
            pieces.append("Product Hunt discovery metadata:\n" + stored)
        official = details.get("official_url") or details.get("website") or ""
        if official and "producthunt.com" not in (urlparse(official).netloc or "").lower():
            primary_url = official

    elif stored:
        pieces.append(stored)
        if stored_verified:
            substantive_parts.append(stored)
            primary_material_retrieved = True

    # GitHub repository HTML contains site-wide Copilot/AI navigation and is not evidence. arXiv
    # is better recovered from Atom/PDF. Other sources may still expose useful official links.
    landing_text = ""
    final_primary_url = ""
    if source not in {"GitHub", "ArXiv"} and primary_url:
        landing_text, research_links, final_primary_url = _fetch_html_document(
            primary_url, max_chars=VERIFICATION_CONTEXT_MAX_CHARS
        )
        if final_primary_url:
            primary_url = final_primary_url
        host = (urlparse(primary_url).netloc or "").lower().split(":", 1)[0]
        discovery_only_landing = (
            source == "ProductHunt" and (host == "producthunt.com" or host.endswith(".producthunt.com"))
        ) or (
            source == "HackerNews" and host in {"news.ycombinator.com", "www.news.ycombinator.com"}
        )
        if landing_text:
            label = "[DISCOVERY_REFERENCE]" if discovery_only_landing else "[REFERENCE_SOURCE]"
            pieces.append(label + "\n" + _truncate_source_context(landing_text))
            if not discovery_only_landing:
                substantive_parts.append(landing_text)
                primary_material_retrieved = True
                freshness_status_available = True
        elif not primary_material_retrieved:
            primary_fetch_failed = True

    supplement_candidates: list[dict] = []
    seen_candidate_keys = {_evidence_trace_url_key(primary_url)} if primary_url else set()

    def _append_supplement_candidate(link: str, label: str, role: str = "PRIMARY_SOURCE", origin: str = "landing") -> None:
        nonlocal primary_url
        if not isinstance(link, str) or not link.startswith(("http://", "https://")):
            return
        link = urldefrag(link)[0]
        if source == "ProductHunt" and "producthunt.com" in (urlparse(link).netloc or "").lower() and (urlparse(link).path or "").startswith("/r/"):
            link = _resolve_producthunt_official_url(link) or link
        if _is_low_value_arxiv_url(link) or _is_redundant_arxiv_doi(link, arxiv_id):
            return
        if _is_github_global_navigation_url(link):
            return
        # A GitHub project's GitHub-hosted evidence must remain inside the same repository.
        if source == "GitHub" and (urlparse(link).netloc or "").lower() in {"github.com", "www.github.com"}:
            linked_repo = _github_repo_name_from_url(link)
            if not linked_repo or (github_repo_name and linked_repo.lower() != github_repo_name.lower()):
                return
        link_key = _evidence_trace_url_key(link)
        if not link or not link_key or link_key in seen_candidate_keys:
            return
        seen_candidate_keys.add(link_key)
        source_type = "arxiv_pdf" if link.lower().split("?", 1)[0].endswith(".pdf") or "pdf" in (label or "").lower() else "official_docs"
        supplement_candidates.append({
            "url": link, "role": role, "source_type": source_type, "label": label, "origin": origin,
        })

    # Source-native candidates are always ordered before generic landing links.
    if source == "ArXiv" and arxiv_id:
        _append_supplement_candidate(f"https://arxiv.org/pdf/{arxiv_id}.pdf", "arxiv_pdf", origin="arxiv")
    if source == "GitHub":
        homepage = details.get("homepage") or ""
        if homepage:
            _append_supplement_candidate(homepage, "GitHub repository homepage", origin="github_metadata")
        for link, label in source_native_links:
            _append_supplement_candidate(link, label, origin="github_readme")
    else:
        for link, label in research_links:
            role = "SUPPLEMENTAL_SOURCE" if re.search(r"supplement|appendix", label, re.I) else "PRIMARY_SOURCE"
            _append_supplement_candidate(link, label, role, origin="landing")

    # Persisted metadata/evidence URLs are explicit source signals and may recover legacy rows.
    metadata_urls: list[tuple[str, str]] = []
    for key in ("official_url", "officialUrl", "website", "website_url", "homepage", "project_url", "docs_url", "documentation_url", "external_url"):
        value = details.get(key)
        if isinstance(value, str):
            metadata_urls.append((value, key))
    for key in ("official_external_links", "links", "related_links"):
        for value in details.get(key, []) if isinstance(details.get(key), list) else []:
            metadata_urls.append((value, key))
    for link, label in metadata_urls:
        _append_supplement_candidate(link, label, origin="metadata")

    deep_source_required = bool(supplement_candidates)
    substantive = "\n\n".join(x for x in substantive_parts if x)
    text_sufficient = bool(substantive.strip())
    if text_sufficient:
        method = GROUNDING_SOURCE_NATIVE
    context = _truncate_source_context("\n\n".join(pieces))
    verification_context = _truncate_verification_context(substantive or context)
    evidence_metadata = _build_evidence_metadata(verification_context, False)
    source_info = {
        "context": context,
        "context_length": len(context),
        "verification_context": verification_context,
        "verification_context_length": len(verification_context),
        "source": source,
        "canonical_entity_id": repo.get("canonicalEntityId") or "",
        "discovery_source": discovery_source,
        "source_name": name,
        "method": method,
        "primary_url": primary_url,
        "source_details": details,
        "sufficient": text_sufficient,
        "text_sufficient": text_sufficient,
        "primary_source_resolved": bool(primary_url and primary_material_retrieved),
        "primary_fetch_failed": bool(primary_fetch_failed and not primary_material_retrieved),
        "freshness_status_available": freshness_status_available,
        "deep_source_required": deep_source_required,
        "deep_source_scanned": False,
        "evidence_sufficient": False,
        "deep_source_urls": [],
        "supplement_candidates": supplement_candidates,
        "evidence_documents": [{
            "url": primary_url, "role": "PRIMARY_SOURCE", "source_type": source.lower(),
            "retrieved": bool(primary_material_retrieved),
            "evidence_extract": _compress_evidence(ledger_primary_snapshot_text or substantive) if (ledger_primary_snapshot_text or substantive) else "",
            "document_text": ledger_primary_snapshot_text or substantive or "",
            "source_version": details.get("arxiv_version") or "",
            "resolved_url": details.get("arxiv_versioned_url") or primary_url,
        }],
        "checked_urls": {_evidence_trace_url_key(primary_url)} if primary_url else set(),
        "evidence_supplement_attempted": False,
        "evidence_supplement_attempts": 0,
        "evidence_metadata": evidence_metadata,
    }
    source_info["evidence_authority_summary"] = _evidence_authority_summary(source_info)
    return source_info


EVIDENCE_SUFFICIENT = "SUFFICIENT"
EVIDENCE_SUPPLEMENT_REQUIRED = "SUPPLEMENT_REQUIRED"
EVIDENCE_INSUFFICIENT = "INSUFFICIENT"


def classify_action_risk_tier(action_text: str) -> str:
    """記事に実際に書かれたActionをLOW/MEDIUM/HIGHへ意味ベースで分類する。"""
    text = action_text or ""
    if re.search(r"全面(?:導入|移行|改修)|全社(?:導入|展開)|本番(?:移行|全面導入)|大規模(?:投資|導入)|セキュリティ境界.{0,12}(?:変更|改修)", text, re.I):
        return "HIGH"
    if re.search(r"既存設計.{0,12}(?:変更|改修)|限定(?:ユーザー|利用者).{0,12}導入|運用プロセス.{0,12}変更|小規模(?:本番|導入)", text, re.I):
        return "MEDIUM"
    return "LOW"


def assess_evidence_sufficiency(source_info: dict) -> dict:
    """Evidence-to-Decision Sufficiencyを判定する。

    網羅性そのものではなく、取得済みの一次情報の範囲で結論とActionを安全な
    強度に制約した記事を作れるかを判定する。制約・鮮度が未確認でも、低リスク
    Actionと明示的な留保で安全に扱える研究紹介まで機械的に落とさない。
    """
    context = source_info.get("verification_context") or source_info.get("context", "") or ""
    coverage = (source_info.get("evidence_metadata") or {}).get("coverage", {})
    found = lambda key: coverage.get(key) == "FOUND"
    numbers_present = bool(re.search(r"(?:\d+(?:\.\d+)?\s*(?:%|x|倍|ms|sec(?:ond)?s?|GB|MB|FPS))", context, re.I))
    time_sensitive = bool(_FUTURE_SOURCE_PATTERN.search(context))
    # `GA`は単語境界なしだとlegacy/organic等へ部分一致するため、英語の鮮度語は境界付きで判定。
    current_state_claim = bool(re.search(
        r"(?:価格|料金|現在|現行|提供中|法令|制度)|\b(?:availability|pricing|current|today|GA|generally available)\b",
        context, re.I,
    ))
    research_scope = source_info.get("source") == "ArXiv" or bool(re.search(r"(?:paper|arxiv|benchmark|論文|研究|実験|提出時点)", context, re.I))
    requested_tier = str(source_info.get("requested_action_risk_tier", "LOW")).upper()
    action_risk_tier = requested_tier if requested_tier in {"LOW", "MEDIUM", "HIGH"} else "LOW"
    checks = {
        "primary_source_resolved": bool(source_info.get("primary_source_resolved")),
        "technical_claims_available": found("method") or bool(re.search(r"\b(?:method|approach|architecture|algorithm|implementation)\b|モデル|手法|方式|実装", context, re.I)),
        "limitations_or_constraints_available": found("limitations") or bool(re.search(r"\b(?:limitation|limitations|constraint|constraints|caveat)\b|not validated|制約|限界|課題|未検証", context, re.I)),
        "conditions_for_numbers_available": (not numbers_present) or any(found(key) for key in ("hardware", "runtime", "benchmark", "dataset")),
        "actor_attribution_available": bool(re.search(r"\b(?:author|authors|developer|developers|researcher|researchers)\b|著者|開発者|研究者", context, re.I)) or bool((source_info.get("source_details") or {}).get("authors")),
        "action_support_available": False,
        "comparison_support_available_if_comparison_is_needed": True,
        "freshness_status_available_if_time_sensitive": (not (time_sensitive or current_state_claim)) or bool(source_info.get("freshness_status_available")),
    }
    # 一次情報にAction文言そのものがなくても、技術根拠から限定PoC・比較・見送り等の
    # LOW RISK Actionは導ける。HIGH RISKは制約・鮮度・数値条件まで要求する。
    low_risk_supported = checks["primary_source_resolved"] and checks["technical_claims_available"]
    medium_risk_supported = low_risk_supported and checks["limitations_or_constraints_available"]
    high_risk_supported = medium_risk_supported and checks["conditions_for_numbers_available"] and checks["freshness_status_available_if_time_sensitive"]
    action_supported_requested_tier = {
        "LOW": low_risk_supported,
        "MEDIUM": medium_risk_supported,
        "HIGH": high_risk_supported,
    }[action_risk_tier]
    checks["action_support_available"] = action_supported_requested_tier
    comparison_needed = bool(re.search(r"(?:compare|comparison|versus|vs\.?|比較|従来方式|代替)", context, re.I))
    if comparison_needed:
        checks["comparison_support_available_if_comparison_is_needed"] = bool(re.search(r"(?:compare|comparison|versus|vs\.?|比較)", context, re.I))

    hard_missing = [key for key in ("primary_source_resolved", "technical_claims_available") if not checks[key]]
    # 数値・主体は、記事で明示的に使う場合だけHard Requirementにする。未確認なら
    # プロンプト側で使わないよう制約し、モデル記憶で補完することを禁止する。
    if source_info.get("numeric_claims_required") and not checks["conditions_for_numbers_available"]:
        hard_missing.append("conditions_for_numbers_available")
    if source_info.get("actor_attribution_required") and not checks["actor_attribution_available"]:
        hard_missing.append("actor_attribution_available")
    conditional_missing = [key for key in (
        "limitations_or_constraints_available", "action_support_available",
        "comparison_support_available_if_comparison_is_needed",
        "freshness_status_available_if_time_sensitive",
    ) if not checks[key]]
    blocking_missing = list(hard_missing)
    # Research evidence is scoped to the paper/version itself. A phrase such as "current" inside
    # a paper must not force a live-product freshness lookup; the article/assessment must instead
    # present it as paper-time evidence. Mutable product/web sources still require freshness.
    if current_state_claim and not research_scope and not checks["freshness_status_available_if_time_sensitive"]:
        blocking_missing.append("freshness_status_available_if_time_sensitive")
    checked_evidence_keys = source_info.get("checked_urls", set())
    candidates_available = any(
        _evidence_trace_url_key(row.get("url", "")) not in checked_evidence_keys
        for row in source_info.get("supplement_candidates", [])
        if row.get("url")
    )
    supplement_already_attempted = bool(source_info.get("evidence_supplement_attempted"))
    action_risk_downgraded_from = ""
    # MEDIUM/HIGHの根拠が不足しても、まず上限付き補強を試す。補強後も足りない
    # 場合は、一次情報から導ける具体的なLOW RISK Actionへ縮退できるかを判定する。
    if blocking_missing:
        state = EVIDENCE_SUPPLEMENT_REQUIRED if candidates_available else EVIDENCE_INSUFFICIENT
    elif action_risk_tier in {"MEDIUM", "HIGH"} and not action_supported_requested_tier:
        if candidates_available and not supplement_already_attempted:
            state = EVIDENCE_SUPPLEMENT_REQUIRED
        elif low_risk_supported:
            action_risk_downgraded_from = action_risk_tier
            action_risk_tier = "LOW"
            checks["action_support_available"] = True
            state = EVIDENCE_SUFFICIENT
        else:
            blocking_missing.append("high_risk_action_unsupported" if requested_tier == "HIGH" else "medium_risk_action_unsupported")
            state = EVIDENCE_INSUFFICIENT
    elif conditional_missing and candidates_available and not supplement_already_attempted:
        state = EVIDENCE_SUPPLEMENT_REQUIRED
    else:
        state = EVIDENCE_SUFFICIENT
    limitations_disclosed = not checks["limitations_or_constraints_available"]
    research_future_only = research_scope and bool(re.search(r"\bfuture\s+work\b|今後の研究|将来(?:の)?研究", context, re.I))
    # Researchのfuture workは製品availabilityの鮮度要件ではないが、記事では論文時点の
    # 将来課題として扱うことを監査メタデータに残す。
    freshness_scope_limited = research_future_only or (research_scope and time_sensitive and not checks["freshness_status_available_if_time_sensitive"])
    evidence_gap_disclosed = bool(conditional_missing)
    decision_scope_safe = state == EVIDENCE_SUFFICIENT or (state == EVIDENCE_SUPPLEMENT_REQUIRED and not blocking_missing)
    return {
        "state": state,
        "checks": checks,
        "core_missing": hard_missing,
        "optional_missing": conditional_missing,
        "blocking_missing": blocking_missing,
        "documents_checked": len(source_info.get("evidence_documents", [])),
        "decision_scope_safe": decision_scope_safe,
        "action_risk_tier": action_risk_tier,
        "action_supported_at_current_tier": checks["action_support_available"],
        "action_risk_downgraded_from": action_risk_downgraded_from,
        "limitations_disclosed": limitations_disclosed,
        "freshness_scope_limited": freshness_scope_limited,
        "evidence_gap_disclosed": evidence_gap_disclosed,
        "research_scope": research_scope,
        "current_state_claim": current_state_claim,
        "numeric_claims_allowed": checks["conditions_for_numbers_available"],
        "actor_attribution_allowed": checks["actor_attribution_available"],
    }


def supplement_source_evidence(source_info: dict) -> dict:
    """SUPPLEMENT_REQUIREDの候補だけを、URL重複なし・上限付きで補強する。"""
    source_info["evidence_supplement_attempted"] = True
    checked_urls = source_info.setdefault("checked_urls", set())
    documents = source_info.setdefault("evidence_documents", [])
    candidates = source_info.get("supplement_candidates", [])
    fetched_parts: list[str] = []
    attempts = 0
    for candidate in candidates:
        if attempts >= MAX_EVIDENCE_SUPPLEMENT_ATTEMPTS or len(documents) >= MAX_EVIDENCE_DOCUMENTS:
            break
        evidence_url = candidate.get("url", "")
        evidence_key = _evidence_trace_url_key(evidence_url)
        if not evidence_url or not evidence_key or evidence_key in checked_urls:
            continue
        checked_urls.add(evidence_key)
        attempts += 1
        is_pdf = candidate.get("source_type") == "arxiv_pdf"
        raw_text = fetch_pdf_context(evidence_url) if is_pdf else fetch_webpage_context(evidence_url)
        doc = dict(candidate)
        doc["retrieved"] = bool(raw_text)
        if raw_text:
            doc["evidence_extract"] = _compress_evidence(raw_text)
            doc["document_text"] = raw_text
            doc["resolved_url"] = evidence_url
        documents.append(doc)
        if not raw_text:
            continue
        if candidate.get("role") == "PRIMARY_SOURCE":
            # Run113: a successfully retrieved first-party supplement (notably arXiv PDF /
            # official docs) is itself enough to resolve the primary-source requirement.
            # Previously the flag stayed False forever when the landing page fetch failed.
            source_info["primary_source_resolved"] = True
            source_info["primary_fetch_failed"] = False
            if source_info.get("source") in {"GitHub", "ProductHunt"}:
                source_info["freshness_status_available"] = True
        label = "[SUPPLEMENTAL_SOURCE]" if candidate.get("role") == "SUPPLEMENTAL_SOURCE" else "[PRIMARY_SOURCE]"
        fetched_parts.append(f"{label}\nURL: {evidence_url}\n{_compress_evidence(raw_text)}")
        verification_piece = f"{label}\nURL: {evidence_url}\n{raw_text}"
        source_info["verification_context"] = _merge_verification_context(
            source_info.get("verification_context") or source_info.get("context", ""), verification_piece
        )
        source_info["verification_context_length"] = len(source_info["verification_context"])
        source_info.setdefault("deep_source_urls", []).append(evidence_url)

    source_info["evidence_supplement_attempts"] = source_info.get("evidence_supplement_attempts", 0) + attempts
    if fetched_parts:
        context = "\n\n".join([source_info.get("context", "")] + fetched_parts)
        source_info["context"] = _truncate_source_context(context[:MAX_EVIDENCE_TOTAL_CHARS])
        source_info["context_length"] = len(source_info["context"])
        source_info["deep_source_scanned"] = True
        source_info["sufficient"] = True
        source_info["method"] = GROUNDING_SOURCE_NATIVE
    verification_context = source_info.get("verification_context") or source_info.get("context", "")
    source_info["evidence_metadata"] = _build_evidence_metadata(verification_context, bool(source_info.get("deep_source_scanned")))
    source_info["evidence_authority_summary"] = _evidence_authority_summary(source_info)
    return source_info


def evidence_reason_rows(evidence_result: dict) -> list[dict]:
    """Evidence不足の原因を、単一の汎用コードへ潰さず保存する。"""
    mapping = {
        "primary_source_resolved": REASON_CODE_PRIMARY_SOURCE_UNRESOLVED,
        "technical_claims_available": REASON_CODE_TECHNICAL_CLAIMS_INSUFFICIENT,
        "conditions_for_numbers_available": REASON_CODE_NUMERIC_CONDITIONS_INSUFFICIENT,
        "freshness_status_available_if_time_sensitive": REASON_CODE_FRESHNESS_REQUIRED_BUT_UNRESOLVED,
        "high_risk_action_unsupported": REASON_CODE_HIGH_RISK_ACTION_UNSUPPORTED,
        "medium_risk_action_unsupported": REASON_CODE_HIGH_RISK_ACTION_UNSUPPORTED,
    }
    rows = [{"reason_code": mapping.get(key, REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT),
             "message": key, "gate": "evidence", "severity": GATE_SEVERITY_HARD}
            for key in evidence_result.get("blocking_missing", [])]
    if evidence_result.get("evidence_gap_disclosed"):
        rows.append({"reason_code": REASON_CODE_EVIDENCE_GAP_DISCLOSURE_REQUIRED,
                     "message": "Conditional evidence gap must be disclosed and action limited.",
                     "gate": "evidence", "severity": GATE_SEVERITY_HARD})
    if not rows:
        rows.append({"reason_code": REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT,
                     "message": "Evidence-to-Decision Sufficiency cannot safely support the core decision.",
                     "gate": "evidence", "severity": GATE_SEVERITY_HARD})
    return rows


# `future work` / `next token`等の研究文脈を「製品の将来予定」と誤認しない。
# 鮮度追跡は公開・提供・対応・発売など、状態が後から変わる明示的な予定表現だけに限定する。
_FUTURE_STATUS_PATTERN = re.compile(
    r"(?:\bwill\s+(?:release|launch|ship|support|publish|open[- ]?source|be\s+available)\b|"
    r"\bplanned\s+(?:release|launch|support|availability)\b|"
    r"\bfuture\s+(?:version|release|feature|support)\b[^.\n]{0,24}\bplanned\b|\bcoming\s+soon\b|"
    r"\bexpected\s+(?:release|launch|availability)\b|\bnot\s+yet\s+available\b|"
    r"\b(?:preview|beta|nightly)\s+(?:release|build|channel)\b|"
    r"(?:公開|提供|対応|発売|リリース|実装|オープンソース化)予定|近日(?:公開|提供|発売)|"
    r"今後[^。\n]{0,30}(?:公開|提供|対応|発売|実装)|開発中)",
    re.I,
)
# 後方互換名。Freshnessの意味は上記のstatus-specific patternへ校正済み。
_FUTURE_SOURCE_PATTERN = _FUTURE_STATUS_PATTERN
_STALE_ARTICLE_PATTERN = re.compile(r"(?:今後|これから).{0,30}(?:予定|議論|対応)|(?:公開|対応|議論)予定", re.I)


def resolve_followup_freshness(source_info: dict) -> dict:
    """状態変更を示す明示的な将来表現だけ、同一公式ドメイン内の後続ページを確認する。"""
    context = source_info.get("verification_context") or source_info.get("context", "")
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
        if _is_low_value_arxiv_url(target):
            continue
        if urlparse(target).netloc.lower() == host and target != base and ("follow" in clean_label.lower() or "update" in clean_label.lower() or "clang" in clean_label.lower() or _FUTURE_SOURCE_PATTERN.search(clean_label) or "blog" in target.lower()):
            candidates.append(target)
    followups = []
    # unrelatedな同一domainブログを「更新済み」と誤認しないよう、長い固有語を
    # source nameから抽出し、候補本文/URLのどちらにも一語も現れなければ棄却する。
    source_name = source_info.get("source_name", "") or ""
    name_tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]{3,}", source_name)
                   if t.lower() not in {"with", "from", "using", "model", "system", "paper", "analysis"}]
    for target in list(dict.fromkeys(candidates))[:FRESHNESS_MAX_LINKS]:
        text = fetch_webpage_context(target)
        haystack = (target + "\n" + text).lower()
        relevant = (not name_tokens) or any(token in haystack for token in name_tokens)
        if text and relevant and not _FUTURE_SOURCE_PATTERN.search(text):
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
    """Unicode-safe title key. Non-Latin titles must not collapse to an empty key."""
    title = unicodedata.normalize("NFKC", (title or "").strip()).casefold()
    title = re.sub(r"[^\w]+", " ", title, flags=re.UNICODE)
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
            # 429/503/timeout等での再照会不能は、論文の不実在を意味しない。
            # Source Integrityの恒久的不一致とは分け、呼び出し元でPending Retryへ送る。
            return False, "TRANSIENT: arXiv再照会に失敗", repo
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
    """Product Hunt GraphQLから直近の新着プロダクトを取得する。

    日次観測で1か月分のVOTES上位を毎日繰り返さないよう、postedAfterを明示し
    NEWEST順で取得する。Tokenはproduction preflightで必須確認される。
    """
    logger.info(">>> [Step 1] Product Hunt一次データの自動巡回...")
    if not PRODUCTHUNT_DEVELOPER_TOKEN:
        logger.warning("[PH SKIP] PRODUCTHUNT_DEVELOPER_TOKEN が未設定のためProduct Huntをスキップします。")
        return []
    items = []
    url = "https://api.producthunt.com/v2/api/graphql"
    headers = {"Authorization": f"Bearer {PRODUCTHUNT_DEVELOPER_TOKEN}", "Content-Type": "application/json"}
    query = """
    query RecentPosts($first: Int!, $postedAfter: DateTime!) {
      posts(order: NEWEST, first: $first, postedAfter: $postedAfter) {
        edges { node { name tagline description url website votesCount createdAt } }
      }
    }
    """
    posted_after = (datetime.now(timezone.utc) - timedelta(hours=PRODUCTHUNT_LOOKBACK_HOURS)).isoformat().replace("+00:00", "Z")
    try:
        response = requests.post(
            url, json={"query": query, "variables": {"first": limit, "postedAfter": posted_after}},
            headers=headers, timeout=15,
        )
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
                producthunt_url = node.get("url") or ""
                primary = node.get("website") or _resolve_producthunt_official_url(producthunt_url) or producthunt_url
                items.append(normalize_item(
                    source="ProductHunt", name=node.get("name"), url=primary,
                    description=tagline or description, engagement=node.get("votesCount", 0),
                    published_at=node.get("createdAt"), source_context=source_context,
                    primary_url=primary, source_details={
                        "producthunt_url": producthunt_url,
                        "official_url": primary if primary and "producthunt.com" not in urlparse(primary).netloc.lower() else "",
                        "website": node.get("website") or "",
                    },
                ))
            except Exception as e:
                logger.warning(f"[PH ITEM SKIP] {e}")
        logger.info(f"   -> Product Hunt {len(items)} 件の候補を取得。")
    except Exception as e:
        logger.error(f"[FAULT ISOLATED] Product Hunt APIエラー: {e}")
    return items


# URL Dedupで無視するトラッキング用クエリパラメータ。意味のあるquery
# parameter（id, page等）は絶対に含めないこと。
_DEDUP_IGNORED_QUERY_PREFIXES = ("utm_",)
_DEDUP_IGNORED_QUERY_KEYS = {"fbclid", "gclid", "ref", "source"}


def canonicalize_url(url: str) -> str:
    """URL Dedup専用の正規化。新規candidate側・Notion既存URL側の両方で
    必ずこの関数を通すことで、表記差（trailing slash / fragment / トラッキング
    パラメータ）による誤重複判定・誤非重複判定を防ぐ。

    正規化対象: 末尾スラッシュ、fragment、utm_*・fbclid・gclid・ref・source。
    URL pathやid等の意味のあるquery parameterは一切変更しない。"""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "").lower()
    netloc = (parsed.netloc or "").lower()
    # URLのscheme/hostはcase-insensitive。既定port差も同一URLとして扱う。
    if scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    elif scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    path = parsed.path.rstrip("/")
    # arXivのv1/v2は同一論文資産として扱い、バージョン更新でStockを重複作成しない。
    if netloc in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        match = re.fullmatch(r"/(abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?", path, re.I)
        if match:
            path = f"/abs/{match.group(2)}"
            netloc = "arxiv.org"
            scheme = "https"
    filtered_query = sorted(
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith(_DEDUP_IGNORED_QUERY_PREFIXES)
        and k.lower() not in _DEDUP_IGNORED_QUERY_KEYS
    )
    return urlunparse((
        scheme, netloc, path, "",
        urlencode(filtered_query, doseq=True), "",
    ))


def candidate_identity_urls(repo: dict) -> set[str]:
    """Cross-source dedupe用の保守的な同一性URL集合。

    タイトル類似度のような推測的semantic matchingは使わず、収集時点で既に
    候補自身が保持している一次URL/公式URLだけを同一性根拠にする。これにより
    HN→GitHub、Product Hunt→公式サイト等の別Discovery Sourceが同じ一次URLを
    指すケースを重複排除できる一方、似た題名の別案件を誤って消さない。
    """
    raw_urls: list[str] = []
    for value in (repo.get("url"), repo.get("primaryUrl")):
        if isinstance(value, str) and value.strip():
            raw_urls.append(value.strip())
    details = repo.get("sourceDetails") or {}
    for key in (
        "external_url", "official_url", "officialUrl", "website", "website_url",
        "homepage", "project_url", "docs_url", "documentation_url",
        # Historical/migration alias: older Stock rows may have stored the discovery URL
        # before official URL resolution was introduced. These are explicit source URLs,
        # not title-similarity guesses, so using them as aliases is conservative.
        "hn_url", "producthunt_url",
    ):
        value = details.get(key)
        if isinstance(value, str) and value.strip():
            raw_urls.append(value.strip())
    # 収集済みの明示リンクだけを利用する。ここで新規HTTP取得はしない。
    for key in ("official_external_links", "links", "related_links"):
        values = details.get(key) or []
        if isinstance(values, (list, tuple, set)):
            raw_urls.extend(v.strip() for v in values if isinstance(v, str) and v.strip())
    return {canonicalize_url(u) for u in raw_urls if canonicalize_url(u)}


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


EXISTING_NOTION_PAGE_INDEX: list[dict] = []


def repair_existing_multilingual_notion_titles(max_updates: int = 25) -> int:
    """既存Stockの非Latin原題を0 API(Gemini)で人間向け表示名へ安全に補正する。

    get_existing_repo_urls()が同じNotion読取で作ったindexを再利用するため追加Readは不要。
    NameだけをPATCHし、URL/原題/Entity keyは変更しない。失敗は本体処理を止めない。
    """
    if not NOTION_API_KEY:
        return 0
    updated = 0
    for row in EXISTING_NOTION_PAGE_INDEX:
        if updated >= max(0, int(max_updates or 0)):
            break
        current = (row.get("name") or "").strip()
        if not current:
            continue
        language = _detect_title_language(current)
        if language in {"ja", "en", "und"}:
            continue
        display, _ = _multilingual_display_name(current, row.get("summary", ""), row.get("source", ""))
        if display == current:
            continue
        try:
            repo_stub = {
                "nameWithOwner": current, "originalTitle": current,
                "sourceLanguage": language, "source": row.get("source", ""),
            }
            repaired_summary = _source_summary_with_original(repo_stub, row.get("summary", ""))
            res = requests.patch(
                f"https://api.notion.com/v1/pages/{row.get('page_id')}",
                json={"properties": {
                    PROP_NAME: {"title": [{"text": {"content": display[:2000]}}]},
                    PROP_SOURCE_SUMMARY: {"rich_text": [{"text": {"content": repaired_summary[:2000]}}]},
                }},
                headers=_notion_headers(), timeout=10,
            )
            if res.status_code == 200:
                updated += 1
                logger.info("[MULTILINGUAL TITLE REPAIRED] %s -> %s", current, display)
            else:
                logger.warning("[MULTILINGUAL TITLE REPAIR SKIP] %s HTTP %s", current, res.status_code)
        except Exception as exc:
            logger.warning("[MULTILINGUAL TITLE REPAIR SKIP] %s: %s", current, exc)
    return updated


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

    global EXISTING_NOTION_PAGE_INDEX
    EXISTING_NOTION_PAGE_INDEX = []
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
            props = page.get("properties", {})
            url_prop = props.get(PROP_URL, {})
            page_url = url_prop.get("url")
            EXISTING_NOTION_PAGE_INDEX.append({
                "page_id": page.get("id"),
                "name": _notion_plain_text(props.get(PROP_NAME, {})),
                "source": ((props.get(PROP_SOURCE, {}).get("select") or {}).get("name") or ""),
                "summary": _notion_plain_text(props.get(PROP_SOURCE_SUMMARY, {})),
                "url": page_url or "",
            })
            if page_url:
                existing_urls.add(canonicalize_url(page_url))
            # Deep Dive済みページではEvidence URLsも既知aliasとして再利用し、
            # arXiv/GitHub/公式Blog等の別入口から同一案件が再Stockされる確率を下げる。
            evidence_text = _notion_plain_text(page.get("properties", {}).get(PROP_EVIDENCE_URLS, {}))
            for alias in re.findall(r"https?://[^\s<>()]+", evidence_text or ""):
                existing_urls.add(canonicalize_url(alias.rstrip(".,;")))

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
    payload = {
        "filter": {"property": PROP_CONTENT_STATUS, "select": {"equals": CONTENT_STATUS_PENDING_RETRY}},
        # 最も長く待っている候補から処理する。再失敗時のstatus更新でlast_edited_timeが
        # 新しくなるため自然に後段へ回り、同じ3件が後続を永久に塞ぐ飢餓を防ぐ。
        "sorts": [{"timestamp": "last_edited_time", "direction": "ascending"}],
        "page_size": min(100, limit),
    }
    res = _query_notion_db_with_retry(_notion_query_url(), _notion_headers(), payload)
    if res is None:
        return None
    items = []
    for page in res.json().get("results", []):
        props = page.get("properties", {})
        url = props.get(PROP_URL, {}).get("url")
        if not url:
            continue
        item_source = props.get(PROP_SOURCE, {}).get("select", {}).get("name") or "GitHub"
        # GitHub案件はStock保存時にPROP_LICENSEへ保持したSPDX IDを復元する。
        # ここが欠けるとLegal Safety Gateが再実行時にNO_LICENSE扱いにしてしまい、
        # 既に安全確認済みの案件を誤って弾く（推測で埋めるのではなく、保存値をそのまま戻す）。
        stored_license = _notion_plain_text(props.get(PROP_LICENSE, {}))
        license_info = {"spdxId": stored_license} if item_source == "GitHub" and stored_license else None
        items.append({"notion_page_id": page.get("id"), "repo": normalize_item(
            item_source,
            _notion_plain_text(props.get(PROP_NAME, {})), url,
            _notion_plain_text(props.get(PROP_SOURCE_SUMMARY, {})),
            props.get(PROP_ENGAGEMENT, {}).get("number") or 0,
            license_info=license_info,
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


def _fresh_regen_candidate_score(repo: dict) -> tuple[float, int, str]:
    """0-API ranking for fresh regression candidates.

    The score is intentionally not a Decision Score and is never persisted.  It only makes
    the test set reproducible enough to favor candidates with usable first-party evidence,
    current source metadata, and some source-native engagement.  Source diversity is applied
    separately so a single feed cannot dominate all three regression articles.
    """
    publishability = publication_probability_score({"repo": repo})
    engagement = int(repo.get("stargazerCount") or 0)
    published = str(repo.get("publishedAt") or "")
    return (float(publishability), engagement, published)


def get_fresh_regen_test_items(limit: int = 3, source_filter: str = "") -> list[dict] | None:
    """Collect *new* regression candidates with zero Gemini screening calls and zero writes.

    Safety/behavior:
    - Fetches a small bounded slice from the four normal acquisition sources.
    - Applies the same legal safety check used by production.
    - Reads the internal Notion URL set and excludes anything already known there.
    - Uses deterministic metadata-only ranking and round-robin source diversity.
    - Does not create/update Notion pages, upload images, run Screening, or publish anything.
    - The selected candidates still go through the normal Deep Dive + Quality Gate later.
    """
    fetch_limit = min(max(REGEN_FRESH_FETCH_PER_SOURCE, max(limit, 1)), 50)
    source_groups = {
        "GitHub": fetch_github_trending(fetch_limit),
        "HackerNews": fetch_hackernews_top(fetch_limit),
        "ArXiv": fetch_arxiv_ai_ml(fetch_limit),
        "ProductHunt": fetch_producthunt_trending(fetch_limit),
    }
    if source_filter:
        source_groups = {source_filter: source_groups.get(source_filter, [])}

    existing_urls = get_existing_repo_urls()
    if existing_urls is None:
        logger.error("[REGEN FRESH] Notion重複チェックに失敗したためFail-Closed停止")
        return None

    eligible_by_source: dict[str, list[dict]] = {}
    seen_identity_urls: set[str] = set()
    seen_fallback_keys: set[str] = set()
    for source, repos in source_groups.items():
        bucket: list[dict] = []
        for repo in repos:
            is_safe, license_status = legal_safety_gate(repo)
            if not is_safe:
                logger.info("[REGEN FRESH SKIP: LICENSE] %s -> %s", repo.get("nameWithOwner"), license_status)
                continue
            identity_urls = candidate_identity_urls(repo)
            title_key = _normalize_title_for_match(repo.get("nameWithOwner", ""))
            fallback_key = f"{repo.get('source', source)}:{title_key}"
            if (identity_urls & existing_urls) or (identity_urls & seen_identity_urls) or (not identity_urls and fallback_key in seen_fallback_keys):
                logger.info("[REGEN FRESH SKIP: KNOWN] %s", repo.get("nameWithOwner"))
                continue
            seen_identity_urls.update(identity_urls)
            if not identity_urls:
                seen_fallback_keys.add(fallback_key)
            bucket.append(repo)
        bucket.sort(key=_fresh_regen_candidate_score, reverse=True)
        eligible_by_source[source] = bucket

    # First pass: one strongest candidate per source, preserving normal source order.
    selected: list[dict] = []
    source_order = ["GitHub", "HackerNews", "ArXiv", "ProductHunt"]
    active_order = [s for s in source_order if s in eligible_by_source]
    for source in active_order:
        if len(selected) >= limit:
            break
        if eligible_by_source.get(source):
            selected.append(eligible_by_source[source].pop(0))

    # Backfill any remaining slots globally by the same 0-API ranking.
    if len(selected) < limit:
        remaining = [repo for source in active_order for repo in eligible_by_source.get(source, [])]
        remaining.sort(key=_fresh_regen_candidate_score, reverse=True)
        selected.extend(remaining[: max(0, limit - len(selected))])

    items: list[dict] = []
    for repo in selected[:limit]:
        metadata_score = publication_probability_score({"repo": repo})
        items.append({
            "notion_page_id": None,
            "screening_score": max(NOTION_SAVE_THRESHOLD_SCORE, int(metadata_score)),
            "screening_reason": "Fresh regression: 0-API source-native metadata selection; not a production Decision Score",
            "repo": repo,
        })
    logger.info(
        "[REGEN FRESH] collected=%s selected=%s sources=%s GeminiScreeningCalls=0 writes=0",
        sum(len(v) for v in source_groups.values()), len(items),
        ",".join(str(x["repo"].get("source") or "Unknown") for x in items),
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
# ダイジェストMarkdownのローカル保存先。会員限定資産のため公開Repositoryへ
# commitせず、GitHub ActionsのPrivate Artifactとして保持する。
MONTHLY_DIGEST_OUTPUT_DIR = os.environ.get("MONTHLY_DIGEST_OUTPUT_DIR", "monthly_digests")
# 旧外部補助コードとの環境変数互換だけを残す。公開GitHub uploadは無効化済み。
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

    【現在の集計仕様（意図的に維持している挙動）】
    フィルタはNotionの組み込み created_time（ページが新規作成された日時）を
    基準にしている。つまりこのダイジェストは「当月新規にStockされたページの集計」
    であり、「当月にDeep Diveへアップグレードされた実績」の集計ではない。
    そのため、前月にStockされ当月Deep Diveへアップグレードされたページは
    当月の集計に含まれない（前月の集計にStock状態として含まれている）。
    TODO: 「当月Deep Dive成果」を集計したい場合は、created_timeではなく
    Analyzed At（Deep Dive実行時刻）を基準にする必要がある。今回のNotion DB
    Persistence修正のスコープ外のため、挙動は変更せずここに明記するに留める。

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
            article_status = (props.get(PROP_ARTICLE_STATUS, {}).get("select") or {}).get("name", "")
            score = props.get(PROP_SCORE, {}).get("number")
            items.append({
                "name": name or "(無題)",
                "url": page_url,
                "source": source,
                "status": status,
                "article_status": article_status,
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

    # Subscriber向けDigestでは、内部Needs Editorial ReviewをDeep Dive完成記事として
    # 扱わない。ReadyのみDeep Dive、その他はStock資産として集計する。
    digest_items = []
    for it in items:
        row = dict(it)
        if row.get("status") == STATUS_DEEP_DIVE and row.get("article_status") != ARTICLE_STATUS_READY:
            row["status"] = STATUS_STOCKED
        digest_items.append(row)

    by_status: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for it in digest_items:
        by_status[it["status"]] = by_status.get(it["status"], 0) + 1
        by_source[it["source"]] = by_source.get(it["source"], 0) + 1

    deep_dive_items = sorted(
        (it for it in digest_items if it["status"] == STATUS_DEEP_DIVE and it.get("article_status") == ARTICLE_STATUS_READY),
        key=lambda x: (x["score"] or 0), reverse=True,
    )
    stocked_items_top10 = sorted(
        (it for it in digest_items if it["status"] == STATUS_STOCKED),
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
    """Deprecated safety guard: subscriber-only digestを公開GitHubへは送らない。

    旧コードや外部補助コードから誤って呼ばれてもraw URLを生成せず、private
    Actions artifact運用へ誘導する。
    """
    logger.warning(
        "[DIGEST PUBLIC UPLOAD DISABLED] %s -> subscriber-only asset; keep as private artifact",
        dest_filename,
    )
    return None

def generate_monthly_digest(target_date=None):
    """
    月末に、当月Notion DBへ保存された全データセット（Deep Dive＋ストックのみ
    双方）を集計し、Markdownダイジェストとしてローカル保存した上で運用者へ
    Telegram通知する。会員限定性を守るため公開GitHub URLへはコミットせず、
    GitHub Actionsのprivate artifactとして保持する。

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

    # 月次Digestは会員限定資産。raw.githubusercontent.comへコミットせず、
    # Workflowのprivate artifactとしてのみ保持する。
    deep_dive_count = sum(
        1 for it in items
        if it["status"] == STATUS_DEEP_DIVE and it.get("article_status") == ARTICLE_STATUS_READY
    )
    stocked_count = len(items) - deep_dive_count
    msg = (
        f"📦【月次ダイジェスト】{target_date.year}年{target_date.month}月分を集計しました。\n"
        f"総件数: {len(items)}件（Deep Dive Ready {deep_dive_count}件 / その他Stock資産 {stocked_count}件）\n"
        f"Private Artifact: {local_path}"
    )
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
    """Human editorial guidance: fix editorial intent, not visible sentence templates."""
    return """
【Human Editorial Style｜最重要】
ARTICLEは管理帳票でも、AIが「きれいに整理した説明文」でもない。人気のある人間のテックライターが、
一次情報を読んで「自分はどこが面白いと思ったか」を選び、読者に順番をつけて渡す文章として書く。

・全部を同じ熱量で説明しない。この記事でいちばん読者に持ち帰ってほしい論点を1つ決め、そこを軸にする。
・事実を網羅するより、判断に必要な事実を選ぶ。重要度の低い説明は短くするか、書かない。
・段落の長さと文の長さを意図的に揃えない。ただし短文を3つ以上連打して広告コピーのように煽らない。
・各節を「結論→理由→箇条書き→注意」の同型にしない。記事の流れに必要な順番を選ぶ。
・見出しは記事固有の内容から作る。「なぜ重要か」「ポイント」「まとめ」など汎用ラベルだけで済ませない。
・「ここで重要なのは」「注目すべきは」「ポイントは」「つまり」「言い換えると」を接着剤のように反復しない。
・「Aではありません。Bです。」の対比構文を連発しない。効く場所で一度使うのはよい。
・「ひとつは〜。もうひとつは〜。」「理由は3つあります。」のように、内容を型へ押し込まない。
・「〜という点です」「〜と言えます」「〜となります」を同じ記事で何度も続けない。
・一次情報を説明したあと、筆者の判断や留保を自然に差し込む。ただし架空の経験・感情は作らない。
・「私は驚いた」「使ってみた」「以前から気になっていた」「現場で担当してきた」は、実体験の根拠がない限り禁止。
・筆者の主観は「私なら、この条件なら試す」「ここはまだ評価を保留する」のような判断として書く。
・読者を急かす煽り、営業コピー、過剰な疑問文を避ける。自然な好奇心で読ませる。
・箇条書きは比較・条件・次のアクションなど、一覧にした方が理解が速いところだけに使う。
・最終判断は曖昧な「注視したい」で逃げず、試す／待つ／見送る／比較する等の具体的な距離感を示す。
・安全性のために記事全体を弱くしない。根拠のない一文だけを弱め、根拠のある面白さと判断は残す。
・同じ内容を言い換えて二度説明しない。読者が一度で理解できる説明はそこで止める。
・接続詞で論理を毎回明示しすぎない。段落の並びだけで意味がつながる場所では「一方で」「そのため」「つまり」を足さない。
・別の記事でも使える汎用的な導入・判断フレーズへ逃げず、この一次情報だから成立する入口と情報順序を選ぶ。
・Roadmap、protocol、SDK、仕様変更のような抽象テーマでも、定義や項目列挙から始めない。読者が実際に困る場面、従来の前提が崩れる瞬間、または「なぜ今これが話題なのか」という記事固有の違和感から入り、そこから技術の核心へ進む。架空の体験談は作らない。
・Security / Sandbox / Isolationでは「何をしてもPCへ影響しない」「被害をこの範囲だけに抑え込める」「安全が担保される」のような保証相当の断定をしない。一次情報が示す隔離機構と、残る条件・制約を分けて書く。
・「興味深い」「注目すべき」「実務的な示唆」「第一の柱／第一段階／第二段階」「妥当な判断と言えます」等の編集語彙を一記事に積み重ねない。必要な語を単発で使うのはよいが、説明を整えすぎず事実そのものに語らせる。

【Reader Experience｜知的エンタメ × Decision Intelligence】
・難しいことを難しく感じさせない。正確さ・Evidence・制約・Decisionを保ったまま、専門書や辞書なしで読み進められる入口を作る。
・専門用語は消さない。この記事の判断に必要な難しい概念は、初出時に「意味や身近な働き＝普通の言葉で何をするものか → 必要なら日常の具体場面・比喩 → 正式名称」の順で橋を架ける。中学生〜非エンジニアが一読後に核心を自分の言葉で1文説明でき、専門家には正式名称・条件・Evidenceが残る状態を狙う。
・判断の中心となる未知語を、説明なしで2個以上ひとつの文・段落へ積み上げない。DPoP、WIF、microVMのような略語・規格名・技術語が続くなら、先に「何を防ぐ／何を可能にする仕組みか」を平易な一文で置いてから詳細へ進む。
・専門語密度が高い記事では、少なくとも一度は非エンジニアの日常と接続する具体的な橋を選ぶ。恋愛、買い物、スマホの権限、鍵、学校、旅行、料理、家族、趣味などは候補にすぎず、記事に最も自然な題材だけを使う。毎回同じ題材や決まり文句を使わない。
・比喩は概念理解の補助でありEvidenceではない。比喩で理解させた直後に技術上の正式な意味へ戻り、似ていない部分まで同一視しない。正確さを落とす比喩なら使わず、平易な機能説明か具体場面で代替する。
・冒頭は発表要約だけで始めず、この話題のどこが人間的に面白いか、読者の仕事や生活に何が変わるか、あるいはどんな意外性があるかから入口を選ぶ。煽りは不要。
・比喩や身近な例は、理解・記憶・心理的距離の改善に本当に効く場所だけで使う。比喩を入れること自体を目的にせず、1記事の個数も固定しない。
・猫、恋愛、コンビニ、家族、学校など特定の題材を毎回使わない。Security / Risk / Governanceなど深刻なテーマでは軽薄な笑いや不釣り合いな比喩を強制しない。
・面白さは笑いではなく、意外性、発見、比較、知的快感、自分とのつながり、常識が少し覆る感覚から記事ごとに選ぶ。
・技術の価値を「すごい」「非常に魅力的」などの形容詞だけで済ませず、何がどう変わるから面白いのかを具体的な事実で見せる。
・重要な場面では、この情報が最も関係する読者にとって何を意味するかを自然に橋渡しする。ただし会社員・経営者・学生など全対象を毎記事列挙しない。
・初心者に合わせてEvidence、数値、制約、比較、一次情報、リスクを削らない。「素人でも読めるが、専門家が読んでも浅くない」を狙う。
・記事末尾では、新しい理解、次に知りたい疑問、実生活とのつながり、具体的な判断または行動のいずれかが自然に残るようにする。毎回同じCTAや勧誘文で閉じない。
・内部では、このテーマ固有の面白さ／最初につまずく概念／身近な例が有効な箇所／比喩を使わない方がよい箇所／自分事化ポイント／読後に残す専門語／最重要Decisionを選んでから書く。これらを可視の固定見出しにはしない。
・「分かりやすい説明」で止めず、読者が次の段落へ進む理由を記事全体に置く。疑問、意外性、逆説、比較、具体場面、リスク、未来像のうち、この一次情報に本当に効くものだけを選ぶ。クリックベイトや過剰な煽りにはしない。
・ニュース記事では、なぜ今日・今週・今回このテーマを読む価値があるのかを、公開日・更新・採用・仕様変更・普及・発見された問題など取得済みEvidenceから早い段階で示す。確認できない「最新」「急速に普及」「業界が注目」は作らない。
・抽象説明や仕様列挙が長く続く箇所は、可能なら一度だけ具体的な場面・比較・問いへ置き換えてから技術要件へ戻す。重要な要件や制約自体は削らない。
・中盤で企業ホワイトペーパーへ戻らない。権限、制約、要件などは、まず何が起こる場面なのかを理解させ、その後で必要な専門要件を渡す。
・【無料note記事の最上位編集目標】読み手が「楽しい」「わかりやすい」「自分にも関係がある」と感じ、AIやITに詳しい人から面白い話を聞いていたら、いつの間にか核心を理解できていた状態を最優先する。技術レポートとして整っているだけでは完成としない。Evidence・数値・制約・反証・Decisionの正確さは絶対に落とさず、それらを読者が自然に理解できる順番と言葉へ編集する。親近感は口語句の数ではなく、読者の経験・疑問・判断と本文がつながっていることで成立させる。
・見出しは説明ラベルではなく、本文固有の意味と次を読む理由を持たせる。「なぜ重要か」「何が変わるか」「今後どうなるか」「最終判断」等を複数並べない。
・Decisionは報告書の固定章として処理せず、事実・制約・適用条件から自然に「私ならまず何をするか」へ到達させる。主観とEvidenceは混同しない。
・Reader-firstの「30秒でわかるこの記事」は公開UI上の要約であり、本文の段落順・見出し順・導入文型を固定するテンプレートではない。本文はその3項目をなぞらず、記事固有の流れを選ぶ。
・会社、営業、会議、CRMだけに例が偏らない。旅行、買い物、家族、学校、趣味、スマホ、SNS等の方が理解が速い場合だけ選ぶ。ただしB2B専門テーマに無理な生活ネタを入れない。
・「実は」「少し考えてみましょう」「○○に例えると」「また3文字の専門用語か」等の演出句へ逃げない。単発使用はよいが、別記事でも使える決まり文句として反復しない。「ここで重要なのは」「ポイントは」「つまり」「注目すべきは」のようなAIが説明を整理するときの常套句も、便利だからという理由で段落頭に繰り返さない。接続語で流れを作るのではなく、前の段落で生まれた疑問・意外性・判断の続きを次の段落が自然に受ける。
・語り口は「教師が講義する」より「AIやITに詳しい友人が隣で、面白いところを一緒に見せてくれる」距離感にする。です・ます調を土台にし、読者を抽象的な「ユーザー」として扱わず、実際にスマホやPCを触り、仕事や生活で迷う一人の人として書く。1記事の中で原則1〜3箇所は、読者の実体験を思い出させる問いかけ、難しい名前への一言、身近な場面への接続など「読者との距離が近くなる一文」を自然に成立させる。ただし毎節で呼びかけたり、相づちを連打したりしない。Security / Risk等で軽い語りが不適切な場合は、無理な冗談ではなく静かな問いかけや平易な一言で距離を縮める。
・親近感は疑問形や相づちの数で採点しない。Security・Risk・Hardware・Researchのようなテーマでは、落ち着いた語りでも、読者が普通の言葉で核心を理解し、制約と判断まで自然に到達できれば十分に人間的で親しみやすい。口語句を足すためだけの修正は禁止する。
・Reader Delightは冒頭だけで作らない。導入で親近感を出した後に本文が技術レポートへ戻る構成は禁止する。記事全体で「読者の疑問 → 普通の言葉で理解 → なぜそうなるか → 何が面白い／困るか → 自分ならどう見る・判断するか」と理解が前へ進む流れを作る。各段落は前段落で生まれた疑問か意味を受け、情報カードの羅列にしない。
・比喩は理解のための橋であり、面白さの代用品ではない。比喩だけで分かった気にさせず、比喩の直後または近接段落で「実際の技術では何が対応するのか」「なぜその現象が起きるのか」を最低1つ具体化する。かわいい例・日常例・口語表現が多くても、技術的な芯や因果が薄ければ完成としない。
・Reader Proximityは「使ってもよい装飾」ではなく、無料note記事の完成条件として扱う。ただし品質Gateを緩めたり、親しみ不足だけを理由にGemini再生成を増やしたりしない。記事全体の温度を1〜2個の口語句で済ませず、硬い説明が2段落続いたら次の段落では、追加説明を足さず、既存文を「読者の判断／具体場面／平易な一言」のどれかへ置き換えて人間の言葉へ戻す。語りかけは装飾ではなく理解の橋として使い、「あなたならどうしますか？」のような中身のない問いは置かない。問いかけたなら、その直後の文で読者が何を見ればよいか・なぜ自分に関係するかへつなげる。ARTICLE全体が長い場合は段落追加ではなく削除・統合を優先する。
・「ですよね。」「やっぱり、」「なんですよ。」「ちょっと想像してみてください。」「ここが面白いところです。」等は使用可能な例であり必須語ではない。固定語でもない。特定の語尾を義務化せず、役割としての親近感を満たす。1記事で同じ語尾・呼びかけを反復せず、記事ごとに語彙を変える。
・親しみやすさのために文章を足し算しない。会話的な一文や日常例は、既存の硬い説明・接続文を置き換えて作る。独立した雑談段落を追加せず、同じ事実を「専門説明＋比喩説明」で二重に説明しない。『硬い説明→親しい説明』は置換であり追記ではない。
・この無料ARTICLEで読者が本当に覚える専門概念を内部で原則2〜3個に絞る。4個目がないとDecisionを誤解する場合だけ4個まで許す。核心概念は「普通の言葉で役割 → 必要なら短い日常例 → 正式名称」の順で理解させる。それ以外の略語・規格番号・内部実装名は、Decisionや重要な制約に不可欠でなければ本文から外すか、意味を一文に圧縮する。一次情報に存在する技術名を全部ARTICLEへ転記することは禁止する。ARTICLE本文で説明する中核概念は原則2〜3個、実装識別子・規格名・コマンド名は意思決定に必要なものだけに限定し、列挙で専門性を演出しない。
・Evidenceの深さとARTICLEの専門語数を混同しない。数値、重要な制約、比較条件、反証、一次情報の根拠、Decisionに必要な技術事実は残す。一方、実装詳細の羅列はSources/Evidenceへ戻って確認できるため、無料ARTICLE本文では「判断に何を意味するか」を優先する。有料会員向けProduct Review / Notion DBの情報密度をARTICLE圧縮に合わせて削らない。
・各見出しでは、最初の1〜2文で非エンジニアにも意味が取れる普通の日本語を置いてから専門語へ進む。専門語だけで段落を開始しない。専門語を説明するために別の未説明専門語を持ち込まない。
・「読みやすくするための追加説明」で長くしない。削る優先順位は、Decisionに不要な内部実装、規格番号・略語の列挙、重複説明、汎用的な前置き、同じ意味の言い換え。Evidence、数値、制約、比較、反証、Decisionは先に削らない。分かりやすさは情報量の水増しではなく、選択・順序・言い換えで作る。
・最終出力前にARTICLEだけを読者目線で再編集する。目標は最終公開稿の目標は2,200〜3,000字、3,200字はSoft Ceiling。『30秒でわかるこの記事』・元情報・Sources / Evidenceなどが後段で追加されるため、生成するARTICLE本文は原則1,800〜2,300字に収める。最終稿が3,200字を超えそうなら、Evidence・数値・制約・比較・反証・Decisionを残し、実装手順の網羅、固有技術名の列挙、二重説明、長いコード例、一般論を先に削って完成させる。ARTICLEは実装チュートリアルやリファレンスマニュアルではなく、読者が採用・試用・見送りを判断するための記事である。コードブロックは意思決定に不可欠な場合を除き出さず、手順・機能・注意点の列挙はそれぞれ最大3項目まで。『詳しく書けるから書く』は禁止とする。3,200字を超えそうなら新しい説明を足さず、Decisionに不要な技術詳細を圧縮する。どうしても重要Evidenceや制約のため超える場合は許容するが、4,000字級を『専門テーマだから仕方ない』で正当化しない。
・最終セルフチェックでは「中学生〜非エンジニアが、この記事を読み終えて『要するに○○の話』と一文で言えるか」「最初の800字だけでも続きを読みたいと思えるか」「3段落以上、専門用語の説明だけが連続していないか」を確認し、失敗していれば新しい情報を足さずに言い換え・圧縮・順序変更で直す。
・「ですよね。」は読者に同意を強要するためではなく、スマホの権限確認、買い物、通勤など多くの人が経験した具体場面を思い出してもらう用途に限る。根拠のない一般化や価値観への同意要求には使わない。
・親近感の一文や比喩から、Evidenceにない固有名詞・数値・市場評価・利用実績を新しく作らない。比喩は理解補助であり新しいFactではない。これにより親しみやすさを理由にFact Gate / Source Boundaryの表面積を増やさない。
・Fact / Evidence / 数値 / 制約 / Security上の重要事項は会話調でぼかさず、冷静で断定範囲の明確な文体を保つ。説明は親しみやすく、Evidenceは冷静に、Decisionは頼れる温度にする。
・会話調を記事全体へ均一に散らさない。連続した文末の「〜ですよね。」「〜なんですよ。」や、毎段落の読者呼びかけは避ける。親近感は口癖ではなく、語彙の平易さ、具体場面、文章の間、問いかけの自然さで作る。
"""

def build_decision_prompt(name, url, stars, desc, quality_feedback: str = "", source: str = "GitHub",
                          source_context: str = "", grounding_status_hint: str = GROUNDING_METADATA_ONLY,
                          evidence_metadata: dict | None = None, freshness: dict | None = None,
                          previous_article: str = "", evidence_result: dict | None = None):
    """無料ARTICLEと記事公開に必要な最小MANAGEMENT DATAだけを生成する。

    Adoption/Production Readiness等の会員向け評価はProduct Review経路へ完全分離し、
    無料記事の生成負荷・Hallucination面積を増やさない。parserは旧出力互換を維持する。
    """
    metric_label = ENGAGEMENT_LABELS.get(source, "Engagement")
    metric_note = ""
    if source == "ArXiv":
        metric_note = "※arXivにはStars/Votes相当の人気指標がないため、人気度を0とみなして価値判断しないこと。\n"
    feedback = f"\n【前回出力への編集フィードバック】\n{quality_feedback}\n事実違反は該当箇所だけを直す。全文を保守的に均さず、根拠付きの判断・具体的な行動・タイトルの引力は残す。具体的Actionを『注視する』だけに置き換えない。\n" if quality_feedback else ""
    previous = ""
    if previous_article:
        previous = (
            "\n【局所修正の対象となる前回ARTICLE】\n"
            "以下の前回稿を基準に、編集フィードバックで指定された箇所だけを修正して、"
            "同じ出力形式の完全稿を返すこと。指定外の根拠付き判断・見出し・構成を一般論へ置換しない。\n"
            + previous_article[:MAX_EVIDENCE_TOTAL_CHARS] + "\n"
        )
    context = _truncate_source_context(source_context)
    fact_rules = _source_fact_discipline(source)
    style_rules = _human_editorial_style_rules()
    display = _article_display_variant(name)
    evidence_json = json.dumps(evidence_metadata or {}, ensure_ascii=False, indent=2)
    freshness_context = (freshness or {}).get("context", "")
    evidence_result = evidence_result or {}
    evidence_guardrails = []
    if evidence_result.get("limitations_disclosed"):
        evidence_guardrails.append("一次資料で実運用上の制約は確認できないことをWhy NOTまたはCaveatに明記し、本番導入を強く推奨しない。")
    if evidence_result.get("freshness_scope_limited"):
        evidence_guardrails.append("現在仕様とは断定せず、『原資料公開時点では』『この研究で確認された範囲では』と時点を限定する。")
    if not evidence_result.get("numeric_claims_allowed", True):
        evidence_guardrails.append("条件を確認できない数値・性能値はARTICLEで使わない。")
    if not evidence_result.get("actor_attribution_allowed", True):
        evidence_guardrails.append("主体の帰属を確認できない固有名詞の断定はしない。")
    if evidence_result.get("action_risk_tier", "LOW") == "LOW" and evidence_result.get("evidence_gap_disclosed"):
        evidence_guardrails.append("Actionは『注視』だけで終わらせず、限定PoC、評価項目への追加、ログ可視化、比較テスト、見送りのいずれかを具体的に提案する。全面導入・本番移行は提案しない。")
    evidence_guardrail_text = "\n".join("・" + item for item in evidence_guardrails) or "・取得済み一次情報の範囲を超える断定をしない。"

    return f"""
あなたはAI・ソフトウェア領域のシニアCTOアドバイザーであり、商業メディア経験のある日本語テック編集者です。
以下の一次情報から、無料公開のnote記事として読者の判断を助ける記事と、記事公開に必要な最小管理データを作成してください。
会員向けTechnology評価（Adoption Score / Adoption Status / Evidence Confidence / Production Readiness / Main Risk / Best For / Avoid For）は別工程で作るため、ここでは絶対に生成しないでください。

【読者】主対象はCTO、テックリード、PM、AI/ソフトウェア導入の意思決定者。ただし専門知識を前提にせず、非エンジニアや一般読者でも入口から理解でき、専門家には判断材料が残る二層構造で書く。
【最重要】ARTICLEは人が読む文章、MANAGEMENT DATAは機械が読む構造データ。両者を混ぜない。
【出力を途中で切らないための優先順位】
1. SECTION_SPLIT_TOKEN、記事タイトル、記事本文の最後の「最終判断」までを最優先で完走する。
2. MANAGEMENT DATAは下記の8項目だけを簡潔に出す。記事本文を削って管理項目を増やさない。
3. 無根拠な背景説明・一般論・競合列挙を追加しない。
4. 不確かな比較・将来予測・導入コストを埋めるために推測しない。途中で省略記号を使わない。
【事実優先順位】Source Native Context > Primary URL取得内容 > Google Search Grounding（有効時） > モデル内部知識。

【SOURCE BOUNDARY — 最重要】
・ARTICLEで「事実」として断定してよい技術仕様・対応状況・価格・数値・競合情報・固有名詞は、原則としてSource Native ContextまたはGroundingで確認できる内容だけ。
・モデル内部知識から背景説明を補う場合は、製品固有の事実として書かず、「一般論として」「ここからは私の推論だが」など、読者が推論だと分かる形にする。
・Source Contextにない企業向け管理製品、競合機能、API仕様、OS/ブラウザ管理方式などを、もっともらしい補足として追加しない。
・ニュース公開時点の仕様と現在のStable仕様は同一視しない。現在仕様をGroundingで確認できなければ「元記事公開時点では」と限定する。
・不明点は補完せず「一次情報からは確認できない」と書く。
・「確認できない」「記載がない」「未公開」「不明」等の不在Claimは、Evidence Coverageが SEARCHED_NOT_FOUND または NOT_DISCLOSED の項目だけに限る。NOT_SEARCHEDまたはSource Depth不足では不在を断定しない。
モデル内部知識だけで現在仕様、競合比較、数値、価格、対応状況を断定しない。

【Evidence-to-Decisionの安全制約】
{evidence_guardrail_text}

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
{previous}

最初に必ず次の見出しをそのまま出す。
=== MANAGEMENT DATA ===
その下に以下の8項目だけを順序通り、各行「・ラベル: 値」で簡潔に出す。
・Source Summary: 一次情報で確認できる事実を1〜2文。
・What: 何が起きたかを2文以内。
・Why Important: 実務への意味。未検証効果は推論と明示。
・Decision: NOW / TRY / WATCH / WAIT / AVOID の1つ。
・Decision Reason: 最大3理由を簡潔に。
・Decision Score: Business Impact X/25; Technical Impact X/25; Urgency X/20; Market Impact X/15; Reliability X/15; 合計 X/100
・Action: 次に検証する具体的行動。根拠のない日数・金額を作らない。
・Article Value: 0〜100

会員向け評価、競合比較、移行コスト、将来シナリオ、Who Should Use等をMANAGEMENT DATAへ追加しない。必要な実務上の対象読者・制約はARTICLE本文へ自然に書く。

次に必ず専用行を出す。
{SECTION_SPLIT_TOKEN}

その次の1行を記事タイトルにする。#は付けない。プロのコピーライターとして、技術の要点と読者の関心を結び、短く惹きつけるタイトルにすること。必ず「。」「？」のいずれかで終える。

【ARTICLE】
記事はすべて無料公開する。有料エリア、有料マーカー、無料部分／有料部分という区分を一切出力しない。

今回は内部の編集ブリーフとして「{display['style']}」の角度、導入のヒント「{display['opening']}」、温度感「{display['tone']}」を使う。
これらは読者に見せるラベルでも見出しでもない。既成の見出し文や段落テンプレートを再現せず、記事固有の内容に合わせて自由に構成する。

タイトル直後は、読者が「何の話か」「なぜ自分に関係するか」をつかめる自然なリードから始める。
Roadmapやprotocolの話でも、冒頭を「〜とは」「主な変更点は」「今回のロードマップでは」の説明開始に固定しない。まず読者が引っかかる変化・困りごと・意外性を1つ置き、専門用語は理解が必要になった時点で名前を付ける。
リードの段落数は固定しない。1〜3段落程度を目安に、必要な情報だけを書く。
発見経路や「一次情報に基づく」という説明を義務的な定型文として毎回入れない。出典は公開稿の「元情報」で別途提示されるため、本文では話を理解するのに必要な場合だけ自然に触れる。

本文の見出しは2〜6個程度を目安に、記事固有の内容から自分で作る。本文セクションの見出しは必ずMarkdownの `##` または `###` を付け、見出し文だけを裸の1行として置かない。以下は内部の意味役割であり、見出し名や順番を固定しない。
・何が起きた／何が変わったのか
・なぜ読者の判断に関係するのか
・仕組みや条件のうち、判断に必要な部分
・面白さと同時に見ておくべき制約
・筆者なら次に何をするか

すべての役割を毎回独立セクションにしない。内容が自然につながるなら統合する。
一方で、記事の終盤には「読者が結局どう動けばよいか」が分かる判断セクションを必ず1つ置く。見出しは記事内容に合わせて自然な日本語で作り、管理用Decisionコードは書かない。

【構成上の禁止】
・Why → What → Key → Decision のような内部構造を、そのまま同じ順番・同じ粒度の見出しへ露出しない。
・旧テンプレートの「先に判断を書くと。」「なぜ、この問題が残り続けるのか。」「今回の仕組みを見てみる。」「導入前に押さえたいポイント。」等をセットで再利用しない。
・各セクションを同じ文字量にそろえない。
・全セクションを同じ「説明→注意→結論」で閉じない。

【ARTICLEの追加ルール】
・NOW / TRY / WATCH / WAIT / AVOID は内部管理コードであり、ARTICLEには絶対に表示しない。括弧書き、英字併記、見出し内も禁止。
・「私ならこう考える」では、管理用Decisionを読者向けの自然な判断文に翻訳する。目安は次の通り。
  NOW → 「今すぐ動く価値がある」「今から着手してよい」
  TRY → 「まずは小さく試す価値がある」「限定した環境で試したい」
  WATCH → 「今は動かず、今後の動きを注視したい」「導入を急ぐ段階ではない」
  WAIT → 「現時点では導入を急がない」「条件が整うまで待つのがよい」
  AVOID → 「今は見送るのが妥当」「現時点では採用しない方がよい」
・上の日本語は定型句として毎回そのまま使わず、記事の文脈に合わせて自然に言い換える。Decision ScoreやBusiness Impact等の内部採点もARTICLEへ一切出さない。採点はMANAGEMENT DATAだけに置く。
・Adoption Score / Adoption Status / Evidence Confidence / Production Readiness も商品DB管理値であり、ARTICLEへラベルや点数をそのまま表示しない。
・競合名を出す場合、Source Native Contextにその競合の比較根拠が存在する時だけ。なければ製品名を列挙しない。
・Preview/Beta/Stableは必ず分離する。
・ニュース公開時点の仕様を現在仕様として断定しない。現在確認できない場合は「元記事公開時点では」と書く。
・根拠のない%・倍数・金額・期間・性能値を作らない。
・「唯一」「一択」「必須」「デファクト」「圧倒的」「劇的」「完全に解決」等は、一次情報だけで立証できない限り使わない。
・記事全体を箇条書き帳票にしない。導入を含め、読者が技術の背景から判断まで自然に追える流れにする。
・「結局、どうするべきか」の結論は管理用Decisionと意味的に一致させる。ただし内部コードは書かない。
・根拠に照らして限定検証、比較テスト、導入見送り、次版待ちなどの判断が妥当なら、理由と対象範囲を添えて明確に書く。安全性のためにすべてを「可能性がある」「注視したい」へ弱めない。
・記事本文の文字数を品質目標にしない。同じ事実の言い換え反復、Decisionに不要な実装列挙、長いコード例、説明の二重化は削る。一方で、Evidence・数値条件・制約・比較・反証・Decisionを文字数のために削らない。長くても読者が迷わず読み進められる情報順序と温度変化を優先する。
"""

def _extract_note_title(note_draft_raw: str) -> tuple[str, str]:
    """
    note原稿の先頭行を記事タイトルとして抽出し、残りの本文と分離する。

    現行プロンプトではSECTION_SPLIT_TOKEN直後に「タイトル行 → 空行 → 無料本文」
    を出す。旧paywall形式の原稿が入力されても後方互換処理でmarkerを除去できる。
    以前はタイトル行を本文から分離しておらず、build_clean_note_manuscript側でも
    そのまま本文の一部として扱われ、Notionの独立プロパティとして構造化できなかった
    （またタイトルが実質的に記事本文の1行目として二重表示される形になっていた）。

    ここでタイトル行を切り出し、残りの本文だけを後続処理へ渡すことで、
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
        "intro": ["はじめに", "気になった背景", "数字の前に見ておきたいこと", "現場で起きがちな課題から"],
        "conclusion": ["この記事の結論", "まず、結論から", "先に判断を書くと。", "この話をどう受け止めるか。", "いま導入を急ぐべきか。"],
        "why": ["なぜ今、この情報を見るべきなのか", "なぜ今、目を向けるのか。", "地味だけれど、ここが大きい。", "実務への影響はどこに出る？", "従来の前提と、どこが違うのか。"],
        "what": ["What｜これは何か", "何が起きている？", "中身をざっくり見る。", "仕組みは意外とシンプルです。", "まずは何をしている技術なのか。"],
        "key": ["ここまでの要点", "要点を整理すると。", "見落としたくないポイント。", "ここで判断が分かれる。", "導入前に見ておきたいところ。"],
        "decision": ["私ならこう考える", "私の判定", "私なら今はこうする。", "実務で使うなら、私はこうする。", "私なら、まず小さく確かめる。", "私ならこの範囲で試す。"],
        "final": ["結局、どうするべきか", "結局、どう見るか。", "いま取るべき距離感。", "急がず、でも見逃さない。", "最後に、判断をまとめる。"],
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
        note_draft, _ = _strip_internal_note_control_lines(note_draft)
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

    adoption_breakdown_match = re.search(
        r"・Adoption Score[:：]\s*(.*?)(?=\n・Adoption Status|\n・Evidence Confidence|$)",
        management_data, re.DOTALL,
    )
    adoption_score_breakdown_text = adoption_breakdown_match.group(1).strip() if adoption_breakdown_match else ""
    adoption_total_match = re.search(
        r"・Adoption Score[:：][^\n]*?合計[:：]?\s*(\d+)\s*/\s*100",
        management_data, re.IGNORECASE,
    )
    adoption_score = int(adoption_total_match.group(1)) if adoption_total_match else 0

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
        "adoption_score": adoption_score,
        "adoption_score_breakdown_text": adoption_score_breakdown_text,
        "adoption_status": extract_field("Adoption Status", "").strip().upper(),
        "evidence_confidence": extract_field("Evidence Confidence", "").strip().upper(),
        "production_readiness": extract_field("Production Readiness", "").strip().upper(),
        "main_risk_text": extract_field("Main Risk", ""),
        "best_for_text": extract_field("Best For", ""),
        "avoid_for_text": extract_field("Avoid For", ""),
        "short_rationale_text": extract_field("Short Rationale", ""),
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
    r"\d+(?:\.\d+)?\s*(?:〜|～|-|–|—|to)\s*\d+(?:\.\d+)?\s*%",
    r"\d+(?:\.\d+)?\s*(?:〜|～|-|–|—|to)\s*\d+(?:\.\d+)?\s*(?:倍|x|×)",
    r"\d+\s*分の\s*\d+",
    r"\d+(?:\.\d+)?\s*%",
    r"\d+(?:\.\d+)?\s*(?:倍|x|×)",
    r"(?:約|およそ|最大|最低|平均)?\s*\d[\d,]*(?:\.\d+)?\s*(?:円|万円|億円|ドル|USD|JPY)",
    r"\d+(?:\.\d+)?\s*(?:ms|ミリ秒|秒|分(?!\s*(?:の|野|割|布|類|岐|析))|時間)",
    r"\d+(?:\.\d+)?\s*(?:日|週間|週|ヶ月|か月|月)\b",
    r"\d[\d,]*(?:\.\d+)?\s*(?:GB|MB|TB|GPU|台|人|件|行|リクエスト|requests?|tokens?|トークン)\b",
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
    # 「coming months」から勝手に『半年』へ具体化するような期間の水増しを検知する。
    r"半年",
    r"数(?:日|週間|週|ヶ月|か月|月|年)",
]


def _normalized_evidence_text(text: str) -> str:
    return re.sub(r"[\s,，]", "", unicodedata.normalize("NFKC", text or "").lower())


def _normalized_named_fact(text: str) -> str:
    """固有名詞の空白・ハイフン・PDF抽出時の合字揺れを吸収する。"""
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", text or "").lower())


def _normalize_numeric_evidence_text(text: str) -> str:
    """数値表現の表記揺れだけを正規化する。意味や条件は補完しない。"""
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    # 日本語分数「40分の1」= 1/40 を英数字表現と照合可能にする。
    normalized = re.sub(r"(\d+)\s*分の\s*(\d+)", lambda m: f"{m.group(2)}/{m.group(1)}", normalized)
    normalized = normalized.replace("ミリ秒", "ms").replace("秒", "s")
    normalized = re.sub(r"\bseconds?\b|\bsec\b", "s", normalized)
    normalized = normalized.replace("トークン", "tokens").replace("リクエスト", "requests")
    normalized = re.sub(r"\btoken\b", "tokens", normalized)
    normalized = re.sub(r"\brequest\b", "requests", normalized)
    normalized = re.sub(r"(?<=\d)分(?!\s*(?:野|割|布|類|岐|析))", "minutes", normalized)
    normalized = re.sub(r"(?<=\d)日", "days", normalized)
    normalized = normalized.replace("時間", "hours").replace("週間", "weeks").replace("週", "weeks")
    normalized = re.sub(r"\bminutes?\b|\bmins?\b", "minutes", normalized)
    normalized = re.sub(r"\bdays?\b", "days", normalized)
    normalized = normalized.replace("ヶ月", "months").replace("か月", "months")
    normalized = re.sub(r"\bhours?\b", "hours", normalized)
    normalized = re.sub(r"\bweeks?\b", "weeks", normalized)
    normalized = re.sub(r"\bmonths?\b", "months", normalized)
    normalized = normalized.replace("ドル", "usd")
    normalized = re.sub(r"\busd\b", "usd", normalized)
    normalized = normalized.replace("×", "x").replace("倍", "x")
    normalized = normalized.replace("パーセント", "%")
    normalized = re.sub(r"\bpercent(?:age)?\b", "%", normalized)
    normalized = normalized.replace("〜", "-").replace("～", "-").replace("–", "-").replace("—", "-").replace("−", "-")
    normalized = re.sub(r"\bto\b", "-", normalized)
    # 10-hour / 10 hours、50%-80% / 50-80%等を同じ表記へ寄せる。
    normalized = re.sub(r"(?<=\d)-(?=(?:hours|minutes|days|weeks|months|ms|s|tokens|requests)\b)", "", normalized)
    normalized = re.sub(r"%(?=-\d)", "", normalized)
    normalized = normalized.replace("約", "")
    return re.sub(r"[\s,，]", "", normalized)


def _numeric_claim_condition_tags(text: str) -> dict[str, set[str]]:
    """数値近傍の条件を粗くタグ化する。異なる条件の同一数値を誤Groundingしないための補助。"""
    raw = text or ""
    low = raw.lower()
    metric_map = {
        "speed": r"速度|高速|throughput|tokens?/s|tok/s|speed|latency|runtime|処理時間|レイテンシ",
        "memory": r"メモリ|memory|vram|ram",
        "accuracy": r"精度|accuracy|f1|auc|precision|recall",
        "cost": r"費用|コスト|cost|price|pricing|料金",
        "energy": r"電力|消費電力|energy|power",
    }
    metrics = {name for name, pattern in metric_map.items() if re.search(pattern, low, re.I)}
    hardware = set(re.findall(
        r"(?<![A-Za-z0-9])(?:A|H|V|L|T|P)\d{2,5}(?![A-Za-z0-9])|"
        r"(?<![A-Za-z0-9])RTX\s*\d{3,5}(?![A-Za-z0-9])|"
        r"(?<![A-Za-z0-9])M[1-9](?![A-Za-z0-9])", raw, re.I
    ))
    hardware = {re.sub(r"\s+", "", item).upper() for item in hardware}
    datasets = {item.lower() for item in re.findall(r"(?<![A-Za-z0-9])dataset\s+[A-Za-z0-9_.-]+", raw, re.I)}
    return {"metrics": metrics, "hardware": hardware, "datasets": datasets}


def _numeric_condition_compatible(claim_window: str, evidence_window: str) -> bool:
    claim = _numeric_claim_condition_tags(claim_window)
    evidence = _numeric_claim_condition_tags(evidence_window)
    # 両側に明示条件がある場合だけ矛盾をFailにする。Evidence側に条件記載が無い場合は
    # 文字列の存在だけで過剰Rejectしない（別行/表見出しに条件があるケースを考慮）。
    for key in ("metrics", "hardware", "datasets"):
        if claim[key] and evidence[key] and claim[key].isdisjoint(evidence[key]):
            return False
    return True


def _is_protocol_cardinality_expression(text: str, start: int, end: int, token: str) -> bool:
    """Return True only for schematic protocol cardinality, never quantitative performance.

    Human technical prose often contrasts a simple interaction shape such as
    ``1リクエスト・1レスポンス`` or ``1リクエスト・1ツール呼び出し`` with a more
    agentic flow.  The leading ``1`` is structural notation, not a measured limit.  Keep this
    exception fail-closed: require a paired interaction term in the same sentence, a clear
    structural/contrast cue, and no quota/rate/latency/cost/capacity cue.
    """
    normalized_token = unicodedata.normalize("NFKC", token or "").lower()
    if not re.search(r"\d[\d,]*(?:\.\d+)?\s*(?:リクエスト|requests?)\b", normalized_token, re.I):
        return False
    raw = text or ""
    prev_boundaries = [raw.rfind(ch, 0, start) for ch in ("。", "！", "？", "!", "?", "\n")]
    left = max(prev_boundaries) + 1
    following = [pos for ch in ("。", "！", "？", "!", "?", "\n") if (pos := raw.find(ch, end)) >= 0]
    right = min(following) if following else len(raw)
    window = raw[left:right]

    pair = re.search(
        r"\d[\d,]*(?:\.\d+)?\s*(?:リクエスト|requests?)\s*[・:/\-–—↔⇄とand ]+\s*"
        r"(?:\d[\d,]*(?:\.\d+)?\s*)?(?:レスポンス|responses?|ツール呼び出し|tool\s+calls?)(?![A-Za-z0-9_])",
        window, re.I,
    )
    if not pair:
        return False
    structural_cue = re.compile(
        r"(?:従来|単純|単なる|標準的|対話型|構成|パターン|通信|やり取り|interaction|request[- ]?response|"
        r"から.{0,80}(?:へ|に変化|に移行|を超え))",
        re.I,
    )
    if not structural_cue.search(window):
        return False
    performance_cue = re.compile(
        r"(?:毎秒|/s|per\s+second|秒間|分間|時間あたり|上限|最大|最低|平均|レート|rate|throughput|qps|rps|"
        r"料金|価格|cost|price|quota|制限|limit|同時|concurrent|latency|レイテンシ|処理回数|回まで|件まで)",
        re.I,
    )
    return not performance_cue.search(window)


def _find_unsupported_numeric_claims(draft: str, source_context: str, evidence_metadata: dict | None = None) -> list[str]:
    """記事中のセンシティブな具体値を一次情報の値+近傍条件で照合する。"""
    evidence_raw = source_context + "\n" + json.dumps(evidence_metadata or {}, ensure_ascii=False)
    evidence = _normalize_numeric_evidence_text(evidence_raw)
    failures: list[str] = []
    scrubbed = re.sub(r"Decision\s*Score[^\n]*", "", draft or "", flags=re.IGNORECASE)
    scrubbed = re.sub(r"\bScore[^\n]*", "", scrubbed, flags=re.IGNORECASE)
    scrubbed = scrubbed.replace("3〜12ヶ月", "").replace("3-12ヶ月", "")
    # 公開日などのカレンダー日付を「導入期間○日」と誤判定しない。
    scrubbed = re.sub(r"(?:20\d{2}年)?\d{1,2}月\d{1,2}日", "", scrubbed)
    # 「2026年8月」のような公開年月は導入期間ではなくカレンダー情報。
    # 月数の性能Claimと誤判定しない（年月の事実性はSource Boundary側で扱う）。
    scrubbed = re.sub(r"20\d{2}年\d{1,2}月", "", scrubbed)

    occupied_spans: list[tuple[int, int]] = []
    for pattern in _SENSITIVE_NUMERIC_PATTERNS:
        for m in re.finditer(pattern, scrubbed, re.IGNORECASE):
            # rangeを先に照合し、その内部の末尾80%等を別claimとして二重判定しない。
            if any(m.start() >= start and m.end() <= end for start, end in occupied_spans):
                continue
            occupied_spans.append((m.start(), m.end()))
            token = m.group(0).strip()
            if _is_protocol_cardinality_expression(scrubbed, m.start(), m.end(), token):
                continue
            normalized_token = _normalize_numeric_evidence_text(token)
            if normalized_token not in evidence:
                failures.append(f"unsupported numeric claim: {token}")
                continue

            # 同じ数値が別条件にだけ存在する事故を防ぐ。数値本体を手掛かりにEvidence近傍を比較。
            numbers = re.findall(r"\d+(?:\.\d+)?", token.replace(",", ""))
            claim_window = scrubbed[max(0, m.start() - 100): min(len(scrubbed), m.end() + 120)]
            evidence_windows: list[str] = []
            if numbers:
                anchor = numbers[-1]
                # 条件照合は一次本文だけを見る。metadata JSON中の数値コピーを候補にすると、
                # ハードウェア/データセット条件が消えて誤ってcompatibleになるため。
                condition_source = source_context or ""
                for em in re.finditer(re.escape(anchor), condition_source, re.I):
                    evidence_windows.append(condition_source[max(0, em.start() - 180): min(len(condition_source), em.end() + 220)])
            if evidence_windows and not any(_numeric_condition_compatible(claim_window, window) for window in evidence_windows):
                failures.append(f"numeric condition mismatch: {token}")

    def vague_supported(token: str) -> bool:
        normalized_evidence = _normalized_evidence_text(evidence_raw)
        if _normalized_evidence_text(token) in normalized_evidence:
            return True
        # 日本語の自然な期間表現と英語一次情報の表記差だけを吸収する。
        # 「半年」は six months / half a year が明示された場合のみ許可し、
        # 単なる coming months からの勝手な具体化は許可しない。
        temporal_map = {
            "半年": r"(?:half\s+(?:a\s+)?year|six\s+months|6\s+months)",
            "数日": r"(?:several|a\s+few)\s+days",
            "数週間": r"(?:several|a\s+few)\s+weeks",
            "数週": r"(?:several|a\s+few)\s+weeks",
            "数ヶ月": r"(?:coming|next|several|a\s+few)\s+months",
            "数か月": r"(?:coming|next|several|a\s+few)\s+months",
            "数月": r"(?:several|a\s+few)\s+months",
            "数年": r"(?:several|a\s+few)\s+years",
        }
        pattern = temporal_map.get(token)
        return bool(pattern and re.search(pattern, evidence_raw, re.I))

    for pattern in _VAGUE_QUANTIFIED_PATTERNS:
        for m in re.finditer(pattern, scrubbed):
            token = m.group(0)
            if not vague_supported(token):
                failures.append(f"unsupported vague quantified claim: {token}")
    return list(dict.fromkeys(failures))[:8]


def _claim_is_negated(text: str, start: int, end: int) -> bool:
    """Judge negation in the same sentence, not an arbitrary short character window.

    Japanese business prose often places the negating predicate far after an urgency/hype token
    (e.g. 「今すぐ…リアーキテクチャすることは推奨しません」). A fixed 40-char window
    creates false positives and destroys otherwise publishable articles. Sentence scope is still
    conservative: negation in another sentence cannot legalize the claim.
    """
    body = text or ""
    left_candidates = [body.rfind(mark, 0, start) for mark in ("。", "！", "？", "\n")]
    left = max(left_candidates) + 1
    rights = [pos for mark in ("。", "！", "？", "\n") if (pos := body.find(mark, end)) >= 0]
    right = min(rights) + 1 if rights else min(len(body), end + 220)
    sentence = body[left:right]
    return bool(re.search(
        r"(?:ではない|ではありません|わけではない|わけではありません|とは言えない|とは言えません|"
        r"とは限らない|とは限りません|断定できない|確認できない|保証しない|保証するものではない|"
        r"根拠(?:が|は)ない|未確認|未検証|避ける|使わない|禁止|推奨しない|推奨しません|推奨できない)",
        sentence, re.IGNORECASE
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
    # Run145: 実記事で確認したsandbox/securityの絶対保証を個別に閉じる。
    # 「影響を狭めやすい」のような限定表現は対象外。何をしても影響なし／被害を特定範囲に
    # 抑え込める、といった保証相当の断定だけをHard Fact defectとして扱う。
    run145_security_overclaims = (
        (r"(?:AI|エージェント|サンドボックス|sandbox)[^。！？\n]{0,90}(?:どんな|いかなる|何をしても)[^。！？\n]{0,90}(?:PC|ホスト|端末|本体)[^。！？\n]{0,50}(?:影響が及びません|影響は及びません|影響しません)", "unsupported absolute isolation"),
        (r"(?:被害|影響)(?:の)?範囲を[^。！？\n]{0,80}(?:だけ|のみ|内|範囲内)[^。！？\n]{0,50}(?:に)?(?:抑え込める|封じ込められる|限定できる)", "unsupported containment guarantee"),
    )
    for pattern, label in run145_security_overclaims:
        for m in re.finditer(pattern, text, re.I):
            if not _claim_is_negated(text, m.start(), m.end()):
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


def _evidence_has_substantive_coverage(key: str, source_context: str, evidence_metadata: dict | None = None) -> bool:
    """Confirm that FOUND metadata represents substantive evidence, not a keyword hit.

    Run 99 showed that the word "benchmark" alone can mark coverage=FOUND and then falsely reject a
    sentence saying benchmark data are unavailable. For hard contradiction checks we require concrete
    result/condition signals in the source itself.
    """
    text = source_context or ""
    meta_found = ((evidence_metadata or {}).get("coverage", {}) or {}).get(key) == "FOUND"
    if not meta_found or not text.strip():
        return False
    if key == "benchmark":
        for m in re.finditer(r"\b(?:benchmark|evaluation|experiment|test|results?)\b|ベンチマーク|評価|実験|結果", text, re.I):
            window = text[max(0, m.start() - 180): min(len(text), m.end() + 260)]
            if re.search(r"\d+(?:\.\d+)?\s*(?:%|ms|s\b|sec|x\b|倍|MB|GB|RPS|req|score|points?)|p\d{2}|latency|throughput|faster|slower|improv", window, re.I):
                return True
        return False
    if key == "runtime":
        return bool(re.search(r"\d+(?:\.\d+)?\s*(?:ms|s\b|sec(?:onds?)?|minutes?|hours?|分|秒|時間)", text, re.I))
    if key == "hardware":
        return bool(re.search(r"\b(?:GPU|CPU|H100|A100|RTX\s?\d+|TPU|GB\s+(?:RAM|VRAM))\b", text, re.I))
    if key == "code_availability":
        return bool(re.search(r"github\.com|source code|repository|repo\b|コード|リポジトリ", text, re.I))
    return meta_found


def _find_false_negative_evidence_claims(draft: str, evidence_metadata: dict, source_context: str = "") -> list[str]:
    """Stop a false 'unknown/not published' statement only when the source concretely proves otherwise."""
    text = draft or ""
    if not re.search(r"確認できない|記載されていない|不明|未公開|未評価|データがない", text):
        return []
    mapping = {
        "GPU|ハードウェア|環境": "hardware",
        "処理時間|runtime|速度|秒": "runtime",
        "コード|ソースコード": "code_availability",
        "評価|ベンチマーク": "benchmark",
    }
    failures = []
    for sentence in re.split(r"(?<=[。！？])", text):
        if not re.search(r"確認できない|記載されていない|不明|未公開|未評価|データがない", sentence):
            continue
        for cue, key in mapping.items():
            if re.search(cue, sentence, re.I) and _evidence_has_substantive_coverage(key, source_context, evidence_metadata):
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



def _markdown_prose_only(text: str) -> str:
    """Remove fenced/inline code from leak checks so technical constants are not mistaken for management codes."""
    prose = re.sub(r"```.*?```", " ", text or "", flags=re.S)
    prose = re.sub(r"`[^`]*`", " ", prose)
    return prose


def _decision_code_context_pattern(code: str) -> str:
    # Public-article leaks are normally parenthetical labels such as （WATCH） or decision prose such as
    # "WATCH と判断". Requiring decision context avoids false positives for unrelated technical acronyms.
    return (
        rf"(?:[（(]\s*{code}\s*[）)])|"
        rf"(?:Decision|Status)\s*[:：]\s*{code}\b|"
        rf"\b{code}\b(?=.{{0,20}}(?:と判断|という判断|スタンス|方針|採用|導入|見送|注視))"
    )


def _find_decision_code_leak(draft: str) -> list[str]:
    """Detect internal Decision codes only when they appear as public decision labels."""
    text = _markdown_prose_only(draft or "")
    leaked = []
    for code in ("NOW", "TRY", "WATCH", "WAIT", "AVOID"):
        if re.search(_decision_code_context_pattern(code), text):
            leaked.append(code)
    return ["internal decision code leaked into ARTICLE: " + ", ".join(dict.fromkeys(leaked))] if leaked else []


def _replace_public_decision_code_leaks(text: str, code_phrases: dict[str, str]) -> tuple[str, list[str]]:
    """0-API repair of management labels in prose, preserving fenced/inline code exactly."""
    changes: list[str] = []
    # Split fenced code first; odd indices are code and remain byte-for-byte untouched.
    fenced = re.split(r"(```.*?```)", text or "", flags=re.S)
    for i in range(0, len(fenced), 2):
        parts = re.split(r"(`[^`]*`)", fenced[i])
        for j in range(0, len(parts), 2):
            prose = parts[j]
            for code, phrase in code_phrases.items():
                # Parenthetical labels are redundant: remove the label only.
                updated = re.sub(rf"[（(]\s*{code}\s*[）)]", "", prose)
                # Explicit management label in prose becomes a reader-facing phrase.
                updated = re.sub(rf"(?:Decision|Status)\s*[:：]\s*{code}\b", phrase, updated)
                updated = re.sub(rf"\b{code}\b(?=.{{0,20}}(?:と判断|という判断|スタンス|方針|採用|導入|見送|注視))", phrase, updated)
                if updated != prose:
                    changes.append(f"decision_code_to_reader_phrase:{code}")
                    prose = updated
            parts[j] = prose
        fenced[i] = "".join(parts)
    return "".join(fenced), list(dict.fromkeys(changes))


def _find_management_score_leak(draft: str) -> list[str]:
    """Notion用の内部採点がnote本文へ漏れていないか検出する。"""
    text = draft or ""
    leaks = []
    if re.search(r"(?:Business Impact|Technical Impact|Market Impact|Reliability)\s*[:：]", text, re.IGNORECASE):
        leaks.append("management score breakdown leaked into ARTICLE")
    # Decision Score / 総合スコアの明示もARTICLEでは禁止。一般本文中の数値は別Gateで扱う。
    if re.search(r"(?:Decision Score|総合スコア|判定スコア|Score)\s*[:：]\s*\d+\s*(?:/\s*100)?", text, re.IGNORECASE):
        leaks.append("management decision score leaked into ARTICLE")
    if re.search(r"(?:Adoption Score|Adoption Status|Evidence Confidence|Production Readiness)\s*[:：]", text, re.IGNORECASE):
        leaks.append("decision intelligence management field leaked into ARTICLE")
    return leaks


_EVIDENCE_ALIAS_GROUPS = (
    # Canonical acronym/full-name pairs that commonly appear in primary technical sources.
    # This is deliberately small and explicit: aliases improve matching, never create evidence.
    ("MCP", "Model Context Protocol"),
    ("RAG", "Retrieval Augmented Generation", "Retrieval-Augmented Generation"),
    ("TTS", "Text to Speech", "Text-to-Speech"),
    ("ESP-IDF", "Espressif IoT Development Framework"),
    ("WIMSE", "Workload Identity in Multi-System Environments"),
)


def _expand_evidence_aliases(source_context: str) -> str:
    """Add canonical aliases only when one member is already present in the evidence.

    This prevents a primary source that says ``MCP`` from making the public expansion
    ``Model Context Protocol`` look like an unsupported named fact.  The helper does not
    infer products, actors, versions, or capabilities.
    """
    raw = source_context or ""
    normalized = _normalized_evidence_text(raw)
    additions: list[str] = []

    def alias_present(alias: str) -> bool:
        # Short all-caps aliases must be token matches.  Plain substring matching would,
        # for example, find RAG inside the ordinary word "storage" and fabricate support.
        if alias.isupper() and len(alias) <= 6:
            return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", raw, re.I))
        return _normalized_evidence_text(alias) in normalized

    for group in _EVIDENCE_ALIAS_GROUPS:
        if any(alias_present(alias) for alias in group):
            additions.extend(group)
    return raw + (("\n" + " ".join(dict.fromkeys(additions))) if additions else "")


def _find_source_boundary_violations(draft: str, source_context: str, repo_name: str = "") -> list[str]:
    """Source Context外の「固有製品/企業/モデルに関する事実補完」だけを止める補助Gate。

    一般技術用語・略語・固定見出し・Decision語は対象外。さらに、単に未知の英字語が
    出たという理由だけではFailにせず、現在仕様/導入/比較/価格/公開/サポート等を
    断定する文でのみ判定する。これにより Cursor/Copilot の無根拠補完は止めつつ、
    PoC / What / API / SaaS 等の誤検知を避ける。
    """
    alias_expanded_context = _expand_evidence_aliases(source_context)
    evidence = _normalized_evidence_text(alias_expanded_context)
    if not draft or not evidence:
        return []

    failures: list[str] = []
    sentences = re.split(r"(?<=[。！？])\s*", draft)
    factual_cue = re.compile(
        r"(?:比較|一方で|に比べ|よりも|公式|サポート|対応|提供|採用|導入|標準|管理|利用|使える|使えない|"
        r"必須|要求|実装|公開|発表|提案|開発|著者|研究者|開発元|料金|価格|シェア|市場|クラウド|オンプレ|セルフホスト|発売|リリース|"
        r"統合|搭載|廃止|終了|互換|移行|採用され|導入され|提供され|サポートされ|発表した|開発した|提案した)"
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
        "RPD","VCS","IDE","OS","Web","Bot","Bots","Agent","Agents","Auditability","Inference",
        "Schema","Format","Protocol","Specification"
    }

    def _is_name_candidate(name: str) -> bool:
        if name in ignore:
            return False
        parts = name.split()
        # `LLM API`のように一般略語だけを連結した語は固有製品名ではない。
        if parts and all(part in ignore or part.upper() in ignore for part in parts):
            return False
        # ALL-CAPS略語は原則一般技術語扱い。固有名として厳格に見るのは通常語形の製品名。
        if len(parts) == 1 and name.isupper():
            return False
        # 3文字以下の単語はノイズが多い。
        if len(name) <= 3:
            return False
        return True

    low_risk_action_cue = re.compile(
        r"(?:監査|確認|検索|スキャン|チェック|検証|比較|試す|試したい|見直|隔離|制限|拒否|"
        r"ホワイトリスト|回帰テスト|PoC|CI|私なら|推奨|すべき|必要があります|命じます)", re.I
    )

    def _looks_like_operational_artifact(name: str) -> bool:
        """LOW RISK Actionで使うローカル成果物/設定ファイル名だけを限定的に許容する。

        `Cargo.lock` のような監査手段はSource本文への逐語一致を要求しない一方、
        `Enterprise Sync` のような未確認の外部製品機能は、Action文であっても許容しない。
        """
        token = (name or "").strip()
        lowered = token.lower()
        if not token:
            return False
        if "/" in token or "\\" in token:
            return True
        if re.search(r"\.(?:lock|toml|ya?ml|json|jsonl|log|env|ini|cfg|conf|txt|csv|tsv|md|xml)$", lowered):
            return True
        return False

    for sent in sentences:
        if not factual_cue.search(sent) or inference.search(sent):
            continue
        is_low_risk_action = bool(
            low_risk_action_cue.search(sent) and classify_action_risk_tier(sent) == "LOW"
        )
        # CamelCase/TitleCase製品名候補。2語製品名も拾う。
        names = re.findall(r"(?<![A-Za-z0-9_])[A-Z][A-Za-z0-9.+_-]{2,}(?:\s+[A-Z][A-Za-z0-9.+_-]{2,})?(?![A-Za-z0-9_])", sent)
        unsupported = []
        for name in dict.fromkeys(names):
            if not _is_name_candidate(name):
                continue
            # PDF抽出で ``DiffVG`` が ``Diff VG`` / ``DiﬀVG`` になるケースを
            # 文字列一致だけで一次資料外と誤判定しない。
            compact_name = _normalized_named_fact(name)
            compact_evidence = _normalized_named_fact(alias_expanded_context)
            if _normalized_evidence_text(name) not in evidence and compact_name not in compact_evidence:
                if is_low_risk_action and _looks_like_operational_artifact(name):
                    continue
                # Run122: the current target entity plus a generic technical descriptor (SDK/API/CLI)
                # is not a newly invented third-party product name. Require both the entity identity
                # and descriptor to already exist in evidence; this cannot bootstrap an unsupported entity.
                descriptor_match = re.fullmatch(r"(.+?)\s+(SDK|API|CLI)", name, re.I)
                if descriptor_match and repo_name:
                    entity_part, descriptor = descriptor_match.group(1).strip(), descriptor_match.group(2)
                    repo_norm = _normalized_evidence_text(repo_name)
                    entity_norm = _normalized_evidence_text(entity_part)
                    if (entity_norm and (entity_norm == repo_norm or entity_norm in repo_norm or repo_norm in entity_norm)
                            and entity_norm in evidence and re.search(rf"(?<![A-Za-z0-9]){re.escape(descriptor)}(?![A-Za-z0-9])", alias_expanded_context, re.I)):
                        continue
                unsupported.append(name)
        if unsupported:
            failures.append("source-boundary unsupported named fact: " + ", ".join(unsupported[:4]))
    return list(dict.fromkeys(failures))[:6]


class _BoundaryLinkParser(HTMLParser):
    """Collect bounded first-party links for Product Review boundary reconciliation only."""
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._label: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href", "")
            self._href = urljoin(self.base_url, href) if href else ""
            self._label = []

    def handle_data(self, data):
        if self._href:
            self._label.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a" or not self._href:
            return
        href = urldefrag(self._href)[0]
        label = re.sub(r"\s+", " ", " ".join(self._label)).strip()
        if href.startswith(("http://", "https://")) and not _is_github_global_navigation_url(href):
            self.links.append((href, label))
        self._href, self._label = "", []


def _source_boundary_failure_names(failures: list[str] | tuple[str, ...] | None) -> list[str]:
    names: list[str] = []
    prefix = "source-boundary unsupported named fact:"
    for failure in failures or []:
        text = str(failure or "")
        if prefix not in text:
            continue
        tail = text.split(prefix, 1)[1]
        names.extend(x.strip() for x in tail.split(",") if x.strip())
    return list(dict.fromkeys(names))[:8]


def _same_first_party_host(candidate_host: str, seed_host: str) -> bool:
    a = (candidate_host or "").lower().split(":", 1)[0].removeprefix("www.")
    b = (seed_host or "").lower().split(":", 1)[0].removeprefix("www.")
    if not a or not b:
        return False
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def _boundary_link_matches_name(name: str, label: str, url: str) -> bool:
    full = _normalized_named_fact(name)
    hay = _normalized_named_fact((label or "") + " " + (urlparse(url or "").path or ""))
    if full and full in hay:
        return True
    tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9]{4,}", name or "")]
    # For multi-word product features, a distinctive child token such as ``tracking`` is enough
    # to select a page. The retrieved page must still contain the full named fact before support
    # is accepted, so this selection rule cannot create evidence by itself.
    if len(tokens) >= 2:
        return any(_normalized_named_fact(token) in hay for token in tokens[1:])
    return bool(tokens and _normalized_named_fact(tokens[0]) in hay)


def _product_review_boundary_seed_urls(source_info: dict) -> list[str]:
    """Return only explicit first-party candidates already discovered before Product Review."""
    urls: list[str] = []
    source = str(source_info.get("source") or "")
    primary = str(source_info.get("primary_url") or "")
    # Never reintroduce GitHub repository HTML scraping. README/REST are already represented in
    # verification_context; feature reconciliation should use explicitly linked official docs.
    if primary and not (source == "GitHub" and (urlparse(primary).netloc or "").lower() in {"github.com", "www.github.com"}):
        urls.append(primary)
    for row in source_info.get("supplement_candidates", []) or []:
        if row.get("role") != "PRIMARY_SOURCE":
            continue
        url = str(row.get("url") or "")
        if not url or _is_github_global_navigation_url(url):
            continue
        if source == "GitHub" and (urlparse(url).netloc or "").lower() in {"github.com", "www.github.com"}:
            continue
        urls.append(url)
    details = source_info.get("source_details") or {}
    for key in ("homepage", "official_url", "officialUrl", "website", "website_url", "docs_url", "documentation_url"):
        url = str(details.get(key) or "")
        if url and not _is_github_global_navigation_url(url):
            urls.append(url)
    return list(dict.fromkeys(urls))[:8]


def _fetch_boundary_html(url: str) -> tuple[str, list[tuple[str, str]], str]:
    raw, content_type, final_url = _http_get_limited(
        url, ("text/html", "application/xhtml+xml", "text/plain"), min(WEB_CONTEXT_MAX_BYTES, 1_500_000)
    )
    if not raw:
        return "", [], final_url or ""
    text = raw.decode("utf-8", errors="replace")
    links: list[tuple[str, str]] = []
    if "html" in content_type or "<html" in text[:1000].lower():
        body = _ReadableHTMLTextParser(); body.feed(text)
        parser = _BoundaryLinkParser(final_url or url); parser.feed(text)
        text = body.text(); links = list(dict.fromkeys(parser.links))
    return _truncate_verification_context(unescape(text)), links[:200], final_url or url


# Run116: Source-boundary reconciliation remains zero-Gemini and fail-closed, but may
# discover a small number of first-party docs through bounded sitemap inspection.
# These are hard safety ceilings, not tuning targets.
_PRODUCT_REVIEW_BOUNDARY_MAX_BODY_FETCHES = 6
_PRODUCT_REVIEW_BOUNDARY_MAX_DISCOVERY_FETCHES = 3
_PRODUCT_REVIEW_BOUNDARY_MAX_SITEMAP_URLS = 1200
_PRODUCT_REVIEW_BOUNDARY_MAX_RANKED_CANDIDATES = 4
_PRODUCT_REVIEW_BOUNDARY_MAX_SEED_BODY_FETCHES = 2


def _boundary_sitemap_urls_for_seed(seed: str) -> list[str]:
    """Return a tiny deterministic set of likely first-party sitemap endpoints.

    A docs URL such as ``/docs/latest/genai/tracing`` yields the most specific
    ``/docs/latest/sitemap.xml`` first, then ``/docs/sitemap.xml``, then root.
    No guessed product/feature path is constructed here.
    """
    parsed = urlparse(seed or "")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return []
    origin = f"{parsed.scheme}://{parsed.netloc}"
    parts = [p for p in (parsed.path or "").split("/") if p]
    candidates: list[str] = []
    # Most docs generators publish a sitemap at the docs version root.
    for depth in range(min(len(parts), 3), 0, -1):
        prefix = "/" + "/".join(parts[:depth])
        if parts[0].lower() in {"docs", "documentation", "guide", "guides", "manual"}:
            candidates.append(origin + prefix + "/sitemap.xml")
    candidates.append(origin + "/sitemap.xml")
    return list(dict.fromkeys(candidates))[:4]


def _boundary_text_supports_name(text: str, name: str) -> bool:
    """Require the full named-fact token sequence, not a mere compact substring.

    ``Tracking Server`` may match ``Tracking-Server`` or ``Tracking_Server`` but must not match
    ``Tracking Serverless``. Boundary reconciliation works on HTML/plain-text docs, so a strict
    token-boundary check is safer than the looser PDF/source-context normalization used elsewhere.
    """
    normalized_text = unicodedata.normalize("NFKC", text or "").lower()
    tokens = [re.escape(t.lower()) for t in re.findall(r"[A-Za-z0-9]+", unicodedata.normalize("NFKC", name or ""))]
    if not tokens:
        return False
    pattern = r"(?<![a-z0-9])" + r"[\s\-_/.:]*".join(tokens) + r"(?![a-z0-9])"
    return bool(re.search(pattern, normalized_text, re.I))


def _boundary_candidate_score(url: str, names: list[str]) -> int:
    """Rank a first-party URL by lexical evidence only; score never proves support."""
    parsed = urlparse(url or "")
    hay_raw = unescape((parsed.path or "") + "?" + (parsed.query or ""))
    hay = _normalized_named_fact(hay_raw)
    if not hay:
        return 0
    score = 0
    for name in names:
        full = _normalized_named_fact(name)
        if full and full in hay:
            score = max(score, 100)
        tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9]{3,}", name or "")]
        matched = sum(1 for token in tokens if _normalized_named_fact(token) in hay)
        if tokens:
            score = max(score, matched * 18 + (20 if matched == len(tokens) else 0))
            # Later words in a feature name (e.g. ``Server`` in ``Tracking Server``)
            # are useful for ranking but can never establish evidence by themselves.
            if len(tokens) >= 2 and _normalized_named_fact(tokens[-1]) in hay:
                score += 4
    lower_path = (parsed.path or "").lower()
    if any(seg in lower_path for seg in ("/docs/", "/documentation/", "/guide/", "/guides/", "/reference/", "/architecture/")):
        score += 6
    return score


def _parse_boundary_sitemap(raw: bytes, final_url: str, seed_host: str) -> tuple[list[str], list[str]]:
    """Parse one sitemap document into same-first-party page URLs and child sitemaps."""
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, ValueError):
        return [], []
    page_urls: list[str] = []
    child_sitemaps: list[str] = []
    root_name = root.tag.rsplit("}", 1)[-1].lower()
    for loc in root.iter():
        if loc.tag.rsplit("}", 1)[-1].lower() != "loc" or not (loc.text or "").strip():
            continue
        url = urldefrag((loc.text or "").strip())[0]
        host = (urlparse(url).netloc or "").lower()
        if not _same_first_party_host(host, seed_host):
            continue
        if root_name == "sitemapindex" or url.lower().split("?", 1)[0].endswith(("sitemap.xml", ".xml.gz")):
            child_sitemaps.append(url)
        else:
            page_urls.append(url)
        if len(page_urls) >= _PRODUCT_REVIEW_BOUNDARY_MAX_SITEMAP_URLS:
            break
    return list(dict.fromkeys(page_urls)), list(dict.fromkeys(child_sitemaps))


def _discover_boundary_candidate_urls(
    seeds: list[str], names: list[str], boundary_checked: set[str], checked: set[str]
) -> dict:
    """Discover ranked first-party page URLs with bounded, zero-Gemini sitemap reads.

    Discovery XML is never itself added to Evidence. A candidate page still has to be fetched
    under the body-fetch ceiling and contain the full normalized named fact before it can repair
    a source-boundary failure.
    """
    sitemap_queue: list[tuple[str, str]] = []
    for seed in seeds:
        seed_host = (urlparse(seed).netloc or "").lower()
        if not seed_host:
            continue
        for sm in _boundary_sitemap_urls_for_seed(seed):
            sitemap_queue.append((sm, seed_host))
    sitemap_queue = list(dict.fromkeys(sitemap_queue))

    discovery_fetches = 0
    discovered: list[str] = []
    rejected: list[dict] = []
    cursor = 0
    while cursor < len(sitemap_queue) and discovery_fetches < _PRODUCT_REVIEW_BOUNDARY_MAX_DISCOVERY_FETCHES:
        sitemap_url, seed_host = sitemap_queue[cursor]; cursor += 1
        key = _evidence_trace_url_key(sitemap_url)
        if not key or key in boundary_checked:
            continue
        boundary_checked.add(key); checked.add(key); discovery_fetches += 1
        raw, _ctype, final_url = _http_get_limited(
            sitemap_url,
            ("application/xml", "text/xml", "application/rss+xml", "text/plain", "application/octet-stream"),
            min(WEB_CONTEXT_MAX_BYTES, 1_500_000),
        )
        resolved = final_url or sitemap_url
        final_host = (urlparse(resolved).netloc or "").lower()
        if not _same_first_party_host(final_host, seed_host):
            rejected.append({
                "requested_url": sitemap_url, "final_url": resolved,
                "reason": "discovery_redirect_outside_first_party",
            })
            continue
        if not raw:
            continue
        pages, children = _parse_boundary_sitemap(raw, resolved, seed_host)
        discovered.extend(pages)
        # A sitemap index is stronger evidence than another guessed sitemap location.
        # Follow its same-first-party children next, still under the same hard discovery budget.
        child_rows = [(child, seed_host) for child in children]
        if child_rows:
            sitemap_queue[cursor:cursor] = [row for row in child_rows if row not in sitemap_queue[:cursor]]
        if len(discovered) >= _PRODUCT_REVIEW_BOUNDARY_MAX_SITEMAP_URLS:
            discovered = discovered[:_PRODUCT_REVIEW_BOUNDARY_MAX_SITEMAP_URLS]
            break

    ranked = sorted(
        ((u, _boundary_candidate_score(u, names)) for u in list(dict.fromkeys(discovered))),
        key=lambda row: (-row[1], len(urlparse(row[0]).path or ""), row[0]),
    )
    ranked = [u for u, score in ranked if score > 0][:_PRODUCT_REVIEW_BOUNDARY_MAX_RANKED_CANDIDATES]
    return {
        "urls": ranked,
        "discovery_fetches": discovery_fetches,
        "discovered_urls": len(set(discovered)),
        "rejected_urls": rejected,
    }


def reconcile_product_review_source_boundary(parsed: dict, source_info: dict, failures: list[str]) -> dict:
    """Resolve false source-boundary rejects by bounded first-party discovery with zero Gemini.

    Run116 keeps the Run115 fail-closed contract and adds only bounded recall:
    1) inspect at most two explicit official seed pages,
    2) if unresolved, inspect at most three first-party sitemap documents,
    3) rank at most four candidate pages lexically,
    4) fetch at most six HTML/text bodies total,
    5) accept support only when the *full normalized named fact* is present in a fetched page.

    Discovery XML never becomes Evidence, third-party redirects/bodies are discarded, and no
    Gemini request is made. If the exact first-party support cannot be proven, the original
    validator rejection remains unchanged.
    """
    names = _source_boundary_failure_names(failures)
    if not names:
        return {"attempted": False, "resolved": False, "names": [], "documents_added": 0}
    seeds = _product_review_boundary_seed_urls(source_info)
    if not seeds:
        return {"attempted": True, "resolved": False, "names": names, "documents_added": 0}

    checked = source_info.setdefault("checked_urls", set())
    boundary_checked: set[str] = set()
    documents = source_info.setdefault("evidence_documents", [])
    added_parts: list[str] = []
    documents_added = 0
    body_fetches = 0
    discovery_fetches = 0
    discovered_urls = 0
    ranked_candidates_considered = 0

    def add_if_supports(url: str, seed_host: str) -> tuple[bool, list[tuple[str, str]]]:
        nonlocal body_fetches, documents_added
        if body_fetches >= _PRODUCT_REVIEW_BOUNDARY_MAX_BODY_FETCHES:
            return False, []
        key = _evidence_trace_url_key(url)
        if not key or key in boundary_checked:
            return False, []
        if not _same_first_party_host(urlparse(url).netloc, seed_host):
            return False, []
        boundary_checked.add(key); checked.add(key); body_fetches += 1
        text, links, final_url = _fetch_boundary_html(url)
        resolved_url = final_url or url
        final_host = (urlparse(resolved_url).netloc or "").lower()
        if not _same_first_party_host(final_host, seed_host):
            source_info.setdefault("boundary_rejected_urls", []).append({
                "requested_url": url, "final_url": resolved_url, "reason": "redirect_outside_first_party",
            })
            logger.warning(
                "[PRODUCT REVIEW BOUNDARY REDIRECT REJECTED] seed_host=%s requested=%s final=%s",
                seed_host, url, resolved_url,
            )
            return False, []
        if not text:
            return False, links
        supported = [name for name in names if _boundary_text_supports_name(text, name)]
        if not supported:
            return False, links
        # Boundary exploration pages are not evidence merely because they are first-party.
        # Only a page that actually proves the full named fact enters the audit trail.
        documents.append({
            "url": resolved_url, "role": "PRIMARY_SOURCE", "source_type": "boundary_official_docs",
            "retrieved": True, "label": "Product Review boundary reconciliation",
            "evidence_extract": _compress_evidence(text), "document_text": text, "resolved_url": resolved_url,
        })
        piece = f"[PRIMARY_SOURCE_BOUNDARY_RECONCILIATION]\nURL: {resolved_url}\n{text}"
        added_parts.append(piece); documents_added += 1
        source_info.setdefault("deep_source_urls", []).append(resolved_url)
        return True, links

    unresolved = set(names)
    # Explicit official seeds remain the cheapest/highest-trust path, but they no longer consume
    # the entire body-fetch budget before sitemap discovery gets a chance.
    seed_fetches = 0
    all_matching_links: list[tuple[str, str]] = []
    for seed in seeds:
        if body_fetches >= _PRODUCT_REVIEW_BOUNDARY_MAX_BODY_FETCHES or not unresolved:
            break
        if seed_fetches >= _PRODUCT_REVIEW_BOUNDARY_MAX_SEED_BODY_FETCHES:
            break
        seed_host = (urlparse(seed).netloc or "").lower()
        if not seed_host:
            continue
        before_fetches = body_fetches
        supported, links = add_if_supports(seed, seed_host)
        if body_fetches > before_fetches:
            seed_fetches += 1
        if supported and added_parts:
            combined = _normalized_named_fact(added_parts[-1])
            unresolved = {n for n in unresolved if _normalized_named_fact(n) not in combined}
        if not unresolved:
            break
        for link, label in links:
            if (_same_first_party_host(urlparse(link).netloc, seed_host)
                    and any(_boundary_link_matches_name(name, label, link) for name in unresolved)):
                all_matching_links.append((link, seed_host))

    # Direct first-party links exposed by the seed are preferable to sitemap discovery.
    for link, seed_host in list(dict.fromkeys(all_matching_links))[:2]:
        if body_fetches >= _PRODUCT_REVIEW_BOUNDARY_MAX_BODY_FETCHES or not unresolved:
            break
        supported, _ = add_if_supports(link, seed_host)
        if supported and added_parts:
            combined = _normalized_named_fact(added_parts[-1])
            unresolved = {n for n in unresolved if _normalized_named_fact(n) not in combined}

    # Run116 bounded recall: discover likely docs URLs only when explicit links were insufficient.
    if unresolved and body_fetches < _PRODUCT_REVIEW_BOUNDARY_MAX_BODY_FETCHES:
        discovery = _discover_boundary_candidate_urls(seeds, sorted(unresolved), boundary_checked, checked)
        discovery_fetches = int(discovery.get("discovery_fetches") or 0)
        discovered_urls = int(discovery.get("discovered_urls") or 0)
        for rejected in discovery.get("rejected_urls") or []:
            source_info.setdefault("boundary_rejected_urls", []).append(rejected)
        ranked = discovery.get("urls") or []
        ranked_candidates_considered = len(ranked)
        # Each ranked URL is still re-checked against the host of an explicit seed.
        seed_hosts = [(urlparse(seed).netloc or "").lower() for seed in seeds]
        for candidate in ranked:
            if body_fetches >= _PRODUCT_REVIEW_BOUNDARY_MAX_BODY_FETCHES or not unresolved:
                break
            host = (urlparse(candidate).netloc or "").lower()
            seed_host = next((h for h in seed_hosts if _same_first_party_host(host, h)), "")
            if not seed_host:
                continue
            supported, _ = add_if_supports(candidate, seed_host)
            if supported and added_parts:
                combined = _normalized_named_fact(added_parts[-1])
                unresolved = {n for n in unresolved if _normalized_named_fact(n) not in combined}

    if added_parts:
        merged = source_info.get("verification_context") or source_info.get("context", "")
        for part in added_parts:
            merged = _merge_verification_context(merged, part)
        source_info["verification_context"] = _truncate_verification_context(merged)
        source_info["verification_context_length"] = len(source_info["verification_context"])
        source_info["evidence_metadata"] = _build_evidence_metadata(
            source_info["verification_context"], bool(source_info.get("deep_source_scanned"))
        )
    return {
        "attempted": True, "resolved": not unresolved, "names": names,
        "unresolved_names": sorted(unresolved), "documents_added": documents_added,
        # ``fetches`` is kept for artifact/backward compatibility and means body fetches.
        "fetches": body_fetches, "body_fetches": body_fetches,
        "discovery_fetches": discovery_fetches, "discovered_urls": discovered_urls,
        "ranked_candidates_considered": ranked_candidates_considered,
    }


_RELATION_FAMILIES = {
    # Bare Japanese nouns such as 「開発体制」「提案内容」must never trigger a relation claim.
    # Only explicit predicates are accepted here.
    "provide": (
        r"提供(?:する|した|しました|している|される|された|されています|しています|しており|していること)",
        r"\b(?:provide|provides|provided|offer|offers|offered|ship|ships|shipped|maintain|maintains|maintained)\b",
    ),
    "propose": (
        r"提唱(?:する|した|しました|している|されています|しています|しており)|提案(?:する|した|しました|している|されています|しています|しており)",
        r"\b(?:propose|proposes|proposed|introduce|introduces|introduced)\b",
    ),
    "adopt": (
        r"採用(?:する|した|しました|している|される|された|されています|しています|しており)",
        r"\b(?:adopt|adopts|adopted|use|uses|used)\b|\bbuilt\s+on\b",
    ),
    "develop": (
        r"開発(?:する|した|しました|している|される|された|されています|しています|しており)",
        r"\b(?:develop|develops|developed|create|creates|created|build|builds|built)\b",
    ),
}


def _relation_family_for_predicate(predicate: str) -> tuple[str | None, tuple[str, ...] | None]:
    for family, patterns in _RELATION_FAMILIES.items():
        if any(re.search(pattern, predicate or "", re.I) for pattern in patterns):
            return family, patterns
    return None, None


def _clean_relation_entity(value: str) -> str:
    text = re.sub(r"^[\s'\"「『（(]+|[\s'\"」』）),，、]+$", "", value or "").strip()
    text = re.sub(r"(?:社|氏|チーム|財団|プロジェクト)$", "", text).strip()
    # Keep the claim conservative. A full clause/list is not an entity.
    if len(text) > 64 or re.search(r"[,，、;；]|(?:および|ならびに|または)", text):
        return ""
    return text


def _looks_like_relation_entity(value: str) -> bool:
    text = _clean_relation_entity(value)
    if len(text) < 2:
        return False
    # At least one proper-name signal: Latin token/camel case, quoted Japanese name, or honorific/company marker
    # in the original expression. Generic concepts such as 「開発体制」 are intentionally excluded.
    return bool(
        re.search(r"[A-Za-z][A-Za-z0-9.+_-]+", text)
        or re.search(r"[「『][^」』]{2,}[」』]", value or "")
        or re.search(r"(?:社|氏|チーム|財団|プロジェクト)", value or "")
    )


def _extract_explicit_relation_claim(sentence: str) -> tuple[str, str, str, tuple[str, ...]] | None:
    """Extract only grammatically explicit actor→relation→object claims.

    This deliberately prefers precision over recall. Relation Gate is a hard-fail gate, so a bare noun
    such as 「開発」「提案」「採用」 or a list of product names must not be interpreted as a factual
    actor relationship. Unsupported claims that are not explicit relations remain covered by the other
    Fact/Source-Boundary gates.
    """
    sent = (sentence or "").strip()
    if not sent:
        return None

    # Japanese active voice: Timescale社がpgvectorを提供しています。
    # Keep actor/object windows small so headings and enumerations do not become pseudo-relations.
    jp_patterns = [
        re.compile(
            r"(?P<actor>[A-Za-z0-9_.+\-/一-龥ぁ-んァ-ヶ々ー・「『』」 ]{2,48}?(?:社|氏|チーム|財団|プロジェクト)?)"
            r"(?:が|は)\s*(?P<object>[A-Za-z0-9_.+\-/一-龥ぁ-んァ-ヶ々ー・「『』」 ]{2,64}?)を\s*"
            r"(?P<predicate>提供(?:する|した|している|される|された|しています|しており)|"
            r"提唱(?:する|した|しました|している|されています|しています|しており)|提案(?:する|した|しました|している|されています|しています|しており)|"
            r"採用(?:する|した|しました|している|される|された|されています|しています|しており)|"
            r"開発(?:する|した|しました|している|される|された|されています|しています|しており))"
        ),
        # Japanese passive voice: WidgetXはAcmeによって開発された。
        re.compile(
            r"(?P<object>[A-Za-z0-9_.+\-/一-龥ぁ-んァ-ヶ々ー・「『』」 ]{2,64}?)は\s*"
            r"(?P<actor>[A-Za-z0-9_.+\-/一-龥ぁ-んァ-ヶ々ー・「『』」 ]{2,48}?(?:社|氏|チーム|財団|プロジェクト)?)"
            r"によって\s*(?P<predicate>提供された|提唱された|提案された|採用された|開発された)"
        ),
    ]
    for pattern in jp_patterns:
        m = pattern.search(sent)
        if not m:
            continue
        actor_raw, object_raw, predicate = m.group("actor"), m.group("object"), m.group("predicate")
        actor, obj = _clean_relation_entity(actor_raw), _clean_relation_entity(object_raw)
        family, family_patterns = _relation_family_for_predicate(predicate)
        if family and family_patterns and _looks_like_relation_entity(actor_raw) and _looks_like_relation_entity(object_raw):
            return family, actor, obj, family_patterns

    # English active voice. Require proper-name-looking actor AND object; generic prose is ignored.
    english_relation = r"provides?|provided|offers?|offered|ships?|shipped|maintains?|maintained|proposes?|proposed|introduced?|adopts?|adopted|uses?|used|develops?|developed|creates?|created|builds?|built"
    m = re.search(
        rf"(?P<actor>[A-Z][A-Za-z0-9_.+/-]*(?:\s+[A-Z][A-Za-z0-9_.+/-]*){{0,2}})\s+"
        rf"(?P<predicate>{english_relation})\s+"
        rf"(?P<object>[A-Z][A-Za-z0-9_.+/-]*(?:\s+[A-Z][A-Za-z0-9_.+/-]*){{0,2}})",
        sent,
    )
    if m:
        actor, obj, predicate = m.group("actor"), m.group("object"), m.group("predicate")
        family, family_patterns = _relation_family_for_predicate(predicate)
        if family and family_patterns:
            return family, actor, obj, family_patterns

    # English passive voice: WidgetX was developed by Acme.
    m = re.search(
        rf"(?P<object>[A-Z][A-Za-z0-9_.+/-]*(?:\s+[A-Z][A-Za-z0-9_.+/-]*){{0,2}})\s+"
        rf"(?:is|was|are|were|has been|have been)\s+(?P<predicate>provided|offered|maintained|proposed|introduced|adopted|used|developed|created|built)\s+by\s+"
        rf"(?P<actor>[A-Z][A-Za-z0-9_.+/-]*(?:\s+[A-Z][A-Za-z0-9_.+/-]*){{0,2}})",
        sent,
        re.I,
    )
    if m:
        actor, obj, predicate = m.group("actor"), m.group("object"), m.group("predicate")
        family, family_patterns = _relation_family_for_predicate(predicate)
        if family and family_patterns:
            return family, actor, obj, family_patterns
    return None


def _evidence_supports_relation(actor: str, obj: str, family_patterns: tuple[str, ...], source_context: str) -> bool:
    actor_norm = _normalized_named_fact(actor)
    object_norm = _normalized_named_fact(obj)
    for ev in re.split(r"(?<=[。！？.!?])\s+|\n+", source_context or ""):
        if not ev.strip() or not any(re.search(pattern, ev, re.I) for pattern in family_patterns):
            continue
        normalized_ev = _normalized_named_fact(ev)
        if actor_norm and object_norm and actor_norm in normalized_ev and object_norm in normalized_ev:
            return True
    return False


def _find_entity_relation_violations(draft: str, source_context: str) -> list[str]:
    """High-precision hard gate for unsupported actor→object factual relationships.

    Only explicit grammatical claims are eligible for hard failure. Lists, co-occurring product names,
    headings, and nouns such as 「開発体制」 are ignored. This prevents Run-99-style false positives
    while still rejecting high-confidence attribution errors such as "Timescale provides pgvector".
    """
    if not draft or not source_context:
        return []
    failures: list[str] = []
    for sent in re.split(r"(?<=[。！？.!?])\s+|\n+", draft):
        if not sent or re.search(r"一次情報(?:では|からは)確認できない|未確認|推測|可能性|仮に|たとえば|例えば", sent):
            continue
        claim = _extract_explicit_relation_claim(sent)
        if not claim:
            continue
        family, actor, obj, family_patterns = claim
        if not _evidence_supports_relation(actor, obj, family_patterns, source_context):
            failures.append(f"unsupported entity relation ({family}): {actor} -> {obj}")
    return list(dict.fromkeys(failures))[:6]


def _classify_source_info_evidence(source_info: dict | None) -> list[dict]:
    """Return deterministic authority classifications for retrieved evidence documents."""
    if not source_info:
        return []
    rows=[]
    for doc in source_info.get("evidence_documents", []) or []:
        if not doc.get("retrieved"):
            continue
        authority=classify_evidence(
            url=str(doc.get("url") or ""), role=str(doc.get("role") or ""),
            raw_source_type=str(doc.get("source_type") or ""), label=str(doc.get("label") or ""),
            origin=str(doc.get("origin") or ""), pipeline_source=str(source_info.get("source") or ""),
            primary_url=str(source_info.get("primary_url") or ""),
            entity_id=str(source_info.get("canonical_entity_id") or ""),
            source_details=source_info.get("source_details") or {}, evidence_extract=str(doc.get("evidence_extract") or ""),
        )
        row=dict(doc); row.update(authority); rows.append(row)
    return rows


def _evidence_authority_summary(source_info: dict | None) -> dict:
    rows=_classify_source_info_evidence(source_info)
    eligible=[r for r in rows if r.get("decision_eligible")]
    best=max((authority_rank(r.get("authority_class")) for r in eligible), default=0)
    return {
        "retrieved_documents":len(rows), "decision_eligible_documents":len(eligible),
        "best_authority_rank":best,
        "source_types":list(dict.fromkeys(str(r.get("source_type") or "UNKNOWN") for r in rows)),
        "authority_classes":list(dict.fromkeys(str(r.get("authority_class") or "UNKNOWN") for r in rows)),
    }


_SECONDARY_NEWS_HOST_SUFFIXES = (
    "reuters.com", "apnews.com", "bloomberg.com", "techcrunch.com", "theverge.com",
    "wired.com", "arstechnica.com", "zdnet.com", "venturebeat.com", "cnbc.com",
)


def _primary_source_authority_failures(source_info: dict | None) -> list[str]:
    """Require decision-eligible authority behind HN/PH discovery.

    Run118 evaluates the retrieved evidence set rather than trusting a URL simply because it
    resolved. Discovery and secondary-news documents may remain in the audit ledger, but they
    never satisfy paid Decision Intelligence primary-authority requirements.
    """
    if not source_info:
        return []
    source=str(source_info.get("source") or "")
    if source not in {"HackerNews","ProductHunt"}:
        return []
    rows=_classify_source_info_evidence(source_info)
    if not rows and source_info.get("primary_url"):
        fallback=classify_evidence(
            url=str(source_info.get("primary_url") or ""), role="PRIMARY_SOURCE",
            raw_source_type=str(source_info.get("source") or ""), label="primary URL", origin="primary_url",
            pipeline_source=source, primary_url=str(source_info.get("primary_url") or ""),
            entity_id=str(source_info.get("canonical_entity_id") or ""), source_details=source_info.get("source_details") or {},
        )
        rows=[{"url":source_info.get("primary_url"), **fallback}]
    eligible=[r for r in rows if r.get("decision_eligible") and authority_rank(r.get("authority_class")) >= 2]
    if eligible and source_info.get("primary_source_resolved"):
        return []
    source_info["evidence_authority_summary"]=_evidence_authority_summary(source_info)
    if any(r.get("source_type")=="SECONDARY_NEWS" for r in rows):
        kind="secondary news report"
    elif any(r.get("source_type")=="DISCOVERY" for r in rows) or not rows:
        kind="discovery source"
    else:
        kind="non-authoritative evidence"
    return [f"PRIMARY_SOURCE_AUTHORITY_INSUFFICIENT: {kind} cannot establish decision authority"]


_JAPANESE_SAFE_FIXES = (
    (re.compile(r"をな(?=[一-龥ぁ-んァ-ヶA-Za-z])"), "を"),
    (re.compile(r"がを(?=[一-龥ぁ-んァ-ヶA-Za-z])"), "を"),
    (re.compile(r"にを(?=[一-龥ぁ-んァ-ヶA-Za-z])"), "を"),
    (re.compile(r"というという"), "という"),
)


def _apply_final_japanese_polish(parsed: dict) -> tuple[dict, list[str]]:
    """0-API deterministic cleanup for unmistakable Japanese mechanical glitches."""
    out = dict(parsed or {})
    changes: list[str] = []
    # Quality retries can accidentally copy uppercase MANAGEMENT decision codes back into ARTICLE.
    # Translate only exact uppercase standalone codes; normal English words such as "Watch" are untouched.
    decision_code_phrases = {
        "NOW": "今すぐ着手する", "TRY": "限定的に試す", "WATCH": "今後の動きを注視する",
        "WAIT": "条件が整うまで待つ", "AVOID": "現時点では採用を見送る",
    }
    if out.get("note_draft"):
        article, code_changes = _replace_public_decision_code_leaks(str(out.get("note_draft") or ""), decision_code_phrases)
        changes.extend(code_changes)
        out["note_draft"] = article
    for key in ("note_draft", "title_text", "action_text", "decision_reason_text"):
        text = str(out.get(key) or "")
        for pattern, replacement in _JAPANESE_SAFE_FIXES:
            new_text, count = pattern.subn(replacement, text)
            if count:
                changes.append(f"{key}:{pattern.pattern}:{count}")
                text = new_text
        out[key] = text
    return out, changes


def _find_final_japanese_polish_issues(text: str) -> list[str]:
    issues = []
    body = text or ""
    suspicious = (
        (r"[をがにでへ]な(?:を|が|に|で|へ)", "suspicious particle sequence"),
        (r"(?:です|ます){2,}", "duplicated polite ending"),
        (r"というという", "duplicated phrase"),
    )
    for pattern, label in suspicious:
        if re.search(pattern, body):
            issues.append("japanese_polish: " + label)
    return issues


_ADOPTION_SCORE_COMPONENTS = (
    ("Evidence Quality", 25),
    ("Production Maturity", 25),
    ("Use-case Utility / Fit", 20),
    ("Reliability / Security Risk", 15),
    ("Integration / Migration Feasibility", 10),
    ("Ecosystem / Support Durability", 5),
)


def _parse_adoption_score_components(breakdown_text: str) -> tuple[dict[str, int], list[str]]:
    values: dict[str, int] = {}
    failures: list[str] = []
    text = breakdown_text or ""
    for label, maximum in _ADOPTION_SCORE_COMPONENTS:
        m = re.search(rf"{re.escape(label)}\s*(\d+)\s*/\s*{maximum}", text, re.IGNORECASE)
        if not m:
            failures.append(f"Adoption component missing: {label}")
            continue
        value = int(m.group(1))
        if not 0 <= value <= maximum:
            failures.append(f"Adoption component out of range: {label}={value}/{maximum}")
        values[label] = value
    return values, failures


def validate_decision_intelligence_assessment(parsed: dict, evidence_result: dict,
                                               verification_context: str,
                                               evidence_metadata: dict | None = None) -> tuple[bool, list[str]]:
    """Validate product-only Adoption assessment independently from article Quality Gates.

    The validator is deliberately strict on evidence and structure, but it does not use
    article Human Appeal / Publication Readiness as a prerequisite.  This allows a valid
    technology assessment to be stored even when the free-note manuscript still needs editing.
    """
    if not decision_intelligence.ENABLE_DECISION_INTELLIGENCE_DB:
        return False, ["Decision Intelligence DB disabled"]

    failures: list[str] = []
    score = int(parsed.get("adoption_score") or 0)
    status = str(parsed.get("adoption_status") or "").upper()
    confidence = str(parsed.get("evidence_confidence") or "").upper()
    readiness = str(parsed.get("production_readiness") or "").upper()
    main_risk = str(parsed.get("main_risk_text") or "").strip()
    best_for = str(parsed.get("best_for_text") or "").strip()
    avoid_for = str(parsed.get("avoid_for_text") or "").strip()
    rationale = str(parsed.get("short_rationale_text") or "").strip()

    if not 1 <= score <= 100:
        failures.append("Adoption Score missing/invalid")
    components, component_failures = _parse_adoption_score_components(
        str(parsed.get("adoption_score_breakdown_text") or "")
    )
    failures.extend(component_failures)
    if len(components) == len(_ADOPTION_SCORE_COMPONENTS):
        component_total = sum(components.values())
        if component_total != score:
            failures.append(f"Adoption Score total mismatch: components={component_total} total={score}")

    if status not in decision_intelligence.ADOPTION_STATUSES:
        failures.append("Adoption Status missing/invalid")
    if confidence not in decision_intelligence.CONFIDENCE_LEVELS:
        failures.append("Evidence Confidence missing/invalid")
    if readiness not in decision_intelligence.READINESS_LEVELS:
        failures.append("Production Readiness missing/invalid")
    for label, value in (
        ("Main Risk", main_risk), ("Best For", best_for),
        ("Avoid For", avoid_for), ("Short Rationale", rationale),
    ):
        if not _is_meaningful_field(value):
            failures.append(f"{label} missing")

    # Adoption assessment may not outrun the verified evidence scope.
    if evidence_result.get("state") == EVIDENCE_INSUFFICIENT or not evidence_result.get("decision_scope_safe", False):
        failures.append("Adoption assessment evidence scope unsafe")
    if confidence == "HIGH" and evidence_result.get("state") != EVIDENCE_SUFFICIENT:
        failures.append("Evidence Confidence HIGH requires SUFFICIENT evidence")
    if status == "ADOPT" and (confidence != "HIGH" or readiness != "HIGH"):
        failures.append("ADOPT requires Evidence Confidence HIGH and Production Readiness HIGH")
    if status == "AVOID" and not main_risk:
        failures.append("AVOID requires Main Risk")

    # Check only the subscriber-facing assessment prose; never copy the article Decision Score
    # or article narrative into Adoption Score semantics.
    assessment_text = "\n".join([main_risk, best_for, avoid_for, rationale])
    failures.extend(_find_unsupported_numeric_claims(
        assessment_text, verification_context, evidence_metadata or {}
    ))
    failures.extend(_find_source_boundary_violations(assessment_text, verification_context))
    failures.extend(_find_hype_claims(assessment_text, verification_context, evidence_metadata or {}))
    return not failures, list(dict.fromkeys(failures))[:16]


def _select_decision_intelligence_assessment_for_persistence(
        final_parsed: dict, current_evidence_result: dict, source_info: dict,
        retained_parsed: dict | None = None, retained_evidence_result: dict | None = None
) -> tuple[dict, dict, str]:
    """Choose the newest valid Adoption assessment without coupling it to article rewrites.

    Quality Retry is allowed to rewrite the free-note manuscript.  If that rewrite drops or
    corrupts otherwise-valid Decision Intelligence fields, preserve the most recent assessment
    that independently passed the strict DI validator.  No additional Gemini request is made.
    The retained snapshot is revalidated against the same verified source context before use.
    """
    if not decision_intelligence.ENABLE_DECISION_INTELLIGENCE_DB:
        return final_parsed, current_evidence_result, "disabled"

    verification_context = source_info.get("verification_context") or source_info.get("context", "")
    metadata = source_info.get("evidence_metadata", {})
    current_ok, _ = validate_decision_intelligence_assessment(
        final_parsed, current_evidence_result, verification_context, metadata
    )
    if current_ok:
        return final_parsed, current_evidence_result, "current"

    if retained_parsed is not None:
        retained_evidence = retained_evidence_result or current_evidence_result
        retained_ok, _ = validate_decision_intelligence_assessment(
            retained_parsed, retained_evidence, verification_context, metadata
        )
        if retained_ok:
            return retained_parsed, retained_evidence, "retained"

    return final_parsed, current_evidence_result, "invalid"


def _resolve_evidence_source_version(repo: dict, source_info: dict) -> tuple[str, str]:
    """Resolve one immutable primary-source version with zero Gemini, only at persistence time."""
    source = _effective_evidence_source(repo)
    primary = source_info.get("primary_url") or repo.get("url") or ""
    if source == "GitHub":
        repo_name = _github_repo_name_from_url(primary) or str(repo.get("nameWithOwner") or "")
        default_branch = (source_info.get("source_details") or {}).get("default_branch") or "HEAD"
        if repo_name and GH_PAT:
            try:
                r = requests.get(
                    f"https://api.github.com/repos/{repo_name}/commits/{default_branch}",
                    headers={"Authorization": f"Bearer {GH_PAT}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
                    timeout=12,
                )
                if r.status_code == 200:
                    sha = str((r.json() or {}).get("sha") or "")
                    if re.fullmatch(r"[0-9a-fA-F]{40}", sha):
                        return sha, f"https://github.com/{repo_name}/tree/{sha}"
            except Exception as exc:
                logger.warning("[EVIDENCE VERSION] GitHub commit resolve failed %s: %s", repo_name, exc)
    if source == "ArXiv":
        details = source_info.get("source_details") or {}
        version = details.get("arxiv_version") or ""
        versioned = details.get("arxiv_versioned_url") or ""
        if version:
            return version, versioned or primary
    return "", ""


def persist_decision_intelligence_assessment(repo: dict, parsed: dict, source_info: dict,
                                             evidence_result: dict, reviewed_at: str,
                                             screening_score: int | None = None,
                                             screening_reason: str = "",
                                             attribution_context: dict | None = None,
                                             pipeline_status: str = STATUS_DEEP_DIVE,
                                             content_status: str = CONTENT_STATUS_DEEP_DIVE,
                                             article_status: str = ARTICLE_STATUS_NOT_PLANNED) -> dict:
    """Best-effort product DB side-path. Never changes article persistence outcome."""
    if not decision_intelligence.ENABLE_DECISION_INTELLIGENCE_DB:
        return {"enabled": False, "saved": False, "reason": "disabled"}

    verification_context = source_info.get("verification_context") or source_info.get("context", "")
    assessment_ok, failures = validate_decision_intelligence_assessment(
        parsed, evidence_result, verification_context, source_info.get("evidence_metadata", {})
    )
    if not assessment_ok:
        logger.warning(
            "[DECISION INTELLIGENCE SKIP] %s: assessment invalid: %s",
            repo.get("nameWithOwner"), " / ".join(failures)[:1500],
        )
        return {"enabled": True, "saved": False, "reason": "assessment_invalid", "failures": failures}

    resolution = decision_intelligence.resolve_canonical_entity_id(repo, source_info)
    if resolution.status == "AMBIGUOUS":
        logger.warning(
            "[DECISION INTELLIGENCE AMBIGUOUS] %s -> %s (%s)",
            repo.get("nameWithOwner"), resolution.entity_id, resolution.reason,
        )
        return {"enabled": True, "saved": False, "reason": "entity_ambiguous", "entity_id": resolution.entity_id}

    evidence_urls = _collect_final_evidence_urls(source_info, None)
    candidate = attribution_context or {}
    assessment = {
        "technology_name": _notion_display_name(repo) or "Technology",
        "primary_url": resolution.primary_url or source_info.get("primary_url") or repo.get("url"),
        "sources": [repo.get("source", "GitHub")],
        "category": candidate.get("portfolio_topic") or "OTHER",
        "adoption_score": int(parsed.get("adoption_score") or 0),
        "adoption_status": str(parsed.get("adoption_status") or "").upper(),
        "evidence_confidence": str(parsed.get("evidence_confidence") or "").upper(),
        "production_readiness": str(parsed.get("production_readiness") or "").upper(),
        "main_risk": parsed.get("main_risk_text", ""),
        "best_for": parsed.get("best_for_text", ""),
        "avoid_for": parsed.get("avoid_for_text", ""),
        "short_rationale": parsed.get("short_rationale_text", ""),
        "japanese_display_label": parsed.get("japanese_display_label", ""),
        "reviewed_at": reviewed_at,
        "evidence_urls": evidence_urls,
        "source_summary": parsed.get("source_summary_text", ""),
        "published_at": repo.get("publishedAt"),
        "screening_score": screening_score,
        "screening_reason": screening_reason,
        "pipeline_status": pipeline_status,
        "content_status": content_status,
        "article_status": article_status,
        "tracking_status": "ACTIVE",
        "tracking_eligibility": True,
        "tracking_reason": "Deep Dive / Decision Assessment completed",
        "assessment_state": "ASSESSED",
        "next_review": (datetime.now(timezone.utc) + timedelta(days=TRACKING_REVIEW_DAYS)).isoformat(),
    }
    try:
        result = decision_intelligence.upsert_technology_intelligence(assessment, resolution)
        if result.get("saved") and evidence_ledger.ENABLE_EVIDENCE_LEDGER:
            try:
                source_version, immutable_url = _resolve_evidence_source_version(repo, source_info)
                snapshots = evidence_ledger.build_snapshots(
                    resolution.entity_id, result.get("page_id") or "", source_info, reviewed_at,
                    source_version=source_version, immutable_url=immutable_url,
                )
                ledger_result = evidence_ledger.persist_snapshots(snapshots, decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY)
                result["evidence_ledger"] = ledger_result
                logger.info("[EVIDENCE LEDGER] %s -> %s", repo.get("nameWithOwner"), ledger_result)
                if evidence_ledger.EVIDENCE_LEDGER_REQUIRED and not snapshots:
                    raise RuntimeError("Evidence Ledger required but no evidence snapshot was produced")
            except Exception as ledger_exc:
                result["evidence_ledger_error"] = str(ledger_exc)
                logger.error("[EVIDENCE LEDGER FAILED] %s: %s", repo.get("nameWithOwner"), ledger_exc)
                if evidence_ledger.EVIDENCE_LEDGER_REQUIRED:
                    result["saved"] = False
                    result["reason"] = "evidence_ledger_failed"
                    return result
        if result.get("saved"):
            logger.info(
                "[DECISION INTELLIGENCE SAVED] %s -> entity=%s created=%s changed=%s history=%s",
                repo.get("nameWithOwner"), result.get("entity_id"), result.get("created"),
                result.get("changed"), bool(result.get("history_id")),
            )
        return result
    except Exception as exc:
        # Product persistence is deliberately isolated from the free-note article state machine.
        logger.error("[DECISION INTELLIGENCE PERSISTENCE FAILED] %s: %s", repo.get("nameWithOwner"), exc)
        return {"enabled": True, "saved": False, "reason": "persistence_failed", "error": str(exc)}


def validate_fact_gate(parsed: dict, repo_name: str, source_context: str = "", source: str = "",
                       evidence_metadata: dict | None = None, source_info: dict | None = None,
                       freshness: dict | None = None, output_truncated: bool = False) -> tuple[bool, list[str]]:
    """公開可否を決めるFact Gate。事実・構造上の致命傷だけをFailにする。"""
    failures: list[str] = []
    draft = parsed.get("note_draft", "")
    marker = PAID_AREA_PATTERN.search(draft)

    # Hard Fact Gateは「公開安全性」に必要な管理項目だけを見る。
    # 競合比較・移行コスト・Future Scenario等はEvidenceが弱い案件ほど埋める行為自体が
    # Hallucinationを誘発するため、Product/DB completenessを記事公開条件にしない。
    required_fields = {
        "Decision Reason": "decision_reason_text",
        "Action": "action_text",
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
    # Run122: visible heading labels are editorial presentation, not factual safety.
    # Run108 intentionally removed fixed heading names. Missing/unstyled section headings are handled
    # by Publication Readiness as a repairable REVIEW/HARD publication defect, never as a Fact claim.
    if output_truncated:
        failures.append("OUTPUT_TRUNCATED")
    if source_info and source_info.get("deep_source_required") and not source_info.get("deep_source_scanned") and not source_info.get("decision_scope_safe"):
        failures.append("SOURCE_DEPTH_INSUFFICIENT")

    failures.extend(_find_unsupported_numeric_claims(draft, source_context, evidence_metadata))
    failures.extend(_find_hype_claims(draft, source_context, evidence_metadata))
    failures.extend(_find_false_negative_evidence_claims(draft, evidence_metadata or {}, source_context))
    failures.extend(_find_final_wording_violations(draft, evidence_metadata or {}, freshness))
    failures.extend(_find_unsupported_competitor_claims(parsed, source_context))
    failures.extend(_find_management_score_leak(draft))
    failures.extend(_find_decision_code_leak(draft))
    failures.extend(_find_source_boundary_violations(draft, source_context, repo_name))
    failures.extend(_find_entity_relation_violations(draft, source_context))
    failures.extend(_primary_source_authority_failures(source_info))

    # 深い一次資料に明示された限界を記事から丸ごと落とすことを禁止する。
    limitation_present = re.search(r"limitation|limitations|issue|challenge|artifact|occlusion|noisy background|rough sketch|制約|限界|課題", source_context or "", re.I)
    limitation_retained = re.search(r"制約|限界|課題|注意|未検証|アーティファクト|オクルージョン|ノイズ|粗いスケッチ|promising|可能性", draft, re.I)
    if limitation_present and not limitation_retained:
        failures.append("LIMITATION_DROPPED")

    conflict = _explicit_decision_conflict(parsed)
    if conflict:
        failures.append(conflict)
    return (not failures, list(dict.fromkeys(failures)))


EDITORIAL_SOFT_WARNINGS = {
    # Run 102: 文章美観・型・軽微な日本語Polishは観測するが公開停止しない。
    "mechanical ordinal structure",
    "repetitive AI-like sentence endings",
    "repetitive fixed introduction",
    "missing observation or reservation",
    "mechanical three-reasons phrasing",
    "too many reader questions",
    "monotonous sentence endings",
}


def _editorial_warning_is_soft(warning: str) -> bool:
    text = warning or ""
    return (text in EDITORIAL_SOFT_WARNINGS
            or text.startswith("too many article headings:")
            or text.startswith("japanese_polish:"))


def _blocking_editorial_warnings(warnings: list[str]) -> list[str]:
    # list-heavy / fabricated experience / 未知の将来ruleはReview/Hard候補として残す。
    return [warning for warning in (warnings or []) if not _editorial_warning_is_soft(warning)]


def validate_editorial_gate(parsed: dict, repo_name: str) -> tuple[bool, list[str]]:
    """Editorial Gate: diagnose prose quality; only material defects block publication.

    Soft style signals remain observable in Article Audit but do not turn a factually sound,
    readable technical article into Quality Failed by themselves.
    """
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
    warnings.extend(_find_final_japanese_polish_issues(draft))
    warnings = list(dict.fromkeys(warnings))
    return (not _blocking_editorial_warnings(warnings), warnings)


def _promote_plaintext_section_titles(article: str) -> tuple[str, list[str]]:
    """Promote unmistakable plain-text section labels to Markdown headings without an LLM.

    Some strong long-form generations write content-specific section labels as standalone lines
    but omit the ``###`` marker. This repair is deliberately conservative: long-form only, after
    the Reader-First metadata block, blank-line isolated, short Japanese label, substantial prose
    immediately after it, and at least two independent candidates. A single ambiguous line is
    never promoted.
    """
    body = article or ""
    if len(re.sub(r"\s+", "", body)) < 1200:
        return body, []
    lines = body.splitlines()
    metadata_end = -1
    for i, line in enumerate(lines):
        if re.match(r"^#{2,4}\s+元情報\s*$", line.strip()):
            metadata_end = i
            break
    if metadata_end < 0:
        return body, []

    candidates: list[int] = []
    for i in range(metadata_end + 1, len(lines) - 2):
        raw = lines[i]
        label = raw.strip()
        if not label or raw != label:
            continue
        if i == 0 or lines[i - 1].strip() or lines[i + 1].strip():
            continue
        if re.match(r"^(?:#{1,6}\s|[-*+]\s|\d+[.)、]\s*|>|```|---+$)", label):
            continue
        visible = re.sub(r"\s+", "", label)
        if not (8 <= len(visible) <= 56):
            continue
        if re.search(r"[。！？!?；;：:]$", label) or re.search(r"https?://|`|\[[^]]+\]\(", label):
            continue
        if len(re.findall(r"[ぁ-んァ-ヶ一-龯々]", label)) < 4:
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            continue
        block: list[str] = []
        while j < len(lines) and lines[j].strip():
            if re.match(r"^(?:#{1,6}\s|```|---+$)", lines[j].strip()):
                break
            block.append(lines[j].strip())
            j += 1
        if len(re.sub(r"\s+", "", "".join(block))) < 80:
            continue
        candidates.append(i)

    if len(candidates) < 2:
        return body, []
    if any(b - a < 3 for a, b in zip(candidates, candidates[1:])):
        return body, []
    changed: list[str] = []
    for i in candidates:
        label = lines[i].strip()
        lines[i] = f"### {label}"
        changed.append(label)
    return "\n".join(lines), changed


def _repair_malformed_reader_numbering(article: str) -> tuple[str, list[str]]:
    """Repair only unmistakable line-leading ordinal collisions without changing facts.

    Real regression produced e.g. ``2.2026年〜``.  This is typography, not content, so repair it
    locally with zero Gemini calls.  Mid-sentence decimals/versions are intentionally untouched.
    """
    body = article or ""
    repaired, count = re.subn(r"(?m)^(\s*\d{1,2})\.(?=20\d{2}年)", r"\1. ", body)
    return repaired, ([f"repair_malformed_ordinal_year:{count}"] if count else [])


def _apply_deterministic_structure_polish(parsed: dict) -> tuple[dict, list[str]]:
    polished = dict(parsed or {})
    article, headings = _promote_plaintext_section_titles(str(polished.get("note_draft") or ""))
    article, numbering_changes = _repair_malformed_reader_numbering(article)
    if headings or numbering_changes:
        polished["note_draft"] = article
    return polished, [f"promote_plaintext_heading:{h}" for h in headings] + numbering_changes


def validate_publication_readiness_gate(parsed: dict, source_context: str = "", source_info: dict | None = None) -> tuple[str, list[str]]:
    """Publication Readiness Gate: 公開完成度を横断確認し、根拠・判断の弱さはREVIEWへ分離する。"""
    article = parsed.get("note_draft", "")
    title = parsed.get("title_text", "")
    action = parsed.get("action_text", "") + "\n" + _extract_any_markdown_section(article, _display_heading_aliases("decision"))
    score = int(parsed.get("score") or 0)
    context = source_context or ""
    issues: list[str] = []
    # Run122: require readable sectioning for long-form note prose, but do not require legacy labels.
    # This is repairable presentation quality, not a factual contradiction.
    heading_count = len(re.findall(r"^#{2,3}\s+.+$", article, re.MULTILINE))
    visible_chars = len(re.sub(r"\s+", "", article))
    if visible_chars >= 1200 and heading_count < 2:
        issues.append("article_structure_needs_edit")
    strong = r"(?:革命的|圧倒的|ゲームチェンジャー|世界初|世界最速|必ず|完全に|従来技術を終わらせ|開発を変える)"
    weak_evidence = re.search(r"(?:abstract|要旨|experimental|prototype|proof of concept|demo|予備的|本番未検証|研究環境)", context, re.I)
    if re.search(strong, title) and weak_evidence:
        issues.append("headline_overclaim")
    intro = article[:1200]
    if re.search(strong, intro) and weak_evidence:
        issues.append("intro_overclaim")
    if weak_evidence and re.search(r"(?:本番(?:環境)?(?:へ|に)?(?:導入|投入)|全面(?:導入|移行)|既存(?:環境|システム)を置き換)", action):
        issues.append("research_to_production_leap")
    action_tier = classify_action_risk_tier(action)
    limited_low_risk_action = action_tier == "LOW" and bool(re.search(r"(?:限定|小さく|PoC|比較(?:テスト|検証)|検証環境|回帰テスト|CI|profil(?:ing|e)|プロファイリング)", action, re.I))
    # 低スコアであっても、Evidenceに沿うLOW RISKの限定検証は矛盾ではない。
    if score and score <= 69 and not limited_low_risk_action:
        urgency_pattern = r"(?:今すぐ|直ちに|全面(?:導入|移行)|必ず導入)"
        unsupported_urgency = any(
            not _claim_is_negated(article, m.start(), m.end())
            for m in re.finditer(urgency_pattern, article)
        )
        if unsupported_urgency:
            issues.append("score_narrative_mismatch")
    if score >= 90 and re.search(r"(?:見る必要はない|検討不要|関心を持つ必要はない)", article) and not limited_low_risk_action:
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
        "decision": len(re.findall(r"(?:私なら|試(?:す|したい)|検証(?:する|したい)|比較(?:する|したい)|見送(?:る|り)|待(?:つ|ち)|導入を急が|CI|回帰テスト|profil(?:ing|e)|プロファイリング|計測|ベンチマーク)", article + "\n" + action, re.I)),
    }


def _find_fabricated_personal_experience(text: str) -> list[str]:
    """編集者としての判断は許可し、根拠のない実体験personaだけを検出する。"""
    body = text or ""
    patterns = [
        r"現場で[^。！？\n]{0,40}(?:進める|担当する|運用する|働く)立場として",
        r"(?:私|筆者)(?:自身)?(?:は|が)?[^。！？\n]{0,50}(?:使ってみた|使っている|利用している|試した|導入した|運用した|経験した|遭遇した|体験した)",
        r"(?:私|筆者)(?:自身)?[^。！？\n]{0,35}(?:驚いた|ワクワクした|痛感した|実感した)",
        r"(?:^|[。！？\n])\s*日常(?:の|的な)[^。！？\n]{0,55}(?:感じます|実感します|経験しています|遭遇しています)",
    ]
    hits = []
    for pattern in patterns:
        for match in re.finditer(pattern, body, re.I):
            snippet = re.sub(r"\s+", " ", match.group(0)).strip()
            if snippet:
                hits.append(snippet[:120])
    return list(dict.fromkeys(hits))[:4]


def _ai_style_composite_signals(text: str) -> dict:
    """High-precision, zero-API detector for *combinations* of formulaic AI prose signals.

    A single short sentence, contrast, or transition is normal human writing.  We therefore
    score only recurring/co-occurring patterns and use the composite threshold for review.
    """
    body = text or ""
    headings = [re.sub(r"\s+", " ", h).strip() for h in re.findall(r"^#{2,3}\s+(.+)$", body, re.MULTILINE)]
    prose = re.sub(r"^#{1,6}\s+.*$", "", body, flags=re.MULTILINE)

    glue_phrases = ("ここで重要なのは", "注目すべきは", "ポイントは", "つまり", "言い換えると")
    glue_counts = {phrase: prose.count(phrase) for phrase in glue_phrases}
    glue_total = sum(glue_counts.values())
    repeated_glue = max(glue_counts.values(), default=0) >= 2

    point_ending_count = len(re.findall(r"という点(?:です|だ)[。！？]", prose))
    contrast_count = len(re.findall(r"[^。！？\n]{1,70}ではありません[。！？][^。！？\n]{1,70}(?:です|なのです)[。！？]", prose))
    enum_count = len(re.findall(r"(?:ひとつは|一つは|もうひとつは|もう一つは|理由は[二三23]つ|ポイントは[二三23]つ)", prose))

    template_headings = {
        variant[key]
        for variant in ARTICLE_DISPLAY_VARIANTS
        for key in ("intro", "conclusion", "why", "what", "key", "decision", "final")
    }
    template_heading_hits = sum(1 for h in headings if h in template_headings)
    generic_heading_hits = sum(
        1 for h in headings
        if re.fullmatch(r"(?:なぜ重要なのか[。？]?|ポイント[。？]?|要点[。？]?|まとめ[。？]?|結論[。？]?|何が違うのか[。？]?|何が新しいのか[。？]?)", h)
    )

    # Detect paragraphs made of 3+ very short declarative sentences. One such burst can be
    # deliberate copywriting, so it contributes only one point to the composite.
    short_burst = False
    for para in re.split(r"\n\s*\n", prose):
        sentences = [s.strip() for s in re.split(r"(?<=[。！？])", para) if s.strip()]
        run = 0
        for sentence in sentences:
            visible = re.sub(r"[\s。！？]", "", sentence)
            run = run + 1 if 0 < len(visible) <= 18 else 0
            if run >= 3:
                short_burst = True
                break
        if short_burst:
            break

    # Uniform section size is only a weak signal. It matters only as part of the composite.
    section_lengths = []
    matches = list(re.finditer(r"^#{2,3}\s+.+$", body, re.MULTILINE))
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        length = len(re.sub(r"\s+", "", body[start:end]))
        if length >= 80:
            section_lengths.append(length)
    uniform_sections = False
    if len(section_lengths) >= 5:
        mean = sum(section_lengths) / len(section_lengths)
        variance = sum((x - mean) ** 2 for x in section_lengths) / len(section_lengths)
        cv = (variance ** 0.5) / mean if mean else 1.0
        uniform_sections = cv < 0.18

    # Run124: editorial-register phrases are not a blacklist.  We classify them into
    # independent habits and review only when several habits stack in one article.
    # This catches polished-but-formulaic AI copy while preserving a natural one-off phrase.
    editorial_register_patterns = (
        r"注目すべき", r"興味深い", r"重要なのは", r"実務的な示唆", r"示唆的",
        r"明確な(?:ユースケース|選択肢|メリット|方向性)", r"きわめて(?:エレガント|重要|有効)",
        r"(?:非常に|きわめて)魅力的", r"(?:妥当|適切)な判断(?:と言えます|です)", r"と言えます",
        r"(?:ポイント|要点)を整理(?:します|すると)", r"第一の柱", r"(?:第一|第二|第三)段階(?:として|では)",
        r"(?:第一歩|鍵となる|一番の近道)", r"確かめてみてはいかがでしょうか",
    )
    editorial_register_hits = [pat for pat in editorial_register_patterns if re.search(pat, prose)]
    editorial_register_count = sum(len(re.findall(pat, prose)) for pat in editorial_register_patterns)
    visible_prose_chars = max(1, len(re.sub(r"\s+", "", prose)))
    editorial_register_per_1000 = editorial_register_count * 1000.0 / visible_prose_chars
    ordinal_framing_count = len(re.findall(r"(?:第一の柱|第一段階|第二段階|第三段階|第一に|第二に|第三に)", prose))

    evaluative_register_count = len(re.findall(
        r"(?:非常に|きわめて)魅力的|示唆的|実務的な示唆|明確な(?:ユースケース|選択肢|メリット|方向性)|"
        r"(?:妥当|適切)な判断(?:と言えます|です)|興味深い", prose
    ))
    explanatory_ending_count = len(re.findall(
        r"(?:と言えます|と言える|ことがわかります|ことが分かります|ことを示しています|ことを意味します)[。！？]", prose
    ))
    staged_framing_count = len(re.findall(
        r"(?:第一の柱|第一段階|第二段階|第三段階|第一に|第二に|第三に|第一歩|鍵となる|一番の近道)", prose
    ))
    invitational_close_count = len(re.findall(
        r"(?:してみてはいかがでしょうか|確かめてみてはいかがでしょうか|試してみてはいかがでしょうか)[。！？]?", prose
    ))
    editorial_habit_types = sum(bool(v) for v in (
        evaluative_register_count, explanatory_ending_count, staged_framing_count, invitational_close_count
    ))

    # Two paths, both deliberately composite:
    # 1) classic Run123 density + mechanical companion; or
    # 2) lower raw density but 3+ distinct editorial habits, which is what the real ESP32/Kobo
    #    regressions exposed.  A single "興味深い" or one invitation never triggers this.
    editorial_register_dense = (
        (editorial_register_count >= 5 and len(editorial_register_hits) >= 4 and editorial_register_per_1000 >= 1.0)
        or (editorial_register_count >= 4 and len(editorial_register_hits) >= 4 and editorial_habit_types >= 3)
    )
    editorial_register_companion = bool(
        ordinal_framing_count >= 2 or staged_framing_count >= 2 or point_ending_count >= 1 or repeated_glue
        or (evaluative_register_count >= 2 and invitational_close_count >= 1)
    )

    score = 0
    if glue_total >= 3: score += 2
    if repeated_glue: score += 1
    if point_ending_count >= 3: score += 2
    if contrast_count >= 2: score += 2
    if enum_count >= 2: score += 1
    if template_heading_hits >= 3: score += 3
    elif template_heading_hits >= 1: score += 1
    if generic_heading_hits >= 4: score += 2
    if short_burst: score += 1
    if uniform_sections: score += 1
    if editorial_register_dense and editorial_register_companion: score += 5

    return {
        "score": score,
        "high": score >= 5,
        "glue_total": glue_total,
        "repeated_glue": repeated_glue,
        "point_ending_count": point_ending_count,
        "contrast_count": contrast_count,
        "enum_count": enum_count,
        "template_heading_hits": template_heading_hits,
        "generic_heading_hits": generic_heading_hits,
        "short_burst": short_burst,
        "uniform_sections": uniform_sections,
        "editorial_register_count": editorial_register_count,
        "editorial_register_distinct": len(editorial_register_hits),
        "editorial_register_per_1000": editorial_register_per_1000,
        "editorial_register_dense": editorial_register_dense,
        "editorial_register_companion": editorial_register_companion,
        "ordinal_framing_count": ordinal_framing_count,
        "evaluative_register_count": evaluative_register_count,
        "explanatory_ending_count": explanatory_ending_count,
        "staged_framing_count": staged_framing_count,
        "invitational_close_count": invitational_close_count,
        "editorial_habit_types": editorial_habit_types,
    }


def _sentence_shingles(value: str, width: int = 5) -> set[str]:
    compact = re.sub(r"https?://\S+|`[^`]+`|[A-Za-z0-9_.:/+-]+", " ", value or "")
    compact = re.sub(r"[\s。、！？!?「」『』（）()【】#*_>・:：;；,，.-]+", "", compact)
    if len(compact) < width:
        return set()
    return {compact[i:i + width] for i in range(len(compact) - width + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def _human_editorial_depth_signals(text: str) -> dict:
    """Run121 zero-API signals for over-explaining and mechanically explicit prose.

    These are deliberately weak on their own. Japanese professional prose can naturally use
    transitions and repetition; only recurring combinations feed the composite review threshold.
    """
    body = text or ""
    prose = re.sub(r"^#{1,6}\s+.*$", "", body, flags=re.MULTILINE)
    sentences = [x.strip() for x in re.split(r"(?<=[。！？!?])", prose) if len(re.sub(r"\s+", "", x)) >= 28]
    near_duplicate_pairs = 0
    for i, left in enumerate(sentences):
        a = _sentence_shingles(left)
        if len(a) < 8:
            continue
        for right in sentences[i + 1:i + 7]:
            b = _sentence_shingles(right)
            if len(b) >= 8 and _jaccard(a, b) >= 0.66:
                near_duplicate_pairs += 1
                break

    transitions = ("一方で", "ただし", "そのため", "つまり", "また", "さらに", "そこで", "とはいえ", "なお", "逆に")
    transition_counts = {t: len(re.findall(rf"(?:^|[。！？!?\n])\s*{re.escape(t)}", prose)) for t in transitions}
    transition_total = sum(transition_counts.values())
    repeated_transition = max(transition_counts.values(), default=0) >= 3

    # Repeated explanatory closers are a stronger signal than ordinary desu/masu endings.
    explanatory_closer_count = len(re.findall(r"(?:と言えます|といえます|と考えられます|ということです|ことになります|わけです)[。！？]", prose))

    score = 0
    if near_duplicate_pairs >= 2: score += 3
    elif near_duplicate_pairs == 1: score += 1
    if transition_total >= 8: score += 2
    elif transition_total >= 6: score += 1
    if repeated_transition: score += 1
    if explanatory_closer_count >= 3: score += 2
    return {
        "score": score,
        "high": score >= 4,
        "near_duplicate_pairs": near_duplicate_pairs,
        "transition_total": transition_total,
        "repeated_transition": repeated_transition,
        "explanatory_closer_count": explanatory_closer_count,
    }


def _style_sequence(article: str) -> tuple[str, ...]:
    prose = re.sub(r"^#{1,6}\s+.*$", "", article or "", flags=re.MULTILINE)
    result: list[str] = []
    transition_map = (("一方で", "T_CONTRAST"), ("ただし", "T_CAVEAT"), ("そのため", "T_CAUSE"),
                      ("つまり", "T_SUMMARY"), ("また", "T_ADD"), ("さらに", "T_ADD"),
                      ("そこで", "T_ACTION"), ("とはいえ", "T_CAVEAT"))
    for raw in re.split(r"(?<=[。！？!?])", prose):
        sentence = re.sub(r"\s+", " ", raw).strip()
        visible = re.sub(r"[\s。！？!?]", "", sentence)
        if len(visible) < 8:
            continue
        length = "S" if len(visible) <= 28 else "M" if len(visible) <= 58 else "L" if len(visible) <= 95 else "XL"
        trans = "T_NONE"
        for prefix, code in transition_map:
            if sentence.startswith(prefix):
                trans = code
                break
        if re.search(r"(?:たい|妥当|価値がある|見送り|急がない)[。！？!?]?$", sentence): end = "E_DECISION"
        elif re.search(r"(?:可能性があります|考えられます|かもしれません)[。！？!?]?$", sentence): end = "E_HEDGE"
        elif re.search(r"(?:ということです|わけです|と言えます|といえます)[。！？!?]?$", sentence): end = "E_EXPLAIN"
        elif re.search(r"ます[。！？!?]?$", sentence): end = "E_MASU"
        elif re.search(r"です[。！？!?]?$", sentence): end = "E_DESU"
        else: end = "E_OTHER"
        result.extend((length, trans, end))
        if len(result) >= 45:
            break
    return tuple(result)


def _rhetorical_template_phrases(article: str) -> set[str]:
    """Weak Run127 signature for entertainment-template reuse across articles.

    A phrase never fails an article by itself; it only contributes to the existing cross-article
    composite when multiple staging phrases recur with other structural similarity.
    """
    candidates = (
        "実は", "少し考えてみましょう", "ここがおもしろいところです",
        "また3文字の専門用語か", "恋愛に例えるなら", "猫で考えると",
        "天才だけど", "に例えると", "例えるなら",
    )
    text = article or ""
    return {phrase for phrase in candidates if phrase in text}


def _cross_article_naturalness_signals(article: str, peers: list[dict] | None = None) -> dict:
    """Detect run-level template fingerprints without semantic/LLM comparison.

    A review requires both very similar rhetorical sequencing and at least one additional
    structural coincidence. This keeps shared technical vocabulary from creating false hits.
    """
    peer_rows = peers if peers is not None else _RUN_ARTICLE_STYLE_MEMORY
    seq = _style_sequence(article)
    headings = [re.sub(r"[\s。、！？!?]", "", h) for h in re.findall(r"^#{2,3}\s+(.+)$", article or "", re.MULTILINE)]
    heading_count = len(headings)
    intro = _article_opening_excerpt(article, 520)
    intro_shingles = _sentence_shingles(intro, 5)
    rhetorical = _rhetorical_template_phrases(article)
    best = {"score": 0, "peer": "", "sequence_similarity": 0.0, "opening_similarity": 0.0, "heading_count_match": False, "shared_rhetorical_phrases": []}
    from difflib import SequenceMatcher
    for peer in peer_rows or []:
        other_seq = tuple(peer.get("sequence") or ())
        shared_rhetorical = sorted(rhetorical & set(peer.get("rhetorical_phrases") or ()))
        if len(seq) < 18 or len(other_seq) < 18:
            # Keep visibility of repeated staging phrases even for short articles, but never
            # escalate to cross-article review without enough structural evidence.
            if len(shared_rhetorical) >= 2 and not best.get("shared_rhetorical_phrases"):
                best = {"score": 1, "peer": str(peer.get("name") or ""), "sequence_similarity": 0.0,
                        "opening_similarity": 0.0, "heading_count_match": False,
                        "shared_rhetorical_phrases": shared_rhetorical}
            continue
        sequence_similarity = SequenceMatcher(None, seq, other_seq, autojunk=False).ratio()
        opening_similarity = _jaccard(intro_shingles, set(peer.get("opening_shingles") or ()))
        heading_match = heading_count >= 3 and heading_count == int(peer.get("heading_count") or 0)
        score = 0
        if sequence_similarity >= 0.88: score += 3
        elif sequence_similarity >= 0.82: score += 2
        if opening_similarity >= 0.58: score += 2
        elif opening_similarity >= 0.48: score += 1
        if heading_match: score += 1
        if len(shared_rhetorical) >= 2: score += 1
        if score > best["score"]:
            best = {"score": score, "peer": str(peer.get("name") or ""), "sequence_similarity": sequence_similarity,
                    "opening_similarity": opening_similarity, "heading_count_match": heading_match,
                    "shared_rhetorical_phrases": shared_rhetorical}
    best["high"] = best["score"] >= 4
    return best


def _remember_article_style(name: str, article: str) -> None:
    if not article:
        return
    intro = _article_opening_excerpt(article, 520)
    _RUN_ARTICLE_STYLE_MEMORY.append({
        "name": name or "",
        "sequence": _style_sequence(article),
        "opening_shingles": tuple(_sentence_shingles(intro, 5)),
        "heading_count": len(re.findall(r"^#{2,3}\s+.+$", article, re.MULTILINE)),
        "rhetorical_phrases": tuple(sorted(_rhetorical_template_phrases(article))),
    })
    # TOP3 + backfill is small, but cap memory defensively for long retry/backlog runs.
    del _RUN_ARTICLE_STYLE_MEMORY[:-12]


def reset_article_style_memory() -> None:
    _RUN_ARTICLE_STYLE_MEMORY.clear()


def _article_opening_excerpt(article: str, max_chars: int = 700) -> str:
    """Return the actual reader-facing lead even when Run108 uses a content-specific heading."""
    body = article or ""
    first_heading = re.search(r"^#{2,3}\s+.+$", body, re.MULTILINE)
    if first_heading and first_heading.start() > 0:
        lead = body[:first_heading.start()].strip()
        if lead:
            return lead[:max_chars]
    legacy = _extract_any_markdown_section(body, _display_heading_aliases("intro"))
    if legacy:
        return legacy[:max_chars]
    # If the article starts with a content-specific heading, inspect its first section instead.
    if first_heading:
        start = first_heading.end()
        next_heading = re.search(r"^#{2,3}\s+.+$", body[start:], re.MULTILINE)
        end = start + next_heading.start() if next_heading else len(body)
        return body[start:end].strip()[:max_chars]
    return body[:max_chars]


def _reader_experience_signals(article: str) -> dict:
    """0-API diagnostics for reader pull without creating new hard gates.

    Run140 treats delight as the combination of clarity, human proximity, and an article-specific
    reason to keep reading. Missing analogy, humor, or a particular catchphrase is never itself
    a failure; a plain but engaging explanation can still be GOOD.
    """
    body = article or ""
    headings = [re.sub(r"\s+", " ", h).strip() for h in re.findall(r"^#{2,3}\s+(.+)$", body, re.MULTILINE)]
    prose = re.sub(r"^#{1,6}\s+.*$", "", body, flags=re.MULTILINE)
    visible = re.sub(r"\s+", "", prose)
    sentences = [x.strip() for x in re.split(r"(?<=[。！？!?])", prose) if x.strip()]
    long_sentences = sum(len(re.sub(r"\s+", "", x)) >= 105 for x in sentences)

    common = {"AI", "API", "LLM", "OSS", "URL", "UI", "UX", "DB", "CPU", "GPU", "ID"}
    acronyms = []
    for m in re.finditer(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9-]{1,8})(?![A-Za-z0-9])", prose):
        token = m.group(1)
        if token in common or token in acronyms:
            continue
        near = prose[max(0, m.start()-90):m.end()+120]
        explained = bool(re.search(rf"(?:{re.escape(token)}\s*[（(].{{2,70}}[）)]|[（(].{{2,70}}[）)]\s*{re.escape(token)}|.{{3,90}}[（(]{re.escape(token)}[）)]|{re.escape(token)}(?:とは|は、|は){{1}}.{{4,80}}(?:仕組み|方式|規格|標準|ツール|モデル|プロトコル|ルール))", near, re.S))
        if not explained:
            acronyms.append(token)

    tech_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_.+/#-]{2,}|[ァ-ヴー]{5,}", prose)
    technical_density = len(tech_tokens) * 1000.0 / max(len(visible), 1)

    intro = _article_opening_excerpt(body, 700)
    announcement_only = bool(
        intro and re.match(r"^.{0,45}(?:発表|公開|リリース|更新)(?:しました|された|されました|した)", intro.strip())
        and not re.search(r"(?:なぜ|困|変わ|仕事|生活|使|意外|面白|気にな|身近|たとえば|例えば|もし|ところが|実際)", intro[:520])
    )
    self_relevance = bool(re.search(r"(?:あなた|私たち|現場|仕事|会社|チーム|利用者|ユーザー|開発者|担当者|日常|スマホ|生活|導入する側|使う側|旅行|買い物|学校|家族)", intro[:700] or prose[:700]))
    curiosity = bool(re.search(r"(?:意外|不思議|面白|なぜ|一見|ところが|変わる|違い|気になる|もし|何が|逆に|実際には)", intro[:700]))

    analogy_markers = re.findall(r"(?:たとえば|例えば|〜のような|ようなもの|たとえるなら|例えるなら|まるで|身近な|もし.+なら)", prose)
    analogy_used = bool(analogy_markers)
    playful_topics = re.findall(r"(?:猫|犬|恋愛|デート|コンビニ|家族|料理|ゲーム|旅行)", prose)
    analogy_overuse = len(analogy_markers) >= 4 or (len(playful_topics) >= 4 and len(set(playful_topics)) >= 2)
    serious_theme = bool(re.search(r"(?:security|risk|governance|cyber|脆弱性|攻撃|侵害|情報漏えい|規制|監査|ガバナンス|セキュリティ|リスク)", body, re.I))
    tone_mismatch = serious_theme and len(playful_topics) >= 2

    # Run127: narrative pull is weakened by long uninterrupted explanatory blocks.
    paragraphs = [re.sub(r"\s+", " ", x).strip() for x in re.split(r"\n\s*\n", prose) if re.sub(r"\s+", "", x)]
    explanatory_paras = 0
    max_explanatory_run = 0
    current_run = 0
    pull_markers_re = re.compile(r"(?:[？?]|たとえば|例えば|もし|ところが|一方|逆に|意外|実際|場面|朝\d{0,2}時|困る|怖い|変わる|比べ|なのに)")
    for para in paragraphs:
        is_explain = len(re.sub(r"\s+", "", para)) >= 90 and not pull_markers_re.search(para)
        if is_explain:
            explanatory_paras += 1
            current_run += 1
            max_explanatory_run = max(max_explanatory_run, current_run)
        else:
            current_run = 0
    scene_present = bool(re.search(r"(?:朝\d{1,2}時|会議を|予約を|店を探|予定を|メールを|カレンダー|スマホで|旅行|買い物|学校で|家で|電車で|もし[^。！？]{4,100}(?:頼|言|すると|なら))", prose))
    narrative_pull = curiosity or scene_present or max_explanatory_run <= 2

    # Headings should carry article-specific nouns, not mostly generic labels.
    generic_heading_re = re.compile(r"^(?:なぜ重要(?:なのか)?|何が変わる(?:のか)?|今後どうなる(?:のか)?|今すぐ導入すべき(?:なのか)?|最終判断|まとめ|結論|ポイント|要点|詳細)[。？?]?$" )
    generic_headings = [h for h in headings if generic_heading_re.fullmatch(h)]
    heading_pull = not (len(headings) >= 3 and len(generic_headings) >= 2)

    # Article-specific angle: avoid copy-pastable meta prose without topic-bearing nouns.
    generic_angle_hits = len(re.findall(r"(?:今回の発表|今回の変化|この技術|この仕組み|このニュース|今後に注目|動向を見ていき)", prose))
    specific_heading_chars = sum(len(re.sub(r"(?:なぜ|重要|今後|判断|まとめ|結論|ポイント|詳細|何が|変わる)", "", h)) for h in headings)
    article_specific_angle = generic_angle_hits <= 3 and (not headings or specific_heading_chars >= max(8, len(headings) * 3))

    # Run128: an everyday/plain-language bridge becomes recommended when jargon load is high.
    # This remains a soft diagnostic: Evidence/Fact/Decision gates are never weakened or blocked by it.
    everyday_terms = bool(re.search(r"(?:旅行|レストラン|買い物|家族|恋愛|デート|学校|趣味|猫|犬|ゲーム|SNS|スマホ|料理|引っ越し|電車|病院|天気|スポーツ|友人|会議|メール|カレンダー|鍵|合鍵|受付|店|財布|地図|図書館)", prose))
    plain_explanation = bool(re.search(
        r"(?:簡単に言えば|ひと言で言えば|一言で言えば|平たく言えば|要するに|言葉を変えると|"
        r"つまり[^。！？]{3,90}(?:仕組み|ルール|方法|考え方|役割)|"
        r"(?:これは|これはつまり|この仕組みは)[^。！？]{4,100}(?:ための|ような)(?:仕組み|ルール|方法|考え方|もの))",
        prose,
    ))
    bridge_needed = bool(acronyms) or technical_density >= 26.0
    plain_language_bridge_present = bool(everyday_terms or scene_present or analogy_used or plain_explanation)
    if plain_language_bridge_present:
        everyday_bridge = "PRESENT"
    elif bridge_needed:
        everyday_bridge = "REVIEW_NEEDED"
    else:
        everyday_bridge = "NOT_REQUIRED"

    # A dense paragraph with several technical tokens and no translation marker is a useful
    # zero-API signal for the exact failure mode seen in the Run127 real-article regression.
    jargon_dense_paragraphs = 0
    for para in paragraphs:
        pv = re.sub(r"\s+", "", para)
        if len(pv) < 70:
            continue
        p_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_.+/#-]{2,}|[ァ-ヴー]{5,}", para)
        p_density = len(p_tokens) * 1000.0 / max(len(pv), 1)
        has_translation = bool(re.search(r"(?:たとえば|例えば|簡単に言えば|ひと言で言えば|一言で言えば|平たく言えば|要するに|つまり|ようなもの|身近な|スマホ|買い物|恋愛|デート|鍵|学校|旅行|料理|家族)", para))
        if p_density >= 38.0 and not has_translation:
            jargon_dense_paragraphs += 1
    jargon_translation = "GOOD" if not (bridge_needed and not plain_language_bridge_present) and jargon_dense_paragraphs <= 1 else "REVIEW"
    non_engineer_core_clarity = "GOOD" if jargon_translation == "GOOD" and (not bridge_needed or plain_language_bridge_present) else "REVIEW"

    # News relevance must come from explicit temporal/event language, not fabricated freshness.
    news_relevance = bool(re.search(r"(?:今回|発表|公開|更新|リリース|対応を開始|採用|仕様変更|公開された|新たに|今週|今日|\d{4}[-年/]\d{1,2})", intro[:900]))

    last = prose[-1000:]
    return_pull = bool(re.search(r"(?:次に|次版|今後|試す|比較|検証|確かめ|判断|選択|待つ|見送|導入|変化|残る|問い|条件|自分なら|私なら)", last))

    # Run131: measure actual reader proximity, not merely the presence of an everyday noun.
    # Run129 was too permissive: a dry sentence containing "スマホ" could be labelled warm even
    # when no human conversational distance was created. We now require a functional proximity
    # moment while keeping it soft-only so warmth cannot consume retry budget or raise rejection.
    conversational_patterns = [
        r"ですよね[。！？!?]", r"なんですよ[。！？!?]", r"やっぱり[、,]",
        r"ちょっと想像してみてください", r"ここが面白いところ",
        r"思い出してみてください", r"ありますよね[。！？!?]",
        r"(?:使った|見た|聞かれた|困った|迷った)こと(?:は)?(?:ありませんか|ありますか|ありますよね)",
        r"(?:難しそう|大げさ|物々しい)(?:な名前|に見え|に聞こえ)[^。！？]{0,45}(?:ですが|けれど|ものの)",
        r"名前は難しそう[^。！？]{0,45}(?:ですが|でも)",
        r"(?:想像|思い浮かべ)して(?:みる|みて)",
    ]
    conversational_hits = sum(len(re.findall(p, prose)) for p in conversational_patterns)
    reader_question_hits = len(re.findall(r"(?:でしょうか|ませんか|ありますか|ありますよね|ですよね|感じませんか|思いませんか|考えたくなりますよね)[。！？!?]", prose))
    friendly_turn_hits = len(re.findall(r"(?:難しそう(?:ですが|でも)|名前は難し|意外と単純|やっていることは[^。！？]{0,35}(?:単純|シンプル)|身近な話にすると)", prose))
    reader_proximity_moments = conversational_hits + reader_question_hits + friendly_turn_hits
    repeated_conversational_phrase = any(len(re.findall(p, prose)) >= 3 for p in conversational_patterns)
    conversational_overuse = conversational_hits >= 7 or reader_question_hits >= 6 or repeated_conversational_phrase
    conversational_warmth = reader_proximity_moments >= 1

    # Run133: Reader-first rhythm and editorial compression diagnostics.
    # The goal is not to reward chatter. We measure whether a non-engineer gets an early foothold,
    # whether dense technical explanation runs too long, and whether the article exposes too many
    # implementation identifiers for a free reader-facing note article. All signals stay soft-only.
    opening_prose = re.sub(r"\s+", " ", prose[:900]).strip()
    opening_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_.+/#-]{2,}|[ァ-ヴー]{5,}", opening_prose)
    opening_density = len(opening_tokens) * 1000.0 / max(len(re.sub(r"\s+", "", opening_prose)), 1)
    opening_reader_bridge = bool(re.search(
        r"(?:[？?]|ありませんか|ありますよね|ですよね|たとえば|例えば|もし|スマホ|買い物|旅行|学校|家族|仕事で|使う側|普通の言葉|簡単に言えば|要するに|意外|困った|迷った)",
        opening_prose,
    ))
    opening_non_engineer_access = "GOOD" if opening_density < 42.0 and (opening_reader_bridge or not bridge_needed) else "REVIEW"

    # Count implementation-heavy identifiers. This is deliberately conservative: we do not claim
    # every token is jargon, only detect an overloaded surface area that often correlates with the
    # Run132 failure mode (RFC numbers, flags, acronyms, internal component names, etc.).
    implementation_identifiers = re.findall(
        r"\b(?:SEP-\d+|RFC\s?\d+|[A-Z]{2,8}-\d{2,}|[A-Z]{2,8}\d{2,}|[A-Z]{3,8}|[A-Za-z]+/[A-Za-z0-9_.-]+)\b",
        prose,
    )
    unique_implementation_identifiers = sorted(set(implementation_identifiers))
    implementation_detail_load = "REVIEW" if len(unique_implementation_identifiers) >= 8 else "GOOD"

    # A reader-friendly article should not stay in dense-explanation mode for three paragraphs in a row.
    # We reuse max_explanatory_run so this adds no model call and no second parsing pipeline.
    reader_temperature_rhythm = "GOOD" if max_explanatory_run <= 2 else "REVIEW"

    accessibility_issues = []
    if acronyms: accessibility_issues.append("unexplained_acronyms")
    if long_sentences >= 3: accessibility_issues.append("long_sentence_cluster")
    if technical_density >= 34: accessibility_issues.append("technical_term_concentration")
    if bridge_needed and not plain_language_bridge_present: accessibility_issues.append("plain_language_bridge_missing")
    if jargon_dense_paragraphs >= 2: accessibility_issues.append("jargon_translation_weak")
    if opening_non_engineer_access != "GOOD": accessibility_issues.append("opening_non_engineer_access_weak")
    if implementation_detail_load != "GOOD": accessibility_issues.append("implementation_detail_overload")
    if reader_temperature_rhythm != "GOOD": accessibility_issues.append("reader_temperature_rhythm_weak")
    enjoyment_issues = []
    if analogy_overuse: enjoyment_issues.append("analogy_overuse")
    if tone_mismatch: enjoyment_issues.append("serious_topic_tone_mismatch")
    if announcement_only: enjoyment_issues.append("announcement_summary_opening")
    if not self_relevance: enjoyment_issues.append("reader_bridge_weak")
    if max_explanatory_run >= 4: enjoyment_issues.append("explanation_run_long")
    if not heading_pull: enjoyment_issues.append("generic_heading_cluster")
    if not article_specific_angle: enjoyment_issues.append("article_specific_angle_weak")
    if not news_relevance: enjoyment_issues.append("news_relevance_weak")
    if not conversational_warmth: enjoyment_issues.append("reader_proximity_missing")
    if conversational_overuse: enjoyment_issues.append("conversational_tone_overuse")

    # Run142: Narrative Understanding Progression.
    # Reader Delight must reflect understanding that moves forward, not a checklist of warm words.
    _paras = [x.strip() for x in re.split(r"\n\s*\n", prose) if x.strip()]
    _body_after_opening = "\n\n".join(_paras[1:]) if len(_paras) > 1 else prose
    narrative_progression_hits = len(re.findall(
        r"(?:ところが|理由(?:の一つ)?が|なぜなら|その結果|だからこそ|だから|すると|そこで|一方で|でも|では導入すれば|つまり何が|何が困る|何を意味する|につながる|ためです|からです)",
        prose,
    ))
    causal_explanation_hits = len(re.findall(
        r"(?:理由|なぜ|ため|ので|その結果|だから|そこで|つまり|一方で|ところが|すると)", prose
    ))
    decision_or_implication_hits = len(re.findall(
        r"(?:私なら|判断|導入|安全性|意味|困る|価値|影響|使うなら|見るべき|確認|試して|比較)", prose
    ))
    factual_substance_hits = len(re.findall(
        r"(?:ニューロン|特徴|活性化|非直交|ベクトル|重み|回路|因果|制約|互換性|一次資料|"
        r"Sparse Autoencoder|Superposition|Polysemanticity|辞書学習|スパース|"
        r"権限|最小権限|アクセス|ログ|承認|監視|演算性能|メモリ|帯域|消費電力|ベンチマーク|"
        r"コスト|冷却|モデル|トークン|暗号|認証|脆弱性|API|プロトコル)",
        prose, re.I,
    ))
    analogy_hits = len(re.findall(
        r"(?:たとえば|例える|ような|みたい|押し入れ|収納|合鍵|家族|スマホ|料理|電車|棚|箱|引き出し)", prose
    ))
    report_style_body_hits = len(re.findall(
        r"(?:評価します|解析します|同定します|抽出します|確認します|検討します|必要があります|方式です|発生します|分布します)",
        _body_after_opening,
    ))
    body_reader_bridge_hits = len(re.findall(
        r"(?:ですよね|ませんか|感じませんか|思いませんか|難しそう|身近|困る|なぜ|だから|ところが|でも|そこで|私なら)",
        _body_after_opening,
    ))
    warm_hook_cold_body = (
        reader_proximity_moments >= 1
        and len(_paras) >= 3
        and report_style_body_hits >= 4
        and body_reader_bridge_hits <= 1
    )
    analogy_substance_thin = analogy_hits >= 3 and factual_substance_hits <= 3 and causal_explanation_hits <= 2
    # Run144: concise good prose can show progression through a concrete technical core + caveat/action,
    # without mandatory catchphrases or a fixed number of explicit causal connectors.
    caveat_or_concrete_action = bool(re.search(
        r"(?:ただし|とは限ら|わけではありません|保証されるわけでは|まず[^。！？]{0,80}(?:試|比較|確認|限定)|"
        r"小さ(?:く|な環境)|範囲を広げ|比較対象|見送|待つ|段階(?:的に)?導入)",
        prose, re.I,
    ))
    explicit_reader_decision_action = bool(re.search(
        r"(?:私なら|導入するなら|使うなら|判断(?:します|する|材料)|比較(?:します|する|対象)|"
        r"確認(?:します|する)|まず[^。！？]{0,80}(?:試|比べ|確認)|見送(?:ります|る)|追(?:います|う)|"
        r"検証(?:します|する)|段階(?:的に)?導入)",
        prose, re.I,
    ))
    practical_reader_progression = (
        len(_paras) >= 3
        and factual_substance_hits >= 2
        and opening_non_engineer_access == "GOOD"
        and (self_relevance or plain_language_bridge_present or reader_proximity_moments >= 1)
        and explicit_reader_decision_action
        and caveat_or_concrete_action
        and decision_or_implication_hits >= 1
    )
    narrative_understanding_progression = (
        (
            narrative_progression_hits >= 2
            and causal_explanation_hits >= 2
            and decision_or_implication_hits >= 1
            and factual_substance_hits >= 2
        )
        or practical_reader_progression
    )
    if warm_hook_cold_body:
        enjoyment_issues.append("warm_hook_cold_body")
    if analogy_substance_thin:
        enjoyment_issues.append("analogy_substance_thin")
    if not narrative_understanding_progression:
        enjoyment_issues.append("narrative_understanding_progression_weak")

    # Run140: composite reader outcome. This remains 0-API and soft-only: it does not trigger
    # an extra Gemini call by itself. The generation prompt is responsible for achieving it.
    reader_delight_good = (
        opening_non_engineer_access == "GOOD"
        and reader_proximity_moments >= 1
        and not conversational_overuse
        and article_specific_angle
        and self_relevance
        and (plain_language_bridge_present or not bridge_needed)
    )
    # Run144: Reader Delight is a balance, not an AND-list of conversational tokens.
    # Hard-negative patterns stay strict; positive quality may be demonstrated by independent signals.
    reader_delight_overclaim = bool(re.search(
        r"(?:完全に理解できれば|完全に整理できます|完全に取り出せ|ブラックボックス問題は解決|"
        r"危険な挙動も事前に見抜け|必須条件にします|すぐ全社導入|私なら今のうちに導入します)",
        prose, re.I,
    ))
    # Repetition is measured across distinct paragraphs, not by repeated technical nouns.
    _paragraph_fragment_counts = {}
    for _para in _paras:
        _compact = re.sub(r"https?://\S+|`[^`]+`|[A-Za-z0-9_.:/+-]+|[\s。、！？!?「」『』（）()【】#*_>・:：;；,，.-]+", "", _para)
        _seen = set()
        for _idx in range(max(0, len(_compact) - 6)):
            _piece = _compact[_idx:_idx + 7]
            if len(_piece) == 7:
                _seen.add(_piece)
        for _piece in _seen:
            _paragraph_fragment_counts[_piece] = _paragraph_fragment_counts.get(_piece, 0) + 1
    repeated_cross_paragraph_fragments = [k for k, v in _paragraph_fragment_counts.items() if v >= 3]
    repetitive_insight = len(repeated_cross_paragraph_fragments) >= 3
    if reader_delight_overclaim:
        enjoyment_issues.append("reader_delight_overclaim")
    if repetitive_insight:
        enjoyment_issues.append("repetitive_insight")

    positive_reader_signals = sum(bool(x) for x in (
        opening_non_engineer_access == "GOOD",
        article_specific_angle,
        plain_language_bridge_present or not bridge_needed,
        self_relevance or reader_proximity_moments >= 1 or everyday_terms or scene_present,
        factual_substance_hits >= 2,
        explicit_reader_decision_action and caveat_or_concrete_action,
        narrative_understanding_progression,
        curiosity or return_pull,
    ))
    reader_delight_base = (
        positive_reader_signals >= 6
        and opening_non_engineer_access == "GOOD"
        and article_specific_angle
        and (plain_language_bridge_present or not bridge_needed)
        and factual_substance_hits >= 2
        and explicit_reader_decision_action
    )
    reader_delight = "GOOD" if (
        reader_delight_base
        and narrative_understanding_progression
        and not conversational_overuse
        and not warm_hook_cold_body
        and not analogy_substance_thin
        and not reader_delight_overclaim
        and not repetitive_insight
    ) else "REVIEW"

    # Reader-value budget: length itself is never a defect. Diagnose only the patterns that make
    # an article *feel* long to a non-engineer: repeated dense explanation, duplicated analogy,
    # implementation overload, or long uninterrupted explanatory runs. Evidence/Decision depth may
    # legitimately require a longer article, so character count remains observability only.
    article_char_count = len(re.sub(r"\s+", "", prose))
    information_budget = "GOOD"
    if (
        jargon_dense_paragraphs >= 3
        or (len(analogy_markers) >= 3 and technical_density >= 30.0)
        or (max_explanatory_run >= 4 and technical_density >= 26.0)
        or (len(unique_implementation_identifiers) >= 10 and jargon_dense_paragraphs >= 2)
    ):
        information_budget = "REVIEW"

    accessibility = "GOOD" if not accessibility_issues else "REVIEW"
    curiosity_pull = "GOOD" if (curiosity or self_relevance) and not announcement_only else "REVIEW"
    reader_enjoyment = "GOOD" if not enjoyment_issues else "REVIEW"
    return_status = "GOOD" if return_pull else "REVIEW"
    return {
        "accessibility": accessibility,
        "curiosity_pull": curiosity_pull,
        "reader_enjoyment": reader_enjoyment,
        "return_pull": return_status,
        "narrative_pull": "GOOD" if narrative_pull and max_explanatory_run < 4 else "REVIEW",
        "article_specific_angle": "GOOD" if article_specific_angle else "REVIEW",
        "everyday_bridge": everyday_bridge,
        "plain_language_bridge": "GOOD" if plain_language_bridge_present or not bridge_needed else "REVIEW",
        "jargon_translation": jargon_translation,
        "non_engineer_core_clarity": non_engineer_core_clarity,
        "headline_pull": "GOOD" if heading_pull else "REVIEW",
        "news_relevance": "GOOD" if news_relevance else "REVIEW",
        "conversational_warmth": "GOOD" if conversational_warmth and not conversational_overuse else ("REVIEW_OVERUSE" if conversational_overuse else "REVIEW_MISSING"),
        "conversational_marker_count": conversational_hits,
        "reader_proximity_moment_count": reader_proximity_moments,
        "reader_proximity": "GOOD" if reader_proximity_moments >= 1 and not conversational_overuse else ("REVIEW_OVERUSE" if conversational_overuse else "REVIEW_MISSING"),
        "reader_delight": reader_delight,
        "reader_delight_positive_signals": positive_reader_signals,
        "reader_delight_overclaim": reader_delight_overclaim,
        "repetitive_insight": repetitive_insight,
        "caveat_or_concrete_action": caveat_or_concrete_action,
        "explicit_reader_decision_action": explicit_reader_decision_action,
        "narrative_understanding_progression": "GOOD" if narrative_understanding_progression else "REVIEW",
        "narrative_progression_hits": narrative_progression_hits,
        "causal_explanation_hits": causal_explanation_hits,
        "factual_substance_hits": factual_substance_hits,
        "analogy_hits": analogy_hits,
        "warm_hook_cold_body": warm_hook_cold_body,
        "analogy_substance_thin": analogy_substance_thin,
        "information_budget": information_budget,
        "opening_non_engineer_access": opening_non_engineer_access,
        "opening_technical_terms_per_1000_chars": round(opening_density, 1),
        "implementation_detail_load": implementation_detail_load,
        "implementation_identifier_count": len(unique_implementation_identifiers),
        "reader_temperature_rhythm": reader_temperature_rhythm,
        "article_char_count": article_char_count,
        "reader_proximity_per_1000_chars": round(reader_proximity_moments * 1000.0 / max(article_char_count, 1), 2),
        "conversational_overuse": conversational_overuse,
        "analogy_used": analogy_used,
        "analogy_necessary": "EDITORIAL_JUDGMENT" if analogy_used else ("BRIDGE_RECOMMENDED" if bridge_needed and not plain_language_bridge_present else "NOT_REQUIRED"),
        "unexplained_jargon": acronyms[:8],
        "accessibility_issues": accessibility_issues,
        "enjoyment_issues": enjoyment_issues,
        "technical_terms_per_1000_chars": round(technical_density, 1),
        "bridge_needed": bridge_needed,
        "plain_language_bridge_present": plain_language_bridge_present,
        "jargon_dense_paragraph_count": jargon_dense_paragraphs,
        "long_sentence_count": long_sentences,
        "max_explanatory_paragraph_run": max_explanatory_run,
        "generic_headings": generic_headings[:8],
        "scene_present": scene_present,
        "soft_only": True,
    }


def validate_human_appeal_gate(parsed: dict, peer_articles: list[dict] | None = None) -> tuple[str, list[str]]:
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

    if _find_fabricated_personal_experience(article):
        issues.append("fabricated_personal_experience")

    # 「○○について。」のような説明だけの題は、過剰な安全化でタイトルの役割を
    # 失った可能性が高い。ただし短い固有名詞タイトルを一律に落とさない。
    if re.fullmatch(r".{1,45}(?:について|の紹介|を解説)[。？]", title.strip()):
        issues.append("headline_flattened")

    hedge_pattern = r"(?:可能性(?:がある|があります)|考えられ(?:る|ます)|注視(?:したい|する|すべき)|様子を見(?:る|たい)|かもしれない)"
    hedge_count = len(re.findall(hedge_pattern, article))
    concrete_action = re.search(r"(?:限定|小さく|検証環境|PoC|比較(?:テスト|検証)|試(?:す|したい)|見送(?:る|り)|待(?:つ|ち)|導入を急がない|CI|回帰テスト|profil(?:ing|e)|プロファイリング|計測|ベンチマーク)", decision_text, re.I)
    generic_monitor = re.search(r"(?:注視|様子を見)", decision_text)
    if generic_monitor and not concrete_action:
        issues.append("action_collapsed_to_generic_monitoring")
    if hedge_count >= 5 and not concrete_action:
        issues.append("over_hedging_without_decision")

    claims = _classify_article_claims(parsed)
    if not concrete_action and claims["decision"] == 0:
        issues.append("decision_voice_missing")
    # 観察文がなくても、根拠付きAction・限定判断・見送り・比較判断はDecision Voice。
    if claims["observation"] == 0 and claims["interpretation"] == 0 and not (concrete_action or claims["decision"]):
        issues.append("no_editorial_observation")
    if len(re.findall(r"(?:ただ、ここは注意が必要です。|一方で、注意が必要です。)", article)) >= 2:
        issues.append("repeated_caveat_phrase")

    # 読み手への入口が説明文だけにならないかを軽く確認する。疑問符は必須にしない。
    intro = _article_opening_excerpt(article)
    if intro and not re.search(r"(?:なぜ|どこ|何が|課題|現場|原資料|一見|数字|変わ|面白|気にな|使|困|発表|公開|登場)", intro[:500]):
        issues.append("opening_hook_weak")

    ai_style = _ai_style_composite_signals(article)
    depth_style = _human_editorial_depth_signals(article)
    # Run121: known-template detector + over-explanation detector are complementary.
    # Either detector must be high-confidence; weak individual style quirks remain warnings-free.
    if ai_style.get("high") or depth_style.get("high"):
        issues.append("ai_style_composite_high")

    cross_style = _cross_article_naturalness_signals(article, peer_articles)
    if cross_style.get("high"):
        issues.append("cross_article_fingerprint_high")

    issues = list(dict.fromkeys(issues))
    return ("WEAK" if issues else "ACCEPTABLE", issues)


# Backward compatibility aliases. 正式な実装・Pipeline本体は *_gate 名を使用する。
validate_publication_readiness = validate_publication_readiness_gate
validate_human_appeal = validate_human_appeal_gate


# ==========================================
# Gate Funnel / Reason Code / 内部レビュー保存
# ==========================================
def _reason_code(message: str, gate: str) -> str:
    """既存Gateの自由文を、観測用の安定したReason Codeに写像する。

    判定条件や閾値は変えない。未知のメッセージも捨てず、既存Gateの分類内で
    最も保守的なコードを付与し、元メッセージは履歴にそのまま保存する。
    """
    text = (message or "").lower()
    if "high_risk_action_unsupported" in text:
        return REASON_CODE_HIGH_RISK_ACTION_UNSUPPORTED
    if "output_truncated" in text or "max_tokens" in text or "token_limit" in text:
        return REASON_CODE_MAX_TOKENS
    if "article_structure_incomplete" in text or "required heading missing" in text or "structure" in text:
        return REASON_CODE_STRUCTURE_MISSING
    if "primary_source_authority_insufficient" in text or "primary source" in text and "authority" in text:
        return REASON_CODE_PRIMARY_SOURCE_UNRESOLVED
    if "source_depth_insufficient" in text or "primary_evidence_insufficient" in text or "grounding failed" in text:
        return REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT
    if gate == "fact":
        if any(token in text for token in ("numeric", "number", "数値", "unit", "%")):
            return REASON_CODE_FACT_NUMERICAL_MISMATCH
        if any(token in text for token in ("actor", "author", "attribution", "publisher", "発表主体", "帰属", "entity relation")):
            return REASON_CODE_FACT_ACTOR_MISMATCH
        if "named fact" in text or "unsupported named" in text or "固有名" in text:
            return REASON_CODE_FACT_UNSUPPORTED_NAMED_FACT
        if any(token in text for token in ("limitation", "qualifier", "scope", "fresh", "final wording", "conditional")):
            return REASON_CODE_FACT_CONDITIONALITY_LOSS
        return REASON_CODE_FACT_UNSUPPORTED_CLAIM
    if gate == "editorial":
        if "unsupported personal experience" in text:
            return REASON_CODE_APPEAL_FABRICATED_EXPERIENCE
        return REASON_CODE_EDITORIAL_STRUCTURE_ERROR
    if gate == "publication":
        mapping = {
            "headline_overclaim": REASON_CODE_PUB_HEADLINE_OVERCLAIM,
            "intro_overclaim": REASON_CODE_PUB_INTRO_OVERCLAIM,
            "research_to_production_leap": REASON_CODE_PUB_UNSUPPORTED_CONCLUSION,
            "score_narrative_mismatch": REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH,
            "marketing_claim_adoption": REASON_CODE_PUB_UNSUPPORTED_CONCLUSION,
            "negative_evidence_omission": REASON_CODE_PUB_NEGATIVE_EVIDENCE_OMISSION,
            "primary_evidence_insufficient": REASON_CODE_PUB_SOURCE_SUFFICIENCY,
            "article_structure_needs_edit": REASON_CODE_STRUCTURE_MISSING,
        }
        return mapping.get(message, REASON_CODE_PUB_ACTION_EVIDENCE_MISMATCH)
    if gate == "human_appeal":
        mapping = {
            "over_hedging_without_decision": REASON_CODE_APPEAL_OVER_HEDGING,
            "action_collapsed_to_generic_monitoring": REASON_CODE_APPEAL_ACTION_COLLAPSE,
            "headline_flattened": REASON_CODE_APPEAL_TITLE_FLATTENING,
            "decision_voice_missing": REASON_CODE_APPEAL_DECISION_VOICE_LOSS,
            "fabricated_personal_experience": REASON_CODE_APPEAL_FABRICATED_EXPERIENCE,
            "ai_style_composite_high": REASON_CODE_APPEAL_AI_STYLE_COMPOSITE,
            "cross_article_fingerprint_high": REASON_CODE_APPEAL_CROSS_ARTICLE_FINGERPRINT,
            "human_appeal_materially_degraded_after_reedit": REASON_CODE_APPEAL_DECISION_VOICE_LOSS,
        }
        return mapping.get(message, REASON_CODE_APPEAL_DECISION_VOICE_LOSS)
    return REASON_CODE_FACT_UNSUPPORTED_CLAIM


def classify_gate_reason_severity(gate: str, message: str, reason_code: str = "") -> str:
    """Run 102のHARD / REVIEW / SOFT分類。

    Gateを緩めるためではなく、公開停止と改善提案を分離するための分類。
    Fact/Evidence/Decision矛盾は守り、文章美観だけのためのGemini Retryを止める。
    """
    text = (message or "").lower()
    code = reason_code or _reason_code(message, gate)
    if gate in {"fact", "evidence"}:
        return GATE_SEVERITY_HARD
    if gate == "publication":
        # headline/intro overclaimも読者誤認につながるため、修正されるまで公開しない。
        return GATE_SEVERITY_HARD
    if gate == "editorial":
        if "unsupported personal experience" in text:
            return GATE_SEVERITY_HARD
        # 本文の過半が箇条書きの状態は「美観」ではなく読解性・商品価値の問題。
        if "article too list-like" in text:
            return GATE_SEVERITY_REVIEW
        known_soft = (
            "mechanical ordinal structure", "repetitive ai-like sentence endings",
            "too many article headings", "repetitive fixed introduction",
            "missing observation or reservation", "mechanical three-reasons phrasing",
            "too many reader questions", "monotonous sentence endings", "japanese_polish:",
        )
        if any(token in text for token in known_soft):
            return GATE_SEVERITY_SOFT
        # 将来Editorial ruleが追加された時に、未知の重大欠陥を自動Soft化しないFail-safe。
        return GATE_SEVERITY_REVIEW
    if gate == "human_appeal":
        if code == REASON_CODE_APPEAL_FABRICATED_EXPERIENCE or "fabricated_personal_experience" in text:
            return GATE_SEVERITY_HARD
        if message in {"headline_flattened", "opening_hook_weak", "repeated_caveat_phrase"}:
            return GATE_SEVERITY_SOFT
        if message in {"ai_style_composite_high", "cross_article_fingerprint_high"} or code in {REASON_CODE_APPEAL_AI_STYLE_COMPOSITE, REASON_CODE_APPEAL_CROSS_ARTICLE_FINGERPRINT}:
            return GATE_SEVERITY_REVIEW
        if message in {
            "action_collapsed_to_generic_monitoring",
            "decision_voice_missing",
            "no_editorial_observation",
            "over_hedging_without_decision",
            "human_appeal_materially_degraded_after_reedit",
        } or code == REASON_CODE_APPEAL_DECISION_VOICE_LOSS:
            # 「何をすべきか」が消えた記事は獲得商品として弱い。Soft扱いして量産しない。
            return GATE_SEVERITY_REVIEW
        # 未知のHuman Appeal defectもまずReview。新ルール追加時の過剰通過を防ぐ。
        return GATE_SEVERITY_REVIEW
    return GATE_SEVERITY_HARD


def map_gate_reasons(gate: str, messages: list[str] | None) -> list[dict]:
    rows: list[dict] = []
    for message in (messages or []):
        code = _reason_code(message, gate)
        rows.append({
            "reason_code": code,
            "message": message,
            "gate": gate,
            "severity": classify_gate_reason_severity(gate, message, code),
        })
    return rows


def _infer_gate_from_reason_code(reason_code: str) -> str:
    code = reason_code or ""
    if code.startswith("FACT_") or code in {REASON_CODE_MAX_TOKENS, REASON_CODE_STRUCTURE_MISSING}:
        return "fact"
    if code in {
        REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT, REASON_CODE_PRIMARY_SOURCE_UNRESOLVED,
        REASON_CODE_TECHNICAL_CLAIMS_INSUFFICIENT, REASON_CODE_NUMERIC_CONDITIONS_INSUFFICIENT,
        REASON_CODE_FRESHNESS_REQUIRED_BUT_UNRESOLVED, REASON_CODE_HIGH_RISK_ACTION_UNSUPPORTED,
        REASON_CODE_EVIDENCE_GAP_DISCLOSURE_REQUIRED,
    }:
        return "evidence"
    if code.startswith("PUB_"):
        return "publication"
    if code == REASON_CODE_EDITORIAL_STRUCTURE_ERROR:
        return "editorial"
    if code.startswith("APPEAL_"):
        return "human_appeal"
    if code in {
        REASON_CODE_PENDING_RETRY, REASON_CODE_MODEL_UNAVAILABLE,
        REASON_CODE_DEEP_DIVE_RUN_BUDGET_EXHAUSTED, REASON_CODE_NOTION_PERSISTENCE_FAILED,
    }:
        return "operational"
    return "fact"


def normalize_gate_reason_rows(reason_rows: list[dict] | None) -> list[dict]:
    normalized: list[dict] = []
    for original in (reason_rows or []):
        row = dict(original)
        code = str(row.get("reason_code") or "")
        gate = str(row.get("gate") or _infer_gate_from_reason_code(code))
        row["gate"] = gate
        if not row.get("severity"):
            if gate == "operational":
                row["severity"] = GATE_SEVERITY_OPERATIONAL
            else:
                row["severity"] = classify_gate_reason_severity(gate, str(row.get("message") or ""), code)
        normalized.append(row)
    return normalized


def gate_reason_disposition(reason_rows: list[dict] | None) -> str:
    rows = normalize_gate_reason_rows(reason_rows)
    severities = {row.get("severity") for row in rows}
    if GATE_SEVERITY_HARD in severities:
        return GATE_DISPOSITION_BLOCK
    if GATE_SEVERITY_REVIEW in severities:
        return GATE_DISPOSITION_REVIEW
    if GATE_SEVERITY_SOFT in severities:
        return GATE_DISPOSITION_PASS_WITH_WARNINGS
    return GATE_DISPOSITION_PASS


def _reason_rows_by_severity(reason_rows: list[dict] | None, *severities: str) -> list[dict]:
    allowed = set(severities)
    return [row for row in normalize_gate_reason_rows(reason_rows) if row.get("severity") in allowed]


def _quality_warning_messages(reason_rows: list[dict] | None) -> list[str]:
    return [str(row.get("message", "")) for row in normalize_gate_reason_rows(reason_rows)
            if row.get("severity") == GATE_SEVERITY_SOFT and row.get("message")]


def finalize_retry_diagnostics(retry_diagnostics: dict | None, final_reason_codes: list[dict],
                              final_gate_result: str, final_article: str = "") -> dict:
    """初稿の起因と最終稿に残った理由を混同せずGate履歴へ残す。"""
    details = dict(retry_diagnostics or {})
    if not details:
        return details
    details["final_reason_codes"] = list(final_reason_codes)
    details["final_gate_result"] = final_gate_result
    details["retry_article"] = final_article
    details["retry_succeeded"] = bool(details.get("retry_attempted")) and final_gate_result == "READY"
    return details


NON_REPAIRABLE_RETRY_REASON_CODES = {
    REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT,
    REASON_CODE_PRIMARY_SOURCE_UNRESOLVED,
    REASON_CODE_TECHNICAL_CLAIMS_INSUFFICIENT,
    REASON_CODE_NUMERIC_CONDITIONS_INSUFFICIENT,
    REASON_CODE_FRESHNESS_REQUIRED_BUT_UNRESOLVED,
    REASON_CODE_HIGH_RISK_ACTION_UNSUPPORTED,
    REASON_CODE_PUB_SOURCE_SUFFICIENCY,
}


def should_attempt_dynamic_retry(reason_rows: list[dict], evidence_result: dict | None,
                                 candidate_origin: str = "new") -> tuple[bool, str]:
    """利益に近い修正だけにGemini Quality Retryを使う。

    SOFTだけなら公開可能なので0 API。Evidence不足は再作文で増えないので0 API。
    HARDの局所修正、またはDecision Voice等のREVIEWだけを最大1回修正する。
    """
    rows = list(reason_rows or [])
    if rows and gate_reason_disposition(rows) == GATE_DISPOSITION_PASS_WITH_WARNINGS:
        return False, "soft_quality_only"
    if candidate_origin == "pending_retry" and not PENDING_RETRY_REQUEST_BUDGET.can_request():
        return False, "pending_retry_budget_exhausted"
    evidence_result = evidence_result or {}
    if evidence_result.get("state") not in {None, "", EVIDENCE_SUFFICIENT}:
        return False, "evidence_not_sufficient"
    codes = {row.get("reason_code") for row in rows if row.get("reason_code")}
    if codes & NON_REPAIRABLE_RETRY_REASON_CODES:
        return False, "non_repairable_evidence_or_source_gap"
    if not rows:
        return False, "no_blocking_reason"
    return True, "repairable"


def build_dynamic_retry_instruction(reason_rows: list[dict]) -> tuple[str, list[str]]:
    """Reason Codeごとに局所修正を要求する。文字数ノルマやGate緩和は行わない。"""
    rules = {
        REASON_CODE_FACT_NUMERICAL_MISMATCH: ("数値と単位だけを一次情報の条件付き表現へ修正し、根拠がなければ削除してください。", "numbers"),
        REASON_CODE_FACT_CONDITIONALITY_LOSS: ("元資料の対象範囲・実験条件・制約を該当箇所へ復元してください。", "conditions"),
        REASON_CODE_FACT_ACTOR_MISMATCH: ("発表主体・著者・製品名の帰属だけを一次情報に合わせて修正してください。", "attribution"),
        REASON_CODE_FACT_UNSUPPORTED_NAMED_FACT: ("一次情報にない技術名・API・パッケージ名だけを削除または原資料の表記へ修正してください。", "named_facts"),
        REASON_CODE_FACT_UNSUPPORTED_CLAIM: ("一次情報にない主張だけを削除または根拠範囲へ弱めてください。", "claims"),
        REASON_CODE_PUB_HEADLINE_OVERCLAIM: ("タイトルだけを本文Evidenceの強度に合わせて修正してください。", "title"),
        REASON_CODE_PUB_INTRO_OVERCLAIM: ("導入部だけを一次情報の強度に合わせて修正してください。", "introduction"),
        REASON_CODE_PUB_UNSUPPORTED_CONCLUSION: ("結論とActionだけを一次情報が支える限定判断へ修正してください。", "conclusion_action"),
        REASON_CODE_PUB_ACTION_EVIDENCE_MISMATCH: ("Actionだけを根拠範囲へ修正し、限定検証・比較・見送りのいずれかを具体的に示してください。", "action"),
        REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH: ("Decision Scoreと矛盾する結論・緊急度表現だけを修正してください。", "conclusion"),
        REASON_CODE_PUB_NEGATIVE_EVIDENCE_OMISSION: ("一次情報にある制約・反証・未検証条件を該当箇所へ追加してください。", "limitations"),
        REASON_CODE_APPEAL_OVER_HEDGING: ("根拠付き判断を残し、不要な曖昧表現だけを減らしてください。", "voice"),
        REASON_CODE_APPEAL_ACTION_COLLAPSE: ("『注視』へ潰れたActionを、根拠付きの限定検証・比較・見送り判断へ戻してください。", "action"),
        REASON_CODE_APPEAL_TITLE_FLATTENING: ("Evidenceを超えない範囲でタイトルの引力だけを回復してください。", "title"),
        REASON_CODE_APPEAL_DECISION_VOICE_LOSS: ("架空体験や感情を足さず、原稿内の根拠に基づく筆者判断だけを復元してください。", "voice"),
        REASON_CODE_APPEAL_FABRICATED_EXPERIENCE: ("実際に経験していない現場体験・使用体験・感情を削除し、一次情報に基づく編集者の観察・判断へ書き換えてください。", "voice"),
        REASON_CODE_APPEAL_AI_STYLE_COMPOSITE: ("事実・数値・判断の意味は変えず、汎用的な接続句の反復、同型見出し、短文連打、説明の言い換え反復を崩してください。記事固有の焦点を1つ選び、人間の編集者が書いた自然なリズムへ再編集してください。新しい事実は追加しないでください。", "prose_style"),
        REASON_CODE_APPEAL_CROSS_ARTICLE_FINGERPRINT: ("同じRunの別記事と似た導入リズム・段落運び・判断の置き方を避け、この記事固有の一次情報に合う順序へ再編集してください。事実・数値・Decisionの意味は変えず、新しい事実は追加しないでください。", "cross_article_style"),
        REASON_CODE_EDITORIAL_STRUCTURE_ERROR: ("読みやすさを損なう構造だけを自然な文章へ直してください。文末単調が指摘された場合は語尾だけを機械的に置換せず、文の長短、主語の置き方、事実提示・判断・留保の順序を局所的に組み替えてリズムを変えてください。新しい事実は追加しないでください。", "structure"),
    }
    instructions, sections = [], []
    for row in reason_rows:
        code = row.get("reason_code", "")
        if code in {REASON_CODE_MAX_TOKENS, REASON_CODE_STRUCTURE_MISSING}:
            instructions.append("長文本文のセクションを内容固有のMarkdown見出し（##/###）で明確に区切り、最終判断が本文から読み取れる短縮完全版にしてください。『導入』『結論』『最終判断』などの固定見出し名は要求しません。前稿へ文章を継ぎ足さないでください。")
            sections.append("structure")
        elif code in rules:
            instruction, section = rules[code]
            instructions.append(f"{code}: {instruction}")
            sections.append(section)
    if not instructions:
        instructions.append("既存原稿の根拠付き判断を保ち、Quality Gateが示した該当箇所だけを修正してください。")
    # Retry itself must not re-introduce internal management vocabulary into the public article.
    instructions.append("ARTICLE本文には内部管理コード NOW / TRY / WATCH / WAIT / AVOID を絶対に出力せず、読者向けの自然な日本語判断文へ言い換えてください。")
    hard_retry = any(row.get("severity") == GATE_SEVERITY_HARD for row in normalize_gate_reason_rows(reason_rows))
    if hard_retry:
        # HARD retry has one job: repair factual/publication safety. Combining it with whole-article
        # compression caused new overclaims in real regression, so explicitly forbid broad rewriting.
        instructions.append("HARD修正では記事全体の短文化・全面再構成を同時に行わず、指摘された事実・条件・導入・結論など必要箇所だけを最小限修正してください。修正対象外のEvidence・数値・固有名詞・制約・比較・反証・Decisionの意味と文章構造はできるだけ保持してください。")
        instructions.append("Retry中に『安全性が担保される』『保証される』『完全に防げる』『必ず改善する』等、一次情報より強い保証・一般化を新たに作らないでください。根拠にない時間・金額・性能・業界標準も追加しないでください。")
    elif any((row.get("reason_code") or "") in {REASON_CODE_APPEAL_AI_STYLE_COMPOSITE, REASON_CODE_APPEAL_CROSS_ARTICLE_FINGERPRINT} for row in reason_rows):
        instructions.append("AI臭・量産テンプレ感の修正では見出し名・段落分割・文章リズムを変更してよい。必要なら情報提示順も変更してよい。ただし一次情報、数値、固有名詞、Decisionの意味、制約条件は変更・追加しないでください。文字数合わせではなく、重複説明を減らして長く感じさせないことを優先してください。『ここで重要なのは』『ポイントは』『つまり』『注目すべきは』等の常套句へ置き換えるだけの修正は禁止です。1〜3箇所の自然な読者接続は残してよいが、呼びかけ・相づち・疑問形を連打せず、記事固有の疑問や場面から自然に次段落へつないでください。")
    else:
        instructions.append("修正対象外の一次情報・数値・固有名詞は不用意に書き換えないでください。文字数を目標にせず、同じ事実の言い換え、不要な実装列挙、一般論、完全なコードブロック、実装チュートリアルなど読者の判断に不要な重複だけを削除・統合してください。Evidence・数値・制約・比較・反証・Decisionは短文化のために削らず、非エンジニアでも流れを追える説明順序を優先してください。")
    return "\n".join(dict.fromkeys(instructions)), list(dict.fromkeys(sections))



def _remove_sentences_with_token(text: str, token: str) -> tuple[str, int]:
    """Remove only prose sentences containing an unsupported token.

    Headings are never removed. This is deliberately subtractive: it never invents replacement
    facts, numbers, products, dates, performance, or comparisons.
    """
    if not text or not token:
        return text or "", 0
    removed = 0
    out_lines: list[str] = []
    for line in (text or "").splitlines():
        if line.lstrip().startswith("#") or token not in line:
            out_lines.append(line)
            continue
        parts = re.split(r"(?<=[。！？!?])", line)
        kept = []
        for part in parts:
            if token in part:
                removed += 1
            else:
                kept.append(part)
        cleaned = "".join(kept).strip()
        if cleaned:
            out_lines.append(cleaned)
        elif line.strip() == "":
            out_lines.append("")
    return "\n".join(out_lines), removed


def _apply_deterministic_publication_rescue(parsed: dict, reason_rows: list[dict]) -> tuple[dict, list[str]]:
    """0-API, subtractive rescue for a narrow set of already-diagnosed article defects.

    It may delete unsupported hype, an unsupported numeric/named-fact sentence, or fabricated
    experience. It may not add facts or evidence. If a risky token is in the title or deleting it
    would erase the concrete Action, the rescue declines and the normal fail-closed path remains.
    """
    rescued = dict(parsed or {})
    article = str(rescued.get("note_draft") or "")
    title = str(rescued.get("title_text") or "")
    action = str(rescued.get("action_text") or "")
    changes: list[str] = []
    removed_sentences = 0
    important_numeric_removed = False

    hype_replacements = {
        "唯一": "", "一択": "", "必須": "", "デファクトスタンダード": "選択肢",
        "圧倒的": "", "劇的": "", "革命的": "", "完全に解決": "改善",
    }
    for row in reason_rows or []:
        code = row.get("reason_code") or ""
        message = str(row.get("message") or "")
        if code == REASON_CODE_FACT_UNSUPPORTED_CLAIM:
            matched = False
            for bad, replacement in hype_replacements.items():
                if bad in message and (bad in article or bad in title):
                    if bad == "唯一":
                        # Remove the grammatical unit as well; deleting only 「唯一」 leaves
                        # malformed prose such as 「、の『インフラ』」. This remains subtractive.
                        article = article.replace("唯一の", "").replace("唯一", replacement)
                        title = title.replace("唯一の", "").replace("唯一", replacement)
                    else:
                        article = article.replace(bad, replacement)
                        title = title.replace(bad, replacement)
                    changes.append(f"remove_unsupported_hype:{bad}")
                    matched = True
            if not matched:
                # Generic unsupported claims are too broad for deterministic rewriting.
                continue
        elif code in {REASON_CODE_FACT_NUMERICAL_MISMATCH, REASON_CODE_FACT_UNSUPPORTED_NAMED_FACT}:
            token = message.rsplit(":", 1)[-1].strip()
            if not token or token in title:
                continue
            new_article, removed = _remove_sentences_with_token(article, token)
            if removed:
                article = new_article
                removed_sentences += removed
                if code == REASON_CODE_FACT_NUMERICAL_MISMATCH and re.search(r"\d", token):
                    important_numeric_removed = True
                changes.append(f"remove_unsupported_sentence:{token}")
                if token in action:
                    derived_action = _extract_any_markdown_section(article, _display_heading_aliases("decision"))
                    if _is_meaningful_field(derived_action) and token not in derived_action:
                        action = derived_action
                    else:
                        # Do not publish without a concrete Action merely to rescue a draft.
                        return dict(parsed or {}), []
        elif code == REASON_CODE_APPEAL_FABRICATED_EXPERIENCE:
            for snippet in _find_fabricated_personal_experience(article):
                article, removed = _remove_sentences_with_token(article, snippet)
                if removed:
                    removed_sentences += removed
                    changes.append("remove_fabricated_experience")

    if not changes:
        return dict(parsed or {}), []
    article = re.sub(r"[ \t]{2,}", " ", article)
    article = re.sub(r"\n{3,}", "\n\n", article).strip()
    title = re.sub(r"\s{2,}", " ", title).strip()
    title = re.sub(r"^[、,:：\-\s]+", "", title)
    if title and not re.search(r"[。？]$", title):
        title += "。"
    if not _is_meaningful_field(action):
        return dict(parsed or {}), []
    rescued["note_draft"] = article
    rescued["title_text"] = title
    rescued["action_text"] = action
    rescued["_rescue_loss"] = {
        "removed_sentences": removed_sentences,
        "important_numeric_removed": important_numeric_removed,
        "loss_exceeded": bool(removed_sentences >= 3 or (important_numeric_removed and removed_sentences != 1)),
    }
    return rescued, list(dict.fromkeys(changes))


def _publication_rescue_can_be_ready(parsed: dict, source_context: str, source: str,
                                     evidence_metadata: dict, source_info: dict, freshness: dict,
                                     output_truncated: bool = False, peer_articles: list[dict] | None = None) -> tuple[bool, dict]:
    fact_ok, fact_failures = validate_fact_gate(
        parsed, "publication-rescue", source_context=source_context, source=source,
        evidence_metadata=evidence_metadata, source_info=source_info,
        freshness=freshness, output_truncated=output_truncated,
    )
    editorial_ok, editorial_warnings = validate_editorial_gate(parsed, "publication-rescue")
    publication_state, publication_issues = validate_publication_readiness_gate(parsed, source_context, source_info)
    human_state, human_issues = validate_human_appeal_gate(parsed, peer_articles)
    reason_rows = (map_gate_reasons("fact", fact_failures)
                   + map_gate_reasons("editorial", editorial_warnings)
                   + map_gate_reasons("publication", publication_issues)
                   + map_gate_reasons("human_appeal", human_issues))
    disposition = gate_reason_disposition(reason_rows)
    ready = disposition in {GATE_DISPOSITION_PASS, GATE_DISPOSITION_PASS_WITH_WARNINGS}
    return ready, {
        "fact_ok": fact_ok, "fact_failures": fact_failures,
        "editorial_ok": editorial_ok, "editorial_warnings": editorial_warnings,
        "publication_state": publication_state, "publication_issues": publication_issues,
        "human_state": human_state, "human_issues": human_issues,
        "reason_rows": reason_rows, "disposition": disposition,
    }


class DeepDiveGateFunnel:
    """一回の本番実行におけるDeep Diveの脱落経路を集計する。"""
    COUNTERS = (
        "deep_dive_candidates_attempted", "generation_completed", "generation_failed",
        "pending_retry_candidates_attempted", "new_deep_dive_candidates_attempted", "total_deep_dive_candidates_processed",
        "generation_api_completed", "article_parsed", "quality_evaluation_completed",
        "evidence_sufficient", "evidence_supplement_required", "evidence_supplement_success",
        "evidence_insufficient", "deep_dive_generation_called", "deep_dive_calls_avoided",
        "retry_attempted", "retry_success", "retry_failed",
        "retry_triggered_hard", "retry_triggered_review", "retry_avoided_soft_only",
        "deterministic_rescue_attempted", "deterministic_rescue_success",
        "retry_skipped_nonrepairable", "retry_skipped_budget",
        "max_tokens_failed", "structure_failed", "primary_evidence_failed",
        "fact_gate_failed", "editorial_gate_failed", "editorial_warning",
        "publication_readiness_review", "publication_readiness_failed",
        "human_appeal_warning", "human_appeal_review",
        "hard_blocked", "review_required", "soft_warning_ready",
        "pending_retry", "ready_count", "notion_persistence_failed",
    )

    def __init__(self):
        self.counters = {key: 0 for key in self.COUNTERS}
        self.records: list[dict] = []

    def incr(self, key: str, amount: int = 1) -> None:
        if key not in self.counters:
            raise KeyError(f"Unknown funnel counter: {key}")
        self.counters[key] += amount

    def record(self, record: dict) -> None:
        self.records.append(record)
        self.incr("deep_dive_candidates_attempted")
        self.incr("total_deep_dive_candidates_processed")
        self.incr("pending_retry_candidates_attempted" if record.get("candidate_origin") == "pending_retry" else "new_deep_dive_candidates_attempted")
        evidence_state = record.get("evidence_sufficiency")
        initial_evidence_state = record.get("evidence_initial_sufficiency", evidence_state)
        if evidence_state == EVIDENCE_SUFFICIENT:
            self.incr("evidence_sufficient")
        elif evidence_state == EVIDENCE_INSUFFICIENT:
            self.incr("evidence_insufficient")
            self.incr("deep_dive_calls_avoided")
        if initial_evidence_state == EVIDENCE_SUPPLEMENT_REQUIRED:
            self.incr("evidence_supplement_required")
        if record.get("evidence_supplement_success"):
            self.incr("evidence_supplement_success")
        trigger_rows = (record.get("retry_diagnostics") or {}).get("trigger_reason_codes", []) or []
        if record.get("retry_attempted"):
            self.incr("retry_attempted")
            trigger_severities = {row.get("severity") for row in trigger_rows}
            if GATE_SEVERITY_HARD in trigger_severities:
                self.incr("retry_triggered_hard")
            if GATE_SEVERITY_REVIEW in trigger_severities:
                self.incr("retry_triggered_review")
        if (record.get("retry_diagnostics") or {}).get("retry_skipped_reason") == "soft_quality_only":
            self.incr("retry_avoided_soft_only")
        if record.get("retry_succeeded"):
            self.incr("retry_success")
        elif record.get("retry_attempted"):
            self.incr("retry_failed")
        generation = record.get("generation_status")
        if generation == "completed":
            self.incr("generation_completed")
        elif generation in {"failed", "pending_retry"}:
            self.incr("generation_failed")
        codes = {row.get("reason_code") for row in record.get("reason_codes", [])}
        if REASON_CODE_MAX_TOKENS in codes or record.get("any_generation_truncated"):
            self.incr("max_tokens_failed")
        if REASON_CODE_STRUCTURE_MISSING in codes:
            self.incr("structure_failed")
        if REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT in codes:
            self.incr("primary_evidence_failed")
        if record.get("fact_gate") == GATE_STATUS_FAIL:
            self.incr("fact_gate_failed")
        if record.get("editorial_gate") == GATE_STATUS_WARNING:
            # backward-compatible counter is retained, but user-facing wording is Warning.
            self.incr("editorial_gate_failed")
            self.incr("editorial_warning")
        if record.get("publication_readiness_gate") == GATE_STATUS_REVIEW:
            self.incr("publication_readiness_review")
        if record.get("publication_readiness_gate") == GATE_STATUS_FAIL:
            self.incr("publication_readiness_failed")
        if record.get("human_appeal_gate") == GATE_STATUS_WARNING:
            self.incr("human_appeal_warning")
        if record.get("human_appeal_gate") == GATE_STATUS_REVIEW:
            self.incr("human_appeal_review")
        severities = {row.get("severity") for row in record.get("reason_codes", [])}
        if record.get("final_status") != ARTICLE_STATUS_READY and GATE_SEVERITY_HARD in severities:
            self.incr("hard_blocked")
        if record.get("final_status") == ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW:
            self.incr("review_required")
        if record.get("final_status") == CONTENT_STATUS_PENDING_RETRY:
            self.incr("pending_retry")
        if record.get("final_status") == ARTICLE_STATUS_READY:
            self.incr("ready_count")
            if GATE_SEVERITY_SOFT in severities and not ({GATE_SEVERITY_HARD, GATE_SEVERITY_REVIEW} & severities):
                self.incr("soft_warning_ready")
        if record.get("final_status") == CONTENT_STATUS_PERSISTENCE_FAILED or REASON_CODE_NOTION_PERSISTENCE_FAILED in codes:
            self.incr("notion_persistence_failed")

    def render_text(self) -> str:
        c = self.counters
        candidate_den = c["deep_dive_candidates_attempted"]
        generated_den = c["generation_completed"]
        candidate_yield = (100.0 * c["ready_count"] / candidate_den) if candidate_den else 0.0
        generated_yield = (100.0 * c["ready_count"] / generated_den) if generated_den else 0.0
        return "\n".join([
            "Deep Dive Funnel", "",
            f"Candidates Attempted: {c['deep_dive_candidates_attempted']}",
            f"Pending Retry Candidates Attempted: {c['pending_retry_candidates_attempted']}",
            f"New Deep Dive Candidates Attempted: {c['new_deep_dive_candidates_attempted']}",
            f"Total Deep Dive Candidates Processed: {c['total_deep_dive_candidates_processed']}",
            f"Generation Completed: {c['generation_completed']}",
            f"Generation Failed: {c['generation_failed']}", "",
            f"Generation API Completed: {c['generation_api_completed']}",
            f"Article Parsed: {c['article_parsed']}",
            f"Quality Evaluation Completed: {c['quality_evaluation_completed']}",
            f"Evidence Sufficient: {c['evidence_sufficient']}",
            f"Evidence Supplement Required: {c['evidence_supplement_required']}",
            f"Evidence Supplement Success: {c['evidence_supplement_success']}",
            f"Evidence Insufficient: {c['evidence_insufficient']}",
            f"Deep Dive Generation Called: {c['deep_dive_generation_called']}",
            f"Deep Dive Calls Avoided by Evidence Gate: {c['deep_dive_calls_avoided']}",
            f"Dynamic Retry Attempted: {c['retry_attempted']}",
            f"Dynamic Retry Success: {c['retry_success']}",
            f"Dynamic Retry Failed: {c['retry_failed']}",
            f"Retry Triggered by HARD: {c['retry_triggered_hard']}",
            f"Retry Triggered by REVIEW: {c['retry_triggered_review']}",
            f"Retry Avoided (SOFT only): {c['retry_avoided_soft_only']}", "",
            f"Deterministic Rescue Attempted: {c['deterministic_rescue_attempted']}",
            f"Deterministic Rescue Success: {c['deterministic_rescue_success']}",
            f"Dynamic Retry Skipped (Non-repairable): {c['retry_skipped_nonrepairable']}",
            f"Dynamic Retry Skipped (Budget): {c['retry_skipped_budget']}", "",
            f"MAX_TOKENS: {c['max_tokens_failed']}",
            f"Structure Failed: {c['structure_failed']}",
            f"Primary Evidence Failed: {c['primary_evidence_failed']}",
            f"Fact Gate Failed: {c['fact_gate_failed']}",
            f"Editorial Warning: {c['editorial_warning']}",
            f"Publication Readiness Review: {c['publication_readiness_review']}",
            f"Publication Readiness Failed: {c['publication_readiness_failed']}",
            f"Human Appeal Warning: {c['human_appeal_warning']}",
            f"Human Appeal Review: {c['human_appeal_review']}",
            f"Hard Blocked: {c['hard_blocked']}",
            f"Needs Editorial Review: {c['review_required']}",
            f"Ready with SOFT Warnings: {c['soft_warning_ready']}",
            f"Pending Retry: {c['pending_retry']}", "",
            f"Notion Persistence Failed: {c['notion_persistence_failed']}", "",
            f"Ready: {c['ready_count']}",
            f"Candidate Publish Yield: {c['ready_count']}/{candidate_den} ({candidate_yield:.1f}%)",
            f"Generated Publish Yield: {c['ready_count']}/{generated_den} ({generated_yield:.1f}%)",
        ])

    def render_ready_zero_summary(self) -> str:
        c = self.counters
        reason_counts: dict[str, int] = {}
        for record in self.records:
            for row in record.get("reason_codes", []):
                code = row.get("reason_code", "")
                if code:
                    reason_counts[code] = reason_counts.get(code, 0) + 1
        # Evidence不足は個別Reason Codeを優先表示する。PRIMARY_EVIDENCE_INSUFFICIENT
        # だけに丸めず、technical claims不足等の実際の停止理由を運用者へ出す。
        evidence_reason_codes = {
            REASON_CODE_PRIMARY_SOURCE_UNRESOLVED,
            REASON_CODE_TECHNICAL_CLAIMS_INSUFFICIENT,
            REASON_CODE_NUMERIC_CONDITIONS_INSUFFICIENT,
            REASON_CODE_FRESHNESS_REQUIRED_BUT_UNRESOLVED,
            REASON_CODE_HIGH_RISK_ACTION_UNSUPPORTED,
            REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT,
        }
        causes = [
            (code, count) for code, count in reason_counts.items() if code in evidence_reason_codes
        ] + [
            ("Publication Readiness Review", c["publication_readiness_review"]),
            ("Publication Readiness Failed", c["publication_readiness_failed"]),
            ("Fact Gate Failed", c["fact_gate_failed"]),
            ("MAX_TOKENS", c["max_tokens_failed"]),
            ("Primary Evidence Failed", c["primary_evidence_failed"]),
            ("Human Appeal Review", c["human_appeal_review"]),
            ("Pending Retry", c["pending_retry"]),
            ("Notion Persistence Failed", c["notion_persistence_failed"]),
        ]
        ranked = sorted(((label, count) for label, count in causes if count), key=lambda item: (-item[1], item[0]))
        lines = ["READY ARTICLES: 0", "", "Top Failure Causes:"]
        lines += [f"{idx}. {label}: {count}" for idx, (label, count) in enumerate(ranked[:3], start=1)] or ["None recorded"]
        lines += ["", f"Review Candidates Saved: {sum(1 for row in self.records if row.get('final_status') == ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW)}"]
        return "\n".join(lines)

    def render_telegram_summary(self) -> str:
        c = self.counters
        candidate_den = c["deep_dive_candidates_attempted"]
        generated_den = c["generation_completed"]
        candidate_yield = (100.0 * c["ready_count"] / candidate_den) if candidate_den else 0.0
        generated_yield = (100.0 * c["ready_count"] / generated_den) if generated_den else 0.0
        top_gate = max(
            [("Publication Readiness", c["publication_readiness_review"] + c["publication_readiness_failed"]),
             ("Fact Gate", c["fact_gate_failed"]),
             ("Human Appeal", c["human_appeal_review"]),
             ("MAX_TOKENS", c["max_tokens_failed"])], key=lambda item: item[1],
        )[0]
        review_saved = sum(1 for row in self.records if row.get("final_status") == ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW)
        return "\n".join([
            f"Deep Dive Attempted: {c['deep_dive_candidates_attempted']}",
            f"Ready: {c['ready_count']}",
            f"Needs Editorial Review: {review_saved}",
            f"Quality Failed: {c['fact_gate_failed'] + c['primary_evidence_failed']}",
            f"Pending Retry: {c['pending_retry']}",
            f"Candidate Publish Yield: {candidate_yield:.1f}%",
            f"Generated Publish Yield: {generated_yield:.1f}%", "",
            f"Retry Avoided (SOFT only): {c['retry_avoided_soft_only']}",
            f"Deep Dive Calls Avoided: {c['deep_dive_calls_avoided']}",
            f"Top Gate: {top_gate}",
            f"Review Candidates Saved: {review_saved}",
        ])


DEEP_DIVE_GATE_FUNNEL: DeepDiveGateFunnel | None = None


def reset_deep_dive_gate_funnel() -> DeepDiveGateFunnel:
    global DEEP_DIVE_GATE_FUNNEL
    DEEP_DIVE_GATE_FUNNEL = DeepDiveGateFunnel()
    return DEEP_DIVE_GATE_FUNNEL


def _active_gate_funnel(persist_results: bool) -> DeepDiveGateFunnel | None:
    return DEEP_DIVE_GATE_FUNNEL if persist_results else None


def build_candidate_gate_record(candidate_rank: int, repo_name: str, source_url: str,
                                decision_score: int | None, generation_status: str,
                                fact_gate: str = GATE_STATUS_NOT_RUN,
                                editorial_gate: str = GATE_STATUS_NOT_RUN,
                                publication_readiness_gate: str = GATE_STATUS_NOT_RUN,
                                human_appeal_gate: str = GATE_STATUS_NOT_RUN,
                                reason_codes: list[dict] | None = None,
                                final_status: str = "", article_saved: bool = False,
                                evidence_result: dict | None = None,
                                deep_dive_generation_called: bool = False,
                                retry_diagnostics: dict | None = None,
                                candidate_origin: str = "new",
                                source: str = "Unknown", generation_request_count: int = 0) -> dict:
    reasons = normalize_gate_reason_rows(reason_codes)
    first = reasons[0] if reasons else {}
    return {
        "candidate_rank": candidate_rank,
        "name": repo_name,
        "url": source_url,
        "source": source,
        "generation_request_count": max(0, int(generation_request_count or 0)),
        "decision_score": decision_score,
        "generation_status": generation_status,
        "fact_gate": fact_gate,
        "editorial_gate": editorial_gate,
        "publication_readiness_gate": publication_readiness_gate,
        "human_appeal_gate": human_appeal_gate,
        "final_status": final_status,
        "reason_code": first.get("reason_code", ""),
        "reason": first.get("message", ""),
        "reason_codes": reasons,
        "gate_disposition": gate_reason_disposition(reasons),
        "hard_reason_count": sum(1 for row in reasons if row.get("severity") == GATE_SEVERITY_HARD),
        "review_reason_count": sum(1 for row in reasons if row.get("severity") == GATE_SEVERITY_REVIEW),
        "soft_warning_count": sum(1 for row in reasons if row.get("severity") == GATE_SEVERITY_SOFT),
        "article_saved": article_saved,
        "evidence_sufficiency": (evidence_result or {}).get("state", ""),
        "evidence_initial_sufficiency": (evidence_result or {}).get("initial_state", (evidence_result or {}).get("state", "")),
        "evidence_supplement_attempted": bool((evidence_result or {}).get("supplement_attempted")),
        "evidence_supplement_success": bool((evidence_result or {}).get("supplement_success")),
        "evidence_documents_checked": (evidence_result or {}).get("documents_checked", 0),
        "evidence_checks": (evidence_result or {}).get("checks", {}),
        "decision_scope_safe": (evidence_result or {}).get("decision_scope_safe"),
        "action_risk_tier": (evidence_result or {}).get("action_risk_tier", ""),
        "action_supported_at_current_tier": (evidence_result or {}).get("action_supported_at_current_tier"),
        "limitations_disclosed": (evidence_result or {}).get("limitations_disclosed"),
        "freshness_scope_limited": (evidence_result or {}).get("freshness_scope_limited"),
        "evidence_gap_disclosed": (evidence_result or {}).get("evidence_gap_disclosed"),
        "deep_dive_generation_called": deep_dive_generation_called,
        "retry_diagnostics": retry_diagnostics or {},
        "retry_attempted": bool((retry_diagnostics or {}).get("retry_attempted")),
        "retry_succeeded": bool((retry_diagnostics or {}).get("retry_succeeded")),
        "dynamic_retry_reason_codes": (retry_diagnostics or {}).get("trigger_reason_codes", []),
        "candidate_origin": candidate_origin,
        "recorded_at": _analyzed_at_now_iso(),
    }


def _internal_article_path(directory: str, repo_name: str, source_url: str) -> str:
    safe_name = _sanitize_filename(repo_name or "untitled")
    fingerprint = hashlib.sha256((source_url or repo_name or "unknown").encode("utf-8")).hexdigest()[:10]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return os.path.join(directory, f"{stamp}_{safe_name}_{fingerprint}.json")


def _save_json_private(directory: str, repo_name: str, source_url: str, payload: dict) -> str | None:
    try:
        os.makedirs(directory, exist_ok=True)
        path = _internal_article_path(directory, repo_name, source_url)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        logger.info("[PRIVATE REVIEW SAVED] %s", path)
        return path
    except Exception as exc:
        logger.error("[PRIVATE REVIEW SAVE FAILED] %s: %s", repo_name, exc)
        return None


def build_internal_article_record(repo: dict, parsed: dict | None, gate_record: dict,
                                  source_info: dict | None, failure_reason: str) -> dict:
    parsed = parsed or {}
    article = parsed.get("note_draft", "")
    return {
        "pipeline_status": gate_record.get("final_status"),
        "failed_gate": next((name for name, state in (
            ("Fact", gate_record.get("fact_gate")),
            ("Publication Readiness", gate_record.get("publication_readiness_gate")),
            ("Human Appeal", gate_record.get("human_appeal_gate")),
        ) if state in {GATE_STATUS_FAIL, GATE_STATUS_REVIEW}), ""),
        "gate_history": gate_record,
        "failure_reason": failure_reason,
        "article": article,
        "title": parsed.get("title_text", ""),
        "introduction": _extract_any_markdown_section(article, _display_heading_aliases("intro")),
        "conclusion": _extract_any_markdown_section(article, _display_heading_aliases("conclusion")),
        "action": parsed.get("action_text", ""),
        "decision_score": parsed.get("score"),
        "why_not": parsed.get("why_not_important_text", ""),
        "primary_evidence": {
            "primary_url": (source_info or {}).get("primary_url", repo.get("url")),
            "evidence_urls": (source_info or {}).get("evidence_urls", []),
            "metadata": (source_info or {}).get("evidence_metadata", {}),
            "verification_context_length": (source_info or {}).get("verification_context_length", 0),
        },
        "candidate_rank": gate_record.get("candidate_rank"),
        "source_url": repo.get("url"),
        "generated_at": _analyzed_at_now_iso(),
    }


def save_needs_editorial_review_article(repo: dict, parsed: dict, gate_record: dict,
                                        source_info: dict, failure_reason: str) -> str | None:
    record = build_internal_article_record(repo, parsed, gate_record, source_info, failure_reason)
    path = _save_json_private(REVIEW_CANDIDATES_DIR, repo.get("nameWithOwner", "untitled"), repo.get("url", ""), record)
    if path:
        markdown_path = os.path.splitext(path)[0] + ".md"
        try:
            with open(markdown_path, "w", encoding="utf-8") as handle:
                handle.write(build_external_review_markdown(record))
            logger.info("[EXTERNAL REVIEW MARKDOWN SAVED] %s", markdown_path)
        except Exception as exc:
            logger.error("[EXTERNAL REVIEW MARKDOWN SAVE FAILED] %s: %s", repo.get("nameWithOwner"), exc)
    return path


def save_quality_failed_article(repo: dict, parsed: dict | None, gate_record: dict,
                                source_info: dict | None, failure_reason: str,
                                audit_snapshots: dict | None = None) -> str | None:
    path = _save_json_private(
        QUALITY_FAILURES_DIR, repo.get("nameWithOwner", "untitled"), repo.get("url", ""),
        build_internal_article_record(repo, parsed, gate_record, source_info, failure_reason),
    )
    save_article_audit_package(
        repo, "QUALITY_FAILED", parsed, source_info, gate_record, failure_reason,
        snapshots=audit_snapshots or {},
    )
    return path


def reset_article_audit_for_production_run() -> None:
    """本番Artifactを1 Run単位に隔離し、同梱済み/前Run/テスト残骸の混入を防ぐ。"""
    import shutil
    root = Path(ARTICLE_AUDIT_DIR)
    try:
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)
        logger.info("[ARTICLE AUDIT RESET] clean run directory: %s", root)
    except Exception as exc:
        # Human auditの完全性が壊れた状態で継続すると、Ready件数を誤認する。
        raise RuntimeError(f"Article Audit初期化に失敗しました: {exc}") from exc


def _article_audit_key(repo: dict) -> str:
    name = repo.get("nameWithOwner") or "untitled"
    url = repo.get("url") or name
    fingerprint = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    return f"{_sanitize_filename(name)}_{fingerprint}"


def _write_article_audit_markdown(path: str, article: str, metadata: dict | None = None) -> str | None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        meta = metadata or {}
        lines = ["# Article Audit", ""]
        for label, key in (
            ("Status", "status"), ("Stage", "stage"), ("Source", "source"),
            ("Decision Score", "decision_score"), ("Quality Notes", "quality_notes"),
            ("Failure Reason", "failure_reason"),
        ):
            value = meta.get(key)
            if value not in (None, ""):
                lines.extend([f"## {label}", str(value), ""])
        evidence_urls = meta.get("evidence_urls") or []
        if evidence_urls:
            lines.extend(["## Primary Evidence URLs", *[f"- {u}" for u in evidence_urls], ""])
        reader = _reader_experience_signals(article or "")
        lines.extend([
            "## Reader Experience",
            f"- Accessibility: {reader.get('accessibility')}",
            f"- Curiosity Pull: {reader.get('curiosity_pull')}",
            f"- Reader Enjoyment: {reader.get('reader_enjoyment')}",
            f"- Return Pull: {reader.get('return_pull')}",
            f"- Narrative Pull: {reader.get('narrative_pull')}",
            f"- Article-Specific Angle: {reader.get('article_specific_angle')}",
            f"- Everyday Bridge: {reader.get('everyday_bridge')}",
            f"- Plain-Language Bridge: {reader.get('plain_language_bridge')}",
            f"- Jargon Translation: {reader.get('jargon_translation')}",
            f"- Non-Engineer Core Clarity: {reader.get('non_engineer_core_clarity')}",
            f"- Conversational Warmth: {reader.get('conversational_warmth')}",
            f"- Conversational Marker Count: {reader.get('conversational_marker_count')}",
            f"- Reader Proximity: {reader.get('reader_proximity')}",
            f"- Reader Delight: {reader.get('reader_delight')}",
            f"- Narrative Understanding Progression: {reader.get('narrative_understanding_progression')}",
            f"- Warm Hook Cold Body: {reader.get('warm_hook_cold_body')}",
            f"- Analogy Substance Thin: {reader.get('analogy_substance_thin')}",
            f"- Reader Proximity Moment Count: {reader.get('reader_proximity_moment_count')}",
            f"- Information Budget: {reader.get('information_budget')}",
            f"- Opening Non-Engineer Access: {reader.get('opening_non_engineer_access')}",
            f"- Opening Technical Terms / 1000 chars: {reader.get('opening_technical_terms_per_1000_chars')}",
            f"- Implementation Detail Load: {reader.get('implementation_detail_load')}",
            f"- Implementation Identifier Count: {reader.get('implementation_identifier_count')}",
            f"- Reader Temperature Rhythm: {reader.get('reader_temperature_rhythm')}",
            f"- Article Character Count: {reader.get('article_char_count')}",
            f"- Reader Proximity / 1000 chars: {reader.get('reader_proximity_per_1000_chars')}",
            f"- Headline Pull: {reader.get('headline_pull')}",
            f"- News Relevance: {reader.get('news_relevance')}",
            f"- Analogy Used: {reader.get('analogy_used')}",
            f"- Analogy Necessary: {reader.get('analogy_necessary')}",
            f"- Unexplained Jargon: {', '.join(reader.get('unexplained_jargon') or []) or 'None'}",
            "",
        ])
        lines.extend(["## Article", article or "（本文なし）", ""])
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
        logger.info("[ARTICLE AUDIT SAVED] %s", path)
        return path
    except Exception as exc:
        logger.error("[ARTICLE AUDIT SAVE FAILED] %s", exc)
        return None


def save_article_audit_package(repo: dict, status: str, parsed: dict | None,
                               source_info: dict | None = None, gate_record: dict | None = None,
                               failure_reason: str = "", snapshots: dict | None = None,
                               clean_manuscript: str = "", eyecatch_path: str = "") -> list[str]:
    """Private Artifact用の記事監査パッケージ。追加APIなしで既存生成稿を書き出す。"""
    if not repo:
        return []
    status_slug = _sanitize_filename((status or "unknown").lower())
    base = os.path.join(ARTICLE_AUDIT_DIR, "articles", status_slug, _article_audit_key(repo))
    parsed = parsed or {}
    snapshots = snapshots or {}
    evidence_urls = list((source_info or {}).get("evidence_urls") or [])
    primary = (source_info or {}).get("primary_url")
    if primary and primary not in evidence_urls:
        evidence_urls.insert(0, primary)
    meta = {
        "status": status,
        "source": repo.get("source", ""),
        "decision_score": parsed.get("score"),
        "quality_notes": failure_reason if status == "READY" else "",
        "failure_reason": "" if status == "READY" else failure_reason,
        "evidence_urls": evidence_urls,
    }
    saved: list[str] = []
    # Readyは最終公開稿だけで十分。Quality Failedは原因切り分けのため最大3段階を残す。
    if status == "READY":
        final_article = clean_manuscript or parsed.get("note_draft", "")
        path = _write_article_audit_markdown(os.path.join(base, "final.md"), final_article, {**meta, "stage": "final"})
        if path: saved.append(path)
    elif status == "QUALITY_FAILED":
        for stage, filename in (("generated_original", "generated_original.md"), ("after_quality_retry", "after_quality_retry.md")):
            article = snapshots.get(stage, "")
            if article:
                path = _write_article_audit_markdown(os.path.join(base, filename), article, {**meta, "stage": stage})
                if path: saved.append(path)
        final_article = snapshots.get("final_after_rescue", "") or parsed.get("note_draft", "")
        path = _write_article_audit_markdown(os.path.join(base, "final_after_rescue.md"), final_article, {**meta, "stage": "final_after_rescue"})
        if path: saved.append(path)
    else:
        final_article = parsed.get("note_draft", "") or snapshots.get("after_quality_retry", "") or snapshots.get("generated_original", "")
        path = _write_article_audit_markdown(os.path.join(base, "current.md"), final_article, {**meta, "stage": "current"})
        if path: saved.append(path)
    if eyecatch_path and os.path.isfile(eyecatch_path):
        try:
            import shutil
            out_dir = os.path.join(ARTICLE_AUDIT_DIR, "eyecatch")
            os.makedirs(out_dir, exist_ok=True)
            dst = os.path.join(out_dir, os.path.basename(eyecatch_path))
            shutil.copy2(eyecatch_path, dst)
            saved.append(dst)
        except Exception as exc:
            logger.warning("[ARTICLE AUDIT EYECATCH COPY FAILED] %s", exc)
    _append_article_audit_summary(repo, status, parsed, gate_record, failure_reason, saved, evidence_urls)
    return saved


def _append_article_audit_summary(repo: dict, status: str, parsed: dict,
                                  gate_record: dict | None, failure_reason: str,
                                  saved_paths: list[str], evidence_urls: list[str]) -> None:
    try:
        os.makedirs(ARTICLE_AUDIT_DIR, exist_ok=True)
        path = os.path.join(ARTICLE_AUDIT_DIR, "RUN_SUMMARY.md")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("# Daily Article Audit Summary\n\n")
                handle.write("| Candidate | Source | Decision Score | Final Status | Disposition | Quality Warnings / Failure Reason | Markdown |\n")
                handle.write("|---|---|---:|---|---|---|---|\n")
        md_paths = [os.path.relpath(x, ARTICLE_AUDIT_DIR).replace(os.sep, "/") for x in saved_paths if x.endswith(".md")]
        gate_record = gate_record or {}
        reason_rows = gate_record.get("reason_codes", []) or []
        warning_text = "; ".join(_quality_warning_messages(reason_rows))
        reason = (failure_reason or warning_text or gate_record.get("reason", "")).replace("|", "\\|").replace("\n", " ")[:500]
        disposition = gate_record.get("gate_disposition", gate_reason_disposition(reason_rows))
        name = str(repo.get("nameWithOwner") or "untitled").replace("|", "\\|")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"| {name} | {repo.get('source','')} | {parsed.get('score','')} | {status} | {disposition} | {reason} | {', '.join(md_paths)} |\n")
    except Exception as exc:
        logger.error("[ARTICLE AUDIT SUMMARY FAILED] %s", exc)


def build_external_review_markdown(record: dict) -> str:
    """未公開記事を外部レビューへ渡すための貼り付け用Markdown。"""
    history = record.get("gate_history", {})
    reason_codes = history.get("reason_codes", [])
    code_lines = "\n".join(f"- {row.get('reason_code')}: {row.get('message')}" for row in reason_codes) or "- None"
    return "\n".join([
        "# Review Candidate", "",
        "## Pipeline Status", str(record.get("pipeline_status", "")), "",
        "## Failed Gate", str(record.get("failed_gate", "")), "",
        "## Reason Code", code_lines, "",
        "## Decision Score", str(record.get("decision_score", "")), "",
        "## External Review Rubric",
        "1. 事実・数値・条件\n2. Evidence Scope\n3. Title/Introduction/Conclusionの過剰表現\n4. Decision ScoreとActionの整合\n5. Negative Evidence\n6. Human Appeal・AIテンプレート臭・過剰Hedging\n7. note公開可否（A/B/C/D）", "",
        "## Article", record.get("article", ""), "",
    ])


def classify_review_mismatch(pipeline_result: str, external_review: str) -> str | None:
    result = (pipeline_result or "").upper()
    external = (external_review or "").upper()
    if result in {"REVIEW", "FAIL", ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW.upper(), CONTENT_STATUS_QUALITY_FAILED.upper()} and external in {"A", "B"}:
        return "false_positive"
    if result in {"READY", "PASS", ARTICLE_STATUS_READY.upper()} and external in {"C", "D"}:
        return "false_negative"
    return None


def build_regression_case(case_id: str, pipeline_gate: str, pipeline_result: str,
                          external_review: str, reason_code: str, article: str,
                          ground_truth: dict | None = None) -> dict:
    mismatch = classify_review_mismatch(pipeline_result, external_review)
    if not mismatch:
        raise ValueError("Pipeline result and external review are not a false-positive/false-negative mismatch")
    return {
        "case_id": case_id,
        "source_type": f"real_{mismatch}",
        "pipeline_gate": pipeline_gate,
        "pipeline_result": pipeline_result,
        "external_review": external_review,
        "reason_code": reason_code,
        "expected_result": "PASS" if mismatch == "false_positive" else "BLOCK",
        "severity": "critical" if mismatch == "false_negative" else "major",
        "ground_truth": ground_truth or {},
        "article": article,
    }


def register_regression_case(case: dict) -> str:
    """Ground Truth確定前の回帰候補をprivate領域へ登録する。自動でGateは変更しない。"""
    required = {"case_id", "source_type", "pipeline_gate", "pipeline_result", "external_review", "reason_code", "expected_result", "ground_truth", "article"}
    missing = sorted(required - set(case))
    if missing:
        raise ValueError("Regression case missing fields: " + ", ".join(missing))
    os.makedirs(REGRESSION_CASES_DIR, exist_ok=True)
    safe_id = _sanitize_filename(str(case["case_id"]))
    path = os.path.join(REGRESSION_CASES_DIR, f"{safe_id}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(case, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path


# 実運用で過剰Failとなったケース。記事本文はprivate artifactの原稿を正とし、ここでは
# タイトル照合でGateを特別扱いしない。将来の判定結果がQuality Failedへ戻らないことを
# 回帰条件として固定する。
REAL_ARTICLE_REGRESSION_CASES = (
    {
        "case_id": "real_model_hypnosis_20260819",
        "title": "Model Hypnosis",
        "prior_pipeline_result": CONTENT_STATUS_QUALITY_FAILED,
        "external_review": "C",
        "expected_minimum_status": ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW,
        "reason": "一次資料と技術主張は存在し、Evidence Gapの開示とLOW RISK Actionへの縮退で過剰Failを避ける。",
    },
    {
        "case_id": "real_tad_20260819",
        "title": "Topological Attribution Distance (TAD)",
        "prior_pipeline_result": CONTENT_STATUS_QUALITY_FAILED,
        "external_review": "B",
        "expected_minimum_status": ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW,
        "reason": "軽微修正またはEditorial Reviewで扱い、Quality Failedへ直行させない。",
    },
    {
        "case_id": "real_when_agents_coordinate_20260819",
        "title": "When Agents Coordinate",
        "prior_pipeline_result": CONTENT_STATUS_QUALITY_FAILED,
        "external_review": "B",
        "expected_minimum_status": ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW,
        "reason": "軽微修正またはEditorial Reviewで扱い、Quality Failedへ直行させない。",
    },
    {
        "case_id": "real_taffy_low_risk_poc_20260820",
        "title": "Taffy",
        "prior_pipeline_result": ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW,
        "external_review": "B",
        "expected_minimum_status": ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW,
        "reason": "Decision Score 63でも、LOW RISKの限定PoC・比較検証はScore Narrative mismatchにしない。",
    },
)


def register_real_article_regression_cases() -> list[str]:
    """既知の過剰Fail事例をprivate regression候補として必ず登録する。"""
    paths = []
    for item in REAL_ARTICLE_REGRESSION_CASES:
        payload = {
            "case_id": item["case_id"], "source_type": "real_over_reject",
            "pipeline_gate": "evidence_to_decision", "pipeline_result": item["prior_pipeline_result"],
            "external_review": item["external_review"], "reason_code": REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT,
            "expected_result": item["expected_minimum_status"], "ground_truth": {"title": item["title"], "reason": item["reason"]},
            # 本文は別途private artifactにあり、ここで架空の本文を作らない。
            "article": "",
        }
        paths.append(register_regression_case(payload))
    return paths


def real_article_regression_allows(case_id: str, final_status: str) -> bool:
    """既知事例が根拠不足だけでQuality Failedへ戻らないことを検証する。"""
    case = next((row for row in REAL_ARTICLE_REGRESSION_CASES if row["case_id"] == case_id), None)
    if case is None:
        raise ValueError(f"Unknown real article regression case: {case_id}")
    return final_status in {ARTICLE_STATUS_READY, ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW}


def save_gate_history(funnel: DeepDiveGateFunnel | None) -> str | None:
    if funnel is None:
        return None
    payload = {"generated_at": _analyzed_at_now_iso(), "funnel": funnel.counters, "candidates": funnel.records}
    return _save_json_private(GATE_HISTORY_DIR, "deep_dive_gate_history", "gate-history", payload)


def finalize_deep_dive_observability(funnel: DeepDiveGateFunnel | None) -> None:
    """日次終了時に、本文を含めずFunnelと運用要約だけを記録・通知する。"""
    if funnel is None:
        return
    logger.info("\n%s", funnel.render_text())
    history_path = save_gate_history(funnel)
    if funnel.counters["ready_count"] == 0:
        logger.warning("\n%s", funnel.render_ready_zero_summary())
    if history_path:
        logger.info("[GATE HISTORY] %s", history_path)
    send_telegram_alert("📊 Deep Dive Gate Summary\n" + funnel.render_telegram_summary())


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
    if not re.search(r"(?:ただ|一方(?:で|、)|一見すると|現時点では|注意(?:点|が必要|したい)?|制約|限界|リスク|課題|未検証|未対応|トレードオフ|保証されない|無保証|適していません|急ぐ必要はない)", text):
        warnings.append("missing observation or reservation")
    if len(re.findall(r"理由は(?:3|三)つ", text)) >= 1:
        warnings.append("mechanical three-reasons phrasing")
    if len(re.findall(r"[？?]", text)) > 5:
        warnings.append("too many reader questions")
    sentences = [s.strip() for s in re.split(r"(?<=[。！？])", text) if s.strip()]

    def _sentence_ending_family(sentence: str) -> str:
        # Never collapse every plain-form ending into one ``other`` bucket.  That made
        # ``〜する / 〜ある / 〜された / 〜ている`` look mechanically identical.
        clean = re.sub(r"[。！？!?\s]+$", "", sentence or "")
        patterns = (
            ("ませんでした", r"ませんでした$"), ("でした", r"でした$"),
            ("ません", r"ません$"), ("ます", r"ます$"), ("です", r"です$"),
            ("である", r"である$"), ("と言える", r"(?:と|とい)言える$|といえる$"),
            ("必要がある", r"必要がある$"), ("考えられる", r"考えられる$"),
            ("している", r"している$"), ("ている", r"ている$"),
            ("される", r"される$"), ("られる", r"られる$"),
            ("できる", r"できる$"), ("となる", r"となる$"), ("になる", r"になる$"),
            ("する", r"する$"), ("ある", r"ある$"), ("ない", r"ない$"),
            ("した", r"した$"), ("された", r"された$"), ("だった", r"だった$"), ("だ", r"だ$"),
        )
        for label, pattern in patterns:
            if re.search(pattern, clean):
                return label
        return ""

    endings = [_sentence_ending_family(s) for s in sentences]
    endings = [ending for ending in endings if ending]
    # Only a known, repeated ending family may trigger. Unclassified prose never votes as one bucket.
    if len(sentences) >= 8 and len(endings) >= 6:
        counts = Counter(endings)
        dominant_count = max(counts.values(), default=0)
        if dominant_count >= 7 and dominant_count / max(1, len(sentences)) > 0.62:
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
                                    request_kind: str = "deep_dive", request_context: str = "",
                                    request_origin: str = "new"):
    """Deep Dive専用generateContent。URL Context/Searchを同一call内で使いBudgetを守る。"""
    use_url = _should_use_url_context(repo, source_info)
    use_search = ENABLE_GOOGLE_SEARCH_GROUNDING
    tools = []
    if use_url:
        tools.append({"url_context": {}})
    if use_search:
        tools.append({"google_search": {}})

    # source-nativeもURL Contextも無い候補は、タイトルだけで記事を生成しない。
    if not source_info.get("sufficient") and not use_url:
        raise ValueError("一次情報不足: source-native不十分かつURL Context利用不可")

    config = {"max_output_tokens": GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS}
    if tools:
        config["tools"] = tools
    logger.info("[GEMINI DEEP DIVE CALL] kind=%s timeout=%ss", request_kind, GEMINI_DEEP_DIVE_CALL_TIMEOUT_SECONDS)
    response, selected_model = _call_deep_dive_pool(
        prompt, config, request_kind, request_context=request_context, request_origin=request_origin
    )
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
                                 persist_results: bool = True,
                                 candidate_rank: int = 0,
                                 candidate_origin: str = "new",
                                 attribution_context: dict | None = None):
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
    funnel = _active_gate_funnel(persist_results)
    gate_statuses = {
        "fact": GATE_STATUS_NOT_RUN, "editorial": GATE_STATUS_NOT_RUN,
        "publication": GATE_STATUS_NOT_RUN, "human_appeal": GATE_STATUS_NOT_RUN,
    }
    source_info: dict = {}
    candidate_generation_request_count = 0
    generation_attempt_history: list[dict] = []
    article_audit_snapshots: dict[str, str] = {}

    def record_gate_outcome(generation_status: str, final_status: str,
                            fact_gate: str | None = None,
                            editorial_gate: str | None = None,
                            publication_gate: str | None = None,
                            human_appeal_gate: str | None = None,
                            reason_codes: list[dict] | None = None,
                            article_saved: bool = False,
                            decision_score: int | None = None,
                            evidence_result: dict | None = None,
                            deep_dive_generation_called: bool = False,
                            retry_diagnostics: dict | None = None) -> dict:
        record = build_candidate_gate_record(
            candidate_rank, name, url, decision_score if decision_score is not None else screening_score,
            generation_status,
            fact_gate or gate_statuses["fact"], editorial_gate or gate_statuses["editorial"],
            publication_gate or gate_statuses["publication"], human_appeal_gate or gate_statuses["human_appeal"],
            reason_codes, final_status, article_saved, evidence_result,
            deep_dive_generation_called, retry_diagnostics, candidate_origin,
            source=source, generation_request_count=candidate_generation_request_count,
        )
        record.update({
            "generation_attempt_history": list(generation_attempt_history),
            "any_generation_truncated": any(bool(row.get("truncated")) for row in generation_attempt_history),
            "pre_generation_grounding_state": source_info.get("pre_generation_grounding_state", "NOT_RUN"),
            "generation_grounding_state": source_info.get("generation_grounding_state", "NOT_RUN"),
            "retry_grounding_state": source_info.get("retry_grounding_state", "NOT_RUN"),
            "final_grounding_state": source_info.get("final_grounding_state", "NOT_RUN"),
        })
        if funnel:
            funnel.record(record)
        return record

    if source == "ArXiv":
        integrity_ok, integrity_reason, verified_repo = _verify_arxiv_source_integrity(repo)
        if not integrity_ok:
            if integrity_reason.startswith("TRANSIENT:"):
                logger.warning("[ARXIV INTEGRITY PENDING RETRY] %s: %s", name, integrity_reason)
                record = record_gate_outcome(
                    "pending_retry", CONTENT_STATUS_PENDING_RETRY,
                    reason_codes=[{"reason_code": REASON_CODE_PENDING_RETRY, "message": integrity_reason}],
                )
                if persist_results and notion_page_id:
                    update_notion_pending_retry(notion_page_id, name, integrity_reason)
                return None
            logger.error(f"[SOURCE INTEGRITY FAILED] {name}: {integrity_reason}")
            reasons = map_gate_reasons("fact", ["SOURCE_DEPTH_INSUFFICIENT: " + integrity_reason])
            record = record_gate_outcome("failed", CONTENT_STATUS_QUALITY_FAILED, reason_codes=reasons)
            if persist_results:
                save_quality_failed_article(repo, None, record, None, integrity_reason)
                # 恒久的なSource Integrity Failure（ID不正・title mismatch・実在確認失敗等）を
                # Pipeline内部だけのFailureにせず、Notion Stockが正常状態のまま残らないようにする。
                # 記事本文は公開保存せず、理由の詳細はGate History（private artifact）側に残す。
                if notion_page_id:
                    update_notion_quality_failed(notion_page_id, name, grounding_status=GROUNDING_FAILED)
                send_telegram_alert(f"ℹ️ Source Integrity Failed: {name}\n{integrity_reason[:1200]}")
            return None
        repo = verified_repo
        logger.info(f"[SOURCE INTEGRITY OK] {name}: {integrity_reason}")

    source_info = prepare_source_context(repo)
    source_info["pre_generation_grounding_state"] = "VERIFIED" if source_info.get("primary_source_resolved") else "UNVERIFIED"
    source_info["generation_grounding_state"] = "NOT_RUN"
    source_info["retry_grounding_state"] = "NOT_RUN"
    source_info["final_grounding_state"] = source_info["pre_generation_grounding_state"]
    primary_url = source_info.get("primary_url") or url
    freshness = resolve_followup_freshness(source_info)
    if freshness.get("context"):
        source_info["context"] = _truncate_source_context(source_info.get("context", "") + "\n\n" + freshness["context"])
        source_info["verification_context"] = _merge_verification_context(
            source_info.get("verification_context") or source_info.get("context", ""), freshness["context"]
        )
        source_info["verification_context_length"] = len(source_info["verification_context"])
    source_info["freshness_status_available"] = not freshness.get("triggered") or freshness.get("followup_found", False)
    source_info["evidence_metadata"] = _build_evidence_metadata(
        source_info.get("verification_context") or source_info.get("context", ""),
        bool(source_info.get("deep_source_scanned")),
    )
    evidence_result = assess_evidence_sufficiency(source_info)
    initial_evidence_state = evidence_result["state"]
    evidence_result["supplement_attempted"] = False
    evidence_result["supplement_success"] = False
    if evidence_result["state"] == EVIDENCE_SUPPLEMENT_REQUIRED:
        before_docs = len(source_info.get("evidence_documents", []))
        supplement_source_evidence(source_info)
        evidence_result = assess_evidence_sufficiency(source_info)
        evidence_result["supplement_attempted"] = True
        evidence_result["supplement_success"] = (
            evidence_result["state"] == EVIDENCE_SUFFICIENT
            and len(source_info.get("evidence_documents", [])) > before_docs
        )
    evidence_result["initial_state"] = initial_evidence_state
    source_info["evidence_sufficiency"] = evidence_result["state"]
    source_info["evidence_sufficient"] = evidence_result["state"] == EVIDENCE_SUFFICIENT
    source_info["decision_scope_safe"] = evidence_result.get("decision_scope_safe", False)
    source_info["evidence_result"] = evidence_result
    # 既存URL Context fallbackの互換フィールドも、意味ベースの判定へ揃える。
    source_info["sufficient"] = source_info["evidence_sufficient"]
    if evidence_result["state"] == EVIDENCE_INSUFFICIENT:
        missing = evidence_result.get("blocking_missing", evidence_result["core_missing"])
        logger.warning("[EVIDENCE INSUFFICIENT] %s: Deep Dive APIを使わずBackfillへ進む (%s)", name, ", ".join(missing))
        reasons = evidence_reason_rows(evidence_result)
        record_gate_outcome("skipped", "Evidence Insufficient", reason_codes=reasons,
                            evidence_result=evidence_result)
        return None

    quality_feedback = ""
    last_grounding = {"grounding_status": source_info.get("method", GROUNDING_METADATA_ONLY), "evidence_urls": [primary_url] if primary_url else []}
    quality_gate_passed = False
    final_quality_failures: list[str] = []
    final_reason_rows: list[dict] = []
    appeal_before_reedit: dict | None = None
    retry_diagnostics: dict = {}
    deep_dive_generation_called = False
    decision_intelligence_attempted = False
    retained_decision_assessment: dict | None = None
    retained_decision_evidence: dict | None = None

    def persist_product_sidecar_once(final_parsed: dict, content_status: str, article_status: str) -> dict:
        nonlocal decision_intelligence_attempted
        if decision_intelligence_attempted or not persist_results:
            return {"saved": False, "reason": "already_attempted_or_nonpersistent"}
        # Free Article Delivery and paid Product Review are intentionally decoupled in Phase 2.
        # New article prompts do not ask for Adoption fields; tracking/product-review will assess them
        # independently. Keep legacy/retry compatibility if an older response still contains them.
        if not final_parsed.get("adoption_score") or not final_parsed.get("adoption_status"):
            return {"saved": False, "reason": "article_assessment_not_requested"}
        decision_intelligence_attempted = True
        assessment_parsed, assessment_evidence, assessment_source = (
            _select_decision_intelligence_assessment_for_persistence(
                final_parsed, evidence_result, source_info,
                retained_decision_assessment, retained_decision_evidence,
            )
        )
        if assessment_source == "retained":
            logger.info(
                "[DECISION INTELLIGENCE RETAINED] %s: Quality RetryのDI項目が無効なため直前の有効Assessmentを使用",
                name,
            )
        return persist_decision_intelligence_assessment(
            repo, assessment_parsed, source_info, assessment_evidence, _analyzed_at_now_iso(),
            screening_score=screening_score, screening_reason=screening_reason,
            attribution_context=attribution_context, pipeline_status=STATUS_DEEP_DIVE,
            content_status=content_status, article_status=article_status,
        )

    try:
        parsed = None
        for attempt in range(MAX_QUALITY_RETRIES + 1):
            request_kind = "deep_dive" if attempt == 0 else "quality_retry"
            prompt = build_decision_prompt(
                name, primary_url, stars, desc, quality_feedback, source,
                source_context=source_info.get("context", ""),
                grounding_status_hint=source_info.get("method", GROUNDING_METADATA_ONLY),
                evidence_metadata=source_info.get("evidence_metadata", {}), freshness=freshness,
                previous_article=retry_diagnostics.get("original_article", "") if attempt else "",
                evidence_result=evidence_result,
            )
            deep_dive_generation_called = True
            candidate_generation_request_count += 1
            response, grounding = call_gemini_grounded_deep_dive(
                prompt, repo, source_info, request_kind=request_kind,
                request_context=f"{source}:{name}", request_origin=candidate_origin,
            )
            if funnel:
                funnel.incr("generation_api_completed")
            stage_grounding = grounding.get("grounding_status", GROUNDING_FAILED)
            if attempt == 0:
                source_info["generation_grounding_state"] = stage_grounding
            else:
                source_info["retry_grounding_state"] = stage_grounding
            # Retryのmetadata欠落は、事前に確認済みの一次情報を取り消す根拠ではない。
            source_info["final_grounding_state"] = (
                stage_grounding if stage_grounding != GROUNDING_FAILED
                else source_info.get("pre_generation_grounding_state", "UNVERIFIED")
            )
            output_truncated = _response_was_truncated(response)
            generation_attempt_history.append({
                "attempt": attempt + 1, "kind": request_kind, "truncated": bool(output_truncated)
            })
            last_grounding = grounding
            parsed = _parse_gemini_response(response.text or "")
            parsed, polish_changes = _apply_final_japanese_polish(parsed)
            if polish_changes:
                logger.info("[FINAL JAPANESE POLISH] %s changes=%s", name, polish_changes)
            parsed, structure_changes = _apply_deterministic_structure_polish(parsed)
            if structure_changes:
                logger.info("[DETERMINISTIC STRUCTURE POLISH] %s changes=%s", name, structure_changes)
            if attempt == 0 and parsed.get("note_draft"):
                article_audit_snapshots["generated_original"] = parsed.get("note_draft", "")
            elif attempt > 0 and parsed.get("note_draft"):
                article_audit_snapshots["after_quality_retry"] = parsed.get("note_draft", "")
            if funnel:
                funnel.incr("article_parsed")
            parsed.update({
                "grounding_status": grounding.get("grounding_status", GROUNDING_FAILED),
                "evidence_urls_text": "\n".join(grounding.get("evidence_urls", [])),
            })
            if parsed["grounding_status"] == GROUNDING_FAILED and source_info.get("pre_generation_grounding_state") == "VERIFIED":
                parsed["grounding_status"] = source_info.get("method", GROUNDING_SOURCE_NATIVE)
            # Grounding失敗は文章構造の問題ではないため、Quality Retryを消費しない。
            # source-nativeもURL Contextも一次情報を確保できなかった候補は即Backfillへ回す。
            if parsed["grounding_status"] == GROUNDING_FAILED and source_info.get("pre_generation_grounding_state") != "VERIFIED":
                failures = ["Grounding failed"]
                logger.error(f"[GROUNDING FAILED] {name}: 一次情報の取得を確認できないため記事化せずBackfill")
                reasons = map_gate_reasons("fact", failures)
                record = record_gate_outcome("failed", CONTENT_STATUS_QUALITY_FAILED, reason_codes=reasons,
                                             decision_score=parsed.get("score"), evidence_result=evidence_result,
                                             deep_dive_generation_called=deep_dive_generation_called,
                                             retry_diagnostics=retry_diagnostics)
                page_id = notion_page_id
                if persist_results and not page_id and screening_score is not None and screening_score >= NOTION_SAVE_THRESHOLD_SCORE:
                    page_id = save_screening_metadata_to_notion(repo, screening_score, screening_reason or "Deep Dive候補")
                if persist_results and page_id:
                    update_notion_quality_failed(page_id, name, GROUNDING_FAILED, grounding.get("evidence_urls", []))
                if persist_results:
                    save_quality_failed_article(repo, parsed, record, source_info, " / ".join(failures))
                    send_telegram_alert(f"ℹ️ Grounding Failed: {name}\n一次情報を確認できないため記事化せず次候補へ進みます。")
                return None

            # 生成稿のActionが、事前に許可したLOW RISKの範囲を超えていないかを確認する。
            # HIGH RISKへ強まった場合は同じ一次情報で再判定し、弱いEvidenceのまま通さない。
            actual_action_tier = classify_action_risk_tier(parsed.get("action_text", ""))
            if actual_action_tier != evidence_result.get("action_risk_tier", "LOW"):
                source_info["requested_action_risk_tier"] = actual_action_tier
                article_evidence_result = assess_evidence_sufficiency(source_info)
                if article_evidence_result["state"] == EVIDENCE_SUPPLEMENT_REQUIRED:
                    before_docs = len(source_info.get("evidence_documents", []))
                    supplement_source_evidence(source_info)
                    article_evidence_result = assess_evidence_sufficiency(source_info)
                    article_evidence_result["supplement_attempted"] = True
                    article_evidence_result["supplement_success"] = (
                        len(source_info.get("evidence_documents", [])) > before_docs
                        and article_evidence_result["state"] == EVIDENCE_SUFFICIENT
                    )
                article_evidence_result.update({
                    "initial_state": evidence_result.get("initial_state", evidence_result.get("state")),
                    "supplement_attempted": article_evidence_result.get("supplement_attempted", evidence_result.get("supplement_attempted", False)),
                    "supplement_success": article_evidence_result.get("supplement_success", evidence_result.get("supplement_success", False)),
                })
                evidence_result = article_evidence_result
                source_info["evidence_result"] = evidence_result
                source_info["decision_scope_safe"] = evidence_result.get("decision_scope_safe", False)

            # Article Quality Retry and subscriber-facing Adoption Assessment are independent.
            # Capture the newest independently valid DI snapshot before the article gates can
            # trigger a rewrite.  A later retry may improve it; an invalid retry may not erase it.
            if (decision_intelligence.ENABLE_DECISION_INTELLIGENCE_DB
                    and parsed.get("adoption_score") and parsed.get("adoption_status")):
                verification_context = source_info.get("verification_context") or source_info.get("context", "")
                assessment_ok, assessment_failures = validate_decision_intelligence_assessment(
                    parsed, evidence_result, verification_context, source_info.get("evidence_metadata", {})
                )
                if assessment_ok:
                    retained_decision_assessment = dict(parsed)
                    retained_decision_evidence = dict(evidence_result)
                    logger.info(
                        "[DECISION INTELLIGENCE SNAPSHOT] %s: valid assessment retained from %s",
                        name, request_kind,
                    )
                elif retained_decision_assessment is not None:
                    logger.info(
                        "[DECISION INTELLIGENCE SNAPSHOT] %s: %s assessment invalid; prior valid assessment retained (%s)",
                        name, request_kind, " / ".join(assessment_failures)[:500],
                    )

            verification_context = source_info.get("verification_context") or source_info.get("context", "")
            fact_ok, fact_failures = validate_fact_gate(
                parsed, name, source_context=verification_context, source=source,
                evidence_metadata=source_info.get("evidence_metadata", {}), source_info=source_info,
                freshness=freshness, output_truncated=output_truncated,
            )
            if evidence_result.get("action_risk_downgraded_from"):
                fact_failures.append(f"{evidence_result['action_risk_downgraded_from']}_RISK_ACTION_UNSUPPORTED: downgrade to LOW required")
                fact_ok = False
            editorial_ok, editorial_warnings = validate_editorial_gate(parsed, name)
            publication_state, publication_issues = validate_publication_readiness_gate(
                parsed, verification_context, source_info,
            )
            human_appeal, human_appeal_issues = validate_human_appeal_gate(parsed, _RUN_ARTICLE_STYLE_MEMORY if persist_results else [])
            gate_statuses.update({
                "fact": GATE_STATUS_PASS if fact_ok else GATE_STATUS_FAIL,
                "editorial": GATE_STATUS_PASS if editorial_ok else GATE_STATUS_WARNING,
                "publication": GATE_STATUS_PASS if publication_state == "PASS" else (GATE_STATUS_REVIEW if publication_state == "REVIEW" else GATE_STATUS_FAIL),
                "human_appeal": GATE_STATUS_PASS if human_appeal == "ACCEPTABLE" else GATE_STATUS_WARNING,
            })
            if funnel:
                funnel.incr("quality_evaluation_completed")
            logger.info("[PUBLICATION READINESS GATE] %s: %s", name, publication_state)
            logger.info("[HUMAN APPEAL GATE] %s: %s", name, human_appeal)
            if appeal_before_reedit is None:
                appeal_before_reedit = parsed.copy()
            elif human_appeal_materially_degraded(appeal_before_reedit, parsed):
                human_appeal_issues.append("human_appeal_materially_degraded_after_reedit")
                human_appeal = "WEAK"
            # Run 102: GateをHARD / REVIEW / SOFTへ分離する。
            # 「文章が最高ではない」だけで無料枠と公開機会を失わない一方、
            # Fact/Evidence/Decisionの信頼性と「で、どうするか」という商品価値は守る。
            all_reason_rows = (map_gate_reasons("fact", fact_failures)
                               + map_gate_reasons("editorial", editorial_warnings)
                               + map_gate_reasons("publication", publication_issues)
                               + map_gate_reasons("human_appeal", human_appeal_issues))
            disposition = gate_reason_disposition(all_reason_rows)
            final_reason_rows = list(all_reason_rows)
            final_quality_failures = [str(row.get("message", "")) for row in all_reason_rows if row.get("message")]
            failures = list(final_quality_failures)
            human_rows = [row for row in all_reason_rows if row.get("gate") == "human_appeal"]
            appeal_review_required = any(row.get("severity") in {GATE_SEVERITY_HARD, GATE_SEVERITY_REVIEW}
                                         for row in human_rows)
            if appeal_review_required:
                gate_statuses["human_appeal"] = GATE_STATUS_REVIEW

            # PASS_WITH_WARNINGSはここで即出荷。SOFT文章改善だけのQuality Retryは禁止する。
            if disposition in {GATE_DISPOSITION_PASS, GATE_DISPOSITION_PASS_WITH_WARNINGS}:
                quality_gate_passed = True
                if persist_results:
                    _remember_article_style(name, parsed.get("note_draft", ""))
                if disposition == GATE_DISPOSITION_PASS_WITH_WARNINGS:
                    soft_messages = _quality_warning_messages(all_reason_rows)
                    logger.warning("[QUALITY PASS WITH WARNINGS] %s: %s", name, ", ".join(soft_messages))
                    retry_diagnostics = {
                        "original_article": parsed.get("note_draft", ""),
                        "trigger_reason_codes": _reason_rows_by_severity(all_reason_rows, GATE_SEVERITY_SOFT),
                        "changed_sections": [],
                        "retry_attempted": False,
                        "retry_skipped_reason": "soft_quality_only",
                    }
                break

            # Retry/Rescueへ渡すのは公開停止・意思決定価値に関係する理由だけ。
            # Soft warningはArtifactへ残すが、修正プロンプトには混ぜない。
            reason_rows = _reason_rows_by_severity(
                all_reason_rows, GATE_SEVERITY_HARD, GATE_SEVERITY_REVIEW
            )

            # Try the zero-API subtractive rescue before spending a Gemini quality-retry request.
            # This is especially valuable for isolated hype/named-fact/numeric defects: if Fact and
            # Publication become safe after deleting the exact offending material, an extra model
            # call would add cost and a new hallucination opportunity without adding evidence.
            hard_reason_rows = _reason_rows_by_severity(reason_rows, GATE_SEVERITY_HARD)
            if ENABLE_DETERMINISTIC_PUBLICATION_RESCUE and attempt < MAX_QUALITY_RETRIES and hard_reason_rows:
                pre_rescue_article = parsed.get("note_draft", "")
                rescued_parsed, rescue_changes = _apply_deterministic_publication_rescue(parsed, hard_reason_rows)
                if rescue_changes:
                    rescue_ready, rescue_diag = _publication_rescue_can_be_ready(
                        rescued_parsed, verification_context, source, source_info.get("evidence_metadata", {}),
                        source_info, freshness, output_truncated=output_truncated,
                        peer_articles=_RUN_ARTICLE_STYLE_MEMORY if persist_results else [],
                    )
                    if funnel:
                        funnel.incr("deterministic_rescue_attempted")
                    rescue_loss = rescued_parsed.get("_rescue_loss", {})
                    loss_exceeded = bool(rescue_loss.get("loss_exceeded"))
                    if rescued_parsed.get("note_draft"):
                        article_audit_snapshots["pre_retry_rescue"] = rescued_parsed.get("note_draft", "")
                    logger.info(
                        "[PUBLICATION RESCUE PRE-RETRY] %s changes=%s ready=%s loss=%s remaining_fact=%s publication=%s",
                        name, rescue_changes, rescue_ready, rescue_loss, rescue_diag.get("fact_failures"), rescue_diag.get("publication_state"),
                    )
                    if loss_exceeded:
                        logger.warning("[RESCUE LOSS LIMIT] %s auto-Ready blocked; one dynamic recompose required", name)
                    if rescue_ready and not loss_exceeded:
                        if funnel:
                            funnel.incr("deterministic_rescue_success")
                        parsed = rescued_parsed
                        quality_gate_passed = True
                        fact_ok = bool(rescue_diag.get("fact_ok"))
                        editorial_ok = bool(rescue_diag.get("editorial_ok"))
                        publication_state = str(rescue_diag.get("publication_state"))
                        human_appeal = str(rescue_diag.get("human_state"))
                        fact_failures = list(rescue_diag.get("fact_failures") or [])
                        editorial_warnings = list(rescue_diag.get("editorial_warnings") or [])
                        publication_issues = list(rescue_diag.get("publication_issues") or [])
                        human_appeal_issues = list(rescue_diag.get("human_issues") or [])
                        final_reason_rows = list(rescue_diag.get("reason_rows") or [])
                        final_quality_failures = [str(row.get("message", "")) for row in final_reason_rows if row.get("message")]
                        retry_diagnostics = {
                            "original_article": pre_rescue_article,
                            "trigger_reason_codes": hard_reason_rows,
                            "changed_sections": ["deterministic_subtractive_rescue"],
                            "retry_attempted": False,
                            "deterministic_rescue": rescue_changes,
                        }
                        break
            retry_allowed, retry_skip_reason = should_attempt_dynamic_retry(
                reason_rows, evidence_result, candidate_origin=candidate_origin
            )
            final_attempt = attempt >= MAX_QUALITY_RETRIES or not retry_allowed
            if not retry_allowed and attempt < MAX_QUALITY_RETRIES:
                retry_diagnostics = {
                    "original_article": parsed.get("note_draft", ""),
                    "trigger_reason_codes": reason_rows,
                    "changed_sections": [],
                    "retry_attempted": False,
                    "retry_skipped_reason": retry_skip_reason,
                }
                if funnel:
                    if retry_skip_reason == "pending_retry_budget_exhausted":
                        funnel.incr("retry_skipped_budget")
                    elif retry_skip_reason == "soft_quality_only":
                        funnel.incr("retry_avoided_soft_only")
                    else:
                        funnel.incr("retry_skipped_nonrepairable")
                logger.warning("[QUALITY RETRY SKIPPED] %s: %s", name, retry_skip_reason)

            # Fact Gate FAILは事実誤認/根拠外主張なのでReviewへ降格してはいけない。
            # Fact PASS後にHARD/REVIEWが残る場合は、公開せず人間レビューへ。
            # Publication矛盾、Decision Voice消失、重大Editorial defectをここで安全に止める。
            if (fact_ok and publication_state != "FAIL"
                    and disposition in {GATE_DISPOSITION_BLOCK, GATE_DISPOSITION_REVIEW} and final_attempt):
                blocking_rows = _reason_rows_by_severity(
                    all_reason_rows, GATE_SEVERITY_HARD, GATE_SEVERITY_REVIEW
                )
                review_issues = [str(row.get("message", "")) for row in blocking_rows if row.get("message")]
                logger.warning("[QUALITY REVIEW REQUIRED] %s: %s", name, ", ".join(review_issues))
                reason_rows = blocking_rows
                retry_final = finalize_retry_diagnostics(
                    retry_diagnostics, reason_rows, "NEEDS_EDITORIAL_REVIEW", parsed.get("note_draft", "")
                )
                if not persist_results:
                    record_gate_outcome(
                        "completed", ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW,
                        GATE_STATUS_PASS, GATE_STATUS_PASS if editorial_ok else GATE_STATUS_WARNING,
                        GATE_STATUS_REVIEW if publication_state == "REVIEW" else GATE_STATUS_PASS,
                        GATE_STATUS_REVIEW if appeal_review_required else (GATE_STATUS_WARNING if human_appeal_issues else GATE_STATUS_PASS),
                        reason_rows, decision_score=parsed.get("score"), evidence_result=evidence_result,
                        deep_dive_generation_called=deep_dive_generation_called, retry_diagnostics=retry_final,
                    )
                    break
                page_id = notion_page_id
                if not page_id and screening_score is not None and screening_score >= NOTION_SAVE_THRESHOLD_SCORE:
                    page_id = save_screening_metadata_to_notion(repo, screening_score, screening_reason or "Deep Dive候補")
                review_notion_saved = False
                if page_id:
                    analyzed_at = _analyzed_at_now_iso()
                    # Review稿もReady稿と同じEvidence集約規則を使う。Grounding metadataだけに
                    # 依存すると、Supplementで実際に読んだPDF/DocsがNotion Evidence URLsと
                    # 人間レビュー用原稿末尾から落ち、レビュー再現性が壊れる。
                    review_evidence_urls = _collect_final_evidence_urls(source_info, last_grounding)
                    review_meta = dict(parsed)
                    review_meta["evidence_urls_text"] = "\n".join(review_evidence_urls)
                    manuscript_primary_url = source_info.get("primary_url") or url
                    discovery_url = (repo.get("sourceDetails", {}) or {}).get("hn_url", "")
                    if source == "ProductHunt":
                        discovery_url = (repo.get("sourceDetails", {}) or {}).get("producthunt_url", "") or url
                    review_manuscript = build_clean_note_manuscript(
                        parsed["note_draft"], name, manuscript_primary_url, spdx_id, source,
                        evidence_urls=review_evidence_urls,
                        title_text=parsed.get("title_text", ""),
                        discovery_url=discovery_url,
                    )
                    review_properties = build_notion_properties(
                        name, url, parsed["score"], parsed["score_breakdown_text"], parsed["what_text"],
                        parsed["why_important_text"], parsed["why_not_important_text"], parsed["action_text"],
                        spdx_id, parsed["paradigm_shift_text"], parsed["alternative_comparison_text"],
                        parsed["migration_cost_text"], source, stars, parsed["title_text"], "",
                        published_at, analyzed_at, report_meta=review_meta,
                    )
                    review_notion_saved = persist_notion_needs_editorial_review(
                        page_id, name, review_manuscript, review_properties, review_issues
                    )
                if review_notion_saved:
                    persist_product_sidecar_once(
                        parsed, CONTENT_STATUS_DEEP_DIVE, ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW
                    )
                    record = record_gate_outcome(
                        "completed", ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW,
                        GATE_STATUS_PASS, GATE_STATUS_PASS if editorial_ok else GATE_STATUS_WARNING,
                        GATE_STATUS_REVIEW if publication_state == "REVIEW" else GATE_STATUS_PASS,
                        GATE_STATUS_REVIEW if appeal_review_required else (GATE_STATUS_WARNING if human_appeal_issues else GATE_STATUS_PASS),
                        reason_rows, decision_score=parsed.get("score"), evidence_result=evidence_result,
                        deep_dive_generation_called=deep_dive_generation_called, retry_diagnostics=retry_final,
                    )
                    alert_prefix = "ℹ️ Needs Editorial Review"
                else:
                    persist_product_sidecar_once(
                        parsed, CONTENT_STATUS_PENDING_RETRY, ARTICLE_STATUS_NOT_PLANNED
                    )
                    persistence_rows = reason_rows + [{
                        "reason_code": REASON_CODE_NOTION_PERSISTENCE_FAILED,
                        "message": "Needs Editorial Review manuscript could not be persisted to Notion; queued for retry",
                        "gate": "persistence", "severity": GATE_SEVERITY_OPERATIONAL,
                    }]
                    record = record_gate_outcome(
                        "pending_retry", CONTENT_STATUS_PENDING_RETRY,
                        GATE_STATUS_PASS, GATE_STATUS_PASS if editorial_ok else GATE_STATUS_WARNING,
                        GATE_STATUS_REVIEW if publication_state == "REVIEW" else GATE_STATUS_PASS,
                        GATE_STATUS_REVIEW if appeal_review_required else GATE_STATUS_PASS,
                        persistence_rows, decision_score=parsed.get("score"), evidence_result=evidence_result,
                        deep_dive_generation_called=deep_dive_generation_called,
                        retry_diagnostics=finalize_retry_diagnostics(retry_diagnostics, persistence_rows, "PENDING_RETRY", parsed.get("note_draft", "")),
                    )
                    alert_prefix = "⚠️ Needs Editorial Review Persistence Failed / Pending Retry"
                saved_path = save_needs_editorial_review_article(repo, parsed, record, source_info, " / ".join(review_issues))
                save_article_audit_package(
                    repo, "NEEDS_EDITORIAL_REVIEW", parsed, source_info, record, " / ".join(review_issues),
                    snapshots=article_audit_snapshots,
                )
                record["notion_review_saved"] = review_notion_saved
                record["article_saved"] = bool(saved_path)
                send_telegram_alert(f"{alert_prefix}: {name}\n" + " / ".join(review_issues)[:1200])
                return None
            if final_attempt:
                # Last-chance 0-API rescue: delete only the exact unsupported material already
                # diagnosed by the gates. Never invent replacement facts or weaken evidence checks.
                if ENABLE_DETERMINISTIC_PUBLICATION_RESCUE:
                    rescued_parsed, rescue_changes = _apply_deterministic_publication_rescue(parsed, reason_rows)
                    if rescue_changes:
                        if funnel:
                            funnel.incr("deterministic_rescue_attempted")
                        rescue_ready, rescue_diag = _publication_rescue_can_be_ready(
                            rescued_parsed, verification_context, source, source_info.get("evidence_metadata", {}),
                            source_info, freshness, output_truncated=output_truncated,
                            peer_articles=_RUN_ARTICLE_STYLE_MEMORY if persist_results else [],
                        )
                        rescue_loss = rescued_parsed.get("_rescue_loss", {})
                        loss_exceeded = bool(rescue_loss.get("loss_exceeded"))
                        if rescued_parsed.get("note_draft"):
                            article_audit_snapshots["final_after_rescue"] = rescued_parsed.get("note_draft", "")
                        logger.info(
                            "[PUBLICATION RESCUE] %s changes=%s ready=%s loss=%s remaining_fact=%s publication=%s",
                            name, rescue_changes, rescue_ready, rescue_loss, rescue_diag.get("fact_failures"), rescue_diag.get("publication_state"),
                        )
                        if loss_exceeded:
                            logger.warning("[RESCUE LOSS LIMIT] %s final subtractive rescue cannot auto-Ready", name)
                        if rescue_ready and not loss_exceeded:
                            if funnel:
                                funnel.incr("deterministic_rescue_success")
                            parsed = rescued_parsed
                            quality_gate_passed = True
                            fact_ok = bool(rescue_diag.get("fact_ok"))
                            editorial_ok = bool(rescue_diag.get("editorial_ok"))
                            publication_state = str(rescue_diag.get("publication_state"))
                            human_appeal = str(rescue_diag.get("human_state"))
                            fact_failures = list(rescue_diag.get("fact_failures") or [])
                            editorial_warnings = list(rescue_diag.get("editorial_warnings") or [])
                            publication_issues = list(rescue_diag.get("publication_issues") or [])
                            human_appeal_issues = list(rescue_diag.get("human_issues") or [])
                            final_reason_rows = list(rescue_diag.get("reason_rows") or [])
                            final_quality_failures = [str(row.get("message", "")) for row in final_reason_rows if row.get("message")]
                            retry_diagnostics = dict(retry_diagnostics or {})
                            retry_diagnostics["deterministic_rescue"] = rescue_changes
                            break
                        # Keep final failure diagnostics aligned with the rescued manuscript.
                        fact_ok = bool(rescue_diag.get("fact_ok"))
                        editorial_ok = bool(rescue_diag.get("editorial_ok"))
                        publication_state = str(rescue_diag.get("publication_state"))
                        human_appeal = str(rescue_diag.get("human_state"))
                        fact_failures = list(rescue_diag.get("fact_failures") or [])
                        editorial_warnings = list(rescue_diag.get("editorial_warnings") or [])
                        publication_issues = list(rescue_diag.get("publication_issues") or [])
                        human_appeal_issues = list(rescue_diag.get("human_issues") or [])
                        failures = fact_failures + editorial_warnings + publication_issues + human_appeal_issues
                        final_reason_rows = list(rescue_diag.get("reason_rows") or [])
                logger.error(f"[QUALITY GATE FAILED] {name}: {', '.join(failures)}")
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
                persist_product_sidecar_once(
                    parsed, CONTENT_STATUS_QUALITY_FAILED, ARTICLE_STATUS_NOT_PLANNED
                )
                reason_rows = (map_gate_reasons("fact", fact_failures) + map_gate_reasons("editorial", editorial_warnings)
                               + map_gate_reasons("publication", publication_issues) + map_gate_reasons("human_appeal", human_appeal_issues))
                record = record_gate_outcome(
                    "completed", CONTENT_STATUS_QUALITY_FAILED,
                    GATE_STATUS_PASS if fact_ok else GATE_STATUS_FAIL,
                    GATE_STATUS_PASS if editorial_ok else GATE_STATUS_WARNING,
                    GATE_STATUS_PASS if publication_state == "PASS" else (GATE_STATUS_REVIEW if publication_state == "REVIEW" else GATE_STATUS_FAIL),
                    GATE_STATUS_WARNING if human_appeal_issues else GATE_STATUS_PASS,
                    reason_rows, decision_score=parsed.get("score"), evidence_result=evidence_result,
                    deep_dive_generation_called=deep_dive_generation_called,
                    retry_diagnostics=finalize_retry_diagnostics(retry_diagnostics, reason_rows, "QUALITY_FAILED", parsed.get("note_draft", "")),
                )
                saved_path = save_quality_failed_article(repo, parsed, record, source_info, " / ".join(failures), audit_snapshots=article_audit_snapshots)
                record["article_saved"] = bool(saved_path)
                send_telegram_alert(f"ℹ️ Quality Failed: {name}\n" + " / ".join(failures)[:1500])
                return None
            quality_feedback, changed_sections = build_dynamic_retry_instruction(reason_rows)
            retry_diagnostics = {
                "original_article": parsed.get("note_draft", ""),
                "trigger_reason_codes": reason_rows,
                "changed_sections": changed_sections,
                "retry_attempted": True,
            }
            retry_severities = {row.get("severity") for row in reason_rows}
            gate_name = "HARD" if GATE_SEVERITY_HARD in retry_severities else "DECISION_VALUE_REVIEW"
            logger.warning(f"[QUALITY RETRY:{gate_name}] {name}: {quality_feedback}")

        if not parsed:
            return None

        evidence_urls = _collect_final_evidence_urls(source_info, last_grounding)
        # Notion側のEvidence URLsも、最終的にGateを支えた実取得資料と一致させる。
        parsed["evidence_urls_text"] = "\n".join(evidence_urls)
        manuscript_primary_url = source_info.get("primary_url") or url
        discovery_url = (repo.get("sourceDetails", {}) or {}).get("hn_url", "")
        if source == "ProductHunt":
            discovery_url = (repo.get("sourceDetails", {}) or {}).get("producthunt_url", "") or url
        reader_summary = build_reader_first_summary(parsed)
        clean_manuscript = build_clean_note_manuscript(
            parsed["note_draft"], name, manuscript_primary_url, spdx_id, source, evidence_urls=evidence_urls,
            title_text=parsed.get("title_text", ""), discovery_url=discovery_url,
            reader_summary=reader_summary, published_at=published_at,
        )

        eyecatch_url = ""
        if persist_results:
            try:
                os.makedirs(EYECATCH_OUTPUT_DIR, exist_ok=True)
                eyecatch_filename = f"{_sanitize_filename(name)}.png"
                eyecatch_path = os.path.join(EYECATCH_OUTPUT_DIR, eyecatch_filename)
                technical_impact, urgency = _extract_eyecatch_score_components(parsed.get("score_breakdown_text", ""))
                generated_path = generate_eyecatch_image(
                    parsed["title_text"], eyecatch_path, source, decision_score=parsed.get("score"),
                    technical_impact=technical_impact, urgency=urgency, article_ready=True,
                )
                if generated_path:
                    logger.info(f"[EYECATCH] {name} -> {eyecatch_path} を生成しました。")
                    eyecatch_url = upload_eyecatch_to_github(eyecatch_path, eyecatch_filename) or ""
            except Exception as e:
                logger.warning(f"[EYECATCH SKIP] {name}: {e}")
        else:
            logger.info(f"[REGEN TEST] eyecatch生成・GitHub uploadをスキップ: {name}")

        analyzed_at = _analyzed_at_now_iso()
        notion_name = _notion_display_name(repo)
        parsed["source_summary_text"] = _source_summary_with_original(repo, parsed.get("source_summary_text", ""))
        if persist_results:
            # Readyの定義: Quality Gate PASS AND Notion Persistence SUCCESS。
            # 戻り値を必ず確認し、Notionへ保存されていない記事をReadyとして扱わない。
            if notion_page_id:
                notion_persisted = upgrade_notion_page_with_report(
                    notion_page_id,
                    notion_name, url, parsed["score"], parsed["score_breakdown_text"], parsed["what_text"],
                    parsed["why_important_text"], parsed["why_not_important_text"], parsed["action_text"],
                    spdx_id, clean_manuscript, parsed["paradigm_shift_text"],
                    parsed["alternative_comparison_text"], parsed["migration_cost_text"],
                    source, stars, parsed["title_text"], eyecatch_url, published_at, analyzed_at,
                    report_meta=parsed,
                )
            else:
                notion_persisted = save_to_notion(
                    notion_name, url, parsed["score"], parsed["score_breakdown_text"], parsed["what_text"],
                    parsed["why_important_text"], parsed["why_not_important_text"], parsed["action_text"],
                    spdx_id, clean_manuscript, parsed["paradigm_shift_text"],
                    parsed["alternative_comparison_text"], parsed["migration_cost_text"],
                    source, stars, parsed["title_text"], eyecatch_url, published_at, analyzed_at,
                    report_meta=parsed, screening_score=screening_score, screening_reason=screening_reason,
                )
            reason_rows = list(final_reason_rows)
            if not notion_persisted:
                persist_product_sidecar_once(
                    parsed, CONTENT_STATUS_PERSISTENCE_FAILED, ARTICLE_STATUS_NOT_PLANNED
                )
                # 記事品質は問題ない（Quality Gate PASS）が、永続保存層が失敗している。
                # Readyにせず、Ready件数にも加算しない。Quality Failedとは区別して記録する。
                logger.error(f"[NOTION PERSISTENCE FAILED] {name} -> Quality Gate PASSだがNotion保存/アップグレードに失敗")
                persistence_reason_rows = reason_rows + [{
                    "reason_code": REASON_CODE_NOTION_PERSISTENCE_FAILED,
                    "message": "Quality Gate PASS after Notion save/upgrade failure",
                    "gate": "persistence", "severity": GATE_SEVERITY_OPERATIONAL,
                }]
                record_gate_outcome(
                    "completed", CONTENT_STATUS_PERSISTENCE_FAILED,
                    GATE_STATUS_PASS, GATE_STATUS_PASS if not final_quality_failures else GATE_STATUS_WARNING,
                    GATE_STATUS_PASS, GATE_STATUS_WARNING if final_quality_failures else GATE_STATUS_PASS,
                    persistence_reason_rows, decision_score=parsed.get("score"), evidence_result=evidence_result,
                    deep_dive_generation_called=deep_dive_generation_called,
                    retry_diagnostics=finalize_retry_diagnostics(retry_diagnostics, persistence_reason_rows, "NOTION_PERSISTENCE_FAILED", parsed.get("note_draft", "")),
                    article_saved=False,
                )
                save_article_audit_package(
                    repo, "PENDING_RETRY", parsed, source_info, None, "Notion persistence failed after Quality Gate PASS",
                    snapshots=article_audit_snapshots, clean_manuscript=clean_manuscript,
                    eyecatch_path=eyecatch_path if 'eyecatch_path' in locals() else "",
                )
                send_telegram_alert(f"⚠️ Notion Persistence Failed: {name}\n記事はQuality Gateを通過しましたが、Notionへの保存/アップグレードに失敗したためReadyにしていません。")
                # Readyの定義（Quality Gate PASS AND Notion Persistence SUCCESS）を
                # 満たしていないため、ここでNoneを返してgenerated_count/retry_generated
                # への誤加算（呼び出し元の `if report:` / `if generate_intelligence_report(...):`）
                # を防ぐ。以降のclean_manuscript返却経路（regen比較用のFalse分岐やこの
                # 関数末尾のreturn）へは到達させない。
                return None
            else:
                persist_product_sidecar_once(
                    parsed, CONTENT_STATUS_DEEP_DIVE, ARTICLE_STATUS_READY
                )
                editorial_soft = any(row.get("gate") == "editorial" and row.get("severity") == GATE_SEVERITY_SOFT for row in reason_rows)
                human_soft = any(row.get("gate") == "human_appeal" and row.get("severity") == GATE_SEVERITY_SOFT for row in reason_rows)
                ready_record = record_gate_outcome(
                    "completed", ARTICLE_STATUS_READY,
                    GATE_STATUS_PASS, GATE_STATUS_WARNING if editorial_soft else GATE_STATUS_PASS,
                    GATE_STATUS_PASS, GATE_STATUS_WARNING if human_soft else GATE_STATUS_PASS,
                    reason_rows, decision_score=parsed.get("score"), evidence_result=evidence_result,
                    deep_dive_generation_called=deep_dive_generation_called,
                    retry_diagnostics=finalize_retry_diagnostics(retry_diagnostics, reason_rows, "READY", parsed.get("note_draft", "")),
                    article_saved=True,
                )
                # Conversion attribution is business telemetry only. It runs after Ready is established
                # and therefore can never weaken/override the quality or Notion-persistence gate.
                attribution_path = save_subscription_attribution_record(
                    repo, parsed, analyzed_at, notion_page_id=notion_page_id,
                    attribution_context=attribution_context,
                )
                logger.info("[SUBSCRIPTION ATTRIBUTION] %s -> %s", name, attribution_path or "not-recorded")
                ready_warnings = "; ".join(_quality_warning_messages(reason_rows))
                save_article_audit_package(
                    repo, "READY", parsed, source_info, ready_record, ready_warnings, snapshots=article_audit_snapshots,
                    clean_manuscript=clean_manuscript, eyecatch_path=eyecatch_path if 'eyecatch_path' in locals() else "",
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
        provider_failure = isinstance(e, (GeminiCallTimeoutError, NoAvailableModelError)) or (isinstance(e, APIError) and getattr(e, "code", None) in {429, 503})
        reason_code = REASON_CODE_MODEL_UNAVAILABLE if provider_failure else REASON_CODE_PENDING_RETRY
        record_gate_outcome("pending_retry", CONTENT_STATUS_PENDING_RETRY,
                            reason_codes=[{"reason_code": reason_code, "message": str(e)}])
        page_id = notion_page_id
        if persist_results and not page_id and screening_score is not None and screening_score >= NOTION_SAVE_THRESHOLD_SCORE:
            page_id = save_screening_metadata_to_notion(repo, screening_score, screening_reason or "Deep Dive候補")
        if persist_results and page_id:
            update_notion_pending_retry(page_id, name, str(e))
        if persist_results:
            save_article_audit_package(repo, "PENDING_RETRY", parsed if isinstance(parsed, dict) else {}, source_info, None, str(e), snapshots=article_audit_snapshots)
        return None
    except DeepDiveRunBudgetExceededError as e:
        logger.warning(f"[DEEP DIVE RUN BUDGET STOP] {name}: {e}")
        record_gate_outcome(
            "pending_retry", CONTENT_STATUS_PENDING_RETRY,
            reason_codes=[{"reason_code": REASON_CODE_DEEP_DIVE_RUN_BUDGET_EXHAUSTED, "message": str(e)}],
        )
        if persist_results and notion_page_id:
            update_notion_pending_retry(notion_page_id, name, str(e))
        if persist_results:
            save_article_audit_package(repo, "PENDING_RETRY", parsed if isinstance(parsed, dict) else {}, source_info, None, str(e), snapshots=article_audit_snapshots)
        return None
    except GeminiBudgetExceededError as e:
        logger.warning(f"[GEMINI BUDGET STOP] {name}: {e}")
        record_gate_outcome("pending_retry", CONTENT_STATUS_PENDING_RETRY,
                            reason_codes=[{"reason_code": REASON_CODE_PENDING_RETRY, "message": str(e)}])
        if persist_results and notion_page_id:
            update_notion_pending_retry(notion_page_id, name, str(e))
        return None
    except Exception as e:
        logger.error(f"[DEEP DIVE FAILED] {name}: {e}")
        record_gate_outcome("pending_retry", CONTENT_STATUS_PENDING_RETRY,
                            reason_codes=[{"reason_code": REASON_CODE_PENDING_RETRY, "message": str(e)}])
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
以下の{source}発の一次情報について、CTO/PM向け無料noteで読者を獲得し、
会員向け意思決定DBへ蓄積する題材としての価値を0〜100点で採点せよ。
判断基準: 技術的な新規性・実務への即効性・意思決定への影響・話題性。
COMMERCIALは品質スコアとは独立して、読者需要の見込み・会員DB転換可能性・継続的な実務需要を0〜100で保守的に推定する。
SHELFは情報価値の持続性を0〜100で推定し、0-34=FLASH、35-69=TREND、70-100=EVERGREENを目安とする。
TOPICは内容の主テーマを MODEL / AGENT / DEVTOOLS / INFRA / DATA / SECURITY / MULTIMODAL / PRODUCT / OTHER のいずれか1つで返す。
Source種別ではなく内容で分類し、論文だからRESEARCHのような分類はしない。
入力にないアクセス数・検索量・売上は捏造しない。
出所が異なる案件同士でも公平に比較できるよう、指標の絶対値ではなく
内容の質・インパクトを軸に採点すること。

・出所: {source}
・名前: {name}
・{metric_label}: {stars}
{metric_note}・概要: {desc}

出力は必ず次の1行形式のみ。説明文・Markdown・前置きは一切不要。
SCORE=<0-100> COMMERCIAL=<0-100> SHELF=<0-100> TOPIC=<上記9分類> REASON=<20文字以内の一言理由>
"""

def _parse_screening_response(text: str) -> dict:
    score_match = re.search(r"SCORE\s*=\s*(\d+)", text)
    commercial_match = re.search(r"COMMERCIAL\s*=\s*(\d+)", text)
    shelf_match = re.search(r"SHELF\s*=\s*(\d+)", text)
    topic_match = re.search(r"TOPIC\s*=\s*([A-Za-z_]+)", text)
    reason_match = re.search(r"REASON\s*=\s*(.+)", text)
    score = int(score_match.group(1)) if score_match else 0
    commercial = int(commercial_match.group(1)) if commercial_match else PROFIT_SCORE_NEUTRAL
    shelf = int(shelf_match.group(1)) if shelf_match else PROFIT_SCORE_NEUTRAL
    return {
        "score": max(0, min(100, score)), "commercial_score": max(0, min(100, commercial)),
        "shelf_life_score": max(0, min(100, shelf)), "shelf_life": shelf_life_label(shelf),
        "portfolio_topic": normalize_portfolio_topic(topic_match.group(1) if topic_match else None),
        "deep_dive_priority_score": deep_dive_priority_score(score, commercial),
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
                request_context=f"{source}:{name}",
            )
            parsed = _parse_screening_response(response.text)
            logger.info(
                f"[SCREENED] {name}: Decision {parsed['score']} / Commercial {parsed['commercial_score']} / "
                f"Shelf {parsed['shelf_life']} ({parsed['reason']})"
            )
            return {"repo": repo, **parsed}
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


def _source_base_fetch_limits() -> dict[str, int]:
    return {
        "GitHub": max(0, GITHUB_FETCH_LIMIT),
        "HackerNews": max(0, HN_FETCH_LIMIT),
        "ArXiv": max(0, ARXIV_FETCH_LIMIT),
        "ProductHunt": max(0, PRODUCTHUNT_FETCH_LIMIT),
    }


def _empty_source_roi_state() -> dict:
    return {"version": 2, "runs": []}


def load_source_roi_state(path: str | None = None) -> dict:
    """Load aggregate-only ROI history. Corrupt/missing state must never block Daily."""
    state_path = path or SOURCE_ROI_STATE_PATH
    if not ENABLE_SOURCE_ROI_LEARNING:
        return _empty_source_roi_state()
    try:
        with open(state_path, "r", encoding="utf-8") as handle:
            state = json.load(handle)
        if not isinstance(state, dict) or not isinstance(state.get("runs", []), list):
            raise ValueError("invalid source ROI state schema")
        state.setdefault("version", 1)
        state.setdefault("runs", [])
        # v1 mixed provider outages into source quality denominators. Do not perpetuate that bias.
        if int(state.get("version", 1) or 1) < 2:
            logger.warning("[SOURCE ROI] legacy v1 state ignored to prevent provider-outage learning contamination")
            return _empty_source_roi_state()
        return state
    except FileNotFoundError:
        return _empty_source_roi_state()
    except Exception as exc:
        logger.warning("[SOURCE ROI] state load failed; cold-start fallback: %s", exc)
        return _empty_source_roi_state()


def _source_roi_smoothed_rate(success: float, total: float, prior_rate: float, prior_weight: float) -> float:
    total = max(0.0, float(total or 0.0))
    success = max(0.0, float(success or 0.0))
    return max(0.0, min(1.0, (success + prior_rate * prior_weight) / (total + prior_weight)))


def compute_source_roi_profile(state: dict | None) -> dict[str, dict]:
    """Compute recency-weighted, Bayesian-smoothed source yield without touching quality scores."""
    runs = list((state or {}).get("runs", []))[-max(1, SOURCE_ROI_HISTORY_RUNS):]
    aggregate = {
        src: {"screened": 0.0, "stock_saved": 0.0, "deep_dive_attempted": 0.0,
              "generation_requests": 0.0, "ready": 0.0, "review": 0.0}
        for src in SOURCE_ROI_SOURCES
    }
    decay = max(0.0, min(1.0, SOURCE_ROI_RECENCY_DECAY))
    for age, run in enumerate(reversed(runs)):
        weight = decay ** age
        metrics = run.get("sources", {}) if isinstance(run, dict) else {}
        for src in SOURCE_ROI_SOURCES:
            row = metrics.get(src, {}) if isinstance(metrics, dict) else {}
            for key in aggregate[src]:
                try:
                    aggregate[src][key] += max(0.0, float(row.get(key, 0) or 0)) * weight
                except (TypeError, ValueError):
                    pass

    result: dict[str, dict] = {}
    mature_count = 0
    for src, row in aggregate.items():
        stock_rate = _source_roi_smoothed_rate(row["stock_saved"], row["screened"], 0.35, 20.0)
        ready_rate = _source_roi_smoothed_rate(row["ready"], row["deep_dive_attempted"], 0.25, 6.0)
        efficiency_rate = _source_roi_smoothed_rate(row["ready"], row["generation_requests"], 0.18, 6.0)
        total_weight = max(1e-9, SOURCE_ROI_STOCK_WEIGHT + SOURCE_ROI_READY_WEIGHT + SOURCE_ROI_EFFICIENCY_WEIGHT)
        score = 100.0 * (
            stock_rate * SOURCE_ROI_STOCK_WEIGHT
            + ready_rate * SOURCE_ROI_READY_WEIGHT
            + efficiency_rate * SOURCE_ROI_EFFICIENCY_WEIGHT
        ) / total_weight
        mature = (
            row["screened"] >= max(1, SOURCE_ROI_MIN_SCREENED)
            and row["deep_dive_attempted"] >= max(1, SOURCE_ROI_MIN_DEEP_DIVE_ATTEMPTS)
        )
        if mature:
            mature_count += 1
        # Exploration bonus is deliberately small; mandatory floors are the main anti-starvation guard.
        exploration = min(1.0, 1.0 / ((1.0 + row["screened"] / max(1, SOURCE_ROI_MIN_SCREENED)) ** 0.5))
        allocation_weight = max(
            0.05,
            (1.0 - max(0.0, min(0.5, SOURCE_ROI_EXPLORATION_WEIGHT))) * (score / 100.0)
            + max(0.0, min(0.5, SOURCE_ROI_EXPLORATION_WEIGHT)) * exploration,
        )
        result[src] = {
            **row, "stock_yield": round(stock_rate, 4), "ready_yield": round(ready_rate, 4),
            "generation_efficiency": round(efficiency_rate, 4), "roi_score": round(score, 2),
            "allocation_weight": round(allocation_weight, 6), "mature": mature,
        }
    learning_active = ENABLE_SOURCE_ROI_LEARNING and mature_count >= max(1, SOURCE_ROI_MIN_MATURE_SOURCES)
    for row in result.values():
        row["learning_active"] = learning_active
    return result


def allocate_source_fetch_limits(profile: dict[str, dict] | None, total_limit: int | None = None) -> dict[str, int]:
    """Allocate collection/screening slots while guaranteeing each mandatory Source a floor."""
    base = _source_base_fetch_limits()
    if not ENABLE_SOURCE_ROI_LEARNING or not profile or not any(row.get("learning_active") for row in profile.values()):
        return base

    total = max(0, int(MAX_SCREENING_CANDIDATES if total_limit is None else total_limit))
    caps = {
        src: max(base.get(src, 0), max(0, int(SOURCE_ROI_MAX_FETCH_BY_SOURCE.get(src, base.get(src, 0)))))
        for src in SOURCE_ROI_SOURCES
    }
    floors = {src: min(caps[src], max(0, SOURCE_ROI_MIN_FETCH_PER_SOURCE)) for src in SOURCE_ROI_SOURCES}
    if sum(floors.values()) > total:
        # An unusually small global cap must preserve round-robin fairness rather than inventing source priority.
        return {src: min(base[src], max(0, total // len(SOURCE_ROI_SOURCES))) for src in SOURCE_ROI_SOURCES}

    allocation = dict(floors)
    remaining = min(total, sum(caps.values())) - sum(allocation.values())
    while remaining > 0:
        available = [src for src in SOURCE_ROI_SOURCES if allocation[src] < caps[src]]
        if not available:
            break
        weight_sum = sum(max(0.0001, float((profile.get(src) or {}).get("allocation_weight", 0.5))) for src in available)
        proposed = {}
        fractions = []
        for src in available:
            weight = max(0.0001, float((profile.get(src) or {}).get("allocation_weight", 0.5)))
            exact = remaining * weight / weight_sum
            room = caps[src] - allocation[src]
            add = min(room, int(exact))
            proposed[src] = add
            fractions.append((exact - int(exact), weight, src))
        used = sum(proposed.values())
        for src, add in proposed.items():
            allocation[src] += add
        remaining -= used
        if remaining <= 0:
            break
        # Largest-remainder allocation, still respecting caps.
        progressed = False
        for _frac, _weight, src in sorted(fractions, reverse=True):
            if remaining <= 0:
                break
            if allocation[src] < caps[src]:
                allocation[src] += 1
                remaining -= 1
                progressed = True
        if not progressed and used == 0:
            break
    return allocation


def build_source_roi_run_metrics(screened: list[dict] | None, funnel: "DeepDiveGateFunnel | None") -> dict:
    metrics = {
        src: {"screened": 0, "stock_saved": 0, "deep_dive_attempted": 0,
              "generation_requests": 0, "ready": 0, "review": 0,
              "quality_failed": 0, "pending_retry": 0}
        for src in SOURCE_ROI_SOURCES
    }
    for item in screened or []:
        src = item.get("repo", {}).get("source")
        if src not in metrics or item.get("screening_status") != "completed":
            continue
        metrics[src]["screened"] += 1
        if item.get("notion_page_id"):
            metrics[src]["stock_saved"] += 1
    for record in (funnel.records if funnel else []):
        src = record.get("source")
        if src not in metrics:
            continue
        reason_codes = {row.get("reason_code") for row in record.get("reason_codes", []) if isinstance(row, dict)}
        provider_or_budget_failure = bool(reason_codes & {
            REASON_CODE_MODEL_UNAVAILABLE, REASON_CODE_DEEP_DIVE_RUN_BUDGET_EXHAUSTED
        }) or record.get("error_category") in {"provider_unavailable", "quota", "timeout", "budget"}
        # Source ROI learns editorial/source yield, not Gemini availability. Provider/quota/budget failures
        # are excluded from attempt/request denominators so a 503 cannot reduce future source collection.
        if not provider_or_budget_failure:
            metrics[src]["deep_dive_attempted"] += 1
            metrics[src]["generation_requests"] += max(0, int(record.get("generation_request_count", 0) or 0))
        status = record.get("final_status")
        if status == ARTICLE_STATUS_READY:
            metrics[src]["ready"] += 1
        elif status == ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW:
            metrics[src]["review"] += 1
        elif status == CONTENT_STATUS_QUALITY_FAILED:
            metrics[src]["quality_failed"] += 1
        elif status == CONTENT_STATUS_PENDING_RETRY:
            metrics[src]["pending_retry"] += 1
    return metrics


def _upload_source_roi_state_to_github(local_path: str) -> str | None:
    if not EYECATCH_GITHUB_REPO or not GH_PAT:
        logger.warning("[SOURCE ROI UPLOAD SKIP] GitHub repository/token unavailable")
        return None
    dest_path = f"{SOURCE_ROI_GITHUB_DIR}/source_roi_state.json"
    api_url = f"https://api.github.com/repos/{EYECATCH_GITHUB_REPO}/contents/{dest_path}"
    try:
        with open(local_path, "rb") as handle:
            content_b64 = base64.b64encode(handle.read()).decode("utf-8")
        headers = {"Authorization": f"Bearer {GH_PAT}", "Accept": "application/vnd.github+json"}
        current = requests.get(api_url, headers=headers, params={"ref": EYECATCH_GITHUB_BRANCH}, timeout=15)
        payload = {"message": "chore: update source ROI state", "content": content_b64, "branch": EYECATCH_GITHUB_BRANCH}
        if current.status_code == 200:
            payload["sha"] = current.json().get("sha")
        put_res = requests.put(api_url, headers=headers, json=payload, timeout=30)
        if put_res.status_code not in (200, 201):
            logger.error("[SOURCE ROI UPLOAD FAILED] %s", put_res.text[:300])
            return None
        return f"https://raw.githubusercontent.com/{EYECATCH_GITHUB_REPO}/{EYECATCH_GITHUB_BRANCH}/{dest_path}"
    except Exception as exc:
        logger.error("[SOURCE ROI UPLOAD EXCEPTION] %s", exc)
        return None


def update_source_roi_state(state: dict | None, screened: list[dict] | None,
                            funnel: "DeepDiveGateFunnel | None", persist: bool = True) -> dict:
    if not ENABLE_SOURCE_ROI_LEARNING:
        return state or _empty_source_roi_state()
    updated = dict(state or _empty_source_roi_state())
    runs = list(updated.get("runs", []))
    run_metrics = build_source_roi_run_metrics(screened, funnel)
    runs.append({
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "sources": run_metrics,
    })
    updated["version"] = 2
    updated["runs"] = runs[-max(1, SOURCE_ROI_HISTORY_RUNS):]
    updated["profile"] = compute_source_roi_profile(updated)
    if persist:
        try:
            directory = os.path.dirname(SOURCE_ROI_STATE_PATH)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(SOURCE_ROI_STATE_PATH, "w", encoding="utf-8") as handle:
                json.dump(updated, handle, ensure_ascii=False, indent=2)
            _upload_source_roi_state_to_github(SOURCE_ROI_STATE_PATH)
        except Exception as exc:
            logger.error("[SOURCE ROI SAVE FAILED] %s", exc)
    return updated


def log_source_roi_profile(profile: dict[str, dict], fetch_limits: dict[str, int] | None = None) -> None:
    if not ENABLE_SOURCE_ROI_LEARNING:
        return
    limits = fetch_limits or {}
    for src in SOURCE_ROI_SOURCES:
        row = profile.get(src, {})
        logger.info(
            "[SOURCE ROI] %s score=%.1f mature=%s stock=%.3f ready=%.3f efficiency=%.3f fetch=%s",
            src, float(row.get("roi_score", 50.0)), bool(row.get("mature")),
            float(row.get("stock_yield", 0.35)), float(row.get("ready_yield", 0.25)),
            float(row.get("generation_efficiency", 0.18)), limits.get(src, "base"),
        )


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


def _bounded_optional_score(value, candidate_id: str, field: str, invalid: list[str]) -> int | None:
    """Parse an optional 0-100 profit metadata score without invalidating the core row."""
    if value is None:
        invalid.append(f"missing_{field}:{candidate_id}")
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        invalid.append(f"invalid_{field}:{candidate_id}")
        return None
    if not 0 <= parsed <= 100:
        invalid.append(f"{field}_out_of_range:{candidate_id}")
        return None
    return parsed


def shelf_life_label(score: int | float | None) -> str:
    """Map a numeric shelf-life estimate into FLASH / TREND / EVERGREEN."""
    try:
        value = max(0, min(100, int(score)))
    except (TypeError, ValueError):
        value = PROFIT_SCORE_NEUTRAL
    if value <= 34:
        return "FLASH"
    if value <= 69:
        return "TREND"
    return "EVERGREEN"


def deep_dive_priority_score(decision_score: int | float | None, commercial_score: int | float | None) -> float:
    """Profit-aware priority; it never changes Stock eligibility or Quality Gate outcomes."""
    try:
        decision = max(0.0, min(100.0, float(decision_score or 0)))
    except (TypeError, ValueError):
        decision = 0.0
    try:
        commercial = max(0.0, min(100.0, float(commercial_score)))
    except (TypeError, ValueError):
        commercial = float(PROFIT_SCORE_NEUTRAL)
    decision_weight = max(0.0, DEEP_DIVE_DECISION_WEIGHT)
    commercial_weight = max(0.0, DEEP_DIVE_COMMERCIAL_WEIGHT)
    total_weight = decision_weight + commercial_weight
    if total_weight <= 0:
        return round(decision, 2)
    return round((decision * decision_weight + commercial * commercial_weight) / total_weight, 2)


def _attach_profit_metadata(item: dict, commercial_score: int | None, shelf_life_score: int | None) -> dict:
    try:
        commercial = PROFIT_SCORE_NEUTRAL if commercial_score is None else max(0, min(100, int(commercial_score)))
    except (TypeError, ValueError):
        commercial = PROFIT_SCORE_NEUTRAL
    try:
        shelf = PROFIT_SCORE_NEUTRAL if shelf_life_score is None else max(0, min(100, int(shelf_life_score)))
    except (TypeError, ValueError):
        shelf = PROFIT_SCORE_NEUTRAL
    item["commercial_score"] = commercial
    item["shelf_life_score"] = shelf
    item["shelf_life"] = shelf_life_label(shelf)
    item["deep_dive_priority_score"] = deep_dive_priority_score(item.get("score"), commercial)
    return item


def normalize_portfolio_topic(value) -> str:
    """Normalize topic metadata without making missing auxiliary data fatal."""
    topic = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "MODELS": "MODEL", "AI_MODEL": "MODEL", "AI_MODELS": "MODEL",
        "AGENTS": "AGENT", "AUTOMATION": "AGENT",
        "DEVTOOL": "DEVTOOLS", "DEVELOPER_TOOLS": "DEVTOOLS",
        "INFRASTRUCTURE": "INFRA", "PLATFORM": "INFRA", "MLOPS": "INFRA",
        "RETRIEVAL": "DATA", "RAG": "DATA", "DATA_RETRIEVAL": "DATA",
        "SAFETY": "SECURITY", "PRIVACY": "SECURITY", "GOVERNANCE": "SECURITY",
        "VISION": "MULTIMODAL", "AUDIO": "MULTIMODAL", "ROBOTICS": "MULTIMODAL",
        "BUSINESS": "PRODUCT", "SAAS": "PRODUCT",
        "RESEARCH": "OTHER", "UNKNOWN": "OTHER", "": "OTHER",
    }
    topic = aliases.get(topic, topic)
    return topic if topic in PORTFOLIO_TOPICS else "OTHER"


def _attach_portfolio_topic(item: dict, topic=None, raw_topic=None) -> dict:
    normalized = normalize_portfolio_topic(topic if topic is not None else item.get("portfolio_topic"))
    item["portfolio_topic"] = normalized
    if raw_topic is not None and "raw_portfolio_topic" not in item:
        item["raw_portfolio_topic"] = normalize_portfolio_topic(raw_topic)
    return item


def _salvage_screening_json_rows(text: str) -> list[dict]:
    """Recover complete JSON objects from a truncated/partially malformed JSON array.

    Gemini may return HTTP 200 yet cut the tail of a long array.  We never guess or repair a
    partial object; only individually valid, balanced JSON objects are accepted.  Missing IDs are
    then handled by the existing smaller recovery batches.
    """
    rows: list[dict] = []
    src = text or ""
    depth = 0
    start = None
    in_string = False
    escaped = False
    for i, ch in enumerate(src):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    row = json.loads(src[start:i + 1])
                    if isinstance(row, dict):
                        rows.append(row)
                except json.JSONDecodeError:
                    pass
                start = None
    return rows


def _parse_batch_screening_response(text: str, expected_ids: set[str], include_diagnostic: bool = False):
    diagnostic_parts: list[str] = []
    try:
        payload = json.loads(text or "[]")
    except json.JSONDecodeError as exc:
        payload = _salvage_screening_json_rows(text or "")
        diagnostic_parts.append(f"json_decode_error:{exc.msg}")
        diagnostic_parts.append(f"salvaged={len(payload)}")

    parsed: dict[str, dict] = {}
    if not isinstance(payload, list):
        diagnostic_parts.append("response_not_list")
        payload = []

    invalid: list[str] = []
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
        commercial_score = _bounded_optional_score(row.get("commercial_score"), candidate_id, "commercial_score", invalid)
        shelf_life_score = _bounded_optional_score(row.get("shelf_life_score"), candidate_id, "shelf_life_score", invalid)
        tracking_raw = row.get("tracking_eligible")
        if isinstance(tracking_raw, bool):
            tracking_eligible = tracking_raw
        elif isinstance(tracking_raw, str) and tracking_raw.strip().lower() in {"true", "false"}:
            tracking_eligible = tracking_raw.strip().lower() == "true"
        else:
            tracking_eligible = score >= TRACKING_ELIGIBILITY_MIN_SCORE
            invalid.append(f"missing_tracking_eligible:{candidate_id}")
        tracking_reason = str(row.get("tracking_reason", "")).strip()[:160]
        raw_topic = row.get("topic")
        normalized_topic = normalize_portfolio_topic(raw_topic)
        topic_valid = raw_topic is not None
        if raw_topic is None:
            invalid.append(f"missing_topic:{candidate_id}")
            topic_valid = False
        elif normalized_topic == "OTHER" and str(raw_topic).strip().upper() not in {"OTHER", "RESEARCH", "UNKNOWN"}:
            invalid.append(f"invalid_topic:{candidate_id}")
            topic_valid = False
        parsed[candidate_id] = {
            "score": score, "reason": reason,
            "commercial_score": commercial_score, "shelf_life_score": shelf_life_score,
            "tracking_eligible": tracking_eligible, "tracking_reason": tracking_reason,
            "portfolio_topic": normalized_topic, "topic_valid": topic_valid,
        }
    if invalid:
        diagnostic_parts.extend(invalid)
    missing = sorted(expected_ids - set(parsed))
    diagnostic = ";".join(diagnostic_parts)
    return (parsed, missing, diagnostic) if include_diagnostic else (parsed, missing)


def call_screening_provider(prompt: str, kind: str = "screening_batch", request_context: str = ""):
    max_tokens = GLOBAL_CALIBRATION_MAX_OUTPUT_TOKENS if kind == "global_calibration" else SCREENING_BATCH_MAX_OUTPUT_TOKENS
    response, model_name = _call_screening_pool(
        prompt, {"response_mime_type": "application/json", "max_output_tokens": max_tokens}, kind,
        GEMINI_RESERVED_DEEP_DIVE_REQUESTS, request_context=request_context,
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
        "以下の候補を、CTO/PM向け無料noteで読者を獲得し、会員向け意思決定DBへ蓄積する題材として評価せよ。"
        "scoreは従来の品質・意思決定価値スコア（0〜100）で、技術的新規性、実務インパクト、"
        "導入・意思決定への影響、緊急性、市場波及性、情報源の信頼性を総合評価する。"
        "commercial_scoreは独立した商業価値スコア（0〜100）で、読者需要の見込み、意思決定の緊急性、"
        "会員DB転換可能性、継続的な実務需要、商業隣接性をmetadataだけから保守的に推定する。"
        "実アクセス数・検索量・売上など入力にない数値を捏造してはならない。"
        "shelf_life_scoreは0〜100で情報価値の持続性を推定する。"
        "0-34=FLASH(主に1-7日)、35-69=TREND(主に1-4週)、70-100=EVERGREEN(数か月以上)を目安とする。"
        "topicはSource種別ではなく内容の主テーマを MODEL, AGENT, DEVTOOLS, INFRA, DATA, SECURITY, MULTIMODAL, PRODUCT, OTHER のいずれか1つで返す。"
        "tracking_eligibleは記事化価値とは独立し、今後の導入判断・回避判断・成熟度変化を追う価値があるTechnologyならtrueとする。"
        "単に面白い記事という理由ではtrueにせず、逆に記事scoreが低くてもAVOID判断や将来の成熟監視に価値があればtrueにできる。"
        "tracking_reasonはその理由を40字以内で返す。"
        "Sourceが異なる候補間でEngagementの絶対値を直接比較してはならない。"
        "この段階ではURL本文・README・論文全文を推測して使わない。"
        "出力は必ずJSON配列だけ。各要素は id, score, commercial_score, shelf_life_score, topic, tracking_eligible(boolean), tracking_reason（40字以内）, reason（40字以内）とする。\n"
        + json.dumps(rows, ensure_ascii=False)
    )


def _calibration_prompt(batch: list[dict]) -> str:
    rows = []
    for item in batch:
        repo = item["repo"]
        rows.append({"id": item["screening_id"], "source": repo.get("source", ""),
                     "name": repo.get("nameWithOwner", ""), "description": repo.get("description", ""),
                     "raw_score": item.get("raw_score"), "raw_commercial_score": item.get("raw_commercial_score", item.get("commercial_score")),
                     "raw_shelf_life_score": item.get("raw_shelf_life_score", item.get("shelf_life_score")),
                     "raw_topic": item.get("raw_portfolio_topic", item.get("portfolio_topic", "OTHER")),
                     "tracking_eligible": item.get("tracking_eligible", False),
                     "tracking_reason": item.get("tracking_reason", ""),
                     "engagement": repo.get("stargazerCount", 0),
                     "published_at": repo.get("publishedAt"), "url": repo.get("url", "")})
    return (
        "以下は一次Batch審査で55点以上だった候補である。候補群を横断比較し、"
        "Notion Stock候補としての一貫した最終Decision Scoreを返せ。"
        "scoreは技術的新規性、実務インパクト、意思決定への影響、緊急性、情報源の信頼性を評価する。"
        "commercial_scoreは品質スコアと独立して、読者需要の見込み、意思決定の緊急性、会員DB転換可能性、"
        "継続的な実務需要、商業隣接性をmetadataだけから保守的に再評価する。"
        "shelf_life_scoreは情報価値の持続性を0〜100で再評価する。入力にないアクセス数や売上を捏造しない。"
        "topicは主テーマを MODEL, AGENT, DEVTOOLS, INFRA, DATA, SECURITY, MULTIMODAL, PRODUCT, OTHER のいずれか1つで再判定する。"
        "tracking_eligibleは記事価値と独立したTechnology追跡価値で再判定し、tracking_reasonを40字以内で返す。"
        "異Source間でEngagementの絶対値を直接比較してはならない。"
        "出力はJSON配列のみ。各要素は id, score, commercial_score, shelf_life_score, topic, tracking_eligible, tracking_reason, reason（40字以内）。\n"
        + json.dumps(rows, ensure_ascii=False)
    )


def screen_batch(batch: list[dict], *_args, recovery: bool = False, **_kwargs):
    if not batch:
        return [], [], 0
    if not GEMINI_BUDGET.can_request(reserve=GEMINI_RESERVED_DEEP_DIVE_REQUESTS):
        return [], list(batch), 0
    try:
        label = "screening_recovery" if recovery else "screening_batch"
        batch_context = f"{label}:{batch[0]['screening_id']}-{batch[-1]['screening_id']}:n={len(batch)}"
        response = call_screening_provider(_batch_screening_prompt(batch), label, request_context=batch_context)
        parsed, missing, diagnostic = _parse_batch_screening_response(
            getattr(response, "text", ""), {item["screening_id"] for item in batch}, include_diagnostic=True,
        )
        if diagnostic:
            logger.warning("[BATCH SCREENING] %s", diagnostic)
        completed = []
        for item in batch:
            row = parsed.get(item["screening_id"])
            if row:
                raw_commercial = PROFIT_SCORE_NEUTRAL if row.get("commercial_score") is None else row.get("commercial_score")
                raw_shelf = PROFIT_SCORE_NEUTRAL if row.get("shelf_life_score") is None else row.get("shelf_life_score")
                completed_item = {"repo": item["repo"], "screening_id": item["screening_id"],
                                  "raw_score": row["score"], "final_score": row["score"],
                                  "raw_commercial_score": raw_commercial, "raw_shelf_life_score": raw_shelf,
                                  "raw_portfolio_topic": row.get("portfolio_topic", "OTHER"),
                                  "portfolio_topic": row.get("portfolio_topic", "OTHER"),
                                  "score": row["score"], "reason": row["reason"],
                                  "tracking_eligible": bool(row.get("tracking_eligible")),
                                  "tracking_reason": row.get("tracking_reason") or row["reason"],
                                  "calibrated": False, "screening_status": "completed"}
                _attach_profit_metadata(completed_item, raw_commercial, raw_shelf)
                completed.append(_attach_portfolio_topic(completed_item, row.get("portfolio_topic"), row.get("portfolio_topic")))
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
                failed_item = {"repo": item["repo"], "screening_id": item["screening_id"],
                                  "raw_score": None, "final_score": None, "score": 0,
                                  "reason": "Screening APIで判定できなかった", "calibrated": False,
                                  "screening_status": "failed", "error_category": "quota_or_transport"}
                _attach_profit_metadata(failed_item, None, None)
                completed.append(_attach_portfolio_topic(failed_item, "OTHER", "OTHER"))
    else:
        for item in missing:
            failed_item = {"repo": item["repo"], "screening_id": item["screening_id"],
                              "raw_score": None, "final_score": None, "score": 0,
                              "reason": "Screening APIで判定できなかった", "calibrated": False,
                              "screening_status": "failed", "error_category": "quota_or_transport"}
            completed.append(_attach_profit_metadata(failed_item, None, None))
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
            batch_context = f"global_calibration:{batch[0]['screening_id']}-{batch[-1]['screening_id']}:n={len(batch)}"
            response = call_screening_provider(
                _calibration_prompt(batch), "global_calibration", request_context=batch_context
            )
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
                    if row.get("commercial_score") is not None:
                        item["commercial_score"] = row["commercial_score"]
                    if row.get("shelf_life_score") is not None:
                        item["shelf_life_score"] = row["shelf_life_score"]
                    if row.get("topic_valid"):
                        item["portfolio_topic"] = row["portfolio_topic"]
                    item["tracking_eligible"] = bool(row.get("tracking_eligible", item.get("tracking_eligible", False)))
                    item["tracking_reason"] = row.get("tracking_reason") or item.get("tracking_reason") or item.get("reason", "")
                    _attach_profit_metadata(item, item.get("commercial_score"), item.get("shelf_life_score"))
                    _attach_portfolio_topic(item, item.get("portfolio_topic"), item.get("raw_portfolio_topic"))
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
                          calibration_calls: int = 0, total_collected: int | None = None,
                          source_roi_profile: dict | None = None, source_fetch_limits: dict | None = None) -> str | None:
    if not ENABLE_OBSERVED_HISTORY:
        return None
    os.makedirs(OBSERVED_HISTORY_DIR, exist_ok=True)
    path = os.path.join(OBSERVED_HISTORY_DIR, f"screening_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
    observed_items = [{"id": item.get("screening_id"), "source": item["repo"].get("source"),
                       "name": item["repo"].get("nameWithOwner"), "url": item["repo"].get("url"),
                       "published_at": item["repo"].get("publishedAt"), "engagement": item["repo"].get("stargazerCount", 0),
                       "raw_screening_score": item.get("raw_score"), "final_screening_score": item.get("final_score"),
                       "raw_commercial_value_score": item.get("raw_commercial_score"),
                       "commercial_value_score": item.get("commercial_score"),
                       "raw_shelf_life_score": item.get("raw_shelf_life_score"),
                       "shelf_life_score": item.get("shelf_life_score"), "shelf_life": item.get("shelf_life"),
                       "raw_portfolio_topic": item.get("raw_portfolio_topic"),
                       "portfolio_topic": item.get("portfolio_topic", "OTHER"),
                       "deep_dive_priority_score": item.get("deep_dive_priority_score"),
                       "screening_reason": item.get("reason"), "calibrated": item.get("calibrated", False),
                       "screening_status": item.get("screening_status"), "error_category": item.get("error_category"),
                       "stock_eligible": (item.get("score") or 0) >= NOTION_SAVE_THRESHOLD_SCORE,
                       "stock_persisted": bool(item.get("notion_page_id")),
                       "stocked": bool(item.get("notion_page_id")) if "notion_page_id" in item else (item.get("score") or 0) >= NOTION_SAVE_THRESHOLD_SCORE} for item in items]
    payload = {"run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
               "analyzed_at": datetime.now(timezone.utc).isoformat(), "total_collected": total_collected,
               "total_screened": len(items), "stock_threshold": NOTION_SAVE_THRESHOLD_SCORE,
               "batch_calls": batch_calls, "recovery_calls": recovery_calls, "calibration_calls": calibration_calls,
               "source_roi": {
                   "enabled": ENABLE_SOURCE_ROI_LEARNING,
                   "fetch_limits": dict(source_fetch_limits or {}),
                   "profile": dict(source_roi_profile or {}),
               },
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
    STALE_THRESHOLD_DAYSの意味は「最後の正常なReady記事から何日経過したか」。
    Needs Editorial ReviewもStatus/Content Status上はDeep Diveとして内部保存されるため、
    Content Status=Deep Diveを条件に含めるとReady=0が長期間続いてもReview記事が
    stale警告を隠してしまう。したがってArticle Status=Readyだけを対象にする。

    注意: これは購読者への告知ではない。運用者が「そろそろ購読者への
    説明を検討すべきか」を判断するためのトリガーに過ぎない。
    """
    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID):
        logger.warning("Notion未設定のため滞留検知をスキップします。")
        return

    url = _notion_query_url()
    headers = _notion_headers()
    payload = {
        "filter": {"property": PROP_ARTICLE_STATUS, "select": {"equals": ARTICLE_STATUS_READY}},
        "sorts": [{"property": PROP_ANALYZED_AT, "direction": "descending"}],
        "page_size": 1,
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code != 200:
            logger.error(f"[STALE CHECK] Notion問い合わせ失敗: {res.text}")
            return

        results = res.json().get("results", [])
        if not results:
            # Ready記事が1件も存在しない = 最悪のstale状態。Review記事では代替しない。
            logger.warning("[STALE CHECK] Ready記事が1件も見つかりません。")
            send_telegram_alert(
                "🟡【運用確認】Ready記事が1件も見つかりません。"
                "パイプラインの異常有無を確認してください。"
            )
            return

        props = results[0].get("properties", {})
        analyzed_at_str = (props.get(PROP_ANALYZED_AT, {}).get("date") or {}).get("start")
        if not analyzed_at_str:
            logger.warning("[STALE CHECK] 最新Ready記事にAnalyzed Atが設定されていません。")
            return
        latest_analyzed = datetime.fromisoformat(analyzed_at_str.replace("Z", "+00:00"))
        days_since = (datetime.now(timezone.utc) - latest_analyzed.astimezone(timezone.utc)).days

        logger.info(f"[STALE CHECK] 最終Ready記事から {days_since} 日経過（閾値 {STALE_THRESHOLD_DAYS} 日）")

        if days_since >= STALE_THRESHOLD_DAYS:
            send_telegram_alert(
                f"🟡【運用確認】最終Ready記事から {days_since} 日が経過しています"
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

    if REGEN_TEST_ARTICLE_SET not in {"fixed", "fresh"}:
        raise ValueError("REGEN_TEST_ARTICLE_SET must be fixed or fresh")
    if REGEN_TEST_ARTICLE_SET == "fresh":
        logger.warning(" REGEN ARTICLE SET: FRESH（新規候補・0-API選定）")
        items = get_fresh_regen_test_items(REGEN_TEST_LIMIT, REGEN_TEST_SOURCE)
    else:
        logger.warning(" REGEN ARTICLE SET: FIXED（既存Deep Dive A/B比較）")
        items = get_regen_test_items(REGEN_TEST_LIMIT, REGEN_TEST_SOURCE)
    if items is None:
        logger.error("[REGEN TEST ABORTED] 回帰テスト候補の読み出し/収集に失敗しました。")
        logger.info(GEMINI_BUDGET.summary())
        logger.info(DEEP_DIVE_MODEL_BUDGET.summary())
        logger.info(PENDING_RETRY_REQUEST_BUDGET.summary())
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
        # 未公開原稿全文はWorkflow Logへ出さない。private artifactだけに保持する。
        logger.info(
            "[REGEN TEST ARTICLE SAVED] %s status=%s chars=%d output_dir=%s",
            name, regen_status, len(manuscript), REGEN_TEST_OUTPUT_DIR,
        )

    logger.info(
        f"[REGEN TEST COMPLETE] ACCEPTED {accepted} / REJECTED {rejected} / "
        f"GENERATED {generated} / TOTAL {len(items)}"
    )
    logger.info(f"[REGEN TEST OUTPUT] {REGEN_TEST_OUTPUT_DIR}/")
    logger.info(GEMINI_BUDGET.summary())
    logger.info(DEEP_DIVE_MODEL_BUDGET.summary())
    logger.info(PENDING_RETRY_REQUEST_BUDGET.summary())
    logger.info(PRODUCT_REVIEW_REQUEST_BUDGET.summary())
    logger.info(GEMINI_USAGE_AUDIT.summary(include_contexts=True))
    logger.info(PERSISTENT_GEMINI_COUNTER.summary())


# ==========================================
def _notion_writable_rich_text(items: list[dict] | None) -> list[dict]:
    """Notion read responseのrich_text/title要素からwrite可能な最小表現だけを残す。"""
    writable: list[dict] = []
    for item in items or []:
        kind = item.get("type") or "text"
        if kind == "text":
            text = item.get("text") or {}
            content = text.get("content")
            if content is None:
                content = item.get("plain_text", "")
            row = {"type": "text", "text": {"content": str(content or "")}}
            if text.get("link"):
                row["text"]["link"] = text.get("link")
            annotations = item.get("annotations")
            if isinstance(annotations, dict):
                row["annotations"] = {
                    k: annotations[k] for k in (
                        "bold", "italic", "strikethrough", "underline", "code", "color"
                    ) if k in annotations
                }
            writable.append(row)
        elif kind == "equation" and (item.get("equation") or {}).get("expression") is not None:
            writable.append({"type": "equation", "equation": {"expression": item["equation"]["expression"]}})
        # mention等はこのPipelineの公開プロパティでは生成しない。response-only objectを
        # 無理にwriteして同期全体を壊すより、安全に落とす。
    return writable


def _notion_property_for_write(prop: dict, prop_type: str) -> dict:
    """Notion page read responseをCreate/Update Pageで許容されるproperty payloadへ変換。"""
    if prop_type == "title":
        return {"title": _notion_writable_rich_text(prop.get("title"))}
    if prop_type == "rich_text":
        return {"rich_text": _notion_writable_rich_text(prop.get("rich_text"))}
    if prop_type == "url":
        return {"url": prop.get("url")}
    if prop_type == "number":
        return {"number": prop.get("number")}
    if prop_type == "select":
        selected = prop.get("select")
        return {"select": ({"name": selected.get("name")} if selected and selected.get("name") else None)}
    if prop_type == "status":
        selected = prop.get("status")
        return {"status": ({"name": selected.get("name")} if selected and selected.get("name") else None)}
    if prop_type == "date":
        date = prop.get("date")
        if not date:
            return {"date": None}
        return {"date": {k: date.get(k) for k in ("start", "end", "time_zone") if date.get(k) is not None}}
    if prop_type == "checkbox":
        return {"checkbox": bool(prop.get("checkbox"))}
    raise ValueError(f"Unsupported public DB property type for safe copy: {prop_type}")


def sync_public_approved_to_member_db() -> None:
    """Internal DBをSource of Truthとして会員公開DBをreconcileする。

    Ready AND Public Approvedだけをcreate/updateし、一度公開後に承認取消・Review・
    Quality Failed等へ変わった内部レコードは会員DB側をarchiveする。会員DBに手動で
    追加されたURL（内部DBに対応URLが存在しないもの）は勝手に削除しない。
    """
    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID) or not (NOTION_PUBLIC_DATA_SOURCE_ID or NOTION_PUBLIC_DATABASE_ID):
        raise ValueError("PUBLIC_DB_SYNC_MODEには NOTION_API_KEY / NOTION_DATA_SOURCE_ID（またはDATABASE_ID） / NOTION_PUBLIC_DATA_SOURCE_ID（またはDATABASE_ID）が必要です。")
    headers = _notion_headers()
    source_url = _notion_query_url()
    public_url = _notion_query_url(NOTION_PUBLIC_DATA_SOURCE_ID, NOTION_PUBLIC_DATABASE_ID)

    def fetch_all(query_url: str, base_payload: dict | None = None) -> list[dict]:
        pages: list[dict] = []
        payload = dict(base_payload or {})
        payload.setdefault("page_size", 100)
        while True:
            res = requests.post(query_url, json=payload, headers=headers, timeout=20)
            res.raise_for_status()
            body = res.json()
            pages.extend(body.get("results", []))
            if not body.get("has_more"):
                return pages
            payload["start_cursor"] = body.get("next_cursor")

    eligible_filter = {
        "filter": {"and": [
            {"property": PROP_REVIEW_STATUS, "status": {"equals": REVIEW_STATUS_PUBLIC_APPROVED}},
            {"property": PROP_ARTICLE_STATUS, "select": {"equals": ARTICLE_STATUS_READY}},
        ]},
        "page_size": 100,
    }
    approved = fetch_all(source_url, eligible_filter)
    # revoke対象を安全に特定するため、内部DB全URLも取得する。
    internal_pages = fetch_all(source_url, {"page_size": 100})

    schema_res = requests.get(
        _notion_schema_url(NOTION_PUBLIC_DATA_SOURCE_ID, NOTION_PUBLIC_DATABASE_ID),
        headers=headers, timeout=20,
    )
    schema_res.raise_for_status()
    destination_schema = schema_res.json().get("properties", {})
    destination_properties = set(destination_schema.keys())
    if PROP_URL not in destination_properties or (destination_schema.get(PROP_URL) or {}).get("type") != "url":
        raise ValueError("会員公開DBにはURL（URL型）列が必要です。")
    public_names = {
        PROP_NAME, PROP_URL, PROP_SOURCE, PROP_SCORE, PROP_DECISION, PROP_DECISION_REASON,
        PROP_WHAT, PROP_WHY_IMPORTANT, PROP_WHY_NOT_IMPORTANT, PROP_ACTION, PROP_PARADIGM_SHIFT,
        PROP_ALTERNATIVE_COMPARISON, PROP_MIGRATION_COST, PROP_WHO_SHOULD_USE,
        PROP_WHO_SHOULD_NOT_USE, PROP_FUTURE_SCENARIO, PROP_EVIDENCE_URLS,
        PROP_GROUNDING_STATUS, PROP_PUBLISHED_AT,
    } & destination_properties
    # Public DBは列を省略してもよいが、同名列がある場合は内部DBと同じ型を要求する。
    # 型違いのまま一部recordだけ同期して止まる partial write をPreflightで防ぐ。
    mismatched_public_types = []
    for prop_name in sorted(public_names):
        expected = NOTION_REQUIRED_PROPERTY_TYPES.get(prop_name)
        actual = (destination_schema.get(prop_name) or {}).get("type")
        if expected and actual and expected != actual:
            mismatched_public_types.append(f"{prop_name}:{actual}!={expected}")
    if mismatched_public_types:
        raise ValueError("会員公開DB schema type mismatch: " + ", ".join(mismatched_public_types))

    destination_pages = fetch_all(public_url, {"page_size": 100})
    public_by_key: dict[str, list[dict]] = {}
    for page in destination_pages:
        url = page.get("properties", {}).get(PROP_URL, {}).get("url") or ""
        if url:
            public_by_key.setdefault(canonicalize_url(url), []).append(page)

    internal_keys = {
        canonicalize_url(page.get("properties", {}).get(PROP_URL, {}).get("url") or "")
        for page in internal_pages
        if page.get("properties", {}).get(PROP_URL, {}).get("url")
    }
    eligible_by_key = {}
    for page in approved:
        record_url = page.get("properties", {}).get(PROP_URL, {}).get("url") or ""
        if record_url:
            eligible_by_key[canonicalize_url(record_url)] = page

    # create/update eligible records; canonical duplicateは1件に集約する。
    for key, page in eligible_by_key.items():
        props = page.get("properties", {})
        record_url = props.get(PROP_URL, {}).get("url")
        copied = {
            prop_name: _notion_property_for_write(
                props.get(prop_name) or {},
                (destination_schema.get(prop_name) or {}).get("type") or NOTION_REQUIRED_PROPERTY_TYPES[prop_name],
            )
            for prop_name in public_names
            if prop_name in props
        }
        existing = public_by_key.get(key, [])
        if existing:
            response = requests.patch(
                f"https://api.notion.com/v1/pages/{existing[0]['id']}",
                json={"properties": copied}, headers=headers, timeout=20,
            )
            action = "UPDATED"
            # 同一canonical URLの重複public pageは余分な方をarchive。
            for duplicate in existing[1:]:
                requests.patch(
                    f"https://api.notion.com/v1/pages/{duplicate['id']}",
                    json={"archived": True}, headers=headers, timeout=20,
                ).raise_for_status()
        else:
            response = requests.post(
                "https://api.notion.com/v1/pages",
                json={"parent": _notion_parent(NOTION_PUBLIC_DATA_SOURCE_ID, NOTION_PUBLIC_DATABASE_ID), "properties": copied},
                headers=headers, timeout=20,
            )
            action = "CREATED"
        response.raise_for_status()
        logger.info("[PUBLIC SYNC %s] %s", action, record_url)

    # 内部DBには存在するが現在eligibleではない公開コピーを失効させる。
    for key, pages in public_by_key.items():
        if key in internal_keys and key not in eligible_by_key:
            for page in pages:
                response = requests.patch(
                    f"https://api.notion.com/v1/pages/{page['id']}",
                    json={"archived": True}, headers=headers, timeout=20,
                )
                response.raise_for_status()
                logger.info("[PUBLIC SYNC ARCHIVED] %s", key)

def _topic_counts(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        topic = normalize_portfolio_topic(item.get("portfolio_topic"))
        if topic == "OTHER":
            continue
        counts[topic] = counts.get(topic, 0) + 1
    return counts


def _apply_content_portfolio_balance(ordered: list[dict], visible_slots: int) -> list[dict]:
    """Conservatively diversify visible Deep Dive slots without weakening quality/profit.

    Only a candidate within PORTFOLIO_TOPIC_PRIORITY_TOLERANCE of the current cutoff can
    displace a duplicate-topic candidate. OTHER is neutral and never forces a replacement.
    The sole EVERGREEN slot is protected when EVERGREEN_PORTFOLIO_MIN is active.
    """
    if not ENABLE_PORTFOLIO_BALANCE or visible_slots <= 1 or len(ordered) <= 1:
        return ordered
    target = min(max(1, PORTFOLIO_MIN_DISTINCT_TOPICS), visible_slots)
    if target <= 1:
        return ordered
    result = list(ordered)
    current = result[:visible_slots]
    current_topics = [normalize_portfolio_topic(item.get("portfolio_topic")) for item in current]
    # Auxiliary topic metadata is intentionally non-blocking. If the visible set contains
    # OTHER/unknown, do not infer a diversity deficit and reorder on incomplete metadata.
    if any(topic == "OTHER" for topic in current_topics):
        return result
    counts = _topic_counts(current)
    if len(counts) >= target:
        return result
    cutoff = float(current[-1].get("deep_dive_priority_score", current[-1].get("score", 0)))
    evergreen_count = sum(1 for item in current if item.get("shelf_life") == "EVERGREEN")
    protected_evergreen = min(max(0, EVERGREEN_PORTFOLIO_MIN), visible_slots) > 0 and evergreen_count <= 1

    for candidate_idx in range(visible_slots, len(result)):
        candidate = result[candidate_idx]
        topic = normalize_portfolio_topic(candidate.get("portfolio_topic"))
        if topic == "OTHER" or topic in counts:
            continue
        priority = float(candidate.get("deep_dive_priority_score", candidate.get("score", 0)))
        if priority + max(0.0, PORTFOLIO_TOPIC_PRIORITY_TOLERANCE) < cutoff:
            continue
        replace_idx = None
        current_counts = _topic_counts(result[:visible_slots])
        for idx in range(visible_slots - 1, -1, -1):
            existing = result[idx]
            existing_topic = normalize_portfolio_topic(existing.get("portfolio_topic"))
            if existing_topic == "OTHER" or current_counts.get(existing_topic, 0) > 1:
                if protected_evergreen and existing.get("shelf_life") == "EVERGREEN":
                    continue
                replace_idx = idx
                break
        if replace_idx is None:
            break
        selected = result.pop(candidate_idx)
        displaced = result.pop(replace_idx)
        result.insert(replace_idx, selected)
        result.insert(candidate_idx, displaced)
        current = result[:visible_slots]
        counts = _topic_counts(current)
        if len(counts) >= target:
            break
    return result



def publication_probability_score(item: dict) -> int:
    """Rule-based probability proxy for reaching Ready, using metadata only and 0 Gemini calls.

    This is not a quality score. It rewards direct primary-source surfaces and complete metadata so
    TOP_N contains at least one candidate that is realistically finishable today.
    """
    repo = (item or {}).get("repo", {}) or {}
    source = str(repo.get("source") or "GitHub")
    url = str(repo.get("primaryUrl") or repo.get("url") or "")
    host = (urlparse(url).hostname or "").lower()
    desc = str(repo.get("description") or "").strip()
    score = {"ArXiv": 78, "GitHub": 74, "HackerNews": 52, "ProductHunt": 50}.get(source, 48)
    if source == "ArXiv" and "arxiv.org" in host:
        score += 12
    elif source == "GitHub" and host in {"github.com", "www.github.com"}:
        score += 10
    elif source == "HackerNews" and host and "ycombinator.com" not in host:
        score += 18
    elif source == "ProductHunt" and host and "producthunt.com" not in host:
        score += 18
    if len(desc) >= 160:
        score += 8
    elif len(desc) >= 60:
        score += 5
    elif desc:
        score += 2
    if repo.get("publishedAt"):
        score += 3
    if source == "GitHub":
        spdx = str(((repo.get("licenseInfo") or {}).get("spdxId") or "")).upper()
        if spdx and spdx not in {"NOASSERTION", "UNLICENSED", "UNLICENSE"}:
            score += 3
    return max(0, min(100, int(round(score))))


def _apply_publication_reliability_slot(ordered: list[dict], visible_slots: int) -> list[dict]:
    if not ENABLE_PUBLICATION_RELIABILITY_SLOT or PUBLICATION_RELIABILITY_SLOTS <= 0 or visible_slots <= 0:
        return ordered
    for item in ordered:
        item["publication_probability_score"] = publication_probability_score(item)
    qualified = [
        (idx, item) for idx, item in enumerate(ordered)
        if float(item.get("score") or 0) >= PUBLICATION_RELIABILITY_MIN_DECISION_SCORE
    ]
    if not qualified:
        return ordered
    # One slot is intentionally enough: the remaining visible slots stay optimized for business value.
    best_idx, best = max(
        qualified,
        key=lambda pair: (pair[1].get("publication_probability_score", 0),
                          pair[1].get("deep_dive_priority_score", 0), pair[1].get("score", 0)),
    )
    if best_idx < visible_slots:
        return ordered
    current = ordered[:visible_slots]
    current_best_publishability = max((x.get("publication_probability_score", 0) for x in current), default=0)
    if best.get("publication_probability_score", 0) < current_best_publishability + PUBLICATION_RELIABILITY_MIN_ADVANTAGE:
        return ordered
    selected = ordered.pop(best_idx)
    ordered.insert(visible_slots - 1, selected)
    logger.info(
        "[PUBLICATION RELIABILITY SLOT] promoted=%s publishability=%s decision=%s",
        selected.get("repo", {}).get("nameWithOwner"), selected.get("publication_probability_score"), selected.get("score"),
    )
    return ordered


def _select_stocked_deep_dive_candidates(screened: list[dict]) -> list[dict]:
    """Select only persisted Stock, then order it for profit without weakening quality.

    Eligibility is unchanged: Decision Score >= stock threshold AND successful Notion persistence.
    Commercial Value only reorders eligible Stock. Shelf life adds one conservative portfolio rule:
    if the visible TOP_N contains no EVERGREEN, an EVERGREEN can enter only when its priority is
    within EVERGREEN_PRIORITY_TOLERANCE points of the current cutoff.
    """
    eligible = [
        item for item in screened
        if item.get("score", 0) >= NOTION_SAVE_THRESHOLD_SCORE and item.get("notion_page_id")
    ]
    for item in eligible:
        _attach_profit_metadata(item, item.get("commercial_score"), item.get("shelf_life_score"))
        _attach_portfolio_topic(item, item.get("portfolio_topic"), item.get("raw_portfolio_topic"))

    if not ENABLE_PROFIT_PRIORITY:
        return sorted(
            eligible,
            key=lambda item: (item.get("score", 0), item.get("repo", {}).get("stargazerCount", 0)),
            reverse=True,
        )

    ordered = sorted(
        eligible,
        key=lambda item: (
            item.get("deep_dive_priority_score", 0), item.get("score", 0),
            item.get("commercial_score", PROFIT_SCORE_NEUTRAL),
            item.get("repo", {}).get("stargazerCount", 0),
        ),
        reverse=True,
    )
    visible_slots = min(TOP_N_FOR_DEEP_DIVE, len(ordered))
    evergreen_needed = min(max(0, EVERGREEN_PORTFOLIO_MIN), visible_slots)
    if evergreen_needed and visible_slots:
        current = ordered[:visible_slots]
        evergreen_count = sum(1 for item in current if item.get("shelf_life") == "EVERGREEN")
        if evergreen_count < evergreen_needed:
            cutoff = float(current[-1].get("deep_dive_priority_score", 0))
            for idx in range(visible_slots, len(ordered)):
                candidate = ordered[idx]
                if candidate.get("shelf_life") != "EVERGREEN":
                    continue
                priority = float(candidate.get("deep_dive_priority_score", 0))
                if priority + max(0.0, EVERGREEN_PRIORITY_TOLERANCE) < cutoff:
                    continue
                selected = ordered.pop(idx)
                ordered.insert(visible_slots - 1, selected)
                evergreen_count += 1
                if evergreen_count >= evergreen_needed:
                    break
    ordered = _apply_content_portfolio_balance(ordered, visible_slots)
    ordered = _apply_publication_reliability_slot(ordered, visible_slots)
    return ordered



def _deferred_ttl_days(shelf_life: str) -> int:
    return {"FLASH": DEFERRED_FLASH_TTL_DAYS, "TREND": DEFERRED_TREND_TTL_DAYS, "EVERGREEN": DEFERRED_EVERGREEN_TTL_DAYS}.get(str(shelf_life or "TREND").upper(), DEFERRED_TREND_TTL_DAYS)


def _deferred_key(candidate: dict) -> str:
    repo = candidate.get("repo", {})
    urls = candidate_identity_urls(repo)
    if urls:
        return sorted(urls)[0]
    return f"{repo.get('source','')}:{_normalize_title_for_match(repo.get('nameWithOwner',''))}"


def _deferred_serializable(candidate: dict) -> dict:
    repo = candidate.get("repo", {})
    now = datetime.now(timezone.utc)
    ttl = _deferred_ttl_days(candidate.get("shelf_life"))
    safe_repo = {k: v for k, v in repo.items() if isinstance(v, (str, int, float, bool, type(None), list, dict))}
    return {
        "key": _deferred_key(candidate), "deferred_at": now.isoformat(),
        "expires_at": (now + timedelta(days=ttl)).isoformat(), "repo": safe_repo,
        "notion_page_id": candidate.get("notion_page_id"), "score": candidate.get("score"),
        "reason": candidate.get("reason", ""), "commercial_score": candidate.get("commercial_score"),
        "shelf_life_score": candidate.get("shelf_life_score"), "shelf_life": candidate.get("shelf_life"),
        "portfolio_topic": candidate.get("portfolio_topic", "OTHER"),
        "deep_dive_priority_score": candidate.get("deep_dive_priority_score"),
    }


def load_deferred_deep_dive_queue() -> list[dict]:
    payload = None
    if EYECATCH_GITHUB_REPO and GH_PAT:
        dest_path = f"{DEFERRED_DEEP_DIVE_GITHUB_DIR}/deferred_queue.json"
        api_url = f"https://api.github.com/repos/{EYECATCH_GITHUB_REPO}/contents/{dest_path}"
        try:
            res = requests.get(api_url, headers={"Authorization": f"Bearer {GH_PAT}", "Accept": "application/vnd.github+json"}, params={"ref": EYECATCH_GITHUB_BRANCH}, timeout=15)
            if res.status_code == 200:
                raw = base64.b64decode(res.json().get("content", "")).decode("utf-8")
                payload = json.loads(raw)
            elif res.status_code not in {404}:
                logger.warning("[DEFERRED LOAD] GitHub HTTP %s", res.status_code)
        except Exception as exc:
            logger.warning("[DEFERRED LOAD] GitHub fallback to local: %s", exc)
    if payload is None:
        try:
            with open(DEFERRED_DEEP_DIVE_STATE_PATH, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            payload = {"version": 1, "items": []}
        except Exception as exc:
            logger.warning("[DEFERRED LOAD] local state corrupt; fail-closed empty queue: %s", exc)
            payload = {"version": 1, "items": []}
    now = datetime.now(timezone.utc)
    valid = []
    for row in payload.get("items", []) if isinstance(payload, dict) else []:
        try:
            expiry = datetime.fromisoformat(str(row.get("expires_at", "")).replace("Z", "+00:00"))
        except Exception:
            continue
        if expiry > now and row.get("key") and isinstance(row.get("repo"), dict):
            valid.append(row)
    return valid[:DEFERRED_DEEP_DIVE_MAX_QUEUE]


def save_deferred_deep_dive_queue(items: list[dict]) -> bool:
    payload = {"version": 1, "updated_at": datetime.now(timezone.utc).isoformat(), "items": items[:DEFERRED_DEEP_DIVE_MAX_QUEUE]}
    try:
        directory = os.path.dirname(DEFERRED_DEEP_DIVE_STATE_PATH)
        if directory: os.makedirs(directory, exist_ok=True)
        with open(DEFERRED_DEEP_DIVE_STATE_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error("[DEFERRED SAVE] local write failed: %s", exc)
        return False
    if not (EYECATCH_GITHUB_REPO and GH_PAT):
        # Local-only is acceptable outside GitHub Actions; in production repo/token are preflighted.
        return not os.environ.get("GITHUB_ACTIONS")
    dest_path = f"{DEFERRED_DEEP_DIVE_GITHUB_DIR}/deferred_queue.json"
    api_url = f"https://api.github.com/repos/{EYECATCH_GITHUB_REPO}/contents/{dest_path}"
    headers = {"Authorization": f"Bearer {GH_PAT}", "Accept": "application/vnd.github+json"}
    try:
        current = requests.get(api_url, headers=headers, params={"ref": EYECATCH_GITHUB_BRANCH}, timeout=15)
        body = base64.b64encode(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii")
        put = {"message": "chore: update deferred deep dive queue", "content": body, "branch": EYECATCH_GITHUB_BRANCH}
        if current.status_code == 200: put["sha"] = current.json().get("sha")
        res = requests.put(api_url, headers=headers, json=put, timeout=30)
        if res.status_code not in {200, 201}:
            logger.error("[DEFERRED SAVE] GitHub HTTP %s %s", res.status_code, res.text[:300]); return False
        return True
    except Exception as exc:
        logger.error("[DEFERRED SAVE] GitHub exception: %s", exc); return False


def _fallback_deferred_rows_to_notion(rows: list[dict], reason: str) -> int:
    """Fail-safe for queue loss/overflow: preserve candidates in existing Notion Pending Retry."""
    moved = 0
    seen = set()
    for row in rows or []:
        page_id = row.get("notion_page_id")
        if not page_id or page_id in seen:
            continue
        seen.add(page_id)
        try:
            _mark_pending_retry_or_escalate(page_id, row.get("repo", {}).get("nameWithOwner", "Deferred candidate"), reason)
            moved += 1
        except Exception as exc:
            logger.error("[DEFERRED FAILSAFE FAILED] %s: %s", page_id, exc)
    return moved


def enqueue_deferred_candidates(candidates: list[dict]) -> int:
    if not candidates: return 0
    queue = load_deferred_deep_dive_queue()
    merged = {row.get("key"): row for row in queue if row.get("key")}
    new_rows = []
    for candidate in candidates:
        row = _deferred_serializable(candidate); merged[row["key"]] = row; new_rows.append(row)
    ranked = sorted(merged.values(), key=lambda r: (float(r.get("deep_dive_priority_score") or r.get("score") or 0), r.get("deferred_at", "")), reverse=True)
    final = ranked[:DEFERRED_DEEP_DIVE_MAX_QUEUE]
    evicted = ranked[DEFERRED_DEEP_DIVE_MAX_QUEUE:]
    if save_deferred_deep_dive_queue(final):
        if evicted:
            _fallback_deferred_rows_to_notion(evicted, "Deferred queue capacity overflow")
        logger.info("[DEFERRED SAVED] queued=%s total=%s evicted_to_pending=%s", len(new_rows), len(final), len(evicted)); return len(new_rows)
    # Persistence failure must not silently lose any queue candidate (old or new).
    _fallback_deferred_rows_to_notion(ranked, "Deferred queue persistence failed")
    return 0


def pop_deferred_candidates(limit: int) -> tuple[list[dict], list[dict]]:
    queue = load_deferred_deep_dive_queue()
    selected = queue[:max(0, limit)]
    remaining = queue[len(selected):]
    return selected, remaining


_PRODUCT_REVIEW_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "category": {"type": "string", "enum": sorted(PORTFOLIO_TOPICS)},
        "adoption_score": {"type": "integer", "minimum": 1, "maximum": 100},
        "components": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                label: {"type": "integer", "minimum": 0, "maximum": maximum}
                for label, maximum in _ADOPTION_SCORE_COMPONENTS
            },
            "required": [label for label, _ in _ADOPTION_SCORE_COMPONENTS],
        },
        "adoption_status": {"type": "string", "enum": sorted(decision_intelligence.ADOPTION_STATUSES)},
        "evidence_confidence": {"type": "string", "enum": sorted(decision_intelligence.CONFIDENCE_LEVELS)},
        "production_readiness": {"type": "string", "enum": sorted(decision_intelligence.READINESS_LEVELS)},
        "main_risk": {"type": "string"},
        "best_for": {"type": "string"},
        "avoid_for": {"type": "string"},
        "short_rationale": {"type": "string"},
        "japanese_display_label": {"type": "string"},
        "next_review_days": {"type": "integer", "minimum": 7, "maximum": 60},
    },
    "required": [
        "category", "adoption_score", "components", "adoption_status", "evidence_confidence",
        "production_readiness", "main_risk", "best_for", "avoid_for", "short_rationale",
        "next_review_days",
    ],
}


def _call_product_review_pool(prompt: str, request_context: str, request_kind_base: str = "product_review"):
    """Call Product Review with provider-enforced JSON Schema.

    ``request_kind_base`` distinguishes the one logical structured-output repair request from
    transport retries.  Both still consume the existing Product Review request budget; no new
    quota lane or provider call path is introduced.
    """
    last_error = None
    for model_name in DEEP_DIVE_MODEL_POOL:
        if model_name in SESSION_EXHAUSTED_MODELS or model_name in SESSION_UNAVAILABLE_MODELS:
            continue
        for attempt in range(2):
            if not PRODUCT_REVIEW_REQUEST_BUDGET.can_request():
                raise ProductReviewBudgetExceededError(PRODUCT_REVIEW_REQUEST_BUDGET.summary())
            try:
                time.sleep(max(0, GEMINI_DEEP_DIVE_CALL_PACING_SECONDS))
                kind = request_kind_base if attempt == 0 else "product_review_retry"
                return _generate_via_chat(
                    model_name, prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_json_schema": _PRODUCT_REVIEW_RESPONSE_SCHEMA,
                        "max_output_tokens": 2200,
                    },
                    request_kind=kind,
                    request_context=request_context, count_as_deep_dive=False, request_origin="product_review",
                ), model_name
            except APIError as exc:
                last_error = exc; code = getattr(exc, "code", None)
                quota_type = classify_gemini_quota_error(exc) if code == 429 else ""
                if code == 429 and quota_type in {"RPD", "DAILY_TOKEN"}: _mark_model_exhausted(model_name, quota_type); break
                if code == 503 and attempt == 0: time.sleep(_extract_retry_delay(exc, 10)); continue
                if code in {503, 404}: _mark_model_unavailable(model_name, str(code)); break
                if code == 429 and quota_type in {"RPM", "TPM"} and attempt == 0: time.sleep(_extract_retry_delay(exc, 15)); continue
                break
            except (GeminiBudgetExceededError, GeminiCallTimeoutError) as exc:
                last_error = exc; break
    raise NoAvailableModelError("Product Reviewに利用可能なGeminiモデルがありません") from last_error


def _product_review_prompt(repo: dict, source_info: dict, current: dict) -> str:
    context = (source_info.get("context") or "")[:50000]
    # Run115: output shape/enums/ranges live in response_json_schema. Do not duplicate that
    # contract in the prompt; Google's GenAI SDK documentation explicitly warns that repeating
    # the schema in the prompt can reduce structured-output quality. Keep only decision semantics.
    return (
        "以下の一次情報だけを使い、会員向けTechnology Decision Intelligenceを評価せよ。記事は書かない。"
        "入力外の市場シェア、価格、利用実績、競合優位性を推測しない。"
        "categoryはSource種別や既存Categoryをコピーせず、一次情報で確認できる主用途・主機能から判断し、"
        "複数カテゴリが同程度または根拠が弱い場合はOTHERを選ぶ。"
        "adoption_scoreは Evidence Quality 25, Production Maturity 25, Use-case Utility / Fit 20, "
        "Reliability / Security Risk 15, Integration / Migration Feasibility 10, Ecosystem / Support Durability 5 の合計100点とし、"
        "componentsの合計と必ず一致させる。"
        "ADOPTはEvidence ConfidenceがHIGHかつProduction ReadinessがHIGHの場合に限る。"
        "main_risk / best_for / avoid_for / short_rationaleは、一次情報から判断できる範囲で具体的かつ空欄にしない。"
        "japanese_display_labelは任意の表示専用フィールド。正式な製品名・プロジェクト名・論文名を改変せず、"
        "『名称 — 日本語で何の技術か』の短い説明ラベルにする。推奨・評価・誇張・スコア・Adoption Statusを含めず、"
        "一次情報だけから安全に説明できない場合は空文字にする。Identity判定には使われない。\n"
        f"Technology: {repo.get('nameWithOwner')}\nURL: {repo.get('url')}\nCurrent: {json.dumps(current, ensure_ascii=False)}\n"
        f"Verified source context:\n{context}"
    )


def _product_review_schema_error(message: str) -> ValueError:
    return ValueError(f"Product Review schema_invalid: {message}")


def _strict_schema_int(value: object, field: str, minimum: int, maximum: int) -> int:
    # bool is a subclass of int in Python, but JSON Schema integer must not silently accept it
    # for scoring/range decisions.
    if isinstance(value, bool) or not isinstance(value, int):
        raise _product_review_schema_error(f"{field} must be integer")
    if not minimum <= value <= maximum:
        raise _product_review_schema_error(f"{field} out_of_range {value} not in {minimum}..{maximum}")
    return value


def _validate_product_review_payload(obj: dict) -> dict:
    """Locally validate provider structured output before any semantic normalization.

    Provider-side JSON Schema is a transport guard, not a trust boundary.  Run115 validates
    required keys, additional keys, enums, component structure/ranges, score sum, text fields,
    and review range again in application code.  Any violation is a structured-output failure
    eligible for the single logical retry; no invalid enum is silently coerced to OTHER.
    """
    if not isinstance(obj, dict):
        raise _product_review_schema_error("response_not_object")
    required = set(_PRODUCT_REVIEW_RESPONSE_SCHEMA["required"])
    allowed = set(_PRODUCT_REVIEW_RESPONSE_SCHEMA["properties"])
    actual = set(obj)
    missing = sorted(required - actual)
    extra = sorted(actual - allowed)
    if missing:
        raise _product_review_schema_error("missing_fields=" + ",".join(missing))
    if extra:
        raise _product_review_schema_error("unexpected_fields=" + ",".join(extra))

    category = obj.get("category")
    if not isinstance(category, str) or category not in PORTFOLIO_TOPICS:
        raise _product_review_schema_error(f"category invalid={category!r}")

    score = _strict_schema_int(obj.get("adoption_score"), "adoption_score", 1, 100)
    components = obj.get("components")
    if not isinstance(components, dict):
        raise _product_review_schema_error("components must be object")
    expected_components = {label for label, _ in _ADOPTION_SCORE_COMPONENTS}
    component_keys = set(components)
    if component_keys != expected_components:
        missing_components = sorted(expected_components - component_keys)
        extra_components = sorted(component_keys - expected_components)
        detail = []
        if missing_components:
            detail.append("missing=" + ",".join(missing_components))
        if extra_components:
            detail.append("extra=" + ",".join(extra_components))
        raise _product_review_schema_error("components_keys " + " ".join(detail))
    component_values: dict[str, int] = {}
    for label, maximum in _ADOPTION_SCORE_COMPONENTS:
        component_values[label] = _strict_schema_int(components.get(label), f"components.{label}", 0, maximum)
    component_total = sum(component_values.values())
    if component_total != score:
        raise _product_review_schema_error(f"adoption_score_sum_mismatch components={component_total} score={score}")

    for field, allowed in (
        ("adoption_status", decision_intelligence.ADOPTION_STATUSES),
        ("evidence_confidence", decision_intelligence.CONFIDENCE_LEVELS),
        ("production_readiness", decision_intelligence.READINESS_LEVELS),
    ):
        value = obj.get(field)
        if not isinstance(value, str) or value not in allowed:
            raise _product_review_schema_error(f"{field} invalid={value!r}")

    for field in ("main_risk", "best_for", "avoid_for", "short_rationale"):
        value = obj.get(field)
        if not isinstance(value, str) or not value.strip():
            raise _product_review_schema_error(f"{field} must be non-empty string")

    _strict_schema_int(obj.get("next_review_days"), "next_review_days", 7, 60)
    return obj



def _normalize_japanese_display_label(value: object) -> str:
    """Soft-normalize the UI-only Japanese label without failing Product Review.

    This field is deliberately excluded from assessment validity, retry triggers, entity identity,
    evidence authority, History change detection, and launch readiness.
    """
    if not isinstance(value, str):
        return ""
    label = re.sub(r"\s+", " ", value).strip()
    if not label or len(label) > 80 or "\n" in value or "\r" in value:
        return ""
    if not re.search(r"[\u3040-\u30ff\u3400-\u9fff]", label):
        return ""
    forbidden = re.compile(
        r"(?:\b(?:WATCH|TEST|ADOPT|AVOID)\b|(?:Adoption|Decision)\s*Score|\d{1,3}\s*/\s*100|"
        r"おすすめ|推奨|最強|最高|革命的|必須|今すぐ導入|採用すべき)", re.I,
    )
    if forbidden.search(label):
        return ""
    return label


def _decode_product_review_json(text: str) -> dict:
    """Parse provider JSON with deterministic, zero-API wrapper cleanup.

    Structured output should already be valid JSON. This fallback only tolerates harmless code
    fences / leading or trailing transport text; it never repairs missing fields or invents values.
    """
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        obj = json.loads(raw or "{}")
    except json.JSONDecodeError:
        start = raw.find("{")
        if start < 0:
            raise
        obj, _ = json.JSONDecoder().raw_decode(raw[start:])
    if not isinstance(obj, dict):
        raise ValueError("Product Review response_not_object")
    return obj


def _parse_product_review_response(payload: object) -> dict:
    obj = payload if isinstance(payload, dict) else _decode_product_review_json(str(payload or ""))
    obj = _validate_product_review_payload(obj)
    components = obj["components"]
    breakdown = "\n".join(f"{label} {components[label]}/{maximum}" for label, maximum in _ADOPTION_SCORE_COMPONENTS)
    return {
        "category": obj["category"],
        "adoption_score": obj["adoption_score"], "adoption_score_breakdown_text": breakdown,
        "adoption_status": obj["adoption_status"],
        "evidence_confidence": obj["evidence_confidence"],
        "production_readiness": obj["production_readiness"],
        "main_risk_text": obj["main_risk"], "best_for_text": obj["best_for"],
        "avoid_for_text": obj["avoid_for"], "short_rationale_text": obj["short_rationale"],
        "japanese_display_label": _normalize_japanese_display_label(obj.get("japanese_display_label")),
        "source_summary_text": "Product Review from verified primary evidence",
        "next_review_days": obj["next_review_days"],
    }


def _parse_product_review_model_response(response: object) -> dict:
    provider_parsed = getattr(response, "parsed", None)
    if isinstance(provider_parsed, dict):
        return _parse_product_review_response(provider_parsed)
    model_dump = getattr(provider_parsed, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return _parse_product_review_response(dumped)
    return _parse_product_review_response(getattr(response, "text", ""))

def _technology_state_to_repo(state: dict) -> dict:
    """Rehydrate the minimum source identity lost by the legacy Notion schema.

    Technology rows intentionally do not store sourceDetails JSON. Run113 reconstructs only
    explicit facts already present in Primary URL / Canonical Entity ID / Evidence URLs / aliases;
    it never guesses an official site from the technology name.
    """
    sources = [str(x) for x in (state.get("sources") or ["GitHub"]) if x]
    discovery_source = sources[0] if sources else "GitHub"
    primary_url = str(state.get("primary_url") or "")
    entity_id = str(state.get("canonical_entity_id") or "")
    name = str(state.get("technology_name") or "Technology")
    temp = {
        "source": discovery_source, "primaryUrl": primary_url, "url": primary_url,
        "canonicalEntityId": entity_id, "nameWithOwner": name,
    }
    effective_source = _effective_evidence_source(temp)
    if effective_source == "GitHub":
        repo_identity = _github_repo_identity(temp)
        if repo_identity:
            name = repo_identity
    details: dict[str, object] = {
        "discovery_sources": sources,
        "related_links": list(state.get("evidence_urls") or []),
    }
    aliases = [str(x) for x in (state.get("entity_aliases") or []) if x]
    for alias in aliases:
        host = (urlparse(alias).netloc or "").lower()
        if "news.ycombinator.com" in host and not details.get("hn_url"):
            details["hn_url"] = alias
        if "producthunt.com" in host and not details.get("producthunt_url"):
            details["producthunt_url"] = alias
    if effective_source == "HackerNews" and primary_url and "news.ycombinator.com" not in (urlparse(primary_url).netloc or "").lower():
        details["external_url"] = primary_url
    if effective_source == "ProductHunt" and primary_url and "producthunt.com" not in (urlparse(primary_url).netloc or "").lower():
        details["official_url"] = primary_url
    return {
        "source": effective_source,
        "discoverySource": discovery_source,
        "nameWithOwner": name,
        "canonicalEntityId": entity_id,
        "url": primary_url,
        "primaryUrl": primary_url,
        "description": state.get("source_summary") or state.get("short_rationale") or "",
        # Legacy Source Summary is useful discovery context but is not silently promoted to
        # verified primary evidence. Exact GitHub/arXiv/official sources are re-fetched first.
        "sourceContext": state.get("source_summary") or "",
        "sourceContextVerified": False,
        "publishedAt": None,
        "stargazerCount": 0,
        "sourceDetails": details,
    }


def select_product_review_candidates() -> list[dict]:
    if not (ENABLE_REVENUE_PRODUCT_PHASE2 and decision_intelligence.ENABLE_DECISION_INTELLIGENCE_DB and PRODUCT_REVIEW_MAX_PER_RUN > 0): return []
    pages = decision_intelligence.query_technology_records(max_records=5000)
    states = [decision_intelligence.technology_page_to_state(page) for page in pages]
    bootstrap_order: dict[str, int] = {}
    if INVENTORY_BOOTSTRAP_ACTIVE:
        # Fail closed: manual acceleration must never review arbitrary inventory when the reviewed
        # Plan was not propagated into this subprocess. An empty allowlist may still run Subscriber
        # sync, but Product Review itself returns no candidates.
        bootstrap_order = {entity_id: idx for idx, entity_id in enumerate(INVENTORY_BOOTSTRAP_ENTITY_IDS)}
        if not bootstrap_order:
            logger.warning("[INVENTORY BOOTSTRAP] ordered entity allowlist is empty; Product Review disabled")
            return []
        states = [s for s in states if str(s.get("canonical_entity_id") or "") in bootstrap_order]
    now = datetime.now(timezone.utc)
    active = []
    legacy = []
    for state in states:
        st = state.get("assessment_state") or ""
        if st == "LEGACY_PENDING":
            # Never spend Gemini on unresolved legacy identities. They may become resolvable when
            # a future discovery supplies an official/project URL. Also honor evidence cooldown.
            if state.get("entity_status") != "RESOLVED":
                continue
            if state.get("next_review"):
                try:
                    if datetime.fromisoformat(state["next_review"].replace("Z", "+00:00")) > now:
                        continue
                except Exception:
                    pass
            legacy.append(state); continue
        if st == "HISTORY_PENDING" and state.get("tracking_eligibility"):
            active.append((0, state)); continue
        if st == "SCREENED" and state.get("tracking_eligibility"):
            if state.get("next_review"):
                try:
                    if datetime.fromisoformat(state["next_review"].replace("Z", "+00:00")) > now:
                        continue
                except Exception:
                    pass
            active.append((0, state)); continue
        if st == "ASSESSED" and state.get("tracking_eligibility") and state.get("tracking_status") != "ARCHIVED":
            due = False
            if state.get("next_review"):
                try: due = datetime.fromisoformat(state["next_review"].replace("Z", "+00:00")) <= now
                except Exception: due = True
            elif state.get("last_reviewed"):
                try: due = datetime.fromisoformat(state["last_reviewed"].replace("Z", "+00:00")) <= now - timedelta(days=TRACKING_REVIEW_DAYS)
                except Exception: due = True
            else: due = True
            if due: active.append((1, state))
    if INVENTORY_BOOTSTRAP_ACTIVE:
        active.sort(key=lambda x: bootstrap_order.get(str(x[1].get("canonical_entity_id") or ""), 10**9))
        legacy.sort(key=lambda x: bootstrap_order.get(str(x.get("canonical_entity_id") or ""), 10**9))
        # Run113: manual Bootstrap preflight may inspect beyond max_reviews without Gemini.
        # Evidence-unresolvable candidates therefore cannot consume the paid Product Review slots.
        ordered: list[dict] = [state for _, state in active] + list(legacy)
        ordered.sort(key=lambda x: bootstrap_order.get(str(x.get("canonical_entity_id") or ""), 10**9))
        deduped: list[dict] = []
        seen_ids: set[str] = set()
        for state in ordered:
            key = str(state.get("canonical_entity_id") or state.get("page_id") or id(state))
            if key in seen_ids:
                continue
            seen_ids.add(key); deduped.append(state)
        return deduped[:PRODUCT_REVIEW_PREFLIGHT_SCAN_LIMIT]
    else:
        active.sort(key=lambda x: (x[0], -(x[1].get("screening_score") or 0), x[1].get("last_reviewed") or ""))
        legacy.sort(key=lambda x: (-(x.get("screening_score") or 0), x.get("first_seen") or ""))
    # Reserve a small legacy bootstrap lane so the migrated inventory cannot starve forever
    # behind an always-full active review queue. Paid-product freshness still gets the majority.
    legacy_slots = 0
    if legacy and LEGACY_BOOTSTRAP_MAX_PER_RUN > 0:
        legacy_slots = min(LEGACY_BOOTSTRAP_MAX_PER_RUN, PRODUCT_REVIEW_MAX_PER_RUN)
    active_slots = max(0, PRODUCT_REVIEW_MAX_PER_RUN - legacy_slots)
    selected = [state for _, state in active[:active_slots]]
    if legacy_slots:
        selected.extend(legacy[:legacy_slots])
    # If no legacy work exists, return the unused reservation to active reviews.
    remaining = PRODUCT_REVIEW_MAX_PER_RUN - len(selected)
    if remaining > 0:
        already = {str(x.get("canonical_entity_id") or x.get("technology_page_id") or id(x)) for x in selected}
        for _, state in active[active_slots:]:
            key = str(state.get("canonical_entity_id") or state.get("technology_page_id") or id(state))
            if key in already:
                continue
            selected.append(state); already.add(key)
            if len(selected) >= PRODUCT_REVIEW_MAX_PER_RUN:
                break
    return selected


def _defer_product_review_candidate(state: dict, days: int = TRACKING_REVIEW_DAYS, reason: str = "review deferred") -> None:
    page_id = state.get("page_id")
    if not page_id:
        return
    nr = (datetime.now(timezone.utc) + timedelta(days=max(1, days))).isoformat()
    res = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        json={"properties": {decision_intelligence.TECH_PROP_NEXT_REVIEW: {"date": {"start": nr}}}},
        headers=decision_intelligence._headers(), timeout=10,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Product review defer patch failed: {res.status_code}")
    logger.info("[PRODUCT REVIEW DEFERRED] %s days=%s reason=%s", state.get("technology_name"), days, reason)


def _product_review_evidence_defer_days(source_info: dict, evidence: dict) -> int:
    """Use a short cooldown for likely transport failures, normal cadence for real evidence gaps."""
    blocking = set(evidence.get("blocking_missing") or [])
    if "primary_source_resolved" in blocking and source_info.get("primary_fetch_failed"):
        return 1
    return TRACKING_REVIEW_DAYS


def run_product_reviews() -> dict:
    result = {
        "attempted": 0,          # backward-compatible: candidates inspected by evidence preflight
        "inspected": 0,
        "evidence_ready": 0,
        "review_slots_used": 0,  # candidates that reached Gemini Product Review
        "saved": 0,
        "skipped": 0,
        "evidence_skipped": 0,
        "authority_skipped": 0,
        "structured_retries": 0,
        "structured_retry_recovered": 0,
        "boundary_reconciliation_attempted": 0,
        "boundary_reconciled": 0,
    }
    for state in select_product_review_candidates():
        # max_reviews is a Gemini review cap, not a zero-API evidence-inspection cap.
        if result["review_slots_used"] >= PRODUCT_REVIEW_MAX_PER_RUN:
            break
        repo = _technology_state_to_repo(state)
        result["attempted"] += 1
        result["inspected"] += 1
        try:
            source_info = prepare_source_context(repo)
            evidence = assess_evidence_sufficiency(source_info)
            if evidence.get("state") == EVIDENCE_SUPPLEMENT_REQUIRED:
                source_info = supplement_source_evidence(source_info)
                evidence = assess_evidence_sufficiency(source_info)

            authority_failures = _primary_source_authority_failures(source_info)
            if authority_failures:
                logger.info(
                    "[PRODUCT REVIEW SKIP] %s primary authority insufficient: %s",
                    repo.get("nameWithOwner"), " / ".join(authority_failures)[:600],
                )
                _defer_product_review_candidate(state, TRACKING_REVIEW_DAYS, "primary authority insufficient")
                result["skipped"] += 1
                result["authority_skipped"] += 1
                continue

            if evidence.get("state") == EVIDENCE_INSUFFICIENT or not evidence.get("decision_scope_safe"):
                logger.info(
                    "[PRODUCT REVIEW SKIP] %s evidence insufficient blocking=%s",
                    repo.get("nameWithOwner"), evidence.get("blocking_missing") or [],
                )
                days = _product_review_evidence_defer_days(source_info, evidence)
                _defer_product_review_candidate(state, days, "evidence insufficient")
                result["skipped"] += 1
                result["evidence_skipped"] += 1
                continue

            result["evidence_ready"] += 1
            # Only now consult/consume Gemini capacity. Evidence preflight itself is zero Gemini.
            if not PRODUCT_REVIEW_REQUEST_BUDGET.can_request() or not GEMINI_BUDGET.can_request():
                logger.info("[PRODUCT REVIEW STOP] Gemini budget unavailable after evidence preflight")
                break
            if not _model_pool_has_session_candidate(DEEP_DIVE_MODEL_POOL):
                logger.info("[PRODUCT REVIEW STOP] no session model available after evidence preflight")
                break
            if result["review_slots_used"] >= PRODUCT_REVIEW_MAX_PER_RUN:
                break
            result["review_slots_used"] += 1

            review_prompt = _product_review_prompt(repo, source_info, state)
            request_context = f"product_review:{state.get('canonical_entity_id')}"
            response, model = _call_product_review_pool(review_prompt, request_context)
            try:
                parsed = _parse_product_review_model_response(response)
            except (ValueError, TypeError, json.JSONDecodeError) as parse_exc:
                logger.warning(
                    "[PRODUCT REVIEW STRUCTURED OUTPUT INVALID] %s: %s",
                    repo.get("nameWithOwner"), parse_exc,
                )
                # Exactly one logical schema-repair request is allowed, and it must fit inside the
                # existing Product Review + global Gemini budgets. A retry never consumes a new
                # review slot because it is repairing the same candidate assessment.
                if not (PRODUCT_REVIEW_REQUEST_BUDGET.can_request() and GEMINI_BUDGET.can_request()
                        and _model_pool_has_session_candidate(DEEP_DIVE_MODEL_POOL)):
                    raise
                result["structured_retries"] += 1
                response, model = _call_product_review_pool(
                    review_prompt,
                    request_context + ":structured_retry",
                    request_kind_base="product_review_retry",
                )
                parsed = _parse_product_review_model_response(response)
                result["structured_retry_recovered"] += 1

            reviewed_at = datetime.now(timezone.utc).isoformat()
            persist_kwargs = dict(
                screening_score=state.get("screening_score"), screening_reason=state.get("screening_reason", ""),
                attribution_context={"portfolio_topic": parsed.get("category") or "OTHER"}, pipeline_status="Product Review",
                content_status="Stocked", article_status=ARTICLE_STATUS_NOT_PLANNED,
            )
            persisted = persist_decision_intelligence_assessment(
                repo, parsed, source_info, evidence, reviewed_at, **persist_kwargs
            )

            # Run114: a named feature can be real first-party information yet absent from the
            # initially fetched landing/README context. Reconcile only this narrow validator
            # failure by following explicit first-party docs with zero Gemini. Gates are not
            # relaxed: persistence is retried only after the exact named fact becomes verifiable.
            boundary_failures = _source_boundary_failure_names(persisted.get("failures") or [])
            if (not persisted.get("saved") and persisted.get("reason") == "assessment_invalid" and boundary_failures):
                result["boundary_reconciliation_attempted"] += 1
                reconciliation = reconcile_product_review_source_boundary(
                    parsed, source_info, persisted.get("failures") or []
                )
                logger.info(
                    "[PRODUCT REVIEW BOUNDARY RECONCILIATION] %s -> %s",
                    repo.get("nameWithOwner"), reconciliation,
                )
                if reconciliation.get("resolved"):
                    refreshed_evidence = assess_evidence_sufficiency(source_info)
                    if (refreshed_evidence.get("state") != EVIDENCE_INSUFFICIENT
                            and refreshed_evidence.get("decision_scope_safe")):
                        persisted = persist_decision_intelligence_assessment(
                            repo, parsed, source_info, refreshed_evidence, reviewed_at, **persist_kwargs
                        )
                        evidence = refreshed_evidence
                        if persisted.get("saved"):
                            result["boundary_reconciled"] += 1

            if persisted.get("saved"):
                # next_review is a product scheduler field and is intentionally patched after the common upsert.
                days = parsed.get("next_review_days", TRACKING_REVIEW_DAYS)
                page_id = persisted.get("page_id")
                if page_id:
                    nr = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
                    patch = requests.patch(
                        f"https://api.notion.com/v1/pages/{page_id}",
                        json={"properties": {decision_intelligence.TECH_PROP_NEXT_REVIEW: {"date": {"start": nr}}}},
                        headers=decision_intelligence._headers(), timeout=10,
                    )
                    if patch.status_code != 200:
                        raise RuntimeError(f"Next Review patch failed: {patch.status_code}")
                result["saved"] += 1
            else:
                result["skipped"] += 1
        except ProductReviewBudgetExceededError:
            break
        except NoAvailableModelError as exc:
            logger.warning("[PRODUCT REVIEW STOP] %s", exc)
            break
        except Exception as exc:
            logger.error("[PRODUCT REVIEW FAILED] %s: %s", repo.get("nameWithOwner"), exc)
            result["skipped"] += 1
    logger.info("[PRODUCT REVIEW] %s / %s", result, PRODUCT_REVIEW_REQUEST_BUDGET.summary())
    return result


def seed_tracking_candidates(screened: list[dict]) -> dict:
    result = {"eligible": 0, "saved": 0, "ambiguous": 0, "failed": 0}
    if not (ENABLE_REVENUE_PRODUCT_PHASE2 and decision_intelligence.ENABLE_DECISION_INTELLIGENCE_DB): return result
    now = datetime.now(timezone.utc).isoformat()
    for item in screened:
        if item.get("screening_status") != "completed" or not item.get("tracking_eligible") or (item.get("score") or 0) < TRACKING_ELIGIBILITY_MIN_SCORE:
            continue
        result["eligible"] += 1; repo = item.get("repo", {})
        resolution = decision_intelligence.resolve_canonical_entity_id(repo, {"primary_url": repo.get("primaryUrl") or repo.get("url")})
        if resolution.status == "AMBIGUOUS": result["ambiguous"] += 1; continue
        try:
            saved = decision_intelligence.upsert_tracking_seed({
                "name": repo.get("nameWithOwner"), "url": repo.get("url"), "source": repo.get("source"),
                "category": item.get("portfolio_topic") or "OTHER", "screening_score": item.get("score"),
                "screening_reason": item.get("reason", ""), "tracking_eligibility": True,
                "tracking_reason": item.get("tracking_reason") or item.get("reason", ""), "source_summary": repo.get("description", ""),
                "published_at": repo.get("publishedAt"), "analyzed_at": now, "first_seen": now,
                # Initial product assessment should be eligible on the next run; later reviews set their own cadence.
                "next_review": now,
            }, resolution)
            if saved.get("saved"): result["saved"] += 1
        except Exception as exc:
            logger.error("[TRACKING SEED FAILED] %s: %s", repo.get("nameWithOwner"), exc); result["failed"] += 1
    logger.info("[TRACKING SEED] %s", result); return result


def _previous_month_id(today) -> str:
    first = today.replace(day=1)
    prev = first - timedelta(days=1)
    return f"{prev.year:04d}-{prev.month:02d}"


def _current_month_id(today) -> str:
    return f"{today.year:04d}-{today.month:02d}"


def run_evidence_health_maintenance() -> dict:
    """Zero-Gemini health checks. Material source changes only accelerate Next Review."""
    result = {"enabled": evidence_ledger.ENABLE_EVIDENCE_LEDGER, "checked": 0, "material": 0, "missing": 0, "cosmetic": 0, "moved": 0, "errors": 0}
    if not evidence_ledger.ENABLE_EVIDENCE_LEDGER:
        return result
    token = decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY
    for state in evidence_ledger.query_health_candidates(token):
        try:
            def fetcher(url: str):
                source_type = str(state.get("source_type") or "").lower()
                if source_type == "github":
                    repo_name = _github_repo_name_from_url(url)
                    if repo_name:
                        text = fetch_github_readme_context(repo_name)
                        return (200 if text else 0), text, url
                if source_type == "arxiv":
                    arxiv_id = _extract_arxiv_id(url)
                    if arxiv_id:
                        text, details = fetch_arxiv_api_context(arxiv_id)
                        final = details.get("arxiv_versioned_url") or url
                        return (200 if text else 0), text, final
                status, text, final = _http_get_health_limited(url, min(WEB_CONTEXT_MAX_BYTES, 1_500_000))
                if status == 200 and ("<html" in text[:1200].lower() or "<!doctype html" in text[:1200].lower()):
                    parser = _ReadableHTMLTextParser()
                    try:
                        parser.feed(text); text = parser.text()
                    except Exception:
                        pass
                return status, text, final
            health = evidence_ledger.check_health(state, fetcher)
            result["checked"] += 1
            h = health.get("health")
            if h == "COSMETIC_CHANGE": result["cosmetic"] += 1
            elif h == "MOVED": result["moved"] += 1
            elif h == "MISSING": result["missing"] += 1
            if health.get("material"):
                result["material"] += 1
                tech_page = state.get("tech_page_id")
                if tech_page:
                    now = datetime.now(timezone.utc).isoformat()
                    patch = requests.patch(
                        f"https://api.notion.com/v1/pages/{tech_page}",
                        json={"properties": {decision_intelligence.TECH_PROP_NEXT_REVIEW: {"date": {"start": now}}}},
                        headers=decision_intelligence._headers(), timeout=10,
                    )
                    if patch.status_code != 200:
                        raise RuntimeError(f"Technology Next Review acceleration failed: {patch.status_code}")
                evidence_ledger.update_health(state["page_id"], health, token, rereview_triggered=True)
            else:
                evidence_ledger.update_health(state["page_id"], health, token, rereview_triggered=False)
        except Exception as exc:
            result["errors"] += 1
            logger.warning("[EVIDENCE HEALTH FAILED] %s: %s", state.get("url"), exc)
    logger.info("[EVIDENCE HEALTH] %s", result)
    return result


def run_product_delivery_maintenance(today=None) -> dict:
    result = {"subscriber": None, "monthly": [], "evidence_health": None}
    if not (ENABLE_REVENUE_PRODUCT_PHASE2 and decision_intelligence.ENABLE_DECISION_INTELLIGENCE_DB): return result
    try:
        result["evidence_health"] = run_evidence_health_maintenance()
    except Exception as exc:
        logger.error("[EVIDENCE HEALTH MAINTENANCE FAILED] %s", exc)
    try:
        result["subscriber"] = decision_intelligence.sync_subscriber_technology_db()
        if result["subscriber"] and result["subscriber"].get("enabled"): logger.info("[SUBSCRIBER TECH SYNC] %s", result["subscriber"])
    except Exception as exc:
        logger.error("[SUBSCRIBER TECH SYNC FAILED] %s", exc)
    if decision_intelligence.ENABLE_DECISION_MONTHLY_DIGEST:
        local_today = today or datetime.now(ZoneInfo(NOTION_TIMEZONE)).date()
        # Re-check the most recent three completed periods every run. Period ID idempotency makes
        # this cheap and lets the paid monthly product recover even after a multi-week outage.
        targets = []
        cursor = local_today.replace(day=1)
        for _ in range(3):
            cursor = (cursor - timedelta(days=1)).replace(day=1)
            targets.append(f"{cursor.year:04d}-{cursor.month:02d}")
        tomorrow = local_today + timedelta(days=1)
        if tomorrow.month != local_today.month:
            targets.append(_current_month_id(local_today))
        for period in dict.fromkeys(targets):
            try:
                row = decision_intelligence.create_history_monthly_digest(period); result["monthly"].append(row)
                if row.get("created"): logger.info("[DECISION MONTHLY CREATED] %s events=%s", period, row.get("events"))
            except Exception as exc:
                logger.error("[DECISION MONTHLY FAILED] %s: %s", period, exc)
    return result


def process_article_backlog(pending_items: list[dict] | None, generated_count: int,
                            next_candidate_rank: int) -> tuple[int, int]:
    """Use leftover article capacity for deferred (never attempted) then pending (previously failed).

    Fresh acquisition is intentionally scheduled before this helper. This prevents failure-prone
    backlog items from consuming model availability before today's best new candidates. On a day
    with no fresh candidates, main() calls this helper directly so valuable backlog is still recoverable.
    """
    # Deferred first: these candidates were not sent to Gemini in the previous run and therefore
    # have a better expected publication yield than a transport/quality-failed Pending Retry item.
    if generated_count < TOP_N_FOR_DEEP_DIVE and DEFERRED_DEEP_DIVE_MAX_PER_RUN > 0:
        deferred_selected, deferred_remaining = pop_deferred_candidates(DEFERRED_DEEP_DIVE_MAX_PER_RUN)
        deferred_keep = list(deferred_remaining)
        for row in deferred_selected:
            if generated_count >= TOP_N_FOR_DEEP_DIVE:
                deferred_keep.insert(0, row)
                continue
            page_id = row.get("notion_page_id")
            already_handled = False
            if page_id and NOTION_API_KEY:
                try:
                    pg = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=_notion_headers(), timeout=10)
                    if pg.status_code == 200:
                        props = pg.json().get("properties", {})
                        article_state = ((props.get(PROP_ARTICLE_STATUS) or {}).get("select") or {}).get("name") or ""
                        content_state = ((props.get(PROP_CONTENT_STATUS) or {}).get("select") or {}).get("name") or ""
                        already_handled = article_state in {ARTICLE_STATUS_READY, ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW} or content_state in {CONTENT_STATUS_QUALITY_FAILED, CONTENT_STATUS_PENDING_RETRY}
                except Exception as exc:
                    logger.warning("[DEFERRED VERIFY] %s", exc)
            if already_handled:
                logger.info("[DEFERRED DROP] already handled: %s", row.get("repo", {}).get("nameWithOwner"))
                continue
            if not (GEMINI_BUDGET.can_request() and DEEP_DIVE_MODEL_BUDGET.can_request() and _model_pool_has_session_candidate(DEEP_DIVE_MODEL_POOL)):
                deferred_keep.insert(0, row)
                continue
            next_candidate_rank += 1
            logger.info("[DEFERRED DEEP DIVE] %s", row.get("repo", {}).get("nameWithOwner"))
            try:
                report = generate_intelligence_report(
                    row.get("repo", {}), notion_page_id=page_id, screening_score=row.get("score"),
                    screening_reason=row.get("reason", ""), candidate_rank=next_candidate_rank,
                    candidate_origin="deferred", attribution_context=row,
                )
                if report:
                    generated_count += 1
            except DailyQuotaExhaustedError:
                deferred_keep.insert(0, row)
                break
        if not save_deferred_deep_dive_queue(deferred_keep):
            logger.error("[DEFERRED QUEUE] post-attempt persistence failed; moving remaining queue to Notion Pending Retry")
            _fallback_deferred_rows_to_notion(deferred_keep, "Deferred queue post-attempt persistence failed")

    if generated_count >= TOP_N_FOR_DEEP_DIVE:
        return generated_count, next_candidate_rank

    for item in (pending_items or []):
        if generated_count >= TOP_N_FOR_DEEP_DIVE:
            break
        if not PENDING_RETRY_REQUEST_BUDGET.can_request():
            logger.info("[PENDING RETRY STOP] dedicated request budget exhausted; article target preserved")
            break
        if not (GEMINI_BUDGET.can_request() and DEEP_DIVE_MODEL_BUDGET.can_request() and _model_pool_has_session_candidate(DEEP_DIVE_MODEL_POOL)):
            logger.warning("[PENDING RETRY STOP] no remaining article/model budget")
            break
        next_candidate_rank += 1
        logger.info("[PENDING RETRY] %s", item["repo"].get("nameWithOwner"))
        try:
            if generate_intelligence_report(
                item["repo"], item.get("notion_page_id"), item.get("screening_score"), item.get("screening_reason", ""),
                candidate_rank=next_candidate_rank, candidate_origin="pending_retry",
            ):
                generated_count += 1
        except DailyQuotaExhaustedError:
            logger.warning("[PENDING RETRY STOP] Gemini日次クォータ到達")
            break
    return generated_count, next_candidate_rank


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
    if INVENTORY_BOOTSTRAP_ACTIVE:
        logger.info("[INVENTORY BOOTSTRAP MODE] normal acquisition/article pipeline is bypassed")
        initialize_inventory_bootstrap_runtime()
        review_result = run_product_reviews()
        delivery_result = run_product_delivery_maintenance()
        logger.info("[INVENTORY BOOTSTRAP COMPLETE] product_review=%s subscriber=%s", review_result, delivery_result.get("subscriber"))
        logger.info(PRODUCT_REVIEW_REQUEST_BUDGET.summary())
        logger.info(GEMINI_USAGE_AUDIT.summary(include_contexts=True))
        logger.info(PERSISTENT_GEMINI_COUNTER.summary())
        return
    # Private Article Auditはrun-local成果物。配布ZIPや前Runに残ったテスト稿を
    # 今回の本番Readyとして誤認しないよう、Production開始時に必ず初期化する。
    reset_article_audit_for_production_run()
    reset_article_style_memory()
    initialize_runtime()
    if REGEN_TEST_MODE:
        run_regen_test_mode()
        return
    funnel = reset_deep_dive_gate_funnel()
    source_roi_state = load_source_roi_state()
    source_roi_profile = compute_source_roi_profile(source_roi_state)
    source_fetch_limits = allocate_source_fetch_limits(source_roi_profile, MAX_SCREENING_CANDIDATES)
    log_source_roi_profile(source_roi_profile, source_fetch_limits)
    pending_items = get_pending_retry_items(limit=TOP_N_FOR_DEEP_DIVE)
    if pending_items is None:
        # Pending Retry is a recovery lane, not a prerequisite for fresh acquisition.
        # The later full dedupe query remains the authoritative fail-closed check.
        logger.warning("[PENDING RETRY] read failed; skip backlog recovery and continue fresh acquisition")
        pending_items = []
    next_candidate_rank = 0

    check_stale_content()

    github_items = fetch_github_trending(source_fetch_limits.get("GitHub", GITHUB_FETCH_LIMIT))
    hackernews_items = fetch_hackernews_top(source_fetch_limits.get("HackerNews", HN_FETCH_LIMIT))
    arxiv_items = fetch_arxiv_ai_ml(source_fetch_limits.get("ArXiv", ARXIV_FETCH_LIMIT))
    producthunt_items = fetch_producthunt_trending(source_fetch_limits.get("ProductHunt", PRODUCTHUNT_FETCH_LIMIT))
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
    if existing_urls is not None:
        repaired_titles = repair_existing_multilingual_notion_titles()
        if repaired_titles:
            logger.info("[MULTILINGUAL TITLE NORMALIZATION] repaired_existing=%d", repaired_titles)
    if existing_urls is None:
        logger.error("[PIPELINE ABORTED] 重複チェック不能のためFail-Closed停止")
        source_roi_state = update_source_roi_state(source_roi_state, [], funnel)
        run_product_delivery_maintenance()
        logger.info(GEMINI_BUDGET.summary())
        logger.info(DEEP_DIVE_MODEL_BUDGET.summary())
        finalize_deep_dive_observability(funnel)
        return

    deduped_repos = []
    local_identity_urls: set[str] = set()
    local_fallback_keys: set[str] = set()
    for repo in safe_repos:
        identity_urls = candidate_identity_urls(repo)
        title_key = _normalize_title_for_match(repo.get("nameWithOwner", ""))
        fallback_key = f"{repo.get('source', '')}:{title_key}"
        # Cross-source dedupeは候補自身が保持する公式/一次URLの共有だけで判定する。
        # title類似度だけで別案件を落とすことはしない。
        if (identity_urls & existing_urls) or (identity_urls & local_identity_urls) or (not identity_urls and fallback_key in local_fallback_keys):
            logger.info(f" [SKIP: DUPLICATE] {repo.get('nameWithOwner')}")
            continue
        local_identity_urls.update(identity_urls)
        if not identity_urls:
            local_fallback_keys.add(fallback_key)
        deduped_repos.append(repo)
    if not deduped_repos:
        logger.info("本日は新規候補が0件でした。Backlogから公開可能記事を救済します。")
        generated_count, next_candidate_rank = process_article_backlog(pending_items, 0, next_candidate_rank)
        run_product_reviews()
        source_roi_state = update_source_roi_state(source_roi_state, [], funnel)
        run_product_delivery_maintenance()
        logger.info("[ARTICLE DELIVERY] Ready=%s target=%s source=backlog", generated_count, TOP_N_FOR_DEEP_DIVE)
        logger.info(GEMINI_BUDGET.summary())
        logger.info(DEEP_DIVE_MODEL_BUDGET.summary())
        logger.info(PRODUCT_REVIEW_REQUEST_BUDGET.summary())
        finalize_deep_dive_observability(funnel)
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

    seed_tracking_candidates(screened)

    logger.info(f"[STOCK] final_score>={NOTION_SAVE_THRESHOLD_SCORE} = {stocked_count}")
    logger.info(f">>> Screening {len(screened)}件 / Stock {stocked_count}件")
    if ENABLE_OBSERVED_HISTORY:
        observed_path = save_observed_history(
            screened, screening_calls,
            max(0, screening_calls - ((len(screening_candidates) + SCREENING_BATCH_SIZE - 1) // SCREENING_BATCH_SIZE)),
            calibration_calls=calibration_calls, total_collected=len(repos),
            source_roi_profile=source_roi_profile, source_fetch_limits=source_fetch_limits,
        )
        logger.info("[OBSERVED] saved=%s path=%s", len(screened), observed_path)

    if daily_quota_stop:
        source_roi_state = update_source_roi_state(source_roi_state, screened, funnel)
        log_source_roi_profile(compute_source_roi_profile(source_roi_state), source_fetch_limits)
        logger.info(GEMINI_BUDGET.summary())
        logger.info(DEEP_DIVE_MODEL_BUDGET.summary())
        generate_monthly_digest()
        run_product_delivery_maintenance()
        finalize_deep_dive_observability(funnel)
        return

    # TOP_Nは『候補数』ではなく『最大成功記事数』。失敗時は4位・5位へBackfillする。
    generated_count = 0
    attempted = 0
    # Deep Diveは3層設計上「Stocked上位」だけを対象にする。Score条件を満たしても
    # Notion Stock永続化に失敗した候補へGeminiを追加消費しない。保存失敗候補はDBに
    # dedupe記録がないため、次回収集で再浮上した時にStockからやり直せる。
    candidates = _select_stocked_deep_dive_candidates(screened)
    if len(candidates) < TOP_N_FOR_DEEP_DIVE:
        logger.info(
            f"[DEEP DIVE POOL] Stock基準{NOTION_SAVE_THRESHOLD_SCORE}点以上は{len(candidates)}件。"
            "低スコア候補で本数を水増しせず、この範囲だけで記事生成します。"
        )
    for candidate_index, candidate in enumerate(candidates):
        if generated_count >= TOP_N_FOR_DEEP_DIVE:
            break
        if attempted >= MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS:
            break
        remaining_attempt_slots = max(0, MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS - attempted)
        def _defer_remaining():
            # Only candidates that could have been backfilled this run are carried forward; never queue the whole Stock DB.
            enqueue_deferred_candidates(candidates[candidate_index:candidate_index + remaining_attempt_slots])
        if not GEMINI_BUDGET.can_request():
            logger.warning("[DEEP DIVE STOP] Gemini local budget残量なし")
            _defer_remaining(); break
        if not DEEP_DIVE_MODEL_BUDGET.can_request():
            logger.warning("[DEEP DIVE STOP] run budget exhausted: %s/%s; remaining Backfill candidates deferred", DEEP_DIVE_MODEL_BUDGET.used, DEEP_DIVE_MODEL_BUDGET.budget)
            _defer_remaining(); break
        if not _model_pool_has_session_candidate(DEEP_DIVE_MODEL_POOL):
            logger.warning("[DEEP DIVE STOP] all configured Deep Dive models unavailable; remaining Backfill candidates deferred")
            _defer_remaining(); break
        attempted += 1
        next_candidate_rank += 1
        repo = candidate["repo"]
        name = repo.get("nameWithOwner")
        logger.info(
            f" [DEEP DIVE {attempted}] {name}（Decision {candidate['score']} / "
            f"Commercial {candidate.get('commercial_score', PROFIT_SCORE_NEUTRAL)} / "
            f"Shelf {candidate.get('shelf_life', 'TREND')} / Topic {candidate.get('portfolio_topic', 'OTHER')} / "
            f"Priority {candidate.get('deep_dive_priority_score', candidate['score'])}）"
        )
        try:
            report = generate_intelligence_report(
                repo,
                notion_page_id=candidate.get("notion_page_id"),
                screening_score=candidate.get("score"),
                screening_reason=candidate.get("reason", ""),
                candidate_rank=next_candidate_rank,
                attribution_context=candidate,
            )
            if report:
                generated_count += 1
        except DailyQuotaExhaustedError:
            send_telegram_alert("⚠️ Gemini APIの日次クォータに到達しました（Deep Dive中）。")
            daily_quota_stop = True
            break

    # Only after fresh acquisition has had first access to the article models, use leftover capacity
    # for never-attempted Deferred candidates and then previously failed Pending Retry items.
    generated_count, next_candidate_rank = process_article_backlog(pending_items, generated_count, next_candidate_rank)

    # Paid Product Review runs after all free-article acquisition/recovery lanes. It keeps its own
    # small request cap but shares global/persistent quotas. Product-side 503 cannot poison today's
    # article model pool before acquisition is attempted.
    run_product_reviews()

    if generated_count == 0:
        reason = "daily quota" if daily_quota_stop else "source/quality/API/budget"
        send_telegram_alert(f"⚠️ 本日のDeep Dive記事生成は0件でした。原因区分: {reason}")

    if generated_count > 0 or stocked_count > 0:
        msg = (
            f"✅ 【AI note事業】Collected {len(repos)} / Screened {len(screened)}件、"
            f"Screening API Calls {screening_calls}、Calibration {calibration_calls}回、Stock {stocked_count}件、"
            f"Deep Dive Ready {generated_count}件（試行{attempted}件）。\n"
            f"{GEMINI_BUDGET.summary()}\n"
            f"{GEMINI_USAGE_AUDIT.summary(include_contexts=False)}\n"
            f"{PERSISTENT_GEMINI_COUNTER.summary()}\nhttps://notion.so/{NOTION_DATABASE_ID}"
        )
        send_telegram_alert(msg)
        logger.info(msg)
    else:
        logger.info("本日は生成条件を満たす記事・Stockがありませんでした。")

    source_roi_state = update_source_roi_state(source_roi_state, screened, funnel)
    log_source_roi_profile(compute_source_roi_profile(source_roi_state), source_fetch_limits)
    generate_monthly_digest()
    run_product_delivery_maintenance()
    finalize_deep_dive_observability(funnel)
    logger.info(GEMINI_BUDGET.summary())
    logger.info(DEEP_DIVE_MODEL_BUDGET.summary())
    logger.info(PENDING_RETRY_REQUEST_BUDGET.summary())
    logger.info(PRODUCT_REVIEW_REQUEST_BUDGET.summary())
    logger.info(GEMINI_USAGE_AUDIT.summary(include_contexts=True))
    logger.info(PERSISTENT_GEMINI_COUNTER.summary())


if __name__ == "__main__":
    main()
