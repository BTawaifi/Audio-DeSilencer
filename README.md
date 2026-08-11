# Audio DeSilencer

Audio DeSilencer is a small Python package and CLI for shortening long silent pauses **without processing the audio you keep**.

The core invariant is simple:

> If a source interval is retained, Audio DeSilencer does not normalize, limit, EQ, compress, de-ess, crossfade, or otherwise modify it. Only selected time ranges are removed.

```bash
pip install audio-desilencer
```

## Requirements

- Python 3.10+
- `ffmpeg` and `ffprobe` available on `PATH`

No third-party Python runtime packages are required.

Install FFmpeg separately if needed:

```text
Windows:
winget install Gyan.FFmpeg

macOS:
brew install ffmpeg

Ubuntu / Debian:
sudo apt update
sudo apt install ffmpeg
```

Verify:

```bash
ffmpeg -version
ffprobe -version
```

## Why this design

Silence removal is an editing problem, not a mastering problem. The source recording stays authoritative:

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

The processing backend is FFmpeg end-to-end. Audio is not first converted through an integer `AudioSegment` representation, avoiding premature integer clipping of over-range floating-point samples from formats such as Opus.

## Defaults

The stable defaults are intentionally conservative for speech:

```text
minimum continuous silence: 700 ms
silence threshold:           -38 dBFS
silence retained per pause:   150 ms
output format:                WAV
```

A 1.5-second pause, for example, is shortened to roughly 150 ms. Speech on either side remains untouched.

## Detection modes

### Fixed threshold — default

```bash
audio-desilencer input.ogg --threshold -38
```

This uses FFmpeg's `silencedetect` behavior and is the stable default.

### Conservative auto threshold

```bash
audio-desilencer input.ogg --threshold auto
```

Auto mode does **not** use AI, a model, training data, internet access, or a cloud service. It analyzes short peak-level windows in the recording and estimates a conservative threshold from the quieter part of the signal.

Safety rules:

- any loud sample on any channel makes that analysis window active
- all channels must be quiet before a frame is considered quiet
- auto mode never chooses a threshold more aggressive than the normal `-38 dBFS` default
- auto mode uses 3 dB of exit hysteresis by default to avoid rapidly switching state around the threshold

You can also enable hysteresis with a numeric threshold:

```bash
audio-desilencer input.ogg --threshold -38 --hysteresis_db 3
```

A numeric threshold with no `--hysteresis_db` preserves the stable FFmpeg detector path.

## CLI

```bash
audio-desilencer input.ogg \
  --output_folder output \
  --min_silence_len 700 \
  --threshold -38 \
  --target_silence_len 150 \
  --output_format wav
```

Use `--target_silence_len 0` to remove accepted silence completely. Keeping a small value is usually more natural because edits remain inside quiet material instead of landing directly on word boundaries.

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

`*_non_silent.wav` is the desilenced recording. It still contains the amount of pause requested by `target_silence_len`.

`*_silent.wav` is an **inspection artifact** containing only the removed ranges concatenated together. It is not intended to sound like a natural continuous recording.

## Choosing settings

A practical starting point for voice recordings:

```text
--threshold -38
--min_silence_len 700
--target_silence_len 150
```

More aggressive pacing:

```text
--target_silence_len 50
```

More natural pacing:

```text
--target_silence_len 250
```

If the recording level/noise floor varies and you do not want to choose a threshold manually:

```text
--threshold auto
```

If quiet speech is ever being classified as silence, make the threshold **lower/more negative**, for example `-42`, or use `auto`. If too little silence is detected, raise it cautiously.

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
print(result.silent_ranges)              # source ranges actually removed
print(result.non_silent_ranges)          # source ranges retained
print(result.resolved_threshold_dbfs)    # useful with threshold="auto"
print(result.detector)                    # ffmpeg / adaptive / hysteresis
print(result.non_silent_audio_path)
```

Auto mode:

```python
result = processor.process_audio(
    threshold="auto",
    min_silence_len=700,
    target_silence_len=150,
)
```

Direct detection remains available:

```python
silent_ranges = processor.detect_silence_ranges(
    min_silence_len=700,
    threshold=-38,
)
```

The backward-compatible non-silent range API is also available:

```python
non_silent_source_ranges = processor.split_audio_by_silence(
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
- `ProcessingResult.detected_silence_ranges` exposes full silence regions before pause shortening.

## Signal preservation

Audio DeSilencer deliberately performs no gain or tone processing.

The render graph only uses timing operations:

```text
atrim -> timestamp reset -> concat
```

For WAV output, the package writes 32-bit floating-point PCM. This preserves over-range floating-point source samples instead of forcing them through an integer PCM ceiling. No attenuation or normalization is applied.

Lossy formats such as MP3 must be re-encoded and therefore cannot be sample-identical to the source. Use WAV when validating editing quality or when you want a lossless intermediate.

## Stereo and multichannel policy

Silence removal is conservative across channels.

A section is considered quiet only when **all channels are quiet**. Activity on one channel protects that interval from removal. This avoids deleting material from stereo recordings where only one side contains useful audio.

## Large recordings

Recordings with many detected pauses can produce very large FFmpeg filter graphs. Audio DeSilencer automatically moves large graphs into a temporary FFmpeg filter-script file instead of placing the entire graph on the operating-system command line. The temporary file is removed after rendering.

## Architecture

```text
CLI / Python caller
        │
        ▼
AudioProcessor
├── ffprobe source metadata
├── fixed FFmpeg silence detection
│      OR deterministic peak/hysteresis analysis
├── normalize detected ranges
├── build removal ranges from the middle of silence
├── compute retained source ranges
├── FFmpeg trim + concatenate retained spans
├── export removed spans separately
└── write source-time timelines
```

The detector decides **where editing is safe**. The renderer does not attempt to repair bad detection by processing the voice.

## Testing

```bash
python -m unittest discover -s tests -v
```

The regression suite covers:

- leading, internal, and trailing silence
- fully silent and fully non-silent files
- conservative middle-of-pause removal
- fixed and deterministic auto detection
- hysteresis behavior
- stereo channel-safety behavior
- source/removed/retained range semantics
- real FFmpeg silence detection on synthetic audio
- over-range float WAV preservation
- byte-for-byte equality of retained decoded PCM on lossless fixtures
- large edit graphs / command-length safety
- output naming and path containment
- timeline serialization
- CLI success/failure behavior

GitHub Actions runs the suite on Python 3.10, 3.11, 3.12, and 3.13 and separately builds and installs the wheel/source distribution.

## Scope / limitations

- Fixed and auto detection are deterministic signal analysis, not semantic voice-activity detection.
- Auto mode is deliberately conservative and may leave more silence rather than risk removing quiet speech.
- A very noisy recording may still require a manually chosen threshold.
- The current production path does not normalize loudness or repair already-clipped source audio by design.
- FFmpeg codec support depends on the FFmpeg build installed on the host.
- No ML/VAD dependency is bundled. A future optional voice-specific guard can be added without changing the non-destructive renderer.

## License

MIT
