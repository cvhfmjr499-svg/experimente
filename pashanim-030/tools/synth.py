"""Sound design + final mix for the PASHANIM // 030 edit.

The music is his own songs (tools/medley.py builds audio/music_bed.wav). This
script synthesizes the sound design from scratch (no samples: DTMF "030" dial
tones, impacts, whooshes, thunder, split-flap clatter, chart-counter ticks, the
German busy tone), schedules every hit in *frames* from the shared timeline
(assets/data/timeline.json) and the song accents (assets/data/accents.json),
keeps it well under the songs, and masters the result.

Also writes assets/data/events.js(on): timeline, accents, split-flap board and
chart-counter schedules, plus per-frame band envelopes of the final mix that
drive the audio-reactive visuals.

usage: python tools/synth.py   (after tools/medley.py)
"""
import json

import numpy as np
import scipy.signal as sg
from scipy.io import wavfile
from scipy.ndimage import maximum_filter1d

SR, FPS = 48000, 60
F2S = SR // FPS  # 800 samples per frame
TL = json.load(open("assets/data/timeline.json"))
FRAMES = TL["frames"]
N = FRAMES * F2S
L = N + SR * 3  # room for tails, trimmed at the end
T = {k: v[0] for k, v in TL["scenes"].items()}          # scene cut frames
E = {k: v[0] + v[1] for k, v in TL["scenes"].items()}   # scene end frames
ACC = json.load(open("assets/data/accents.json"))
BED_PATH = "audio/music_bed.wav"
HIT = 0.55  # extra trim on the big hits: the songs come first

rng = np.random.default_rng(30)

def fr(f):
    return int(round(f * F2S))


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tt(n):
    return np.arange(n, dtype=np.float64) / SR


STEMS = ["sfx", "dtmf", "verb_send"]
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



# ------------------------------------------------------------- sound design
def roll(v_from, v_to, f0, f1, n=13):
    """chart counter: values from v_from down to v_to, decelerating, landing on f1"""
    vals = sorted(set(int(round(v)) for v in np.geomspace(v_from, v_to, n)), reverse=True)
    k = len(vals) - 1
    frames = [int(round(f0 + (f1 - f0) * (1 - (1 - i / k) ** 1.8))) for i in range(len(vals))]
    return {"values": vals, "frames": frames}


cb = crackle_bed(N, 1.0)
env = np.full(N, 0.35)
env[:fr(100)] = np.linspace(1, 0.35, fr(100))
place("sfx", cb * env, 0)

# S1: dialing 0-3-0, portal whoosh into the call
for f, d in [(0, "0"), (25, "3"), (50, "0")]:
    place("dtmf", dtmf(d, level=0.62), fr(f), send=0.25)
    place("sfx", impact(0.42, dur=0.55, f0=120, f1=48), fr(f), send=0.2)
    place("sfx", hat(0.4, dec=0.02), fr(f), pan=0.2)
place("sfx", whoosh(34 / 60, 200, 9000, 0.32, rising=True, pan_from=0.0, pan_to=0.0), fr(66), send=0.2)
place("sfx", impact(0.35, dur=0.6, f0=80, f1=40), fr(T["s2"]))

# S2: Hauseingang card slides in; zip line into S3
place("sfx", whoosh(0.2, 700, 7000, 0.14, rising=False, pan_from=0.8, pan_to=0.2), fr(ACC["s2b"] - 8))
place("sfx", zip_sound(0.2, 0.3), fr(E["s2"] - 14), pan=-0.2, send=0.2)

# S3: radio static, three chart counters (DE / AT / CH) landing on snares
place("sfx", static_burst(0.45, 0.22), fr(T["s3"]), pan=0.1, send=0.15)
COUNTERS = {"de": roll(100, 2, T["s3"] + 22, ACC["s3"], 14),
            "at": roll(48, 6, ACC["s3b"] - 14, ACC["s3b"], 9),
            "ch": roll(60, 13, ACC["s3c"] - 14, ACC["s3c"], 9)}
for key, c in COUNTERS.items():
    for i, f in enumerate(c["frames"]):
        last = i == len(c["frames"]) - 1
        place("sfx", tick(0.5 if last else 0.28, 3600 + 60 * i + (0 if key == "de" else 300)), fr(f), pan=-0.3 if key == "de" else 0.3)
place("sfx", tv_filter(noise(fr(14)), "bandpass", lambda p: (2000 + 4000 * p, 9000), order=1) * 0.12, fr(E["s3"] - 14), pan=0.1)

# S4: thunder on the cut + extra strikes on snares, #1 slam, riser into the drop
place("sfx", thunder(0.9 * HIT), fr(T["s4"]), send=0.35)
place("sfx", thunder(0.28 * HIT, 0.9), fr(T["s4"] + 4), pan=0.4)
place("sfx", thunder(0.22 * HIT, 0.9), fr(T["s4"] + 9), pan=-0.4)
place("sfx", thunder(0.45 * HIT, 1.6), fr(ACC["s4b"]), pan=-0.3, send=0.25)
place("sfx", thunder(0.35 * HIT, 1.4), fr(ACC["s4c"]), pan=0.35, send=0.25)
place("sfx", impact(0.45 * HIT, dur=1.0, f0=120, f1=45), fr(ACC["s4"]), send=0.2)
place("sfx", riser(1.0, 0.36 * 0.8), fr(E["s4"] - 60), send=0.25)

# S5: drop, tiles, stamp, card flip to Mittelmeer + re-stamp, whip out
place("sfx", impact(1.0 * HIT, dur=2.4), fr(T["s5"]), send=0.4)
place("sfx", crash(0.55 * HIT), fr(T["s5"]), send=0.3)
for i, f in enumerate([2, 8, 14, 20]):
    place("sfx", whoosh(0.16, 900, 7000, 0.12, rising=False, pan_from=-0.7 + i * 0.45, pan_to=-0.5 + i * 0.45), fr(T["s5"] + f))
place("sfx", impact(0.5 * HIT, dur=0.5, f0=140, f1=60), fr(ACC["s5"]))
place("sfx", whoosh(0.26, 300, 5000, 0.2, rising=False, pan_from=-0.6, pan_to=0.6), fr(ACC["s5b"] - 4), send=0.15)
place("sfx", impact(0.5 * HIT, dur=0.5, f0=150, f1=65), fr(ACC["s5c"]))
place("sfx", whoosh(0.22, 400, 8000, 0.3, rising=False, pan_from=0.8, pan_to=-0.8), fr(E["s5"] - 10), send=0.15)

# S6: split-flap board (schedule shared with the composition), row scan, flood
BOARD_ROWS = [
    ("2021", "SOMMERGEWITTER", "#1"),
    ("2024", "MITTELMEER", "#1"),
    ("2025", "SHABAB(E)S IM VIP", "#1"),
    ("2026", "LOUNGE MUSIK", "#1"),
]
CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#()"
board, flips_all = [], []
for r, (yr, title, pk) in enumerate(BOARD_ROWS):
    text = (yr + " " + title.ljust(17) + " " + pk)
    row = []
    for c, ch in enumerate(text):
        start = T["s6"] + r * 3 + (c % 3)
        settle = int(round(T["s6"] + 6 + r * 7 + c * 1.5))
        steps, f = [], start
        while f < settle:
            steps.append([f, CHARSET[int(rng.integers(len(CHARSET)))]])
            f += 3
        steps.append([settle, ch])
        row.append({"steps": steps})
        flips_all += [s[0] for s in steps]
    board.append({"text": text, "cells": row})
for f in flips_all:
    place("sfx", flap_click(0.03), fr(f) + int(rng.integers(0, 600)), pan=float(rng.uniform(-0.6, 0.6)))
for f in ACC["s6"]:
    for j in range(6):
        place("sfx", flap_click(0.035), fr(f) + j * 220, pan=float(rng.uniform(-0.3, 0.3)))
place("sfx", whoosh(0.3, 150, 2500, 0.22, rising=True), fr(E["s6"] - 18), send=0.3)

# S7: badges, tracklist ticker, tilt up
for f, p in zip(ACC["s7"], (988, 1175, 1319)):
    place("sfx", pop(p, 0.28), fr(f), pan=(f - ACC["s7"][1]) / 60, send=0.2)
place("sfx", whoosh(0.22, 500, 6000, 0.12, rising=False, pan_from=-0.8, pan_to=0.6), fr(ACC["s7d"] - 6))
place("sfx", whoosh(0.24, 300, 9000, 0.32, rising=False, pan_from=0, pan_to=0), fr(E["s7"] - 14), send=0.2)

# S8: headline swap, flare riser
place("sfx", whoosh(0.2, 800, 6000, 0.1, rising=False, pan_from=0.4, pan_to=-0.4), fr(ACC["s8b"] - 6), send=0.2)
place("sfx", riser(0.55, 0.3), fr(E["s8"] - 33), send=0.2)

# S9: final hit, then the call ends (German busy tone, 425 Hz)
place("sfx", impact(1.0 * HIT, dur=2.6, f0=100, f1=30), fr(T["s9"]), send=0.5)
place("sfx", crash(0.6 * HIT), fr(T["s9"]), send=0.4)
BUSY = [T["s9"] + 90, T["s9"] + 108]
for f in BUSY:
    n = int(0.16 * SR)
    beep = bp(np.sin(2 * np.pi * 425 * tt(n)), 300, 3400)
    place("dtmf", fade(beep * 0.3, 0.004, 0.02), fr(f), send=0.15)

# ----------------------------------------------------------------- mix
irn = int(2.2 * SR)
it = tt(irn)
ir = np.stack([lp(noise(irn), 6500), lp(noise(irn), 6500)], 1) * np.exp(-it / 0.36)[:, None]
ir[: int(0.012 * SR)] = 0
ir /= np.sqrt((ir ** 2).sum(0))
verb = np.stack([sg.fftconvolve(st["verb_send"][:, c], ir[:, c])[:L] for c in range(2)], 1)
verb = hp(verb, 220)

sr_, bed = wavfile.read(BED_PATH)
assert sr_ == SR
bed_full = np.zeros((L, 2))
bed_full[: min(L, len(bed))] = bed[:L]
GAINS = {"sfx": 0.17, "dtmf": 0.38}
mix = bed_full + sum(st[k] * g for k, g in GAINS.items()) + verb * 0.1
mix = hp(mix, 28)[:N]

# look-ahead peak limiter (clean transients, headroom for AAC overshoot)
mix *= 10 ** (-13.6 / 20) / np.sqrt((mix ** 2).mean())
look = int(0.004 * SR)
pk = maximum_filter1d(np.abs(mix).max(1), size=2 * look + 1)
g = np.minimum(1.0, 0.62 / np.maximum(pk, 1e-9))
rel = np.exp(-1 / (0.09 * SR))
gs = np.empty_like(g)
cur = 1.0
for i in range(len(g)):
    cur = g[i] if g[i] < cur else g[i] + (cur - g[i]) * rel
    gs[i] = cur
mix *= gs[:, None]
mix = np.clip(mix, -0.7, 0.7)
mix[-int(0.08 * SR):] *= np.linspace(1, 0, int(0.08 * SR))[:, None]
wavfile.write("audio/score.wav", SR, mix.astype(np.float32))
print("score.wav  %.2f s  peak %.3f  rms %.1f dBFS" % (len(mix) / SR, np.abs(mix).max(), 20 * np.log10(np.sqrt((mix ** 2).mean()))))

# chromatic-aberration pulses for tools/encode.sh (big hits)
CA = [(T["s4"], 4), (ACC["s4"], 2), (T["s5"], 4), (ACC["s5"], 2), (ACC["s5c"], 2), (T["s9"], 3)]
open("audio/ca_hits.txt", "w").write("+".join(f"between(n,{a},{a + d})" for a, d in CA))


# ---------------------------------------------------- per-frame features
def band_env(x, lo, hi):
    y = sg.sosfilt(sg.butter(4, [lo, hi], "bandpass", fs=SR, output="sos"), x[:N].mean(1))
    e = np.sqrt((y.reshape(FRAMES, F2S) ** 2).mean(1))
    return (e / (e.max() + 1e-9)).round(4).tolist()


def full_env(x):
    m = x[:N].mean(1)
    e = np.sqrt((m.reshape(FRAMES, F2S) ** 2).mean(1))
    return (e / (e.max() + 1e-9)).round(4).tolist()


features = {"kick": band_env(mix, 30, 120), "bass": band_env(mix, 60, 250), "snare": band_env(mix, 1500, 5000),
            "hats": band_env(mix, 6000, 16000), "lead": band_env(mix, 300, 2000), "mix": full_env(mix)}
acc_out = {k: v for k, v in ACC.items() if k != "scenes"}
events = {"fps": FPS, "frames": FRAMES, "timeline": TL["scenes"], "acc": acc_out, "busy": BUSY,
          "board": board, "counters": COUNTERS, "counter": COUNTERS["de"], "features": features,
          "songs": {k: v["song"] for k, v in ACC["scenes"].items()}}
with open("assets/data/events.json", "w") as f:
    json.dump(events, f)
with open("assets/data/events.js", "w") as f:
    f.write("window.EVENTS = " + json.dumps(events) + ";\n")
print("events.json written; frames", FRAMES, "board flips", len(flips_all))
