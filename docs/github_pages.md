# GitHub Pages Publishing Notes

The project website is designed to publish as a static GitHub Pages site from the `site/` folder.

## What Gets Published

The workflow in `.github/workflows/pages.yml` builds a clean `_site/` artifact containing:

- the interactive static dashboard from `site/`;
- selected public-facing documentation from `docs/`;
- `REPLICATION.md`;
- `.nojekyll`, so GitHub Pages serves files without Jekyll processing.

The workflow does not publish the full local `data/` or `outputs/` trees.

## First-Time Setup

1. Create a GitHub repository.
2. Push this project to the repository's `main` branch.
3. In GitHub, open `Settings > Pages`.
4. Set the Pages source to `GitHub Actions`.
5. Open the `Actions` tab and run `Deploy Trend Site`, or push a new commit to `main`.

After the first successful deployment, GitHub will show the public Pages URL in the deployment summary.

## Updating The Public Site

When trend tables change locally:

```bash
make trends
make site-data
```

Review `site/index.html` locally, commit the updated `site/data.js` and related docs, then push to `main`.

## Data Boundary

Keep source code, configs, tests, prompts, website files, and public documentation in git. Keep large raw API caches, PDF/OCR caches, intermediate reviewer files, and generated output folders outside git unless a separate replication archive is intentionally prepared.
