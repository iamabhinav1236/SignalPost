"""Adapters for permitted public sources. The official registry is authoritative for core facts."""
from __future__ import annotations
import time
from typing import Any
from urllib.parse import quote
import requests
from .models import CompanyProfile, Fact, normalize_orgno, utc_now

BASE_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"

class SourceError(RuntimeError):
    pass

class BrregClient:
    def __init__(self, timeout: float = 12.0, max_retries: int = 3, session: requests.Session | None = None,
                 min_interval: float = 0.15, user_agent: str = "SignalpostIntelligence/1.0 (public-data research)"):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.min_interval = max(0.0, min_interval)
        self.user_agent = user_agent
        self._last_request = 0.0
        self.request_count = 0

    def _get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            delay = self.min_interval - (time.monotonic() - self._last_request)
            if delay > 0:
                time.sleep(delay)
            try:
                response = self.session.get(url, params=params, timeout=self.timeout,
                                            headers={"User-Agent": self.user_agent, "Accept": "application/json"})
                self._last_request = time.monotonic()
                self.request_count += 1
                if response.status_code == 404:
                    raise SourceError("Company not found in the official Norwegian Entity Register")
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self.max_retries:
                        retry_after = response.headers.get("Retry-After")
                        try:
                            pause = min(20.0, float(retry_after)) if retry_after else min(2 ** attempt, 8)
                        except ValueError:
                            pause = min(2 ** attempt, 8)
                        time.sleep(pause)
                        continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise SourceError("Unexpected response from official registry")
                return payload
            except SourceError:
                raise
            except (requests.RequestException, ValueError) as exc:
                if attempt >= self.max_retries:
                    raise SourceError(f"Official registry request failed: {exc}") from exc
                time.sleep(min(2 ** attempt, 8))
        raise SourceError("Official registry request failed after retries")

    def lookup(self, org_number: str) -> CompanyProfile:
        orgno = normalize_orgno(org_number)
        url = f"{BASE_URL}/{quote(orgno)}"
        payload = self._get_json(url)
        # Critical guard: never publish a response unless its registry identity matches the request.
        returned = str(payload.get("organisasjonsnummer", ""))
        if returned != orgno:
            raise SourceError(f"Identity mismatch: requested {orgno}, registry returned {returned or 'no number'}")
        retrieved = utc_now()
        name = payload.get("navn")
        if not isinstance(name, str) or not name.strip():
            raise SourceError("Registry response has no valid company name; refusing to publish profile")
        fields = {
            "organization_form": "organisasjonsform",
            "registered_in_entity_register": "registrertIEnhetsregisteret",
            "registered_in_vat_register": "registrertIMvaregisteret",
            "registered_in_business_register": "registrertIForetaksregisteret",
            "foundation_date": "stiftelsesdato",
            "registration_date": "registreringsdatoEnhetsregisteret",
            "business_description": "naeringskode1",
            "website": "hjemmeside",
            "number_of_employees": "antallAnsatte",
            "postal_address": "postadresse",
            "business_address": "forretningsadresse",
            "sector_code": "institusjonellSektorkode",
            "latest_annual_accounts": "sisteInnsendteAarsregnskap",
        }
        facts: list[Fact] = [Fact("name", name.strip(), url, retrieved)]
        for key, source_key in fields.items():
            actual_key = source_key.strip()
            value = payload.get(actual_key)
            if value is None or value == "" or value == []:
                continue
            # Preserve source values exactly; do not infer or manufacture financial data.
            facts.append(Fact(key, value, url, retrieved, payload.get("oppdateringsdato")))
        facts.append(Fact("organization_number", orgno, url, retrieved, payload.get("oppdateringsdato")))
        return CompanyProfile(orgno, name.strip(), facts, url, retrieved, payload.get("oppdateringsdato"))

    def list_companies(self, page: int = 0, size: int = 100, only_active: bool = False) -> tuple[list[CompanyProfile], dict[str, Any]]:
        if page < 0 or not 1 <= size <= 1000:
            raise ValueError("page must be >= 0 and size must be between 1 and 1000")
        params: dict[str, Any] = {"page": page, "size": size, "sort": "organisasjonsnummer"}
        if only_active:
            params["konkurs"] = "false"
        url = BASE_URL
        payload = self._get_json(url, params)
        embedded = payload.get("_embedded", {})
        items = embedded.get("enheter", []) if isinstance(embedded, dict) else []
        profiles: list[CompanyProfile] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            orgno = str(item.get("organisasjonsnummer", ""))
            name = item.get("navn")
            # List payloads are also identity-checked and only emit facts actually present.
            if len(orgno) != 9 or not orgno.isdigit() or not isinstance(name, str) or not name.strip():
                continue
            retrieved = utc_now()
            item_url = f"{BASE_URL}/{orgno}"
            facts = [Fact("name", name.strip(), item_url, retrieved), Fact("organization_number", orgno, item_url, retrieved)]
            for key, source_key in (("organization_form", "organisasjonsform"), ("registered_in_entity_register", "registrertIEnhetsregisteret"),
                                    ("registered_in_vat_register", "registrertIMvaregisteret"), ("foundation_date", "stiftelsesdato"),
                                    ("registration_date", "registreringsdatoEnhetsregisteret"), ("business_description", "naeringskode1"),
                                    ("number_of_employees", "antallAnsatte"), ("business_address", "forretningsadresse")):
                value = item.get(source_key)
                if value not in (None, "", []):
                    facts.append(Fact(key, value, item_url, retrieved, item.get("oppdateringsdato")))
            profiles.append(CompanyProfile(orgno, name.strip(), facts, item_url, retrieved, item.get("oppdateringsdato")))
        return profiles, payload.get("page", {})
