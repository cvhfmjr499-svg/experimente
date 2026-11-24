# PASHANIM // 030

A 15-second motion piece about the Berlin rapper Pashanim: 1920×1080 at 60 fps. It's an unofficial fan edit.

The edit is cut in 100-frame bars. Each scene runs on one of his songs: a beat-aligned excerpt from the 30 s Deezer preview, time-stretched with rubberband (pitch kept, at most ±9 %) to a grid-friendly tempo (144 BPM = 25 frames per beat, 180 BPM = 20). The excerpt's start beat lands exactly on the cut. Each scene's visual accents (slams, stamp, badges) are snapped to the frame of a real snare in that song (`tools/medley.py` writes them to `assets/data/accents.json`). Sound design synthesized from scratch glues the cuts together: DTMF tones for "030", thunder, whooshes, flap clatter and a busy tone.

| Bar | Frames | Scene + song | Motion idea |
|---|---|---|---|
| 1 | 0–99 | **030** | Berlin's area code is "dialed" (real DTMF tones). The digits are vector glyph windows with a tri-tone photo inside. The camera flies through the counter of the last "0", and that portal opens onto scene 2. |
| 2 | 100–199 | **PASHANIM** · *Hauseingang* (it first comes through the phone line) | The name sits behind a cut-out portrait, with an outline copy in front. The variable-font width axis opens on the snare. |
| 3 | 200–299 | **Airwaves** (2020, #2) · *Airwaves* (tuned in like a radio) | A waveform driven by the soundtrack's real envelope, plus a chart counter that rolls from 100 down to 2. |
| 4 | 300–399 | **Sommergewitter** (2021, first #1) · *Sommergewitter* | The waveform morphs into a lightning bolt. The text is lit only by the strikes, then a white-out into the drop. |
| 5 | 400–499 | **2000** (debut album, #1) · *Mittelmeer* | The cover assembles from 25 tiles flying in 3D, the outline type draws on, and a spinning #1 stamp lands. |
| 6 | 500–599 | **Nr. 1** · *Shabab(e)s im VIP* | A split-flap board (with clatter in the score), then an orange flood out of the *Lounge Musik* row. |
| 7 | 600–699 | ***Lounge Musik*** (2026, #1 DE · AT · CH) · *Goldrichtig* | Serif type and a spring entrance. The badges pop on the beats. |
| 8 | 700–799 | **Himmel über Berlin**: TFELD, Tempelhofer Feld · *Tourlife.mp3* | A camera tilt up into the sky, then a sun flare white-out. |
| 9 | 800–899 | **End card** · *Berlin calling* (collapses back into the phone line) | "Vom Hauseingang bis Tempelhof." and the German busy tone: *Anruf beendet* (call ended). |

## Rebuild

You need Node with Playwright and Chromium, ffmpeg, ImageMagick, and Python 3 with `rembg[cpu] opencv-python-headless fonttools brotli scipy pillow numpy librosa soundfile`.

```bash
./tools/fetch_assets.sh                 # press photo + cover art (not committed, see below)
python tools/prep_images.py             # cut-outs, edge feathering, inpainted sky plate
python tools/glyphs.py assets/fonts/archivo-var.woff2 assets/data/glyphs.json
python tools/fetch_music.py             # 30 s Deezer previews of the songs (not committed)
python tools/medley.py                  # beat-matched song bed + accents.json
python tools/synth.py                   # sound design + mix -> audio/score.wav, assets/data/events.js
node tools/render.cjs --out frames      # 900 PNG frames (seeks window.__seek(f))
./tools/encode.sh                       # out/pashanim-030.mp4
node tools/determinism.cjs              # optional: frames must not depend on seek order
```

To preview, open `index.html` in a browser. Space plays it with sound, and the arrow keys step one frame. The page also exposes `window.__maTimeline.seek(t)`.

## Rights

- The photos and cover art (Apple Music / Deezer artist images and release covers) are copyrighted by the artist and label. They are downloaded by `fetch_assets.sh` and are not part of this repo. Check the rights before publishing the rendered video anywhere.
- The fonts are Archivo, Instrument Serif and JetBrains Mono, all under the SIL Open Font License 1.1 (see `assets/fonts/OFL.txt`).
- The music is Pashanim's own recordings (Deezer previews), copyrighted by the artist and label. The previews are fetched locally and not committed. Expect a Content ID claim or a muted upload on social platforms unless the edit is licensed.
- The sound design is synthesized from scratch in `tools/synth.py`. Without the song bed, the script falls back to its own synthesized 144 BPM score.
