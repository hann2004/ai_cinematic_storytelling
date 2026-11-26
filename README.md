# AI Cinematic Storytelling

This repository is the source of truth for the short film's storyboard,
pipeline code, documentation, and Kaggle notebook source. Run GPU-dependent
image generation in Kaggle; keep private input photos and credentials out of
the repository.

## Character reference image (Kaggle)

The old `pipeline.keyframes` command used text-only Cloudflare FLUX, so it
could not use a supplied photo as visual guidance. Do not use it for the
character reference. Use [`notebooks/character_reference.ipynb`](notebooks/character_reference.ipynb).
The notebook clones this public repository and runs
[`pipeline/kaggle_character_reference.py`](pipeline/kaggle_character_reference.py),
so the generation logic and prompt are maintained in GitHub rather than copied
into an independent Kaggle script.

1. Commit and push the notebook and script to the public `main` branch before
   using Kaggle. Create a private Kaggle notebook and copy/import the tracked
   notebook there.
2. Attach the reference photo as a **private Kaggle dataset**. Do not add the
   photo to GitHub. It should guide broad visual qualities for a new fictional
   character, not reproduce the person's identity.
3. Enable Kaggle Internet and a GPU accelerator. If Hugging Face requires
   accepting model terms, accept them on its site and save a read-only token in
   Kaggle Secrets as `HF_TOKEN`. Never paste the token into code or Git.
4. Run the Kaggle notebook cells in order. The tracked Python script validates
   `storyboard.json`, generates one image, and logs the model call in
   `runs.jsonl` inside the Kaggle clone. It also creates a JSON metadata file
   and a downloadable one-line JSONL run record. It does not record the private
   image path or automatically retry.
5. Review the image. If approved, download the image, metadata, and run record.
   Copy the image and metadata into `outputs/` and append the run-record line to
   the existing `runs.jsonl`; do not replace the log. Update
   `storyboard.json` to point to the image only after approval.
6. If the assignment requires generated outputs in GitHub, commit only the
   approved deliverables. Never commit the private input photo, credentials, or
   Kaggle secrets. Check current model licences and usage terms before public
   release.

Kaggle GPU availability and free usage limits can change. The assignment
requires the public repository `hann2004/heritage-short`; rename this
workspace's existing GitHub repository before pushing the notebook and script.
