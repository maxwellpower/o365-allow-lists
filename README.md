# O365 Allow Lists

Microsoft 365 / Office 365 allow lists in adblock-style exception format for Pi-hole and similar DNS or content filtering systems.

The repo maintains curated `minimal` and `sane` lists, plus an automatically generated `full` list derived from the official Microsoft 365 endpoint web service.

## Files

### `o365-minimal-allowlist.txt`
Smallest starting point.

Use this when you mainly want:
- sign-in and identity flows
- Outlook / Exchange access
- basic tenant routing

This is best for desktop Office and Outlook setups where you do not need full Teams, SharePoint, or OneDrive web functionality.

### `o365-sane-allowlist.txt`
Recommended default.

Use this when you want the best balance between:
- Microsoft 365 working normally
- avoiding broader Microsoft domains that may be blocked by privacy lists for good reason

This list covers the core domains for:
- authentication
- Outlook / Exchange
- Teams
- SharePoint
- OneDrive
- Office web apps
- newer Microsoft `cloud.microsoft` infrastructure

### `o365-full-allowlist.txt`
Maximum compatibility list.

Use this when you want to allow nearly everything published or commonly required for Microsoft 365 and related services, including many supporting and optional domains.

This list is useful for:
- troubleshooting broken Microsoft 365 behaviour
- testing whether a block list is interfering with service operation
- environments where compatibility matters more than minimising allowed Microsoft infrastructure

### `data/m365-endpoint-metadata.json`
Stored metadata for the latest Microsoft 365 endpoint version used to generate the repo.

### `scripts/generate_o365_lists.py`
Single source of truth for:
- curated domain sets
- upstream endpoint fetching
- domain normalization
- allowlist rendering
- file validation

### `.github/workflows/update-o365-lists.yml`
Scheduled and manual updater. Runs weekly and only commits when generated files actually change.

### `.github/workflows/validate-o365-lists.yml`
CI validation for pushes and pull requests. Verifies tests and file integrity without depending on a live upstream diff.

### `addons/`
Optional manually maintained sidecar allowlists that are not part of the automated Microsoft 365 update flow.

Current examples:
- `addons/okta-allowlist.txt` for a small Okta / Okta Verify compatibility sidecar
- `addons/github-allowlist.txt` for conservative GitHub web/API/assets coverage

## Format

All files use adblock-style exception syntax, for example:

```txt
@@||office.com^
@@||microsoftonline.com^
@@||cloud.microsoft^
```

## Suggested starting point

Start with `o365-sane-allowlist.txt`.

Move to `o365-minimal-allowlist.txt` if you want a tighter setup and know you do not need the extra Microsoft 365 web services.

Move to `o365-full-allowlist.txt` if something is still breaking and you want to rule out domain blocking first.

## Notes

- These lists are intended as practical starting points, not a guarantee that every Microsoft feature will work in every environment.
- Microsoft continues moving services onto newer domains such as `cloud.microsoft`, so these lists will likely evolve over time.
- The generator uses the official Microsoft 365 endpoint web service for the `Worldwide` instance with a stable `ClientRequestId`.
- `minimal` and `sane` are intentionally hand-curated in code and are not widened automatically when Microsoft adds new endpoints.
- Files under `addons/` are optional extras. They are maintained separately and are not modified by the O365 generator or scheduled updater.
- The GitHub addon is intentionally conservative. It is meant to keep core GitHub usage working, not to cover every GitHub-adjacent service such as Actions, Packages, Codespaces, or Copilot.

## Automation

The intended long-term process is:

1. GitHub Actions runs weekly or on manual dispatch.
2. The generator fetches the latest Microsoft endpoint data.
3. `o365-full-allowlist.txt` is rebuilt from upstream domains after normalization and cleanup.
4. `o365-minimal-allowlist.txt` and `o365-sane-allowlist.txt` are rebuilt from explicit curated constants.
5. The workflow validates file integrity and only commits if content changed.

This keeps the broad compatibility list fresh while protecting the curated lists from accidental expansion.

## Local Usage

Regenerate all files:

```bash
python3 scripts/generate_o365_lists.py
```

Validate the tracked files:

```bash
python3 scripts/generate_o365_lists.py --validate-only
```

Run unit tests:

```bash
python3 -m unittest discover -s tests
```
