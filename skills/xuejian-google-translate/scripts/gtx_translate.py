#!/usr/bin/env python3
"""Free Google translation via the unofficial web endpoint (client=gtx). No API key.

Endpoint: GET https://translate.googleapis.com/translate_a/single
This is the endpoint behind translate.google.com itself; borrowed usage is
what googletrans-style libraries do. Unofficial: no SLA, implicit per-IP
rate limits, GET URL length caps text per request (we chunk long input).

Subcommands:
  translate <text> [--to zh-CN] [--from auto] [--json]
      Full translation; long text is chunked at sentence boundaries.
  dict <word> [--to zh-CN] [--from auto] [--json]
      Translation + dictionary senses (dt=bd) + romanization (dt=rm).
  detect <text> [--json]
      Source-language detection only (sl=auto).

Proxy (China networks: Google is blocked, direct connect times out):
  --proxy <url>            force a proxy for this run ("direct"/"off"/"none" = direct)
  --no-proxy               same as --proxy direct
  1) --proxy  2) GOOGLE_TRANSLATE_PROXY / TRANSLATE_PROXY  3) WEB_SEARCH_PROXY
  4) standard HTTPS_PROXY/ALL_PROXY/HTTP_PROXY  5) cached proxy  6) direct
  On network failure with zero explicit config, probes the Windows system
  proxy (registry) then common local ports (7890/7897/10809/8118/2080/1080,
  HTTP proxies only - urllib cannot do socks5), retries through the first
  one that works, and caches it to ~/.xuejian/translate-proxy.json.
  A stale cache entry is evicted and re-probed automatically.

Notes: http proxies only in auto-probe (clash 7890/7897 and v2ray 10809 are
mixed ports and work). socks-only setups must expose an http port or call
curl by hand. Output keeps the console's original encoding (GBK-safe) with
errors="replace"; use --json (pure ASCII) when the target language cannot
survive the console encoding.

Exit codes: 0 ok, 1 error (network/parse/usage), 2 rate limited (429).
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://translate.googleapis.com/translate_a/single"
USER_AGENT = "xuejian-google-translate/1.0"
CHUNK_MAX = 1400          # chars of raw text per request (GET URL limit headroom)
CHUNK_SLEEP = 0.35        # seconds between chunk requests; limits are per-IP
REQUEST_TIMEOUT = 10
PROBE_TIMEOUT = 2.0
RATE_LIMIT_EXIT = 2
PROBE_PORTS = [7890, 7897, 10809, 8118, 2080, 1080]  # http/mixed ports only
PROBE_HOSTS = ["127.0.0.1"]
SENTENCE_SPLIT = re.compile(r"(?<=[。！？；!?;\n])")
CACHE_FILE = os.path.join(os.path.expanduser("~"), ".xuejian", "translate-proxy.json")


def _relax_stdout_errors():
    # Keep the console's original encoding (forcing UTF-8 garbles GBK pipes);
    # only stop hard crashes on characters the pipe cannot represent.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError):
            pass


def die(message, code=1):
    sys.stderr.write(message.rstrip() + "\n")
    sys.exit(code)


class Parser(argparse.ArgumentParser):
    # argparse usage errors default to exit code 2, which collides with the
    # documented "2 = rate limited" contract; force them to 1.
    def error(self, message):
        self.print_usage(sys.stderr)
        die(f"gtx_translate.py: error: {message}", 1)


# ---------------------------------------------------------------- proxy ----

def _registry_system_proxy():
    """Windows system proxy from the registry, "" on any failure/non-Windows."""
    if os.name != "nt":
        return ""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        server, _ = winreg.QueryValueEx(key, "ProxyServer")
        winreg.CloseKey(key)
        if not enable or not server:
            return ""
        if ";" in server:  # per-scheme form: "http=...;https=...;ftp=..."
            for part in server.split(";"):
                if part.lower().startswith("http="):
                    server = part.split("=", 1)[1]
                    break
        return server if "://" in server else "http://" + server
    except OSError:
        return ""


def _cache_read():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f).get("proxy") or ""
    except (OSError, ValueError):
        return ""


def _cache_write(proxy):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"proxy": proxy, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
    except OSError:
        pass


def _cache_clear():
    try:
        os.remove(CACHE_FILE)
    except OSError:
        pass


def _fetch_via(params, proxy, timeout):
    """GET BASE?params through proxy ("" = direct). Returns bytes or raises."""
    url = BASE + "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    if proxy:
        handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        opener = urllib.request.build_opener(handler)
    else:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()


def _probe_candidate(proxy):
    try:
        _fetch_via({"client": "gtx", "sl": "en", "tl": "zh-CN",
                    "ie": "UTF-8", "oe": "UTF-8", "dt": "t", "q": "ok"}, proxy, PROBE_TIMEOUT)
        return proxy
    except (urllib.error.URLError, OSError, ValueError):
        return ""


def _probe_proxies():
    """Parallel-probe registry proxy + common local ports; first winner wins."""
    candidates = []
    reg = _registry_system_proxy()
    if reg:
        candidates.append(reg)
    for host in PROBE_HOSTS:
        for port in PROBE_PORTS:
            candidates.append(f"http://{host}:{port}")
    seen, unique = set(), []
    for cand in candidates:
        if cand not in seen:
            seen.add(cand)
            unique.append(cand)
    with ThreadPoolExecutor(max_workers=max(len(unique), 1)) as pool:
        for found in pool.map(_probe_candidate, unique):
            if found:
                return found
    return ""


def _explicit_proxy(args):
    """Proxy the user pinned for this run, or None when nothing is configured.

    A pin (even "" meaning "direct") is honoured exactly as given: on failure
    we exit instead of silently probing behind the user's back.
    """
    value = (args.proxy or "").strip()
    if args.no_proxy or value.lower() in ("direct", "off", "none"):
        return ""
    if value:
        return value
    for var in ("GOOGLE_TRANSLATE_PROXY", "TRANSLATE_PROXY", "WEB_SEARCH_PROXY",
                "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy",
                "HTTP_PROXY", "http_proxy"):
        env = os.environ.get(var, "").strip()
        if env:
            return env
    return None


def translate_raw(params, pinned):
    """One request with proxy fallback + auto-probe.

    Returns (payload, proxy_used, probed). HTTP-level errors (429 etc.)
    propagate: they are endpoint answers, not proxy problems.
    """
    cached = "" if pinned is not None else _cache_read()
    if pinned is not None:
        attempts = [pinned]
    elif cached:
        attempts = [cached, "", None]    # cache; direct; then probe (sentinel)
    else:
        attempts = ["", None]            # direct, then probe

    last = None
    for proxy in attempts:
        if proxy is None:            # sentinel: probe and retry through the winner
            if cached:
                _cache_clear()       # the stale entry led us here; evict it
            found = _probe_proxies()
            if not found:
                break
            try:
                data = _fetch_via(params, found, REQUEST_TIMEOUT)
                _cache_write(found)
                return json.loads(data.decode("utf-8", "replace")), found, True
            except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
                break
        try:
            data = _fetch_via(params, proxy, REQUEST_TIMEOUT)
            return json.loads(data.decode("utf-8", "replace")), proxy, False
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, OSError, ValueError) as exc:
            last = exc
            if pinned is not None:
                break  # pinned proxy failed: report it, never swap silently
    if pinned is not None:
        where = pinned if pinned else "direct connection"
        detail = f"{where} failed: {last if last is not None else 'connection failed'}"
    elif attempts and attempts[0]:
        detail = f"cached proxy {attempts[0]} stale and direct/probe failed: {last}"
    else:
        detail = f"direct failed and probe found no working local proxy: {last}"
    sys.stderr.write(f"network error ({detail})\n")
    sys.exit(1)


def fetch_payload(params, pinned):
    """One Google request with a single 429 backoff retry. Returns translate_raw's tuple."""
    for attempt in range(2):
        try:
            return translate_raw(params, pinned)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 1:
                die(f"HTTP {exc.code} from Google"
                    + (" (rate limited)" if exc.code == 429 else " (request rejected)"),
                    RATE_LIMIT_EXIT if exc.code == 429 else 1)
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            delay = float(retry_after) if (retry_after or "").isdigit() else 5.0
            sys.stderr.write(f"429 rate limited; backing off {delay:.0f}s ...\n")
            time.sleep(delay)
    die("rate limited twice in a row; slow down and retry later", RATE_LIMIT_EXIT)


# ---------------------------------------------------------------- chunk ----

def split_chunks(text, limit=CHUNK_MAX):
    if len(text) <= limit:
        return [text]
    pieces, current = [], ""
    for part in SENTENCE_SPLIT.split(text):
        part = part.strip()
        if not part:
            continue
        while len(part) > limit:  # single sentence longer than a chunk: hard split
            if current:
                pieces.append(current)
                current = ""
            pieces.append(part[:limit])
            part = part[limit:]
        if len(current) + len(part) + 1 > limit:
            pieces.append(current)
            current = part
        else:
            current = (current + " " + part) if current else part
    if current:
        pieces.append(current)
    return pieces or [text]


def translate_chunks(text, source, target, dt_list, pinned):
    """Translate text chunk by chunk.

    Returns (translation, detected_lang, n_chunks, proxy_used, probed).
    """
    chunks = split_chunks(text)
    translated, detected = [], None
    proxy_used, probed = "", False
    for i, chunk in enumerate(chunks):
        if i:
            time.sleep(CHUNK_SLEEP)
        params = {"client": "gtx", "sl": source or "auto", "tl": target,
                  "ie": "UTF-8", "oe": "UTF-8", "q": chunk, "dt": dt_list}
        payload, proxy_used, probed_any = fetch_payload(params, pinned)
        probed = probed or probed_any
        for seg in payload[0] or []:
            if isinstance(seg, list) and seg and isinstance(seg[0], str):
                translated.append(seg[0])
        if detected is None:
            detected = payload[2]
    return "".join(translated), detected, len(chunks), proxy_used, probed


def _base_params(args, text, dt_list):
    return {"client": "gtx", "sl": args.source or "auto", "tl": args.target,
            "ie": "UTF-8", "oe": "UTF-8", "q": text, "dt": dt_list}


# ---------------------------------------------------------------- main -----

def main():
    _relax_stdout_errors()
    parser = Parser(
        prog="gtx_translate.py",
        description="Free Google translation (unofficial gtx endpoint, no API key).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--from", dest="source", default="auto",
                        help="source language code (default: auto)")
        sp.add_argument("--to", dest="target", default="zh-CN", help="target language code")
        sp.add_argument("--json", action="store_true", help="machine-readable JSON (pure ASCII)")
        sp.add_argument("--proxy", default="", help="proxy URL, or direct/off/none to force direct")
        sp.add_argument("--no-proxy", action="store_true", help="force direct connection")

    p_t = sub.add_parser("translate", help="translate text")
    p_t.add_argument("text", help="text to translate")
    add_common(p_t)

    p_d = sub.add_parser("dict", help="translation + dictionary senses + romanization")
    p_d.add_argument("text", help="word or short phrase to look up")
    add_common(p_d)

    p_l = sub.add_parser("detect", help="detect source language only")
    p_l.add_argument("text", help="text to detect")
    p_l.add_argument("--json", action="store_true", help="machine-readable JSON (pure ASCII)")
    p_l.add_argument("--proxy", default="", help="proxy URL, or direct/off/none to force direct")
    p_l.add_argument("--no-proxy", action="store_true", help="force direct connection")

    args = parser.parse_args()
    pinned = _explicit_proxy(args)

    if args.cmd == "detect":
        params = {"client": "gtx", "sl": "auto", "tl": "en",
                  "ie": "UTF-8", "oe": "UTF-8", "dt": "t", "q": args.text}
        payload, proxy_used, probed = fetch_payload(params, pinned)
        if args.json:
            print(json.dumps({"lang": payload[2], "proxy": proxy_used or "direct",
                              "proxy_auto_probed": probed}, ensure_ascii=True))
        else:
            print(payload[2] or "unknown")
        return

    if args.cmd == "dict":
        if len(args.text) > CHUNK_MAX:
            die(f"dict input is limited to {CHUNK_MAX} chars; use translate for long text")
        payload, proxy_used, probed = fetch_payload(
            _base_params(args, args.text, ["t", "bd", "rm"]), pinned)
        translation = "".join(seg[0] for seg in payload[0] or []
                              if isinstance(seg, list) and seg and isinstance(seg[0], str))
        senses = []
        for entry in payload[1] or []:
            if isinstance(entry, list) and len(entry) >= 2:
                pos = entry[0] or ""
                terms = [t for t in (entry[1] or []) if isinstance(t, str)][:8]
                if pos or terms:
                    senses.append({"pos": pos, "terms": terms})
        roman = ""
        for seg in payload[0] or []:
            if isinstance(seg, list) and len(seg) > 3 and isinstance(seg[3], str) and seg[3]:
                roman = seg[3]
                break
        if args.json:
            print(json.dumps({"translation": translation, "detected_lang": payload[2],
                              "senses": senses, "romanization": roman,
                              "proxy": proxy_used or "direct",
                              "proxy_auto_probed": probed}, ensure_ascii=True))
            return
        print(translation)
        if roman:
            print(f"({roman})")
        for sense in senses:
            print(f"{sense['pos']}: " + ", ".join(sense["terms"]))
        return

    translation, detected, n, proxy_used, probed = translate_chunks(
        args.text, args.source, args.target, ["t"], pinned)
    if args.json:
        print(json.dumps({
            "translation": translation,
            "detected_lang": detected if (args.source or "auto") == "auto" else (args.source or None),
            "chunks": n,
            "proxy": proxy_used or "direct",
            "proxy_auto_probed": probed,
        }, ensure_ascii=True))
        return
    print(translation)


if __name__ == "__main__":
    main()
