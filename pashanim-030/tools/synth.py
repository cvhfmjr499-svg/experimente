"""Original score + sound design for the PASHANIM // 030 edit.

Everything is synthesized from scratch (no samples): 144 BPM, 48 kHz, which
makes one beat exactly 20000 samples = 25 video frames at 60 fps, and the
15 s edit exactly 9 bars. Every sound-design hit is scheduled in *frames*, the
same frame numbers the composition uses, so picture and sound cannot drift.

Also writes assets/data/events.json: shared schedules (split-flap board,
chart counter) + per-frame audio envelopes that drive audio-reactive visuals.

usage: python tools/synth.py   (from the project root)
"""
import json

import numpy as np
import scipy.signal as sg
from scipy.io import wavfile


def sf_read(path):
    sr, x = wavfile.read(path)
    return x.astype(np.float64), sr

SR = 48000
BPM = 144
FPS = 60
BEAT = SR * 60 // BPM  # 20000
S16 = BEAT // 4  # 5000
BAR = BEAT * 4  # 80000
FRAMES = 900
N = FRAMES * SR // FPS  # 720000 (15 s)
L = N + SR * 3  # room for tails, trimmed at the end
F2S = SR // FPS  # 800 samples per frame

rng = np.random.default_rng(30)

# When tools/medley.py has built a bed from his songs, the synthesized music
# stems are muted and only the sound design is kept, re-timed to the accents.
import os  # noqa: E402
BED_PATH, ACC_PATH = "audio/music_bed.wav", "assets/data/accents.json"
USE_BED = os.path.exists(BED_PATH) and os.path.exists(ACC_PATH)
HIT = 0.55 if USE_BED else 1.0  # extra trim on the big hits under the songs
ACC = json.load(open(ACC_PATH)) if USE_BED else {"s2": 150, "s3": 250, "s4": 350, "s5": 425, "s7": [625, 650, 675]}


def fr(f):
    return int(round(f * F2S))


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tt(n):
    return np.arange(n, dtype=np.float64) / SR


STEMS = ["kick", "snare", "hats", "bass", "pad", "lead", "sfx", "dtmf", "verb_send"]
st = {k: np.zeros((L, 2), np.float64) for k in STEMS}


def place(stem, sig, start, gain=1.0, pan=0.0, send=0.0):
    sig = np.asarray(sig, np.float64)
    if sig.ndim == 1:
        a = (pan + 1) * np.pi / 4
        sig = np.stack([sig * np.cos(a), sig * np.sin(a)], 1) * np.sqrt(2)
    s = int(start)
    if s < 0:
        sig = sig[-s:]
        s = 0
    e = min(L, s + len(sig))
    if e <= s:
        return
    st[stem][s:e] += sig[: e - s] * gain
    if send:
        st["verb_send"][s:e] += sig[: e - s] * gain * send


def fade(sig, fin=0.002, fout=0.01):
    n = len(sig)
    a, b = int(fin * SR), int(fout * SR)
    env = np.ones(n)
    if a:
        env[: min(a, n)] = np.linspace(0, 1, min(a, n))
    if b:
        env[max(0, n - b):] *= np.linspace(1, 0, n - max(0, n - b))
    return sig * (env if sig.ndim == 1 else env[:, None])


def bp(x, lo, hi, order=2):
    sos = sg.butter(order, [lo, hi], "bandpass", fs=SR, output="sos")
    return sg.sosfilt(sos, x, axis=0)


def hp(x, f, order=2):
    return sg.sosfilt(sg.butter(order, f, "highpass", fs=SR, output="sos"), x, axis=0)


def lp(x, f, order=2):
    return sg.sosfilt(sg.butter(order, f, "lowpass", fs=SR, output="sos"), x, axis=0)


def tv_filter(x, kind, cut_fn, block=256, order=2):
    """time-varying butterworth: cutoff (or (lo,hi)) evaluated per block."""
    y = np.zeros_like(x)
    zi = None
    for i in range(0, len(x), block):
        c = cut_fn((i + block / 2) / len(x))
        sos = sg.butter(order, c, kind, fs=SR, output="sos")
        if zi is None:
            zi = np.zeros((sos.shape[0], 2))
        y[i:i + block], zi = sg.sosfilt(sos, x[i:i + block], zi=zi)
    return y


def noise(n):
    return rng.standard_normal(n)


# ----------------------------------------------------------------- instruments
def kick(level=1.0, f0=170.0, f1=50.0, pdec=0.032, adec=0.13, dur=0.36):
    n = int(dur * SR)
    t = tt(n)
    freq = f1 + (f0 - f1) * np.exp(-t / pdec)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t / adec)
    click = hp(noise(n), 2500) * np.exp(-t / 0.003) * 0.4
    return fade(np.tanh(1.15 * (body + click)) * level, 0.0005, 0.02)


def snare(level=1.0, tone=190.0, dur=0.32):
    n = int(dur * SR)
    t = tt(n)
    body = np.sin(2 * np.pi * tone * t) * np.exp(-t / 0.045) * 0.6
    nz = bp(noise(n), 1200, 7000) * np.exp(-t / 0.09)
    # clap layers: three quick bursts
    clap = np.zeros(n)
    for k, off in enumerate([0.0, 0.009, 0.019]):
        o = int(off * SR)
        m = n - o
        clap[o:] += bp(noise(m), 900, 3200) * np.exp(-tt(m) / (0.006 if k < 2 else 0.07))
    return fade(np.tanh(1.3 * (body + 0.55 * nz + 0.9 * clap)) * level, 0.0005, 0.03)


HAT_FREQS = np.array([205.3, 304.4, 369.6, 522.7, 540.0, 800.0]) * 1.71


def hat(level=1.0, dec=0.028, dur=None):
    dur = dur or max(0.06, dec * 5)
    n = int(dur * SR)
    t = tt(n)
    metal = sum(np.sign(np.sin(2 * np.pi * f * t + i)) for i, f in enumerate(HAT_FREQS))
    sig = hp(bp(metal, 6000, 15000), 7000) * 0.5 + hp(noise(n), 8000) * 0.25
    return fade(sig * np.exp(-t / dec) * level, 0.0003, 0.005)


def crash(level=1.0, dur=1.9):
    n = int(dur * SR)
    t = tt(n)
    metal = sum(np.sign(np.sin(2 * np.pi * f * 1.37 * t + i)) for i, f in enumerate(HAT_FREQS))
    sig = hp(bp(metal, 3500, 14000), 3000) * 0.35 + hp(noise(n), 4500) * 0.6
    env = np.exp(-t / 0.55) * (1 - np.exp(-t / 0.002))
    st_sig = np.stack([sig, np.roll(sig, 37)], 1) * env[:, None]
    return fade(st_sig * level, 0.0005, 0.2)


def bass808(m, dur, level=1.0, glide_from=None):
    n = int(dur * SR)
    t = tt(n)
    f = mtof(m)
    if glide_from is not None:
        f0 = mtof(glide_from)
        freq = f + (f0 - f) * np.exp(-t / 0.06)
    else:
        freq = f * (1 + 0.5 * np.exp(-t / 0.012))
    x = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    env = np.minimum(1, t / 0.003) * (0.45 + 0.55 * np.exp(-t / 0.28))
    y = np.tanh(2.0 * x) * env
    return fade(lp(y, 1400) * level, 0.0008, 0.03)


def saw(f, n, phase=0.0):
    ph = (f * tt(n) + phase) % 1.0
    return 2 * ph - 1


def pad_chord(notes, dur, cutoff, level=1.0, attack=0.25, release=0.35, sweep=None):
    n = int((dur + release) * SR)
    t = tt(n)
    out = np.zeros((n, 2))
    for i, m in enumerate(notes):
        f = mtof(m)
        for ch, dets in enumerate([(-8, 4), (8, -4)]):
            v = sum(saw(f * 2 ** (d / 1200), n, rng.random()) for d in dets) / 2
            out[:, ch] += v
    out /= max(1, len(notes))
    if sweep:
        out = np.stack([tv_filter(out[:, c], "lowpass", lambda p: float(np.clip(sweep(p), 80, 18000)))
                        for c in range(2)], 1)
    else:
        out = lp(out, cutoff)
    env = np.minimum(1, t / attack) * np.clip((dur + release - t) / release, 0, 1)
    # gentle tremolo for life
    env *= 1 + 0.06 * np.sin(2 * np.pi * 0.37 * t)
    return out * env[:, None] * level


def bell(m, dur=1.4, level=1.0, ratio=3.5, index=2.4):
    n = int(dur * SR)
    t = tt(n)
    f = mtof(m)
    mod = index * np.exp(-t / 0.22) * np.sin(2 * np.pi * f * ratio * t)
    y = np.sin(2 * np.pi * f * t + mod) * np.exp(-t / 0.55)
    y += 0.25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.18)
    return fade(y * level, 0.001, 0.05)


def pluck(m, dur=0.45, level=1.0):
    n = int(dur * SR)
    t = tt(n)
    f = mtof(m)
    y = sum((1 / k) * np.sin(2 * np.pi * k * f * t) * np.exp(-t * (4 + 6 * k)) for k in range(1, 8))
    return fade(y * level, 0.0008, 0.03)


DTMF = {"0": (941, 1336), "3": (697, 1477)}


def dtmf(d, dur=0.17, level=1.0):
    n = int(dur * SR)
    t = tt(n)
    lo, hi = DTMF[d]
    y = 0.5 * np.sin(2 * np.pi * lo * t) + 0.5 * np.sin(2 * np.pi * hi * t)
    y = bp(np.tanh(1.4 * y), 300, 3400)
    return fade(y * level, 0.003, 0.02)


def impact(level=1.0, dur=2.2, f0=95.0, f1=32.0):
    n = int(dur * SR)
    t = tt(n)
    freq = f1 + (f0 - f1) * np.exp(-t / 0.25)
    sub = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t / 0.7)
    burst = lp(noise(n), 2500) * np.exp(-t / 0.08) * 0.6
    return fade(np.tanh(1.4 * (sub + burst)) * level, 0.0005, 0.3)


def whoosh(dur, lo=250, hi=6000, level=1.0, rising=True, pan_from=-0.6, pan_to=0.6):
    n = int(dur * SR)
    x = noise(n)

    def band(p):
        q = p if rising else 1 - p
        c = lo * (hi / lo) ** q
        return (max(30, c * 0.6), min(20000, c * 1.6))

    y = tv_filter(x, "bandpass", band, order=1)
    p = np.linspace(0, 1, n)
    env = np.sin(np.pi * np.clip(p, 0, 1)) ** 1.5 if not rising else p ** 2.2 * (1 - np.exp(-(1 - p) * 40))
    y = y * env * level
    pan = np.linspace(pan_from, pan_to, n)
    a = (pan + 1) * np.pi / 4
    return np.stack([y * np.cos(a), y * np.sin(a)], 1) * np.sqrt(2)


def riser(dur, level=1.0):
    n = int(dur * SR)
    t = tt(n)
    p = t / (dur)
    f = 110 * (8 ** p)
    tone = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.25 + saw(1, n) * 0
    tone = lp(tone, 3000)
    nz = tv_filter(noise(n), "bandpass", lambda q: (300 * 20 ** q, min(20000, 900 * 20 ** q)), order=1)
    y = (tone * 0.5 + nz * 1.2) * p ** 2.5
    return y * level


def thunder(level=1.0, dur=2.6):
    n = int(dur * SR)
    t = tt(n)
    crack = hp(noise(n), 900) * np.exp(-t / 0.035) * 1.2
    # crackle: sparse impulses in the first 300 ms
    imp = np.zeros(n)
    k = int(0.35 * SR)
    idx = rng.choice(k, 160, replace=False)
    imp[idx] = rng.standard_normal(160) * np.exp(-idx / (0.12 * SR))
    crackle = bp(imp, 1500, 9000) * 18
    rumble = lp(noise(n), 140, order=4) * 9 * (1 - np.exp(-t / 0.05)) * np.exp(-t / 0.9)
    rumble *= 1 + 0.5 * np.sin(2 * np.pi * 3.1 * t)
    y = np.tanh(crack + crackle + rumble)
    return fade(np.stack([y, np.roll(y, 211)], 1) * level, 0.0003, 0.4)


def static_burst(dur=0.45, level=1.0):
    n = int(dur * SR)
    t = tt(n)
    nz = bp(noise(n), 700, 4500) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 37 * t)))
    chirp = np.sin(2 * np.pi * np.cumsum(2200 - 1800 * (t / dur)) / SR) * 0.3
    env = np.minimum(1, t / 0.01) * np.exp(-t / 0.16)
    return fade((nz + chirp) * env * level, 0.002, 0.05)


def zip_sound(dur=0.2, level=1.0):
    n = int(dur * SR)
    t = tt(n)
    f = 500 * (8 ** (t / dur))
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-((t - dur * 0.6) / (dur * 0.35)) ** 2)
    y += hp(noise(n), 5000) * 0.15 * np.exp(-((t - dur * 0.7) / (dur * 0.2)) ** 2)
    return fade(y * level, 0.002, 0.02)


def tick(level=1.0, f=3800.0):
    n = int(0.018 * SR)
    t = tt(n)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.0025) + hp(noise(n), 3000) * np.exp(-t / 0.0012) * 0.6
    return y * level


def flap_click(level=1.0):
    n = int(0.02 * SR)
    t = tt(n)
    f = rng.uniform(2300, 3600)
    y = bp(noise(n), 1500, 6000) * np.exp(-t / 0.0018) + 0.4 * np.sin(2 * np.pi * f * t) * np.exp(-t / 0.003)
    return y * level


def pop(f0, level=1.0):
    n = int(0.12 * SR)
    t = tt(n)
    f = f0 * (1 + 0.35 * (1 - np.exp(-t / 0.02)))
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.045)
    return fade(y * level, 0.0008, 0.02)


def crackle_bed(n, level=1.0):
    y = lp(noise(n), 5000) * 0.03
    idx = rng.choice(n, int(n / SR * 22), replace=False)
    imp = np.zeros(n)
    imp[idx] = rng.standard_normal(len(idx))
    y += bp(imp, 800, 7000) * 1.4
    return y * level


# --------------------------------------------------------------- arrangement
def bar_s(b, s16=0.0):
    return int(b * BAR + s16 * S16)


F_ = [53, 57, 60, 64]
G_ = [55, 59, 62, 64]
AM = [57, 60, 64, 67, 71]
F11 = [53, 57, 60, 64, 71]
AMF = [45, 52, 57, 59, 60, 64]
CHORDS = [F_, F_, G_, AM, F_, G_, AM, F11, AMF]
ROOT = [29, 29, 31, 33, 29, 31, 33, 29, 33]  # 808 roots (F1 G1 A1)

# --- pads
place("pad", pad_chord(F_, 1.75, 0, level=0.55, attack=0.9, sweep=lambda p: 260 + 500 * p), bar_s(0, 4), pan=0, send=0.5)
for b in (1, 2):
    place("pad", pad_chord(CHORDS[b], 1.72, 1500, level=0.55), bar_s(b), send=0.35)
place("pad", pad_chord(AM, 1.6, 0, level=0.58, sweep=lambda p: 1200 + 5200 * p ** 2), bar_s(3), send=0.35)
for b in (4, 5, 6):
    place("pad", pad_chord(CHORDS[b], 1.72, 2600, level=0.5, attack=0.04), bar_s(b), send=0.3)
place("pad", pad_chord(F11, 1.72, 3200, level=0.6, attack=0.18), bar_s(7), send=0.6)
place("pad", pad_chord(AMF, 1.55, 2800, level=0.75, attack=0.004, release=1.3), bar_s(8), send=0.9)

# --- drums
KICKS = {1: [0, 6, 10], 2: [0, 3, 10, 14], 3: [0, 6, 10], 4: [0, 6, 10], 5: [0, 6, 10, 11],
         6: [0, 8, 10], 7: [0, 10]}
SNARES = {1: [8], 2: [8], 3: [8], 4: [4, 12], 5: [4, 12], 6: [4, 12], 7: [8]}
GHOST = {4: [7, 15], 5: [7, 14], 6: [15]}
for b, ks in KICKS.items():
    for k in ks:
        place("kick", kick(0.95), bar_s(b, k))
for b, ss in SNARES.items():
    for s in ss:
        place("snare", snare(0.8), bar_s(b, s), send=0.22)
for b, ss in GHOST.items():
    for s in ss:
        place("snare", snare(0.22, tone=230), bar_s(b, s), pan=0.15)
# build-up snare roll (bar 3, beat 3.. end) and fill into the end card (bar 7)
for i in range(8):
    place("snare", snare(0.18 + 0.05 * i, tone=200 + 8 * i), bar_s(3, 9 + i * 0.75), send=0.15)
for i in range(6):
    place("snare", snare(0.22 + 0.07 * i, tone=180 + 12 * i), bar_s(7, 12 + i * 0.5), send=0.2)

# hats: half-time sections 8ths (+rolls); drop sections shuffled 16ths
for b in (1, 2, 3, 7):
    for s in range(0, 16, 2):
        place("hats", hat(0.5 if s % 4 else 0.62), bar_s(b, s), pan=0.25)
for b, s0 in [(1, 14), (2, 6), (7, 6)]:
    for j in range(3):
        place("hats", hat(0.35), bar_s(b, s0 + j * 2 / 3), pan=0.25)
for s in range(12, 16):
    place("hats", hat(0.45), bar_s(3, s + 0.5), pan=0.25)
for b in (4, 5, 6):
    for s in range(16):
        sw = 0.12 if s % 2 else 0.0
        lvl = 0.62 if s % 4 == 2 else (0.32 if s % 2 else 0.42)
        if s % 4 == 2:
            place("hats", hat(lvl * 0.75, dec=0.11), bar_s(b, s + sw), pan=0.3)
        else:
            place("hats", hat(lvl), bar_s(b, s + sw), pan=0.3)
place("sfx", crash(0.55 * HIT), bar_s(4), send=0.3)
if not USE_BED:
    place("sfx", crash(0.3), bar_s(7), send=0.4)
place("sfx", crash(0.6 * HIT), bar_s(8), send=0.4)

# --- 808
prev = None
for b in range(1, 8):
    ks = KICKS[b]
    for i, k in enumerate(ks):
        nxt = ks[i + 1] if i + 1 < len(ks) else 16
        dur = (nxt - k) * S16 / SR + 0.02
        m = ROOT[b] + (12 if (b in (2, 5) and k == 14) else 0)
        place("bass", bass808(m, dur, 0.95, glide_from=prev if (k == 0 and prev and prev != m) else None), bar_s(b, k))
        prev = m
place("bass", bass808(ROOT[8], 1.6, 1.0, glide_from=ROOT[7]), bar_s(8))

# --- plucks before the drop, bells after
for b in (1, 2, 3):
    notes = CHORDS[b]
    for j in range(8):
        m = notes[(j * 2 + (j // 4)) % len(notes)] + 12
        place("lead", pluck(m, 0.4, 0.22), bar_s(b, j * 2), pan=(-0.35 if j % 2 else 0.35), send=0.25)
MEL = {
    4: [(0, 81, 3), (3, 79, 3), (6, 76, 2), (8, 72, 2), (10, 76, 2), (12, 79, 2), (14, 81, 2)],
    5: [(0, 79, 3), (3, 76, 3), (6, 74, 2), (8, 71, 2), (10, 74, 2), (12, 76, 2), (14, 79, 2)],
    6: [(0, 81, 3), (3, 79, 3), (6, 76, 2), (8, 72, 2), (10, 76, 2), (12, 83, 2), (14, 81, 2)],
    7: [(0, 76, 8), (8, 72, 4), (12, 74, 4)],
}
for b, ns in MEL.items():
    for s, m, ln in ns:
        y = bell(m, 1.3 if ln < 4 else 2.2, 0.36)
        place("lead", y, bar_s(b, s), pan=-0.12, send=0.35)
        # dotted-8th ping-pong echo
        place("lead", lp(y, 3500) * 0.33, bar_s(b, s + 3), pan=0.7, send=0.2)
        place("lead", lp(y, 2500) * 0.16, bar_s(b, s + 6), pan=-0.7, send=0.2)

# ------------------------------------------------------------- sound design
place("sfx", crackle_bed(N, 1.0) * np.r_[np.linspace(1, 0.35, fr(100)), np.full(N - fr(100), 0.35)], 0)
for f, d in [(0, "0"), (25, "3"), (50, "0")]:
    place("dtmf", dtmf(d, level=0.62), fr(f), send=0.25)
    place("sfx", impact(0.42, dur=0.55, f0=120, f1=48), fr(f), send=0.2)
    place("sfx", hat(0.4, dec=0.02), fr(f), pan=0.2)
place("sfx", whoosh(34 / 60, 200, 9000, 0.32, rising=True, pan_from=0.0, pan_to=0.0), fr(66), send=0.2)
place("sfx", impact(0.35, dur=0.6, f0=80, f1=40), fr(100))
place("sfx", zip_sound(0.2, 0.3), fr(186), pan=-0.2, send=0.2)
place("sfx", static_burst(0.45, 0.22 if USE_BED else 0.42), fr(200), pan=0.1, send=0.15)

# chart counter #100 -> #2 (decelerating), lands on the snare at f250
counter_vals = [100, 86, 71, 55, 42, 31, 22, 15, 10, 7, 5, 4, 3, 2]
counter_frames = [round(222 + (ACC["s3"] - 222) * (1 - (1 - i / (len(counter_vals) - 1)) ** 1.8)) for i in range(len(counter_vals))]
for i, f in enumerate(counter_frames):
    place("sfx", tick(0.28 if i < len(counter_frames) - 1 else 0.5, 3600 + 60 * i), fr(f), pan=-0.3)

place("sfx", tv_filter(noise(fr(14)), "bandpass", lambda p: (2000 + 4000 * p, 9000), order=1) * 0.12, fr(286), pan=0.1)
place("sfx", thunder(0.9 * HIT), fr(300), send=0.35)
place("sfx", thunder(0.28 * HIT, 0.9), fr(304), pan=0.4)
place("sfx", thunder(0.22 * HIT, 0.9), fr(309), pan=-0.4)
place("sfx", impact(0.45 * HIT, dur=1.0, f0=120, f1=45), fr(ACC["s4"]), send=0.2)
place("sfx", riser(1.0, 0.36 * (0.8 if USE_BED else 1)), fr(340), send=0.25)
place("sfx", impact(1.0 * HIT, dur=2.4), fr(400), send=0.4)
for i, f in enumerate([402, 408, 414, 420]):
    place("sfx", whoosh(0.16, 900, 7000, 0.12, rising=False, pan_from=-0.7 + i * 0.45, pan_to=-0.5 + i * 0.45), fr(f))
place("sfx", impact(0.5 * HIT, dur=0.5, f0=140, f1=60), fr(ACC["s5"]))
place("sfx", whoosh(0.22, 400, 8000, 0.3, rising=False, pan_from=0.8, pan_to=-0.8), fr(490), send=0.15)

# split-flap board schedule (shared with the composition)
BOARD_ROWS = [
    ("2021", "SOMMERGEWITTER", "#1"),
    ("2024", "MITTELMEER", "#1"),
    ("2025", "SHABAB(E)S IM VIP", "#1"),
    ("2026", "LOUNGE MUSIK", "#1"),
]
COLS = 4 + 1 + 17 + 1 + 2
CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#()"
board = []
flips_all = []
for r, (yr, title, pk) in enumerate(BOARD_ROWS):
    text = (yr + " " + title.ljust(17) + " " + pk)
    assert len(text) == COLS, text
    row = []
    for c, ch in enumerate(text):
        start = 500 + r * 3 + (c % 3)
        settle = int(round(506 + r * 7 + c * 1.5))
        steps = []
        f = start
        while f < settle:
            steps.append([f, CHARSET[int(rng.integers(len(CHARSET)))]])
            f += 3
        steps.append([settle, ch])
        row.append({"steps": steps})
        flips_all += [s[0] for s in steps]
    board.append({"text": text, "cells": row})
# clatter: one click per flip, slightly humanized
for f in flips_all:
    place("sfx", flap_click(0.03 if USE_BED else 0.05), fr(f) + int(rng.integers(0, 600)), pan=float(rng.uniform(-0.6, 0.6)))

place("sfx", whoosh(0.3, 150, 2500, 0.22, rising=True), fr(582), send=0.3)
for f, p in zip(ACC["s7"], (988, 1175, 1319)):
    place("sfx", pop(p, 0.28), fr(f), pan=(f - 650) / 60, send=0.2)
place("sfx", whoosh(0.24, 300, 9000, 0.32, rising=False, pan_from=0, pan_to=0), fr(686), send=0.2)
rev_sh = pad_chord([76, 79, 83, 88], 0.4, 6000, level=0.3, attack=0.38, release=0.02)
place("sfx", rev_sh, fr(690), send=0.8)
place("sfx", riser(0.55, 0.3), fr(767), send=0.2)
place("sfx", impact(1.0 * HIT, dur=2.6, f0=100, f1=30), fr(800), send=0.5)
# hang-up: German busy tone (425 Hz) twice, phone band-limited
for f in ((852, 874) if USE_BED else (848, 870)):
    n = int(0.16 * SR)
    beep = bp(np.sin(2 * np.pi * 425 * tt(n)), 300, 3400)
    place("dtmf", fade(beep * 0.3, 0.004, 0.02), fr(f), send=0.15)

# ----------------------------------------------------------------- mix
# pre-drop silence (all music stems) f394-f400 except the riser
gap = np.ones(L)
a, b_ = fr(394), fr(400)
gap[a:b_] = 0.0
for k in ("kick", "snare", "hats", "bass", "pad", "lead"):
    st[k] *= gap[:, None]

# sidechain from kick
kenv = np.abs(st["kick"][:, 0])
kenv = sg.lfilter([1 - np.exp(-1 / (0.09 * SR))], [1, -np.exp(-1 / (0.09 * SR))], kenv)
duck = 1 - 0.55 * np.clip(kenv / (kenv.max() + 1e-9) * 2.5, 0, 1)
for k in ("pad", "lead", "bass"):
    st[k] *= duck[:, None] if k != "bass" else (0.35 + 0.65 * duck)[:, None]

# reverb: synthetic stereo IR (RT60 ~1.8 s), convolved with the send bus
irn = int(2.2 * SR)
it = tt(irn)
ir = np.stack([lp(noise(irn), 6500), lp(noise(irn), 6500)], 1) * np.exp(-it / 0.36)[:, None]
ir[: int(0.012 * SR)] = 0
ir /= np.sqrt((ir ** 2).sum(0))
verb = np.stack([sg.fftconvolve(st["verb_send"][:, c], ir[:, c])[:L] for c in range(2)], 1)
verb = hp(verb, 220)

GAINS = {"kick": 0.80, "snare": 0.80, "hats": 0.42, "bass": 0.40, "pad": 0.62, "lead": 0.52,
         "sfx": 0.50, "dtmf": 0.85}
if USE_BED:
    for k in ("kick", "snare", "hats", "bass", "pad", "lead"):
        GAINS[k] = 0.0
    GAINS["sfx"] = 0.17
    GAINS["dtmf"] = 0.38
    bed, bsr = sf_read(BED_PATH)
    assert bsr == SR
    bed_full = np.zeros((L, 2))
    bed_full[: len(bed)] = bed[:L]
mix = sum(st[k] * g for k, g in GAINS.items()) + verb * (0.1 if USE_BED else 0.28)
if USE_BED:
    mix = mix + bed_full * 1.0
mix = hp(mix, 28)
# look-ahead peak limiter (keeps transients clean instead of saturating)
from scipy.ndimage import maximum_filter1d
mix = mix[:N]
target_rms_db = -13.6
mix *= 10 ** (target_rms_db / 20) / np.sqrt((mix ** 2).mean())
look = int(0.004 * SR)
pk = maximum_filter1d(np.abs(mix).max(1), size=2 * look + 1)
thr = 0.62  # leaves headroom for AAC overshoot (true-peak checked after encoding)
g = np.minimum(1.0, thr / np.maximum(pk, 1e-9))
rel = np.exp(-1 / (0.09 * SR))
gs = np.empty_like(g)
cur = 1.0
for i in range(len(g)):  # attack instant (look-ahead covers it), smooth release
    cur = g[i] if g[i] < cur else g[i] + (cur - g[i]) * rel
    gs[i] = cur
mix *= gs[:, None]
mix = np.clip(mix, -0.7, 0.7)
mix[-int(0.08 * SR):] *= np.linspace(1, 0, int(0.08 * SR))[:, None]
wavfile.write("audio/score.wav", SR, mix.astype(np.float32))
rms = np.sqrt((mix ** 2).mean())
print("score.wav  peak %.3f  rms %.1f dBFS" % (np.abs(mix).max(), 20 * np.log10(rms)))

# ---------------------------------------------------- per-frame features
def frame_env(x):
    m = x[:N].mean(1) if x.ndim == 2 else x[:N]
    e = np.sqrt((m.reshape(FRAMES, F2S) ** 2).mean(1))
    return (e / (e.max() + 1e-9)).round(4).tolist()


def band_env(x, lo, hi):
    y = sg.sosfilt(sg.butter(4, [lo, hi], "bandpass", fs=SR, output="sos"), x[:N].mean(1))
    e = np.sqrt((y.reshape(FRAMES, F2S) ** 2).mean(1))
    return (e / (e.max() + 1e-9)).round(4).tolist()


if USE_BED:
    features = {"kick": band_env(mix, 30, 120), "bass": band_env(mix, 60, 250), "snare": band_env(mix, 1500, 5000),
                "hats": band_env(mix, 6000, 16000), "lead": band_env(mix, 300, 2000), "pad": band_env(mix, 300, 2000),
                "sfx": frame_env(st["sfx"])}
else:
    features = {k: frame_env(st[k]) for k in ("kick", "snare", "hats", "bass", "pad", "lead", "sfx")}
features["mix"] = frame_env(mix)
events = {
    "fps": FPS, "frames": FRAMES, "bpm": BPM, "beatFrames": 25,
    "board": board, "counter": {"values": counter_vals, "frames": counter_frames},
    "acc": {k: ACC[k] for k in ("s2", "s3", "s4", "s5", "s7")},
    "features": features,
}
with open("assets/data/events.json", "w") as f:
    json.dump(events, f)
with open("assets/data/events.js", "w") as f:
    f.write("window.EVENTS = " + json.dumps(events) + ";\n")
print("events.json written; board flips:", len(flips_all))
