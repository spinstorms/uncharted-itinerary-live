/**
 * StayOdds — Crisp Uniform Monochrome SVG Icon Library (1.75px stroke, Lucide-style).
 * Replaces garish browser-rendered Unicode emojis with clean, luxury-editorial icons.
 */

const PATHS = {
  search:
    '<circle cx="11" cy="11" r="7.5"/><line x1="20.5" y1="20.5" x2="16.35" y2="16.35"/>',
  sparkles:
    '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z"/><path d="M19.5 16l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2z"/>',
  compass:
    '<circle cx="12" cy="12" r="9.5"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
  compare:
    '<rect x="3" y="4" width="7.5" height="16" rx="1.8"/><rect x="13.5" y="4" width="7.5" height="16" rx="1.8"/>',
  sliders:
    '<line x1="4" y1="6" x2="20" y2="6"/><circle cx="9" cy="6" r="2" fill="currentColor"/><line x1="4" y1="12" x2="20" y2="12"/><circle cx="15" cy="12" r="2" fill="currentColor"/><line x1="4" y1="18" x2="20" y2="18"/><circle cx="11" cy="18" r="2" fill="currentColor"/>',
  mapPin:
    '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0z"/><circle cx="12" cy="10" r="2.75"/>',
  globe:
    '<circle cx="12" cy="12" r="9.5"/><line x1="2.5" y1="12" x2="21.5" y2="12"/><path d="M12 2.5a14.5 14.5 0 0 1 0 19 14.5 14.5 0 0 1 0-19z"/>',
  bed:
    '<path d="M3 7v11"/><path d="M3 14h18v4"/><path d="M21 14v-3a3 3 0 0 0-3-3H8a2 2 0 0 0-2 2v4"/><circle cx="7" cy="10" r="1.2"/>',
  sun:
    '<circle cx="12" cy="12" r="4"/><line x1="12" y1="2.5" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="21.5"/><line x1="4.93" y1="4.93" x2="6.7" y2="6.7"/><line x1="17.3" y1="17.3" x2="19.07" y2="19.07"/><line x1="2.5" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="21.5" y2="12"/><line x1="4.93" y1="19.07" x2="6.7" y2="17.3"/><line x1="17.3" y1="6.7" x2="19.07" y2="4.93"/>',
  award:
    '<circle cx="12" cy="8.5" r="5.5"/><path d="M8.5 13.5L7 21l5-2.5L17 21l-1.5-7.5"/>',
  trophy:
    '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 21h16"/><path d="M10 14.7V17c0 .6-.5 1-1 1.2C7.8 18.7 7 20 7 21"/><path d="M14 14.7V17c0 .6.5 1 1 1.2 1.2.5 2 1.8 2 2.8"/><path d="M18 3H6v6.5a6 6 0 0 0 12 0V3z"/>',
  key:
    '<circle cx="7.5" cy="15.5" r="4.2"/><path d="M10.8 12.2L20 3"/><path d="M16.5 6.5l2.5 2.5"/><path d="M14 9l2 2"/>',
  star:
    '<polygon points="12 2.5 14.9 8.4 21.4 9.3 16.7 13.9 17.8 20.4 12 17.3 6.2 20.4 7.3 13.9 2.6 9.3 9.1 8.4 12 2.5"/>',
  starFilled:
    '<polygon fill="currentColor" points="12 2.5 14.9 8.4 21.4 9.3 16.7 13.9 17.8 20.4 12 17.3 6.2 20.4 7.3 13.9 2.6 9.3 9.1 8.4 12 2.5"/>',
  heart:
    '<path d="M20.4 5.6a5.2 5.2 0 0 0-7.4 0L12 6.6l-1-1a5.2 5.2 0 0 0-7.4 7.4l1 1L12 21l7.4-7 1-1a5.2 5.2 0 0 0 0-7.4z"/>',
  heartFilled:
    '<path fill="currentColor" d="M20.4 5.6a5.2 5.2 0 0 0-7.4 0L12 6.6l-1-1a5.2 5.2 0 0 0-7.4 7.4l1 1L12 21l7.4-7 1-1a5.2 5.2 0 0 0 0-7.4z"/>',
  check:
    '<polyline points="20 6 9 17 4 12"/>',
  alert:
    '<path d="M10.3 3.9L1.8 18.5a1.8 1.8 0 0 0 1.6 2.7h17.2a1.8 1.8 0 0 0 1.6-2.7L13.7 3.9a1.8 1.8 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13.5"/><circle cx="12" cy="17" r="0.8" fill="currentColor"/>',
  waves:
    '<path d="M2 10c2 0 2.5-1.5 4.5-1.5S9 10 11 10s2.5-1.5 4.5-1.5S18 10 20 10h2"/><path d="M2 15.5c2 0 2.5-1.5 4.5-1.5S9 15.5 11 15.5s2.5-1.5 4.5-1.5S18 15.5 20 15.5h2"/>',
  mountain:
    '<path d="M3 19l6.5-11 4.2 6.8L16.5 11 21 19H3z"/>',
  building:
    '<rect x="4" y="3" width="16" height="18" rx="1.5"/><line x1="9" y1="8" x2="9.01" y2="8"/><line x1="15" y1="8" x2="15.01" y2="8"/><line x1="9" y1="12" x2="9.01" y2="12"/><line x1="15" y1="12" x2="15.01" y2="12"/><path d="M9.5 21v-4h5v4"/>',
  landmark:
    '<line x1="3" y1="21" x2="21" y2="21"/><line x1="4" y1="10" x2="20" y2="10"/><polygon points="12 3 3 8 21 8 12 3"/><line x1="7" y1="10" x2="7" y2="18"/><line x1="12" y1="10" x2="12" y2="18"/><line x1="17" y1="10" x2="17" y2="18"/>',
  trees:
    '<path d="M12 3l-5 8h3l-3.5 6h11L14 11h3L12 3z"/><line x1="12" y1="17" x2="12" y2="21"/>',
  droplets:
    '<path d="M12 3.5C12 3.5 6 10.2 6 14.5a6 6 0 0 0 12 0C18 10.2 12 3.5 12 3.5z"/>',
  utensils:
    '<path d="M4 3v7a3 3 0 0 0 6 0V3"/><line x1="7" y1="3" x2="7" y2="21"/><path d="M17 3v18"/><path d="M17 3a4 4 0 0 1 3 4v4h-3"/>',
  camera:
    '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h3.5l2-3h5l2 3H20a2 2 0 0 1 2 2z"/><circle cx="12" cy="13.5" r="3.5"/>',
  link:
    '<path d="M10 13a5 5 0 0 0 7.1 0l2.8-2.8a5 5 0 0 0-7.1-7.1L11.2 4.7"/><path d="M14 11a5 5 0 0 0-7.1 0L4.1 13.8a5 5 0 0 0 7.1 7.1l1.6-1.6"/>',
  download:
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
  play:
    '<polygon points="6 4 20 12 6 20 6 4"/>',
  tag:
    '<path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.2" fill="currentColor"/>',
  users:
    '<path d="M17 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9.5" cy="7" r="3.5"/><path d="M22 21v-2a3.5 3.5 0 0 0-2.6-3.4"/><path d="M16 3.6a3.5 3.5 0 0 1 0 6.8"/>',
  calendar:
    '<rect x="3" y="4" width="18" height="17" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
  wifi:
    '<path d="M5 12.6a11 11 0 0 1 14 0"/><path d="M8.5 16.1a6 6 0 0 1 7 0"/><circle cx="12" cy="19.5" r="1" fill="currentColor"/>',
  creditCard:
    '<rect x="2" y="5" width="20" height="14" rx="2.5"/><line x1="2" y1="10" x2="22" y2="10"/>',
  home:
    '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>',
};

export function svgIcon(name, size = 15, extraClass = "") {
  const path = PATHS[name] || PATHS.compass;
  const cls = extraClass ? `so-ico ${extraClass}` : "so-ico";
  return `<svg class="${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
}
