import argparse
import ctypes
import ctypes.util
import math
import shutil
import wave
from array import array
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_RATE = 48_000
BLOCK_SIZE = SAMPLE_RATE // 10
DEFAULT_OUTPUT = REPO_ROOT / "outputs" / "original_score.wav"
SOUNDFONT_CANDIDATES = (
    Path("/usr/share/sounds/sf2/TimGM6mb.sf2"),
    Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
)

# Root note, chord intervals, and duration in seconds.
PROGRESSION = (
    (50, (0, 3, 7), 8),
    (46, (0, 4, 7), 8),
    (41, (0, 4, 7), 8),
    (48, (0, 4, 7), 8),
    (50, (0, 3, 7), 8),
    (43, (0, 3, 7), 8),
    (46, (0, 4, 7), 8),
    (41, (0, 4, 7), 8),
    (48, (0, 4, 7), 8),
    (43, (0, 3, 7), 8),
    (45, (0, 4, 7, 10), 4),
    (50, (0, 3, 7), 6),
)


def find_soundfont(path: Path | None = None) -> Path:
    if path is not None:
        soundfont = path.expanduser().resolve()
        if not soundfont.is_file():
            raise FileNotFoundError(f"SoundFont file was not found: {soundfont}")
        return soundfont

    for candidate in SOUNDFONT_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "No supported SoundFont was found. Install timgm6mb-soundfont or pass "
        "--soundfont with a SoundFont file."
    )


def _render_events(duration: float, sample_rate: int) -> list[tuple[int, int, int, int, int]]:
    events: list[tuple[int, int, int, int, int]] = []
    chord_start = 0.0
    for root, intervals, chord_duration in PROGRESSION:
        if chord_start >= duration:
            break
        chord_end = min(chord_start + chord_duration, duration)
        chord_length = chord_end - chord_start
        if chord_length <= 0:
            break

        pad_velocity = 22 if chord_start < 40 else 28
        for interval in (12, intervals[1] + 12, 19):
            note = root + interval
            start_frame = round(chord_start * sample_rate)
            end_frame = round(max(chord_start, chord_end - 0.8) * sample_rate)
            events.append((start_frame, 1, 1, note, pad_velocity))
            events.append((end_frame, 0, 1, note, 0))

        arpeggio = (root + 12, root + 19, root + intervals[1] + 12, root + 19)
        beat = 0.0
        note_index = 0
        while beat < chord_length - 0.15:
            note = arpeggio[note_index % len(arpeggio)]
            start_frame = round((chord_start + beat) * sample_rate)
            end_frame = round(
                min(chord_start + beat + 1.25, chord_end - 0.08) * sample_rate
            )
            velocity = 34 if chord_start < 40 else 41
            events.append((start_frame, 1, 0, note, velocity))
            events.append((max(start_frame, end_frame), 0, 0, note, 0))
            beat += 1.6
            note_index += 1

        chord_start += chord_duration

    return sorted(events)


def generate_score(
    output: Path = DEFAULT_OUTPUT,
    duration: float = 90,
    soundfont: Path | None = None,
    force: bool = False,
) -> Path:
    if duration <= 0:
        raise ValueError("Score duration must be greater than zero.")
    if output.exists() and not force:
        raise FileExistsError(
            f"{output} already exists. Review it first, or pass --force to replace it."
        )
    if ctypes.util.find_library("fluidsynth") is None:
        raise RuntimeError(
            "The FluidSynth shared library is required to generate the score."
        )

    soundfont_path = find_soundfont(soundfont)
    library = ctypes.CDLL(ctypes.util.find_library("fluidsynth"))
    library.new_fluid_settings.argtypes = []
    library.new_fluid_settings.restype = ctypes.c_void_p
    library.fluid_settings_setnum.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_double,
    ]
    library.fluid_settings_setnum.restype = ctypes.c_int
    library.fluid_settings_setint.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    library.fluid_settings_setint.restype = ctypes.c_int
    library.new_fluid_synth.argtypes = [ctypes.c_void_p]
    library.new_fluid_synth.restype = ctypes.c_void_p
    library.fluid_synth_sfload.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    library.fluid_synth_sfload.restype = ctypes.c_int
    library.fluid_synth_program_select.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
    ]
    library.fluid_synth_program_select.restype = ctypes.c_int
    library.fluid_synth_noteon.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
    ]
    library.fluid_synth_noteoff.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
    ]
    library.fluid_synth_write_float.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
    ]
    library.fluid_synth_write_float.restype = ctypes.c_int
    library.delete_fluid_synth.argtypes = [ctypes.c_void_p]
    library.delete_fluid_settings.argtypes = [ctypes.c_void_p]

    settings = library.new_fluid_settings()
    if not settings:
        raise RuntimeError("FluidSynth could not create audio settings.")
    synth = None
    try:
        if library.fluid_settings_setnum(
            settings, b"synth.sample-rate", float(SAMPLE_RATE)
        ) != 0:
            raise RuntimeError("FluidSynth rejected the requested sample rate.")
        if library.fluid_settings_setnum(settings, b"synth.gain", 0.55) != 0:
            raise RuntimeError("FluidSynth rejected the requested output gain.")
        library.fluid_settings_setint(settings, b"synth.reverb.active", 1)
        synth = library.new_fluid_synth(settings)
        if not synth:
            raise RuntimeError("FluidSynth could not initialize its synthesizer.")

        soundfont_id = library.fluid_synth_sfload(
            synth, str(soundfont_path).encode(), 1
        )
        if soundfont_id < 0:
            raise RuntimeError(f"FluidSynth could not load {soundfont_path}.")
        for channel, instrument in ((0, 0), (1, 48)):
            if library.fluid_synth_program_select(
                synth, channel, soundfont_id, 0, instrument
            ) < 0:
                raise RuntimeError(
                    f"FluidSynth could not select instrument {instrument}."
                )

        output.parent.mkdir(parents=True, exist_ok=True)
        total_frames = round(duration * SAMPLE_RATE)
        events = _render_events(duration, SAMPLE_RATE)
        cursor = 0

        with wave.open(str(output), "wb") as score:
            score.setnchannels(2)
            score.setsampwidth(2)
            score.setframerate(SAMPLE_RATE)

            def render_frames(frame_count: int) -> None:
                nonlocal cursor
                remaining = frame_count
                while remaining:
                    block = min(remaining, BLOCK_SIZE)
                    left = (ctypes.c_float * block)()
                    right = (ctypes.c_float * block)()
                    result = library.fluid_synth_write_float(
                        synth, block, left, 0, 1, right, 0, 1
                    )
                    if result != 0:
                        raise RuntimeError("FluidSynth failed while rendering audio.")
                    samples = array("h")
                    for left_sample, right_sample in zip(left, right):
                        samples.append(
                            max(-32768, min(32767, round(left_sample * 32767)))
                        )
                        samples.append(
                            max(-32768, min(32767, round(right_sample * 32767)))
                        )
                    score.writeframesraw(samples.tobytes())
                    cursor += block
                    remaining -= block

            for frame, action, channel, note, velocity in events:
                frame = min(frame, total_frames)
                if frame > cursor:
                    render_frames(frame - cursor)
                if action == 0:
                    library.fluid_synth_noteoff(synth, channel, note)
                else:
                    library.fluid_synth_noteon(synth, channel, note, velocity)
            if cursor < total_frames:
                render_frames(total_frames - cursor)
    finally:
        if synth:
            library.delete_fluid_synth(synth)
        library.delete_fluid_settings(settings)

    print(f"Generated instrumental score: {output}")
    print(f"SoundFont: {soundfont_path}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a reflective, original instrumental score."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--duration", type=float, default=90)
    parser.add_argument("--soundfont", type=Path)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing output file.",
    )
    arguments = parser.parse_args()
    output = arguments.output
    if not output.is_absolute():
        output = REPO_ROOT / output
    generate_score(
        output=output.resolve(),
        duration=arguments.duration,
        soundfont=arguments.soundfont,
        force=arguments.force,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())