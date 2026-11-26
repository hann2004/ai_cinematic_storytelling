# Ethics, consent, and licensing

## People and consent

- The planned protagonist is fictional and is not intended to reproduce an identifiable person.
- The current plan uses generated narration, not a real person's recorded or cloned voice.
- A phone-call image must not reveal a real family member's face, name, or readable private information.
- No real-person likeness or voice has been included in the planned film so far.
- A user-supplied photo may be used privately in the Kaggle IP-Adapter workflow as broad visual guidance for a new fictional character. Only upload it if the user has permission to use it; do not copy the person's exact identity or distinctive likeness, and never commit the private reference photo or Hugging Face token to GitHub. Delete the private Kaggle dataset when it is no longer needed.
- If the film later uses any real person's recognizable face, likeness, or voice, pause and record that person's informed consent for this specific use before generating or publishing it.

## Model and output records

| Use | Model/provider | Current record | Follow-up |
|---|---|---|---|
| Smoke-test image only | Cloudflare Workers AI, `@cf/black-forest-labs/flux-1-schnell` | Generated image is in `outputs/smoke/`; it is not intended as a film shot. | Verify current model/output terms before using any production output publicly; record the source and licence. |
| Smoke-test narration only | Google Gemini TTS, `gemini-3.8-flash-tts`, preset voice `Kore` | A short synthetic Amharic sample is in `outputs/smoke/`; it is not a real person's voice. | Verify current API terms and language quality before production use. |
| Character reference workflow | Hugging Face Diffusers with SDXL and IP-Adapter in a private Kaggle notebook | Source notebook is `notebooks/character_reference.ipynb`; the IP-Adapter reference-guided output is not yet approved. | Confirm image-use permission, keep the input dataset private, review current model licences/terms, and record the selected output and parameters. |
| Production keyframes, motion, and music | Not selected/generated yet | No production shot output exists yet. | Record model version, licence/terms, output use, parameters, and attribution needs when selected. |

## Labelling and privacy

- Final film must have a visible end card stating it was made with AI.
- Enable the platform's AI-content disclosure when posting, where available.
- Keep provenance metadata or watermarks intact when present.
- Do not send private family details, contact information, or identifiable photographs to model providers without a clear need and consent.

This file is a current plan and record, not a claim that final model terms or participant consent have already been verified.