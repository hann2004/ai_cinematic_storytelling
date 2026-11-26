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
3. Enable Kaggle Internet and a GPU accelerator. This workflow uses the public,
   ungated [RealVisXL checkpoint](https://huggingface.co/SG161222/RealVisXL_V4.0)
   and [IP-Adapter](https://huggingface.co/h94/IP-Adapter), so no Hugging Face
   token is required for downloading them.
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

Kaggle GPU availability and free usage limits can change. This workflow uses
the current public repository `hann2004/ai_cinematic_storytelling`.

## First storyboard keyframe (Kaggle)

The earlier SDXL/IP-Adapter keyframe did not match the intended home-gate
composition. The user chose to return to a realistic live-action look and try
the public [RealVisXL SDXL checkpoint](https://huggingface.co/SG161222/RealVisXL_V4.0)
with the existing approved character reference. This model has not yet been
tested in this workflow; it may still produce artifacts or fail to follow the
composition. Both model repositories are public and ungated, so no Hugging Face
token is required. The shot prompt and visual direction are recorded in
`storyboard.json`. Use
[`notebooks/keyframes.ipynb`](notebooks/keyframes.ipynb) to generate only
`shot-01` in Kaggle with RealVisXL + IP-Adapter. The tracked implementation is
[`pipeline/kaggle_keyframes.py`](pipeline/kaggle_keyframes.py).

1. Commit and push the latest storyboard, schema, pipeline, and notebook files.
2. Import the latest notebook into Kaggle and enable Internet and a GPU.
3. Review the shot prompt in the notebook's source repository, then run its
   cells in order. The final launch cell makes one generation request for
   `shot-01`; rerunning it creates a separate output folder.
4. Review the image before approving it. The download ZIP contains the PNG,
   metadata JSON, and one-line JSONL model-call record. Add those to the
   project only if approved.

The selected narration remains unchanged. The bus departure is a silent shot,
and the nine storyboard holds total 90 seconds. Review the new model's result
after one attempt before deciding whether to continue.
