# Signalpost Intelligence

An evidence-first agent for Norwegian company research. It accepts a Norwegian organization number, retrieves official public registry information, stores fact-level provenance, exports at least 1,000 profiles, and records meaningful profile changes.

## Design principles

- **Identity before enrichment:** a requested organization number must exactly match the number in the official registry response. No fuzzy name matching is used to assign facts.
- **Evidence on every fact:** facts include a source URL, retrieval timestamp, source update timestamp when available, evidence type, and confidence label.
- **No fabricated values:** absent source fields are omitted, never guessed. Financial figures are not inferred from company size or other proxies.
- **Refresh without destructive failure:** a failed lookup does not replace the stored profile. Use `--refresh` to check the official source.
- **Update history:** SQLite keeps the current profile and snapshots when source-backed content changes.
- **Budget awareness:** outbound requests are counted and bounded per process; retries and a modest request interval reduce load.

## Requirements

- Python 3.10+
- Network access to `data.brreg.no`

## One-command setup and run

From the repository root, install and collect 1,000 profiles:

```bash
python -m pip install -e . && signalpost crawl --target 1000
```

If you prefer not to install the command entry point, use `python -m signalpost.cli crawl --target 1000` after `pip install -e .`.

## Commands

```bash
# Look up a company; use its 9-digit Norwegian organization number
signalpost lookup 923609016

# Fetch current official data rather than returning the local cached profile
signalpost lookup 923609016 --refresh

# Crawl a collection (can resume into the same SQLite database)
signalpost crawl --target 1000 --page-size 100

# Export every stored profile, including evidence
signalpost export --output data/profiles.jsonl --format jsonl
signalpost export --output data/profiles.csv --format csv

# Inspect change history and collection size
signalpost history 923609016
signalpost stats
```

Use `--db /path/to/db.sqlite3` to select a database and `--max-requests 2000` to set the invocation request budget. The crawl command exits with status `3` if it cannot reach the requested target within the available source pages or request budget. The number of distinct profiles in the database is reported explicitly; never claim the 1,000-profile requirement has been met until `target_reached` is true and the exported dataset is checked.

## Optional HTTP API

```bash
python -m pip install -e '.[api]'
uvicorn signalpost.api:app --host 127.0.0.1 --port 8000
```

Then use `GET /companies/{org_number}`, `GET /companies/{org_number}?refresh=true`, or `GET /health`. The API intentionally does not publish a guessed financial value. If financial facts are added later, implement a dedicated official-source adapter and include reporting period, units/currency, source URL, retrieval date, and the source's original value.

## Data and schema

Each JSON profile includes `org_number`, `name`, `source_url`, `retrieved_at`, `source_updated_at`, and a `facts` array. Each fact has `key`, `value`, `source_url`, `retrieved_at`, `source_updated_at`, `evidence_type`, and `confidence`. The registry is the source of truth for these fields; retrieval time is not misrepresented as the source's own update time.

The first adapter uses the Brønnøysund Register Centre's public Enhetsregisteret API (`https://data.brreg.no/enhetsregisteret/api/enheter`). Review the source's current terms, rate limits, and availability before production/challenge execution. Only permitted public sources should be enabled.

## Testing

```bash
python -m pip install -e '.[test]'
pytest -q
```

Tests cover organization-number validation, exact identity matching, missing-name rejection, and change-history behavior. The integration path should also be exercised against the live source before submission.

## Model/API details

- **LLM:** none required for core registry extraction. This is deliberate: official registry facts are structured, and deterministic extraction reduces hallucination and operating cost.
- **External API:** Brønnøysund Register Centre Enhetsregisteret public HTTP API.
- **Local API:** optional FastAPI wrapper.
- **Storage:** SQLite; JSONL/CSV export.

## Expected costs

- Model/API inference: **$0** for the baseline implementation.
- Public registry API: no paid API key is configured by this project; verify current terms and any applicable limits before running.
- Compute: local CPU and disk only; actual infrastructure cost depends on where it is run.
- The crawl uses approximately `ceil(target / page_size)` listing requests when the source returns full pages, plus retries. This is an estimate, not a guarantee. The request budget is enforced per invocation.

## Submission checklist

- [ ] Run the test suite and a live-source smoke test.
- [ ] Crawl and verify at least 1,000 distinct organization numbers.
- [ ] Export the profiles and inspect source URLs, timestamps, and organization-number uniqueness.
- [ ] Record the actual Git commit hash from the submitted repository.
- [ ] Confirm current API terms and the challenge's permitted-source rules.
- [ ] Email the repository/archive and required submission files to `submit@builderr.ai`.

## Limitations / next improvements

This baseline deliberately favors correctness over speculative breadth. It does not yet add secondary public sources or financial-statement extraction. To improve challenge coverage, add source adapters one at a time, require each adapter to verify the same organization number, store fact-level citations and reporting periods, and test against known positive and negative examples. Never publish a financial number without direct source evidence.
