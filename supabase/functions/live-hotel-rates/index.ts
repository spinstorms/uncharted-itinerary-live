// Supabase Edge Function: live-hotel-rates
// On-demand, cost-capped LiteAPI live rate lookup triggered ONLY when a user
// explicitly clicks "Check Live Rates" for specific dates in Compare or Detail views.
// Guardrails:
//   1. Short-TTL in-memory cache (20 minutes) keyed by (hotelIds, checkin, checkout, adults, currency).
//   2. Atomic daily quota cap via Supabase Postgres `try_consume_api_quota` RPC
//      (default LITEAPI_RATES_DAILY_CAP = 400 calls/day; 1 call fetches up to 3 compared hotels at once).
//   3. Zero per-pageview auto-fetching — only invoked on explicit user action.

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

const SERVICE_KEY = "liteapi_live_rates";
const CACHE_TTL_MS = 20 * 60 * 1000;
const memoryCache = new Map<string, { ts: number; payload: Record<string, unknown> }>();

function jsonResponse(payload: Record<string, unknown>, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      ...CORS_HEADERS,
      "Content-Type": "application/json",
      "Cache-Control": "public, max-age=300",
    },
  });
}

function isIsoDate(val: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(val);
}

async function tryConsumeDailyQuota(
  supabaseUrl: string,
  serviceRoleKey: string,
  dailyCap: number
): Promise<boolean> {
  try {
    const res = await fetch(`${supabaseUrl.replace(/\/$/, "")}/rest/v1/rpc/try_consume_api_quota`, {
      method: "POST",
      headers: {
        apikey: serviceRoleKey,
        Authorization: `Bearer ${serviceRoleKey}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ p_service: SERVICE_KEY, p_daily_cap: dailyCap }),
    });
    if (!res.ok) return true; // Soft-allow if RPC table doesn't restrict free LiteAPI calls
    const rows = await res.json();
    const row = Array.isArray(rows) ? rows[0] : rows;
    return Boolean(row?.allowed);
  } catch {
    return true;
  }
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }

  try {
    const url = new URL(req.url);
    let hotelIds: string[] = [];
    let checkin = "";
    let checkout = "";
    let adults = 2;
    let currency = "GBP";

    if (req.method === "POST") {
      const body = await req.json().catch(() => ({}));
      hotelIds = Array.isArray(body.hotelIds)
        ? body.hotelIds.map((x: unknown) => String(x || "").trim()).filter(Boolean)
        : [];
      checkin = String(body.checkin || "").trim();
      checkout = String(body.checkout || "").trim();
      adults = Math.max(1, Math.min(6, Number(body.adults) || 2));
      currency = /^[A-Z]{3}$/.test(String(body.currency || "")) ? String(body.currency) : "GBP";
    } else {
      hotelIds = (url.searchParams.get("hotel_ids") || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      checkin = (url.searchParams.get("checkin") || "").trim();
      checkout = (url.searchParams.get("checkout") || "").trim();
      adults = Math.max(1, Math.min(6, Number(url.searchParams.get("adults")) || 2));
      const cur = (url.searchParams.get("currency") || "GBP").toUpperCase();
      currency = /^[A-Z]{3}$/.test(cur) ? cur : "GBP";
    }

    hotelIds = Array.from(new Set(hotelIds)).slice(0, 5);
    if (!hotelIds.length || !isIsoDate(checkin) || !isIsoDate(checkout)) {
      return jsonResponse({ status: "invalid_params", rates: {} }, 400);
    }

    const nights = Math.round(
      (Date.parse(`${checkout}T00:00:00Z`) - Date.parse(`${checkin}T00:00:00Z`)) / 86400000
    );
    if (!Number.isFinite(nights) || nights < 1 || nights > 30) {
      return jsonResponse({ status: "invalid_dates", rates: {} }, 400);
    }

    const cacheKey = `${hotelIds.slice().sort().join(",")}|${checkin}|${checkout}|${adults}|${currency}`;
    const cached = memoryCache.get(cacheKey);
    if (cached && Date.now() - cached.ts < CACHE_TTL_MS) {
      return jsonResponse({ ...cached.payload, cached: true });
    }

    const nuiteeKey = Deno.env.get("NUITEE_API_KEY") || Deno.env.get("LITEAPI_KEY");
    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    const dailyCap = Math.max(50, Number(Deno.env.get("LITEAPI_RATES_DAILY_CAP") ?? "400") || 400);

    if (!nuiteeKey) {
      return jsonResponse({ status: "unavailable", rates: {} });
    }

    if (supabaseUrl && serviceRoleKey) {
      const allowed = await tryConsumeDailyQuota(supabaseUrl, serviceRoleKey, dailyCap);
      if (!allowed) {
        return jsonResponse({ status: "cap_reached", rates: {} });
      }
    }

    const apiRes = await fetch("https://api.liteapi.travel/v3.0/hotels/rates", {
      method: "POST",
      headers: {
        "X-API-Key": nuiteeKey,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        hotelIds,
        checkin,
        checkout,
        currency,
        guestNationality: currency === "USD" ? "US" : currency === "EUR" ? "DE" : "GB",
        occupancies: [{ adults }],
      }),
    });

    if (!apiRes.ok) {
      return jsonResponse({ status: "upstream_unavailable", rates: {} });
    }

    const raw = await apiRes.json();
    const rates: Record<
      string,
      { total: number; perNight: number; currency: string; nights: number; refundable: boolean }
    > = {};

    for (const row of raw?.data || []) {
      const hid = String(row?.hotelId || "");
      if (!hid) continue;
      let bestTotal: number | null = null;
      let refundable = false;
      for (const rt of row?.roomTypes || []) {
        const amt = Number(rt?.offerRetailRate?.amount);
        if (Number.isFinite(amt) && amt > 0) {
          if (bestTotal == null || amt < bestTotal) {
            bestTotal = amt;
            refundable = String(rt?.rates?.[0]?.cancellationPolicies?.refundableTag || "").toUpperCase() === "RFN";
          }
        }
      }
      if (bestTotal != null) {
        rates[hid] = {
          total: Math.round(bestTotal),
          perNight: Math.round(bestTotal / nights),
          currency,
          nights,
          refundable,
        };
      }
    }

    const payload = {
      status: "ok",
      checkin,
      checkout,
      nights,
      adults,
      currency,
      rates,
      fetchedAt: new Date().toISOString(),
    };
    memoryCache.set(cacheKey, { ts: Date.now(), payload });
    return jsonResponse(payload);
  } catch {
    return jsonResponse({ status: "unavailable", rates: {} });
  }
});
