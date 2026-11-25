# Ethics, consent, and licensing

## People and consent

- The planned protagonist is fictional and is not intended to reproduce an identifiable person.
- The current plan uses generated narration, not a real person's recorded or cloned voice.
- A phone-call image must not reveal a real family member's face, name, or readable private information.
- No real-person likeness or voice has been included in the planned film so far.
- If the film later uses any real person's recognizable face, likeness, or voice, pause and record that person's informed consent for this specific use before generating or publishing it.

## Model and output records

| Use | Model/provider | Current record | Follow-up |
|---|---|---|---|
| Smoke-test image only | Cloudflare Workers AI, `@cf/black-forest-labs/flux-1-schnell` | Generated image is in `outputs/smoke/`; it is not intended as a film shot. | Verify current model/output terms before using any production output publicly; record the source and licence. |
| Smoke-test narration only | Google Gemini TTS, `gemini-3.8-flash-tts`, preset voice `Kore` | A short synthetic Amharic sample is in `outputs/smoke/`; it is not a real person's voice. | Verify current API terms and language quality before production use. |
| Production keyframes, motion, and music | Not selected/generated yet | No production output exists yet. | Record model version, licence/terms, output use, parameters, and attribution needs when selected. |

## Labelling and privacy

- Final film must have a visible end card stating it was made with AI.
- Enable the platform's AI-content disclosure when posting, where available.
- Keep provenance metadata or watermarks intact when present.
- Do not send private family details, contact information, or identifiable photographs to model providers without a clear need and consent.

This file is a current plan and record, not a claim that final model terms or participant consent have already been verified.