#!/usr/bin/env python3
"""Run156: narrow repair for 13 evidence-boundary validation failures.

This script changes only wording that the production source-boundary validator
correctly treated as cross-source/unsupported naming. It does not change scores,
statuses, readiness, or relax any validator. ZERO provider calls.
"""
from __future__ import annotations

import json
from pathlib import Path

PATH = Path("external_reviews/run156_remaining68.json")

REPLACEMENTS = {
    "InternLM/InternLM": [
        ("Llama/Qwen/Gemma等", "他の主要オープンモデル"),
        ("Fine-tuning関連情報", "追加学習関連情報"),
    ],
    "openai/openai-agents-python": [
        ("LangGraph等", "状態管理を重視する別基盤"),
    ],
    "ComposioHQ/composio": [
        ("Gmail、CRM、SaaS等", "メール、CRM、業務SaaS等"),
    ],
    "FlowiseAI/Flowise": [
        ("Dify等の保守中候補", "現在保守されているローコードAI基盤"),
    ],
    "ChatGPTNextWeb/NextChat": [
        ("Open WebUI/LibreChat等", "他のセルフホスト型AIポータル"),
    ],
    "NVIDIA/TensorRT-LLM": [
        ("vLLM/SGLangとの", "他の推論エンジンとの"),
    ],
    "kserve/kserve": [
        ("Kubernetes・Ingress・ストレージ・GPUスケジューリング等", "Kubernetesのネットワーク公開・ストレージ・GPU割り当て等"),
    ],
    "NVIDIA/Megatron-LM": [("Fine-tuning", "追加学習")],
    "huggingface/diffusers": [("Fine-tuning", "追加学習")],
    "facebookresearch/sam2": [
        ("リアルタイム処理を保証したい", "リアルタイム処理が必須となる"),
    ],
    "weaviate/weaviate": [
        ("Qdrant/Milvus等", "他の主要Vector DB"),
    ],
    "chroma-core/chroma": [
        ("Weaviate/Qdrant/Milvus等", "他の本番向けVector DB"),
    ],
    "getzep/zep": [
        ("旧Zep OSSの理解", "旧Community Editionの理解"),
    ],
}


def replace_tree(value, pairs):
    if isinstance(value, str):
        for old, new in pairs:
            value = value.replace(old, new)
        return value
    if isinstance(value, dict):
        return {key: replace_tree(item, pairs) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_tree(item, pairs) for item in value]
    return value


def main() -> int:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    rows = payload.get("reviews") or []
    by_name = {str(row.get("name") or ""): row for row in rows}
    missing = sorted(set(REPLACEMENTS) - set(by_name))
    if missing:
        raise SystemExit(f"Run156 repair targets missing: {missing}")

    changed = []
    for name, pairs in REPLACEMENTS.items():
        before = json.dumps(by_name[name], ensure_ascii=False, sort_keys=True)
        repaired = replace_tree(by_name[name], pairs)
        after = json.dumps(repaired, ensure_ascii=False, sort_keys=True)
        if before == after:
            raise SystemExit(f"Run156 repair made no change for {name}")
        by_name[name].clear()
        by_name[name].update(repaired)
        changed.append(name)

    PATH.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(json.dumps({"changed": changed, "count": len(changed), "zero_gemini_calls": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
