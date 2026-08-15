"""Pillowアイキャッチだけを生成するための手動テスト用スクリプト。

Gemini、Notion、Telegram、GitHub Contents APIは呼び出さない。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Pillow scorecard eyecatch test")
    parser.add_argument("--source", choices=sorted(pipeline.SOURCE_BACKGROUND_IMAGE), default="GitHub")
    parser.add_argument("--score", type=int, default=82)
    parser.add_argument("--technical-impact", type=int, default=21)
    parser.add_argument("--urgency", type=int, default=16)
    parser.add_argument("--output-dir", default="eyecatch_test_outputs")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"eyecatch_{args.source}_{args.score}.png"
    generated = pipeline.generate_eyecatch_image(
        "eyecatch test",
        str(output_path),
        args.source,
        decision_score=args.score,
        technical_impact=args.technical_impact,
        urgency=args.urgency,
    )
    if not generated:
        print(f"SKIPPED: Decision Score {args.score} is below {pipeline.EYECATCH_MIN_DECISION_SCORE}.")
        return 2

    print(f"GENERATED: {generated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
