from reader_experience_signals import reader_experience_signals


def _opening(article: str, limit: int) -> str:
    return article[:limit]


def test_inline_gloss_counts_as_plain_language_bridge_without_requiring_analogy():
    article = """
# AIエージェントの権限を職級で分ける

AIコーディングツールに重要な変更まで任せてよいのか迷う場面があります。そこで、AIに職級（Tier）と操作上限（Ceiling）を持たせ、担当範囲を越えた作業は上位へ引き継ぐ設計を考えます。

## 役割ごとに境界を作る

T0（インターン相当）は小さな修正だけを担当し、認証やデータ移行には触れません。T1、T2、T3と段階を上げるほど扱える変更は広がりますが、判断が難しい処理はハンドオフ（引き継ぎパケット）にまとめます。CLIから実行する場合でも、誰が何を変更したかを残して確認できることが重要です。

## 小さく試して判断する

私なら、まず影響の少ない検証用リポジトリで、職級の境界と引き継ぎが期待どおり動くかを確認します。主要な本番環境へ一括導入する前に、失敗時に止まれることと変更を追跡できることを比較します。
"""
    result = reader_experience_signals(article, _opening)

    assert result["bridge_needed"] is True
    assert result["inline_gloss_present"] is True
    assert result["plain_language_bridge"] == "GOOD"
    assert result["jargon_translation"] == "GOOD"
    assert result["non_engineer_core_clarity"] == "GOOD"


def test_one_inline_gloss_does_not_excuse_repeated_dense_untranslated_jargon():
    dense = (
        "Transformer Architecture Attention Pipeline Runtime Kernel CUDA TensorRT Scheduler "
        "Inference Backend Throughput Latency Quantization KV-Cache Routing RoPE RMSNorm GQA MLA "
    )
    article = f"""
# LLMの内部構造を比較する

大型言語モデル（LLM）の設計差を調べます。ここでは構造を読むこと自体が目的で、本番導入の判断とは分けます。

## 実装の詳細

{dense}{dense}設計上の差分を確認します。

{dense}{dense}各層の処理順序と依存関係を確認します。

{dense}{dense}実装識別子と処理経路を比較します。

{dense}{dense}性能条件と内部構造を並べて確認します。

## 判断

私なら本番ライブラリとしては使わず、構造学習のための比較対象として限定的に確認します。
"""
    result = reader_experience_signals(article, _opening)

    assert result["inline_gloss_present"] is True
    assert result["jargon_dense_paragraph_count"] >= 2
    assert result["jargon_translation"] == "REVIEW"
    assert result["non_engineer_core_clarity"] == "REVIEW"
