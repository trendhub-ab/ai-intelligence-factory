"""Run395C: preserve WATCH while making the bounded validation action concrete."""
import run395_gorules_full_gate_revalidation as base

_original_parsed = base.parsed

def _parsed(core):
    row = _original_parsed(core)
    row["action_text"] = "割引ルール1つを検証環境へ移し、同じ入力で既存実装との出力一致を比較検証し、変更作業時間と実行時間を計測する。"
    return row

base.parsed = _parsed

if __name__ == "__main__":
    raise SystemExit(base.main())
