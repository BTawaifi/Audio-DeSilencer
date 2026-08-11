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

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    @patch('audio_desilencer.audio_processor.detect_nonsilent')
    @patch('audio_desilencer.audio_processor.AudioSegment.empty')
    @patch('audio_desilencer.audio_processor.os.makedirs')
    def test_process_audio_logic(self, mock_makedirs, mock_empty, mock_detect_nonsilent, mock_from_file):
        # Configure mocks
        mock_audio = MagicMock()
        mock_from_file.return_value = mock_audio
        mock_detect_nonsilent.return_value = [[100, 200], [400, 500]]

        # Mock AudioSegment slices to have 'raw_data'
        def get_slice(s):
            m = MagicMock()
            m.raw_data = b"data_" + str(s.start).encode() + b"_" + str(s.stop).encode()
            return m
        mock_audio.__getitem__.side_effect = get_slice

        mock_empty_segment = MagicMock()
        mock_empty.return_value = mock_empty_segment

        # Instantiate AudioProcessor
        processor = AudioProcessor("dummy.mp3")

        # Call process_audio
        with patch.object(processor, 'save_audio') as mock_save_audio, \
             patch.object(processor, 'save_timeline_to_text') as mock_save_timeline:
            processor.process_audio()

            # Verify detect_nonsilent call
            mock_detect_nonsilent.assert_called_once()

            # Verify slices (non_silent: [100:200], [400:500], silent: [0:100], [200:400])
            expected_slices = [slice(100, 200), slice(0, 100), slice(400, 500), slice(200, 400)]
            actual_slices = [call.args[0] for call in mock_audio.__getitem__.call_args_list]
            self.assertEqual(len(actual_slices), 4)
            for s in expected_slices:
                self.assertIn(s, actual_slices)

            # Verify raw data concatenation and _spawn calls
            # non_silent raw data: b"data_100_200" + b"data_400_500"
            # silent raw data: b"data_0_100" + b"data_200_400"
            expected_non_silent_raw = b"data_100_200data_400_500"
            expected_silent_raw = b"data_0_100data_200_400"

            spawn_calls = mock_audio._spawn.call_args_list
            self.assertEqual(len(spawn_calls), 2)
            actual_spawn_data = [call.args[0] for call in spawn_calls]
            self.assertIn(expected_non_silent_raw, actual_spawn_data)
            self.assertIn(expected_silent_raw, actual_spawn_data)


if __name__ == '__main__':
    unittest.main()
