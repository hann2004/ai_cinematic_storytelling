# Experiments

## 1. Cloudflare FLUX seed support

- **Hypothesis:** The FLUX REST endpoint accepts a fixed `seed` parameter, as shown in the model documentation example.
- **Change:** Sent one image request with `seed: 42`, then removed the field after the API rejected it.
- **Result:** The live endpoint returned error 5006 (`Additional or unevaluated properties '/seed' ... not allowed`). A request without `seed` succeeded and generated `outputs/smoke/flux_schnell.jpg`.
- **Decision:** Omit the seed for this endpoint unless its live schema later confirms support.

## 2. Amharic narration length and voice iteration

- **Hypothesis:** A shorter filmmaker-approved Amharic script and a different preset with feminine, youthful delivery guidance may better fit the film and sound more suitable to its student protagonist.
- **Change:** Replaced the earlier narration with the filmmaker's new Amharic script, changed the TTS preset from Kore to Leda, and requested natural feminine/youthful delivery. Kept the earlier audio and saved this take separately.
- **Result:** V2 measures 72.46 seconds, within the 60–90 second target, and the filmmaker preferred its smoother sound. V3 (70.15 seconds) and v4 (69.34 seconds) used the same Leda voice and style settings with two audience-suggested wording changes. The filmmaker said these did not sound like v2 and preferred v2.
- **Decision:** Use `outputs/narration_am_v2.wav` for the radio cut and restore its exact Amharic text in `storyboard.json`. The generated takes differ in perceived smoothness despite identical configured voice/style; exact voice quality is not guaranteed between generations.

## 3. Radio-cut placeholder bed

- **Hypothesis:** A very quiet temporary bed under narration can help audience listeners imagine the eventual score without distracting from the story.
- **Change:** Mixed the narration with a low-volume synthesized three-note tone bed over a black screen using FFmpeg; the bed is explicitly a placeholder, not the final score.
- **Result:** `outputs/radio_cut.mp4` rendered as H.264/AAC at 1280×720 and 24 fps, with a 72.50-second container duration.
- **Decision:** Use this only to test story and pacing. Replace the placeholder with the selected original score during final assembly.

## 4. Character-reference image workflow

- **Hypothesis:** A text-only image prompt is insufficient to guide the character toward a user-supplied visual reference; an image-reference adapter should provide stronger broad visual guidance.
- **Change:** Tried Cloudflare FLUX using text-only prompts. The generated composite-style reference was rejected by the filmmaker. One later request failed because the prompt exceeded Cloudflare's 2,048-character limit. Replaced that workflow with the GitHub-tracked `notebooks/character_reference.ipynb`, which uses SDXL with IP-Adapter in a private Kaggle notebook and accepts a reference image.
- **Result:** The text-only images did not meet the filmmaker's visual goal. The first Kaggle IP-Adapter output did not wear a hijab. A later output wore the black hijab and abaya but included makeup, which the filmmaker did not want.
- **Keyframe result:** `shot-01.png` showed a close-up of the protagonist alone instead of the family farewell. The shot prompt requested the family, but the negative prompt also prohibited an "extra person"; the image adapter preserved the portrait-like crop of the reference.
- **Decision:** The filmmaker selected a polished 3D animated style after rejecting the first keyframe. The script now requests a stylized animated frame, gives shot composition precedence over the portrait reference, lowers IP-Adapter strength to 0.25, and removes the contradictory "extra person" negative for the family scene. The revised approach is untested; generate one frame and review before continuing. Keep the notebook and scripts in GitHub as the code source of truth, and keep the original private reference photo in Kaggle only.