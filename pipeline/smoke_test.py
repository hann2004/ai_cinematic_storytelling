import argparse
import base64
import os
import sys
from pathlib import Path
from typing import Callable

import requests
from dotenv import load_dotenv
from google import genai

from pipeline.logger import timed_call

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "outputs" / "smoke"
GEMINI_TEXT_MODEL = "gemini-3.8-flash"
GEMINI_TTS_MODEL = "gemini-3.8-flash-tts"
CLOUDFLARE_IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"
AMHARIC_SAMPLE = "ሰላም፣ ዛሬ እንዴት ነዎት?"


def run_step(name: str, action: Callable[[], None]) -> bool:
    try:
        action()
    except Exception as error:
        print(f"{name} failed ({type(error).__name__}): {error}", file=sys.stderr)
        return False

    print(f"{name} succeeded")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the configured model providers.")
    parser.add_argument(
        "--only",
        choices=("gemini-text", "gemini-tts", "cloudflare-image"),
        help="Run only one provider check.",
    )
    arguments = parser.parse_args()
    load_dotenv(REPO_ROOT / ".env")

    selected_steps = (
        (arguments.only,)
        if arguments.only
        else ("gemini-text", "gemini-tts", "cloudflare-image")
    )
    required_keys = []
    if "gemini-text" in selected_steps or "gemini-tts" in selected_steps:
        required_keys.append("GEMINI_API_KEY")
    if "cloudflare-image" in selected_steps:
        required_keys.extend(("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"))
    missing_keys = [key for key in required_keys if not os.environ.get(key)]
    if missing_keys:
        print(
            "Missing required .env setting(s): " + ", ".join(missing_keys),
            file=sys.stderr,
        )
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gemini_client = None
    if "GEMINI_API_KEY" in required_keys:
        gemini_client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],
            http_options={"api_version": "v1beta"},
        )

    def get_gemini_client() -> genai.Client:
        if gemini_client is None:
            raise RuntimeError("Gemini client was not configured for this check.")
        return gemini_client

    def generate_text() -> None:
        response = get_gemini_client().models.generate_content(
            model=GEMINI_TEXT_MODEL,
            contents="Reply with exactly: Gemini API smoke test passed.",
        )
        if not response.text:
            raise RuntimeError("Gemini returned no text.")
        print(f"Gemini reply: {response.text}")

    def generate_amharic_tts() -> None:
        interaction = get_gemini_client().interactions.create(
            model=GEMINI_TTS_MODEL,
            input=[
                {
                    "type": "user_input",
                    "content": [
                        {
                            "type": "text",
                            "text": AMHARIC_SAMPLE,
                            "annotations": [
                                {
                                    "type": "speech_metadata",
                                    "style": "warm, clear, and natural",
                                }
                            ],
                        }
                    ],
                }
            ],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": "Kore"}]},
        )
        audio_data = interaction.output_audio.data if interaction.output_audio else None
        if not audio_data:
            raise RuntimeError("Gemini returned no audio data.")
        output_path = OUTPUT_DIR / "amharic_greeting.wav"
        output_path.write_bytes(base64.b64decode(audio_data))
        print(f"Saved TTS audio to {output_path.relative_to(REPO_ROOT)}")

    def generate_image() -> None:
        account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
        api_token = os.environ["CLOUDFLARE_API_TOKEN"]
        endpoint = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{account_id}/ai/run/{CLOUDFLARE_IMAGE_MODEL}"
        )
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_token}"},
            json={
                "prompt": (
                    "A quiet Ethiopian highland landscape at sunrise, "
                    "soft golden light, cinematic illustration"
                )
            },
            timeout=120,
        )
        if not response.ok:
            try:
                error_payload = response.json()
            except ValueError:
                error_payload = {}
            errors = error_payload.get("errors", [])
            messages = [
                f"{item.get('code')}: {item.get('message')}"
                for item in errors
                if isinstance(item, dict) and item.get("message")
            ] if isinstance(errors, list) else []
            details = "; ".join(messages) or "No structured error details returned."
            raise RuntimeError(
                f"Cloudflare API returned HTTP {response.status_code}: {details}"
            )
        payload = response.json()
        image_data = payload.get("result", {}).get("image")
        if not payload.get("success") or not image_data:
            raise RuntimeError("Cloudflare response did not contain a generated image.")
        output_path = OUTPUT_DIR / "flux_schnell.jpg"
        output_path.write_bytes(base64.b64decode(image_data))
        print(f"Saved generated image to {output_path.relative_to(REPO_ROOT)}")

    steps = {
        "gemini-text": (
            "Gemini text",
            lambda: timed_call(
                stage="smoke_test",
                model=GEMINI_TEXT_MODEL,
                params={"prompt": "Reply with a short smoke-test confirmation."},
                seed=None,
                cost_estimate=None,
                function=generate_text,
                note="Cost not estimated; check provider usage.",
            ),
        ),
        "gemini-tts": (
            "Gemini Amharic TTS",
            lambda: timed_call(
                stage="smoke_test",
                model=GEMINI_TTS_MODEL,
                params={
                    "text": AMHARIC_SAMPLE,
                    "voice": "Kore",
                    "style": "warm, clear, and natural",
                    "output": "outputs/smoke/amharic_greeting.wav",
                },
                seed=None,
                cost_estimate=None,
                function=generate_amharic_tts,
                note="Cost not estimated; check provider usage.",
            ),
        ),
        "cloudflare-image": (
            "Cloudflare FLUX image",
            lambda: timed_call(
                stage="smoke_test",
                model=CLOUDFLARE_IMAGE_MODEL,
                params={
                    "prompt": (
                        "A quiet Ethiopian highland landscape at sunrise, "
                        "soft golden light, cinematic illustration"
                    ),
                    "output": "outputs/smoke/flux_schnell.jpg",
                },
                seed=None,
                cost_estimate=None,
                function=generate_image,
                note="Cost not estimated; check provider usage.",
            ),
        ),
    }

    results = [
        run_step(*steps[step_name])
        for step_name in selected_steps
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
