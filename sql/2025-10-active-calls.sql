-- Tabella per tracciare chiamate attive per ristorante
CREATE TABLE IF NOT EXISTS active_calls (
  id SERIAL PRIMARY KEY,
  restaurant_id INTEGER NOT NULL,
  call_sid TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_active_calls_active_rid
  ON active_calls (restaurant_id, active);

-- Funzione: prova ad acquisire uno slot
-- Ritorna TRUE se overload (limite superato), FALSE se acquisito
CREATE OR REPLACE FUNCTION acquire_slot(p_rid INT, p_call_sid TEXT, p_max INT)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
  v_active_count INT;
BEGIN
  SELECT COUNT(*) INTO v_active_count
  FROM active_calls
  WHERE restaurant_id = p_rid AND active = TRUE;

  IF v_active_count >= p_max THEN
    RETURN TRUE; -- overload
  END IF;

  INSERT INTO active_calls (restaurant_id, call_sid, active)
  VALUES (p_rid, p_call_sid, TRUE)
  ON CONFLICT (call_sid) DO UPDATE
    SET active = EXCLUDED.active,
        restaurant_id = EXCLUDED.restaurant_id;

  RETURN FALSE; -- acquisito
END;
$$;

-- Funzione: rilascia lo slot (segna la call come non attiva)
CREATE OR REPLACE FUNCTION release_slot(p_call_sid TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
  v_released BOOLEAN := FALSE;
BEGIN
  UPDATE active_calls
  SET active = FALSE
  WHERE call_sid = p_call_sid AND active = TRUE
  RETURNING TRUE INTO v_released;

  RETURN COALESCE(v_released, FALSE);
END;
$$;
