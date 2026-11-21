# The Uncharted Itinerary — Live Video Hub, AI Summaries & Affiliate Page

A **\$0/month**, auto-updating companion site built to match [uncharteditinerary.com](https://www.uncharteditinerary.com/) and link seamlessly from **any Squarespace plan** (no Business/Core upgrade required).

## What It Includes

- **Live Video Hub (`/`)**: Automatically syncs new long-form episodes (`UULFtSEMj7vSYDUYbDeIumnEOw`) and Shorts (`UUSHtSEMj7vSYDUYbDeIumnEOw`) from `@TheUnchartedItinerary` every 2 hours via GitHub Actions — zero YouTube API key required.
- **AI Travel Summaries**: Generates structured editorial summaries (TL;DR, 3–4 highlights, "Best for" verdict, clickable chapter timestamps, and per-video affiliate links) for every new upload using the free Gemini API tier (or OpenAI), with an automatic description-parser fallback.
- **Live Affiliate & Deals Page (`/links/`)**: Merges your curated **Google Sheet** (`The Uncharted Itinerary — Live Affiliate Links`) with affiliate links automatically extracted from your YouTube video descriptions. Includes one-click promo code copying (`OKM2ZH`) and mobile-friendly Link-in-Bio layout.
- **Embed-Ready Mode (`?embed=1`)**: Append `?embed=1` to either URL if you ever upgrade to Squarespace Core+ and want to iframe it directly inside a Squarespace page.

---

## Quick 5-Minute Setup Checklist

### 1. Connect Your Free Custom Subdomain (e.g., `videos.uncharteditinerary.com`)
1. In your domain DNS settings (Squarespace Domains → **Domains** → `uncharteditinerary.com` → **DNS** → **Custom Records**), add a **CNAME** record:
   - **Host:** `videos` (or `live` / `explore`)
   - **Type:** `CNAME`
   - **Data:** `spinstorms.github.io`
2. In this GitHub repository, go to **Settings → Pages → Custom domain**, enter `videos.uncharteditinerary.com`, click **Save**, and enable **Enforce HTTPS**.
3. *(Optional second subdomain `links.uncharteditinerary.com`)*: If you want a separate `links.uncharteditinerary.com` URL for your bio, either use `videos.uncharteditinerary.com/links/` directly, or add a URL forward in Squarespace Domains from `links.uncharteditinerary.com` → `https://videos.uncharteditinerary.com/links/`.

### 2. Link It Inside Your Squarespace Navigation Bar (Works on All Plans!)
1. Open your Squarespace dashboard → **Website → Pages → Main Navigation**.
2. Click **`+` → Link**:
   - **Link Title:** `Live Videos` → **URL:** `https://videos.uncharteditinerary.com/`
   - **Link Title:** `Deals & Links` → **URL:** `https://videos.uncharteditinerary.com/links/`
3. Click **Save** — visitors now move seamlessly between `uncharteditinerary.com` and your auto-updating pages with matching branding and navigation.

### 3. Connect Your Live Affiliate Google Sheet (1 Minute)
1. Open your Google Sheet: **The Uncharted Itinerary — Live Affiliate Links** (saved in your `Antigravity` Google Drive folder).
2. Click **File → Share → Publish to web**.
3. Choose **`Curated Links`** and **`Comma-separated values (.csv)`**, click **Publish**, and copy the generated `.csv` URL.
4. Paste that URL into **either**:
   - `config.json` → `"googleSheetCsvUrl"` (enables instant browser-level live updates + 2-hour snapshots), **and/or**
   - GitHub repo **Settings → Secrets and variables → Actions → Variables** → New variable `AFFILIATE_SHEET_CSV_URL`.

### 4. Turn On Automatic AI Summaries for Every Future Upload (Free!)
1. Get a free API key at [Google AI Studio](https://aistudio.google.com/apikey) (no credit card required for the free tier).
2. In this GitHub repo, go to **Settings → Secrets and variables → Actions → Secrets → New repository secret**:
   - **Name:** `GEMINI_API_KEY`
   - **Value:** *(paste your key)*
3. Every time you publish a new YouTube video, GitHub Actions will automatically pull it within 2 hours, generate a matching editorial AI summary, extract any new affiliate links, and redeploy your site.

---

## Local Testing

```bash
python3 scripts/sync.py
python3 -m http.server 8080
```

Then open `http://localhost:8080/` and `http://localhost:8080/links/`.
