# Outils Beam

- `beam_story.py` : génère la série « Les 3 pépites du jour » (récap + 3 affiches détaillées, 1080x1920) à partir des annonces publiques de beam.sn.
- `logo.b64` : logo Beam en base64, passé au script via la variable `BEAM_LOGO_B64`.

Usage : `BEAM_LOGO_B64="$(cat logo.b64)" python3 beam_story.py out [AAAA-MM-JJ]`
