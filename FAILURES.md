# Failures and recoveries

## Provider smoke test

- **Gemini text (`gemini-3.8-flash`):** The request returned HTTP 503 (`UNAVAILABLE`) because the model was experiencing high demand. The failure is recorded in `runs.jsonl`. No retry has been made; retry later when capacity is available.
- **Cloudflare FLUX (`@cf/black-forest-labs/flux-1-schnell`):** The first request returned HTTP 400 because the live endpoint rejected the documented `seed` field (error 5006). Removed the field and reran only the image check; generation succeeded.
- **Gemini Amharic TTS (`gemini-3.8-flash-tts`):** A short test greeting and the full-script request both generated valid WAV files, but the filmmaker reports that the preset voice sounds unnatural in Amharic. The full narration succeeded with a warm, clear, unhurried style instruction; its measured duration is 114.32 seconds, above the 60–90 second film requirement. Review pronunciation and pacing, then shorten/revise the script before picture production. No model retry has been made.