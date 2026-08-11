from __future__ import annotations

import argparse
import array
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


Timeline = list[tuple[int, int]]
Threshold = float | str

DEFAULT_THRESHOLD_DBFS = -38.0
DEFAULT_MIN_SILENCE_MS = 700
DEFAULT_TARGET_SILENCE_MS = 150
DEFAULT_AUTO_HYSTERESIS_DB = 3.0
ANALYSIS_WINDOW_MS = 20


@dataclass(frozen=True)
class ProcessingResult:
    silent_audio_path: str
    non_silent_audio_path: str
    silent_timeline_path: str
    non_silent_timeline_path: str
    silent_ranges: tuple[tuple[int, int], ...]
    non_silent_ranges: tuple[tuple[int, int], ...]
    detected_silence_ranges: tuple[tuple[int, int], ...] = ()
    resolved_threshold_dbfs: float | None = None
    detector: str = "ffmpeg"


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
    """Return only the middle portions of confirmed silence that are safe to delete."""
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


def estimate_adaptive_threshold(
    frame_levels_dbfs: Sequence[float],
    *,
    percentile: float = 0.35,
    margin_db: float = 8.0,
    minimum_dbfs: float = -55.0,
    maximum_dbfs: float = DEFAULT_THRESHOLD_DBFS,
) -> float:
    """Estimate a conservative silence threshold from short-window peak levels.

    This is deterministic signal analysis, not a learned model. The lower-level
    portion of the recording is treated as a noise-floor estimate and a small
    margin is added. Auto mode is deliberately conservative: by default it will
    never choose a threshold more aggressive than the normal -38 dBFS default.
    """
    if not frame_levels_dbfs:
        return DEFAULT_THRESHOLD_DBFS
    if not 0.0 <= percentile <= 1.0:
        raise ValueError("percentile must be between zero and one")
    if minimum_dbfs > maximum_dbfs:
        raise ValueError("minimum_dbfs cannot exceed maximum_dbfs")

    levels = sorted(
        max(-120.0, min(0.0, float(level)))
        for level in frame_levels_dbfs
        if math.isfinite(float(level))
    )
    if not levels:
        return DEFAULT_THRESHOLD_DBFS

    index = int((len(levels) - 1) * percentile)
    noise_floor = levels[index]
    threshold = noise_floor + float(margin_db)
    return max(float(minimum_dbfs), min(float(maximum_dbfs), threshold))


def detect_silence_from_levels(
    frames: Sequence[tuple[int, int, float]],
    *,
    min_silence_len: int,
    enter_threshold_dbfs: float,
    hysteresis_db: float = 0.0,
    total_duration_ms: int | None = None,
) -> Timeline:
    """Detect continuous silence from short-window levels with exit hysteresis."""
    if min_silence_len <= 0:
        raise ValueError("min_silence_len must be greater than zero")
    if hysteresis_db < 0 or not math.isfinite(float(hysteresis_db)):
        raise ValueError("hysteresis_db must be a finite value >= 0")

    enter = float(enter_threshold_dbfs)
    if not math.isfinite(enter):
        raise ValueError("enter_threshold_dbfs must be finite")
    exit_threshold = enter + float(hysteresis_db)

    ranges: Timeline = []
    candidate_start: int | None = None
    silence_start: int | None = None
    in_silence = False
    last_end = 0

    for raw_start, raw_end, raw_level in frames:
        start = max(0, int(raw_start))
        end = max(start, int(raw_end))
        level = float(raw_level)
        last_end = max(last_end, end)

        if not in_silence:
            if level <= enter:
                if candidate_start is None:
                    candidate_start = start
                if end - candidate_start >= min_silence_len:
                    in_silence = True
                    silence_start = candidate_start
            else:
                candidate_start = None
            continue

        if level > exit_threshold:
            if silence_start is not None and start > silence_start:
                ranges.append((silence_start, start))
            in_silence = False
            silence_start = None
            candidate_start = None

    if in_silence and silence_start is not None:
        final_end = int(total_duration_ms) if total_duration_ms is not None else last_end
        if final_end > silence_start:
            ranges.append((silence_start, final_end))

    total = int(total_duration_ms) if total_duration_ms is not None else last_end
    return _normalize_ranges(ranges, total)


def _parse_threshold(value: str) -> Threshold:
    if value.strip().lower() == "auto":
        return "auto"
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("threshold must be a dBFS number or 'auto'") from exc
    if not math.isfinite(result):
        raise argparse.ArgumentTypeError("threshold must be finite")
    return result


class AudioProcessor:
    """Non-destructive silence editor backed directly by FFmpeg.

    Retained audio is never normalized, limited, EQ'd, compressed, de-essed,
    crossfaded, or otherwise altered. Detection may analyze decoded samples, but
    rendering only trims time ranges and concatenates retained source spans.
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

    @staticmethod
    def _coerce_threshold(threshold: Threshold) -> Threshold:
        if isinstance(threshold, str):
            if threshold.strip().lower() == "auto":
                return "auto"
            try:
                threshold = float(threshold)
            except ValueError as exc:
                raise ValueError("threshold must be a finite dBFS number or 'auto'") from exc
        value = float(threshold)
        if not math.isfinite(value):
            raise ValueError("threshold must be a finite dBFS number or 'auto'")
        return value

    def _measure_frame_levels(self, window_ms: int = ANALYSIS_WINDOW_MS) -> list[tuple[int, int, float]]:
        """Measure peak level in short windows.

        Any over-threshold sample on any channel makes the window active. This
        conservative peak policy protects short consonants/transients and means a
        frame counts as quiet only when every channel is quiet.
        """
        if window_ms <= 0:
            raise ValueError("window_ms must be greater than zero")

        samples_per_window = max(1, int(round(self._info.sample_rate * window_ms / 1000.0)))
        bytes_per_sample = 4
        frame_bytes = samples_per_window * self._info.channels * bytes_per_sample

        process = subprocess.Popen(
            [
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-i", self.input_file_path,
                "-map", "0:a:0",
                "-f", "f32le",
                "-acodec", "pcm_f32le",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stdout is not None
        assert process.stderr is not None

        frames: list[tuple[int, int, float]] = []
        total_samples_per_channel = 0

        try:
            while True:
                buffer = bytearray()
                while len(buffer) < frame_bytes:
                    chunk = process.stdout.read(frame_bytes - len(buffer))
                    if not chunk:
                        break
                    buffer.extend(chunk)

                if not buffer:
                    break

                complete_sample_bytes = (len(buffer) // (bytes_per_sample * self._info.channels)) * (
                    bytes_per_sample * self._info.channels
                )
                if complete_sample_bytes == 0:
                    break

                values = array.array("f")
                values.frombytes(buffer[:complete_sample_bytes])
                if sys.byteorder != "little":
                    values.byteswap()

                samples_this_channel = len(values) // self._info.channels
                max_peak = max((abs(float(value)) for value in values), default=0.0)
                level_dbfs = 20.0 * math.log10(max_peak) if max_peak > 0.0 else -120.0

                start_ms = int(round(total_samples_per_channel * 1000.0 / self._info.sample_rate))
                total_samples_per_channel += samples_this_channel
                end_ms = min(
                    self._info.duration_ms,
                    int(round(total_samples_per_channel * 1000.0 / self._info.sample_rate)),
                )
                frames.append((start_ms, max(start_ms, end_ms), level_dbfs))

                if len(buffer) < frame_bytes:
                    break

            stderr = process.stderr.read().decode("utf-8", errors="replace")
            return_code = process.wait()
            if return_code != 0:
                raise OSError(stderr.strip() or "FFmpeg level analysis failed")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()

        return frames

    def _detect_silence_ffmpeg(self, min_silence_len: int, threshold: float) -> Timeline:
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

    def _detect_silence(
        self,
        min_silence_len: int,
        threshold: Threshold,
        hysteresis_db: float | None,
    ) -> tuple[Timeline, float, str]:
        threshold = self._coerce_threshold(threshold)
        if min_silence_len <= 0:
            raise ValueError("min_silence_len must be greater than zero")
        if hysteresis_db is not None and (
            not math.isfinite(float(hysteresis_db)) or float(hysteresis_db) < 0
        ):
            raise ValueError("hysteresis_db must be a finite value >= 0")

        if threshold != "auto" and (hysteresis_db is None or float(hysteresis_db) == 0.0):
            resolved = float(threshold)
            return self._detect_silence_ffmpeg(min_silence_len, resolved), resolved, "ffmpeg"

        frames = self._measure_frame_levels()
        levels = [level for _, _, level in frames]
        if threshold == "auto":
            resolved = estimate_adaptive_threshold(levels)
            resolved_hysteresis = (
                DEFAULT_AUTO_HYSTERESIS_DB if hysteresis_db is None else float(hysteresis_db)
            )
            detector = "adaptive"
        else:
            resolved = float(threshold)
            resolved_hysteresis = 0.0 if hysteresis_db is None else float(hysteresis_db)
            detector = "hysteresis"

        ranges = detect_silence_from_levels(
            frames,
            min_silence_len=min_silence_len,
            enter_threshold_dbfs=resolved,
            hysteresis_db=resolved_hysteresis,
            total_duration_ms=self._info.duration_ms,
        )
        return ranges, resolved, detector

    def detect_silence_ranges(
        self,
        min_silence_len: int = DEFAULT_MIN_SILENCE_MS,
        threshold: Threshold = DEFAULT_THRESHOLD_DBFS,
        hysteresis_db: float | None = None,
    ) -> Timeline:
        """Detect continuous silence.

        Numeric thresholds with no hysteresis preserve the established FFmpeg
        silencedetect behavior. ``threshold="auto"`` enables deterministic
        noise-floor estimation and 3 dB exit hysteresis by default.
        """
        ranges, _, _ = self._detect_silence(min_silence_len, threshold, hysteresis_db)
        return ranges

    def split_audio_by_silence(
        self,
        min_silence_len: int,
        threshold: Threshold,
        hysteresis_db: float | None = None,
    ) -> Timeline:
        """Backward-compatible detection API returning non-silent source ranges."""
        silent = self.detect_silence_ranges(
            min_silence_len=min_silence_len,
            threshold=threshold,
            hysteresis_db=hysteresis_db,
        )
        return complement_ranges(self._info.duration_ms, silent)

    def is_fully_silent(
        self,
        min_silence_len: int = DEFAULT_MIN_SILENCE_MS,
        threshold: Threshold = DEFAULT_THRESHOLD_DBFS,
        hysteresis_db: float | None = None,
    ) -> bool:
        return not self.split_audio_by_silence(min_silence_len, threshold, hysteresis_db)

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
            filter_complex = ";".join(filters) + ";" + "".join(labels) + (
                f"concat=n={len(labels)}:v=0:a=1{output_label}"
            )

        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", self.input_file_path,
        ]

        script_path: Path | None = None
        try:
            if len(filter_complex) > 8000:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    suffix=".ffscript",
                    delete=False,
                ) as script:
                    script.write(filter_complex)
                    script_path = Path(script.name)
                command += ["-filter_complex_script", str(script_path)]
            else:
                command += ["-filter_complex", filter_complex]

            command += ["-map", output_label]
            if output_format == "wav":
                command += ["-c:a", "pcm_f32le"]
            command.append(str(output_path))
            self._run(command)
        finally:
            if script_path is not None:
                script_path.unlink(missing_ok=True)

    def process_audio(
        self,
        min_silence_len: int = DEFAULT_MIN_SILENCE_MS,
        threshold: Threshold = DEFAULT_THRESHOLD_DBFS,
        target_silence_len: int = DEFAULT_TARGET_SILENCE_MS,
        hysteresis_db: float | None = None,
        output_folder: str | os.PathLike[str] = "output",
        output_format: str = "wav",
        output_stem: str | None = None,
    ) -> ProcessingResult:
        if min_silence_len <= 0:
            raise ValueError("min_silence_len must be greater than zero")
        if target_silence_len < 0:
            raise ValueError("target_silence_len must be zero or greater")
        threshold = self._coerce_threshold(threshold)
        if hysteresis_db is not None and (
            not math.isfinite(float(hysteresis_db)) or float(hysteresis_db) < 0
        ):
            raise ValueError("hysteresis_db must be a finite value >= 0")

        normalized_format = output_format.strip().lower()
        if not re.fullmatch(r"[a-z0-9]+", normalized_format):
            raise ValueError("output_format must be a simple format name such as 'mp3' or 'wav'")

        print("Processing audio...")
        detected_silence_ranges, resolved_threshold, detector = self._detect_silence(
            min_silence_len,
            threshold,
            hysteresis_db,
        )
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

        print(
            f"Audio processing completed. detector={detector}, "
            f"threshold={resolved_threshold:.2f} dBFS"
        )
        return ProcessingResult(
            silent_audio_path=str(silent_audio_path),
            non_silent_audio_path=str(non_silent_audio_path),
            silent_timeline_path=str(silent_timeline_path),
            non_silent_timeline_path=str(non_silent_timeline_path),
            silent_ranges=tuple(removed_ranges),
            non_silent_ranges=tuple(retained_ranges),
            detected_silence_ranges=tuple(detected_silence_ranges),
            resolved_threshold_dbfs=resolved_threshold,
            detector=detector,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Remove long silence without processing retained audio")
    parser.add_argument("input_file", help="Input audio file path")
    parser.add_argument("--output_folder", default="output", help="Output folder path")
    parser.add_argument(
        "--min_silence_len",
        type=int,
        default=DEFAULT_MIN_SILENCE_MS,
        help="Minimum continuous silence in milliseconds",
    )
    parser.add_argument(
        "--threshold",
        type=_parse_threshold,
        default=DEFAULT_THRESHOLD_DBFS,
        help="Silence threshold in dBFS, or 'auto' for deterministic noise-floor estimation",
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
