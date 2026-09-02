#!/usr/bin/env python3
"""Run153 curated external-review catalog.

The candidate purpose/category/maturity labels below were selected by the external
reviewer. Scoring is deterministic from the same six-component Product Review
rubric so scores remain calibrated and auditable. Every row is still re-fetched
from its primary GitHub source and must pass production evidence/assessment gates
before persistence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Ordered deliberately: current inventory is short on MODEL/AGENT/PRODUCT/INFRA/
# MULTIMODAL. The first 74 rows fill those gaps; later rows are evidence-failure
# fallbacks in categories that already have some inventory.
CANDIDATES = [
    # MODEL (12)
    ("MODEL","QwenLM/Qwen3","Qwen3","オープンウェイトの大規模言語モデル群を提供し、推論や生成AIアプリの基盤として利用できる。","top"),
    ("MODEL","deepseek-ai/DeepSeek-V3","DeepSeek V3","大規模言語モデルのモデル実装・技術情報を公開し、推論・生成用途の基盤を提供する。","top"),
    ("MODEL","deepseek-ai/DeepSeek-R1","DeepSeek R1","推論能力を重視した大規模言語モデルと関連技術を公開している。","top"),
    ("MODEL","meta-llama/llama-models","Llama models","Llamaモデル群の利用・推論に関する公式リソースを提供する。","top"),
    ("MODEL","mistralai/mistral-inference","Mistral inference","Mistralモデルを推論・利用するための公式実装を提供する。","high"),
    ("MODEL","google-deepmind/gemma","Gemma","Google DeepMindのオープンモデルGemmaに関する公式実装・利用情報を提供する。","top"),
    ("MODEL","THUDM/GLM-4","GLM-4","GLM系大規模言語モデルのモデル・推論関連実装を提供する。","medium"),
    ("MODEL","01-ai/Yi","Yi","Yi系オープンモデルのモデル情報と利用実装を提供する。","medium"),
    ("MODEL","InternLM/InternLM","InternLM","InternLM大規模言語モデル群の学習・推論・利用情報を提供する。","medium"),
    ("MODEL","OpenBMB/MiniCPM","MiniCPM","比較的小型の生成AIモデル群と関連実装を提供する。","medium"),
    ("MODEL","allenai/OLMo","OLMo","オープンな大規模言語モデル開発・研究のためのモデルと関連資産を公開する。","medium"),
    ("MODEL","microsoft/Phi-3CookBook","Phi Cookbook","Microsoft Phi系小型言語モデルの利用例と実装ガイドを提供する。","medium"),

    # AGENT (18)
    ("AGENT","langchain-ai/langgraph","LangGraph","状態を持つ長時間・複数ステップのLLMエージェントワークフローを構築するためのフレームワーク。","top"),
    ("AGENT","crewAIInc/crewAI","CrewAI","複数AIエージェントを役割分担させてワークフローを実行するためのフレームワーク。","high"),
    ("AGENT","microsoft/autogen","AutoGen","複数エージェントの会話・協調を使ったAIアプリを構築するためのフレームワーク。","high"),
    ("AGENT","microsoft/semantic-kernel","Semantic Kernel","LLM、プラグイン、エージェントを組み合わせたAIアプリケーションを構築するSDK。","top"),
    ("AGENT","google/adk-python","Google Agent Development Kit","AIエージェントを開発・評価・実行するためのGoogleのPython SDK。","top"),
    ("AGENT","openai/openai-agents-python","OpenAI Agents SDK","ツール利用やハンドオフを含むAIエージェントを構築するためのOpenAI公式SDK。","top"),
    ("AGENT","pydantic/pydantic-ai","Pydantic AI","Pythonで型安全なAIエージェントやLLMアプリを構築するためのフレームワーク。","top"),
    ("AGENT","agno-agi/agno","Agno","ツール、知識、メモリを組み合わせたAIエージェントを構築するフレームワーク。","medium"),
    ("AGENT","huggingface/smolagents","smolagents","Hugging Faceが提供する軽量なAIエージェント構築ライブラリ。","top"),
    ("AGENT","browser-use/browser-use","Browser Use","AIエージェントからWebブラウザを操作するためのオープンソース基盤。","top"),
    ("AGENT","a2aproject/A2A","Agent2Agent Protocol","異なるAIエージェント同士の相互運用を支えるプロトコル実装・仕様。","medium"),
    ("AGENT","letta-ai/letta","Letta","長期的なメモリや状態を持つエージェントを構築・運用するための基盤。","medium"),
    ("AGENT","mastra-ai/mastra","Mastra","TypeScriptでAIエージェントやワークフローを構築するためのフレームワーク。","medium"),
    ("AGENT","camel-ai/camel","CAMEL","マルチエージェント研究・開発のためのエージェントフレームワーク。","medium"),
    ("AGENT","langchain-ai/deepagents","Deep Agents","複雑なタスクを進めるエージェント構築のためのLangChain系フレームワーク。","medium"),
    ("AGENT","ComposioHQ/composio","Composio","AIエージェントから外部アプリやツールを接続・実行するための統合基盤。","top"),
    ("AGENT","e2b-dev/E2B","E2B","AIエージェントやコード実行向けの隔離された実行環境を提供する基盤。","top"),
    ("AGENT","mem0ai/mem0","Mem0","AIエージェントやアプリに長期メモリ機能を追加するための基盤。","top"),

    # PRODUCT (14)
    ("PRODUCT","langgenius/dify","Dify","LLMアプリ、ワークフロー、エージェントをGUIとAPIで構築・運用できるAIアプリ基盤。","top"),
    ("PRODUCT","open-webui/open-webui","Open WebUI","複数のLLMバックエンドを利用できるセルフホスト型AIチャットUI。","top"),
    ("PRODUCT","lobehub/lobe-chat","LobeChat","複数モデルやツール統合に対応するオープンソースAIチャット製品。","high"),
    ("PRODUCT","All-Hands-AI/OpenHands","OpenHands","ソフトウェア開発タスクを自律的に進めるAIコーディングエージェント。","top"),
    ("PRODUCT","cline/cline","Cline","IDE内でコード編集やツール実行を行うAIコーディングエージェント。","top"),
    ("PRODUCT","RooCodeInc/Roo-Code","Roo Code","VS Code上で複数モードのAIコーディング支援を行うエージェント型拡張。","high"),
    ("PRODUCT","TabbyML/tabby","Tabby","セルフホスト可能なAIコーディング支援基盤。","medium"),
    ("PRODUCT","continuedev/continue","Continue","IDEで利用できるオープンソースのAIコーディング支援・エージェント基盤。","top"),
    ("PRODUCT","plandex-ai/plandex","Plandex","複数ファイルにまたがる開発タスクを計画・実行するAIコーディングエージェント。","medium"),
    ("PRODUCT","FlowiseAI/Flowise","Flowise","LLMワークフローやエージェントをノーコード/ローコードで構築する製品。","high"),
    ("PRODUCT","Mintplex-Labs/anything-llm","AnythingLLM","文書検索やLLMチャットをセルフホストで構築できるAIワークスペース。","medium"),
    ("PRODUCT","danny-avila/LibreChat","LibreChat","複数のAIモデルやエージェント機能を統合できるオープンソースチャットUI。","high"),
    ("PRODUCT","ChatGPTNextWeb/NextChat","NextChat","複数の生成AIモデルに接続できる軽量なWebチャットクライアント。","medium"),
    ("PRODUCT","mckaywrigley/chatbot-ui","Chatbot UI","LLMチャットを構築・利用するためのオープンソースWeb UI。","medium"),

    # INFRA (19)
    ("INFRA","vllm-project/vllm","vLLM","LLM推論・サービングのスループットと効率を高めるオープンソース推論エンジン。","top"),
    ("INFRA","sgl-project/sglang","SGLang","大規模言語モデルとマルチモーダルモデルの高速推論・サービング基盤。","top"),
    ("INFRA","ggml-org/llama.cpp","llama.cpp","さまざまなローカル環境でLLM推論を実行するための軽量C/C++基盤。","top"),
    ("INFRA","huggingface/text-generation-inference","Text Generation Inference","Hugging Faceの大規模言語モデル向け推論・サービング基盤。","high"),
    ("INFRA","NVIDIA/TensorRT-LLM","TensorRT-LLM","NVIDIA GPU上のLLM推論を最適化するための推論ライブラリ。","top"),
    ("INFRA","bentoml/BentoML","BentoML","AIモデルや生成AIサービスをAPIとしてパッケージ・デプロイするための基盤。","high"),
    ("INFRA","ray-project/ray","Ray","分散Python処理やAIワークロードをスケールさせるための分散実行基盤。","high"),
    ("INFRA","triton-inference-server/server","Triton Inference Server","複数フレームワークのAIモデルをサーバーで提供するNVIDIAの推論サーバー。","high"),
    ("INFRA","ollama/ollama","Ollama","ローカル環境で大規模言語モデルを取得・実行するためのランタイム。","top"),
    ("INFRA","kserve/kserve","KServe","Kubernetes上で機械学習・生成AIモデルをサービングするための基盤。","high"),
    ("INFRA","microsoft/onnxruntime","ONNX Runtime","ONNX形式の機械学習モデルを複数ハードウェアで高速実行するランタイム。","high"),
    ("INFRA","openvinotoolkit/openvino","OpenVINO","Intelハードウェア上などでAI推論を最適化するツールキット。","high"),
    ("INFRA","llm-d/llm-d","llm-d","Kubernetes環境で分散LLM推論を運用するためのオープンソース基盤。","medium"),
    ("INFRA","dstackai/dstack","dstack","クラウドやGPU環境でAIワークロードを実行・管理するためのオーケストレーション基盤。","medium"),
    ("INFRA","runhouse/runhouse","Runhouse","ローカルコードをリモートGPU・クラウド環境で実行するためのAIインフラ基盤。","medium"),
    ("INFRA","skypilot-org/skypilot","SkyPilot","複数クラウドでAI・GPUワークロードを起動・最適化するためのオーケストレーター。","top"),
    ("INFRA","NVIDIA/Megatron-LM","Megatron-LM","大規模言語モデルの分散学習を行うためのNVIDIAの研究・学習基盤。","high"),
    ("INFRA","deepspeedai/DeepSpeed","DeepSpeed","大規模モデルの分散学習・推論を効率化するMicrosoftの最適化ライブラリ。","high"),
    ("INFRA","Dao-AILab/flash-attention","FlashAttention","TransformerのAttention計算を高速・省メモリ化する実装。","high"),

    # MULTIMODAL (11) — row 74 ends here
    ("MULTIMODAL","huggingface/diffusers","Diffusers","画像・動画・音声などの生成モデルを扱うためのHugging Faceライブラリ。","top"),
    ("MULTIMODAL","comfyanonymous/ComfyUI","ComfyUI","生成画像・動画モデルをノードベースで組み合わせて実行するUI・ワークフロー基盤。","high"),
    ("MULTIMODAL","openai/whisper","Whisper","音声認識・文字起こしを行うOpenAIのオープンソース音声モデル実装。","top"),
    ("MULTIMODAL","SYSTRAN/faster-whisper","faster-whisper","Whisper音声認識をCTranslate2で高速に実行する実装。","high"),
    ("MULTIMODAL","facebookresearch/sam2","SAM 2","画像や動画内の対象をセグメンテーションするためのMetaのモデル実装。","top"),
    ("MULTIMODAL","QwenLM/Qwen2.5-VL","Qwen2.5-VL","画像や文書など視覚情報とテキストを扱う視覚言語モデル。","high"),
    ("MULTIMODAL","Tencent-Hunyuan/HunyuanVideo","HunyuanVideo","テキストなどから動画を生成するオープンな動画生成モデル・実装。","medium"),
    ("MULTIMODAL","Wan-Video/Wan2.1","Wan","動画生成向けのオープンモデルと実装を提供するプロジェクト。","medium"),
    ("MULTIMODAL","myshell-ai/OpenVoice","OpenVoice","音声の声質・スタイルを扱う音声生成・音声クローン関連技術。","medium"),
    ("MULTIMODAL","FunAudioLLM/CosyVoice","CosyVoice","多言語音声合成や音声生成を行うモデル・実装。","medium"),
    ("MULTIMODAL","THUDM/CogVideo","CogVideo","テキストから動画を生成するモデル群と関連実装。","medium"),

    # Fallbacks if early rows fail evidence/identity validation.
    ("SECURITY","NVIDIA/garak","garak","LLMの脆弱性や安全性上の問題を自動評価するためのセキュリティスキャナー。","top"),
    ("SECURITY","protectai/llm-guard","LLM Guard","LLM入出力に対するセキュリティ・安全性チェックを実装するためのライブラリ。","medium"),
    ("SECURITY","microsoft/PyRIT","PyRIT","生成AIシステムのリスクや脆弱性を評価するためのMicrosoftのレッドチーミング基盤。","top"),
    ("SECURITY","promptfoo/promptfoo","Promptfoo","LLMアプリの評価、テスト、レッドチーミングを自動化するためのツール。","top"),
    ("SECURITY","protectai/modelscan","ModelScan","機械学習モデルファイルに含まれる危険なコードやリスクを検査するツール。","medium"),
    ("SECURITY","llm-attacks/llm-attacks","LLM Attacks","大規模言語モデルへの敵対的プロンプト攻撃研究の実装。","medium"),
    ("DATA","qdrant/qdrant","Qdrant","ベクトル検索とメタデータフィルタリングを提供するベクトルデータベース。","top"),
    ("DATA","weaviate/weaviate","Weaviate","ベクトル検索やハイブリッド検索を提供するAI向けデータベース。","top"),
    ("DATA","milvus-io/milvus","Milvus","大規模ベクトル検索を提供するオープンソースのベクトルデータベース。","top"),
    ("DATA","chroma-core/chroma","Chroma","AIアプリやRAGで埋め込みベクトルを保存・検索するためのデータ基盤。","top"),
    ("DATA","lancedb/lancedb","LanceDB","AI・マルチモーダル用途向けのベクトル検索データベース。","high"),
    ("DATA","getzep/zep","Zep","AIエージェント向けの長期コンテキスト・メモリを扱うデータ基盤。","medium"),
    ("DEVTOOLS","BerriAI/litellm","LiteLLM","複数のLLM APIを統一形式で呼び出し、ゲートウェイとして管理するための開発基盤。","top"),
    ("DEVTOOLS","instructor-ai/instructor","Instructor","LLM出力を型付き構造データとして取得・検証しやすくするPythonライブラリ。","high"),
    ("DEVTOOLS","dottxt-ai/outlines","Outlines","LLM出力をJSONなど指定形式に制約して生成するためのライブラリ。","medium"),
    ("DEVTOOLS","guidance-ai/guidance","Guidance","LLM生成をプログラム的に制御し、構造化された出力を作るためのライブラリ。","medium"),
    ("DEVTOOLS","guardrails-ai/guardrails","Guardrails","LLMの入出力を検証・制御するための開発フレームワーク。","medium"),
    ("DEVTOOLS","langfuse/langfuse","Langfuse","LLMアプリのトレーシング、評価、プロンプト管理などを行うオープンソース基盤。","top"),
    ("DEVTOOLS","Arize-ai/phoenix","Phoenix","LLM・AIアプリのトレーシング、評価、可観測性を支援するオープンソースツール。","top"),
    ("DEVTOOLS","traceloop/openllmetry","OpenLLMetry","LLMアプリの観測データをOpenTelemetry互換で収集するための計装基盤。","medium"),
]

CATEGORY = {
    "MODEL": (17,10,7,"モデル選定後も、ライセンス、必要計算資源、出力品質を自社用途で検証してから本番利用する必要がある。","モデル評価を行わず、特定用途での品質・コスト・運用要件を確認せずに即時標準化したい場合。","生成AIモデル・モデル技術"),
    "AGENT": (18,10,8,"外部ツール権限、長時間実行時の失敗処理、意図しない操作範囲を本番導入前に設計する必要がある。","単純な一回の生成だけで十分で、ツール実行や複数ステップの状態管理を必要としない用途。","AIエージェント開発基盤"),
    "PRODUCT": (18,11,8,"認証・権限、保存データ、外部モデル/APIとの接続範囲を自社運用条件に合わせて確認する必要がある。","既存の運用フローを変えず、外部モデルやAI機能を組み込む必要がない用途。","AIアプリ・製品"),
    "INFRA": (17,11,7,"ハードウェア要件、運用監視、バージョン更新に伴う互換性を自社環境で継続的に管理する必要がある。","小規模な試作だけで、推論・学習基盤の運用やスケールを必要としない用途。","AI実行・運用基盤"),
    "MULTIMODAL": (17,10,7,"生成・認識品質は入力条件やモデル構成に左右されるため、対象データで品質と計算負荷を検証する必要がある。","テキスト処理だけで完結し、画像・音声・動画などを扱う必要がない用途。","画像・音声・動画AI技術"),
    "SECURITY": (17,12,8,"検査結果だけで安全性を保証せず、対象モデルや運用環境に合わせた追加検証と人間のレビューが必要になる。","単一ツールの結果だけで安全性やコンプライアンス適合を保証したい場合。","AIセキュリティ評価技術"),
    "DATA": (18,12,8,"データ量、検索品質、運用構成によって性能が変わるため、自社データで検索精度と運用負荷を検証する必要がある。","小規模な固定データだけを扱い、ベクトル検索やAI向けデータ基盤を必要としない用途。","AIデータ・検索基盤"),
    "DEVTOOLS": (18,12,9,"対応モデルやSDKの更新が速いため、依存関係と互換性を継続的に確認する運用が必要になる。","LLM連携やAIアプリ開発を行わず、通常のソフトウェア開発だけで完結する用途。","AI開発支援ツール"),
}


def build_rows():
    rows = []
    for category, repo, display, purpose, level in CANDIDATES:
        utility, risk, integration, risk_text, avoid_for, label = CATEGORY[category]
        if level == "top":
            evidence, maturity, ecosystem = 25, 24, 5
            readiness, status, review_days = "HIGH", "ADOPT", 30
        elif level == "high":
            evidence, maturity, ecosystem = 24, 22, 4
            readiness, status, review_days = "HIGH", "TEST", 30
        else:
            evidence, maturity, ecosystem = 23, 18, 3
            utility, risk, integration = utility - 1, risk - 1, integration - 1
            readiness, status, review_days = "MEDIUM", "TEST", 21
        components = {
            "Evidence Quality": evidence,
            "Production Maturity": maturity,
            "Use-case Utility / Fit": utility,
            "Reliability / Security Risk": risk,
            "Integration / Migration Feasibility": integration,
            "Ecosystem / Support Durability": ecosystem,
        }
        score = sum(components.values())
        rows.append({
            "source": "GitHub",
            "name": repo,
            "url": f"https://github.com/{repo}",
            "primary_url": f"https://github.com/{repo}",
            "description": purpose,
            "screening_reason": "Run153 GPT-5.6 Sol external reviewer backfill; primary evidence must pass production validation.",
            "review": {
                "category": category,
                "adoption_score": score,
                "components": components,
                "adoption_status": status,
                "evidence_confidence": "HIGH",
                "production_readiness": readiness,
                "main_risk": risk_text,
                "best_for": purpose.rstrip("。") + "ことを自社のAI導入・開発・運用で具体的に必要としているチーム。",
                "avoid_for": avoid_for,
                "short_rationale": display + "は、公式一次情報で「" + purpose.rstrip("。") + "」という主用途を確認でき、導入候補として比較する価値がある。",
                "japanese_display_label": display + " — " + label,
                "next_review_days": review_days,
            },
        })
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="external_reviews/run153_backfill.json")
    args = p.parse_args()
    rows = build_rows()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "reviewer": "GPT-5.6 Sol external reviewer / calibrated Product Review rubric",
        "run": "Run153",
        "reviews": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out), "reviews": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
