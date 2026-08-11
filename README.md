# Audio DeSilencer

Audio DeSilencer is a small Python package and CLI for shortening long silent pauses **without processing the audio you keep**.

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

## Zero-config usage

For normal speech recordings, the recommended CLI usage is now simply:

```bash
audio-desilencer input.m4a
```

The CLI uses conservative speech-oriented defaults:

```text
minimum continuous silence: 700 ms
silence threshold:           auto
silence retained per pause:  150 ms
auto hysteresis:               3 dB
output format:                WAV
output folder:                output
```

`auto` is deterministic signal analysis. It does **not** use AI, a model, training data, internet access, or a cloud service.

Auto mode analyzes short peak-level windows, estimates the quieter part of the recording, and chooses a conservative silence threshold. It never chooses a threshold more aggressive than `-38 dBFS`. Any activity on any channel protects that interval from removal.

A 1.5-second accepted pause, for example, is shortened to roughly 150 ms. Speech on either side remains untouched.

## Why this design

Silence removal is an editing problem, not a mastering problem. The source recording stays authoritative:

```text
source audio
    │
    ├── detect confirmed long silence
    ├── keep a small natural pause around speech
    ├── remove only the middle of each accepted silence
    └── concatenate the untouched retained source spans
```

The processing backend is FFmpeg end-to-end. Audio is not first converted through an integer `AudioSegment` representation, avoiding premature integer clipping of over-range floating-point samples from formats such as Opus.

## Detection modes

### Auto threshold — CLI default

```bash
audio-desilencer input.ogg
```

Equivalent to:

```bash
audio-desilencer input.ogg --threshold auto
```

Auto mode uses 3 dB of exit hysteresis by default so the detector does not rapidly switch state around the threshold.

### Fixed threshold

For a fixed, explicitly reproducible threshold:

```bash
audio-desilencer input.ogg --threshold -38
```

A numeric threshold with no `--hysteresis_db` uses FFmpeg's stable `silencedetect` path.

You can also add hysteresis to a numeric threshold:

```bash
audio-desilencer input.ogg --threshold -38 --hysteresis_db 3
```

## CLI options

```bash
audio-desilencer input.ogg \
  --output_folder output \
  --min_silence_len 700 \
  --threshold auto \
  --target_silence_len 150 \
  --output_format wav
```

Use `--target_silence_len 0` to remove accepted silence completely. Keeping a small value is usually more natural because edits remain inside quiet material instead of landing directly on word boundaries.

For more aggressive pacing:

```bash
audio-desilencer input.ogg --target_silence_len 50
```

For more natural pacing:

```bash
audio-desilencer input.ogg --target_silence_len 250
```

If quiet speech is ever classified as silence, use a lower/more-negative fixed threshold such as `-42`.

## Outputs

For `interview.m4a`, the default WAV outputs are:

```text
output/interview_silent.wav
output/interview_non_silent.wav
output/interview_silent_parts.txt
output/interview_non_silent_parts.txt
```

`*_non_silent.wav` is the desilenced recording.

`*_silent.wav` is an **inspection artifact** containing only the removed ranges concatenated together. It is not intended to sound like a natural continuous recording.

Timeline files contain Python-literal `(start_ms, end_ms)` tuples in **source time**.

## Python API

The Python API keeps explicit detector control:

```python
from audio_desilencer import AudioProcessor

processor = AudioProcessor("input.ogg")
result = processor.process_audio(
    min_silence_len=700,
    threshold="auto",
    target_silence_len=150,
    output_folder="output",
    output_format="wav",
)

print(result.detected_silence_ranges)
print(result.silent_ranges)              # source ranges actually removed
print(result.non_silent_ranges)          # source ranges retained
print(result.resolved_threshold_dbfs)
print(result.detector)                    # ffmpeg / adaptive / hysteresis
print(result.non_silent_audio_path)
```

For a fixed detector:

```python
result = processor.process_audio(threshold=-38)
```

Direct detection remains available with `detect_silence_ranges()` and the backward-compatible `split_audio_by_silence()` API.

## Signal preservation

Audio DeSilencer deliberately performs no gain or tone processing.

The render graph only uses timing operations:

```text
atrim -> timestamp reset -> concat
```

For WAV output, the package writes 32-bit floating-point PCM. This preserves over-range floating-point source samples instead of forcing them through an integer PCM ceiling. No attenuation or normalization is applied.

Lossy formats such as MP3 must be re-encoded and therefore cannot be sample-identical to the source. Use WAV when validating editing quality or when you want a lossless intermediate.

## Stereo and multichannel policy

A section is considered quiet only when **all channels are quiet**. Activity on one channel protects that interval from removal.

## Large recordings

Recordings with many pauses can produce large FFmpeg filter graphs. Audio DeSilencer automatically moves large graphs into a temporary FFmpeg filter-script file instead of placing the entire graph on the operating-system command line. The temporary file is removed after rendering.

## Testing

```bash
python -m unittest discover -s tests -v
```

The regression suite covers fixed and adaptive detection, hysteresis, stereo safety, pause shortening, retained-sample identity, over-range float preservation, large edit lists, output naming, timelines, and CLI behavior. GitHub Actions runs Python 3.10, 3.11, 3.12, and 3.13 plus a packaging/install job.

## Scope / limitations

- Detection is deterministic signal analysis, not semantic voice-activity detection.
- Auto mode is deliberately conservative and may leave more silence rather than risk removing quiet speech.
- Very noisy or unusual recordings may still benefit from an explicit threshold.
- Audio DeSilencer does not normalize loudness or repair already-clipped source audio by design.
- FFmpeg codec support depends on the FFmpeg build installed on the host.

## License

MIT
