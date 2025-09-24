-- Opening hours settimanali
CREATE TABLE IF NOT EXISTS opening_hours (
  id SERIAL PRIMARY KEY,
  restaurant_id INTEGER NOT NULL,
  weekday INTEGER NOT NULL,             -- 0=Mon .. 6=Sun
  start_time VARCHAR(5) NOT NULL,       -- 'HH:MM'
  end_time   VARCHAR(5) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_opening_weekday_rest
  ON opening_hours (restaurant_id, weekday);

-- Eccezioni calendario (chiuso/aperto speciale)
CREATE TABLE IF NOT EXISTS special_days (
  id SERIAL PRIMARY KEY,
  restaurant_id INTEGER NOT NULL,
  date VARCHAR(10) NOT NULL,            -- 'YYYY-MM-DD'
  is_closed BOOLEAN NOT NULL DEFAULT FALSE,
  start_time VARCHAR(5),
  end_time   VARCHAR(5)
);
CREATE INDEX IF NOT EXISTS idx_special_date_rest
  ON special_days (restaurant_id, date);

-- Settings per ristorante
CREATE TABLE IF NOT EXISTS restaurant_settings (
  restaurant_id INTEGER PRIMARY KEY,
  tz VARCHAR(64),
  slot_step_min INTEGER,
  last_order_min INTEGER,
  min_party INTEGER,
  max_party INTEGER,
  capacity_per_slot INTEGER
);
