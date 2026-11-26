import argparse
import base64
import hashlib
import importlib.metadata
import io
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
from google import genai
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.logger import RUNS_FILE, timed_call  # noqa: E402

STORYBOARD_PATH = REPO_ROOT / "storyboard.json"
SCHEMA_PATH = REPO_ROOT / "schema" / "storyboard.schema.json"
MODEL_ID = "gemini-nano-banana-2.1"
NEGATIVE_PROMPT = (
    "collage, diptych, split screen, cloned identity, repeated identical face, "
    "giant face, face inset, cropped head, deformed face, deformed hands, extra fingers, "
    "blurry face, 3D render, CGI, illustration, anime, text, logo, watermark"
)
SHOT_NEGATIVE_PROMPTS = {
    "shot-01": (
        "portrait, headshot, close-up, close-up face, solo woman, isolated subject, "
        "empty background, cropped body, cropped legs, cropped feet, close framing, "
        "giant face, rural village, countryside, "
        "mud hut, thatched hut, shanty, visibly impoverished home, luxury mansion, "
        "children, toddlers, babies, schoolchildren, uncovered hair, bareheaded, "
        "missing hijab, white t-shirt"
    )
}


def generate_image(
    client: genai.Client,
    reference_image: Image.Image,
    prompt: str,
    negative_prompt: str,
) -> Image.Image:
    image_buffer = io.BytesIO()
    reference_image.save(image_buffer, format="PNG")
    image_data = base64.b64encode(image_buffer.getvalue()).decode("ascii")
    request_prompt = (
        f"{prompt}\nAvoid these elements: {negative_prompt}"
    )
    interaction = client.interactions.create(
        model=MODEL_ID,
        input=[
            {"type": "text", "text": request_prompt},
            {
                "type": "image",
                "data": image_data,
                "mime_type": "image/png",
            },
        ],
    )
    if not interaction.output_image or not interaction.output_image.data:
        raise RuntimeError(f"{MODEL_ID} returned no generated image.")
    generated_bytes = base64.b64decode(interaction.output_image.data, validate=True)
    with Image.open(io.BytesIO(generated_bytes)) as image:
        return image.convert("RGB")


def package_versions() -> dict[str, str]:
    names = ("google-genai", "jsonschema", "Pillow")
    return {name: importlib.metadata.version(name) for name in names}


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

    negative_prompt = NEGATIVE_PROMPT
    if shot_id == "shot-01":
        negative_prompt = f"{negative_prompt}, {SHOT_NEGATIVE_PROMPTS[shot_id]}"

    prompt = (
        "Create one photorealistic cinematic film still. Follow this shot "
        "description closely; prioritize the specified people, clothing, props, "
        "and setting. "
        f"{shot['image_prompt']} "
        "The attached image is the approved character reference for the "
        "protagonist. Preserve her recognizable face, black hijab, and modest "
        "black clothing while adapting her naturally to the requested full-body "
        "scene. Do not copy the portrait crop. No text or logos."
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
    arguments = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        parser.error("Set GEMINI_API_KEY using Kaggle Secrets before running this script.")
    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})

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
            "reference_method": "image input to Gemini",
            "reference_images": [
                path.relative_to(REPO_ROOT).as_posix()
                for path in shot_data["reference_paths"]
            ],
            "prompt": shot_data["prompt"],
            "negative_prompt": shot_data["negative_prompt"],
            "output": image_path.name,
        }
        image = timed_call(
            "keyframe",
            MODEL_ID,
            params,
            None,
            None,
            generate_image,
            client,
            reference_image,
            shot_data["prompt"],
            shot_data["negative_prompt"],
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
            "reference_method": "image input to Gemini",
            "parameters": params,
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
