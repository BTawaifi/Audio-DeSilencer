# Audio DeSilencer

Audio DeSilencer is a Python package and CLI for detecting silence in audio, removing silent segments, and exporting timing data for downstream audio/video workflows.

```bash
pip install audio-desilencer
```

The project is intentionally small: it wraps a concrete audio-processing workflow behind both a Python API and a command-line interface rather than requiring users to script FFmpeg/pydub behavior themselves.

## Features

- Detect silent and non-silent regions using configurable thresholds
- Remove detected silence from audio
- Export silent/non-silent timeline data
- Detect fully silent files
- Support formats handled by FFmpeg/pydub, including MP3, WAV, FLAC, OGG, and M4A/MP4A
- Use the same functionality through Python or the CLI

## Architecture

```text
CLI / Python caller
        │
        ▼
AudioProcessor
├── load audio through pydub
├── detect non-silent ranges
├── derive silent ranges
├── export processed audio
└── write timing metadata
        │
        ▼
FFmpeg-backed codec support
```

The core processing logic lives in the package rather than in the CLI entry point, so command-line use and programmatic use share the same behavior.

## Why pydub + FFmpeg

The package delegates codec handling to mature tooling instead of implementing decoders itself.

**Benefit:** broad input-format support and a much smaller codebase.

**Cost:** runtime behavior ultimately depends on FFmpeg availability for formats that require it.

## Silence detection model

Silence is determined from two main parameters:

- `threshold`: audio below this dBFS level is considered silent
- `min_silence_len`: minimum duration required before a region is treated as silence

Those values are intentionally caller-configurable because there is no universal threshold that works equally well for speech, music, noisy recordings, and studio audio.

## Python usage

```python
from audio_desilencer.audio_processor import AudioProcessor

processor = AudioProcessor("input.m4a")

if processor.is_fully_silent():
    print("No meaningful audio detected")

segments = processor.split_audio_by_silence(
    min_silence_len=200,
    threshold=-40,
)
```

## CLI usage

```bash
audio-desilencer input_audio.mp3 \
  --output_folder output \
  --min_silence_len 100 \
  --threshold -30
```

Typical output includes processed audio plus text files describing silent and non-silent intervals.

## Testing strategy

The repository includes a `unittest` suite around the processing layer. External audio/codec behavior is mocked where appropriate so core segmentation and error-handling logic can be tested deterministically without depending on large media fixtures.

CI runs the suite across multiple Python versions on pushes and pull requests:

```bash
python -m unittest discover -s tests -v
```

This keeps package behavior verifiable independently from a developer's local FFmpeg installation.

## Engineering tradeoffs

### Timing metadata as plain text

**Benefit:** simple to inspect, script, and feed into video-editing workflows.

**Cost:** it is less structured than JSON or a typed interchange format.

### Threshold-based detection

**Benefit:** deterministic, fast, explainable, and user-tunable.

**Cost:** it does not attempt semantic speech/music detection and therefore needs appropriate threshold configuration for noisy recordings.

### Lightweight package surface

**Benefit:** easy installation and a small API.

**Cost:** advanced workflows such as VAD models, streaming processing, batch orchestration, or GUI editing are intentionally outside the core package.

## Known limitations

- Results depend heavily on the chosen silence threshold and minimum duration.
- Codec support depends on the local FFmpeg/pydub environment.
- The package is designed for file-based processing, not real-time audio streams.
- It does not attempt ML-based voice activity detection.

## Development

Clone and install in editable mode:

```bash
git clone https://github.com/BTawaifi/Audio-DeSilencer.git
cd Audio-DeSilencer
pip install -e .
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

## Contributing

Issues and pull requests are welcome. Changes to detection behavior should ideally include regression tests covering the relevant threshold/segment edge case.

## License

MIT
