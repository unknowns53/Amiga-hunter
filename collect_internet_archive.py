"""Fetch Amiga / LightWave 3D archives from Internet Archive items.

Usage:
    python collect_internet_archive.py                          # all curated identifiers
    python collect_internet_archive.py --identifier lightrom1   # one item
    python collect_internet_archive.py --identifier CommodoreAmigaApplicationsADF \
        --filter-keywords --limit 10                            # head/face/man names only
    python collect_internet_archive.py --identifier lightrom1 --list-only

Strategy:
- Internet Archive items expose a JSON metadata endpoint at
  https://archive.org/metadata/<identifier> that lists every file with
  size, source ("original"/"derivative"/"metadata"), and format hints.
- We keep only "original" files whose extension is in --include-ext
  (default = Amiga/PC archive + disk-image formats).
- Optional --filter-keywords matches pipeline.config.KEYWORDS against the
  filename (LightWave / Aminet collections often encode the subject in
  the file name, e.g. "head1.lwo", "manhead.lha").
- Downloads happen in parallel (--workers, default 4). Files that already
  exist with the expected size are skipped (cheap resume).

Output layout:
    archives_raw/ia/<identifier>/<original_filename>

Why a separate collector from collect_aminet.py: Aminet uses Apache-style
HTML directory listings; IA uses a JSON API and items can hold ISO images
that Aminet does not. Sharing code would force one of them into an awkward
shape, so they stay siblings.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pipeline.config import (
    ARCHIVES_DIR,
    INTERNET_ARCHIVE_IDENTIFIERS,
    KEYWORDS,
)

log = logging.getLogger("collect_ia")

USER_AGENT = "amiga-hunter-collector/0.1 (+research)"
METADATA_URL = "https://archive.org/metadata/{identifier}"
# Default download endpoint. Used when metadata doesn't expose a workable
# server hint (rare). IA's redirect layer through /download/ sometimes routes
# to broken CDN edges (dn7***.ca.archive.org returning 500), so we prefer the
# direct mirror URL from metadata's `workable_servers` / `server`+`dir` when
# available — see direct_url_from_meta().
DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"


def direct_url_from_meta(meta: dict, filename: str) -> str | None:
    """Build a direct mirror URL of the form
    https://{server}{dir}/{filename} from IA metadata.

    `workable_servers` is preferred (it's curated). Falls back to `d2`/`d1`/
    `server`. Returns None if no usable host is in metadata."""
    workable = meta.get("workable_servers") or []
    server = workable[0] if workable else (
        meta.get("d2") or meta.get("d1") or meta.get("server")
    )
    item_dir = meta.get("dir")
    if not server or not item_dir:
        return None
    return f"https://{server}{item_dir}/{quote(filename)}"

# Extensions we care about. Anything else (auto-generated thumbnails,
# .torrent files, _meta.xml, derivative .ocr.txt, etc.) is dropped.
DEFAULT_EXTS = {
    ".adf", ".hdf", ".dms", ".ipf",         # Amiga disk images
    ".iso", ".bin", ".cue",                 # PC/CD-ROM images
    ".lha", ".lzh", ".lzx",                 # Amiga archives
    ".zip", ".7z", ".rar",                  # Generic archives
    ".tar", ".gz", ".tgz",
    ".lwo", ".lwob", ".obj", ".3ds",        # Bare model files (rare on IA)
}

# Default cap on per-file size. CD-ROM compendiums (LIGHT-ROM, Amiga 3D)
# are around 500-700 MB, so 2 GB lets one slip through but blocks
# accidental multi-DVD downloads.
DEFAULT_MAX_SIZE_MB = 2048


# ---------- HTTP -----------------------------------------------------------

def http_get(url: str, timeout: int = 60) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_metadata(identifier: str) -> dict:
    url = METADATA_URL.format(identifier=identifier)
    log.info("Fetching metadata: %s", url)
    raw = http_get(url, timeout=60)
    return json.loads(raw.decode("utf-8", errors="replace"))


# ---------- file selection -------------------------------------------------

def keep_file(
    entry: dict,
    include_exts: set[str],
    keyword_filter: list[str] | None,
    name_substrings: list[str],
    max_size_bytes: int,
) -> tuple[bool, str]:
    """Decide whether a single IA file entry should be downloaded.

    Returns (keep, reason). reason is human-readable for log output."""
    name = entry.get("name", "")
    if not name:
        return False, "no name"

    # IA marks auto-generated files as "derivative". We only want originals.
    src = entry.get("source", "")
    if src not in ("", "original"):
        return False, f"non-original ({src})"

    suffix = Path(name).suffix.lower()
    if suffix not in include_exts:
        return False, f"ext {suffix or '<none>'} not in include set"

    # IA sizes are strings.
    size = int(entry.get("size") or 0)
    if size and size > max_size_bytes:
        return False, f"size {size / 1e6:.0f} MB > cap"

    low = name.lower()
    if name_substrings:
        if not any(s.lower() in low for s in name_substrings):
            return False, "no --include-name match"

    if keyword_filter is not None:
        if not any(kw in low for kw in keyword_filter):
            return False, "no keyword match"

    return True, "ok"


# ---------- download -------------------------------------------------------

def download_file(
    identifier: str,
    name: str,
    expected_size: int,
    target_dir: Path,
    timeout: int = 1800,
    direct_url: str | None = None,
) -> tuple[str, str]:
    """Download one IA file. Returns (name, status) where status is one of
    'downloaded' / 'already_present' / 'failed'.

    If direct_url is provided (built from item metadata), use it instead of
    /download/. Falls back to /download/ if direct_url fails."""
    dest = target_dir / name
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and dest.stat().st_size > 0:
        if expected_size == 0 or dest.stat().st_size == expected_size:
            return name, "already_present"

    candidate_urls: list[str] = []
    if direct_url:
        candidate_urls.append(direct_url)
    candidate_urls.append(DOWNLOAD_URL.format(identifier=identifier, filename=quote(name)))

    for url in candidate_urls:
        try:
            # Stream to disk; IA files can be hundreds of MB.
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=timeout) as resp, open(dest, "wb") as fh:
                while True:
                    chunk = resp.read(1 << 20)  # 1 MiB
                    if not chunk:
                        break
                    fh.write(chunk)
            return name, "downloaded"
        except HTTPError as e:
            log.warning("HTTP %s for %s", e.code, url)
        except URLError as e:
            log.warning("URL error for %s: %s", url, e)
        except Exception as e:
            log.warning("Download failed %s: %s", url, e)
        # Clean up partial file before next attempt / final failure.
        try:
            if dest.exists() and dest.stat().st_size != expected_size:
                dest.unlink()
        except Exception:
            pass
    return name, "failed"


# ---------- per-identifier orchestration -----------------------------------

def collect_item(
    identifier: str,
    base_target: Path,
    include_exts: set[str],
    keyword_filter: list[str] | None,
    name_substrings: list[str],
    max_size_bytes: int,
    limit: int | None,
    workers: int,
    list_only: bool,
) -> dict:
    summary = {
        "identifier": identifier,
        "files_total": 0,
        "kept": 0,
        "downloaded": 0,
        "already_present": 0,
        "failed": 0,
        "skipped": 0,
    }
    try:
        meta = fetch_metadata(identifier)
    except Exception as e:
        log.error("Cannot fetch metadata for %s: %s", identifier, e)
        summary["failed"] = 1
        return summary

    files = meta.get("files") or []
    summary["files_total"] = len(files)
    log.info("[%s] %d file entries in item", identifier, len(files))

    keep: list[tuple[str, int]] = []
    for entry in files:
        ok, reason = keep_file(
            entry, include_exts, keyword_filter, name_substrings, max_size_bytes,
        )
        if ok:
            keep.append((entry["name"], int(entry.get("size") or 0)))
        else:
            summary["skipped"] += 1
            log.debug("[%s] drop %s (%s)", identifier, entry.get("name"), reason)

    if limit is not None:
        keep = keep[:limit]
    summary["kept"] = len(keep)
    log.info("[%s] %d file(s) selected for download", identifier, len(keep))

    if list_only:
        for name, size in keep:
            log.info("  %10d  %s", size, name)
        return summary

    target_dir = base_target / identifier
    target_dir.mkdir(parents=True, exist_ok=True)

    if not keep:
        return summary

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = {
            ex.submit(
                download_file, identifier, name, size, target_dir, 1800,
                direct_url_from_meta(meta, name),
            ): name
            for name, size in keep
        }
        for i, fut in enumerate(as_completed(futures), 1):
            name, status = fut.result()
            summary[status] = summary.get(status, 0) + 1
            log.info("[%s] (%d/%d) %s -> %s",
                     identifier, i, len(keep), status, name)

    return summary


# ---------- CLI ------------------------------------------------------------

def parse_ext_list(s: str) -> set[str]:
    parts = [p.strip().lower() for p in s.split(",") if p.strip()]
    return {p if p.startswith(".") else "." + p for p in parts}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--identifier", action="append", default=None,
        help="IA item identifier (repeatable). If omitted, uses the curated "
             "INTERNET_ARCHIVE_IDENTIFIERS list from pipeline.config.",
    )
    ap.add_argument(
        "--target", type=Path, default=ARCHIVES_DIR / "ia",
        help="local download dir (default: archives_raw/ia/)",
    )
    ap.add_argument(
        "--include-ext", default=",".join(sorted(DEFAULT_EXTS)),
        help="comma-separated allowed extensions",
    )
    ap.add_argument(
        "--filter-keywords", action="store_true",
        help="only download files whose name contains a keyword from "
             "pipeline.config.KEYWORDS (head/face/man/...)",
    )
    ap.add_argument(
        "--include-name", action="append", default=[],
        help="additional case-insensitive substring filter on filename "
             "(repeatable). Combines with --filter-keywords (AND).",
    )
    ap.add_argument(
        "--max-size-mb", type=int, default=DEFAULT_MAX_SIZE_MB,
        help=f"per-file size cap (default: {DEFAULT_MAX_SIZE_MB} MB)",
    )
    ap.add_argument("--limit", type=int, help="cap downloads per item")
    ap.add_argument(
        "--workers", type=int, default=4,
        help="parallel download workers per item (default: 4)",
    )
    ap.add_argument(
        "--list-only", action="store_true",
        help="print selected files without downloading",
    )
    ap.add_argument(
        "--sleep", type=float, default=0.0,
        help="seconds between identifier-level requests (default: 0)",
    )
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    identifiers = args.identifier or list(INTERNET_ARCHIVE_IDENTIFIERS)
    include_exts = parse_ext_list(args.include_ext)
    keyword_filter = list(KEYWORDS) if args.filter_keywords else None
    max_size_bytes = args.max_size_mb * 1024 * 1024

    log.info("Targets: %s", ", ".join(identifiers))
    log.info("Extensions: %s", ", ".join(sorted(include_exts)))
    if keyword_filter:
        log.info("Keyword filter: %s", ", ".join(keyword_filter))
    if args.include_name:
        log.info("Name filter: %s", ", ".join(args.include_name))

    overall: list[dict] = []
    for ident in identifiers:
        summary = collect_item(
            ident, args.target, include_exts, keyword_filter,
            args.include_name, max_size_bytes, args.limit, args.workers,
            args.list_only,
        )
        overall.append(summary)
        if args.sleep > 0:
            time.sleep(args.sleep)

    log.info("=== Per-item summary ===")
    for s in overall:
        log.info(
            "%-50s files=%d kept=%d dl=%d have=%d fail=%d skip=%d",
            s["identifier"], s["files_total"], s["kept"],
            s.get("downloaded", 0), s.get("already_present", 0),
            s.get("failed", 0), s["skipped"],
        )


if __name__ == "__main__":
    main()
