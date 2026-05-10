"""Fetch Amiga 3D-object archives from Aminet into archives_raw/.

Usage:
    python collect_aminet.py                       # default: gfx/3d/ on FAU mirror
    python collect_aminet.py --filter-readme       # only files whose .readme matches KEYWORDS
    python collect_aminet.py --dir gfx/misc/ --limit 50

Strategy:
- Parses the Apache-style directory index at ftp.fau.de.
- Downloads each .lha / .lzx / .lzh plus its companion .readme into ARCHIVES_DIR.
- Optional --filter-readme pre-fetches the .readme and skips archives whose
  text contains none of the KEYWORDS from pipeline/config.py.

Note: the historical Aminet path `gfx/3dobj/` (used by older versions of this
script) no longer exists on any mirror as of 2026 — `gfx/3d/` is now the
canonical location for Amiga 3D content (apps + bundled sample models).
The legacy `us.aminet.net` host also has a TLS hostname-mismatch issue;
`ftp.fau.de` is a known-good HTTPS mirror.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from pipeline.config import ARCHIVES_DIR, KEYWORDS

log = logging.getLogger("collect_aminet")

DEFAULT_BASE = "https://ftp.fau.de/aminet/"
DEFAULT_DIR = "gfx/3d/"
USER_AGENT = "amiga-hunter-collector/0.1 (+research)"

ARCHIVE_SUFFIXES = (".lha", ".lzx", ".lzh")
HREF_RE = re.compile(r'href="([^"#?][^"]*)"', re.IGNORECASE)


def http_get(url: str, timeout: int = 60) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def list_directory(base: str, subdir: str) -> list[str]:
    if not subdir.endswith("/"):
        subdir += "/"
    url = urljoin(base, subdir)
    log.info("Listing %s", url)
    html = http_get(url).decode("utf-8", errors="replace")
    names = HREF_RE.findall(html)
    out: list[str] = []
    for n in names:
        # Skip parent / sort links / absolute URLs
        if n.startswith("/") or n.startswith("?") or "://" in n or n in ("../",):
            continue
        # Skip .readme here; we handle them per-archive below.
        out.append(n)
    return out


def download_to(url: str, dest: Path, timeout: int = 600) -> bool:
    try:
        data = http_get(url, timeout=timeout)
    except HTTPError as e:
        log.warning("HTTP %s for %s", e.code, url)
        return False
    except URLError as e:
        log.warning("URL error for %s: %s", url, e)
        return False
    except Exception as e:
        log.warning("Download failed %s: %s", url, e)
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def readme_keyword_hits(text: str, keywords: list[str]) -> list[str]:
    low = text.lower()
    return [kw for kw in keywords if kw in low]


def _fetch_readme(base: str, subdir: str, name: str) -> tuple[str, str]:
    """Worker: fetch a single .readme. Returns (name, text) — empty text on
    failure. Used by the parallel prefetch."""
    stem = name.rsplit(".", 1)[0]
    url = urljoin(base, subdir + stem + ".readme")
    try:
        return name, http_get(url, timeout=30).decode("utf-8", errors="replace")
    except Exception:
        return name, ""


def prefetch_readmes(base: str, subdir: str, names: list[str], workers: int) -> dict[str, str]:
    """Fetch all readmes concurrently. Returns {name: readme_text}."""
    out: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_fetch_readme, base, subdir, n): n for n in names}
        done = 0
        for fut in as_completed(futures):
            name, text = fut.result()
            out[name] = text
            done += 1
            if done % 50 == 0:
                log.info("readme prefetch: %d/%d", done, len(names))
    return out


def collect(
    base: str,
    subdir: str,
    target: Path,
    filter_keywords: list[str] | None,
    limit: int | None,
    sleep: float,
    workers: int = 1,
) -> dict:
    target.mkdir(parents=True, exist_ok=True)
    names = list_directory(base, subdir)
    archives = [n for n in names if n.lower().endswith(ARCHIVE_SUFFIXES)]
    log.info("Found %d archive(s) in %s", len(archives), subdir)
    if limit is not None:
        archives = archives[:limit]

    summary = {
        "listed": len(archives),
        "downloaded": 0,
        "already_present": 0,
        "skipped_no_match": 0,
        "failed": 0,
    }

    # Optional parallel prefetch: when filtering by readme, fetching them
    # concurrently is the single biggest speedup (an N-archive listing goes
    # from N*sleep seconds to roughly N/workers * one-RTT). Downloads stay
    # sequential with the existing sleep so we don't hammer the mirror.
    readme_cache: dict[str, str] = {}
    if filter_keywords is not None and workers > 1:
        log.info("Prefetching %d readmes with %d workers ...", len(archives), workers)
        readme_cache = prefetch_readmes(base, subdir, archives, workers)

    for i, name in enumerate(archives, 1):
        archive_url = urljoin(base, subdir + name)
        stem = name.rsplit(".", 1)[0]
        readme_url = urljoin(base, subdir + stem + ".readme")
        local_archive = target / name
        local_readme = target / (stem + ".readme")

        readme_text = ""
        if filter_keywords is not None:
            if name in readme_cache:
                readme_text = readme_cache[name]
            else:
                try:
                    readme_text = http_get(readme_url, timeout=30).decode(
                        "utf-8", errors="replace"
                    )
                except Exception as e:
                    log.debug("readme fetch failed for %s: %s", name, e)
            hits = readme_keyword_hits(readme_text, filter_keywords)
            if not hits:
                log.info("[%d/%d] skip (no kw): %s", i, len(archives), name)
                summary["skipped_no_match"] += 1
                if not readme_cache:
                    time.sleep(sleep)
                continue
            log.info("[%d/%d] kw=%s -> %s", i, len(archives), ",".join(hits), name)

        if local_archive.exists() and local_archive.stat().st_size > 0:
            log.info("[%d/%d] have: %s", i, len(archives), name)
            summary["already_present"] += 1
        else:
            log.info("[%d/%d] get: %s", i, len(archives), name)
            if download_to(archive_url, local_archive):
                summary["downloaded"] += 1
            else:
                summary["failed"] += 1

        if not local_readme.exists():
            if readme_text:
                local_readme.write_text(readme_text, encoding="utf-8")
            else:
                download_to(readme_url, local_readme, timeout=30)

        time.sleep(sleep)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=DEFAULT_BASE, help="Aminet HTTPS mirror base URL")
    parser.add_argument("--dir", default=DEFAULT_DIR, help="subdirectory (default: gfx/3d/)")
    parser.add_argument("--target", type=Path, default=ARCHIVES_DIR, help="local archives dir")
    parser.add_argument(
        "--filter-readme",
        action="store_true",
        help="only download archives whose .readme contains a keyword from pipeline.config.KEYWORDS",
    )
    parser.add_argument("--limit", type=int, help="cap number of files (for testing)")
    parser.add_argument("--sleep", type=float, default=0.5, help="seconds between requests")
    parser.add_argument(
        "--workers", type=int, default=8,
        help="parallel readme prefetch workers (default: 8; set to 1 to disable)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    keywords = KEYWORDS if args.filter_readme else None
    summary = collect(args.base, args.dir, args.target, keywords, args.limit,
                      args.sleep, workers=args.workers)
    log.info("Summary: %s", summary)


if __name__ == "__main__":
    main()
