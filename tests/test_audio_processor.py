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
    def test_split_audio_by_silence(self, mock_detect_nonsilent, mock_from_file):
        # Configure mocks
        mock_audio_segment = MagicMock()
        mock_from_file.return_value = mock_audio_segment
        mock_detect_nonsilent.return_value = [[0, 1000], [2000, 3000]]

        # Instantiate AudioProcessor
        processor = AudioProcessor("dummy.mp4a")

        # Call split_audio_by_silence and assert
        result = processor.split_audio_by_silence(min_silence_len=500, threshold=-40)
        self.assertEqual(result, [[0, 1000], [2000, 3000]])
        mock_from_file.assert_called_once_with("dummy.mp4a")
        mock_detect_nonsilent.assert_called_once_with(mock_audio_segment, min_silence_len=500, silence_thresh=-40)

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    @patch('audio_desilencer.audio_processor.detect_nonsilent')
    def test_is_fully_silent_when_audio_is_silent(self, mock_detect_nonsilent, mock_from_file):
        # Configure mocks
        mock_audio_segment = MagicMock()
        mock_from_file.return_value = mock_audio_segment
        mock_detect_nonsilent.return_value = []  # Simulate full silence

        # Instantiate AudioProcessor
        processor = AudioProcessor("dummy.mp4a")

        # Assert is_fully_silent returns True
        self.assertTrue(processor.is_fully_silent())

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    @patch('audio_desilencer.audio_processor.detect_nonsilent')
    def test_is_fully_silent_when_audio_is_not_silent(self, mock_detect_nonsilent, mock_from_file):
        # Configure mocks
        mock_audio_segment = MagicMock()
        mock_from_file.return_value = mock_audio_segment
        mock_detect_nonsilent.return_value = [[0, 1000]]

        # Instantiate AudioProcessor
        processor = AudioProcessor("dummy.mp4a")

        # Assert is_fully_silent returns False
        self.assertFalse(processor.is_fully_silent())

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    def test_audio_processor_init_format_detection(self, mock_from_file):
        mock_from_file.return_value = MagicMock()

        AudioProcessor("dummy.mp3")
        mock_from_file.assert_called_with("dummy.mp3")

        AudioProcessor("dummy.wav")
        mock_from_file.assert_called_with("dummy.wav")

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    def test_save_audio(self, mock_from_file):
        mock_audio_segment = MagicMock()
        mock_from_file.return_value = mock_audio_segment
        processor = AudioProcessor("dummy.mp3")

        audio_to_save = MagicMock()
        processor.save_audio(audio_to_save, "output.mp3")

        audio_to_save.export.assert_called_once_with("output.mp3", format="mp3")

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_timeline_to_text(self, mock_file, mock_from_file):
        mock_from_file.return_value = MagicMock()
        processor = AudioProcessor("dummy.mp3")

        timeline = [(0, 1000), (2000, 3000)]
        processor.save_timeline_to_text(timeline, "timeline.txt")

        mock_file.assert_called_once_with("timeline.txt", 'w')
        handle = mock_file()
        handle.write.assert_any_call("[")
        handle.write.assert_any_call("(0, 1000), ")
        handle.write.assert_any_call("(2000, 3000), ")
        handle.write.assert_any_call("]")

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_timeline_to_text_empty(self, mock_file, mock_from_file):
        mock_from_file.return_value = MagicMock()
        processor = AudioProcessor("dummy.mp3")

        processor.save_timeline_to_text([], "empty_timeline.txt")

        mock_file.assert_called_once_with("empty_timeline.txt", 'w')
        handle = mock_file()
        handle.write.assert_any_call("[")
        handle.write.assert_any_call("]")

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    @patch('audio_desilencer.audio_processor.detect_nonsilent')
    @patch('audio_desilencer.audio_processor.AudioSegment.empty')
    def test_process_audio_logic(self, mock_empty, mock_detect_nonsilent, mock_from_file):
        mock_audio = MagicMock()
        mock_audio.__getitem__.side_effect = lambda key: MagicMock(raw_data=b'audio')
        mock_audio._spawn.side_effect = lambda data: MagicMock(raw_data=data)
        mock_from_file.return_value = mock_audio
        mock_detect_nonsilent.return_value = [[100, 200], [300, 400]]
        mock_empty.return_value = MagicMock()

        processor = AudioProcessor("dummy.mp3")

        with patch.object(processor, 'save_audio') as mock_save_audio, \
             patch.object(processor, 'save_timeline_to_text') as mock_save_timeline:
            processor.process_audio()

            self.assertEqual(mock_save_audio.call_count, 2)
            self.assertEqual(mock_save_timeline.call_count, 2)

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    @patch('audio_desilencer.audio_processor.detect_nonsilent')
    @patch('audio_desilencer.audio_processor.AudioSegment.empty')
    def test_process_audio_fully_silent(self, mock_empty, mock_detect_nonsilent, mock_from_file):
        mock_audio = MagicMock()
        mock_from_file.return_value = mock_audio
        mock_detect_nonsilent.return_value = []
        mock_empty_segment = MagicMock()
        mock_empty.return_value = mock_empty_segment

        processor = AudioProcessor("dummy.mp3")

        with patch.object(processor, 'save_audio') as mock_save_audio, \
             patch.object(processor, 'save_timeline_to_text') as mock_save_timeline:
            processor.process_audio()

            mock_detect_nonsilent.assert_called_once()
            self.assertEqual(mock_save_audio.call_count, 2)
            self.assertEqual(mock_save_timeline.call_count, 2)

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    @patch('audio_desilencer.audio_processor.detect_nonsilent')
    @patch('audio_desilencer.audio_processor.AudioSegment.empty')
    def test_process_audio_fully_non_silent(self, mock_empty, mock_detect_nonsilent, mock_from_file):
        mock_audio = MagicMock()
        mock_audio.__len__.return_value = 1000
        mock_audio.__getitem__.side_effect = lambda key: MagicMock(raw_data=b'audio')
        mock_audio._spawn.side_effect = lambda data: MagicMock(raw_data=data)
        mock_from_file.return_value = mock_audio
        mock_detect_nonsilent.return_value = [[0, 1000]]
        mock_empty_segment = MagicMock()
        mock_empty.return_value = mock_empty_segment

        processor = AudioProcessor("dummy.mp3")

        with patch.object(processor, 'save_audio') as mock_save_audio, \
             patch.object(processor, 'save_timeline_to_text') as mock_save_timeline:
            processor.process_audio()

            mock_detect_nonsilent.assert_called_once()
            self.assertEqual(mock_save_audio.call_count, 2)
            self.assertEqual(mock_save_timeline.call_count, 2)

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    @patch('audio_desilencer.audio_processor.detect_nonsilent')
    def test_main_defaults(self, mock_detect_nonsilent, mock_from_file):
        mock_audio = MagicMock()
        mock_audio._spawn.return_value = MagicMock()
        mock_from_file.return_value = mock_audio
        mock_detect_nonsilent.return_value = []

        with patch('sys.argv', ['audio-desilencer', 'input.mp3']), \
             patch.object(AudioProcessor, 'save_audio'), \
             patch.object(AudioProcessor, 'save_timeline_to_text'):
            from audio_desilencer.audio_processor import main
            main()

        mock_detect_nonsilent.assert_called_once_with(mock_audio, min_silence_len=100, silence_thresh=-30)

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    @patch('audio_desilencer.audio_processor.detect_nonsilent')
    def test_main_custom_args(self, mock_detect_nonsilent, mock_from_file):
        mock_audio = MagicMock()
        mock_audio._spawn.return_value = MagicMock()
        mock_from_file.return_value = mock_audio
        mock_detect_nonsilent.return_value = []

        with patch('sys.argv', [
            'audio-desilencer', 'input.mp3',
            '--output_folder', 'custom_output',
            '--min_silence_len', '500',
            '--threshold', '-40',
        ]), patch.object(AudioProcessor, 'save_audio'), \
             patch.object(AudioProcessor, 'save_timeline_to_text'):
            from audio_desilencer.audio_processor import main
            main()

        mock_detect_nonsilent.assert_called_once_with(mock_audio, min_silence_len=500, silence_thresh=-40)

    @patch('audio_desilencer.audio_processor.AudioSegment.from_file')
    @patch('audio_desilencer.audio_processor.detect_nonsilent')
    @patch('builtins.print')
    def test_process_audio_exception(self, mock_print, mock_detect_nonsilent, mock_from_file):
        mock_audio = MagicMock()
        mock_from_file.return_value = mock_audio
        mock_detect_nonsilent.side_effect = ValueError("Test Exception")

        processor = AudioProcessor("dummy.mp3")

        processor.process_audio()

        self.assertTrue(mock_print.called)
        self.assertTrue('An error occurred' in str(mock_print.call_args[0][0]))


if __name__ == '__main__':
    unittest.main()
