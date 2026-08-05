#!/usr/bin/env python3
"""Client for configured REDSkill ranking data."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path.home() / ".config" / "redskill-rank-client" / "config.json"
DEFAULT_CACHE_DIR = Path("D:/redskill-rank-cache")
DEFAULT_CACHE_TTL = 600
DEFAULT_ENDPOINT_DATA = "aHR0cDovLzQzLjE1Ni43Ny4yMTcvYXBpL3JlZHNraWxs"
DEFAULT_ACCESS_KEY_DATA = "cmVkc2tpbGwtcHVibGljLXYxLTIwMjYwODA1LTVmNGI4ZTJjMWE5ZDdmMzA="
DEFAULT_FIELDS = {
    "use": ["rank", "skill_id", "skill_name", "use_users", "use_cnt", "note_id"],
    "users": ["rank", "skill_id", "skill_name", "use_users", "use_cnt", "note_id"],
    "new": ["rank", "skill_id", "skill_name", "new7_cnt", "cum_cnt", "note_id"],
    "7d": ["rank", "skill_id", "skill_name", "new7_cnt", "cum_cnt", "note_id"],
    "today": ["rank", "skill_id", "skill_name", "use_users", "use_cnt", "note_id"],
    "daily": ["rank", "skill_id", "skill_name", "use_users", "use_cnt", "note_id"],
    "author": ["rank", "author_id", "nickname", "skill_cnt"],
    "authors": ["rank", "author_id", "nickname", "skill_cnt"],
    "all": ["skill_id", "skill_name", "skill_description"],
}


def load_config(path: Path) -> dict[str, str]:
    config: dict[str, str] = {}
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(loaded, dict):
            config.update({str(k): str(v) for k, v in loaded.items()})
    if os.environ.get("REDSKILL_ENDPOINT"):
        config["endpoint"] = os.environ["REDSKILL_ENDPOINT"]
    if os.environ.get("REDSKILL_ACCESS_KEY"):
        config["access_key"] = os.environ["REDSKILL_ACCESS_KEY"]
    return config


def default_endpoint() -> str:
    return base64.urlsafe_b64decode(DEFAULT_ENDPOINT_DATA.encode("ascii")).decode("utf-8")


def default_access_key() -> str:
    return base64.urlsafe_b64decode(DEFAULT_ACCESS_KEY_DATA.encode("ascii")).decode("utf-8")


def resolve_cache_dir(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_CACHE_DIR


def cache_key(endpoint: str, params: dict[str, str]) -> str:
    key_params = {k: v for k, v in params.items() if k != "refresh"}
    payload = json.dumps(
        {"endpoint": endpoint, "params": sorted(key_params.items())},
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_cache(cache_dir: Path, key: str) -> dict[str, Any] | None:
    path = cache_dir / f"{key}.json"
    if not path.exists():
        return None
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(cached, dict):
        return None
    expires_at = cached.get("expires_at")
    data = cached.get("data")
    if not isinstance(expires_at, (int, float)) or time.time() >= float(expires_at):
        return None
    if not isinstance(data, dict):
        return None
    return data


def write_cache(cache_dir: Path, key: str, data: dict[str, Any], ttl: int) -> None:
    if ttl <= 0:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "cached_at": int(time.time()),
        "expires_at": int(time.time()) + ttl,
        "ttl_seconds": ttl,
        "data": data,
    }
    path = cache_dir / f"{key}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def request_json(endpoint: str, access_key: str, params: dict[str, str], timeout: int) -> dict[str, Any]:
    url = endpoint
    if params:
        separator = "&" if "?" in url else "?"
        url += separator + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json", "X-Access-Key": access_key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Data request failed (HTTP {exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Data request failed: {exc.reason}") from exc
    data = json.loads(raw)
    if not data.get("ok"):
        raise SystemExit(f"Data access failed: {data.get('error', 'unknown error')}")
    return data


def request_json_cached(
    endpoint: str,
    access_key: str,
    params: dict[str, str],
    timeout: int,
    cache_dir: Path,
    cache_ttl: int,
    use_cache: bool,
) -> dict[str, Any]:
    key = cache_key(endpoint, params)
    should_read_cache = use_cache and cache_ttl > 0 and params.get("refresh") != "true"
    if should_read_cache:
        cached = read_cache(cache_dir, key)
        if cached is not None:
            return cached
    data = request_json(endpoint, access_key, params, timeout)
    if use_cache and cache_ttl > 0:
        write_cache(cache_dir, key, data, cache_ttl)
    return data


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def trim(value: Any, width: int) -> str:
    text = stringify(value).replace("\r", " ").replace("\n", " ")
    if len(text) <= width:
        return text
    return text[: max(0, width - 1)] + "..."


def print_table(rows: list[dict[str, Any]], fields: list[str], width: int = 48) -> None:
    if not rows:
        print("(no rows)")
        return
    widths = {field: min(max(len(field), *(len(trim(row.get(field), width)) for row in rows)), width) for field in fields}
    print(" | ".join(field.ljust(widths[field]) for field in fields))
    print("-+-".join("-" * widths[field] for field in fields))
    for row in rows:
        print(" | ".join(trim(row.get(field), widths[field]).ljust(widths[field]) for field in fields))


def output_rows(rows: list[dict[str, Any]], fields: list[str], fmt: str, output: str | None) -> None:
    if fmt == "json":
        text = json.dumps(rows, ensure_ascii=False, indent=2)
        if output:
            Path(output).expanduser().resolve().write_text(text + "\n", encoding="utf-8")
        else:
            print(text)
        return
    if fmt == "csv":
        if output:
            path = Path(output).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            fh = path.open("w", newline="", encoding="utf-8-sig")
            close = True
        else:
            fh = sys.stdout
            close = False
        try:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        finally:
            if close:
                fh.close()
        return
    print_table(rows, fields)


def fields_from(raw: str | None, fallback: list[str]) -> list[str]:
    if not raw:
        return fallback
    return [part.strip() for part in raw.split(",") if part.strip()]


def common_config(args: argparse.Namespace) -> tuple[str, str, Path, int, bool]:
    config = load_config(Path(args.config).expanduser())
    endpoint = args.endpoint or config.get("endpoint") or default_endpoint()
    access_key = args.access_key or config.get("access_key") or default_access_key()
    cache_dir = resolve_cache_dir(args.cache_dir or config.get("cache_dir"))
    cache_ttl = args.cache_ttl
    if args.cache_ttl == DEFAULT_CACHE_TTL and config.get("cache_ttl"):
        try:
            cache_ttl = int(config["cache_ttl"])
        except ValueError as exc:
            raise SystemExit("config.json cache_ttl must be an integer number of seconds.") from exc
    if not endpoint:
        raise SystemExit("Missing REDSkill data endpoint. Set REDSKILL_ENDPOINT or config.json endpoint.")
    if not access_key:
        raise SystemExit("Missing REDSkill access key. Set REDSKILL_ACCESS_KEY or config.json access_key.")
    if cache_ttl < 0:
        raise SystemExit("--cache-ttl must be >= 0")
    return endpoint, access_key, cache_dir, cache_ttl, not args.no_cache


def cmd_summary(args: argparse.Namespace) -> None:
    endpoint, access_key, cache_dir, cache_ttl, use_cache = common_config(args)
    data = request_json_cached(
        endpoint,
        access_key,
        {"op": "summary", "refresh": str(args.refresh).lower()},
        args.timeout,
        cache_dir,
        cache_ttl,
        use_cache,
    )
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_top(args: argparse.Namespace) -> None:
    endpoint, access_key, cache_dir, cache_ttl, use_cache = common_config(args)
    params = {"op": "top", "list": args.list, "limit": str(args.limit), "refresh": str(args.refresh).lower()}
    if args.query:
        params["query"] = args.query
    if args.fields:
        params["fields"] = args.fields
    data = request_json_cached(endpoint, access_key, params, args.timeout, cache_dir, cache_ttl, use_cache)
    rows = data["rows"]
    fallback = DEFAULT_FIELDS.get(args.list.lower(), list(rows[0].keys()) if rows else [])
    fields = fields_from(args.fields, fallback)
    output_rows(rows, fields, args.format, args.output)


def cmd_search(args: argparse.Namespace) -> None:
    endpoint, access_key, cache_dir, cache_ttl, use_cache = common_config(args)
    params = {"op": "search", "query": args.query, "limit": str(args.limit), "refresh": str(args.refresh).lower()}
    if args.fields:
        params["fields"] = args.fields
    data = request_json_cached(endpoint, access_key, params, args.timeout, cache_dir, cache_ttl, use_cache)
    rows = data["rows"]
    fields = fields_from(
        args.fields,
        ["skill_id", "skill_name", "source", "useList_rank", "newList_rank", "todayList_rank", "use_users", "use_cnt", "new7_cnt", "note_id"],
    )
    output_rows(rows, fields, args.format, args.output)


def cmd_detail(args: argparse.Namespace) -> None:
    endpoint, access_key, cache_dir, cache_ttl, use_cache = common_config(args)
    params = {"op": "detail", "refresh": str(args.refresh).lower()}
    if args.skill_id:
        params["skill_id"] = args.skill_id
    if args.note_id:
        params["note_id"] = args.note_id
    if args.fields:
        params["fields"] = args.fields
    data = request_json_cached(endpoint, access_key, params, args.timeout, cache_dir, cache_ttl, use_cache)
    rows = data["rows"]
    fields = fields_from(args.fields, list(rows[0].keys()) if rows else [])
    output_rows(rows, fields, args.format, args.output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query configured REDSkill ranking data.")

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", default=str(DEFAULT_CONFIG), help=argparse.SUPPRESS)
        p.add_argument("--endpoint", help=argparse.SUPPRESS)
        p.add_argument("--access-key", help=argparse.SUPPRESS)
        p.add_argument("--timeout", type=int, default=30)
        p.add_argument("--refresh", action="store_true", help="Ask the data provider to refresh data.")
        p.add_argument("--cache-dir", help=f"Cache directory. Default: {DEFAULT_CACHE_DIR}")
        p.add_argument("--cache-ttl", type=int, default=DEFAULT_CACHE_TTL, help="Cache lifetime in seconds. Default: 600.")
        p.add_argument("--no-cache", action="store_true", help="Disable local cache for this run.")

    sub = parser.add_subparsers(dest="command", required=True)
    summary = sub.add_parser("summary")
    common(summary)
    summary.set_defaults(func=cmd_summary)

    top = sub.add_parser("top")
    common(top)
    top.add_argument("--list", required=True, help="use, new, today, author, all")
    top.add_argument("--limit", type=int, default=20)
    top.add_argument("--query")
    top.add_argument("--fields")
    top.add_argument("--format", choices=["table", "json", "csv"], default="table")
    top.add_argument("--output")
    top.set_defaults(func=cmd_top)

    search = sub.add_parser("search")
    common(search)
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--fields")
    search.add_argument("--format", choices=["table", "json", "csv"], default="table")
    search.add_argument("--output")
    search.set_defaults(func=cmd_search)

    detail = sub.add_parser("detail")
    common(detail)
    ident = detail.add_mutually_exclusive_group(required=True)
    ident.add_argument("--skill-id")
    ident.add_argument("--note-id")
    detail.add_argument("--fields")
    detail.add_argument("--format", choices=["table", "json", "csv"], default="table")
    detail.add_argument("--output")
    detail.set_defaults(func=cmd_detail)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if hasattr(args, "limit") and args.limit < 1:
        raise SystemExit("--limit must be >= 1")
    args.func(args)


if __name__ == "__main__":
    main()
