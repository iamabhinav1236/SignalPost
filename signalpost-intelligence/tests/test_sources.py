import pytest
from signalpost.sources import BrregClient, SourceError

class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code, self.headers = payload, status, {}
    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))
    def json(self): return self.payload

class FakeSession:
    def __init__(self, payload): self.payload = payload
    def get(self, *args, **kwargs): return FakeResponse(self.payload)

def test_lookup_refuses_identity_mismatch():
    client = BrregClient(session=FakeSession({"organisasjonsnummer": "111111111", "navn": "Wrong Company"}), min_interval=0)
    with pytest.raises(SourceError, match="Identity mismatch"):
        client.lookup("923609016")

def test_lookup_requires_name():
    client = BrregClient(session=FakeSession({"organisasjonsnummer": "923609016"}), min_interval=0)
    with pytest.raises(SourceError, match="no valid company name"):
        client.lookup("923609016")
