# Audio DeSilencer

Audio DeSilencer is a small Python package and command-line tool for shortening long silent pauses **without processing the audio that is kept**.

The core rule is simple:

> If a source interval is retained, Audio DeSilencer does not normalize, limit, EQ, compress, de-ess, crossfade, or otherwise modify it. It only removes selected time ranges.

The tool is designed for speech recordings, meetings, voice notes, podcasts, screen recordings, interviews, lectures, and other audio where long pauses should be shortened while preserving the original signal.

## What it does

Audio DeSilencer:

- detects continuous quiet regions
- keeps a small amount of natural pause around speech
- removes only the middle of accepted silent regions
- leaves retained audio untouched
- writes a cleaned `*_non_silent.wav`
- optionally writes the removed material as `*_silent.wav` for inspection
- writes source-time timeline files showing exactly what was removed and retained
- supports fixed or automatic threshold detection
- handles mono, stereo, and multichannel audio conservatively
- uses FFmpeg for decoding, detection, trimming, and output

It deliberately does **not** perform mastering or restoration. There is no normalization, limiter, denoiser, EQ, compressor, de-esser, voice enhancement, or automatic loudness processing.

---

## Requirements

- Python 3.10 or newer
- Git
- FFmpeg and FFprobe available on `PATH`

No third-party Python runtime package is required by Audio DeSilencer itself.

### Install FFmpeg

#### Windows

```powershell
winget install Gyan.FFmpeg
```

Close and reopen PowerShell after installation if necessary, then verify:

```powershell
ffmpeg -version
ffprobe -version
```

#### macOS

```bash
brew install ffmpeg
```

Verify:

```bash
ffmpeg -version
ffprobe -version
```

#### Ubuntu / Debian

```bash
sudo apt update
sudo apt install ffmpeg
```

Verify:

```bash
ffmpeg -version
ffprobe -version
```

---

# Installation from source

The recommended installation method is to install directly from a checked-out copy of this repository.

## Windows

```powershell
git clone https://github.com/BTawaifi/Audio-DeSilencer.git
cd Audio-DeSilencer
py -m pip install --upgrade pip
py -m pip install .
```

Verify the installed command:

```powershell
audio-desilencer --help
where.exe audio-desilencer
```

## macOS / Linux

```bash
git clone https://github.com/BTawaifi/Audio-DeSilencer.git
cd Audio-DeSilencer
python3 -m pip install --upgrade pip
python3 -m pip install .
```

Verify:

```bash
audio-desilencer --help
which audio-desilencer
```

## Editable development install

If you are modifying the source code, install it in editable mode:

### Windows

```powershell
py -m pip install -e .
```

### macOS / Linux

```bash
python3 -m pip install -e .
```

With an editable install, changes in the repository are used without rebuilding and reinstalling the package each time.

---

# Updating an existing source installation

If you already cloned the repository:

## Windows

```powershell
cd D:\path\to\Audio-DeSilencer
git pull
py -m pip install --force-reinstall .
```

## macOS / Linux

```bash
cd /path/to/Audio-DeSilencer
git pull
python3 -m pip install --force-reinstall .
```

If the CLI still looks old after reinstalling, see [Troubleshooting](#troubleshooting).

---

# Quick start

For normal speech recordings, the CLI has useful zero-configuration defaults.

```powershell
audio-desilencer "C:\Users\User\Documents\Sound recordings\Recording (2).m4a"
```

or on macOS/Linux:

```bash
audio-desilencer "recording.m4a"
```

The default CLI behavior is:

```text
threshold mode:              auto
minimum continuous silence: 700 ms
silence retained per pause:  150 ms
auto hysteresis:               3 dB
output format:                WAV
output folder:                output
```

In most voice-recording cases, you should start with **no tuning flags at all**.

---

# Output files

For an input named:

```text
recording.m4a
```

the default output folder contains:

```text
output/
├── recording_non_silent.wav
├── recording_silent.wav
├── recording_non_silent_parts.txt
└── recording_silent_parts.txt
```

## `*_non_silent.wav`

This is the main result: the original recording with accepted long pauses shortened.

It still contains the small amount of pause requested by `--target_silence_len` so speech does not get slammed directly together.

## `*_silent.wav`

This is an **inspection artifact** containing the source ranges that were removed, concatenated together.

It is not intended to sound like a normal continuous recording. Its purpose is to let you inspect what the tool removed.

## `*_silent_parts.txt`

Contains the source-time ranges actually removed.

Example:

```text
[(9824, 10599), (19576, 20330)]
```

All values are milliseconds in the original source timeline.

## `*_non_silent_parts.txt`

Contains the source-time ranges retained in the cleaned output.

---

# CLI reference

```text
audio-desilencer INPUT_FILE [options]
```

Show all options:

```bash
audio-desilencer --help
```

## `input_file`

Required path to the source audio file.

Examples:

```powershell
audio-desilencer "voice.m4a"
audio-desilencer "C:\Recordings\meeting.ogg"
```

FFmpeg determines which formats are supported by your local installation. Common formats such as WAV, M4A/AAC, MP3, OGG/Opus, FLAC, and many others are generally supported by standard FFmpeg builds.

## `--output_folder`

Folder where generated files are written.

Default:

```text
output
```

Example:

```powershell
audio-desilencer "voice.m4a" --output_folder "D:\Processed Audio"
```

## `--threshold`

Controls what level is considered quiet.

CLI default:

```text
auto
```

### Automatic threshold

```bash
audio-desilencer input.m4a --threshold auto
```

Auto mode is deterministic signal analysis. It does **not** use AI, a trained model, cloud service, internet connection, or external dataset.

It examines short peak-level windows and estimates a conservative threshold from the quieter part of the recording.

Important safety behavior:

- a loud sample makes the window active
- activity on any channel protects the interval
- auto mode does not choose a threshold more aggressive than the built-in `-38 dBFS` safety ceiling
- auto mode uses exit hysteresis by default

### Fixed threshold

Use a numeric dBFS value when you want explicit, reproducible detection:

```bash
audio-desilencer input.m4a --threshold -38
```

A more negative value is **more conservative** and classifies less material as silence:

```text
-42 dBFS -> safer for quiet speech
-38 dBFS -> practical fixed speech starting point
-32 dBFS -> more aggressive; use carefully
```

## `--min_silence_len`

Minimum continuous quiet duration required before a region can be considered silence.

Default:

```text
700 ms
```

Example:

```bash
audio-desilencer input.m4a --min_silence_len 1000
```

Higher values remove only longer pauses. Lower values make the tool more aggressive.

Recommended speech range:

```text
500-1000 ms
```

## `--target_silence_len`

How much total pause remains after an accepted long silence is shortened.

Default:

```text
150 ms
```

Examples:

```bash
# Tighter pacing
audio-desilencer input.m4a --target_silence_len 50

# Default natural speech pacing
audio-desilencer input.m4a --target_silence_len 150

# Preserve more breathing room
audio-desilencer input.m4a --target_silence_len 250

# Remove accepted silence completely
audio-desilencer input.m4a --target_silence_len 0
```

For normal speech, `100-200 ms` is usually a good range.

## `--hysteresis_db`

Optional difference between entering and leaving the silence state.

Auto mode uses `3 dB` by default.

For a fixed threshold:

```bash
audio-desilencer input.m4a --threshold -38 --hysteresis_db 3
```

Hysteresis helps prevent rapid switching when the signal hovers near the threshold.

If you use a numeric threshold without `--hysteresis_db`, the tool keeps the direct FFmpeg fixed-threshold detector path.

## `--output_format`

Output audio format.

Default:

```text
wav
```

Example:

```bash
audio-desilencer input.m4a --output_format mp3
```

WAV is recommended when quality and validation matter because the tool writes 32-bit floating-point PCM. Lossy formats such as MP3 must be re-encoded and therefore cannot be sample-identical to the decoded source.

## `--output_stem`

Override the base filename used for generated outputs.

Example:

```bash
audio-desilencer interview.m4a --output_stem cleaned_interview
```

Produces names such as:

```text
cleaned_interview_non_silent.wav
cleaned_interview_silent.wav
```

---

# Recommended settings

## Normal speech / voice notes

Use the defaults:

```bash
audio-desilencer input.m4a
```

Equivalent conceptually to:

```text
threshold:          auto
min silence:        700 ms
target pause:       150 ms
auto hysteresis:      3 dB
```

## Quiet speaker or soft consonants

Prefer auto first. If you need a fixed threshold, use a more negative value:

```bash
audio-desilencer input.m4a --threshold -42
```

## Too much silence remains

First reduce the retained pause:

```bash
audio-desilencer input.m4a --target_silence_len 80
```

If long pauses are still not detected, lower the required duration:

```bash
audio-desilencer input.m4a --min_silence_len 500
```

With a fixed threshold, you can cautiously make the threshold less negative:

```bash
audio-desilencer input.m4a --threshold -35
```

Do this carefully because aggressive thresholds can classify quiet speech as silence.

## Speech is being cut

Make detection more conservative:

```bash
audio-desilencer input.m4a --threshold -42 --min_silence_len 800
```

Or return to auto mode:

```bash
audio-desilencer input.m4a --threshold auto
```

You can also preserve more pause:

```bash
audio-desilencer input.m4a --target_silence_len 250
```

## Long-form lecture / meeting

A conservative example:

```bash
audio-desilencer meeting.m4a \
  --threshold auto \
  --min_silence_len 900 \
  --target_silence_len 180
```

PowerShell equivalent:

```powershell
audio-desilencer "meeting.m4a" `
  --threshold auto `
  --min_silence_len 900 `
  --target_silence_len 180
```

---

# How detection works

Audio DeSilencer has two deterministic detection paths.

## Auto detector

Auto mode:

1. decodes the audio through FFmpeg into floating-point samples for analysis
2. measures short peak-level windows
3. estimates the low-level/noise portion of the recording
4. chooses a conservative silence threshold
5. uses hysteresis so the detector does not rapidly switch state around the threshold
6. requires continuous quiet for at least `--min_silence_len`

The detector is intentionally conservative. If uncertain, it should leave silence rather than remove possible speech.

## Fixed detector

A numeric threshold without hysteresis uses FFmpeg's `silencedetect` path directly.

Example:

```bash
audio-desilencer input.m4a --threshold -38
```

This is useful when you need repeatable behavior with an explicitly chosen threshold.

---

# How editing works

The tool does not reconstruct speech from arbitrary fragments.

Instead:

```text
source recording
      |
      v
detect confirmed long quiet region
      |
      v
keep a small pause next to speech
      |
      v
remove only the middle of that quiet region
      |
      v
concatenate retained source-time spans
```

For example, if a detected pause is 1.5 seconds and the target pause is 150 ms, the tool removes the middle portion and leaves approximately 75 ms on each side of the cut.

This keeps edits inside quiet material rather than directly on speech boundaries.

---

# Signal-preservation design

Audio DeSilencer treats silence removal as an **editing** problem, not a mastering problem.

The rendering graph uses timing operations only:

```text
atrim -> timestamp reset -> concat
```

Retained audio is not intentionally subjected to:

- normalization
- limiting
- gain changes
- compression
- EQ
- high-pass filtering
- de-essing
- denoising
- crossfades
- voice enhancement

For WAV output, 32-bit floating-point PCM is used so over-range floating-point decoded samples are not unnecessarily forced through an integer PCM ceiling.

Lossy output formats still require codec re-encoding, so use WAV when checking waveform integrity or when you want a lossless intermediate.

---

# Stereo and multichannel audio

Detection is conservative across channels.

A window is considered quiet only when **all channels are quiet**. If one channel contains activity, the interval is protected.

This avoids deleting useful material from stereo recordings where speech or another important signal exists primarily on one side.

---

# Large recordings

Very long recordings or recordings with many pauses can create large FFmpeg filter graphs.

Audio DeSilencer automatically switches large graphs to a temporary FFmpeg filter-script file instead of putting the entire graph on the command line. This also avoids operating-system command-length problems, especially on Windows.

The temporary filter script is deleted after rendering.

---

# Python API

```python
from audio_desilencer import AudioProcessor

processor = AudioProcessor("input.m4a")

result = processor.process_audio(
    threshold="auto",
    min_silence_len=700,
    target_silence_len=150,
    output_folder="output",
    output_format="wav",
)

print(result.non_silent_audio_path)
print(result.silent_audio_path)
print(result.detected_silence_ranges)
print(result.silent_ranges)
print(result.non_silent_ranges)
print(result.resolved_threshold_dbfs)
print(result.detector)
```

## Important API default difference

The CLI defaults to `threshold="auto"` for convenient speech processing.

The lower-level Python `AudioProcessor.process_audio()` API keeps its fixed numeric threshold default for compatibility with existing callers. If you want the same adaptive behavior as the CLI, pass:

```python
threshold="auto"
```

## Detect silence without rendering output

```python
silent_ranges = processor.detect_silence_ranges(
    min_silence_len=700,
    threshold="auto",
)
```

## Fixed threshold detection

```python
silent_ranges = processor.detect_silence_ranges(
    min_silence_len=700,
    threshold=-38,
)
```

## Get non-silent source ranges

The compatibility API remains available:

```python
non_silent_ranges = processor.split_audio_by_silence(
    min_silence_len=700,
    threshold=-38,
)
```

## Processing result fields

`ProcessingResult` exposes:

```text
silent_audio_path
non_silent_audio_path
silent_timeline_path
non_silent_timeline_path
silent_ranges
non_silent_ranges
detected_silence_ranges
resolved_threshold_dbfs
detector
```

`silent_ranges` means **ranges actually removed**, not every region that was initially detected as low-energy.

---

# Building the package locally

Use these steps when you want a wheel/source distribution instead of installing directly from the checkout.

## Windows

From the repository root:

```powershell
py -m pip install --upgrade build
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
py -m build
```

Generated files appear in:

```text
dist/
```

Typically:

```text
audio_desilencer-1.1.0-py3-none-any.whl
audio_desilencer-1.1.0.tar.gz
```

Install the locally built wheel:

```powershell
py -m pip install --force-reinstall .\dist\audio_desilencer-1.1.0-py3-none-any.whl
```

Or when only one wheel exists:

```powershell
py -m pip install --force-reinstall .\dist\*.whl
```

## macOS / Linux

```bash
python3 -m pip install --upgrade build
rm -rf dist
python3 -m build
python3 -m pip install --force-reinstall dist/*.whl
```

## Verify a built installation

```bash
audio-desilencer --help
```

Windows:

```powershell
py -m pip show Audio-DeSilencer
where.exe audio-desilencer
```

macOS/Linux:

```bash
python3 -m pip show Audio-DeSilencer
which audio-desilencer
```

---

# Running the test suite

FFmpeg and FFprobe must be available before running tests.

From the repository root:

```bash
python -m unittest discover -s tests -v
```

On Windows you can use:

```powershell
py -m unittest discover -s tests -v
```

The regression suite covers areas including:

- leading, internal, and trailing silence
- fully silent and fully active files
- middle-of-pause removal
- automatic threshold estimation
- fixed threshold detection
- hysteresis behavior
- multichannel safety
- retained decoded PCM preservation
- floating-point over-range preservation
- large edit graphs
- output naming and path containment
- timeline semantics
- CLI success and error handling

GitHub Actions runs tests across supported Python versions and separately validates the built package.

---

# Development workflow

A typical local development setup:

```powershell
git clone https://github.com/BTawaifi/Audio-DeSilencer.git
cd Audio-DeSilencer
py -m pip install -e .
py -m unittest discover -s tests -v
```

After making code changes, rerun the test suite before building a wheel.

To inspect the CLI from the current editable checkout:

```powershell
audio-desilencer --help
```

---

# Troubleshooting

## `--threshold auto` is rejected as an integer

If you see an error similar to:

```text
argument --threshold: invalid int value: 'auto'
```

your shell is running an older installed CLI.

Update the repository and reinstall from source:

```powershell
git pull
py -m pip uninstall Audio-DeSilencer -y
py -m pip install --force-reinstall .
```

Then inspect which executable is being used:

```powershell
where.exe audio-desilencer
```

Verify the help now includes:

```text
--threshold
--hysteresis_db
--target_silence_len
```

## `audio-desilencer` command is not found

First verify the package is installed:

```powershell
py -m pip show Audio-DeSilencer
```

Then inspect your Python Scripts directory and `PATH`.

On Windows, `where.exe audio-desilencer` is useful once the command is discoverable.

## FFmpeg or FFprobe is not found

Verify:

```bash
ffmpeg -version
ffprobe -version
```

If those commands fail, install FFmpeg and reopen your shell so the updated `PATH` is loaded.

## The tool removes too much speech

Use a more conservative fixed threshold and/or longer minimum silence:

```bash
audio-desilencer input.m4a --threshold -42 --min_silence_len 900
```

You can also keep more natural pause:

```bash
audio-desilencer input.m4a --target_silence_len 250
```

## The tool removes too little silence

Try a shorter target pause first:

```bash
audio-desilencer input.m4a --target_silence_len 80
```

Then, if needed, reduce minimum silence duration:

```bash
audio-desilencer input.m4a --min_silence_len 500
```

For fixed detection, cautiously use a less-negative threshold:

```bash
audio-desilencer input.m4a --threshold -35
```

## Output sounds different when using MP3

MP3 is lossy and must be encoded again after editing.

Use WAV when validating signal preservation:

```bash
audio-desilencer input.m4a --output_format wav
```

## `_silent.wav` sounds strange

That file contains removed ranges concatenated together. It is only an inspection artifact.

Listen to `*_non_silent.wav` to judge the cleaned recording.

## Very long command / many pauses

The tool automatically uses an FFmpeg filter-script file when the edit graph is large, so normal use should not require any manual workaround.

---

# Architecture

```text
CLI / Python caller
        |
        v
AudioProcessor
├── ffprobe source metadata
├── deterministic auto analysis
│      OR fixed FFmpeg silence detection
├── normalize detected silence ranges
├── shorten only accepted silence interiors
├── compute retained source ranges
├── FFmpeg trim + concatenate retained spans
├── export removed spans for inspection
└── write source-time timelines
```

The detector decides **where editing is safe**. The renderer does not try to hide detector mistakes by processing the voice.

---

# Scope and limitations

- Detection is deterministic signal analysis, not semantic speech recognition.
- No ML/VAD model, training data, cloud API, or internet service is required.
- Auto mode is deliberately conservative and may leave extra silence rather than risk deleting quiet speech.
- Extremely noisy recordings may still need a manually chosen threshold.
- The tool does not repair clipping already present in the source.
- The tool does not normalize loudness.
- Codec support depends on the FFmpeg build installed on the host.
- Lossy output formats cannot be sample-identical to the source because they must be re-encoded.

---

# Uninstall

## Windows

```powershell
py -m pip uninstall Audio-DeSilencer
```

## macOS / Linux

```bash
python3 -m pip uninstall Audio-DeSilencer
```

---

# License

MIT
