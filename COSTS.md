# Measured costs and latency

Measurements are from this project’s recorded runs. Unknown prices are left unknown; check current provider billing/usage pages rather than assuming a request was free.

| Stage | Model/tool | Calls | Measured latency | Output / GPU time | Cost |
|---|---|---:|---:|---|---|
| Smoke-test text | Gemini `gemini-3.8-flash` | 1 | 16.66 s | Failed with HTTP 503; no output | Unknown |
| Smoke-test narration | Gemini `gemini-3.8-flash-tts` | 1 | 20.33 s | 2.52 s WAV; Amharic greeting | Unknown |
| Smoke-test image | Cloudflare `@cf/black-forest-labs/flux-1-schnell` | 3 attempts | 1.63 s, 1.29 s, 6.68 s | One 1024×1024 JPEG succeeded; earlier attempts failed | Unknown |
| Text-only character-reference attempts, rejected | Cloudflare `@cf/black-forest-labs/flux-1-schnell` | 7 (6 succeeded, 1 failed) | 9.07 s, 11.28 s, 19.65 s, 27.23 s, 4.83 s, 4.68 s, 6.64 s | Generated image(s) did not meet the visual goal; one request failed at the 2,048-character prompt limit | Unknown |
| Full narration | Gemini `gemini-3.8-flash-tts` | 1 | 165.61 s | 114.32 s WAV; local/GPU minutes: 0 | Unknown |
| Revised full narration, selected | Gemini `gemini-3.8-flash-tts`, preset `Leda` | 1 | 115.63 s | 72.46 s WAV at `outputs/narration_am_v2.wav`; filmmaker preferred its smoother voice | Unknown |
| Audience-wording narration, not selected | Gemini `gemini-3.8-flash-tts`, preset `Leda` | 1 | 26.35 s | 70.15 s WAV at `outputs/narration_am_v3.wav`; filmmaker preferred v2's voice | Unknown |
| Repeated audience-wording narration, not selected | Gemini `gemini-3.8-flash-tts`, preset `Leda` | 1 | 29.61 s | 69.34 s WAV at `outputs/narration_am_v4.wav`; filmmaker said it did not sound like v2 and selected v2 | Unknown |

These are individual observed calls, not list-price estimates or a complete pipeline cost. No Wan video, ACE-Step music, or IP-Adapter character-reference stage has run, so there are no GPU-minute measurements for those stages yet. The initial text response was HTTP 503; a retry attempt was interrupted and is not included as a verified result.

The selected audio is `outputs/narration_am_v2.wav`. The filmmaker preferred its smoother delivery over v3 and v4. The storyboard narration has been restored to the exact text hash logged for v2 so the selected text and audio match. Audience-suggested alternate wording was considered but not retained in the selected script.