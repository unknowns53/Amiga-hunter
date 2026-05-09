"""Fetch Amiga 3D-object archives from Aminet into archives_raw/.

Usage:
    python collect_aminet.py                       # default: gfx/3dobj/, full mirror
    python collect_aminet.py --filter-readme       # only files whose .readme matches KEYWORDS
    python collect_aminet.py --dir gfx/3d/ --limit 50

Strategy:
- Parses the Apache-style directory index at us.aminet.net.
- Downloads each .lha / .lzx / .lzh plus its companion .readme into ARCHIVES_DIR.
- Optional --filter-readme pre-fetches the .readme and skips archives whose
  text contains none of the KEYWORDS from pipeline/config.py.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from pipeline.config import ARCHIVES_DIR, KEYWORDS

log = logging.getLogger("collect_aminet")

DEFAULT_BASE = "https://us.aminet.net/aminet/"
DEFAULT_DIR = "gfx/3dobj/"
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


def collect(
    base: str,
    subdir: str,
    target: Path,
    filter_keywords: list[str] | None,
    limit: int | None,
    sleep: float,
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

    for i, name in enumerate(archives, 1):
        archive_url = urljoin(base, subdir + name)
        stem = name.rsplit(".", 1)[0]
        readme_url = urljoin(base, subdir + stem + ".readme")
        local_archive = target / name
        local_readme = target / (stem + ".readme")

        readme_text = ""
        if filter_keywords is not None:
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
    parser.add_argument("--dir", default=DEFAULT_DIR, help="subdirectory (default: gfx/3dobj/)")
    parser.add_argument("--target", type=Path, default=ARCHIVES_DIR, help="local archives dir")
    parser.add_argument(
        "--filter-readme",
        action="store_true",
        help="only download archives whose .readme contains a keyword from pipeline.config.KEYWORDS",
    )
    parser.add_argument("--limit", type=int, help="cap number of files (for testing)")
    parser.add_argument("--sleep", type=float, default=0.5, help="seconds between requests")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    keywords = KEYWORDS if args.filter_readme else None
    summary = collect(args.base, args.dir, args.target, keywords, args.limit, args.sleep)
    log.info("Summary: %s", summary)


if __name__ == "__main__":
    main()
