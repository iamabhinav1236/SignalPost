"""Agent orchestration and output generation."""
from __future__ import annotations
import csv, json
from pathlib import Path
from typing import Any
from .models import normalize_orgno
from .sources import BrregClient, SourceError
from .store import ProfileStore

class SignalpostAgent:
    def __init__(self, store: ProfileStore | None = None, client: BrregClient | None = None,
                 max_requests: int = 2000):
        self.store = store or ProfileStore()
        self.client = client or BrregClient()
        self.max_requests = max_requests

    def lookup(self, org_number: str, refresh: bool = False) -> dict[str, Any]:
        orgno = normalize_orgno(org_number)
        cached = self.store.get(orgno)
        if cached and not refresh:
            return {"status": "ok", "cached": True, "profile": cached, "explanation": "Returned the latest locally stored official-registry profile. Use --refresh to check for changes."}
        if self.client.request_count >= self.max_requests:
            raise SourceError(f"Outbound request budget reached ({self.max_requests})")
        profile = self.client.lookup(orgno)
        result = self.store.upsert(profile)
        return {"status": "ok", "cached": False, "change": result, "profile": profile.to_dict(),
                "explanation": "Company identity was matched on the exact nine-digit organization number. Each published fact includes source provenance."}

    def crawl(self, target: int = 1000, page_size: int = 100, only_active: bool = False) -> dict[str, Any]:
        if target < 1:
            raise ValueError("target must be >= 1")
        inserted = updated = skipped = pages = 0
        page = 0
        while self.store.count() < target and self.client.request_count < self.max_requests:
            profiles, metadata = self.client.list_companies(page=page, size=min(page_size, 1000), only_active=only_active)
            pages += 1
            if not profiles:
                break
            for profile in profiles:
                if self.store.count() >= target:
                    break
                outcome = self.store.upsert(profile)
                if outcome["is_new"]: inserted += 1
                elif outcome["changed"]: updated += 1
                else: skipped += 1
            total_pages = metadata.get("totalPages") if isinstance(metadata, dict) else None
            page += 1
            if total_pages is not None and page >= total_pages:
                break
        return {"target": target, "total_profiles": self.store.count(), "inserted": inserted, "updated": updated,
                "unchanged": skipped, "pages_fetched": pages, "requests_used": self.client.request_count,
                "request_budget": self.max_requests, "target_reached": self.store.count() >= target}

    def export(self, output: str, fmt: str = "jsonl") -> int:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        profiles = list(self.store.all_profiles())
        if fmt == "jsonl":
            with path.open("w", encoding="utf-8") as f:
                for item in profiles:
                    f.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
        elif fmt == "csv":
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["org_number", "name", "source_url", "retrieved_at", "source_updated_at", "facts_json"])
                writer.writeheader()
                for item in profiles:
                    writer.writerow({"org_number": item["org_number"], "name": item["name"], "source_url": item["source_url"],
                                     "retrieved_at": item["retrieved_at"], "source_updated_at": item.get("source_updated_at"),
                                     "facts_json": json.dumps(item["facts"], ensure_ascii=False)})
        else:
            raise ValueError("format must be jsonl or csv")
        return len(profiles)
