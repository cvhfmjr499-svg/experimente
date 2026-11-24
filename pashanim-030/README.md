# PASHANIM // 030

A 29-second motion piece about the Berlin rapper Pashanim: 1920×1080 at 60 fps. It's an unofficial fan edit.

Each scene runs on one of his songs: a beat-aligned excerpt from the 30 s Deezer preview, time-stretched with rubberband (pitch kept, at most ±9 %) to a grid-friendly tempo (144 BPM = 25 frames per beat, 180 BPM = 20, 120 BPM = 30). The excerpt's start beat lands exactly on the cut. Every visual accent (slams, counters, stamps, the card flip, the board scan, the headline swap) is snapped to the frame of a real snare in that song. Sound design synthesized from scratch glues the cuts together and sits well under the music: DTMF tones for "030", thunder, whooshes, flap clatter and the German busy tone.

`assets/data/timeline.json` is the single source of truth for scene starts and lengths. `tools/medley.py`, `tools/synth.py` and `index.html` all read it.

| Scene | Frames | Scene + song | Act 1 → Act 2 |
|---|---|---|---|
| 1 | 0–99 | **030** · (*Hauseingang* through the phone line) | Berlin's area code is "dialed" (real DTMF tones). The digits are vector glyph windows with a tri-tone photo inside. The camera flies through the counter of the last "0" into scene 2. |
| 2 | 100–299 | **PASHANIM** · *Hauseingang* | The name sits behind a cut-out portrait with an outline copy in front, and its width axis opens on the snare. → The *Hauseingang* cover lands (2019 · Platin). |
| 3 | 300–499 | **Airwaves** (2020) · *Airwaves* (tuned in like a radio) | A waveform driven by the mix, and the DE chart counter rolls 100 → #2. → AT #6 and CH #13 roll in on the next snares. |
| 4 | 500–699 | **Sommergewitter** (2021, first #1) · *Sommergewitter* | The waveform morphs into lightning, and the text is lit only by the strikes. #1 slam. → More strikes on the snares, peaks DE 1 · AT 2 · CH 3, then a white-out. |
| 5 | 700–899 | **2000** (debut album, #1) · *Mittelmeer* | The cover assembles from 25 tiles flying in 3D, the outline type draws on, and the album #1 stamp lands. → The card flips over to *Mittelmeer* and a single #1 stamp lands. |
| 6 | 900–1099 | **Nr. 1** · *Shabab(e)s im VIP* | A split-flap board flips in, with clatter in the mix. → A cursor scans the rows on the snares, a dot marks the song that's playing, and then an orange flood comes out of the *Lounge Musik* row. |
| 7 | 1100–1299 | ***Lounge Musik*** (2026, #1 DE · AT · CH) · *Goldrichtig* | Serif type, a spring entrance, badges on the beats. → A tracklist ticker with *Goldrichtig* highlighted. |
| 8 | 1300–1539 | **Himmel über Berlin** · *Tourlife.mp3* | A tilt up into the sky: the 2022 mixtape. → The headline rolls to "Tempelhofer Feld." (TFELD, 22.08.2026), then a sun-flare white-out. |
| 9 | 1540–1739 | **End card** · *Berlin calling* | "Vom Hauseingang bis Tempelhof." The music collapses back into the phone line, then the busy tone plays: *Anruf beendet* (call ended). |

A "Jetzt läuft" ("now playing") line in the HUD names the song in each scene.

## Rebuild

You need Node with Playwright and Chromium, ffmpeg (with rubberband), ImageMagick, and Python 3 with `rembg[cpu] opencv-python-headless fonttools brotli scipy pillow numpy librosa soundfile`.

```bash
./tools/fetch_assets.sh                 # press photo + cover art (not committed, see below)
python tools/prep_images.py             # cut-outs, edge feathering, inpainted sky plate, covers
python tools/glyphs.py assets/fonts/archivo-var.woff2 assets/data/glyphs.json
python tools/fetch_music.py             # 30 s Deezer previews of the songs (not committed)
python tools/medley.py                  # beat-matched song bed + accents.json (reads timeline.json)
python tools/synth.py                   # sound design + mix -> audio/score.wav, assets/data/events.js
node tools/render.cjs --out frames      # all frames (seeks window.__seek(f))
./tools/encode.sh                       # out/pashanim-030.mp4
node tools/determinism.cjs              # optional: frames must not depend on seek order
```

To preview, open `index.html` in a browser. Space plays it with sound, and the arrow keys step one frame. The page also exposes `window.__maTimeline.seek(t)`.

## Rights

- The photos and cover art (Apple Music / Deezer artist images and release covers) are copyrighted by the artist and label. They are downloaded by `fetch_assets.sh` and are not part of this repo. Check the rights before publishing the rendered video anywhere.
- The music is Pashanim's own recordings (Deezer previews), copyrighted by the artist and label. The previews are fetched locally and not committed. Expect a Content ID claim or a muted upload on social platforms unless the edit is licensed.
- The fonts are Archivo, Instrument Serif and JetBrains Mono, all under the SIL Open Font License 1.1 (see `assets/fonts/OFL.txt`).
- The sound design is synthesized from scratch in `tools/synth.py`; no samples are used.
