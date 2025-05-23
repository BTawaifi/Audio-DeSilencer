# Audio DeSilencer

Audio DeSilencer is a powerful Python package for audio processing that empowers you to detect and remove silence in audio recordings. Additionally, it provides functionality to facilitate video silence removal using the generated text files.

## Features

- **Silence Detection**: Identify and segment silent parts of audio based on custom-defined silence thresholds and minimum silence duration.

- **Silence Removal**: Effortlessly remove detected silence segments to enhance audio quality and eliminate unnecessary gaps.

- **Text File Generation**: Create text files containing the timeline data of silent and non-silent parts, facilitating further processing for video silence removal or in-depth analysis.

- **Wide Format Support**: Now supports a wider range of audio formats, including MP4A, OGG, FLAC, WAV, MP3, and more, as supported by FFmpeg, thanks to automatic format detection.

- **Command-Line Interface**: Seamlessly integrate Audio DeSilencer into your audio and video processing pipelines with an intuitive command-line interface.

### Checking for Full Silence

The `AudioProcessor` class now includes a method to check if an audio file is completely silent.

**`is_fully_silent(min_silence_len=100, threshold=-30)`**

-   `min_silence_len` (int): The minimum duration (in milliseconds) that a segment of audio must have to be considered non-silent. Default is 100 ms.
-   `threshold` (int): The audio level (in dBFS) below which audio is considered silent. Default is -30 dBFS.
-   **Returns**: `True` if no non-silent segments are found (i.e., the entire audio is below the `threshold` for durations longer than `min_silence_len`), `False` otherwise.

**Example:**

```python
from audio_desilencer.audio_processor import AudioProcessor

# Initialize the processor with your audio file
# Supports MP4A, WAV, MP3, and other ffmpeg-supported formats
processor = AudioProcessor("path/to/your/audiofile.m4a")

# Check if the audio is fully silent using default parameters
if processor.is_fully_silent():
    print("The audio file is completely silent.")
else:
    print("The audio file contains non-silent parts.")

# Or with custom parameters
if processor.is_fully_silent(min_silence_len=200, threshold=-40):
    print("The audio file is completely silent (using custom settings).")
else:
    print("The audio file contains non-silent parts (using custom settings).")
```

## Installation

### Installation via pip

To install Audio DeSilencer using pip, simply run:

```bash
pip install audio-desilencer
```

Now, you can run Audio DeSilencer from the command line:

   ```bash
   audio-desilencer input_audio.mp3 --output_folder output_directory --min_silence_len 100 --threshold -30
   ```

### Manual Installation

If you prefer not to use pip, you can manually install Audio DeSilencer by following these steps:

1. Clone the Audio DeSilencer repository:

   ```bash
   git clone https://github.com/BTawaifi/Audio-DeSilencer.git
   ```

2. Navigate to the project directory:

   ```bash
   cd Audio-DeSilencer
   ```

3. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Now, you can run Audio DeSilencer from the command line:

   ```bash
   python audio-desilencer.py input_audio.mp3 --output_folder output_directory --min_silence_len 100 --threshold -30
   ```

### Command-Line Arguments

- `input_audio.mp3`: The path to the input audio file.
- `--output_folder`: (Optional) The folder where the output files and timeline data will be saved (default is "output").
- `--min_silence_len`: (Optional) The minimum duration of silence (in milliseconds) to be considered as a separate silent part (default is 100 ms).
- `--threshold`: (Optional) The silence threshold in dBFS (decibels relative to full scale) used to distinguish between silent and non-silent parts (default is -30 dBFS).

### Output

Audio DeSilencer will generate the following output:

- `interview_silent.mp3`: Audio file with silence segments removed.
- `interview_non_silent.mp3`: Audio file containing only the non-silent parts.
- `silent_parts.txt`: Timeline data of silent parts.
- `non_silent_parts.txt`: Timeline data of non-silent parts.

## Usage Example

Here's a usage example to get you started:

```bash
python audio-desilencer.py input_audio.mp3 --output_folder output_directory --min_silence_len 100 --threshold -30
```

Or if you have it installed using pip

```bash
audio-desilencer input_audio.mp3 --output_folder output_directory --min_silence_len 100 --threshold -30
```

## Contributing

Contributions to Audio DeSilencer are highly encouraged! Whether you'd like to report issues or submit pull requests to enhance the tool, your contributions are invaluable. Please refer to the [CONTRIBUTING](CONTRIBUTING.md) guide for details on how to contribute.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.