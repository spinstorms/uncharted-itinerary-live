/* "Generate insights" for the 2-3 hotels on the compare page.
   Every line is worked out from data already on StayOdds (guest reviews, critics, our stays,
   awards, prices, seasons, dining, water). Nothing is estimated. Same rules as the StayOdds app
   (stayscore-app lib/compareInsights.ts). */
import { computeStayOdds } from "./stayodds-engine.js?v=14";
import { getBestMonthsMeta, getGuestProfile } from "./stayodds-insights.js?v=9";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const short = (h) => String(h.name || "").replace(/,.*$/, "").replace(/^The /, "");
const n = (x) => Number(x).toLocaleString("en-GB");
const list = (xs) => (xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);
const guestOf = (h) => h?.verifiedGuest?.licensed?.normalized100 ?? null;
const reviewsOf = (h) => Number(h?.verifiedGuest?.licensed?.reviewCount || 0);

function michelinKeys(h) {
  let best = null;
  for (const a of h.officialAwards || []) {
    const t = `${a.awardBody || ""} ${a.label || ""}`;
    if (/michelin/i.test(t)) {
      const m = String(a.label || "").match(/([123])\s*michelin\s*key/i);
      const v = m ? Number(m[1]) : 1;
      if (best == null || v > best) best = v;
    }
  }
  return best;
}
function w50(h) {
  let best = null;
  for (const a of h.officialAwards || []) {
    const t = `${a.awardBody || ""} ${a.label || ""}`;
    if (/50\s*best/i.test(t)) {
      const m = String(a.label || "").match(/(?:No\.?|#)\s*(\d{1,3})/i);
      const v = m ? Number(m[1]) : 999;
      if (best == null || v < best) best = v;
    }
  }
  return best;
}
function forbes(h) {
  let best = null;
  for (const a of h.officialAwards || []) {
    const t = `${a.awardBody || ""} ${a.label || ""}`;
    if (/forbes/i.test(t)) {
      const v = /five[- ]star/i.test(t) ? 5 : /four[- ]star/i.test(t) ? 4 : 3;
      if (best == null || v > best) best = v;
    }
  }
  return best;
}
function priceGbp(h) {
  if (h.priceSnapshot && h.priceSnapshot.nightlyGbp) return Number(h.priceSnapshot.nightlyGbp);
  const m = String(h.priceRange || "").match(/£\s*([\d,]+)/);
  return m ? Number(m[1].replace(/,/g, "")) : null;
}
function km(a, b) {
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const x = Math.sin(dLat / 2) ** 2 + Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}

export function buildCompareInsights(hotels) {
  const hs = (hotels || []).filter(Boolean);
  if (hs.length < 2) return [];
  const out = [];
  const odds = hs.map((h) => computeStayOdds(h));

  const rated = hs.filter((h) => guestOf(h) != null);
  if (rated.length >= 2) {
    const sorted = [...rated].sort((a, b) => guestOf(b) - guestOf(a) || reviewsOf(b) - reviewsOf(a));
    const gap = guestOf(sorted[0]) - guestOf(sorted[sorted.length - 1]);
    out.push({
      icon: "👥",
      title:
        gap <= 1
          ? "Guests rate them almost the same"
          : guestOf(sorted[1]) === guestOf(sorted[0])
            ? `Guests rate ${list(sorted.filter((h) => guestOf(h) === guestOf(sorted[0])).map(short))} highest`
            : `Guests prefer ${short(sorted[0])}`,
      text:
        sorted.map((h) => `${short(h)} ${guestOf(h)}/100 from ${n(reviewsOf(h))} reviews`).join(" · ") +
        (gap <= 1 ? ". A gap this small is within normal variation, so decide on location, rooms or price." : `. That's ${gap} points clear.`),
    });
    const thin = rated.filter((h) => reviewsOf(h) > 0 && reviewsOf(h) < 150);
    if (thin.length)
      out.push({
        icon: "🔍",
        title: "Fewer reviews to go on",
        text: `${list(thin.map(short))} ${thin.length > 1 ? "have" : "has"} under 150 guest reviews, so ${thin.length > 1 ? "their scores" : "its score"} can move more than the others.`,
      });
  }

  const gaps = hs.map((h, i) => ({ h, c: odds[i].critic100, g: odds[i].guest100 })).filter((x) => x.c != null && x.g != null && Math.abs(x.c - x.g) >= 6);
  if (gaps.length)
    out.push({
      icon: "📰",
      title: "Where critics and guests disagree",
      text: gaps.map((x) => `${short(x.h)}: critics ${x.c}, guests ${x.g} (${x.c > x.g ? "critics are keener" : "guests are keener"})`).join(" · "),
    });

  const ours = hs.map((h, i) => ({ h, o: odds[i] })).filter((x) => x.o.personalScore25 != null);
  if (ours.length)
    out.push({
      icon: "🎥",
      title: ours.length === hs.length ? "We stayed at all of them" : `We stayed at ${list(ours.map((x) => short(x.h)))}`,
      text: ours.map((x) => `${short(x.h)} ${x.o.personalScore25}/25 from our filmed stay`).join(" · ") + ".",
    });

  const awards = hs
    .map((h) => {
      const bits = [];
      const k = michelinKeys(h);
      const w = w50(h);
      const f = forbes(h);
      if (k) bits.push(`${k} MICHELIN Key${k > 1 ? "s" : ""}`);
      if (w && w < 999) bits.push(`No. ${w} World's 50 Best`);
      if (f === 5) bits.push("Forbes Five-Star");
      else if (f === 4) bits.push("Forbes Four-Star");
      return { h, bits };
    })
    .filter((x) => x.bits.length);
  if (awards.length) {
    const none = hs.filter((h) => !awards.some((a) => a.h.id === h.id));
    out.push({
      icon: "🏆",
      title: "Awards",
      text:
        awards.map((a) => `${short(a.h)}: ${a.bits.join(", ")}`).join(" · ") +
        (none.length ? ` · ${list(none.map(short))}: no major award (guest scores often match award winners anyway)` : ""),
    });
  }

  const priced = hs.map((h) => ({ h, p: priceGbp(h), g: guestOf(h) })).filter((x) => x.p != null).sort((a, b) => a.p - b.p);
  if (priced.length >= 2 && priced[priced.length - 1].p - priced[0].p >= 50) {
    const lo = priced[0];
    const hi = priced[priced.length - 1];
    const better = lo.g != null && hi.g != null ? (lo.g >= hi.g ? " with an equal or better guest score" : ` for ${hi.g - lo.g} fewer guest points`) : "";
    out.push({
      icon: "💷",
      title: `${short(lo.h)} is the better-value pick`,
      text: `Prices start around £${n(lo.p)} a night against £${n(hi.p)} at ${short(hi.h)}, roughly £${n(hi.p - lo.p)} less per night${better}. Prices are from our latest check, so look at your own dates.`,
    });
  }

  const seasons = hs.map((h) => ({ h, b: getBestMonthsMeta(h) })).filter((s) => s.b && Array.isArray(s.b.months));
  if (seasons.length === hs.length) {
    const shared = seasons[0].b.months.filter((m) => seasons.every((s) => s.b.months.includes(m)));
    out.push({
      icon: "☀️",
      title: shared.length ? "Best months overlap" : "Different best seasons",
      text: shared.length
        ? `All are at their best in ${shared.map((m) => MONTHS[m - 1]).join(", ")}. ` + seasons.map((s) => `${short(s.h)}: ${s.b.label}`).join(" · ")
        : seasons.map((s) => `${short(s.h)}: ${s.b.label}`).join(" · ") + ". Pick by when you can travel.",
    });
  }

  const starred = hs.map((h) => ({ h, d: (h.dining || []).filter((d) => /MICHELIN Star/.test(d.distinction || "")) })).filter((x) => x.d.length);
  if (starred.length)
    out.push({
      icon: "🍽️",
      title: "MICHELIN-starred dining on site",
      text: starred.map((x) => `${short(x.h)}: ${x.d.map((d) => `${d.name} (${String(d.distinction).replace(/MICHELIN /, "")})`).join(", ")}`).join(" · "),
    });

  const paidWater = hs.filter((h) => h.water && h.water.paid > h.water.free);
  if (paidWater.length)
    out.push({ icon: "💧", title: "Bottled water", text: `Guests report paying for bottled water at ${list(paidWater.map(short))}.` });

  const profiles = hs.map((h) => ({ h, p: getGuestProfile(h) || {} }));
  const adults = profiles.filter((x) => x.p.adultsOnly);
  const family = profiles.filter((x) => x.p.familyFriendly);
  if (adults.length || family.length)
    out.push({
      icon: "🧳",
      title: "Who each one suits",
      text: [adults.length ? `Adults-only: ${list(adults.map((x) => short(x.h)))}` : "", family.length ? `Good for families: ${list(family.map((x) => short(x.h)))}` : ""]
        .filter(Boolean)
        .join(" · "),
    });

  if (hs.length === 2 && [hs[0].lat, hs[0].lng, hs[1].lat, hs[1].lng].every((v) => typeof v === "number")) {
    const d = km(hs[0], hs[1]);
    if (d < 60) out.push({ icon: "🗺️", title: "Close neighbours", text: `They're about ${d < 2 ? d.toFixed(1) : Math.round(d)} km apart, so it comes down to the hotel itself rather than the destination.` });
  }

  const watch = hs.filter((h) => h.watchOut && String(h.watchOut).length > 8);
  if (watch.length) out.push({ icon: "⚠️", title: "Watch-outs", text: watch.map((h) => `${short(h)}: ${String(h.watchOut).replace(/\.$/, "")}`).join(" · ") + "." });
  return out;
}

export function renderCompareInsights(hotels) {
  const items = buildCompareInsights(hotels);
  if (!items.length) return "";
  return `
    <div class="h2h-insights" style="margin:0 0 18px;padding:18px 20px;border-radius:16px;border:1px solid var(--line, #e2e8f0);background:var(--card, #fff);">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <div style="font-size:12px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:#ff5d22;">Insights for these ${hotels.length} hotels</div>
        <button type="button" data-h2h-insights-close style="background:none;border:0;font-size:18px;cursor:pointer;opacity:.6;" aria-label="Close insights">×</button>
      </div>
      ${items
        .map(
          (g) => `<div style="display:flex;gap:10px;margin:0 0 10px;">
            <div style="font-size:18px;width:24px;text-align:center;flex:none;">${g.icon}</div>
            <div><div style="font-weight:800;font-size:14.5px;">${esc(g.title)}</div><div style="font-size:14px;line-height:1.5;opacity:.85;">${esc(g.text)}</div></div>
          </div>`,
        )
        .join("")}
      <div style="font-size:12px;opacity:.65;">Worked out from the guest reviews, critics, our stays, awards, prices and seasons on StayOdds. Nothing is estimated.</div>
    </div>`;
}
