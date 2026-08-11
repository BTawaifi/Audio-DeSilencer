import ast
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pydub import AudioSegment
from pydub.generators import Sine

from audio_desilencer.audio_processor import (
    AudioProcessor,
    ProcessingResult,
    _normalize_ranges,
    complement_ranges,
    main,
)
import audio_desilencer.audio_processor as module


def processor_with_audio(audio: AudioSegment, input_path: str = "recording.wav") -> AudioProcessor:
    processor = AudioProcessor.__new__(AudioProcessor)
    processor.input_file_path = input_path
    processor.audio = audio
    return processor


class RangeTests(unittest.TestCase):
    def test_normalize_sorts_clamps_and_merges(self):
        self.assertEqual(
            _normalize_ranges([(300, 500), (-20, 100), (90, 200), (800, 1200), (500, 500)], 1000),
            [(0, 200), (300, 500), (800, 1000)],
        )

    def test_normalize_merges_touching_ranges(self):
        self.assertEqual(_normalize_ranges([(0, 100), (100, 200), (150, 250)], 300), [(0, 250)])

    def test_normalize_rejects_invalid_shape(self):
        with self.assertRaises(ValueError):
            _normalize_ranges([(1, 2, 3)], 10)

    def test_complement_empty_ranges_is_whole_file(self):
        self.assertEqual(complement_ranges(1000, []), [(0, 1000)])

    def test_complement_full_range_is_empty(self):
        self.assertEqual(complement_ranges(1000, [(0, 1000)]), [])

    def test_complement_includes_leading_internal_and_trailing_gaps(self):
        self.assertEqual(
            complement_ranges(1000, [(100, 200), (400, 700)]),
            [(0, 100), (200, 400), (700, 1000)],
        )

    def test_complement_zero_duration_is_empty(self):
        self.assertEqual(complement_ranges(0, []), [])


class AudioProcessorTests(unittest.TestCase):
    @patch.object(module.AudioSegment, "from_file")
    def test_constructor_uses_pydub_format_detection(self, from_file):
        from_file.return_value = AudioSegment.silent(duration=10)
        AudioProcessor("example.m4a")
        from_file.assert_called_once_with("example.m4a")

    def test_real_silence_detection_finds_tone_between_silence(self):
        tone = Sine(440).to_audio_segment(duration=300).apply_gain(-3)
        audio = AudioSegment.silent(duration=200) + tone + AudioSegment.silent(duration=200)
        processor = processor_with_audio(audio)
        ranges = processor.split_audio_by_silence(min_silence_len=100, threshold=-30)
        self.assertEqual(len(ranges), 1)
        start, end = ranges[0]
        self.assertLessEqual(abs(start - 200), 10)
        self.assertLessEqual(abs(end - 500), 10)

    def test_is_fully_silent_true(self):
        processor = processor_with_audio(AudioSegment.silent(duration=300))
        self.assertTrue(processor.is_fully_silent(min_silence_len=50, threshold=-30))

    def test_is_fully_silent_false(self):
        processor = processor_with_audio(Sine(440).to_audio_segment(duration=300).apply_gain(-3))
        self.assertFalse(processor.is_fully_silent(min_silence_len=50, threshold=-30))

    def test_join_ranges_preserves_requested_total_duration(self):
        processor = processor_with_audio(AudioSegment.silent(duration=1000, frame_rate=8000))
        joined = processor._join_ranges([(100, 200), (400, 650)])
        self.assertEqual(len(joined), 350)

    def test_join_ranges_empty_returns_empty_audio(self):
        processor = processor_with_audio(AudioSegment.silent(duration=100))
        self.assertEqual(len(processor._join_ranges([])), 0)

    def test_process_includes_trailing_silence(self):
        processor = processor_with_audio(AudioSegment.silent(duration=1000), "meeting.wav")
        with patch.object(processor, "split_audio_by_silence", return_value=[(200, 700)]), \
             patch.object(processor, "save_audio") as save_audio, \
             patch.object(processor, "save_timeline_to_text") as save_timeline, \
             tempfile.TemporaryDirectory() as tmp:
            result = processor.process_audio(output_folder=tmp, output_format="wav")

        self.assertEqual(result.non_silent_ranges, ((200, 700),))
        self.assertEqual(result.silent_ranges, ((0, 200), (700, 1000)))
        self.assertEqual(len(save_audio.call_args_list[0].args[0]), 500)
        self.assertEqual(len(save_audio.call_args_list[1].args[0]), 500)
        self.assertEqual(save_timeline.call_args_list[0].args[0], [(0, 200), (700, 1000)])

    def test_process_fully_silent_preserves_entire_audio_as_silent(self):
        processor = processor_with_audio(AudioSegment.silent(duration=1000), "silence.wav")
        with patch.object(processor, "split_audio_by_silence", return_value=[]), \
             patch.object(processor, "save_audio") as save_audio, \
             patch.object(processor, "save_timeline_to_text"), \
             tempfile.TemporaryDirectory() as tmp:
            result = processor.process_audio(output_folder=tmp, output_format="wav")

        self.assertEqual(result.silent_ranges, ((0, 1000),))
        self.assertEqual(result.non_silent_ranges, ())
        self.assertEqual(len(save_audio.call_args_list[0].args[0]), 1000)
        self.assertEqual(len(save_audio.call_args_list[1].args[0]), 0)

    def test_process_fully_non_silent_has_no_silent_output(self):
        processor = processor_with_audio(AudioSegment.silent(duration=1000), "speech.wav")
        with patch.object(processor, "split_audio_by_silence", return_value=[(0, 1000)]), \
             patch.object(processor, "save_audio") as save_audio, \
             patch.object(processor, "save_timeline_to_text"), \
             tempfile.TemporaryDirectory() as tmp:
            result = processor.process_audio(output_folder=tmp, output_format="wav")

        self.assertEqual(result.silent_ranges, ())
        self.assertEqual(result.non_silent_ranges, ((0, 1000),))
        self.assertEqual(len(save_audio.call_args_list[0].args[0]), 0)
        self.assertEqual(len(save_audio.call_args_list[1].args[0]), 1000)

    def test_process_uses_input_stem_and_requested_format(self):
        processor = processor_with_audio(AudioSegment.silent(duration=50), "/tmp/client-call.m4a")
        with patch.object(processor, "split_audio_by_silence", return_value=[]), \
             patch.object(processor, "save_audio") as save_audio, \
             patch.object(processor, "save_timeline_to_text"), \
             tempfile.TemporaryDirectory() as tmp:
            result = processor.process_audio(output_folder=tmp, output_format="WAV")

        self.assertTrue(result.silent_audio_path.endswith("client-call_silent.wav"))
        self.assertTrue(result.non_silent_audio_path.endswith("client-call_non_silent.wav"))
        self.assertEqual(save_audio.call_args_list[0].args[2], "wav")

    def test_process_custom_stem_cannot_escape_output_directory(self):
        processor = processor_with_audio(AudioSegment.silent(duration=50), "input.wav")
        with patch.object(processor, "split_audio_by_silence", return_value=[]), \
             patch.object(processor, "save_audio"), \
             patch.object(processor, "save_timeline_to_text"), \
             tempfile.TemporaryDirectory() as tmp:
            result = processor.process_audio(output_folder=tmp, output_format="wav", output_stem="../../safe")
        self.assertEqual(Path(result.silent_audio_path).parent, Path(tmp))
        self.assertEqual(Path(result.silent_audio_path).name, "safe_silent.wav")

    def test_process_rejects_non_positive_min_silence(self):
        processor = processor_with_audio(AudioSegment.silent(duration=50))
        with self.assertRaises(ValueError):
            processor.process_audio(min_silence_len=0)

    def test_process_rejects_unsafe_output_format(self):
        processor = processor_with_audio(AudioSegment.silent(duration=50))
        with self.assertRaises(ValueError):
            processor.process_audio(output_format="../mp3")

    def test_process_returns_structured_result(self):
        processor = processor_with_audio(AudioSegment.silent(duration=100), "clip.wav")
        with patch.object(processor, "split_audio_by_silence", return_value=[(20, 80)]), \
             patch.object(processor, "save_audio"), \
             patch.object(processor, "save_timeline_to_text"), \
             tempfile.TemporaryDirectory() as tmp:
            result = processor.process_audio(output_folder=tmp, output_format="wav")
        self.assertIsInstance(result, ProcessingResult)
        self.assertEqual(result.silent_ranges, ((0, 20), (80, 100)))

    def test_save_timeline_writes_valid_python_literal_without_trailing_comma(self):
        processor = processor_with_audio(AudioSegment.empty())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "timeline.txt"
            processor.save_timeline_to_text([(0, 100), (200, 300)], str(path))
            content = path.read_text(encoding="utf-8")
        self.assertEqual(ast.literal_eval(content), [(0, 100), (200, 300)])
        self.assertNotIn(", ]", content)

    def test_save_audio_uses_requested_format(self):
        processor = processor_with_audio(AudioSegment.empty())
        audio = MagicMock()
        processor.save_audio(audio, "out.wav", "wav")
        audio.export.assert_called_once_with("out.wav", format="wav")


class CliTests(unittest.TestCase):
    @patch.object(module, "AudioProcessor")
    def test_main_passes_all_options_and_returns_zero(self, processor_cls):
        processor = processor_cls.return_value
        code = main([
            "input.wav",
            "--output_folder", "out",
            "--min_silence_len", "250",
            "--threshold", "-42",
            "--output_format", "wav",
            "--output_stem", "cleaned",
        ])
        self.assertEqual(code, 0)
        processor_cls.assert_called_once_with("input.wav")
        processor.process_audio.assert_called_once_with(
            min_silence_len=250,
            threshold=-42,
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
