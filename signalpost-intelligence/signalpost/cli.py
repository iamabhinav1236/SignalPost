"""Command line interface."""
from __future__ import annotations
import argparse, json, sys
from . import __version__
from .agent import SignalpostAgent
from .models import valid_norwegian_orgno
from .sources import SourceError
from .store import ProfileStore

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="signalpost", description="Evidence-first Norwegian company research agent")
    parser.add_argument("--db", default="data/signalpost.sqlite3", help="SQLite database path")
    parser.add_argument("--max-requests", type=int, default=2000, help="Maximum outbound requests per invocation")
    parser.add_argument("--version", action="version", version=f"Signalpost Intelligence {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    lookup = sub.add_parser("lookup", help="Look up a Norwegian organization number")
    lookup.add_argument("org_number")
    lookup.add_argument("--refresh", action="store_true", help="Refresh from the official registry")
    crawl = sub.add_parser("crawl", help="Collect at least N public company profiles")
    crawl.add_argument("--target", type=int, default=1000)
    crawl.add_argument("--page-size", type=int, default=100)
    crawl.add_argument("--only-active", action="store_true")
    export = sub.add_parser("export", help="Export profiles to JSONL or CSV")
    export.add_argument("--output", default="data/profiles.jsonl")
    export.add_argument("--format", choices=["jsonl", "csv"], default="jsonl")
    history = sub.add_parser("history", help="Show changed profile snapshots")
    history.add_argument("org_number")
    stats = sub.add_parser("stats", help="Show local collection statistics")
    return parser

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = ProfileStore(args.db)
    agent = SignalpostAgent(store=store, max_requests=args.max_requests)
    try:
        if args.command == "lookup":
            if not valid_norwegian_orgno(args.org_number):
                print(json.dumps({"status": "error", "error": "Invalid Norwegian organization number or checksum"}), file=sys.stderr)
                return 2
            result = agent.lookup(args.org_number, refresh=args.refresh)
        elif args.command == "crawl":
            result = agent.crawl(args.target, args.page_size, args.only_active)
        elif args.command == "export":
            count = agent.export(args.output, args.format)
            result = {"status": "ok", "exported": count, "path": args.output, "format": args.format}
        elif args.command == "history":
            from .models import normalize_orgno
            result = {"org_number": normalize_orgno(args.org_number), "snapshots": store.history(normalize_orgno(args.org_number))}
        else:
            result = {"profiles": store.count(), "database": args.db, "request_budget_per_invocation": args.max_requests}
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if args.command == "crawl" and not result["target_reached"]:
            return 3
        return 0
    except (ValueError, SourceError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        store.close()

if __name__ == "__main__":
    raise SystemExit(main())
