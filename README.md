# Audio DeSilencer

Audio DeSilencer is a small Python package and CLI for shortening long silent pauses **without processing the audio you keep**.

The core invariant is simple:

> If a source interval is retained, Audio DeSilencer does not normalize, limit, EQ, compress, de-ess, crossfade, or otherwise modify it. Only selected time ranges are removed.

```bash
pip install audio-desilencer
```

## Why this design

Silence removal is an editing problem, not a mastering problem. The processor therefore treats the source recording as authoritative:

```text
source audio
    │
    ├── detect confirmed long silence
    │
    ├── keep a small natural pause around speech
    │
    ├── remove only the middle of each accepted silence
    │
    └── concatenate the untouched retained source spans
```

The processing backend is FFmpeg end-to-end. Audio is not first converted through pydub's integer `AudioSegment` representation, which avoids hard-clipping over-range floating-point samples from formats such as Opus before editing begins.

## Requirements

- Python 3.10+
- `ffmpeg` and `ffprobe` available on `PATH`

No third-party Python runtime packages are required.

## Defaults

The defaults are intentionally conservative for speech:

```text
minimum continuous silence: 700 ms
silence threshold:           -38 dBFS
silence retained per pause:   150 ms
output format:                WAV
```

A 1.5-second pause, for example, is shortened to roughly 150 ms. Speech on either side remains untouched.

## CLI

```bash
audio-desilencer input.ogg \
  --output_folder output \
  --min_silence_len 700 \
  --threshold -38 \
  --target_silence_len 150 \
  --output_format wav
```

Use `--target_silence_len 0` to remove accepted silence completely. Keeping a small value is usually more natural for speech because edits remain inside quiet material instead of landing directly on word boundaries.

Optional custom output stem:

```bash
audio-desilencer interview.m4a --output_stem cleaned
```

For `interview.m4a`, the default WAV outputs are:

```text
interview_silent.wav
interview_non_silent.wav
interview_silent_parts.txt
interview_non_silent_parts.txt
```

`*_non_silent` is the desilenced recording. It still contains the small amount of pause requested by `target_silence_len`.

`*_silent` contains only the material actually removed from the source, not every low-energy sample detected near speech boundaries.

## Python API

```python
from audio_desilencer import AudioProcessor

processor = AudioProcessor("input.ogg")
result = processor.process_audio(
    min_silence_len=700,
    threshold=-38,
    target_silence_len=150,
    output_folder="output",
    output_format="wav",
)

print(result.detected_silence_ranges)
print(result.silent_ranges)       # ranges actually removed
print(result.non_silent_ranges)   # source ranges retained in the output
print(result.non_silent_audio_path)
```

The legacy detection method remains available:

```python
non_silent_source_ranges = processor.split_audio_by_silence(
    min_silence_len=700,
    threshold=-38,
)
```

For direct silence inspection:

```python
silent_ranges = processor.detect_silence_ranges(
    min_silence_len=700,
    threshold=-38,
)
```

## Timeline semantics

Timeline files contain Python-literal `(start_ms, end_ms)` tuples in **source time**.

```text
[(9824, 10599), (19576, 20330)]
```

- `silent_parts.txt` contains ranges actually removed.
- `non_silent_parts.txt` contains source ranges retained in the desilenced output.
- `ProcessingResult.detected_silence_ranges` exposes the full silence regions detected before pause shortening.

## Signal preservation

Audio DeSilencer deliberately performs no gain or tone processing.

The FFmpeg render graph only uses timing operations:

```text
atrim -> timestamp reset -> concat
```

For WAV output, the package writes 32-bit floating-point PCM. This preserves over-range floating-point source samples instead of forcing them through an integer PCM ceiling. No attenuation or normalization is applied.

Lossy formats such as MP3 must be re-encoded and therefore cannot be sample-identical to the source. Use WAV when validating editing quality or when you want a lossless intermediate.

## Architecture

```text
CLI / Python caller
        │
        ▼
AudioProcessor
├── ffprobe source metadata
├── FFmpeg continuous-silence detection
├── normalize detected ranges
├── build removal ranges from the middle of silence
├── compute retained source ranges
├── FFmpeg trim + concatenate retained spans
├── export removed spans separately
└── write source-time timelines
```

This avoids the previous architecture of extracting independent speech chunks and blindly joining their raw PCM bytes at detector boundaries.

## Testing

```bash
python -m unittest discover -s tests -v
```

The regression suite covers:

- leading, internal, and trailing silence
- fully silent and fully non-silent files
- conservative middle-of-pause removal
- source/removed/retained range semantics
- real FFmpeg silence detection on synthetic audio
- over-range float WAV preservation
- byte-for-byte equality of retained decoded PCM on lossless fixtures
- output naming and path containment
- timeline serialization
- CLI success/failure behavior

GitHub Actions runs the suite on Python 3.10, 3.11, 3.12, and 3.13 and separately builds and installs the wheel/source distribution.

## Scope / limitations

- Detection is threshold-based, deterministic, and explainable; it is not semantic voice-activity detection.
- Thresholds still need to match the recording environment. Quiet speech below the selected threshold can still be classified as silence, so conservative settings are recommended.
- The current production path does not normalize loudness or repair already-clipped source audio by design.
- FFmpeg codec support depends on the FFmpeg build installed on the host.

## License

MIT
