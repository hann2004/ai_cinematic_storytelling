import argparse
import json
import math
import re
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

from pipeline.music import DEFAULT_OUTPUT as DEFAULT_SCORE
from pipeline.music import generate_score

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORYBOARD = REPO_ROOT / "storyboard.json"
DEFAULT_IMAGES_DIR = REPO_ROOT / "outputs"
DEFAULT_NARRATION = REPO_ROOT / "outputs" / "narration_am_v2.wav"
DEFAULT_VIDEO = REPO_ROOT / "outputs" / "final_film.mp4"
FRAME_RATE = 25
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
CROSSFADE_FRAMES = 10
MIN_VOICE_SHOT_SECONDS = 6
VOICE_HEADROOM_SECONDS = 0.75


def _run(command: list[str], description: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        details = error.stderr.strip() or error.stdout.strip()
        raise RuntimeError(
            f"{description} failed: {details[-4000:] or 'No error details returned.'}"
        ) from error


def _resolve_path(path: Path) -> Path:
    return (path if path.is_absolute() else REPO_ROOT / path).resolve()


def _audio_duration(path: Path) -> float:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        f"Could not read media duration for {path}",
    )
    try:
        duration = float(result.stdout.strip())
    except ValueError as error:
        raise RuntimeError(f"Could not read a valid duration from {path}.") from error
    if duration <= 0:
        raise ValueError(f"Media duration must be positive: {path}")
    return duration


def _find_image(images_dir: Path, shot_id: str) -> Path:
    shot_number = int(shot_id.rsplit("-", 1)[1])
    candidates = (
        images_dir / f"shot-{shot_number}.jpeg",
        images_dir / f"shot-{shot_number}.jpg",
        images_dir / f"shot-{shot_number}.png",
        images_dir / f"shot-{shot_number:02d}.jpeg",
        images_dir / f"shot-{shot_number:02d}.jpg",
        images_dir / f"shot-{shot_number:02d}.png",
    )
    image = next((candidate for candidate in candidates if candidate.is_file()), None)
    if image is None:
        expected = ", ".join(candidate.name for candidate in candidates)
        raise FileNotFoundError(
            f"No image found for {shot_id} in {images_dir}; expected one of: {expected}"
        )
    return image.resolve()


def _load_storyboard(storyboard_path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    try:
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read storyboard JSON at {storyboard_path}: {error}") from error
    shots = storyboard.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("The storyboard must contain a non-empty shots array.")
    if any(not isinstance(shot, dict) for shot in shots):
        raise ValueError("Every storyboard shot must be a JSON object.")
    target_duration = storyboard.get("target_duration_seconds")
    if not isinstance(target_duration, int) or target_duration <= 0:
        raise ValueError("Storyboard target_duration_seconds must be a positive integer.")
    planned_duration = sum(shot.get("duration_seconds", 0) for shot in shots)
    if planned_duration != target_duration:
        raise ValueError(
            "Storyboard shot durations must sum to target_duration_seconds "
            f"({planned_duration} != {target_duration})."
        )
    for shot in shots:
        if not isinstance(shot.get("id"), str):
            raise ValueError("Every storyboard shot must have a string id.")
        if not isinstance(shot.get("narration_am"), str):
            raise ValueError(f"{shot['id']} must have a narration_am string.")
        if not isinstance(shot.get("duration_seconds"), int) or shot["duration_seconds"] <= 0:
            raise ValueError(f"{shot['id']} must have a positive integer duration.")
    return storyboard, shots


def _narration_segments(
    narration: Path,
    expected_count: int,
    duration: float,
) -> list[tuple[float, float]]:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("Both ffmpeg and ffprobe must be installed and on PATH.")
    result = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-i",
            str(narration),
            "-af",
            "silencedetect=noise=-40dB:d=0.75",
            "-f",
            "null",
            "-",
        ],
        f"Could not analyze narration pauses in {narration}",
    )
    silences = result.stderr
    silence_starts = [
        float(value)
        for value in re.findall(r"silence_start:\s*([\d.]+)", silences)
    ]
    silence_ends = [
        float(value)
        for value in re.findall(r"silence_end:\s*([\d.]+)", silences)
    ]
    expected_gaps = expected_count - 1
    if len(silence_starts) != expected_gaps or len(silence_ends) != expected_gaps:
        raise ValueError(
            "Could not safely align the narration to the storyboard: expected "
            f"{expected_gaps} paragraph pauses longer than 0.75 seconds, found "
            f"{len(silence_starts)} starts and {len(silence_ends)} ends. "
            "Check the selected narration or adjust its pause threshold."
        )

    segments: list[tuple[float, float]] = []
    cursor = 0.0
    for silence_start, silence_end in zip(silence_starts, silence_ends):
        if silence_start <= cursor or silence_end <= silence_start:
            raise ValueError("Narration pause boundaries are not in chronological order.")
        segments.append((cursor, silence_start))
        cursor = silence_end
    if duration <= cursor:
        raise ValueError("Narration has no audio after its final detected pause.")
    segments.append((cursor, duration))
    return segments


def _allocate_scene_frames(
    shots: list[dict[str, object]],
    segments: list[tuple[float, float]],
    target_duration: int,
) -> tuple[list[int], dict[int, tuple[float, float]]]:
    target_frames = target_duration * FRAME_RATE
    voice_shots = [
        index for index, shot in enumerate(shots) if shot["narration_am"].strip()
    ]
    if len(voice_shots) != len(segments):
        raise ValueError(
            "The number of spoken storyboard shots does not match the narration "
            f"paragraphs ({len(voice_shots)} != {len(segments)})."
        )

    allocations = [0] * len(shots)
    segment_by_shot: dict[int, tuple[float, float]] = {}
    for index, shot in enumerate(shots):
        if shot["narration_am"].strip():
            segment = segments[len(segment_by_shot)]
            segment_duration = segment[1] - segment[0]
            minimum = max(
                MIN_VOICE_SHOT_SECONDS,
                segment_duration + VOICE_HEADROOM_SECONDS,
            )
            allocations[index] = math.ceil(minimum * FRAME_RATE)
            segment_by_shot[index] = segment
        else:
            allocations[index] = shot["duration_seconds"] * FRAME_RATE

    remaining = target_frames - sum(allocations)
    if remaining < 0:
        raise ValueError(
            "The full narration cannot fit within the storyboard duration without "
            "speeding it up or shortening it."
        )
    weights = [
        shots[index]["duration_seconds"]
        if index in segment_by_shot
        else 0
        for index in range(len(shots))
    ]
    total_weight = sum(weights)
    if remaining and total_weight == 0:
        raise ValueError("There is no narrated scene to hold the remaining duration.")
    fractional_extras = [
        remaining * weight / total_weight if total_weight else 0
        for weight in weights
    ]
    whole_extras = [math.floor(extra) for extra in fractional_extras]
    for index, extra in enumerate(whole_extras):
        allocations[index] += extra
    frames_left = remaining - sum(whole_extras)
    remainder_order = sorted(
        (index for index, weight in enumerate(weights) if weight),
        key=lambda index: fractional_extras[index] - whole_extras[index],
        reverse=True,
    )
    for index in remainder_order[:frames_left]:
        allocations[index] += 1

    return allocations, segment_by_shot


def _subtitle_cues(
    shots: list[dict[str, object]],
    frame_counts: list[int],
    segments_by_shot: dict[int, tuple[float, float]],
) -> list[tuple[float, float, str]]:
    cues: list[tuple[float, float, str]] = []
    for shot_index, shot in enumerate(shots):
        subtitle = shot["subtitle_en"].strip()
        narration = shot["narration_am"].strip()
        if narration and not subtitle:
            raise ValueError(f"{shot['id']} has narration but no English subtitle.")
        if not narration and subtitle:
            raise ValueError(f"{shot['id']} has a subtitle but no narration.")
        if not subtitle:
            continue

        segment_start, segment_end = segments_by_shot[shot_index]
        scene_start = sum(frame_counts[:shot_index]) / FRAME_RATE
        sentences = re.split(r"(?<=[.!?])\s+", subtitle)
        chunks: list[str] = []
        for sentence in sentences:
            lines = textwrap.wrap(
                sentence,
                width=44,
                break_long_words=False,
                break_on_hyphens=False,
            )
            chunks.extend(
                "\n".join(lines[index : index + 2])
                for index in range(0, len(lines), 2)
            )
        weights = [max(1, len(chunk.replace("\n", " "))) for chunk in chunks]
        total_weight = sum(weights)
        available = segment_end - segment_start
        gap = min(0.08, available / (2 * len(chunks)))
        usable = available - gap * (len(chunks) - 1)
        cursor = segment_start
        for index, (chunk, weight) in enumerate(zip(chunks, weights)):
            end = segment_start + usable * sum(weights[: index + 1]) / total_weight
            start = cursor
            if end <= start:
                raise ValueError(f"Could not assign subtitle timing for {shot['id']}.")
            cues.append((scene_start + start, scene_start + end, chunk))
            cursor = end + gap
    return cues


def _write_srt(
    subtitle_path: Path,
    cues: list[tuple[float, float, str]],
) -> None:
    def timestamp(seconds: float) -> str:
        milliseconds = round(seconds * 1000)
        hours, milliseconds = divmod(milliseconds, 3_600_000)
        minutes, milliseconds = divmod(milliseconds, 60_000)
        whole_seconds, milliseconds = divmod(milliseconds, 1000)
        return (
            f"{hours:02}:{minutes:02}:{whole_seconds:02},"
            f"{milliseconds:03}"
        )

    with subtitle_path.open("w", encoding="utf-8", newline="\n") as subtitle_file:
        for index, (start, end, text) in enumerate(cues, start=1):
            subtitle_file.write(
                f"{index}\n{timestamp(start)} --> {timestamp(end)}\n{text}\n\n"
            )


def _video_filter(
    shots: list[dict[str, object]],
    frame_counts: list[int],
    subtitle_path: Path,
) -> str:
    filters: list[str] = []
    for index, (shot, scene_frames) in enumerate(zip(shots, frame_counts)):
        clip_frames = scene_frames + CROSSFADE_FRAMES
        pan_direction = 1 if index % 2 == 0 else -1
        filters.append(
            f"[{index}:v]"
            f"scale={FRAME_WIDTH}:{FRAME_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={FRAME_WIDTH}:{FRAME_HEIGHT},"
            "zoompan="
            "z='min(zoom+0.0002,1.05)':"
            f"x='iw/2-(iw/zoom/2)+on*{pan_direction * 0.04}':"
            "y='ih/2-(ih/zoom/2)':"
            f"d=1:s={FRAME_WIDTH}x{FRAME_HEIGHT}:fps={FRAME_RATE},"
            f"trim=end_frame={clip_frames},"
            "setpts=PTS-STARTPTS,setsar=1,format=yuv420p"
            f"[scene{index}]"
        )

    previous_label = "scene0"
    for index in range(1, len(shots)):
        offset_frames = sum(frame_counts[:index])
        next_label = f"transition{index}"
        filters.append(
            f"[{previous_label}][scene{index}]"
            "xfade=transition=fade:"
            f"duration={CROSSFADE_FRAMES / FRAME_RATE:.3f}:"
            f"offset={offset_frames / FRAME_RATE:.6f}"
            f"[{next_label}]"
        )
        previous_label = next_label

    fade_out_start = sum(frame_counts) / FRAME_RATE - 1
    escaped_subtitle_path = (
        subtitle_path.resolve().as_posix().replace("\\", "\\\\").replace(":", "\\:")
    )
    filters.append(
        f"[{previous_label}]fade=t=in:st=0:d=1,"
        f"fade=t=out:st={fade_out_start:.3f}:d=1,"
        "format=yuv420p,"
        f"subtitles=filename='{escaped_subtitle_path}':"
        "force_style='FontName=DejaVu Sans,FontSize=24,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BorderStyle=1,Outline=2,Shadow=1,MarginV=30,Alignment=2'"
        "[video]"
    )
    return ";".join(filters)


def _audio_filter(
    voice_index: int,
    music_index: int,
    frame_counts: list[int],
    segments_by_shot: dict[int, tuple[float, float]],
    target_duration: int,
) -> str:
    voice_count = len(segments_by_shot)
    filters = [
        f"[{voice_index}:a]asplit={voice_count}"
        + "".join(f"[voice_source{index}]" for index in range(voice_count))
    ]
    for voice_index_in_mix, (shot_index, (start, end)) in enumerate(
        segments_by_shot.items()
    ):
        segment_duration = end - start
        scene_start = sum(frame_counts[:shot_index]) / FRAME_RATE
        delay_ms = round(scene_start * 1000)
        fade_out_start = max(0, segment_duration - 0.08)
        filters.append(
            f"[voice_source{voice_index_in_mix}]"
            f"atrim=start={start:.6f}:end={end:.6f},"
            "asetpts=PTS-STARTPTS,"
            "afade=t=in:st=0:d=0.04,"
            f"afade=t=out:st={fade_out_start:.6f}:d=0.08,"
            f"adelay=delays={delay_ms}:all=1"
            f"[voice{voice_index_in_mix}]"
        )
    voice_labels = "".join(
        f"[voice{index}]" for index in range(voice_count)
    )
    filters.append(
        f"{voice_labels}amix=inputs={voice_count}:duration=longest:"
        "normalize=0:dropout_transition=0[voices]"
    )
    filters.append(
        "[voices]aformat=sample_rates=48000:channel_layouts=stereo[voices_stereo]"
    )
    filters.append("[voices_stereo]asplit=2[voice_mix][voice_sidechain]")
    filters.extend(
        (
            f"[{music_index}:a]volume=0.46,"
            "afade=t=in:st=0:d=2,"
            f"afade=t=out:st={target_duration - 3}:d=3[music]",
            "[music][voice_sidechain]sidechaincompress="
            "threshold=0.025:ratio=5:attack=120:release=800[ducked]",
            "[voice_mix][ducked]amix=inputs=2:duration=longest:"
            "normalize=0:dropout_transition=0,"
            "alimiter=limit=0.95[audio]",
        )
    )
    return ";".join(filters)


def _verify_output(output: Path, target_duration: int) -> None:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            (
                "format=duration:"
                "stream=codec_type,codec_name,width,height,sample_rate,channels"
            ),
            "-of",
            "json",
            str(output),
        ],
        f"Could not validate rendered video {output}",
    )
    try:
        metadata = json.loads(result.stdout)
        duration = float(metadata["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"FFprobe returned invalid metadata for {output}.") from error
    streams = metadata.get("streams", [])
    video_streams = [stream for stream in streams if stream["codec_type"] == "video"]
    audio_streams = [stream for stream in streams if stream["codec_type"] == "audio"]
    if abs(duration - target_duration) > 0.15:
        raise RuntimeError(
            f"Rendered video is {duration:.3f} seconds; expected {target_duration}."
        )
    if not video_streams or not audio_streams:
        raise RuntimeError("Rendered video must contain both video and audio streams.")
    if (
        video_streams[0].get("width") != FRAME_WIDTH
        or video_streams[0].get("height") != FRAME_HEIGHT
    ):
        raise RuntimeError("Rendered video does not have the requested 1280x720 frame.")
    if audio_streams[0].get("sample_rate") != "48000" or audio_streams[0].get(
        "channels"
    ) != 2:
        raise RuntimeError("Rendered audio is not 48 kHz stereo.")


def assemble_film(
    storyboard_path: Path = DEFAULT_STORYBOARD,
    images_dir: Path = DEFAULT_IMAGES_DIR,
    narration: Path = DEFAULT_NARRATION,
    output: Path = DEFAULT_VIDEO,
    score: Path = DEFAULT_SCORE,
    soundfont: Path | None = None,
    force: bool = False,
    music_track: Path | None = None,
) -> Path:
    for executable in ("ffmpeg", "ffprobe"):
        if shutil.which(executable) is None:
            raise RuntimeError(f"{executable} must be installed and on PATH.")
    storyboard_path = _resolve_path(storyboard_path)
    images_dir = _resolve_path(images_dir)
    narration = _resolve_path(narration)
    output = _resolve_path(output)
    score = _resolve_path(score)
    subtitle_output = output.with_suffix(".srt")
    if music_track is not None:
        music_track = _resolve_path(music_track)
    if not storyboard_path.is_file():
        raise FileNotFoundError(f"Storyboard was not found: {storyboard_path}")
    if not narration.is_file():
        raise FileNotFoundError(f"Narration audio was not found: {narration}")
    if output.exists() and not force:
        raise FileExistsError(
            f"{output} already exists. Review it first, or pass --force to replace it."
        )
    if subtitle_output.exists() and not force:
        raise FileExistsError(
            f"{subtitle_output} already exists. Review it first, or pass --force "
            "to replace it."
        )

    storyboard, shots = _load_storyboard(storyboard_path)
    target_duration = storyboard["target_duration_seconds"]
    images = [_find_image(images_dir, shot["id"]) for shot in shots]
    for image in images:
        _run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(image),
            ],
            f"Could not read storyboard image {image}",
        )

    narration_duration = _audio_duration(narration)
    voice_shot_count = sum(
        1 for shot in shots if shot["narration_am"].strip()
    )
    segments = _narration_segments(narration, voice_shot_count, narration_duration)
    frame_counts, segments_by_shot = _allocate_scene_frames(
        shots, segments, target_duration
    )
    subtitle_cues = _subtitle_cues(shots, frame_counts, segments_by_shot)
    if not subtitle_cues:
        raise ValueError("No English subtitle cues were found in the storyboard.")

    if music_track is None:
        if score.is_file() and not force:
            score_duration = _audio_duration(score)
            if abs(score_duration - target_duration) > 0.1:
                raise ValueError(
                    f"Existing score is {score_duration:.2f} seconds, expected "
                    f"{target_duration}; pass --force to regenerate it."
                )
            music_track = score
            print(f"Using existing score: {music_track}")
        else:
            generate_score(
                output=score,
                duration=target_duration,
                soundfont=soundfont,
                force=force,
            )
            music_track = score
    elif not music_track.is_file():
        raise FileNotFoundError(f"Music track was not found: {music_track}")
    music_duration = _audio_duration(music_track)
    if music_duration + 0.1 < target_duration:
        raise ValueError(
            f"Music track is {music_duration:.2f} seconds; it must cover the "
            f"{target_duration}-second film."
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    audio_filters = _audio_filter(
        len(images),
        len(images) + 1,
        frame_counts,
        segments_by_shot,
        target_duration,
    )
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    for image in images:
        command.extend(("-loop", "1", "-framerate", str(FRAME_RATE), "-i", str(image)))
    command.extend(("-i", str(narration), "-i", str(music_track)))
    with tempfile.NamedTemporaryFile(
        prefix=f"{output.stem}.",
        suffix=".mp4",
        dir=output.parent,
        delete=False,
    ) as temporary_file:
        temporary_output = Path(temporary_file.name)
    with tempfile.NamedTemporaryFile(
        prefix=f"{subtitle_output.stem}.",
        suffix=".srt",
        dir=subtitle_output.parent,
        delete=False,
    ) as temporary_subtitle_file:
        temporary_subtitle = Path(temporary_subtitle_file.name)
    try:
        _write_srt(temporary_subtitle, subtitle_cues)
        video_filters = _video_filter(shots, frame_counts, temporary_subtitle)
        filter_graph = f"{video_filters};{audio_filters}"
        command.extend(
            (
                "-filter_complex",
                filter_graph,
                "-map",
                "[video]",
                "-map",
                "[audio]",
                "-t",
                str(target_duration),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(FRAME_RATE),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
            )
        )
        command.extend(("-y", str(temporary_output)))
        _run(command, "FFmpeg video assembly")
        _verify_output(temporary_output, target_duration)
        temporary_subtitle.replace(subtitle_output)
        temporary_output.replace(output)
    finally:
        temporary_output.unlink(missing_ok=True)
        temporary_subtitle.unlink(missing_ok=True)

    print(f"Created film: {output}")
    print(f"Burned-in English subtitles; SRT sidecar: {subtitle_output}")
    print(
        f"Duration: {target_duration} seconds | "
        f"Frame: {FRAME_WIDTH}x{FRAME_HEIGHT} | "
        f"Voice passages: {voice_shot_count} | "
        f"Silent scenes: {len(shots) - voice_shot_count}"
    )
    for shot, frame_count in zip(shots, frame_counts):
        print(
            f"  {shot['id']}: {frame_count / FRAME_RATE:.2f}s"
            f"{' (silent)' if not shot['narration_am'].strip() else ''}"
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assemble storyboard images, Amharic narration, and score into a film."
    )
    parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORYBOARD)
    parser.add_argument("--images-dir", type=Path, default=DEFAULT_IMAGES_DIR)
    parser.add_argument("--narration", type=Path, default=DEFAULT_NARRATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument(
        "--score",
        type=Path,
        default=DEFAULT_SCORE,
        help="Path for the generated score WAV.",
    )
    parser.add_argument(
        "--music",
        type=Path,
        help="Use an existing music file instead of generating the score.",
    )
    parser.add_argument("--soundfont", type=Path)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing video and score outputs.",
    )
    arguments = parser.parse_args()
    assemble_film(
        storyboard_path=arguments.storyboard,
        images_dir=arguments.images_dir,
        narration=arguments.narration,
        output=arguments.output,
        score=arguments.score,
        soundfont=arguments.soundfont,
        music_track=arguments.music,
        force=arguments.force,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())