#!/usr/bin/env python3
"""Deterministic triple-source web search for the xuejian-web-search skill.

Sources:
  - keenable CLI (no API key)
  - Tavily Search API (TAVILY_API_KEY)
  - Brave Search API (BRAVE_API_KEY)

The script never prints secret values. Missing credentials skip only the
affected source. Exit code is 0 when at least one source returns or executes
successfully, 1 when every requested source fails or is skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


TAVILY_URL = "https://api.tavily.com/search"
BRAVE_WEB_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_NEWS_URL = "https://api.search.brave.com/res/v1/news/search"
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
}
NEWS_HINTS = (
    "news",
    "latest",
    "recent",
    "today",
    "this week",
    "breaking",
    "新闻",
    "资讯",
    "热点",
    "最近",
    "最新",
    "近几天",
    "动态",
)


@dataclass
class SearchResult:
    source: str
    title: str
    url: str
    snippet: str = ""
    published_date: str = ""
    score: float | None = None
    age: str = ""


@dataclass
class SourceStatus:
    source: str
    status: str
    detail: str
    count: int = 0


def configure_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def read_env(name: str) -> str:
    """Read process env, then Windows user/machine env without shelling out."""
    value = os.environ.get(name)
    if value:
        return value
    if os.name != "nt":
        return ""
    try:
        import winreg  # type: ignore
    except ImportError:
        return ""

    locations = (
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    )
    for root, path in locations:
        try:
            with winreg.OpenKey(root, path) as key:
                value, _ = winreg.QueryValueEx(key, name)
            if value:
                return str(value)
        except OSError:
            continue
    return ""


def http_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
    proxy: str = "",
) -> Any:
    data = None
    req_headers = headers or {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers = {"Content-Type": "application/json", **req_headers}

    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    else:
        opener = urllib.request.build_opener()
    with opener.open(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def http_json_curl(
    url: str,
    *,
    headers: dict[str, str],
    timeout: int,
    proxy: str = "",
) -> Any:
    """Fetch JSON with curl.exe/curl as a Windows-friendly network fallback."""
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl not found")

    cmd = [curl, "-s", url, "--max-time", str(timeout), "-w", "\n__HTTP_%{http_code}__"]
    for key, value in headers.items():
        cmd.extend(["-H", "%s: %s" % (key, value)])
    if proxy:
        cmd.extend(["--proxy", proxy])

    completed = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout + 5,
    )
    output = completed.stdout or ""
    body, marker, status = output.rpartition("\n__HTTP_")
    if completed.returncode != 0:
        raise RuntimeError("curl exit code %s" % completed.returncode)
    if not marker or not status.endswith("__"):
        raise RuntimeError("curl returned no HTTP status")
    status_code = status[:-2]
    if not status_code.startswith("2"):
        raise RuntimeError("curl HTTP %s" % status_code)
    return json.loads(body)


def concise_error(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return "HTTP %s" % exc.code
    if isinstance(exc, urllib.error.URLError):
        return "network error: %s" % exc.reason
    if isinstance(exc, subprocess.TimeoutExpired):
        return "timeout after %ss" % exc.timeout
    return "%s: %s" % (exc.__class__.__name__, exc)


def trim_text(value: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", (value or "")).strip()
    if limit <= 0 or len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def parse_keenable_output(text: str, limit: int) -> list[SearchResult]:
    results: list[SearchResult] = []
    current: dict[str, str] | None = None

    def flush() -> None:
        nonlocal current
        if not current:
            return
        title = current.get("title", "").strip()
        url = current.get("url", "").strip()
        if title or url:
            results.append(
                SearchResult(
                    source="keenable",
                    title=title or url,
                    url=url,
                    snippet=current.get("snippet", "").strip(),
                    published_date=current.get("published_date", "").strip(),
                )
            )
        current = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^\d+\.\s+(.+)$", line)
        if match:
            flush()
            current = {"title": match.group(1)}
            continue
        if current is None:
            continue
        if line.startswith("http://") or line.startswith("https://"):
            current["url"] = line.split()[0]
            continue
        if "published:" in line or "acquired:" in line:
            pub = re.search(r"published:\s+(\S+)", line)
            if pub:
                current["published_date"] = pub.group(1)
            continue
        snippet = current.get("snippet", "")
        current["snippet"] = (snippet + " " + line).strip()

    flush()
    return results[:limit]


def search_keenable(query: str, limit: int, timeout: int) -> tuple[list[SearchResult], SourceStatus]:
    if not shutil.which("keenable"):
        return [], SourceStatus("keenable", "skipped", "keenable CLI not found in PATH")
    try:
        completed = subprocess.run(
            ["keenable", "search", query, "-p"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], SourceStatus("keenable", "failed", concise_error(exc))

    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    if completed.returncode != 0:
        return [], SourceStatus("keenable", "failed", "exit code %s" % completed.returncode)
    results = parse_keenable_output(output, limit)
    return results, SourceStatus("keenable", "ok", "parsed keenable output", len(results))


def search_tavily(
    query: str,
    mode: str,
    limit: int,
    days: int,
    timeout: int,
    snippet_chars: int,
) -> tuple[list[SearchResult], SourceStatus]:
    key = read_env("TAVILY_API_KEY")
    if not key:
        return [], SourceStatus("tavily", "skipped", "TAVILY_API_KEY missing")

    payload: dict[str, Any] = {
        "api_key": key,
        "query": query,
        "search_depth": "advanced",
        "max_results": limit,
    }
    if mode == "news":
        payload["topic"] = "news"
        payload["days"] = days

    try:
        data = http_json(TAVILY_URL, method="POST", payload=payload, timeout=timeout)
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        return [], SourceStatus("tavily", "failed", concise_error(exc))

    results = []
    for item in data.get("results", [])[:limit]:
        results.append(
            SearchResult(
                source="tavily",
                title=str(item.get("title") or "").strip(),
                url=str(item.get("url") or "").strip(),
                snippet=trim_text(str(item.get("content") or ""), snippet_chars),
                published_date=str(item.get("published_date") or "").strip(),
                score=item.get("score") if isinstance(item.get("score"), (int, float)) else None,
            )
        )
    return results, SourceStatus("tavily", "ok", "Tavily API returned results", len(results))


def brave_freshness(days: int) -> str:
    if days <= 1:
        return "pd"
    if days <= 7:
        return "pw"
    if days <= 31:
        return "pm"
    return "py"


def search_brave(
    query: str,
    mode: str,
    limit: int,
    days: int,
    timeout: int,
    snippet_chars: int,
) -> tuple[list[SearchResult], SourceStatus]:
    key = read_env("BRAVE_API_KEY")
    if not key:
        return [], SourceStatus("brave", "skipped", "BRAVE_API_KEY missing")

    endpoint = BRAVE_NEWS_URL if mode == "news" else BRAVE_WEB_URL
    params = {
        "q": query,
        "count": str(limit),
        "search_lang": "en",
        "country": "US",
        "safesearch": "moderate",
    }
    if mode == "news":
        params["freshness"] = brave_freshness(days)
    url = endpoint + "?" + urllib.parse.urlencode(params)
    proxy = read_env("BRAVE_PROXY")
    headers = {
        "X-Subscription-Token": key,
        "Accept": "application/json",
        "User-Agent": "xuejian-web-search/1.3",
    }
    via = "urllib"

    def fetch_with_urllib() -> Any:
        return http_json(url, headers=headers, timeout=timeout, proxy=proxy)

    def fetch_with_curl() -> Any:
        return http_json_curl(url, headers=headers, timeout=timeout, proxy=proxy)

    try:
        if os.name == "nt" and (shutil.which("curl.exe") or shutil.which("curl")):
            data = fetch_with_curl()
            via = "curl"
        else:
            data = fetch_with_urllib()
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        try:
            if via == "curl":
                data = fetch_with_urllib()
                via = "urllib fallback"
            else:
                data = fetch_with_curl()
                via = "curl fallback"
        except (
            urllib.error.URLError,
            RuntimeError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
            TimeoutError,
            OSError,
        ) as fallback_exc:
            detail = "%s %s; fallback %s" % (
                via,
                concise_error(exc),
                concise_error(fallback_exc),
            )
            return [], SourceStatus("brave", "failed", detail)

    raw_results = data.get("results") or data.get("web", {}).get("results") or []
    results = []
    for item in raw_results[:limit]:
        results.append(
            SearchResult(
                source="brave",
                title=str(item.get("title") or "").strip(),
                url=str(item.get("url") or "").strip(),
                snippet=trim_text(str(item.get("description") or ""), snippet_chars),
                published_date=str(item.get("page_age") or "").strip(),
                age=str(item.get("age") or "").strip(),
            )
        )
    return results, SourceStatus("brave", "ok", "Brave API returned results via %s" % via, len(results))


def normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlsplit(url.strip())
    query_pairs = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    query = urllib.parse.urlencode(query_pairs, doseq=True)
    normalized = urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            query,
            "",
        )
    )
    return normalized


def dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    seen: dict[str, SearchResult] = {}
    order: list[str] = []
    for result in results:
        key = normalize_url(result.url) or ("title:" + result.title.lower())
        if key not in seen:
            seen[key] = result
            order.append(key)
            continue
        existing = seen[key]
        if result.source not in existing.source.split("+"):
            existing.source += "+" + result.source
        if not existing.snippet and result.snippet:
            existing.snippet = result.snippet
        if not existing.published_date and result.published_date:
            existing.published_date = result.published_date
        if not existing.age and result.age:
            existing.age = result.age
    return [seen[key] for key in order]


def pick_mode(query: str, requested: str) -> str:
    if requested != "auto":
        return requested
    lowered = query.lower()
    return "news" if any(hint in lowered for hint in NEWS_HINTS) else "general"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 三源搜索结果",
        "",
        "- Query: `%s`" % payload["query"],
        "- Mode: `%s`" % payload["mode"],
        "- Generated at: `%s`" % payload["generated_at"],
        "- Used sources: %s" % (", ".join(payload["used_sources"]) or "none"),
        "- Skipped/failed sources: %s"
        % (
            "; ".join(
                "%s=%s (%s)" % (s["source"], s["status"], s["detail"])
                for s in payload["source_statuses"]
                if s["status"] != "ok"
            )
            or "none"
        ),
        "",
        "## Merged Results",
        "",
    ]
    for index, item in enumerate(payload["results"], start=1):
        lines.append("%d. [%s](%s)" % (index, item["title"] or item["url"], item["url"] or "#"))
        meta = []
        if item.get("source"):
            meta.append("source: `%s`" % item["source"])
        if item.get("published_date"):
            meta.append("date: `%s`" % item["published_date"])
        elif item.get("age"):
            meta.append("age: `%s`" % item["age"])
        if meta:
            lines.append("   - " + "; ".join(meta))
        snippet = (item.get("snippet") or "").replace("\n", " ").strip()
        if snippet:
            lines.append("   - " + snippet[:500])
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Triple-source web search digest")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--mode", choices=("auto", "general", "news"), default="auto")
    parser.add_argument("--days", type=int, default=7, help="News freshness window")
    parser.add_argument("--max-results", type=int, default=10, help="Results per source")
    parser.add_argument("--snippet-chars", type=int, default=700, help="Max snippet characters per result")
    parser.add_argument(
        "--sources",
        default="keenable,tavily,brave",
        help="Comma-separated sources: keenable,tavily,brave",
    )
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--json", action="store_true", help="Print structured JSON")
    return parser.parse_args()


def main() -> int:
    configure_stdout()
    args = parse_args()
    mode = pick_mode(args.query, args.mode)
    requested_sources = {s.strip().lower() for s in args.sources.split(",") if s.strip()}
    max_results = max(1, min(args.max_results, 20))
    days = max(1, args.days)
    snippet_chars = max(0, args.snippet_chars)

    all_results: list[SearchResult] = []
    statuses: list[SourceStatus] = []
    runners = {
        "keenable": lambda: search_keenable(args.query, max_results, args.timeout),
        "tavily": lambda: search_tavily(args.query, mode, max_results, days, args.timeout, snippet_chars),
        "brave": lambda: search_brave(args.query, mode, max_results, days, args.timeout, snippet_chars),
    }

    for source in ("keenable", "tavily", "brave"):
        if source not in requested_sources:
            continue
        results, status = runners[source]()
        all_results.extend(results)
        statuses.append(status)

    merged = dedupe_results(all_results)
    for result in merged:
        result.snippet = trim_text(result.snippet, snippet_chars)
    used_sources = [s.source for s in statuses if s.status == "ok"]
    payload = {
        "query": args.query,
        "mode": mode,
        "days": days if mode == "news" else None,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "used_sources": used_sources,
        "source_statuses": [asdict(s) for s in statuses],
        "results": [asdict(r) for r in merged],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload))

    return 0 if used_sources else 1


if __name__ == "__main__":
    raise SystemExit(main())
