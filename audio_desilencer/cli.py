from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .audio_processor import (
    DEFAULT_MIN_SILENCE_MS,
    DEFAULT_TARGET_SILENCE_MS,
    AudioProcessor,
    _parse_threshold,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remove long silence without processing retained audio"
    )
    parser.add_argument("input_file", help="Input audio file path")
    parser.add_argument("--output_folder", default="output", help="Output folder path")
    parser.add_argument(
        "--min_silence_len",
        type=int,
        default=DEFAULT_MIN_SILENCE_MS,
        help=f"Minimum continuous silence in milliseconds (default: {DEFAULT_MIN_SILENCE_MS})",
    )
    parser.add_argument(
        "--threshold",
        type=_parse_threshold,
        default="auto",
        help="Silence threshold in dBFS, or 'auto' (default) for deterministic noise-floor estimation",
    )
    parser.add_argument(
        "--hysteresis_db",
        type=float,
        default=None,
        help="Optional dB gap required to leave silence; auto mode defaults to 3 dB",
    )
    parser.add_argument(
        "--target_silence_len",
        type=int,
        default=DEFAULT_TARGET_SILENCE_MS,
        help=f"Silence to keep for each internal pause in milliseconds (default: {DEFAULT_TARGET_SILENCE_MS})",
    )
    parser.add_argument(
        "--output_format",
        default="wav",
        help="Output audio format (default: wav)",
    )
    parser.add_argument("--output_stem", default=None, help="Optional base name for generated output files")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        processor = AudioProcessor(args.input_file)
        processor.process_audio(
            min_silence_len=args.min_silence_len,
            threshold=args.threshold,
            target_silence_len=args.target_silence_len,
            hysteresis_db=args.hysteresis_db,
            output_folder=args.output_folder,
            output_format=args.output_format,
            output_stem=args.output_stem,
        )
    except (OSError, ValueError) as exc:
        print(f"audio-desilencer: error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
