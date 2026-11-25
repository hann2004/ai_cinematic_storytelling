import argparse
import base64
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from jsonschema import Draft202012Validator

from pipeline.logger import timed_call

REPO_ROOT = Path(__file__).resolve().parents[1]
STORYBOARD_PATH = REPO_ROOT / "storyboard.json"
SCHEMA_PATH = REPO_ROOT / "schema" / "storyboard.schema.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "outputs" / "narration_am.wav"
MODEL = "gemini-3.8-flash-tts"
VOICE = "Leda"
STYLE = (
    "A youthful young-adult woman speaking fluent Amharic in a natural, "
    "conversational, warm, sincere way. Use clear Amharic pronunciation "
    "and natural rhythm, with a gentle unhurried pace. Read the supplied "
    "text exactly as written; do not translate, paraphrase, or add words."
)


def load_narration() -> tuple[list[dict[str, str]], str, str]:
    storyboard_bytes = STORYBOARD_PATH.read_bytes()
    storyboard = json.loads(storyboard_bytes)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(storyboard)

    shot_lines = [
        {"id": shot["id"], "text": shot["narration_am"]}
        for shot in storyboard["shots"]
    ]
    narration = "\n\n".join(line["text"] for line in shot_lines)
    if not narration.strip():
        raise ValueError("The storyboard contains no Amharic narration.")

    return (
        shot_lines,
        narration,
        hashlib.sha256(storyboard_bytes).hexdigest(),
    )


def generate_narration(output_path: Path, force: bool) -> None:
    if output_path.exists() and not force:
        raise FileExistsError(
            f"{output_path} already exists. Review it first, or pass --force "
            "to make another billable model request."
        )

    load_dotenv(REPO_ROOT / ".env")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from the environment or .env.")

    shot_lines, narration, storyboard_sha256 = load_narration()
    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1beta"},
    )

    def request_audio() -> bytes:
        interaction = client.interactions.create(
            model=MODEL,
            input=[
                {
                    "type": "user_input",
                    "content": [
                        {
                            "type": "text",
                            "text": narration,
                            "annotations": [
                                {
                                    "type": "speech_metadata",
                                    "style": STYLE,
                                }
                            ],
                        }
                    ],
                }
            ],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": VOICE}]},
        )
        audio_data = interaction.output_audio.data if interaction.output_audio else None
        if not audio_data:
            raise RuntimeError("Gemini returned no narration audio.")
        return base64.b64decode(audio_data, validate=True)

    audio_bytes = timed_call(
        stage="narration",
        model=MODEL,
        params={
            "language": "Amharic",
            "voice": VOICE,
            "style": STYLE,
            "shot_ids": [line["id"] for line in shot_lines],
            "text_characters": len(narration),
            "text_sha256": hashlib.sha256(narration.encode("utf-8")).hexdigest(),
            "storyboard_sha256": storyboard_sha256,
            "output": str(output_path.relative_to(REPO_ROOT)),
        },
        seed=None,
        cost_estimate=None,
        function=request_audio,
        note="One full-script request; cost unknown, check provider usage.",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio_bytes)
    print(f"Saved Amharic narration to {output_path.relative_to(REPO_ROOT)}")
    print(
        "Each shot's narration was included in order in one model request. "
        "Check the audio duration and listen for pronunciation/pacing."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the storyboard's Amharic narration as one WAV file."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output WAV path (default: outputs/narration_am.wav).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing output by making a new model request.",
    )
    arguments = parser.parse_args()
    output_path = arguments.output
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path = output_path.resolve()

    try:
        output_path.relative_to(REPO_ROOT)
    except ValueError as error:
        raise ValueError("Output must be inside the repository.") from error

    generate_narration(output_path, arguments.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
