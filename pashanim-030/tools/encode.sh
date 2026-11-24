#!/usr/bin/env bash
# Frames + score -> final MP4 (1920x1080, 60 fps, H.264 High, AAC).
# Post: chromatic-aberration pulses on the big hits, fine temporal luma grain,
# explicit BT.709 conversion/tagging so colours match the browser render.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p out
HITS="between(n,300,304)+between(n,350,352)+between(n,400,404)+between(n,425,427)+between(n,800,803)"
ffmpeg -hide_banner -loglevel error -y \
  -framerate 60 -i frames/f%04d.png -i audio/score.wav \
  -filter_complex "[0:v]format=gbrp,rgbashift=rh=-6:bh=6:enable='${HITS}',scale=out_color_matrix=bt709:out_range=tv,format=yuv444p,noise=c0s=5:c0f=t+u,format=yuv420p[v]" \
  -map "[v]" -map 1:a \
  -c:v libx264 -preset slow -crf 18 -profile:v high -pix_fmt yuv420p \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
  -c:a aac -b:a 256k -ar 48000 -movflags +faststart -shortest \
  out/pashanim-030.mp4
ffprobe -v error -show_entries format=duration,size,bit_rate -show_entries stream=codec_name,width,height,r_frame_rate,nb_frames -of compact out/pashanim-030.mp4
