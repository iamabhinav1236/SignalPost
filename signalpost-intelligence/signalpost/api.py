"""Optional FastAPI wrapper: install with `pip install -e '.[api]'`."""
from fastapi import FastAPI, HTTPException, Query
from .agent import SignalpostAgent
from .models import valid_norwegian_orgno
from .sources import SourceError

app = FastAPI(title="Signalpost Intelligence API", version="1.0.0", description="Evidence-backed Norwegian company profiles")
agent = SignalpostAgent()

@app.get("/health")
def health():
    return {"status": "ok", "profiles": agent.store.count(), "requests_used_this_process": agent.client.request_count}

@app.get("/companies/{org_number}")
def company(org_number: str, refresh: bool = Query(False, description="Fetch fresh registry data")):
    if not valid_norwegian_orgno(org_number):
        raise HTTPException(status_code=422, detail="Invalid Norwegian organization number or checksum")
    try:
        return agent.lookup(org_number, refresh=refresh)
    except SourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
