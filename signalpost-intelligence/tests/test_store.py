from signalpost.models import CompanyProfile, Fact
from signalpost.store import ProfileStore

def profile(name="Example AS", retrieved="2026-01-01T00:00:00+00:00"):
    url = "https://data.brreg.no/enhetsregisteret/api/enheter/923609016"
    return CompanyProfile("923609016", name, [Fact("name", name, url, retrieved)], url, retrieved)

def test_upsert_history_only_on_change(tmp_path):
    store = ProfileStore(str(tmp_path / "test.sqlite3"))
    first = store.upsert(profile())
    second = store.upsert(profile(retrieved="2026-01-02T00:00:00+00:00"))
    third = store.upsert(profile(name="Changed AS", retrieved="2026-01-03T00:00:00+00:00"))
    assert first["is_new"] is True
    assert second["changed"] is False
    assert third["changed"] is True
    assert len(store.history("923609016")) == 2
    assert store.get("923609016")["name"] == "Changed AS"
    store.close()
