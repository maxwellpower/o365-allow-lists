#!/usr/bin/env python3
"""Generate and validate Microsoft 365 allow lists."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
LIST_SPECS = {
    "minimal": REPO_ROOT / "o365-minimal-allowlist.txt",
    "sane": REPO_ROOT / "o365-sane-allowlist.txt",
    "full": REPO_ROOT / "o365-full-allowlist.txt",
}
METADATA_PATH = DATA_DIR / "m365-endpoint-metadata.json"

CLIENT_REQUEST_ID = "3f7f7d83-f9b9-4f6b-8c8d-3d4e6db245e1"
INSTANCE = "Worldwide"
VERSION_URL = (
    f"https://endpoints.office.com/version/{INSTANCE}"
    f"?ClientRequestId={CLIENT_REQUEST_ID}"
)
ENDPOINTS_URL = (
    f"https://endpoints.office.com/endpoints/{INSTANCE}"
    f"?ClientRequestId={CLIENT_REQUEST_ID}&NoIPv6=true"
)

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.(?!-)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)
RULE_RE = re.compile(r"^@@\|\|([a-z0-9.-]+)\^$")
LAST_UPDATED_RE = re.compile(r"^! Last Updated: (\d{4}-\d{2}-\d{2})$")

MINIMAL_DOMAINS = {
    "aadcdn.microsoftonline-p.com",
    "aka.ms",
    "cloud.microsoft",
    "live.com",
    "login.live.com",
    "mail.protection.outlook.com",
    "microsoftonline.com",
    "microsoftonline-p.com",
    "msauth.net",
    "msauthimages.net",
    "msftidentity.com",
    "office.com",
    "office365.com",
    "onmicrosoft.com",
    "outlook.com",
    "outlook.office.com",
    "outlook.office365.com",
    "protection.outlook.com",
}

SANE_DOMAINS = {
    "aadcdn.microsoftonline-p.com",
    "aka.ms",
    "cloud.microsoft",
    "config.office.com",
    "live.com",
    "login.live.com",
    "lync.com",
    "mail.protection.outlook.com",
    "microsoft365.com",
    "microsoftonline.com",
    "microsoftonline-p.com",
    "msauth.net",
    "msauthimages.net",
    "msftidentity.com",
    "office.com",
    "office.live.com",
    "office.net",
    "office365.com",
    "officeapps.live.com",
    "officecdn.microsoft.com",
    "onmicrosoft.com",
    "onedrive.com",
    "onenote.com",
    "outlook.com",
    "outlook.office.com",
    "outlook.office365.com",
    "protection.outlook.com",
    "sharepoint.com",
    "sharepointonline.com",
    "skype.com",
    "skypeforbusiness.com",
    "static.microsoft",
    "storage.live.com",
    "teams.microsoft.com",
    "usercontent.microsoft",
}


class ValidationError(Exception):
    """Raised when a generated allowlist fails validation."""


@dataclass(frozen=True)
class FetchResult:
    version: str
    domains: set[str]


def fetch_json(url: str) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "o365-allow-lists-generator/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def fetch_upstream_data() -> FetchResult:
    version_payload = fetch_json(VERSION_URL)
    if not isinstance(version_payload, dict):
        raise ValidationError("Version endpoint did not return an object")
    version = str(version_payload.get("latest", "")).strip()
    if not version:
        raise ValidationError("Version endpoint response did not include a latest value")

    endpoint_payload = fetch_json(ENDPOINTS_URL)
    if not isinstance(endpoint_payload, list):
        raise ValidationError("Endpoints endpoint did not return a list")

    domains = extract_domains(endpoint_payload)
    return FetchResult(version=version, domains=domains)


def extract_domains(records: Sequence[object]) -> set[str]:
    domains: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        urls = record.get("urls", [])
        if not isinstance(urls, list):
            continue
        for raw_value in urls:
            normalised = normalise_domain(raw_value)
            if normalised:
                domains.add(normalised)
    return domains


def normalise_domain(raw_value: object) -> str | None:
    if not isinstance(raw_value, str):
        return None

    value = raw_value.strip().lower()
    if not value:
        return None

    if "://" in value:
        return None

    value = value.replace("\\-", "-").replace("\\.", ".").replace("\\*", "*")
    value = value.strip(".")

    if not value:
        return None

    if "/" in value or ":" in value or " " in value:
        return None

    while value.startswith("*.") or value.startswith("*"):
        value = value[2:] if value.startswith("*.") else value[1:]
        value = value.lstrip(".")

    if not value:
        return None

    if "*" in value:
        wildcard_index = value.rfind("*.")
        if wildcard_index == -1:
            return None
        value = value[wildcard_index + 2 :]

    value = value.strip(".")
    if not value or is_ip_address(value):
        return None
    if not DOMAIN_RE.match(value):
        return None

    return value


def is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def render_allowlist(domains: Iterable[str], header_lines: Sequence[str], last_updated: str) -> str:
    rules = [f"@@||{domain}^" for domain in sorted(set(domains))]
    lines = [f"! {line}" for line in header_lines] + [f"! Last Updated: {last_updated}"]
    return "\n".join(lines + [""] + rules) + "\n"


def extract_last_updated(content: str) -> str | None:
    for line in content.splitlines():
        match = LAST_UPDATED_RE.fullmatch(line.strip())
        if match:
            return match.group(1)
    return None


def strip_last_updated(content: str) -> str:
    lines = [line for line in content.splitlines() if not LAST_UPDATED_RE.fullmatch(line.strip())]
    return "\n".join(lines) + "\n"


def parse_rules(content: str) -> list[str]:
    domains: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("!"):
            continue
        match = RULE_RE.fullmatch(stripped)
        if not match:
            raise ValidationError(f"Invalid rule format: {line}")
        domains.append(match.group(1))
    return domains


def validate_file_content(name: str, content: str, required_domains: set[str] | None = None) -> None:
    domains = parse_rules(content)
    if domains != sorted(domains):
        raise ValidationError(f"{name} is not sorted")
    if len(domains) != len(set(domains)):
        raise ValidationError(f"{name} contains duplicate entries")

    for domain in domains:
        if " " in domain:
            raise ValidationError(f"{name} contains whitespace in a hostname: {domain}")
        if any(token in domain for token in ("(", ")", "[", "]", "{", "}", "\\", "$", "+", "?")):
            raise ValidationError(f"{name} contains regex-like syntax: {domain}")
        if is_ip_address(domain):
            raise ValidationError(f"{name} contains an IP address: {domain}")
        if not DOMAIN_RE.fullmatch(domain):
            raise ValidationError(f"{name} contains an invalid hostname: {domain}")

    if required_domains and not required_domains.issubset(set(domains)):
        missing = sorted(required_domains - set(domains))
        raise ValidationError(f"{name} is missing required domains: {', '.join(missing)}")


def write_if_changed(path: Path, content: str) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def load_metadata() -> dict[str, str]:
    if not METADATA_PATH.exists():
        return {}
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def metadata_content(version: str) -> str:
    payload = {
        "instance": INSTANCE,
        "clientRequestId": CLIENT_REQUEST_ID,
        "latestVersion": version,
        "source": "https://endpoints.office.com",
    }
    return json.dumps(payload, indent=2) + "\n"


def build_outputs(fetch_result: FetchResult, today: str | None = None) -> dict[str, str]:
    today = today or date.today().isoformat()
    existing_contents = {
        name: path.read_text(encoding="utf-8") if path.exists() else ""
        for name, path in LIST_SPECS.items()
    }
    existing_dates = {
        name: extract_last_updated(content) or today
        for name, content in existing_contents.items()
    }

    base_outputs = {
        "minimal": (
            MINIMAL_DOMAINS,
            [
                'Microsoft 365 "minimal" allowlist for Pi-hole',
                "Goal: allow login, identity, Outlook, and basic tenant routing only",
                "Best for desktop Office / Outlook setups where Teams, SharePoint, and OneDrive web features are not required",
                "Format: Adblock exception rules",
            ],
        ),
        "sane": (
            SANE_DOMAINS,
            [
                'Microsoft 365 "sane" allowlist for Pi-hole',
                "Goal: allow core Microsoft 365 functionality (login, Outlook, Teams, SharePoint, OneDrive)",
                "while avoiding broader telemetry/CDN domains where possible",
                "Format: Adblock exception rules",
            ],
        ),
        "full": (
            fetch_result.domains,
            [
                "Microsoft 365 / O365 max-compatibility allowlist for Pi-hole",
                "Format: Adblock-style exception rules",
                "Source: Official Microsoft 365 endpoint web service (Worldwide instance)",
                "Each rule allows the domain and its subdomains",
            ],
        ),
    }

    outputs = {
        name: render_allowlist(domains, header_lines, existing_dates[name])
        for name, (domains, header_lines) in base_outputs.items()
    }

    for name, (domains, header_lines) in base_outputs.items():
        existing = existing_contents[name]
        candidate = outputs[name]
        if strip_last_updated(existing) != strip_last_updated(candidate):
            outputs[name] = render_allowlist(domains, header_lines, today)

    return outputs


def validate_outputs(outputs: dict[str, str]) -> None:
    validate_file_content("minimal", outputs["minimal"], required_domains=MINIMAL_DOMAINS)
    validate_file_content("sane", outputs["sane"], required_domains=SANE_DOMAINS)
    validate_file_content("full", outputs["full"])


def validate_existing_files() -> None:
    for name, path in LIST_SPECS.items():
        required = MINIMAL_DOMAINS if name == "minimal" else SANE_DOMAINS if name == "sane" else None
        validate_file_content(name, path.read_text(encoding="utf-8"), required_domains=required)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the tracked allowlist files without rewriting them.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with a non-zero status if regeneration would change tracked files.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)

    try:
        if args.validate_only:
            validate_existing_files()
            return 0

        fetch_result = fetch_upstream_data()
        outputs = build_outputs(fetch_result)
        validate_outputs(outputs)

        changed = False
        for name, content in outputs.items():
            path = LIST_SPECS[name]
            if args.check:
                existing = path.read_text(encoding="utf-8") if path.exists() else ""
                if existing != content:
                    raise ValidationError(f"{path.name} is out of date; run the generator")
            else:
                changed = write_if_changed(path, content) or changed

        metadata = load_metadata()
        next_metadata = metadata_content(fetch_result.version)
        if args.check:
            existing = METADATA_PATH.read_text(encoding="utf-8") if METADATA_PATH.exists() else ""
            if existing != next_metadata:
                raise ValidationError(f"{METADATA_PATH.name} is out of date; run the generator")
        else:
            changed = write_if_changed(METADATA_PATH, next_metadata) or changed

        if changed:
            print(f"Updated allowlists using Microsoft 365 endpoint version {fetch_result.version}.")
        else:
            print(f"No content changes; Microsoft 365 endpoint version is {fetch_result.version}.")
        return 0
    except (OSError, urllib.error.URLError, ValidationError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
