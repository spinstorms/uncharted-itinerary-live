-- StayOdds Cost Protection: Atomic Daily Quota Counter for Google Places API (New)
-- Prevents ever exceeding the 1,000 free monthly Enterprise Place Details calls
-- even while on Google Cloud Free Trial (where Console quota edits are disabled).

CREATE TABLE IF NOT EXISTS public.api_daily_usage (
  service TEXT NOT NULL,
  usage_date DATE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')::DATE,
  request_count INTEGER NOT NULL DEFAULT 0 CHECK (request_count >= 0),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (service, usage_date)
);

-- Strict RLS: lock down table so anon/public users cannot read or tamper with counters
ALTER TABLE public.api_daily_usage ENABLE ROW LEVEL SECURITY;

-- Atomic check-and-increment RPC (race-safe under concurrent detail page opens)
CREATE OR REPLACE FUNCTION public.try_consume_api_quota(
  p_service TEXT,
  p_daily_cap INTEGER DEFAULT 30
)
RETURNS TABLE (
  allowed BOOLEAN,
  current_count INTEGER,
  daily_cap INTEGER,
  usage_date DATE
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
#variable_conflict use_column
DECLARE
  v_today DATE := (NOW() AT TIME ZONE 'UTC')::DATE;
  v_count INTEGER;
BEGIN
  IF p_daily_cap <= 0 THEN
    RETURN QUERY SELECT FALSE, 0, p_daily_cap, v_today;
    RETURN;
  END IF;

  -- Ensure today's row exists without incrementing yet
  INSERT INTO public.api_daily_usage (service, usage_date, request_count, updated_at)
  VALUES (p_service, v_today, 0, NOW())
  ON CONFLICT (service, usage_date) DO NOTHING;

  -- Atomically increment ONLY if strictly below daily cap (row-level lock prevents races)
  UPDATE public.api_daily_usage
  SET request_count = request_count + 1,
      updated_at = NOW()
  WHERE service = p_service
    AND api_daily_usage.usage_date = v_today
    AND request_count < p_daily_cap
  RETURNING request_count INTO v_count;

  IF FOUND THEN
    RETURN QUERY SELECT TRUE, v_count, p_daily_cap, v_today;
  ELSE
    SELECT u.request_count INTO v_count
    FROM public.api_daily_usage u
    WHERE u.service = p_service
      AND u.usage_date = v_today;
    RETURN QUERY SELECT FALSE, COALESCE(v_count, p_daily_cap), p_daily_cap, v_today;
  END IF;
END;
$$;

-- Restrict RPC execution strictly to service_role (Edge Function server-side only)
REVOKE ALL ON FUNCTION public.try_consume_api_quota(TEXT, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.try_consume_api_quota(TEXT, INTEGER) FROM anon;
REVOKE ALL ON FUNCTION public.try_consume_api_quota(TEXT, INTEGER) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.try_consume_api_quota(TEXT, INTEGER) TO service_role;
