from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .contract import Phase0Case, validate_phase0_cases

TARGET_READER = "AI導入・事業開発・経営判断・企画判断を行う成人ビジネスパーソン"


@dataclass(frozen=True, slots=True)
class ReplayCase:
    case: Phase0Case
    theme: str
    ready_status: str
    source: str
    primary_url: str
    management: Mapping[str, object]


def _management(**values: object) -> Mapping[str, object]:
    return MappingProxyType(dict(values))


def _phase_case(
    *,
    case_id: str,
    title: str,
    sources: tuple[str, ...],
    source_summary: str,
    what: str,
    why_important: str,
    decision: str,
    decision_score: int,
    decision_reason: str,
    action: str,
) -> Phase0Case:
    evidence = (
        f"Source Summary: {source_summary}",
        f"What: {what}",
        f"Why Important: {why_important}",
        f"Decision: {decision}",
        f"Decision Reason: {decision_reason}",
        f"Action: {action}",
    )
    facts = (
        source_summary,
        what,
        why_important,
        decision_reason,
        action,
    )
    return Phase0Case(
        case_id=case_id,
        title=title,
        evidence=evidence,
        facts=facts,
        sources=sources,
        target_reader=TARGET_READER,
    )


_FFT_CASE = _phase_case(
    case_id="3f8479ff-dca9-8146-b90d-df1fc42c40ef",
    title="A look at OpenAI’s math that’s claimed computes faster Fourier transforms",
    sources=(
        "https://www.argmin.net/p/faster-fourier-transforms",
        "https://news.ycombinator.com/item?id=50065932",
    ),
    source_summary="OpenAIが公開した数学リポジトリに含まれる「高速フーリエ変換（FFT）」の高速化手法について、専門家が「実用性は皆無」と指摘。理論上の計算量は削減されているが、実効速度を決める定数項が天文学的に巨大なため。",
    what="OpenAIが標準的なFFT（O(n log n)）を理論上上回る計算手法を提示したが、膨大な定数項を持つ「銀河アルゴリズム」であり、現実のコンピュータでは動作しないことが判明した。",
    why_important="AIが生成する数学的証明が「理論上の正しさ」と「物理的な実用性」を混同させるリスクを示しており、意思決定者が技術評価を行う際の重要な教訓となる。",
    decision="AVOID",
    decision_score=42,
    decision_reason="処理速度を決定する定数項が 10^100 規模と極大であり、宇宙規模のデータ量でない限り従来手法より遅いため。また、現実のハードウェアでは不可能な計算モデルを前提としている。",
    action="現状の標準ライブラリ（FFTW等）を継続利用し、AI発の数学的成果に対しては、実効速度（定数項）と計算モデルの物理的妥当性を精査する。",
)

_ELASTIC_CASE = _phase_case(
    case_id="3fa479ff-dca9-8194-a493-cb3a0d2b3a36",
    title="Your Transformer Is Secretly Elastic",
    sources=("https://arxiv.org/abs/2610.20588v1",),
    source_summary="固定サイズのモデル（S/B/L等）を、再学習なしで計算資源に合わせて伸縮可能にする手法が提案された。既存の学習済みモデルから数分で「弾力性のある」単一モデルを作成し、精度を維持したまま最大60%の計算量を削減できる。",
    what="学習済みTransformerの内部ユニット（ニューロンやアテンションヘッド）を共通の尺度でランク付けし、推論時に動的に計算量を切り替え可能にする技術。",
    why_important="負荷やハードウェア制約に応じてモデルを切り替える手間が省け、一つのモデルで低遅延な推論から高精度な処理までをカバーできる。インフラコストと運用複雑性の低減に寄与する。",
    decision="TRY",
    decision_score=72,
    decision_reason="再学習が不要であり、既存の資産（DINOv3やViTなど）をそのまま活用できる点、および50%の削減で精度低下が0.8%に留まるという高い実用性が示されているため。",
    action="公開されている実装コードを用い、自社の推論環境（A100等）でDINOv3やViTなどの既存モデルがどの程度の精度・速度トレードオフを実現できるかプロトタイプ検証を行う。",
)

_CLAUDE_CASE = _phase_case(
    case_id="3f3479ff-dca9-8153-a62e-d3768adb3160",
    title="Claude now in Google Docs, Sheets and Slides",
    sources=(
        "https://claude.com/resources/articles/claude-now-works-in-google-docs-sheets-and-slides",
        "https://claude.com/download",
        "https://code.claude.com/docs/en/overview",
        "https://news.ycombinator.com/item?id=49998495",
    ),
    source_summary="AnthropicがClaudeをGoogle Workspace（ドキュメント、スプレッドシート、スライド）へ直接統合しました。サイドバーからの閲覧・編集に加え、Claude側からファイルを作成・操作できるコネクタ機能もパブリックベータとして提供されます。",
    what="Google Workspace上でClaudeをサイドバーとして呼び出し、開いているファイルの内容を読み取らせたり、直接編集やグラフ作成を依頼したりできる機能。",
    why_important="ブラウザのタブを行き来する手間（コピペ作業）が解消され、文書の推敲、複雑なスプレッドシートの数式作成、スライドのレイアウト調整を同一画面で完結できるため、実務のスピード向上が見込めます。",
    decision="TRY",
    decision_score=70,
    decision_reason="有料プランユーザーなら追加コストなく試行可能であり、企業の既存権限設定を維持したまま、実務に即したAI支援を検証できるため。",
    action="Google Workspace Marketplaceからアドオンをインストールし、報告書作成やデータ整理の既存ワークフローで「下書きの推敲」や「表の自動生成」を試行する。",
)

READY_CASES = (
    ReplayCase(
        case=_FFT_CASE,
        theme="criticism_risk",
        ready_status="Ready",
        source="HackerNews",
        primary_url=_FFT_CASE.sources[0],
        management=_management(
            source_summary_text=_FFT_CASE.facts[0],
            what_text=_FFT_CASE.facts[1],
            why_important_text=_FFT_CASE.facts[2],
            decision_text="AVOID",
            score=42,
            decision_reason_text=_FFT_CASE.facts[3],
            action_text=_FFT_CASE.facts[4],
            article_value=85,
        ),
    ),
    ReplayCase(
        case=_ELASTIC_CASE,
        theme="tech_breakthrough",
        ready_status="Ready",
        source="ArXiv",
        primary_url=_ELASTIC_CASE.sources[0],
        management=_management(
            source_summary_text=_ELASTIC_CASE.facts[0],
            what_text=_ELASTIC_CASE.facts[1],
            why_important_text=_ELASTIC_CASE.facts[2],
            decision_text="TRY",
            score=72,
            decision_reason_text=_ELASTIC_CASE.facts[3],
            action_text=_ELASTIC_CASE.facts[4],
            article_value=85,
        ),
    ),
    ReplayCase(
        case=_CLAUDE_CASE,
        theme="product_update",
        ready_status="Ready",
        source="HackerNews",
        primary_url=_CLAUDE_CASE.sources[0],
        management=_management(
            source_summary_text=_CLAUDE_CASE.facts[0],
            what_text=_CLAUDE_CASE.facts[1],
            why_important_text=_CLAUDE_CASE.facts[2],
            decision_text="TRY",
            score=70,
            decision_reason_text=_CLAUDE_CASE.facts[3],
            action_text=_CLAUDE_CASE.facts[4],
            article_value=85,
        ),
    ),
)

validate_phase0_cases(item.case for item in READY_CASES)
