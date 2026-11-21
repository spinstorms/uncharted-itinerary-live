-- StayOdds Phase 1B / Phase 2 — Production PostgreSQL Schema (Supabase)
-- Enforces strict data integrity at the database level:
--   1. Every third-party editorial rating, YouTube review, and official award MUST have a valid http(s) source_url.
--   2. Google Places ratings are NEVER cached permanently in this database (fetched live via Edge Function using google_place_id).
--   3. Public read-only access via Row Level Security (RLS); all writes restricted to service_role.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Core Luxury Properties (250+ target portfolio)
CREATE TABLE IF NOT EXISTS public.properties (
  id TEXT PRIMARY KEY, -- URL-friendly slug e.g. 'soneva-fushi', 'taaktana-labuan-bajo'
  name TEXT NOT NULL,
  brand TEXT DEFAULT '',
  city TEXT NOT NULL,
  country TEXT NOT NULL,
  region TEXT NOT NULL,
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  tier TEXT NOT NULL DEFAULT 'global_directory'
    CHECK (tier IN ('first_hand_verified', 'short_preview', 'global_directory')),
  visited_by_founder BOOLEAN NOT NULL DEFAULT FALSE,
  google_place_id TEXT,        -- Permanently cacheable per Google Maps Platform ToS
  nuitee_hotel_id TEXT,        -- Nuitée Connect (formerly LiteAPI) hotel ID
  price_tier TEXT DEFAULT '',  -- e.g. '££££', 'Ultra-Luxury'
  hero_image_url TEXT DEFAULT '',
  image_license_source TEXT DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_properties_region ON public.properties (region);
CREATE INDEX IF NOT EXISTS idx_properties_tier ON public.properties (tier);
CREATE INDEX IF NOT EXISTS idx_properties_country ON public.properties (country);

-- 2. Middle "Key Facts" Panel (Strictly verifiable hotel specs — omit blank fields in UI)
CREATE TABLE IF NOT EXISTS public.property_facts (
  property_id TEXT PRIMARY KEY REFERENCES public.properties(id) ON DELETE CASCADE,
  standout TEXT DEFAULT '',
  watch_out TEXT DEFAULT '',
  pool_heating TEXT DEFAULT '',        -- e.g. 'Heated main & villa pools' / 'Unheated infinity pool'
  beach_or_reef TEXT DEFAULT '',       -- e.g. 'Direct house reef snorkeling' / 'Clifftop — no swimmable beach'
  renovation_year INTEGER,             -- Verified opening or major renovation year
  transfer_logistics TEXT DEFAULT '',  -- e.g. '35-min seaplane from Malé' / '25-min drive from DPS'
  red_flag_tags TEXT[] NOT NULL DEFAULT '{}',
  source_note TEXT DEFAULT '',
  verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Tier 1 First-Hand Reviews (The Uncharted Itinerary — Founding Contributor)
CREATE TABLE IF NOT EXISTS public.first_hand_reviews (
  property_id TEXT PRIMARY KEY REFERENCES public.properties(id) ON DELETE CASCADE,
  contributor_name TEXT NOT NULL DEFAULT 'The Uncharted Itinerary',
  coverage_type TEXT NOT NULL CHECK (coverage_type IN ('Full Review', 'Short Tour')),
  youtube_video_id TEXT DEFAULT '',
  in_live_feed BOOLEAN NOT NULL DEFAULT FALSE,
  rooms_score SMALLINT CHECK (rooms_score BETWEEN 1 AND 5),
  grounds_score SMALLINT CHECK (grounds_score BETWEEN 1 AND 5),
  food_score SMALLINT CHECK (food_score BETWEEN 1 AND 5),
  service_score SMALLINT CHECK (service_score BETWEEN 1 AND 5),
  value_score SMALLINT CHECK (value_score BETWEEN 1 AND 5),
  overall_score SMALLINT CHECK (overall_score BETWEEN 1 AND 5),
  verdict TEXT DEFAULT '',
  where_we_differ TEXT DEFAULT '',     -- Powers the Opinion Gap editorial explanation
  reviewed_date DATE,
  shorts JSONB NOT NULL DEFAULT '[]'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Licensed Guest Scores (Scheduled backend sync from Nuitée Connect / licensed partners — NEVER Google Places)
CREATE TABLE IF NOT EXISTS public.licensed_guest_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id TEXT NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
  partner_source TEXT NOT NULL CHECK (partner_source <> 'google_places'),
  rating NUMERIC(4,2) NOT NULL,
  scale NUMERIC(4,1) NOT NULL DEFAULT 10.0,
  normalized_100 SMALLINT NOT NULL CHECK (normalized_100 BETWEEN 0 AND 100),
  review_count INTEGER,
  attribution TEXT NOT NULL,
  verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (property_id, partner_source)
);

-- 5. Structured Editorial Ratings (STRICT DB-LEVEL source_url ENFORCEMENT)
CREATE TABLE IF NOT EXISTS public.editorial_ratings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id TEXT NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL CHECK (source_url ~* '^https?://[^\s]+$'),
  raw_score TEXT DEFAULT '',
  normalized_100 SMALLINT NOT NULL CHECK (normalized_100 BETWEEN 0 AND 100),
  takeaway TEXT DEFAULT '',
  published_at DATE,
  verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (property_id, source_name, source_url)
);

-- 6. Linked YouTube Video Reviews (STRICT DB-LEVEL source_url ENFORCEMENT — qualitative sentiment, no fake scores)
CREATE TABLE IF NOT EXISTS public.youtube_reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id TEXT NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
  creator_name TEXT NOT NULL,
  source_url TEXT NOT NULL CHECK (source_url ~* '^https?://[^\s]+$'),
  sentiment TEXT NOT NULL DEFAULT 'Recommended'
    CHECK (sentiment IN ('Recommended', 'Mixed', 'Pass', 'Review')),
  takeaway TEXT DEFAULT '',
  published_at DATE,
  verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (property_id, source_url)
);

-- 7. Official Verifiable Awards (MICHELIN Keys, Forbes Stars, World's 50 Best — STRICT source_url)
CREATE TABLE IF NOT EXISTS public.official_awards (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id TEXT NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
  award_body TEXT NOT NULL,       -- e.g. 'MICHELIN Guide', 'Forbes Travel Guide', 'World''s 50 Best'
  label TEXT NOT NULL,            -- e.g. '3 MICHELIN Keys', 'Forbes Five-Star'
  award_year TEXT DEFAULT '',
  normalized_100 SMALLINT CHECK (normalized_100 BETWEEN 0 AND 100),
  source_url TEXT NOT NULL CHECK (source_url ~* '^https?://[^\s]+$'),
  verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (property_id, award_body, label)
);

-- 8. Commercial Dual-Channel Booking Links (Web OTA Affiliate + Mobile-Compliant + VIP Advisor Perks)
CREATE TABLE IF NOT EXISTS public.booking_links (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id TEXT NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
  channel_type TEXT NOT NULL
    CHECK (channel_type IN ('ota_affiliate', 'direct_brand', 'luxury_advisor_vip')),
  partner_name TEXT NOT NULL,     -- e.g. 'Booking.com', 'Expedia', 'Virtuoso / VIP Advisor'
  url TEXT NOT NULL CHECK (url ~* '^https?://[^\s]+$'),
  mobile_allowed BOOLEAN NOT NULL DEFAULT TRUE, -- FALSE for Booking.com Travelpayouts (Web Content Only)
  perks_summary TEXT DEFAULT '',  -- e.g. 'Free breakfast, $100 credit & upgrade when available'
  priority SMALLINT NOT NULL DEFAULT 1,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (property_id, channel_type, partner_name)
);

-- 9. Future User Accounts: Saved Shortlists & StayOdds Pro Foundations
CREATE TABLE IF NOT EXISTS public.saved_shortlists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  title TEXT NOT NULL DEFAULT 'My Luxury Shortlist',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.shortlist_items (
  shortlist_id UUID NOT NULL REFERENCES public.saved_shortlists(id) ON DELETE CASCADE,
  property_id TEXT NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
  note TEXT DEFAULT '',
  added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (shortlist_id, property_id)
);

-- 10. Enable Row Level Security (RLS)
ALTER TABLE public.properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.property_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.first_hand_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.licensed_guest_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.editorial_ratings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.youtube_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.official_awards ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.booking_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saved_shortlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shortlist_items ENABLE ROW LEVEL SECURITY;

-- Public read-only policies for StayOdds web & mobile app
DROP POLICY IF EXISTS "Public read properties" ON public.properties;
CREATE POLICY "Public read properties" ON public.properties FOR SELECT USING (TRUE);

DROP POLICY IF EXISTS "Public read property_facts" ON public.property_facts;
CREATE POLICY "Public read property_facts" ON public.property_facts FOR SELECT USING (TRUE);

DROP POLICY IF EXISTS "Public read first_hand_reviews" ON public.first_hand_reviews;
CREATE POLICY "Public read first_hand_reviews" ON public.first_hand_reviews FOR SELECT USING (TRUE);

DROP POLICY IF EXISTS "Public read licensed_guest_scores" ON public.licensed_guest_scores;
CREATE POLICY "Public read licensed_guest_scores" ON public.licensed_guest_scores FOR SELECT USING (TRUE);

DROP POLICY IF EXISTS "Public read editorial_ratings" ON public.editorial_ratings;
CREATE POLICY "Public read editorial_ratings" ON public.editorial_ratings FOR SELECT USING (TRUE);

DROP POLICY IF EXISTS "Public read youtube_reviews" ON public.youtube_reviews;
CREATE POLICY "Public read youtube_reviews" ON public.youtube_reviews FOR SELECT USING (TRUE);

DROP POLICY IF EXISTS "Public read official_awards" ON public.official_awards;
CREATE POLICY "Public read official_awards" ON public.official_awards FOR SELECT USING (TRUE);

DROP POLICY IF EXISTS "Public read booking_links" ON public.booking_links;
CREATE POLICY "Public read booking_links" ON public.booking_links FOR SELECT USING (TRUE);

-- Authenticated user policies for Saved Shortlists
DROP POLICY IF EXISTS "Users manage own shortlists" ON public.saved_shortlists;
CREATE POLICY "Users manage own shortlists" ON public.saved_shortlists
  FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users manage own shortlist items" ON public.shortlist_items;
CREATE POLICY "Users manage own shortlist items" ON public.shortlist_items
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.saved_shortlists s
      WHERE s.id = shortlist_id AND s.user_id = auth.uid()
    )
  );
