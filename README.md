# AudioDeSilencer

AudioDeSilencer is a powerful audio processing tool that helps you detect and remove silence in audio recordings. It also provides functionality to assist in video silence removal using the generated text files.

## Features

- **Silence Detection**: Identify and segment silent parts of audio based on custom-defined silence thresholds and minimum silence duration.

- **Silence Removal**: Remove detected silence segments to enhance audio quality and reduce unnecessary gaps.

- **Text File Generation**: Create text files containing the timeline data of silent and non-silent parts, enabling further processing for video silence removal or analysis.

- **Command-Line Interface**: Easily integrate AudioDeSilencer into your audio and video processing pipelines with a user-friendly command-line interface.

## Installation

To use AudioDeSilencer, follow these steps:

1. Clone this repository to your local machine.

   ```bash
   git clone https://github.com/btawaifi/AudioDeSilencer.git
   ```

2. Install the required dependencies. You can use pip for this:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

AudioDeSilencer can be run from the command line with various options. Here's a basic usage example:

```bash
python audio_desilencer.py input_audio.mp3 --output_folder output_directory --min_silence_len 100 --threshold -30
```

#### Command-Line Arguments

- `input_audio.mp3`: The path to the input audio file.
- `--output_folder`: (Optional) The folder where the output files and timeline data will be saved (default is "output").
- `--min_silence_len`: (Optional) The minimum duration of silence (in milliseconds) to be considered as a separate silent part (default is 100 ms).
- `--threshold`: (Optional) The silence threshold in dBFS (decibels relative to full scale) used to distinguish between silent and non-silent parts (default is -30 dBFS).

#### Output

AudioDeSilencer will generate the following output:

- `interview_silent.mp3`: Audio file with silence segments removed.
- `interview_non_silent.mp3`: Audio file containing only the non-silent parts.
- `silent_parts.txt`: Timeline data of silent parts.
- `non_silent_parts.txt`: Timeline data of non-silent parts.

## Contributing

We welcome contributions to AudioDeSilencer! Feel free to open issues or submit pull requests to improve the tool.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
