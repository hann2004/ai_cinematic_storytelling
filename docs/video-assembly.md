# Video Assembly Guide

This guide explains how to turn the approved storyboard images and Amharic
narration into the 90-second film. The assembly is local: it does not call an
image, speech, or music-generation API.

## What the assembly creates

The pipeline reads the storyboard, the nine approved still images, and the
selected narration. It generates an instrumental score locally, aligns the
spoken passages to the storyboard, adds restrained movement and transitions
to the stills, mixes narration with music, and exports an MP4.

| Output | Description |
| --- | --- |
| `outputs/original_score.wav` | 90-second, locally synthesized instrumental score |
| `outputs/final_film.mp4` | H.264 video with AAC stereo audio, 1280 × 720, 25 fps, 90 seconds |

The current storyboard has nine 10-second shots. `shot-02` has no narration,
so it remains silent in the voice track while the music continues. English
subtitles are intentionally not generated because the storyboard does not yet
contain a reviewed translation.

## Prerequisites

### Operating system packages

On Ubuntu, install FFmpeg, FFprobe (included with FFmpeg), the FluidSynth
runtime library, and the TimGM6mb General MIDI SoundFont:

```bash
sudo apt update
sudo apt install ffmpeg libfluidsynth3 timgm6mb-soundfont
```

The score generator loads FluidSynth as a shared library. It does not require
the `fluidsynth` command-line executable.

Check that the required programs and SoundFont are available:

```bash
ffmpeg -version
ffprobe -version
ldconfig -p | grep libfluidsynth
test -f /usr/share/sounds/sf2/TimGM6mb.sf2 && echo "SoundFont found"
```

If the SoundFont is installed elsewhere, pass its file path with
`--soundfont /path/to/file.sf2`.

### Python environment

The video and score modules use only the Python standard library. Run them
from the repository root, using the project's Python environment if one is
active:

```bash
python3 -m py_compile pipeline/assemble.py pipeline/music.py
```

Successful syntax compilation prints no output. It verifies Python syntax; it
does not render a video or verify the source media.

## Required inputs

Run the command from the repository root. The default inputs are:

| Input | Default location | Requirement |
| --- | --- | --- |
| Storyboard | `storyboard.json` | Nine shots whose durations add up to `target_duration_seconds` |
| Scene images | `outputs/` | One readable image for each storyboard shot |
| Narration | `outputs/narration_am_v2.wav` | The selected Amharic narration, with one spoken passage for each non-silent storyboard shot |
| Score SoundFont | `/usr/share/sounds/sf2/TimGM6mb.sf2` | Available locally, or supplied using `--soundfont` |

For the current storyboard, image names such as `shot-1.jpeg` through
`shot-9.jpeg` are recognized. The assembler also accepts `.jpg` or `.png`
extensions and zero-padded names such as `shot-01.png`. The number in each
filename must correspond to the shot number in the storyboard. Images should
have a landscape composition suitable for 16:9.

Before rendering, confirm that all inputs are present:

```bash
ls outputs/shot-{1..9}.jpeg
ls -lh outputs/narration_am_v2.wav
```

Use the approved narration take. Do not substitute another take unless its
spoken passage order and wording match the non-empty `narration_am` fields in
the storyboard.

## Run the assembly

From the repository root:

```bash
python3 -m pipeline.assemble
```

If `outputs/final_film.mp4` or `outputs/original_score.wav` already exists,
the command stops rather than replacing it. To deliberately regenerate and
replace those default outputs, use:

```bash
python3 -m pipeline.assemble --force
```

The `--force` option applies to both the film and the generated score. Review
and back up any existing deliverables before using it.

The assembler prints the created paths and duration allocated to each shot.
Its exit status is nonzero if it cannot validate required inputs, align the
narration, generate or load the score, or render and verify the MP4.

### Optional arguments

| Argument | Purpose |
| --- | --- |
| `--storyboard PATH` | Read a different storyboard JSON file |
| `--images-dir PATH` | Read scene images from another directory |
| `--narration PATH` | Use another narration audio file |
| `--output PATH` | Write the MP4 to another path |
| `--score PATH` | Write or read the generated score WAV at another path |
| `--music PATH` | Use an existing music file instead of generating the score |
| `--soundfont PATH` | Use a particular SoundFont when generating a score |
| `--force` | Replace existing output files |

For example, to keep the default score but render to a separate review copy:

```bash
python3 -m pipeline.assemble \
  --output outputs/final_film_review.mp4
```

To supply a different music file:

```bash
python3 -m pipeline.assemble \
  --music outputs/my_music.wav \
  --output outputs/final_film_with_music.mp4
```

When providing custom paths, use `--help` to review the available arguments.

## How narration alignment works

The selected narration is a single continuous recording, while the storyboard
has one narration field per shot. The assembler detects pauses of at least
0.75 seconds in the voice track and uses those pauses to split it into
paragraph-sized passages. It then maps the passages in order onto storyboard
shots with non-empty `narration_am` fields. The empty narration field for the
bus departure shot (`shot-02`) means no voice passage is placed on that scene.

The shot lengths are adjusted to fit both the voice passages and the
storyboard's total running time. This protects the complete recording from
being clipped or accelerated just to force every scene to remain exactly ten
seconds. For the current inputs, the allocator gives the narrated passages
enough room for their detected audio and keeps the silent bus scene at its
storyboard hold. The exact allocations are printed after a successful render.

Alignment depends on the voice track having the same spoken passage order as
the storyboard and one detectable long pause between consecutive narrated
passages. If the pause count does not match the number of narrated sections,
the assembler stops with an error instead of silently shifting passages to
the wrong scenes. Review or re-record the narration with clear paragraph
breaks before trying again.

## Music, movement, and audio mix

`pipeline/music.py` synthesizes a gentle instrumental cue locally through
FluidSynth. The arrangement uses soft sustained chords and a sparse repeating
upper-register pattern, with a warmer harmonic progression later in the film.
Music fades in and out, continues under the silent bus scene, and is
side-chain ducked under narration. The output is stereo at 48 kHz.

The film uses still images rather than generated motion footage. FFmpeg adds a
subtle zoom, alternating lateral drift, crossfades between scenes, and a short
opening and closing fade. These effects do not change the source images and
do not create new character animation.

## Verify the rendered files

The assembler checks that the rendered film has both audio and video, that
the frame is 1280 × 720, that the audio is 48 kHz stereo, and that the total
duration is within 0.15 seconds of the storyboard target. Independently
inspect the delivered file with:

```bash
ffprobe -v error \
  -show_entries format=duration,size:stream=codec_type,codec_name,width,height,sample_rate,channels \
  -of json outputs/final_film.mp4
```

Open the MP4 in a media player and listen through the entire film. Check
especially:

1. The first scene starts with the farewell image and its matching narration.
2. The bus departure is shown without voiceover.
3. Each subsequent narration passage corresponds to its storyboard scene.
4. The voice is understandable and the score does not mask it.
5. Transitions do not obscure important faces, luggage, or story details.
6. The ending has the intended hopeful hold and finishes cleanly.

Automated stream and duration checks cannot judge artistic quality, exact
visual-to-word synchronization, or whether the mix sounds right on the
intended playback device. Record the human review separately.

## Troubleshooting

### `python3 -m py_compile ...` succeeds but there is no video

That command checks syntax only. Run `python3 -m pipeline.assemble` to start
assembly; use `--force` only if you intend to replace existing score and video
files.

### The command reports a missing image

Confirm all nine files are in the selected image directory and use a
recognized name such as `shot-3.jpeg`. Use `--images-dir` if the images are in
a different directory.

### The command cannot find FluidSynth or a SoundFont

Install `libfluidsynth3` and `timgm6mb-soundfont`, verify the `.sf2` path, and
rerun. If the SoundFont is in a custom location, pass `--soundfont`.

### Narration pause count does not match

The file may use different paragraph pauses, contain long pauses inside a
sentence, or be a different narration take. Confirm that the chosen WAV
matches the storyboard text and that there is a clear pause between each
narrated shot. The assembler intentionally fails rather than guessing when it
cannot determine a safe mapping.

### FFmpeg reports an error

Check that FFmpeg and FFprobe are installed, that every input file can be
opened, and that the output directory has enough free space. Retain the full
error message when asking for help; it identifies whether the issue is the
filter graph, a codec, or a media input.

## Production report checklist

Include the following in a report about this production:

1. **Project and story summary:** the film title, intended audience, purpose,
   language, and short synopsis.
2. **Production objective:** the assignment requirements and the intended
   90-second, nine-shot, 16:9 deliverable.
3. **Workflow and tools:** storyboard-driven assembly; Python scripts;
   FFmpeg/FFprobe; FluidSynth; the selected narration file; and the source of
   the nine images.
4. **Inputs and provenance:** the exact image filenames, narration filename,
   storyboard filename, and any supplied or generated assets. State that
   private references and credentials were not placed in the repository.
5. **Creative decisions:** the visual order, still-image motion and
   transitions, reason for retaining the silent bus scene, narration
   alignment approach, and the reflective-to-hopeful musical direction.
6. **Audio design:** Amharic narration, score source and instrumentation,
   music ducking, fades, sample rate, channel count, and any human listening
   review performed.
7. **Technical output:** final filename; runtime; resolution; frame rate;
   video and audio codecs; audio sample rate and channels; and file size,
   copied from `ffprobe`.
8. **Validation evidence:** the syntax-check command and result; assembly
   command and result; FFprobe output; and human review findings. Do not say
   a check passed unless it was actually run against the final version.
9. **Challenges and resolutions:** API quota or generation constraints, any
   tools that were unavailable, how the local assembly workflow addressed
   them, and any remaining issues.
10. **Limitations:** still images with simulated camera movement rather than
    animated footage; automatic narration splitting based on pause detection;
    no reviewed English subtitles; and any visual or timing compromises.
11. **Rights and credits:** identify the TimGM6mb SoundFont and its GPL-2
    licensing terms. Check the assignment's and institution's rules before
    distributing the rendered score or film publicly.
12. **Conclusion and future work:** whether the deliverable meets the
    assignment requirements and improvements such as a reviewed subtitle
    translation, stronger original score, or animated footage.
13. **Appendices:** storyboard, selected image samples, command transcript,
    media metadata, and review checklist, as allowed by the assignment.

Keep the report factual: distinguish automated technical validation from
human creative review, and describe unverified items as pending.
