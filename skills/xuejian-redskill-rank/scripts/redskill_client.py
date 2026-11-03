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
from pathlib import Path, PurePosixPath
from typing import Any


DEFAULT_CONFIG = Path.home() / ".config" / "redskill-rank-client" / "config.json"
DEFAULT_CACHE_TTL = 3600
DEFAULT_ENDPOINT_DATA = "aHR0cHM6Ly9jb3dvcmsueGlhb2hvbmdzaHUuY29tL3MvcmVkc2tpbGwtcmFuay9kYXRhLmpzb24="
DEFAULT_FIELDS = {
    "use": ["rank", "skill_id", "skill_name", "use_users", "use_cnt", "note_id"],
    "users": ["rank", "skill_id", "skill_name", "use_users", "use_cnt", "note_id"],
    "useList": ["rank", "skill_id", "skill_name", "use_users", "use_cnt", "note_id"],
    "new": ["rank", "skill_id", "skill_name", "new7_cnt", "cum_cnt", "note_id"],
    "7d": ["rank", "skill_id", "skill_name", "new7_cnt", "cum_cnt", "note_id"],
    "newList": ["rank", "skill_id", "skill_name", "new7_cnt", "cum_cnt", "note_id"],
    "today": ["rank", "skill_id", "skill_name", "use_users", "use_cnt", "note_id"],
    "daily": ["rank", "skill_id", "skill_name", "use_users", "use_cnt", "note_id"],
    "todayList": ["rank", "skill_id", "skill_name", "use_users", "use_cnt", "note_id"],
    "author": ["rank", "author_id", "nickname", "skill_cnt"],
    "authors": ["rank", "author_id", "nickname", "skill_cnt"],
    "authorList": ["rank", "author_id", "nickname", "skill_cnt"],
    "all": ["skill_id", "skill_name", "skill_description"],
    "allSkills": ["skill_id", "skill_name", "skill_description"],
}

LIST_ALIASES = {
    "use": "useList", "users": "useList", "useList": "useList",
    "new": "newList", "7d": "newList", "newList": "newList",
    "today": "todayList", "daily": "todayList", "todayList": "todayList",
    "author": "authorList", "authors": "authorList", "authorList": "authorList",
    "all": "allSkills", "allSkills": "allSkills",
}


def load_config(path: Path) -> dict[str, str]:
    config: dict[str, str] = {}
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(loaded, dict):
            config.update({str(k): str(v) for k, v in loaded.items()})
    if os.environ.get("REDSKILL_ENDPOINT"):
        config["endpoint"] = os.environ["REDSKILL_ENDPOINT"]
    return config


def default_endpoint() -> str:
    return base64.urlsafe_b64decode(DEFAULT_ENDPOINT_DATA.encode("ascii")).decode("utf-8")


def default_cache_dir_text(
    os_name: str | None = None,
    sys_platform: str | None = None,
    home: str | None = None,
    env: dict[str, str] | None = None,
    d_drive_exists: bool | None = None,
) -> str:
    os_name = os.name if os_name is None else os_name
    sys_platform = sys.platform if sys_platform is None else sys_platform
    env = os.environ if env is None else env
    home = str(Path.home()) if home is None else home
    if os_name == "nt":
        if d_drive_exists is None:
            d_drive_exists = Path("D:/").exists()
        if d_drive_exists:
            return "D:/redskill-rank-cache"
        local_app_data = env.get("LOCALAPPDATA")
        if local_app_data:
            return str(Path(local_app_data) / "redskill-rank-cache")
        return str(Path(home) / "redskill-rank-cache")
    if sys_platform == "darwin":
        return str(PurePosixPath(home) / "Library" / "Caches" / "redskill-rank")
    xdg_cache_home = env.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return str(PurePosixPath(xdg_cache_home) / "redskill-rank")
    return str(PurePosixPath(home) / ".cache" / "redskill-rank")


def default_cache_dir() -> Path:
    return Path(default_cache_dir_text())


def resolve_cache_dir(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()
    return default_cache_dir()


def cache_key(endpoint: str, params: dict[str, str] | None) -> str:
    key_params = {k: v for k, v in (params or {}).items() if k != "refresh"}
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
    req = urllib.request.Request(
        endpoint,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Data request failed (HTTP {exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Data request failed: {exc.reason}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit("Data request failed: endpoint returned non-JSON content") from exc
    if not isinstance(data, dict) or "useList" not in data:
        raise SystemExit("Data request failed: unexpected data shape (missing useList)")
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
    key = cache_key(endpoint, None)
    should_read_cache = use_cache and cache_ttl > 0 and params.get("refresh") != "true"
    if should_read_cache:
        cached = read_cache(cache_dir, key)
        if cached is not None:
            return cached
    data = request_json(endpoint, access_key, params, timeout)
    if use_cache and cache_ttl > 0:
        write_cache(cache_dir, key, data, cache_ttl)
    return data


RANKED_LISTS = ("useList", "newList", "todayList", "authorList")


def _sid(record: dict[str, Any]) -> str:
    return str(record.get("skill_id", ""))


def shape_summary(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "dataDate": data.get("dataDate"),
        "genTime": data.get("genTime"),
        "counts": {name: len(data.get(name) or []) for name in (*RANKED_LISTS, "allSkills")},
    }


def shape_top_rows(data: dict[str, Any], list_name: str) -> list[dict[str, Any]]:
    canonical = LIST_ALIASES.get(list_name) or LIST_ALIASES.get(list_name.lower())
    if not canonical:
        raise SystemExit(f"Unsupported list: {list_name} (expected one of {', '.join(sorted(set(LIST_ALIASES.values())))})")
    rows = []
    for index, record in enumerate(data.get(canonical) or [], start=1):
        row = dict(record)
        row["rank"] = index
        rows.append(row)
    return rows


def shape_search_rows(data: dict[str, Any], query: str, limit: int) -> list[dict[str, Any]]:
    needle = query.strip().lower()
    if not needle:
        return []

    def matches(record: dict[str, Any]) -> bool:
        name = str(record.get("skill_name") or "").lower()
        description = str(record.get("skill_description") or "").lower()
        return needle in name or needle in description

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    rank_maps: dict[str, dict[str, int]] = {}
    for list_name in ("useList", "newList", "todayList"):
        rank_maps[list_name] = {_sid(r): i for i, r in enumerate(data.get(list_name) or [], start=1)}

    for list_name in ("useList", "newList", "todayList"):
        for record in data.get(list_name) or []:
            sid = _sid(record)
            if sid in seen or not matches(record):
                continue
            seen.add(sid)
            row = dict(record)
            row["source"] = list_name
            row["useList_rank"] = rank_maps["useList"].get(sid)
            row["newList_rank"] = rank_maps["newList"].get(sid)
            row["todayList_rank"] = rank_maps["todayList"].get(sid)
            for other in ("useList", "newList", "todayList"):
                if other == list_name:
                    continue
                for candidate in data.get(other) or []:
                    if _sid(candidate) == sid:
                        for field in ("use_users", "use_cnt", "new7_cnt", "cum_cnt", "note_id"):
                            if field not in row or row.get(field) in (None, ""):
                                row[field] = candidate.get(field)
                        break
            rows.append(row)

    for record in data.get("allSkills") or []:
        sid = _sid(record)
        if sid in seen or not matches(record):
            continue
        seen.add(sid)
        row = dict(record)
        row["source"] = "allSkills"
        rows.append(row)

    return rows[:limit]


def shape_detail_rows(data: dict[str, Any], skill_id: str | None, note_id: str | None) -> list[dict[str, Any]]:
    for list_name in ("useList", "newList", "todayList"):
        for record in data.get(list_name) or []:
            if (skill_id is not None and _sid(record) == skill_id) or (
                note_id is not None and str(record.get("note_id") or "") == note_id
            ):
                row = dict(record)
                row["source"] = list_name
                return [row]
    if skill_id is not None:
        for record in data.get("allSkills") or []:
            if _sid(record) == skill_id:
                row = dict(record)
                row["source"] = "allSkills"
                return [row]
    return []


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
            path = Path(output).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text + "\n", encoding="utf-8")
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
    access_key = args.access_key or config.get("access_key") or ""
    cache_dir = resolve_cache_dir(args.cache_dir or config.get("cache_dir"))
    cache_ttl = args.cache_ttl
    if args.cache_ttl == DEFAULT_CACHE_TTL and config.get("cache_ttl"):
        try:
            cache_ttl = int(config["cache_ttl"])
        except ValueError as exc:
            raise SystemExit("config.json cache_ttl must be an integer number of seconds.") from exc
    if not endpoint:
        raise SystemExit("Missing REDSkill data endpoint. Set REDSKILL_ENDPOINT or config.json endpoint.")
    if cache_ttl < 0:
        raise SystemExit("--cache-ttl must be >= 0")
    return endpoint, access_key, cache_dir, cache_ttl, not args.no_cache


def cmd_summary(args: argparse.Namespace) -> None:
    endpoint, access_key, cache_dir, cache_ttl, use_cache = common_config(args)
    data = request_json_cached(
        endpoint,
        access_key,
        {"refresh": str(args.refresh).lower()},
        args.timeout,
        cache_dir,
        cache_ttl,
        use_cache,
    )
    print(json.dumps(shape_summary(data), ensure_ascii=False, indent=2))


def cmd_top(args: argparse.Namespace) -> None:
    endpoint, access_key, cache_dir, cache_ttl, use_cache = common_config(args)
    data = request_json_cached(
        endpoint,
        access_key,
        {"refresh": str(args.refresh).lower()},
        args.timeout,
        cache_dir,
        cache_ttl,
        use_cache,
    )
    rows = shape_top_rows(data, args.list)
    if args.query:
        needle = args.query.strip().lower()
        rows = [
            row
            for row in rows
            if needle in str(row.get("skill_name") or "").lower()
            or needle in str(row.get("skill_description") or "").lower()
            or needle in str(row.get("nickname") or "").lower()
        ]
    rows = rows[: args.limit]
    fallback = DEFAULT_FIELDS.get(args.list) or DEFAULT_FIELDS.get(args.list.lower()) or (
        list(rows[0].keys()) if rows else []
    )
    fields = fields_from(args.fields, fallback)
    output_rows(rows, fields, args.format, args.output)


def cmd_search(args: argparse.Namespace) -> None:
    endpoint, access_key, cache_dir, cache_ttl, use_cache = common_config(args)
    data = request_json_cached(
        endpoint,
        access_key,
        {"refresh": str(args.refresh).lower()},
        args.timeout,
        cache_dir,
        cache_ttl,
        use_cache,
    )
    rows = shape_search_rows(data, args.query, args.limit)
    fields = fields_from(
        args.fields,
        ["skill_id", "skill_name", "source", "useList_rank", "newList_rank", "todayList_rank", "use_users", "use_cnt", "new7_cnt", "note_id"],
    )
    output_rows(rows, fields, args.format, args.output)


def cmd_detail(args: argparse.Namespace) -> None:
    endpoint, access_key, cache_dir, cache_ttl, use_cache = common_config(args)
    data = request_json_cached(
        endpoint,
        access_key,
        {"refresh": str(args.refresh).lower()},
        args.timeout,
        cache_dir,
        cache_ttl,
        use_cache,
    )
    rows = shape_detail_rows(data, args.skill_id, args.note_id)
    fields = fields_from(args.fields, list(rows[0].keys()) if rows else [])
    output_rows(rows, fields, args.format, args.output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query configured REDSkill ranking data.")

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", default=str(DEFAULT_CONFIG), help=argparse.SUPPRESS)
        p.add_argument("--endpoint", help=argparse.SUPPRESS)
        p.add_argument("--access-key", help=argparse.SUPPRESS)
        p.add_argument("--timeout", type=int, default=60)
        p.add_argument("--refresh", action="store_true", help="Skip local cache and re-download the data file.")
        p.add_argument("--cache-dir", help=f"Cache directory. Default: {default_cache_dir()}")
        p.add_argument("--cache-ttl", type=int, default=DEFAULT_CACHE_TTL, help=f"Cache lifetime in seconds. Default: {DEFAULT_CACHE_TTL}.")
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
