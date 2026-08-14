# Contributing

This repository is a **generated API directory**. The catalog is built from the
community tables in [public-apis/public-apis](https://github.com/public-apis/public-apis).
It is a developer resource, not a marketing list.

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
| `data/metadata/overrides.json` | Later verified enrichment with provenance |
| `data/metadata/schema.json` | Record contract |
| `src/` and `scripts/` | Pipeline code |
| `tests/` | Fixtures and unit tests |

To add verified metadata later, append an override object that includes
`source_type`, `source_url`, and `verified_at`. Overrides never replace the
upstream Auth / HTTPS / CORS values.

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

1. Prefer contributing the entry to
   [public-apis/public-apis](https://github.com/public-apis/public-apis) first,
   following that project's [CONTRIBUTING.md](https://github.com/public-apis/public-apis/blob/master/CONTRIBUTING.md).
2. After upstream merges it, the weekly update workflow fetches the new catalog.
3. For metadata that is **not** in upstream (rate limits, OpenAPI, official SDKs),
   add a verified override with a link to official provider documentation.

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
- fewer than 1,000 APIs are present after a full upstream build
- generated Markdown does not match the normalized dataset

## Duplicate policy

Possible duplicates are written to `data/normalized/duplicates.json` and listed
in `generated/indexes/duplicates.md`. Ambiguous pairs are flagged for review.
They are not merged automatically.

## License

Contributions are accepted under the MIT License. Catalog text originates from
the MIT-licensed public-apis project and remains attributed in `LICENSE`.
