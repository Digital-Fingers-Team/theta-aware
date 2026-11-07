# θ-Aware presentation site

Static site, no build step. Live at https://theta-aware.130-110-124-121.sslip.io (noindex).

- `index.html`: one `<section class="slide">` per slide, in order. Edit the text freely.
  `data-scene` picks a 3D scene (chip, bloch, mirror, landscape, compiler), `data-chart` a 2D chart.
  `<aside class="notes">` holds the speaker notes (press N).
- `js/scenes.js`: the 3D scenes (three.js 0.160, vendored in `vendor/`, so it works offline).
- `js/charts.js`: the SVG charts. `js/main.js`: navigation, controls, labels.
- `data/site_data.json`: measured curves, exported by `python 20_export_site_data.py` (no QPU use).
  `data/paper_results.json`: a copy of `paper_results.json`.

Keys: right/left arrow or space, Home/End, F fullscreen, N notes. To open it locally, run a static
server inside `site/` (for example `python -m http.server`); opening index.html as a file blocks the data fetch.

Deploy: copy `site/` to `~/theta-aware-site/html` on the server, then `chmod -R a+rX` it.
