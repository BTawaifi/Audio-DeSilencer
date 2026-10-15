import unittest
from unittest.mock import patch

import audio_desilencer.cli as cli


class CliDefaultTests(unittest.TestCase):
    @patch.object(cli, "AudioProcessor")
    def test_zero_config_cli_uses_smart_speech_defaults(self, processor_cls):
        processor = processor_cls.return_value

        code = cli.main(["input.m4a"])

        self.assertEqual(code, 0)
        processor_cls.assert_called_once_with("input.m4a")
        processor.process_audio.assert_called_once_with(
            min_silence_len=700,
            threshold="auto",
            target_silence_len=150,
            hysteresis_db=None,
            output_folder="output",
            output_format="wav",
            output_stem=None,
        )

    @patch.object(cli, "AudioProcessor")
    def test_cli_still_accepts_fixed_threshold(self, processor_cls):
        processor = processor_cls.return_value

        code = cli.main(["input.wav", "--threshold", "-42", "--hysteresis_db", "2"])

        self.assertEqual(code, 0)
        self.assertEqual(processor.process_audio.call_args.kwargs["threshold"], -42.0)
        self.assertEqual(processor.process_audio.call_args.kwargs["hysteresis_db"], 2.0)

    def test_parser_help_exposes_smart_defaults(self):
        parser = cli.build_parser()
        args = parser.parse_args(["input.wav"])
        self.assertEqual(args.threshold, "auto")
        self.assertEqual(args.min_silence_len, 700)
        self.assertEqual(args.target_silence_len, 150)
        self.assertEqual(args.output_format, "wav")


if __name__ == "__main__":
    unittest.main()
