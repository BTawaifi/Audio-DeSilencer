# Audio DeSilencer

Audio DeSilencer is a small Python package and CLI for detecting silent/non-silent regions, separating those regions into output audio files, and exporting the corresponding timelines.

```bash
pip install audio-desilencer
```

## Features

- Detect non-silent ranges with configurable dBFS and minimum-silence thresholds
- Correctly derive the complete silent complement, including leading and trailing silence
- Handle fully silent and fully non-silent files without dropping audio
- Export separate silent and non-silent audio files
- Export the exact silent/non-silent millisecond timelines
- Choose the output codec/extension instead of forcing every result to MP3
- Use either the Python API or the `audio-desilencer` CLI
- Return a structured `ProcessingResult` to Python callers

Codec support is provided by pydub/FFmpeg. Formats that require FFmpeg still depend on FFmpeg being installed and available on the host system.

## Silence model

Silence detection is controlled by:

- `threshold`: audio below this dBFS level is considered silent
- `min_silence_len`: minimum duration in milliseconds before a region counts as silence

The processor first obtains non-silent ranges and then computes their complement across the full audio duration. That means leading, internal, and trailing silence are represented consistently.

## CLI

```bash
audio-desilencer input_audio.mp3 \
  --output_folder output \
  --min_silence_len 100 \
  --threshold -30 \
  --output_format mp3
```

Optional custom output stem:

```bash
audio-desilencer interview.m4a --output_stem cleaned --output_format wav
```

For an input named `interview.m4a`, the default output names are:

```text
interview_silent.mp3
interview_non_silent.mp3
interview_silent_parts.txt
interview_non_silent_parts.txt
```

The CLI returns a non-zero exit status when loading or processing fails instead of printing an error and appearing successful.

## Python API

```python
from audio_desilencer import AudioProcessor

processor = AudioProcessor("input.m4a")
result = processor.process_audio(
    min_silence_len=200,
    threshold=-40,
    output_folder="output",
    output_format="wav",
)

print(result.silent_ranges)
print(result.non_silent_ranges)
print(result.non_silent_audio_path)
```

You can also use the detection layer directly:

```python
segments = processor.split_audio_by_silence(
    min_silence_len=200,
    threshold=-40,
)

if processor.is_fully_silent():
    print("No non-silent audio detected")
```

`process_audio()` raises processing errors to Python callers. Friendly error reporting is kept at the CLI boundary so library code can reliably distinguish success from failure.

## Timeline format

Timeline files contain a Python-literal list of `(start_ms, end_ms)` tuples:

```text
[(0, 1200), (3400, 5100)]
```

Ranges are clamped, sorted, merged when necessary, and never include zero-length intervals.

## Architecture

```text
CLI / Python caller
        │
        ▼
AudioProcessor
├── load through pydub
├── detect non-silent ranges
├── normalize ranges
├── compute silent complement over full duration
├── concatenate selected source slices
├── export audio
└── write timing metadata
        │
        ▼
FFmpeg-backed codec support where required
```

The processing layer is shared by the CLI and Python API. Output naming is derived from the input stem by default, so processing multiple files into the same output folder does not overwrite a generic `interview_*` filename.

## Testing

The regression suite contains both pure interval tests and tests that use real pydub `AudioSegment` data. It specifically covers:

- leading, internal, and trailing silence
- fully silent audio
- fully non-silent audio
- range clamping/sorting/merging
- real tone-vs-silence detection
- output naming and codec selection
- timeline serialization
- CLI success/failure exit behavior
- package API behavior

Run locally:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the suite on Python 3.10, 3.11, 3.12, and 3.13. A separate packaging job builds the wheel/source distribution, installs the wheel, verifies imports, and exercises the installed CLI.

## Development

```bash
git clone https://github.com/BTawaifi/Audio-DeSilencer.git
cd Audio-DeSilencer
python -m pip install -e .
python -m unittest discover -s tests -v
```

The package declares Python 3.10+ support and excludes the repository's `tests` package from built distributions.

## Scope / limitations

- Threshold-based silence detection is deterministic and explainable but not semantic voice-activity detection.
- Results still depend on choosing a threshold appropriate for the recording.
- File-based processing keeps decoded audio in memory; it is not a streaming engine.
- Codec availability depends on the local pydub/FFmpeg environment.
- The optimized concatenation path joins raw slices from the same source audio and therefore assumes matching audio parameters, which is true for slices produced by this processor.

## License

MIT
