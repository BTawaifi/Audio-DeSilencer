from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


Timeline = list[tuple[int, int]]


@dataclass(frozen=True)
class ProcessingResult:
    silent_audio_path: str
    non_silent_audio_path: str
    silent_timeline_path: str
    non_silent_timeline_path: str
    silent_ranges: tuple[tuple[int, int], ...]
    non_silent_ranges: tuple[tuple[int, int], ...]
    detected_silence_ranges: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class _AudioInfo:
    duration_ms: int
    sample_rate: int
    channels: int
    channel_layout: str | None


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


def build_removal_ranges(
    total_duration: int,
    detected_silence_ranges: Iterable[Sequence[int]],
    target_silence_len: int,
) -> Timeline:
    """Return only the middle portions of confirmed silence that are safe to delete.

    Internal pauses are shortened to ``target_silence_len`` total, split across both
    sides of the cut so speech retains its natural low-level lead-in and tail. Leading
    and trailing silence retain half that amount next to speech. A completely silent
    file is removed in full from the non-silent output.
    """
    total = max(0, int(total_duration))
    target = int(target_silence_len)
    if target < 0:
        raise ValueError("target_silence_len must be zero or greater")

    detected = _normalize_ranges(detected_silence_ranges, total)
    removals: Timeline = []
    left_keep = target // 2
    right_keep = target - left_keep

    for start, end in detected:
        duration = end - start
        if duration <= target:
            continue

        if start == 0 and end == total:
            cut_start, cut_end = 0, total
        elif start == 0:
            cut_start, cut_end = 0, end - right_keep
        elif end == total:
            cut_start, cut_end = start + left_keep, total
        else:
            cut_start, cut_end = start + left_keep, end - right_keep

        if cut_end > cut_start:
            removals.append((cut_start, cut_end))

    return _normalize_ranges(removals, total)


class AudioProcessor:
    """Non-destructive silence editor backed directly by FFmpeg.

    The processor never normalizes, limits, filters, crossfades, or otherwise changes
    retained audio. It detects sufficiently long silence, removes only the middle of
    those pauses, and asks FFmpeg to concatenate the untouched retained source spans.
    """

    def __init__(self, input_file_path: str | os.PathLike[str]):
        self.input_file_path = os.fspath(input_file_path)
        if not Path(self.input_file_path).is_file():
            raise OSError(f"Input file does not exist: {self.input_file_path}")
        self._require_ffmpeg()
        self._info = self._probe_audio()

    @staticmethod
    def _require_ffmpeg() -> None:
        missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
        if missing:
            raise OSError(f"Required executable(s) not found on PATH: {', '.join(missing)}")

    @staticmethod
    def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            raise OSError(detail or "FFmpeg command failed") from exc

    def _probe_audio(self) -> _AudioInfo:
        result = self._run([
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate,channels,channel_layout:format=duration",
            "-of", "json",
            self.input_file_path,
        ])
        try:
            payload = json.loads(result.stdout)
            stream = payload["streams"][0]
            duration_s = float(payload["format"]["duration"])
            sample_rate = int(stream["sample_rate"])
            channels = int(stream["channels"])
            channel_layout = stream.get("channel_layout") or None
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise OSError("Could not read audio stream metadata") from exc

        if not math.isfinite(duration_s) or duration_s < 0:
            raise OSError("Audio duration is invalid")
        return _AudioInfo(
            duration_ms=max(0, int(round(duration_s * 1000))),
            sample_rate=sample_rate,
            channels=channels,
            channel_layout=channel_layout,
        )

    def detect_silence_ranges(self, min_silence_len: int = 700, threshold: float = -38.0) -> Timeline:
        """Detect continuous silence using FFmpeg's RMS-based silencedetect filter."""
        if min_silence_len <= 0:
            raise ValueError("min_silence_len must be greater than zero")
        if not math.isfinite(float(threshold)):
            raise ValueError("threshold must be a finite dBFS value")

        duration_s = min_silence_len / 1000.0
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-i", self.input_file_path,
                "-af", f"silencedetect=n={float(threshold):g}dB:d={duration_s:.6f}",
                "-f", "null",
                "-",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "FFmpeg silence detection failed").strip()
            raise OSError(detail)

        ranges: Timeline = []
        current_start_ms: int | None = None
        start_re = re.compile(r"silence_start:\s*([0-9.]+)")
        end_re = re.compile(r"silence_end:\s*([0-9.]+)")

        for line in result.stderr.splitlines():
            start_match = start_re.search(line)
            if start_match:
                current_start_ms = max(0, int(round(float(start_match.group(1)) * 1000)))
                continue

            end_match = end_re.search(line)
            if end_match and current_start_ms is not None:
                end_ms = min(self._info.duration_ms, int(round(float(end_match.group(1)) * 1000)))
                if end_ms > current_start_ms:
                    ranges.append((current_start_ms, end_ms))
                current_start_ms = None

        if current_start_ms is not None and current_start_ms < self._info.duration_ms:
            ranges.append((current_start_ms, self._info.duration_ms))

        return _normalize_ranges(ranges, self._info.duration_ms)

    def split_audio_by_silence(self, min_silence_len: int, threshold: float) -> Timeline:
        """Backward-compatible detection API returning non-silent source ranges."""
        silent = self.detect_silence_ranges(min_silence_len=min_silence_len, threshold=threshold)
        return complement_ranges(self._info.duration_ms, silent)

    def is_fully_silent(self, min_silence_len: int = 700, threshold: float = -38.0) -> bool:
        return not self.split_audio_by_silence(min_silence_len, threshold)

    def save_timeline_to_text(self, timeline_data: Iterable[Sequence[int]], output_path: str) -> None:
        timeline = [(int(start), int(end)) for start, end in timeline_data]
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(repr(timeline))
        print(f"Saved timeline data to {output_path}")

    def _render_ranges(self, ranges: Iterable[Sequence[int]], output_path: Path, output_format: str) -> None:
        normalized = _normalize_ranges(ranges, self._info.duration_ms)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not normalized:
            layout = self._info.channel_layout
            if not layout:
                layout = "mono" if self._info.channels == 1 else "stereo"
            command = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi",
                "-i", f"anullsrc=r={self._info.sample_rate}:cl={layout}",
                "-t", "0.001",
            ]
            if output_format == "wav":
                command += ["-c:a", "pcm_f32le"]
            command.append(str(output_path))
            self._run(command)
            return

        filters: list[str] = []
        labels: list[str] = []
        for index, (start, end) in enumerate(normalized):
            label = f"a{index}"
            filters.append(
                f"[0:a:0]atrim=start={start / 1000:.6f}:end={end / 1000:.6f},"
                f"asetpts=PTS-STARTPTS[{label}]"
            )
            labels.append(f"[{label}]")

        if len(normalized) == 1:
            filter_complex = filters[0]
            output_label = labels[0]
        else:
            output_label = "[outa]"
            filter_complex = ";".join(filters) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1{output_label}"

        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", self.input_file_path,
            "-filter_complex", filter_complex,
            "-map", output_label,
        ]
        if output_format == "wav":
            command += ["-c:a", "pcm_f32le"]
        command.append(str(output_path))
        self._run(command)

    def process_audio(
        self,
        min_silence_len: int = 700,
        threshold: float = -38.0,
        target_silence_len: int = 150,
        output_folder: str | os.PathLike[str] = "output",
        output_format: str = "wav",
        output_stem: str | None = None,
    ) -> ProcessingResult:
        if min_silence_len <= 0:
            raise ValueError("min_silence_len must be greater than zero")
        if target_silence_len < 0:
            raise ValueError("target_silence_len must be zero or greater")
        if not math.isfinite(float(threshold)):
            raise ValueError("threshold must be a finite dBFS value")

        normalized_format = output_format.strip().lower()
        if not re.fullmatch(r"[a-z0-9]+", normalized_format):
            raise ValueError("output_format must be a simple format name such as 'mp3' or 'wav'")

        print("Processing audio...")
        detected_silence_ranges = self.detect_silence_ranges(min_silence_len, threshold)
        removed_ranges = build_removal_ranges(
            self._info.duration_ms,
            detected_silence_ranges,
            target_silence_len,
        )
        retained_ranges = complement_ranges(self._info.duration_ms, removed_ranges)

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

        self._render_ranges(removed_ranges, silent_audio_path, normalized_format)
        self._render_ranges(retained_ranges, non_silent_audio_path, normalized_format)
        self.save_timeline_to_text(removed_ranges, str(silent_timeline_path))
        self.save_timeline_to_text(retained_ranges, str(non_silent_timeline_path))

        print("Audio processing completed.")
        return ProcessingResult(
            silent_audio_path=str(silent_audio_path),
            non_silent_audio_path=str(non_silent_audio_path),
            silent_timeline_path=str(silent_timeline_path),
            non_silent_timeline_path=str(non_silent_timeline_path),
            silent_ranges=tuple(removed_ranges),
            non_silent_ranges=tuple(retained_ranges),
            detected_silence_ranges=tuple(detected_silence_ranges),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Remove long silence without processing retained audio")
    parser.add_argument("input_file", help="Input audio file path")
    parser.add_argument("--output_folder", default="output", help="Output folder path")
    parser.add_argument("--min_silence_len", type=int, default=700, help="Minimum continuous silence in milliseconds")
    parser.add_argument("--threshold", type=float, default=-38.0, help="Silence threshold in dBFS")
    parser.add_argument(
        "--target_silence_len",
        type=int,
        default=150,
        help="Silence to keep for each internal pause in milliseconds",
    )
    parser.add_argument("--output_format", default="wav", help="Output audio format (default: wav)")
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
