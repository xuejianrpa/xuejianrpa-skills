#!/usr/bin/env python3
"""Upload files / text snippets to a Uguu temporary file host. No API key.

Endpoint: POST https://uguu.se/upload  (multipart field name "files[]")
Response format selected server-side via ?output=json|text|html|csv; this
script always asks for json and renders locally. Official instance keeps
files for 8 hours (fixed in server config - there is NO per-request expiry
parameter); URLs are public and function as the only credential.

Subcommands:
  upload <path> [<path>...] [--json] [--urls-only]
      Upload one or more files. Each file goes in its own request so one
      policy-rejected file cannot kill the whole batch (the server errors
      out a multi-file request on the first bad file).
  text [<content>] [--name paste.txt] [--json] [--urls-only]
      Upload a text snippet as a file without touching disk (multipart is
      built in memory). Reads stdin when <content> is omitted.

Output:
  default      one line per file: "<url>  <original name>"
  --urls-only  just the URLs, one per line (pipe friendly)
  --json       machine-readable pure-ASCII JSON:
               {"files":[{"url","name","size","hash","mimetype","dupe"}],
                "errors":[{"name","reason"}], "expires_hours": 8}

Notes: direct connection from CN networks (no proxy machinery, unlike the
translate skill - uguu.se is not blocked). Files up to 128 MB (client-side
guard fails fast before spending the upload). Do NOT upload secrets: the
URL is public and any holder of it can fetch the file. Non-official API
usage of a community service - no SLA.

Exit codes: 0 all uploads ok, 1 error (usage/network/server/policy;
partial batches report per-file errors in --json and still exit 1).
"""

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request

UPLOAD_URL = "https://uguu.se/upload"
USER_AGENT = "xuejian-uguu-upload/1.0"
MAX_UPLOAD_BYTES = 128 * 1024 * 1024   # official instance max_upload_size
DEFAULT_TIMEOUT = 300                  # seconds; 128 MB on a slow uplink
RETRY_ATTEMPTS = 3                     # transient errors: 502/503/504 + network
RETRY_SLEEP = 2.0                      # linear backoff: 2s, 4s
RETRY_STATUS = {502, 503, 504}         # uguu.se intermittently 503s (no backend)
BOUNDARY = "xuejianUguuForm"


def _relax_stdout_errors():
    # Keep the console's original encoding (forcing UTF-8 garbles GBK pipes);
    # only stop hard crashes on characters the pipe cannot represent.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError):
            pass


def die(message, code=1):
    sys.stderr.write("uguu_upload.py: " + message.rstrip() + "\n")
    sys.exit(code)


class Parser(argparse.ArgumentParser):
    # Keep one documented failure code: argparse usage errors also exit 1.
    def error(self, message):
        self.print_usage(sys.stderr)
        die(f"error: {message}", 1)


# ------------------------------------------------------------ multipart ----

def build_multipart(entries):
    """entries: list of (field, filename, content_type, payload_bytes)."""
    body = bytearray()
    for field, filename, content_type, payload in entries:
        body += b"--" + BOUNDARY.encode() + b"\r\n"
        body += (
            f'Content-Disposition: form-data; name="{field}"; '
            f'filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n"
            "\r\n"  # blank line ends the headers; body follows
        ).encode()
        body += payload + b"\r\n"
    body += b"--" + BOUNDARY.encode() + b"--\r\n"
    return bytes(body)


def post_upload(entries, timeout):
    """POST multipart to the uguu endpoint, return parsed json dict.

    Transient failures are retried: network errors and 502/503/504 (the
    uguu.se load balancer intermittently answers "503 no backend" under
    quick successive uploads). 4xx/5xx otherwise are fatal - that is the
    server rejecting this exact upload.
    """
    body = build_multipart(entries)
    last_error = None
    for attempt in range(RETRY_ATTEMPTS):
        request = urllib.request.Request(
            UPLOAD_URL + "?output=json",
            data=body,
            method="POST",
            headers={
                "Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            snippet = exc.read(300).decode("utf-8", errors="replace").strip()
            if exc.code in RETRY_STATUS:
                last_error = f"HTTP {exc.code}: {snippet}"
                if attempt + 1 < RETRY_ATTEMPTS:
                    time.sleep(RETRY_SLEEP * (attempt + 1))
                    continue
                die(f"{last_error} - still failing after {RETRY_ATTEMPTS} attempts "
                    f"(uguu.se backend episode; retry later)")
            die(f"HTTP {exc.code} from {UPLOAD_URL}: {snippet}")
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = exc
            if attempt + 1 < RETRY_ATTEMPTS:
                time.sleep(RETRY_SLEEP * (attempt + 1))
    die(f"giving up after {RETRY_ATTEMPTS} attempts: {last_error}")


# ------------------------------------------------------------- uploading ----

def guess_content_type(path):
    guessed = mimetypes.guess_type(path)[0]
    return guessed or "application/octet-stream"


def upload_files(paths, timeout):
    ok, failed = [], []
    for path in paths:
        name = os.path.basename(path)
        if not os.path.isfile(path):
            failed.append({"name": name, "reason": "not a file (missing or a directory)"})
            continue
        size = os.path.getsize(path)
        if size > MAX_UPLOAD_BYTES:
            failed.append({
                "name": name,
                "reason": f"{size} bytes exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
            })
            continue
        with open(path, "rb") as handle:
            payload = handle.read()
        entries = [("files[]", name, guess_content_type(path), payload)]
        result = post_upload(entries, timeout)
        files = result.get("files") or []
        errors = result.get("errors") or []
        if files:
            for item in files:
                ok.append({
                    "url": item.get("url", ""),
                    "name": name,
                    "size": item.get("size", size),
                    "hash": item.get("hash", ""),
                    "mimetype": item.get("mimetype", ""),
                    "dupe": bool(item.get("dupe", False)),
                })
        if errors or not files:
            reason = "; ".join(
                e.get("description") or e.get("hash") or json.dumps(e, ensure_ascii=True)
                for e in errors
            ) or "server returned no file entry"
            failed.append({"name": name, "reason": reason})
    return ok, failed


def upload_text(content, name, timeout):
    payload = content.encode("utf-8")
    if len(payload) > MAX_UPLOAD_BYTES:
        die(f"text is {len(payload)} bytes, exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
    entries = [("files[]", name, "text/plain; charset=utf-8", payload)]
    result = post_upload(entries, timeout)
    files = result.get("files") or []
    errors = result.get("errors") or []
    if not files:
        reason = "; ".join(
            e.get("description") or json.dumps(e, ensure_ascii=True) for e in errors
        ) or "server returned no file entry"
        die(f"upload rejected: {reason}")
    item = files[0]
    return {
        "url": item.get("url", ""),
        "name": name,
        "size": item.get("size", len(payload)),
        "hash": item.get("hash", ""),
        "mimetype": item.get("mimetype", "text/plain"),
        "dupe": bool(item.get("dupe", False)),
    }


# --------------------------------------------------------------- output ----

def render(results, failed, args, expires_note):
    if args.json:
        print(json.dumps({
            "files": results,
            "errors": failed,
            "expires_hours": expires_note,
            "endpoint": UPLOAD_URL,
        }, ensure_ascii=True))
        return 1 if failed else 0
    for item in results:
        if args.urls_only:
            print(item["url"])
        else:
            print(f"{item['url']}  {item['name']}")
    for item in failed:
        sys.stderr.write(f"FAILED {item['name']}: {item['reason']}\n")
    return 1 if failed else 0


def main():
    _relax_stdout_errors()
    parser = Parser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--json", action="store_true",
                        help="machine-readable pure-ASCII JSON")
        sp.add_argument("--urls-only", action="store_true",
                        help="print only the URLs, one per line")
        sp.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"per-request timeout seconds (default {DEFAULT_TIMEOUT})")

    p_up = sub.add_parser("upload", help="upload one or more files")
    p_up.add_argument("paths", nargs="+", help="file path(s) to upload")
    add_common(p_up)

    p_tx = sub.add_parser("text", help="upload a text snippet (stdin if no arg)")
    p_tx.add_argument("content", nargs="?", default=None,
                      help="text to upload; omit to read stdin")
    p_tx.add_argument("--name", default="paste.txt",
                      help='stored filename, extension decides the served type (default "paste.txt")')
    add_common(p_tx)

    args = parser.parse_args()
    if args.urls_only and args.json:
        die("--json and --urls-only are mutually exclusive")

    if args.cmd == "upload":
        ok, failed = upload_files(args.paths, args.timeout)
        sys.exit(render(ok, failed, args, expires_note=8))
    else:
        content = args.content
        if content is None:
            if sys.stdin.isatty():
                die("no <content> given and stdin is a tty; pass text or pipe it in")
            content = sys.stdin.read()
        if content == "":
            die("refusing to upload empty text")
        item = upload_text(content, args.name, args.timeout)
        sys.exit(render([item], [], args, expires_note=8))


if __name__ == "__main__":
    main()
