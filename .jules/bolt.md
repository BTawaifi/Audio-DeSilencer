
## AudioSegment Concatenation Optimization (2025-05-15)
- **Problem**: Using `+=` in a loop to concatenate `AudioSegment` objects in `audio_processor.py`.
- **Inefficiency**: `AudioSegment` is immutable, so each addition creates a new object and copies all audio data. This resulted in $O(N^2)$ complexity relative to the number of segments.
- **Solution**: Collected segments into a list and concatenated them using `b"".join(s.raw_data for s in segments)` followed by `self.audio._spawn(...)`.
- **Impact**: Changed $O(N^2)$ data copying to $O(N)$. Mock-based benchmarks showed a >99% improvement for 10,000 segments.
- **Learning**: For bulk concatenation of segments with matching parameters (e.g., slices from the same source), raw data joining is significantly faster than `sum()` or `+=`.
