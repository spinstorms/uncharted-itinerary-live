#!/usr/bin/env python3
"""
StayOdds Thumbnail Optimizer
- Downloads hotel hero images and converts them to ultra-fast 640x400 WebP thumbnails
  in assets/thumbs/<slug>.webp (~15-28 KB each instead of 300 KB - 17.4 MB originals).
- For any broken (HTTP 403/404) or missing hero image whose property has a nuiteeHotelId,
  fetches its static main_photo from LiteAPI's free /data/hotel endpoint.
- Also optimizes assets/logo.jpg to crisp 256x256 JPEG (<10 KB).
"""

from __future__ import annotations

import concurrent.futures
import io
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
THUMBS_DIR = ROOT / "assets" / "thumbs"
THUMBS_DIR.mkdir(parents=True, exist_ok=True)

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


def load_env_local() -> None:
    env_path = ROOT / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def fetch_bytes(url: str, timeout: int = 12) -> bytes | None:
    if not url or not url.startswith("http"):
        return None
    try:
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except Exception:
        return None
    return None


def fetch_liteapi_photo(hotel_id: str, api_key: str) -> str | None:
    if not hotel_id or not api_key:
        return None
    url = f"https://api.liteapi.travel/v3.0/data/hotel?hotelId={urllib.parse.quote(hotel_id)}"
    try:
        req = urllib.request.Request(
            url,
            headers={"X-API-Key": api_key, "Accept": "application/json", "User-Agent": "StayOdds/1.0"},
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8")).get("data") or {}
            photo = data.get("main_photo") or data.get("thumbnail")
            if photo and str(photo).startswith("http"):
                return str(photo)
            imgs = data.get("hotelImages") or []
            for img in imgs:
                u = img.get("url") or img.get("urlHd")
                if u and str(u).startswith("http"):
                    return str(u)
    except Exception:
        return None
    return None


def save_webp(raw: bytes, out_path: Path, size: tuple[int, int] = (640, 400)) -> tuple[int, int]:
    img = Image.open(io.BytesIO(raw))
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (245, 245, 245))
        if img.mode == "P":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Auto-orient EXIF & cleanly crop/fit to 640x400
    img = ImageOps.exif_transpose(img)
    fitted = ImageOps.fit(img, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    buf = io.BytesIO()
    fitted.save(buf, format="WEBP", quality=76, method=5)
    out_bytes = buf.getvalue()
    out_path.write_bytes(out_bytes)
    return len(raw), len(out_bytes)


def optimize_logo() -> None:
    logo_path = ROOT / "assets" / "logo.jpg"
    if not logo_path.exists():
        return
    orig_size = logo_path.stat().st_size
    if orig_size <= 12_000:
        print(f"Logo already optimized: {orig_size/1024:.1f} KB")
        return
    img = Image.open(logo_path).convert("RGB")
    img = ImageOps.fit(img, (256, 256), method=Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82, optimize=True, progressive=True)
    new_bytes = buf.getvalue()
    if len(new_bytes) < orig_size:
        logo_path.write_bytes(new_bytes)
        print(f"Optimized assets/logo.jpg: {orig_size/1024:.1f} KB -> {len(new_bytes)/1024:.1f} KB")


def process_hotel(h: dict, nuitee_key: str) -> tuple[str, str, int, int]:
    slug = h["id"]
    out_path = THUMBS_DIR / f"{slug}.webp"
    if out_path.exists() and out_path.stat().st_size > 2500:
        return (slug, "CACHED", 0, out_path.stat().st_size)

    url = h.get("thumbnail") or ""
    raw = None

    # For YouTube thumbnails, try maxresdefault first for letterbox-free 16:9 crop, fall back to hqdefault
    if "i.ytimg.com" in url:
        if "hqdefault.jpg" in url:
            raw = fetch_bytes(url.replace("hqdefault.jpg", "maxresdefault.jpg")) or fetch_bytes(url)
        else:
            raw = fetch_bytes(url) or fetch_bytes(url.replace("maxresdefault.jpg", "hqdefault.jpg"))
    elif url.startswith("http"):
        # For Unsplash, ask for 800px directly to save download time
        if "images.unsplash.com" in url and "w=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}auto=format&fit=crop&w=800&q=80"
        raw = fetch_bytes(url)

    # Fallback: try free LiteAPI static hotel metadata photo if original failed/empty
    if not raw and h.get("nuiteeHotelId") and nuitee_key:
        alt_url = fetch_liteapi_photo(h["nuiteeHotelId"], nuitee_key)
        if alt_url:
            raw = fetch_bytes(alt_url)

    if not raw:
        return (slug, "MISSING", 0, 0)

    try:
        orig_sz, new_sz = save_webp(raw, out_path)
        return (slug, "OK", orig_sz, new_sz)
    except Exception as e:
        return (slug, f"IMG_ERR:{e}", len(raw), 0)


def main() -> None:
    load_env_local()
    nuitee_key = os.environ.get("NUITEE_API_KEY", "")
    optimize_logo()

    dir_path = ROOT / "data" / "stayodds-directory.json"
    hotels = json.loads(dir_path.read_text(encoding="utf-8"))["hotels"]

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        futs = [ex.submit(process_hotel, h, nuitee_key) for h in hotels]
        for fut in concurrent.futures.as_completed(futs):
            results.append(fut.result())

    ok = [r for r in results if r[1] in ("OK", "CACHED")]
    missing = [r for r in results if r[1] not in ("OK", "CACHED")]
    orig_mb = sum(r[2] for r in ok) / (1024 * 1024)
    new_mb = sum(r[3] for r in ok) / (1024 * 1024)
    avg_kb = (sum(r[3] for r in ok) / len(ok) / 1024) if ok else 0

    print(f"Optimized thumbnails: {len(ok)} / {len(hotels)} hotels")
    print(f"Total weight: {orig_mb:.2f} MB raw -> {new_mb:.2f} MB WebP (avg {avg_kb:.1f} KB/hotel)")
    print(f"Missing/unfetched: {len(missing)}")
    for m in missing[:25]:
        print("  MISS:", m[0], m[1])


if __name__ == "__main__":
    main()
