// Supabase Edge Function: live-google-rating
// ToS-Compliant & Cost-Capped Live Google Places API (New) proxy for Detail & Compare views ONLY.
// Guardrails:
//   1. Atomic daily kill-switch via Supabase Postgres `try_consume_api_quota` RPC.
//      Default GOOGLE_PLACES_DAILY_CAP = 30 (stays safely inside 1,000 free monthly Enterprise calls).
//   2. Strict minimal X-Goog-FieldMask: `rating,userRatingCount` ONLY
//      (Enterprise SKU only — NEVER requests `reviews`, photos, or contact fields).
//   3. Never stores or caches Google rating / userRatingCount in Postgres (per Google Maps ToS).
//   4. Returns required Google Maps attribution + review-policy notice, and clean `cap_reached` fallback.

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
};

const SERVICE_KEY = "google_places_details";

function jsonResponse(payload: Record<string, unknown>, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      ...CORS_HEADERS,
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
  });
}

function buildGoogleMapsPlaceUrl(placeId: string): string {
  return `https://www.google.com/maps/place/?q=place_id:${encodeURIComponent(placeId)}`;
}

async function tryConsumeDailyQuota(
  supabaseUrl: string,
  serviceRoleKey: string,
  dailyCap: number
): Promise<{ allowed: boolean; currentCount: number; dailyCap: number; usageDate: string | null }> {
  const res = await fetch(`${supabaseUrl.replace(/\/$/, "")}/rest/v1/rpc/try_consume_api_quota`, {
    method: "POST",
    headers: {
      apikey: serviceRoleKey,
      Authorization: `Bearer ${serviceRoleKey}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      p_service: SERVICE_KEY,
      p_daily_cap: dailyCap,
    }),
  });

  if (!res.ok) {
    // Fail closed for cost safety: if quota counter cannot be verified, do NOT call paid Google API.
    return { allowed: false, currentCount: dailyCap, dailyCap, usageDate: null };
  }

  const rows = await res.json();
  const row = Array.isArray(rows) ? rows[0] : rows;
  return {
    allowed: Boolean(row?.allowed),
    currentCount: Number(row?.current_count ?? dailyCap),
    dailyCap: Number(row?.daily_cap ?? dailyCap),
    usageDate: row?.usage_date ?? null,
  };
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }

  try {
    const url = new URL(req.url);
    const placeId = (url.searchParams.get("place_id") || "").trim();

    if (!placeId || !/^[A-Za-z0-9_-]{10,120}$/.test(placeId)) {
      return jsonResponse({ status: "invalid_place_id", google_rating: null, google_review_count: null }, 400);
    }

    const googleMapsUri = buildGoogleMapsPlaceUrl(placeId);
    const apiKey = Deno.env.get("GOOGLE_PLACES_API_KEY");
    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

    const rawCap = Number(Deno.env.get("GOOGLE_PLACES_DAILY_CAP") ?? "30");
    const dailyCap = Number.isFinite(rawCap) && rawCap >= 0 ? Math.floor(rawCap) : 30;

    if (!apiKey || !supabaseUrl || !serviceRoleKey) {
      return jsonResponse({
        status: "unavailable",
        placeId,
        google_rating: null,
        google_review_count: null,
        rating: null,
        reviewCount: null,
        googleMapsUri,
      });
    }

    // 1. Atomic daily kill-switch BEFORE making any Google Places API call
    const quota = await tryConsumeDailyQuota(supabaseUrl, serviceRoleKey, dailyCap);
    if (!quota.allowed) {
      return jsonResponse({
        status: "cap_reached",
        placeId,
        google_rating: null,
        google_review_count: null,
        rating: null,
        reviewCount: null,
        googleMapsUri,
        dailyCap: quota.dailyCap,
      });
    }

    // 2. Strict minimal FieldMask -> `rating,userRatingCount` ONLY (Place Details Enterprise SKU)
    const placesRes = await fetch(
      `https://places.googleapis.com/v1/places/${encodeURIComponent(placeId)}`,
      {
        method: "GET",
        headers: {
          "X-Goog-Api-Key": apiKey,
          "X-Goog-FieldMask": "rating,userRatingCount",
          Accept: "application/json",
        },
      }
    );

    if (!placesRes.ok) {
      return jsonResponse({
        status: "upstream_unavailable",
        placeId,
        google_rating: null,
        google_review_count: null,
        rating: null,
        reviewCount: null,
        googleMapsUri,
      });
    }

    const data = await placesRes.json();
    const rating = typeof data.rating === "number" ? data.rating : null;
    const reviewCount = typeof data.userRatingCount === "number" ? data.userRatingCount : null;

    return jsonResponse({
      status: "ok",
      placeId,
      rating,
      google_rating: rating,
      scale: 5,
      normalized100: rating != null ? Math.round(rating * 20) : null,
      reviewCount,
      google_review_count: reviewCount,
      googleMapsUri,
      attribution: "Powered by Google",
      policyNotice: "Reviews are not verified by Google.",
      fetchedAt: new Date().toISOString(),
    });
  } catch {
    return jsonResponse({
      status: "unavailable",
      google_rating: null,
      google_review_count: null,
      rating: null,
      reviewCount: null,
    });
  }
});
