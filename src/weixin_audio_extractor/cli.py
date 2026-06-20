from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .core import WeixinAudioExtractorError, extract_weixin_audio


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract MP3 audio from a Weixin share link."
    )
    parser.add_argument("--url", required=True, help="Weixin share URL to process.")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for generated files. Defaults to the current directory.",
    )
    parser.add_argument(
        "--keep-video",
        action="store_true",
        help="Keep the downloaded MP4 file after extracting the MP3.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    try:
        result = extract_weixin_audio(
            args.url,
            Path(args.output_dir).expanduser().resolve(),
            keep_video=args.keep_video,
        )
    except WeixinAudioExtractorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
