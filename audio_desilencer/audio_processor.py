from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError, CouldntEncodeError
from pydub.silence import detect_nonsilent


Timeline = list[tuple[int, int]]


@dataclass(frozen=True)
class ProcessingResult:
    silent_audio_path: str
    non_silent_audio_path: str
    silent_timeline_path: str
    non_silent_timeline_path: str
    silent_ranges: tuple[tuple[int, int], ...]
    non_silent_ranges: tuple[tuple[int, int], ...]


def _normalize_ranges(ranges: Iterable[Sequence[int]], total_duration: int) -> Timeline:
    """Clamp, sort, and merge time ranges into non-overlapping millisecond intervals."""
    total = max(0, int(total_duration))
    normalized: Timeline = []

    for raw in ranges:
        if len(raw) != 2:
            raise ValueError("Each timeline range must contain exactly two values")
        start = max(0, min(total, int(raw[0])))
        end = max(0, min(total, int(raw[1])))
        if end <= start:
            continue
        normalized.append((start, end))

    normalized.sort(key=lambda item: (item[0], item[1]))
    merged: Timeline = []
    for start, end in normalized:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            previous_start, previous_end = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end))
    return merged


def complement_ranges(total_duration: int, ranges: Iterable[Sequence[int]]) -> Timeline:
    """Return the complement of ranges over [0, total_duration]."""
    total = max(0, int(total_duration))
    normalized = _normalize_ranges(ranges, total)
    complement: Timeline = []
    cursor = 0

    for start, end in normalized:
        if start > cursor:
            complement.append((cursor, start))
        cursor = max(cursor, end)

    if cursor < total:
        complement.append((cursor, total))
    return complement


class AudioProcessor:
    def __init__(self, input_file_path: str | os.PathLike[str]):
        self.input_file_path = os.fspath(input_file_path)
        self.audio = AudioSegment.from_file(self.input_file_path)

    def split_audio_by_silence(self, min_silence_len: int, threshold: int) -> Timeline:
        ranges = detect_nonsilent(
            self.audio,
            min_silence_len=min_silence_len,
            silence_thresh=threshold,
        )
        return [(int(start), int(end)) for start, end in ranges]

    def save_audio(self, audio: AudioSegment, output_path: str, output_format: str = "mp3") -> None:
        audio.export(output_path, format=output_format)
        print(f"Saved audio to {output_path}")

    def save_timeline_to_text(self, timeline_data: Iterable[Sequence[int]], output_path: str) -> None:
        timeline = [(int(start), int(end)) for start, end in timeline_data]
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(repr(timeline))
        print(f"Saved timeline data to {output_path}")

    def is_fully_silent(self, min_silence_len: int = 100, threshold: int = -30) -> bool:
        return not self.split_audio_by_silence(min_silence_len, threshold)

    def _join_ranges(self, ranges: Iterable[Sequence[int]]) -> AudioSegment:
        segments = [self.audio[int(start):int(end)] for start, end in ranges if int(end) > int(start)]
        if not segments:
            return AudioSegment.empty()
        return self.audio._spawn(b"".join(segment.raw_data for segment in segments))

    def process_audio(
        self,
        min_silence_len: int = 100,
        threshold: int = -30,
        output_folder: str | os.PathLike[str] = "output",
        output_format: str = "mp3",
        output_stem: str | None = None,
    ) -> ProcessingResult:
        if min_silence_len <= 0:
            raise ValueError("min_silence_len must be greater than zero")
        normalized_format = output_format.strip().lower()
        if not re.fullmatch(r"[a-z0-9]+", normalized_format):
            raise ValueError("output_format must be a simple format name such as 'mp3' or 'wav'")

        print("Processing audio...")
        duration = len(self.audio)
        non_silent_ranges = _normalize_ranges(
            self.split_audio_by_silence(min_silence_len, threshold),
            duration,
        )
        silent_ranges = complement_ranges(duration, non_silent_ranges)

        audio_silent = self._join_ranges(silent_ranges)
        audio_non_silent = self._join_ranges(non_silent_ranges)

        output_directory = Path(output_folder)
        output_directory.mkdir(parents=True, exist_ok=True)
        stem = output_stem or Path(self.input_file_path).stem or "audio"
        safe_stem = Path(stem).name
        if safe_stem in {"", ".", ".."}:
            raise ValueError("output_stem must contain a valid filename stem")

        silent_audio_path = output_directory / f"{safe_stem}_silent.{normalized_format}"
        non_silent_audio_path = output_directory / f"{safe_stem}_non_silent.{normalized_format}"
        silent_timeline_path = output_directory / f"{safe_stem}_silent_parts.txt"
        non_silent_timeline_path = output_directory / f"{safe_stem}_non_silent_parts.txt"

        self.save_audio(audio_silent, str(silent_audio_path), normalized_format)
        self.save_audio(audio_non_silent, str(non_silent_audio_path), normalized_format)
        self.save_timeline_to_text(silent_ranges, str(silent_timeline_path))
        self.save_timeline_to_text(non_silent_ranges, str(non_silent_timeline_path))

        print("Audio processing completed.")
        return ProcessingResult(
            silent_audio_path=str(silent_audio_path),
            non_silent_audio_path=str(non_silent_audio_path),
            silent_timeline_path=str(silent_timeline_path),
            non_silent_timeline_path=str(non_silent_timeline_path),
            silent_ranges=tuple(silent_ranges),
            non_silent_ranges=tuple(non_silent_ranges),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect and separate silent/non-silent audio regions")
    parser.add_argument("input_file", help="Input audio file path")
    parser.add_argument("--output_folder", default="output", help="Output folder path")
    parser.add_argument("--min_silence_len", type=int, default=100, help="Minimum silence length in milliseconds")
    parser.add_argument("--threshold", type=int, default=-30, help="Silence threshold in dBFS")
    parser.add_argument("--output_format", default="mp3", help="Output audio format (default: mp3)")
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
            output_folder=args.output_folder,
            output_format=args.output_format,
            output_stem=args.output_stem,
        )
    except (OSError, ValueError, CouldntDecodeError, CouldntEncodeError) as exc:
        print(f"audio-desilencer: error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
