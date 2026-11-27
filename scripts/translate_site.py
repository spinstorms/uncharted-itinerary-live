#!/usr/bin/env python3
"""Full-site translation for stayodds.com.

Two jobs:

  --translate DIST   Read every built page in DIST, collect each piece of visible text, and translate the
                     pieces not yet in the cache (data/i18n-cache/<lang>.json) with Gemini. Resumable: the
                     cache is saved as it goes, so a stopped run carries on next time and nothing is paid twice.

  --shards DIST      Write the translations the pages need into DIST/assets/i18n/<lang>/:
                     common.json (text on many pages) and p/<page>.json (text on one page).
                     stayodds-i18n.js loads common + the page's own file when a language is picked.

Hotel names and brand names are left as they are. Nothing is translated on the visitor's device.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "i18n-cache"
LANGS = {
    "es": "Spanish (Spain)",
    "pt-BR": "Brazilian Portuguese",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ar": "Modern Standard Arabic",
    "ja": "Japanese",
    "id": "Indonesian",
    "fa": "Persian (Farsi)",
    "zh-Hans": "Simplified Chinese",
    "ko": "Korean",
}
SKIP_TAGS = {"script", "style", "noscript", "svg", "code", "pre"}
ATTRS = ("placeholder", "aria-label", "title", "alt")
COMMON_MIN_PAGES = 20
MAX_LEN = 2000
BATCH = 60


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def page_key(rel: str) -> str:
    """Same rule as stayodds-i18n.js: the URL path without slashes at the ends, '/' -> '__', '' -> 'home'."""
    p = rel.replace("\\", "/")
    if p.endswith("index.html"):
        p = p[: -len("index.html")]
    elif p.endswith(".html"):
        p = p[: -len(".html")]
    p = p.strip("/")
    return re.sub(r"[^A-Za-z0-9_-]+", "__", p) or "home"


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.out: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
            return
        for k, v in attrs:
            if k in ATTRS and v:
                self._add(v)

    def handle_startendtag(self, tag, attrs):
        for k, v in attrs:
            if k in ATTRS and v:
                self._add(v)

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self._add(data)

    def _add(self, s: str) -> None:
        s = norm(s)
        if s and len(s) <= MAX_LEN and re.search(r"[A-Za-z]{2}", s):
            self.out.append(s)


def keep_as_is() -> set[str]:
    """Hotel and brand names: never translated."""
    names: set[str] = set()
    try:
        hotels = json.loads((ROOT / "data" / "stayodds-directory.json").read_text(encoding="utf-8"))["hotels"]
    except Exception:
        return names
    for h in hotels:
        for k in ("name", "brand"):
            if h.get(k):
                names.add(norm(str(h[k])))
    names |= {"StayOdds", "StayOdds.", "The Uncharted Itinerary", "Uncharted Itinerary"}
    return names


def collect(dist: Path) -> dict[str, set[str]]:
    skip = keep_as_is()
    pages: dict[str, set[str]] = {}
    for f in dist.rglob("*.html"):
        rel = f.relative_to(dist).as_posix()
        if rel.startswith("assets/"):
            continue
        p = TextParser()
        p.feed(f.read_text(encoding="utf-8", errors="ignore"))
        pages[page_key(rel)] = {s for s in p.out if s not in skip}
    return pages


SCRIPT_STRINGS = {
    # stayodds-hotel-acc.js
    "How guests rank it", "Where it sits among hotels nearby", "Why this score", "Our stay, guests and critics, side by side",
    "Before you book", "Best months, prices and tips", "What guests love", "And what to know before you go",
    "Every review and score", "Each source and how we weigh it",
}


def ui_strings() -> set[str]:
    """Strings the site's own scripts draw on the page (the small UI dictionaries, plus the hotel-page rows)."""
    try:
        keys = set(json.loads((ROOT / "assets" / "i18n" / "es.json").read_text(encoding="utf-8")).keys())
    except Exception:
        keys = set()
    return keys | SCRIPT_STRINGS


def load_cache(lang: str) -> dict[str, str]:
    f = CACHE_DIR / f"{lang}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def save_cache(lang: str, cache: dict[str, str]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_DIR / f"{lang}.json.tmp"
    tmp.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(CACHE_DIR / f"{lang}.json")


def gemini(items: list[str], lang_name: str, key: str) -> list[str] | None:
    prompt = (
        f"Translate each string in this JSON array from English into {lang_name} for a luxury hotel comparison website "
        "(StayOdds, by the travel channel The Uncharted Itinerary). Keep it natural and concise, the way a native travel "
        "site would write it. Do NOT translate hotel names, brand names, people's names, 'StayOdds', 'Uncharted', "
        "currency amounts, numbers, URLs or {placeholders}. Keep symbols like →, ↗, %, £ and emoji where they are. "
        "Return ONLY a JSON array of the same length, in the same order.\n\n" + json.dumps(items, ensure_ascii=False)
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }).encode("utf-8")
    model = os.environ.get("GEMINI_TRANSLATE_MODEL", "gemini-flash-lite-latest")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for attempt in range(5):
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json", "X-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode("utf-8"))
            out = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
            if isinstance(out, list) and len(out) == len(items) and all(isinstance(x, str) for x in out):
                return out
            print(f"  [warn] wrong length ({len(out) if isinstance(out, list) else '?'} vs {len(items)})", flush=True)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(4 * (attempt + 1))
                continue
            print(f"  [warn] HTTP {e.code}: {e.read()[:200]!r}", flush=True)
            return None
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] {e}", flush=True)
            time.sleep(2)
    return None


def translate(dist: Path, langs: list[str], budget_s: int) -> None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        sys.exit("GEMINI_API_KEY is not set")
    pages = collect(dist)
    counts = Counter(s for strs in pages.values() for s in strs)
    # most-used text first, so a partial run already covers the menus, buttons and shared blocks
    wanted = [s for s, _ in counts.most_common()] + sorted(ui_strings() - set(counts))
    deadline = time.time() + budget_s
    print(f"{len(pages)} pages, {len(wanted)} unique strings, {sum(map(len, wanted)):,} characters", flush=True)
    for lang in langs:
        cache = load_cache(lang)
        todo = [s for s in wanted if s not in cache]
        print(f"[{lang}] {len(cache):,} cached, {len(todo):,} to translate", flush=True)
        batches, cur, size = [], [], 0
        for s in todo:
            if cur and (len(cur) >= BATCH or size + len(s) > 6000):
                batches.append(cur)
                cur, size = [], 0
            cur.append(s)
            size += len(s)
        if cur:
            batches.append(cur)
        lock, done = threading.Lock(), [0]

        def run(b: list[str]) -> None:
            if time.time() > deadline:
                return
            out = gemini(b, LANGS[lang], key)
            if not out:
                return
            with lock:
                for src, tr in zip(b, out):
                    tr = norm(tr)
                    if tr:
                        cache[src] = tr
                done[0] += 1
                if done[0] % 25 == 0:
                    save_cache(lang, cache)
                    print(f"  [{lang}] {done[0]}/{len(batches)} batches", flush=True)

        with ThreadPoolExecutor(max_workers=int(os.environ.get("TRANSLATE_THREADS", "8"))) as ex:
            for f in as_completed([ex.submit(run, b) for b in batches]):
                f.result()
        save_cache(lang, cache)
        print(f"[{lang}] now {len(cache):,} cached", flush=True)
        if time.time() > deadline:
            print("Time budget used up; the next run carries on.", flush=True)
            break


def shards(dist: Path) -> None:
    pages = collect(dist)
    counts = Counter(s for strs in pages.values() for s in strs)
    common_keys = {s for s, n in counts.items() if n >= COMMON_MIN_PAGES} | ui_strings()
    for lang in LANGS:
        cache = load_cache(lang)
        if not cache:
            continue
        out = dist / "assets" / "i18n" / lang
        (out / "p").mkdir(parents=True, exist_ok=True)
        common = {s: cache[s] for s in common_keys if s in cache}
        (out / "common.json").write_text(json.dumps(common, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        n = 0
        for pk, strs in pages.items():
            d = {s: cache[s] for s in strs if s in cache and s not in common_keys}
            if d:
                (out / "p" / f"{pk}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                n += 1
        print(f"[{lang}] common {len(common):,} strings, {n} page files")


def main() -> None:
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "--translate":
        langs = [a for a in args[2:] if a in LANGS] or list(LANGS)
        translate(Path(args[1]), langs, int(os.environ.get("TRANSLATE_BUDGET_SECONDS", "19800")))
    elif len(args) == 2 and args[0] == "--shards":
        shards(Path(args[1]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
