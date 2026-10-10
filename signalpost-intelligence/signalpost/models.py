"""Typed data structures and identity validation."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
import re

ORGNO_RE = re.compile(r"^\d{9}$")

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def normalize_orgno(value: str) -> str:
    digits = re.sub(r"[\s.-]", "", str(value))
    if not ORGNO_RE.fullmatch(digits):
        raise ValueError("Norwegian organization number must contain exactly 9 digits")
    return digits

def valid_norwegian_orgno(value: str) -> bool:
    """Validate format and the Norwegian organization-number MOD-11 checksum."""
    try:
        orgno = normalize_orgno(value)
    except ValueError:
        return False
    weights = (3, 2, 7, 6, 5, 4, 3, 2)
    remainder = sum(int(d) * w for d, w in zip(orgno[:8], weights)) % 11
    check = 11 - remainder
    if check == 11:
        check = 0
    if check == 10:
        return False
    return int(orgno[-1]) == check

@dataclass
class Fact:
    key: str
    value: Any
    source_url: str
    retrieved_at: str
    source_updated_at: str | None = None
    evidence_type: str = "official_registry"
    confidence: str = "high"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class CompanyProfile:
    org_number: str
    name: str
    facts: list[Fact]
    source_url: str
    retrieved_at: str
    source_updated_at: str | None = None
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "org_number": self.org_number,
            "name": self.name,
            "facts": [f.to_dict() for f in self.facts],
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at,
            "source_updated_at": self.source_updated_at,
        }
