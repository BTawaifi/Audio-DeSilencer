import ast
import io
import math
import struct
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from audio_desilencer.audio_processor import (
    AudioProcessor,
    ProcessingResult,
    _normalize_ranges,
    build_removal_ranges,
    complement_ranges,
    main,
)
import audio_desilencer.audio_processor as module


def write_test_wav(path: Path, sections, sample_rate: int = 8000) -> None:
    """Write mono 16-bit PCM. sections is [(duration_ms, amplitude_0_to_1, hz)]."""
    samples = []
    for duration_ms, amplitude, frequency in sections:
        count = int(sample_rate * duration_ms / 1000)
        for index in range(count):
            if amplitude == 0:
                value = 0
            else:
                value = int(32767 * amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
            samples.append(value)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def decode_f32(path: Path) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "f32le", "-acodec", "pcm_f32le", "-"],
        check=True,
        capture_output=True,
    ).stdout


class RangeTests(unittest.TestCase):
    def test_normalize_sorts_clamps_and_merges(self):
        self.assertEqual(
            _normalize_ranges([(300, 500), (-20, 100), (90, 200), (800, 1200), (500, 500)], 1000),
            [(0, 200), (300, 500), (800, 1000)],
        )

    def test_complement_includes_leading_internal_and_trailing_gaps(self):
        self.assertEqual(
            complement_ranges(1000, [(100, 200), (400, 700)]),
            [(0, 100), (200, 400), (700, 1000)],
        )

    def test_build_removal_shortens_only_middle_of_internal_silence(self):
        self.assertEqual(build_removal_ranges(2000, [(500, 1500)], 200), [(600, 1400)])

    def test_build_removal_keeps_half_target_next_to_leading_and_trailing_speech(self):
        self.assertEqual(
            build_removal_ranges(2000, [(0, 500), (1500, 2000)], 200),
            [(0, 400), (1600, 2000)],
        )

    def test_build_removal_fully_silent_file_removes_everything(self):
        self.assertEqual(build_removal_ranges(1000, [(0, 1000)], 150), [(0, 1000)])

    def test_build_removal_rejects_negative_target(self):
        with self.assertRaises(ValueError):
            build_removal_ranges(1000, [(0, 500)], -1)


class AudioProcessorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def test_constructor_rejects_missing_input(self):
        with self.assertRaises(OSError):
            AudioProcessor(self.root / "missing.wav")

    def test_real_silence_detection_finds_tone_between_silence(self):
        source = self.root / "tone.wav"
        write_test_wav(source, [(200, 0, 440), (300, 0.8, 440), (200, 0, 440)])
        processor = AudioProcessor(source)
        silent = processor.detect_silence_ranges(min_silence_len=100, threshold=-30)
        self.assertEqual(len(silent), 2)
        self.assertLessEqual(abs(silent[0][0] - 0), 10)
        self.assertLessEqual(abs(silent[0][1] - 200), 10)
        self.assertLessEqual(abs(silent[1][0] - 500), 10)
        self.assertLessEqual(abs(silent[1][1] - 700), 10)

        nonsilent = processor.split_audio_by_silence(min_silence_len=100, threshold=-30)
        self.assertEqual(len(nonsilent), 1)
        self.assertLessEqual(abs(nonsilent[0][0] - 200), 10)
        self.assertLessEqual(abs(nonsilent[0][1] - 500), 10)

    def test_is_fully_silent_and_non_silent(self):
        silent_path = self.root / "silent.wav"
        tone_path = self.root / "tone.wav"
        write_test_wav(silent_path, [(500, 0, 440)])
        write_test_wav(tone_path, [(500, 0.8, 440)])
        self.assertTrue(AudioProcessor(silent_path).is_fully_silent(min_silence_len=100, threshold=-30))
        self.assertFalse(AudioProcessor(tone_path).is_fully_silent(min_silence_len=100, threshold=-30))

    def test_process_shortens_pauses_and_reports_removed_and_retained_ranges(self):
        source = self.root / "meeting.wav"
        write_test_wav(source, [
            (200, 0, 440),
            (300, 0.8, 440),
            (1000, 0, 440),
            (300, 0.8, 440),
            (200, 0, 440),
        ])
        processor = AudioProcessor(source)
        result = processor.process_audio(
            min_silence_len=100,
            threshold=-30,
            target_silence_len=100,
            output_folder=self.root / "out",
            output_format="wav",
        )

        self.assertIsInstance(result, ProcessingResult)
        self.assertEqual(result.silent_ranges, ((0, 150), (550, 1450), (1850, 2000)))
        self.assertEqual(result.non_silent_ranges, ((150, 550), (1450, 1850)))
        self.assertEqual(result.detected_silence_ranges, ((0, 200), (500, 1500), (1800, 2000)))
        self.assertTrue(Path(result.non_silent_audio_path).is_file())
        self.assertTrue(Path(result.silent_audio_path).is_file())

    def test_retained_pcm_is_unchanged(self):
        source = self.root / "signal.wav"
        write_test_wav(source, [
            (200, 0, 440),
            (300, 0.72, 323),
            (1000, 0, 440),
            (300, 0.51, 517),
            (200, 0, 440),
        ])
        processor = AudioProcessor(source)
        result = processor.process_audio(
            min_silence_len=100,
            threshold=-30,
            target_silence_len=100,
            output_folder=self.root / "out2",
            output_format="wav",
        )

        source_f32 = decode_f32(source)
        output_f32 = decode_f32(Path(result.non_silent_audio_path))
        bytes_per_frame = 4
        frames_per_ms = 8

        expected = b"".join(
            source_f32[start * frames_per_ms * bytes_per_frame:end * frames_per_ms * bytes_per_frame]
            for start, end in result.non_silent_ranges
        )
        self.assertEqual(output_f32, expected)

    def test_float_wav_render_does_not_integer_clip_over_range_samples(self):
        raw = self.root / "over.f32"
        source = self.root / "over.wav"
        values = [0.0, 0.5, 1.25, -1.4, 0.25] * 1600
        raw.write_bytes(struct.pack(f"<{len(values)}f", *values))
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "f32le", "-ar", "8000", "-ac", "1", "-i", str(raw),
            "-c:a", "pcm_f32le", str(source),
        ], check=True)

        processor = AudioProcessor(source)
        out = self.root / "rendered.wav"
        processor._render_ranges([(0, processor._info.duration_ms)], out, "wav")
        decoded = struct.unpack(f"<{len(values)}f", decode_f32(out))
        self.assertGreater(max(decoded), 1.0)
        self.assertLess(min(decoded), -1.0)
        for actual, expected in zip(decoded[:5], values[:5]):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_process_custom_stem_cannot_escape_output_directory(self):
        source = self.root / "input.wav"
        write_test_wav(source, [(300, 0.8, 440)])
        processor = AudioProcessor(source)
        result = processor.process_audio(
            output_folder=self.root / "safe",
            output_format="wav",
            output_stem="../../cleaned",
        )
        self.assertEqual(Path(result.non_silent_audio_path).parent, self.root / "safe")
        self.assertEqual(Path(result.non_silent_audio_path).name, "cleaned_non_silent.wav")

    def test_process_rejects_invalid_options(self):
        source = self.root / "input.wav"
        write_test_wav(source, [(300, 0.8, 440)])
        processor = AudioProcessor(source)
        with self.assertRaises(ValueError):
            processor.process_audio(min_silence_len=0)
        with self.assertRaises(ValueError):
            processor.process_audio(target_silence_len=-1)
        with self.assertRaises(ValueError):
            processor.process_audio(output_format="../mp3")

    def test_save_timeline_writes_valid_python_literal(self):
        source = self.root / "input.wav"
        write_test_wav(source, [(100, 0.8, 440)])
        processor = AudioProcessor(source)
        path = self.root / "timeline.txt"
        processor.save_timeline_to_text([(0, 100), (200, 300)], str(path))
        self.assertEqual(ast.literal_eval(path.read_text(encoding="utf-8")), [(0, 100), (200, 300)])


class CliTests(unittest.TestCase):
    @patch.object(module, "AudioProcessor")
    def test_main_passes_all_options_and_returns_zero(self, processor_cls):
        processor = processor_cls.return_value
        code = main([
            "input.wav",
            "--output_folder", "out",
            "--min_silence_len", "700",
            "--threshold", "-38",
            "--target_silence_len", "120",
            "--output_format", "wav",
            "--output_stem", "cleaned",
        ])
        self.assertEqual(code, 0)
        processor_cls.assert_called_once_with("input.wav")
        processor.process_audio.assert_called_once_with(
            min_silence_len=700,
            threshold=-38.0,
            target_silence_len=120,
            output_folder="out",
            output_format="wav",
            output_stem="cleaned",
        )

    @patch.object(module, "AudioProcessor", side_effect=OSError("missing input"))
    def test_main_returns_nonzero_when_loading_fails(self, _processor_cls):
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            code = main(["missing.wav"])
        self.assertEqual(code, 1)
        self.assertIn("missing input", stderr.getvalue())

    @patch.object(module, "AudioProcessor")
    def test_main_returns_nonzero_when_processing_fails(self, processor_cls):
        processor_cls.return_value.process_audio.side_effect = ValueError("bad threshold")
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            code = main(["input.wav"])
        self.assertEqual(code, 1)
        self.assertIn("bad threshold", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
