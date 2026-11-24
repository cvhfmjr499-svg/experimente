"""Builds the per-scene music bed from Pashanim's own songs (Deezer previews).

For every scene:
  1. beat-track the preview (librosa), pick a strong beat-aligned segment
     (kick on the start beat, high energy, a snare where the scene's accent wants one)
  2. time-stretch it with rubberband (pitch kept) to the nearest grid-friendly
     tempo (144 BPM = 25 frames/beat, 180 BPM = 20 frames/beat) -- at most ~9 %
  3. place it so its start beat lands exactly on the scene cut
and records the frames of the real snares/beats as accents, so the visual
slams, stamp and badges hit on the song rather than on a fixed grid.

Writes audio/music_bed.wav + assets/data/accents.json
usage: python tools/medley.py   (after tools/fetch_music.py)
"""
import json
import os
import subprocess
import tempfile
import warnings

import librosa
import numpy as np
import scipy.signal as sg
import soundfile as sf

warnings.filterwarnings("ignore")
SR, FPS = 48000, 60
F2S = SR // FPS
TL = json.load(open("assets/data/timeline.json"))
N = TL["frames"] * F2S
SC = {k: (v[0], v[0] + v[1]) for k, v in TL["scenes"].items()}  # scene -> (cut, end)

# scene, song, first frame (cut), last frame (exclusive), pre-roll frames, tempo prior,
# target bpm (None = keep native), accents {name: (desired offset, allowed beat offsets)}
# Accent offsets are frames after the cut; they snap to the song's real snares.
SCENES = [
    ("s2", "hauseingang", SC["s2"][0], SC["s2"][1], 88, 167, 180, {"s2": (50, (40, 60)), "s2b": (100, (100,))}),
    ("s3", "airwaves", SC["s3"][0], SC["s3"][1], 0, 132, 144,
     {"s3": (50, (50,)), "s3b": (100, (100,)), "s3c": (150, (125, 150))}),
    ("s4", "sommergewitter", SC["s4"][0], SC["s4"][1] - 6, 0, 184, 180,
     {"s4": (50, (40, 60)), "s4b": (100, (100,)), "s4c": (140, (140,))}),
    ("s5", "mittelmeer", SC["s5"][0], SC["s5"][1], 0, 178, 180,
     {"s5": (40, (40, 60)), "s5b": (100, (100,)), "s5c": (120, (120,))}),
    ("s6", "shababes_im_vip", SC["s6"][0], SC["s6"][1], 0, 136, 144,
     {"s6a": (100, (100,)), "s6b": (125, (125,)), "s6c": (150, (150,))}),
    ("s7", "goldrichtig", SC["s7"][0], SC["s7"][1], 0, 178, 180,
     {"s7a": (20, (20,)), "s7b": (40, (40,)), "s7c": (60, (60,)), "s7d": (100, (100,))}),
    ("s8", "tourlife", SC["s8"][0], SC["s8"][1], 0, 120, 120, {"s8b": (120, (120,))}),
    ("s9", "berlin_calling", SC["s9"][0], SC["s9"][0] + 110, 0, 172, None, {}),
]
TAIL = 3  # frames of overlap after the cut, faded


def band_flux(y, sr, lo, hi, hop=256):
    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=hop))
    fr = librosa.fft_frequencies(sr=sr, n_fft=1024)
    b = np.log1p(30 * S[(fr >= lo) & (fr < hi)])
    return np.r_[0, np.maximum(0, np.diff(b, axis=1)).sum(0)]


def stretch(x, R):
    """rubberband via ffmpeg; x: (n, 2) float32 at SR; returns stretched (m, 2)."""
    if abs(R - 1) < 1e-4:
        return x.copy()
    with tempfile.TemporaryDirectory() as d:
        a, b = os.path.join(d, "a.wav"), os.path.join(d, "b.wav")
        sf.write(a, x, SR, subtype="FLOAT")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", a, "-af",
                        f"rubberband=tempo={R:.6f}:transients=crisp:detector=percussive:pitchq=quality:channels=together",
                        "-c:a", "pcm_f32le", b], check=True)
        y, _ = sf.read(b, dtype="float32", always_2d=True)
    return y


def onset_env(x, sr=SR, hop=256):
    return librosa.onset.onset_strength(y=x.mean(1) if x.ndim == 2 else x, sr=sr, hop_length=hop)


def bp(x, lo, hi, order=4):
    return sg.sosfilt(sg.butter(order, [lo, hi], "bandpass", fs=SR, output="sos"), x, axis=0)


def tv_filter(x, kind, cut_fn, block=256):
    y = np.zeros_like(x)
    zi = None
    for i in range(0, len(x), block):
        sos = sg.butter(2, cut_fn((i + block / 2) / len(x)), kind, fs=SR, output="sos")
        if zi is None:
            zi = np.zeros((sos.shape[0], 2, x.shape[1]))
        y[i:i + block], zi = sg.sosfilt(sos, x[i:i + block], axis=0, zi=zi)
    return y


def ramp(n, a, b):
    return np.linspace(a, b, n)[:, None]


bed = np.zeros((N + SR, 2), np.float32)
accents, report = {}, {}
for scene, song, f0, f1, pre, prior, target, accs in SCENES:
    path = f"assets/music/{song}.mp3"
    y48, _ = librosa.load(path, sr=SR, mono=False)
    y48 = y48.T.astype(np.float32)  # (n, 2)
    y22 = librosa.resample(y48.mean(1), orig_sr=SR, target_sr=22050)
    oenv = librosa.onset.onset_strength(y=y22, sr=22050, hop_length=256)
    _, beats = librosa.beat.beat_track(onset_envelope=oenv, sr=22050, hop_length=256, units="time",
                                       start_bpm=prior, tightness=200)
    low = band_flux(y22, 22050, 30, 160)
    high = band_flux(y22, 22050, 1500, 6000)
    rms = librosa.feature.rms(y=y22, hop_length=256)[0]
    t2i = lambda t: int(np.clip(round(t * 22050 / 256), 0, len(low) - 1))
    dur_main = (f1 - f0 + TAIL) / FPS
    cands = []
    for i, b in enumerate(beats):
        win = beats[max(0, i - 4): i + 12]
        if len(win) < 6:
            continue
        local_bpm = 60 / np.median(np.diff(win))
        if target:
            R = target / local_bpm
            R *= 2 ** -round(np.log2(R))  # handle half/double tempo
        else:
            R = 1.0
        if b - pre / FPS * R < 0.6 or b + dur_main * R > 28.6:
            continue
        seg = slice(t2i(b), t2i(b + dur_main * R))
        kick = low[t2i(b) - 1: t2i(b) + 2].max()
        energy = rms[seg].mean()
        snare = 0.0
        for name, (want, opts) in accs.items():
            snare += max(high[t2i(b + o / FPS * R) - 1: t2i(b + o / FPS * R) + 2].max() for o in opts)
        cands.append((b, R, local_bpm, kick, energy, snare))
    c = np.array([x[3:] for x in cands])
    c = c / np.maximum(c.max(0), 1e-9)
    score = 1.0 * c[:, 0] + 0.9 * c[:, 1] + 0.5 * c[:, 2]
    b, R, local_bpm = cands[int(np.argmax(score))][:3]

    # extract with margins, stretch, then fine-align the start beat by onset cross-correlation
    m = 0.25
    s0, s1 = b - pre / FPS * R - m, b + dur_main * R + m
    raw = y48[int(s0 * SR): int(s1 * SR)]
    st = stretch(raw, R)
    expect = int(round((pre / FPS + m / R) * SR))  # where the start beat should be in `st`
    ref = onset_env(raw, hop=128)
    got = onset_env(st, hop=128)
    ref_s = np.interp(np.arange(len(got)) * R, np.arange(len(ref)), ref)
    lags = np.arange(-40, 41)
    xc = [np.dot(ref_s[max(0, -L): len(ref_s) - max(0, L)], got[max(0, L): len(got) - max(0, -L)]) for L in lags]
    lag = int(lags[int(np.argmax(xc))]) * 128
    beat_at = expect + lag
    n_main = (f1 - f0 + TAIL) * F2S
    n_pre = pre * F2S
    clip = st[beat_at - n_pre - 240: beat_at + n_main].copy()  # 5 ms pre-roll before the first frame
    # loudness match (main part)
    main = clip[n_pre + 240:]
    clip *= 10 ** (-17 / 20) / (np.sqrt((main ** 2).mean()) + 1e-9)
    # edges: 5 ms fade in, tail fade over the last TAIL frames
    clip[:240] *= ramp(240, 0, 1)
    clip[-TAIL * F2S:] *= ramp(TAIL * F2S, 1, 0)

    # scene-specific treatments
    if scene == "s2":  # the call connects: phone band during the pre-roll, full band on the cut
        k = n_pre + 240
        ph = bp(clip[:k + 480], 380, 3000)
        ph = np.tanh(ph * 2.2) / 2.2
        fade_in = ramp(k, 0, 1) ** 1.6
        x = clip.copy()
        x[:k] = ph[:k] * fade_in * 0.9
        xf = ramp(480, 0, 1)
        x[k:k + 480] = ph[k:k + 480] * 0.8 * (1 - xf) + clip[k:k + 480] * xf
        clip = x
    if scene == "s3":  # tuning in: band-limited sweep opening up over 12 frames
        k = 240 + 12 * F2S
        swept = tv_filter(clip[:k], "bandpass", lambda p: (300 + 1500 * p, 2400 + 15000 * p ** 2))
        w = ramp(k, 0, 1) ** 1.3
        clip[:k] = swept * (1 - w) + clip[:k] * w
    if scene == "s6":  # filter down into the orange flood
        k0 = (f1 - 18 - f0) * F2S + 240
        clip[k0:] = tv_filter(clip[k0:], "lowpass", lambda p: 16000 * (0.03 ** p))
    if scene == "s8":  # thins out under the sun flare
        k0 = (f1 - 28 - f0) * F2S + 240
        clip[k0:] = tv_filter(clip[k0:], "highpass", lambda p: 30 + 2600 * p ** 1.5) * ramp(len(clip) - k0, 1, 0.55)
    if scene == "s9":  # the call collapses back into the phone line
        k0 = (f0 + 76 - f0) * F2S + 240
        ph = tv_filter(clip[k0:], "bandpass", lambda p: (200 + 500 * p, 6000 - 3200 * p))
        clip[k0:] = ph * ramp(len(clip) - k0, 1, 0) ** 1.2

    pos = f0 * F2S - n_pre - 240
    bed[pos: pos + len(clip)] += clip

    # accents: pick the beat (from the allowed offsets) with the strongest snare in the stretched audio
    hi_st = band_flux(st.mean(1), SR, 1500, 6000, hop=400)  # 120 hop/s
    fine = band_flux(st.mean(1), SR, 1500, 6000, hop=100)   # 480 hop/s, for attack timing
    for name, (want, opts) in accs.items():
        best = max(opts, key=lambda o: hi_st[int((beat_at + o * F2S) / 400) - 1: int((beat_at + o * F2S) / 400) + 2].max())
        # snap to the frame of the actual snare attack (within +-2 frames of the beat)
        c = beat_at + best * F2S
        lo, hi = (c - 2 * F2S) // 100, (c + 2 * F2S) // 100
        k = lo + int(np.argmax(fine[lo:hi]))
        accents[name] = f0 + int(round((k * 100 - beat_at) / F2S))
    report[scene] = {"song": song, "start_s": round(float(b), 3), "bpm": round(float(local_bpm), 1),
                     "stretch": round(float(R), 4), "align_ms": round(lag / SR * 1000, 1)}
    print(f"{scene} {song:16s} start {b:6.2f}s  {local_bpm:6.1f} bpm  x{R:.3f}  align {lag / SR * 1000:+.1f} ms")

bed = bed[:N]
sf.write("audio/music_bed.wav", bed, SR, subtype="FLOAT")
acc = {k: v for k, v in accents.items() if k[:2] not in ("s6", "s7") or k in ("s7d",)}
acc["s6"] = [accents["s6a"], accents["s6b"], accents["s6c"]]
acc["s7"] = [accents["s7a"], accents["s7b"], accents["s7c"]]
acc["scenes"] = report
json.dump(acc, open("assets/data/accents.json", "w"), indent=1)
print("accents:", {k: v for k, v in acc.items() if k != "scenes"})
