import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys

# Mock pydub and pydub.silence before importing AudioProcessor
mock_pydub = MagicMock()
mock_pydub_silence = MagicMock()
sys.modules['pydub'] = mock_pydub
sys.modules['pydub.silence'] = mock_pydub_silence

from audio_desilencer.audio_processor import AudioProcessor

class TestAudioProcessor(unittest.TestCase):

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    @patch('audio_desilencer.audio_processor.detect_nonsilent')
    def test_is_fully_silent_when_audio_is_silent(self, mock_detect_nonsilent, mock_from_file):
        # Configure mocks
        mock_audio_segment = MagicMock()
        mock_from_file.return_value = mock_audio_segment
        mock_detect_nonsilent.return_value = []  # Simulate full silence

        # Instantiate AudioProcessor
        processor = AudioProcessor("dummy.mp4a")

        # Call is_fully_silent and assert
        self.assertTrue(processor.is_fully_silent())
        mock_from_file.assert_called_once_with("dummy.mp4a")
        mock_detect_nonsilent.assert_called_once_with(mock_audio_segment, min_silence_len=100, silence_thresh=-30)

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    @patch('audio_desilencer.audio_processor.detect_nonsilent')
    def test_is_fully_silent_when_audio_is_not_silent(self, mock_detect_nonsilent, mock_from_file):
        # Configure mocks
        mock_audio_segment = MagicMock()
        mock_from_file.return_value = mock_audio_segment
        mock_detect_nonsilent.return_value = [[0, 1000]]  # Simulate non-silent segments

        # Instantiate AudioProcessor
        processor = AudioProcessor("dummy.wav")

        # Call is_fully_silent and assert
        self.assertFalse(processor.is_fully_silent())
        mock_from_file.assert_called_once_with("dummy.wav")
        mock_detect_nonsilent.assert_called_once_with(mock_audio_segment, min_silence_len=100, silence_thresh=-30)

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    def test_audio_processor_init_format_detection(self, mock_from_file):
        # Configure mock
        mock_audio_segment = MagicMock()
        mock_from_file.return_value = mock_audio_segment

        # Instantiate AudioProcessor
        processor = AudioProcessor("dummy.m4a")

        # Assert that from_file was called correctly (without format)
        mock_from_file.assert_called_once_with("dummy.m4a")

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    def test_save_timeline_to_text(self, mock_from_file):
        # Configure mock for init
        mock_audio_segment = MagicMock()
        mock_from_file.return_value = mock_audio_segment

        processor = AudioProcessor("dummy.mp3")

        timeline_data = [(0, 1000), (2000, 3000)]
        output_path = "timeline.txt"

        m = mock_open()
        with patch('builtins.open', m):
            processor.save_timeline_to_text(timeline_data, output_path)

        m.assert_called_once_with(output_path, 'w')
        handle = m()
        handle.write.assert_any_call("[")
        handle.write.assert_any_call("(0, 1000), ")
        handle.write.assert_any_call("(2000, 3000), ")
        handle.write.assert_any_call("]")

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    def test_save_timeline_to_text_empty(self, mock_from_file):
        # Configure mock for init
        mock_audio_segment = MagicMock()
        mock_from_file.return_value = mock_audio_segment

        processor = AudioProcessor("dummy.mp3")

        timeline_data = []
        output_path = "empty_timeline.txt"

        m = mock_open()
        with patch('builtins.open', m):
            processor.save_timeline_to_text(timeline_data, output_path)

        m.assert_called_once_with(output_path, 'w')
        handle = m()
        handle.write.assert_any_call("[")
        handle.write.assert_any_call("]")
        # Ensure no tuples were written
        for call in handle.write.call_args_list:
            arg = call[0][0]
            if arg not in ("[", "]"):
                self.assertFalse(arg.startswith("("))


if __name__ == '__main__':
    unittest.main()
