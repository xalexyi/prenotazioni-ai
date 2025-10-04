-- ===========================
--   TABELLE ORARI / REGOLE
-- ===========================

-- Fasce orarie settimanali ricorrenti
CREATE TABLE IF NOT EXISTS opening_hours (
  id SERIAL PRIMARY KEY,
  restaurant_id INTEGER NOT NULL,
  weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6), -- 0=Mon .. 6=Sun
  start_time VARCHAR(5) NOT NULL,       -- "HH:MM"
  end_time   VARCHAR(5) NOT NULL,
  CONSTRAINT fk_opening_rest FOREIGN KEY (restaurant_id)
    REFERENCES restaurants (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_opening_weekday_rest
  ON opening_hours (restaurant_id, weekday);

-- Giorni speciali (chiuso/aperto in deroga al settimanale)
CREATE TABLE IF NOT EXISTS special_days (
  id SERIAL PRIMARY KEY,
  restaurant_id INTEGER NOT NULL,
  date VARCHAR(10) NOT NULL,            -- "YYYY-MM-DD"
  is_closed BOOLEAN NOT NULL DEFAULT FALSE,
  start_time VARCHAR(5),
  end_time   VARCHAR(5),
  CONSTRAINT fk_special_rest FOREIGN KEY (restaurant_id)
    REFERENCES restaurants (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_special_date_rest
  ON special_days (restaurant_id, date);

-- Impostazioni per ristorante
CREATE TABLE IF NOT EXISTS restaurant_settings (
  restaurant_id INTEGER PRIMARY KEY,
  tz VARCHAR(64),
  slot_step_min INTEGER,
  last_order_min INTEGER,
  min_party INTEGER,
  max_party INTEGER,
  capacity_per_slot INTEGER,
  CONSTRAINT fk_settings_rest FOREIGN KEY (restaurant_id)
    REFERENCES restaurants (id) ON DELETE CASCADE
);
