"""Download the 30 s Deezer previews of the songs used per scene.
Copyrighted recordings: kept out of git (assets/music/ is ignored).
usage: python tools/fetch_music.py"""
import json, os, urllib.request
TRACKS = {  # scene -> Deezer track id
    "hauseingang": 833692572, "airwaves": 957653672, "sommergewitter": 1408516272,
    "mittelmeer": 2835932882, "song_2000": 2835932912, "shababes_im_vip": 3342939491,
    "goldrichtig": 4168776142, "augenblick": 4168776172, "tourlife": 1934501717,
    "doppel_g": 1934501707, "berlin_calling": 4168776232,
}
os.makedirs("assets/music", exist_ok=True)
H = {"User-Agent": "Mozilla/5.0"}
for name, tid in TRACKS.items():
    meta = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.deezer.com/track/{tid}", headers=H), timeout=30))
    data = urllib.request.urlopen(urllib.request.Request(meta["preview"], headers=H), timeout=60).read()
    open(f"assets/music/{name}.mp3", "wb").write(data)
    print(f"{name:16s} {meta['title'][:28]:28s} bpm(deezer)={meta.get('bpm')} {len(data)//1024} KB")
