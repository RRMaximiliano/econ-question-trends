# Trend Dashboard

This directory contains a static dashboard for inspecting detected causal/predictive/other trends.

Regenerate the embedded data after refreshing trend outputs:

```bash
make PYTHON=/usr/bin/python3 trends
make PYTHON=/usr/bin/python3 site-data
```

Open `index.html` directly in a browser, or serve it locally:

```bash
python3 -m http.server 8765 --directory site
```

The dashboard is static and reads `site/data.js`, which is generated from CSV files under `outputs/tables/enriched/`.

For GitHub Pages, the repository workflow copies this folder into a clean `_site/` artifact and
adds selected public documentation. Keep `site/data.js` committed when sharing the current trend
snapshot publicly.
