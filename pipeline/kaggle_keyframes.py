import argparse
import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import torch
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.kaggle_character_reference import (  # noqa: E402
    ADAPTER_REPO,
    DEFAULT_SEED,
    GUIDANCE_SCALE,
    INFERENCE_STEPS,
    MODEL_ID,
    package_versions,
    generate_image,
)
from pipeline.logger import RUNS_FILE, timed_call  # noqa: E402

STORYBOARD_PATH = REPO_ROOT / "storyboard.json"
SCHEMA_PATH = REPO_ROOT / "schema" / "storyboard.schema.json"
WIDTH = 1024
HEIGHT = 576
ADAPTER_SCALE = 0.25
NEGATIVE_PROMPT = (
    "collage, diptych, split screen, cloned identity, repeated identical face, "
    "giant face, face inset, cropped head, deformed face, deformed hands, extra fingers, "
    "blurry face, 3D render, CGI, illustration, anime, text, logo, watermark"
)
SHOT_NEGATIVE_PROMPTS = {
    "shot-01": (
        "portrait, headshot, close-up, close-up face, solo woman, isolated subject, "
        "empty background, cropped body, giant face, rural village, countryside, "
        "mud hut, thatched hut, shanty, visibly impoverished home, luxury mansion"
    )
}


def load_shot(shot_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    storyboard = json.loads(STORYBOARD_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(storyboard, schema)

    shot = next((item for item in storyboard["shots"] if item["id"] == shot_id), None)
    if shot is None:
        raise ValueError(f"Unknown shot ID: {shot_id}")
    if not shot["reference_images"]:
        raise ValueError(f"{shot_id} has no approved character reference image.")

    reference_paths = []
    for relative_path in shot["reference_images"]:
        path = (REPO_ROOT / relative_path).resolve()
        if not path.is_relative_to(REPO_ROOT):
            raise ValueError(f"Reference image path must stay inside the repository: {relative_path}")
        if not path.is_file():
            raise FileNotFoundError(f"Reference image not found: {relative_path}")
        reference_paths.append(path)

    shot_composition = ""
    negative_prompt = NEGATIVE_PROMPT
    if shot_id == "shot-01":
        shot_composition = (
            "WIDE 16:9 ESTABLISHING SHOT, not a portrait: show the protagonist and "
            "her family together as a group, full figures visible at an "
            "ordinary, well-kept middle-income Ethiopian city-home gate. Show a "
            "paved urban street, modest plaster-and-concrete residence, simple "
            "metal gate, and tidy lived-in yard. The people and gate should fill "
            "the frame; the protagonist is the clear main character in the group, "
            "not a giant face. Her black hijab, black abaya, suitcase, and laptop "
            "tote must be plainly visible. "
        )
        negative_prompt = f"{negative_prompt}, {SHOT_NEGATIVE_PROMPTS[shot_id]}"

    prompt = (
        "Create a cinematic photorealistic live-action film still with natural "
        "human features, realistic textures, and believable lighting. "
        f"{shot_composition}"
        f"{shot['image_prompt']} "
        f"{storyboard['character']['description']} "
        f"{storyboard['style_block']} "
        "Use the supplied approved character reference to keep the protagonist "
        "visually consistent, while preserving the described scene, framing, "
        "clothing, expression, and setting. Make the scene composition more "
        "important than matching the reference photo's original crop. One coherent "
        "photorealistic frame; no text or logos."
    )
    return (
        {
            "shot": shot,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "reference_paths": reference_paths,
        },
        storyboard,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate one storyboard keyframe using its approved character reference."
    )
    parser.add_argument("--shot-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    arguments = parser.parse_args()

    if not torch.cuda.is_available():
        parser.error("A CUDA GPU is required; select a Kaggle GPU accelerator.")

    try:
        shot_data, _ = load_shot(arguments.shot_id)
        if len(shot_data["reference_paths"]) != 1:
            raise ValueError(
                f"{arguments.shot_id} must have exactly one character reference image."
            )
        reference_image = Image.open(shot_data["reference_paths"][0]).convert("RGB")

        output_dir = arguments.output_dir
        image_path = output_dir / f"{arguments.shot_id}.png"
        metadata_path = output_dir / f"{arguments.shot_id}.json"
        run_record_path = output_dir / f"{arguments.shot_id}_run.jsonl"
        existing = [
            path
            for path in (image_path, metadata_path, run_record_path)
            if path.exists()
        ]
        if existing:
            raise FileExistsError(
                "Output already exists; choose a fresh output directory: "
                + ", ".join(str(path) for path in existing)
            )

        params: dict[str, Any] = {
            "shot_id": arguments.shot_id,
            "model": MODEL_ID,
            "adapter": ADAPTER_REPO,
            "reference_images": [
                path.relative_to(REPO_ROOT).as_posix()
                for path in shot_data["reference_paths"]
            ],
            "prompt": shot_data["prompt"],
            "negative_prompt": shot_data["negative_prompt"],
            "ip_adapter_scale": ADAPTER_SCALE,
            "width": WIDTH,
            "height": HEIGHT,
            "num_inference_steps": INFERENCE_STEPS,
            "guidance_scale": GUIDANCE_SCALE,
            "seed": arguments.seed,
            "output": image_path.name,
        }
        image = timed_call(
            "keyframe",
            f"{MODEL_ID}+{ADAPTER_REPO}",
            params,
            arguments.seed,
            None,
            generate_image,
            reference_image,
            shot_data["prompt"],
            shot_data["negative_prompt"],
            arguments.seed,
            width=WIDTH,
            height=HEIGHT,
            adapter_scale=ADAPTER_SCALE,
            note="Kaggle GPU time; monetary cost not estimated.",
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        image.save(image_path)
        run_line = RUNS_FILE.read_text(encoding="utf-8").splitlines()[-1]
        run_record_path.write_text(run_line + "\n", encoding="utf-8")
        metadata = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "stage": "keyframe",
            "shot_id": arguments.shot_id,
            "model": MODEL_ID,
            "adapter": ADAPTER_REPO,
            "parameters": params,
            "gpu": torch.cuda.get_device_name(0),
            "libraries": package_versions(),
            "output": image_path.name,
            "output_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        }
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (
        FileExistsError,
        FileNotFoundError,
        jsonschema.ValidationError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"Keyframe generation failed: {error}", file=sys.stderr)
        traceback.print_exc()
        return 1

    print(f"Saved keyframe: {image_path}")
    print(f"Saved metadata: {metadata_path}")
    print(f"Saved model-call log record: {run_record_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
