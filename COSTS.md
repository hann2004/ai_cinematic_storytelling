# Measured costs and latency

Measurements are from this project’s recorded runs. Unknown prices are left unknown; check current provider billing/usage pages rather than assuming a request was free.

| Stage | Model/tool | Calls | Measured latency | Output / GPU time | Cost |
|---|---|---:|---:|---|---|
| Smoke-test text | Gemini `gemini-3.8-flash` | 1 | 16.66 s | Failed with HTTP 503; no output | Unknown |
| Smoke-test narration | Gemini `gemini-3.8-flash-tts` | 1 | 20.33 s | 2.52 s WAV; Amharic greeting | Unknown |
| Smoke-test image | Cloudflare `@cf/black-forest-labs/flux-1-schnell` | 3 attempts | 1.63 s, 1.29 s, 6.68 s | One 1024×1024 JPEG succeeded; earlier attempts failed | Unknown |
| Full narration | Gemini `gemini-3.8-flash-tts` | 1 | 165.61 s | 114.32 s WAV; local/GPU minutes: 0 | Unknown |

These are individual observed calls, not list-price estimates or a complete pipeline cost. No Wan video or ACE-Step music stage has run, so there are no GPU-minute measurements for those stages yet. The initial text response was HTTP 503; a retry attempt was interrupted and is not included as a verified result.