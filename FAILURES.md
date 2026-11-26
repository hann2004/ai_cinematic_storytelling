# Failures and recoveries

## Provider smoke test

- **Gemini text (`gemini-3.8-flash`):** The request returned HTTP 503 (`UNAVAILABLE`) because the model was experiencing high demand. The failure is recorded in `runs.jsonl`. No retry has been made; retry later when capacity is available.
- **Cloudflare FLUX (`@cf/black-forest-labs/flux-1-schnell`):** The first request returned HTTP 400 because the live endpoint rejected the documented `seed` field (error 5006). Removed the field and reran only the image check; generation succeeded.
- **Gemini Amharic TTS (`gemini-3.8-flash-tts`):** The first full narration using preset `Kore` measured 114.32 seconds, above the film limit, and the filmmaker disliked the voice. A shorter filmmaker-written script was generated with preset `Leda` and feminine/youthful delivery guidance: v2 measured 72.46 seconds and the filmmaker preferred its smoother voice. V3 and v4 used the same model, voice preset, and style text with the two suggested audience wording changes, but the filmmaker did not find them as smooth as v2 and preferred v2. The storyboard text has therefore been restored to match the selected v2 audio exactly. No further TTS calls are planned unless the filmmaker explicitly requests them.

## Character reference

- **Cloudflare FLUX text-only reference:** The generated image did not match the filmmaker's visual reference and was rejected. Cloudflare also rejected a later request with HTTP 400 because the prompt exceeded its 2,048-character limit. The problem was not solved by adding more prompt wording: this request path could not accept the reference photo at all.
- **Recovery:** Retired `pipeline.keyframes` for this task and added `notebooks/character_reference.ipynb` to the repository. It uses Diffusers IP-Adapter in Kaggle with a private reference image. The first Kaggle output did not wear the requested hijab. A later output wore the requested black hijab and abaya but included makeup, which the filmmaker did not want. The prompt now also asks for a bare face and excludes makeup; this adjustment is untested.