import argparse
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NARRATION = REPO_ROOT / "outputs" / "narration_am_v2.wav"
DEFAULT_OUTPUT = REPO_ROOT / "outputs" / "radio_cut.mp4"
FRAME_RATE = 24


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def get_duration(path: Path) -> float:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    try:
        duration = float(result.stdout.strip())
    except ValueError as error:
        raise RuntimeError(f"Could not read audio duration from {path}.") from error
    if duration <= 0:
        raise ValueError(f"Narration audio must have positive duration: {path}")
    return duration


def create_radio_cut(narration: Path, output: Path, force: bool) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("Both ffmpeg and ffprobe must be installed and on PATH.")
    if not narration.is_file():
        raise FileNotFoundError(f"Narration audio was not found: {narration}")
    if output.exists() and not force:
        raise FileExistsError(
            f"{output} already exists. Review it first, or pass --force to replace it."
        )

    duration = get_duration(narration)
    fade_out_start = max(0.0, duration - 3.0)
    duration_text = f"{duration:.6f}"
    fade_out_text = f"{fade_out_start:.6f}"
    audio_filter = (
        "[1:a]aformat=sample_rates=24000:channel_layouts=mono,"
        "asplit=2[voice][sidechain];"
        f"aevalsrc=0.012*sin(2*PI*130.81*t)+"
        f"0.009*sin(2*PI*164.81*t)+"
        f"0.006*sin(2*PI*196.00*t):s=24000:d={duration_text},"
        "afade=t=in:st=0:d=2,"
        f"afade=t=out:st={fade_out_text}:d=3,"
        "volume=0.12[music];"
        "[music][sidechain]sidechaincompress="
        "threshold=0.02:ratio=6:attack=300:release=1500[ducked];"
        "[ducked][voice]amix=inputs=2:duration=first:dropout_transition=0,"
        "loudnorm=I=-16:LRA=11:TP=-1.5[audio]"
    )
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if force else "-n",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=1280x720:r={FRAME_RATE}:d={duration_text}",
        "-i",
        str(narration),
        "-filter_complex",
        audio_filter,
        "-map",
        "0:v:0",
        "-map",
        "[audio]",
        "-c:v",
        "libx264",
        "-tune",
        "stillimage",
        "-preset",
        "ultrafast",
        "-crf",
        "28",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(FRAME_RATE),
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        str(output),
    ]

    try:
        run(command)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            "FFmpeg failed to create the radio cut: "
            f"{error.stderr.strip() or error.stdout.strip()}"
        ) from error

    print(f"Created radio cut: {output.relative_to(REPO_ROOT)}")
    print(f"Duration: {duration:.2f} seconds")
    print("Picture: black. Audio: narration plus a quiet synthetic placeholder bed.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a black-screen narration radio cut for audience testing."
    )
    parser.add_argument("--narration", type=Path, default=DEFAULT_NARRATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing output file.",
    )
    arguments = parser.parse_args()

    narration = arguments.narration
    output = arguments.output
    if not narration.is_absolute():
        narration = REPO_ROOT / narration
    if not output.is_absolute():
        output = REPO_ROOT / output
    narration = narration.resolve()
    output = output.resolve()

    for path in (narration, output):
        try:
            path.relative_to(REPO_ROOT)
        except ValueError as error:
            raise ValueError("Input and output paths must stay inside the repository.") from error

    create_radio_cut(narration, output, arguments.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
