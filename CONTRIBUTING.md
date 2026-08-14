# Contributing

This repository is a **curated, generated API directory**. It is a developer
resource, not a marketing list.

## Ground rules

- Do not invent API providers, capabilities, pricing, rate limits, SDKs, CORS,
  authentication details, or commercial-use conclusions.
- If a field cannot be verified, it must stay `Unknown` or `null`.
- Do not add affiliate links, advertisements, or sponsored rankings.
- Do not edit files under `generated/` or the root `README.md` by hand. They are
  produced by `scripts/build.py`.
- Do not silently merge or delete entries that look like duplicates. Flag them.

## What to change by hand

| Path | Purpose |
| --- | --- |
| `config/` | Scoring rules, category blurbs, use-case criteria |
| `data/metadata/overrides.json` | Verified enrichment with provenance |
| `data/metadata/schema.json` | Record contract |
| `src/` and `scripts/` | Pipeline code |
| `tests/` | Fixtures and unit tests |

To add verified metadata, append an override object that includes
`source_type`, `source_url`, and `verified_at`. Overrides never replace the
catalog Auth / HTTPS / CORS values without explicit review.

## Local workflow

```bash
git clone <this-repo>
cd public-apis-directory
python -m pip install -r requirements.txt
python scripts/validate.py
python scripts/build.py
pytest
```

Inspect the result before opening a pull request:

```bash
git diff
git status
```

## Adding or correcting an API

1. Open a pull request with the new or corrected API entry in the catalog source
   data (via the build pipeline or normalized dataset, depending on your change).
2. Include the official documentation URL, category, Auth, HTTPS, and CORS values.
3. For extra metadata (rate limits, OpenAPI, official SDKs), add a verified
   override in `data/metadata/overrides.json` with a link to official provider
   documentation.

Commit message example:

```text
Add Example API to Finance
```

Pull request title example:

```text
Add Example API
```

## Validation that must pass

The build fails when:

- name, description, documentation URL, or category is missing
- Auth, HTTPS, or CORS is not in the allowed enum
- two records share the same canonical documentation URL
- fewer than 1,000 APIs are present after a full catalog build
- generated Markdown does not match the normalized dataset

## Duplicate policy

Possible duplicates are written to `data/normalized/duplicates.json` and listed
in `generated/indexes/duplicates.md`. Ambiguous pairs are flagged for review.
They are not merged automatically.

## License

Contributions are accepted under the MIT License. See [LICENSE](LICENSE).
