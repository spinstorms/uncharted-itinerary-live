// Supabase Edge Function: live-google-rating
// ToS-Compliant Live Google Places API (New) proxy for Hotel Detail & Compare views ONLY.
// - Never stores or caches Google rating / reviewCount in Postgres.
// - Uses strict field mask (rating,userRatingCount) -> Place Details Enterprise SKU only (1,000 free/mo).
// - Returns required "Powered by Google" attribution.

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }

  try {
    const url = new URL(req.url);
    const placeId = (url.searchParams.get("place_id") || "").trim();

    if (!placeId || !/^[A-Za-z0-9_-]{10,120}$/.test(placeId)) {
      return new Response(
        JSON.stringify({ error: "Valid google place_id query parameter is required." }),
        { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }
      );
    }

    const apiKey = Deno.env.get("GOOGLE_PLACES_API_KEY");
    if (!apiKey) {
      return new Response(
        JSON.stringify({ error: "GOOGLE_PLACES_API_KEY secret is not configured yet." }),
        { status: 503, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }
      );
    }

    // Strict minimal field mask -> Enterprise SKU (NOT Enterprise + Atmosphere)
    const placesRes = await fetch(
      `https://places.googleapis.com/v1/places/${encodeURIComponent(placeId)}`,
      {
        method: "GET",
        headers: {
          "X-Goog-Api-Key": apiKey,
          "X-Goog-FieldMask": "rating,userRatingCount,googleMapsUri",
          Accept: "application/json",
        },
      }
    );

    if (!placesRes.ok) {
      const errText = await placesRes.text();
      return new Response(
        JSON.stringify({
          error: "Google Places upstream error",
          status: placesRes.status,
          detail: errText.slice(0, 300),
        }),
        { status: 502, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }
      );
    }

    const data = await placesRes.json();
    const rating = typeof data.rating === "number" ? data.rating : null;
    const reviewCount = typeof data.userRatingCount === "number" ? data.userRatingCount : null;

    return new Response(
      JSON.stringify({
        placeId,
        rating,
        scale: 5,
        normalized100: rating != null ? Math.round(rating * 20) : null,
        reviewCount,
        googleMapsUri: data.googleMapsUri || null,
        attribution: "Powered by Google",
        fetchedAt: new Date().toISOString(),
      }),
      {
        status: 200,
        headers: {
          ...CORS_HEADERS,
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
        },
      }
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : "Unexpected error" }),
      { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }
    );
  }
});
