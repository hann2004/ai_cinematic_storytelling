import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import torch
from PIL import Image
from diffusers import AutoPipelineForText2Image

from pipeline.logger import RUNS_FILE, timed_call

REPO_ROOT = Path(__file__).resolve().parents[1]
STORYBOARD_PATH = REPO_ROOT / "storyboard.json"
SCHEMA_PATH = REPO_ROOT / "schema" / "storyboard.schema.json"
MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
ADAPTER_REPO = "h94/IP-Adapter"
ADAPTER_FILE = "ip-adapter_sdxl.bin"
ADAPTER_SCALE = 0.45
WIDTH = 768
HEIGHT = 1024
INFERENCE_STEPS = 28
GUIDANCE_SCALE = 6.0
DEFAULT_SEED = 2026


def load_prompts() -> tuple[str, str]:
    storyboard = json.loads(STORYBOARD_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(storyboard, schema)

    character = storyboard["character"]["description"]
    prompt = (
        "One coherent photorealistic full-body character reference, one fictional "
        "person, standing naturally and visible head-to-toe, centered and occupying "
        "most of the image height, neutral simple background. "
        f"{character} "
        "Use the supplied image only for broad visual guidance; depict a different "
        "fictional individual, not the same person's face or identity. Bright "
        "flattering natural light, realistic skin texture, clear visible face, "
        "cinematic photography. No text or logos."
    )
    negative_prompt = (
        "collage, diptych, split screen, duplicate person, extra person, tiny "
        "duplicate, giant face, face inset, close-up portrait, cropped body, 3D "
        "render, CGI, illustration, anime, plastic skin, underexposed face, blurry "
        "face, deformed hands, extra fingers, text, logo, backpack"
    )
    return prompt, negative_prompt


def generate_image(
    reference_image: Image.Image,
    prompt: str,
    negative_prompt: str,
    hf_token: str,
    seed: int,
) -> Image.Image:
    pipe = AutoPipelineForText2Image.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        use_safetensors=True,
        token=hf_token,
    )
    pipe.load_ip_adapter(
        ADAPTER_REPO,
        subfolder="sdxl_models",
        weight_name=ADAPTER_FILE,
        token=hf_token,
    )
    pipe.set_ip_adapter_scale(ADAPTER_SCALE)
    pipe.enable_vae_slicing()
    pipe.enable_model_cpu_offload()

    result = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        ip_adapter_image=reference_image,
        width=WIDTH,
        height=HEIGHT,
        num_inference_steps=INFERENCE_STEPS,
        guidance_scale=GUIDANCE_SCALE,
        generator=torch.Generator(device="cpu").manual_seed(seed),
    )
    return result.images[0]


def package_versions() -> dict[str, str]:
    names = (
        "diffusers",
        "transformers",
        "accelerate",
        "safetensors",
        "jsonschema",
        "Pillow",
    )
    return {name: importlib.metadata.version(name) for name in names}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate one IP-Adapter character reference in a GPU notebook."
    )
    parser.add_argument("--reference-image", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing outputs and make a new generation.",
    )
    arguments = parser.parse_args()

    if not torch.cuda.is_available():
        parser.error("A CUDA GPU is required; select a Kaggle GPU accelerator.")
    if not arguments.reference_image.is_file():
        parser.error(f"Reference image does not exist: {arguments.reference_image}")

    output_dir = arguments.output_dir
    image_path = output_dir / "character_reference_ipadapter.png"
    metadata_path = output_dir / "character_reference_ipadapter.json"
    run_record_path = output_dir / "character_reference_run.jsonl"
    existing = [path for path in (image_path, metadata_path, run_record_path) if path.exists()]
    if existing and not arguments.force:
        parser.error(
            "Output already exists; review it or pass --force to replace it: "
            + ", ".join(str(path) for path in existing)
        )

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        parser.error("Set HF_TOKEN from Kaggle Secrets before running this script.")

    try:
        reference_image = Image.open(arguments.reference_image).convert("RGB")
        prompt, negative_prompt = load_prompts()
        params: dict[str, Any] = {
            "model": MODEL_ID,
            "adapter": ADAPTER_REPO,
            "reference_input": "private Kaggle dataset; path omitted",
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "ip_adapter_scale": ADAPTER_SCALE,
            "width": WIDTH,
            "height": HEIGHT,
            "num_inference_steps": INFERENCE_STEPS,
            "guidance_scale": GUIDANCE_SCALE,
            "seed": arguments.seed,
            "output": image_path.name,
        }
        image = timed_call(
            "character_reference",
            f"{MODEL_ID}+{ADAPTER_REPO}",
            params,
            arguments.seed,
            None,
            generate_image,
            reference_image,
            prompt,
            negative_prompt,
            hf_token,
            arguments.seed,
            note="Kaggle GPU time; monetary cost not estimated.",
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        image.save(image_path)
        run_line = RUNS_FILE.read_text(encoding="utf-8").splitlines()[-1]
        run_record_path.write_text(run_line + "\n", encoding="utf-8")
        metadata = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "stage": "character_reference",
            "model": MODEL_ID,
            "adapter": ADAPTER_REPO,
            "parameters": params,
            "gpu": torch.cuda.get_device_name(0),
            "libraries": package_versions(),
            "output": image_path.name,
            "output_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "private_reference_image_path_recorded": False,
        }
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (
        jsonschema.ValidationError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"Character reference generation failed: {error}", file=sys.stderr)
        return 1

    print(f"Saved image: {image_path}")
    print(f"Saved metadata: {metadata_path}")
    print(f"Saved model-call log record: {run_record_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
