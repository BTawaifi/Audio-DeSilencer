import unittest
from unittest.mock import patch, MagicMock
from audio_desilencer.audio_processor import AudioProcessor
# Import pydub.silence if you are directly patching detect_nonsilent from there
# from pydub.silence import detect_nonsilent

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
        # Check that 'format' was not in the kwargs or was None
        # called_args, called_kwargs = mock_from_file.call_args
        # self.assertNotIn('format', called_kwargs) # This is one way
        # Or, more simply, if no other args are expected:
        # self.assertEqual(called_args, ("dummy.m4a",))
        # self.assertEqual(called_kwargs, {})


if __name__ == '__main__':
    unittest.main()
