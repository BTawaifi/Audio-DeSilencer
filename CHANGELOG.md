# Changelog

All notable user-facing changes to Audio DeSilencer are documented here.

## 1.1.0

### Changed

- Replaced speech-chunk reconstruction with a non-destructive FFmpeg edit-list renderer.
- Silence removal now shortens only the middle of accepted pauses and preserves a configurable amount of natural pause.
- WAV output uses 32-bit floating-point PCM so over-range decoded samples are not forced through an integer PCM ceiling.
- CLI defaults are now zero-config and speech-oriented: 700 ms minimum silence, deterministic `auto` threshold, 150 ms retained pause, 3 dB auto hysteresis, WAV output.
- The Python API still accepts explicit fixed thresholds such as `threshold=-38` when reproducibility is preferred over adaptive analysis.
- `silent_ranges` / `*_silent_parts.txt` now mean ranges actually removed from the source.
- `*_silent.wav` is explicitly an inspection artifact made from removed source ranges.
- Removed pydub/audioop runtime dependencies; FFmpeg and FFprobe are explicit external requirements.

### Added

- `--target_silence_len`.
- Deterministic `--threshold auto` mode with conservative peak-window analysis.
- Optional `--hysteresis_db` for stable threshold transitions; auto mode defaults to 3 dB.
- `ProcessingResult.resolved_threshold_dbfs` and `ProcessingResult.detector`.
- Conservative stereo/multichannel behavior: activity on any channel protects the interval.
- Automatic FFmpeg filter-script fallback for recordings with very large edit graphs.
- Regression coverage for retained-sample identity, float over-range preservation, adaptive thresholding, hysteresis, multichannel safety, large edit lists, and zero-config CLI defaults.
- FFmpeg installation and tuning guidance in the README.

### Compatibility

- Numeric thresholds without hysteresis keep the stable FFmpeg `silencedetect` path.
- `split_audio_by_silence()` remains available for callers that need non-silent source ranges.

## 1.0.3

- Hardened range normalization, timeline handling, packaging, CLI error behavior, and Python 3.13 compatibility.
