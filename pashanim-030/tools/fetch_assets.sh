#!/usr/bin/env bash
# Downloads the press photo + cover art used in the edit from public streaming
# CDNs (Deezer / Apple Music). These images are copyrighted by the artist /
# label, so they are NOT committed to the repo: run this to re-create them.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=assets/img/raw
mkdir -p "$OUT"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
get() { curl -fsS --max-time 60 -A "$UA" -o "$OUT/$1" "$2" && echo "  $1"; }
DZ=https://cdn-images.dzcdn.net/images/cover
echo "fetching -> $OUT"
# Apple Music artist image (mirror selfie with the Lounge Musik CD)
get portrait.jpg "https://is1-ssl.mzstatic.com/image/thumb/AMCArtistImages211/v4/4c/78/10/4c781040-b955-4901-ebe6-9aa136f03d35/file_cropped.png/3000x3000bb.jpg"
# Deezer artist image (rooftop / Porsche)
get rooftop.jpg "https://cdn-images.dzcdn.net/images/artist/1082883fffbee1688e1b12fe1e69ba80/1500x1500-000000-80-0-0.jpg"
# Cover art
get lounge_musik.jpg   "$DZ/83600f5e36e92afdb9271a198194d886/1000x1000-000000-80-0-0.jpg"
get album_2000.jpg     "$DZ/942577c10f91bacb7fa2bc683176d472/1000x1000-000000-80-0-0.jpg"
get himmel.jpg         "$DZ/928ee2199e6ba15be3108bfde6673ba5/1000x1000-000000-80-0-0.jpg"
get airwaves.jpg       "$DZ/8fe0cbe64993adffa0d9ea8425d6c0d7/1000x1000-000000-80-0-0.jpg"
get sommergewitter.jpg "$DZ/05ff4ebb64ccb837a771aca759c8956a/1000x1000-000000-80-0-0.jpg"
get mittelmeer.jpg     "$DZ/db56e76f402e7315d3c8eaced2abdad4/1000x1000-000000-80-0-0.jpg"
get gruenewuerfelflow.jpg "$DZ/c06cfdfe97d6dcdd1359fc274e5599fe/1000x1000-000000-80-0-0.jpg"
get hauseingang.jpg    "$DZ/94bff33c052ea31184cd5df3e868954d/1000x1000-000000-80-0-0.jpg"
# The yellow Airwaves pack (Melon Menthol packshot) was supplied by hand: put it at
# assets/img/raw/airwaves_melon.jpg before running prep_images.py.
[ -f "$OUT/airwaves_melon.jpg" ] || echo "  NOTE: add assets/img/raw/airwaves_melon.jpg (yellow Airwaves packshot)"
echo "done"
