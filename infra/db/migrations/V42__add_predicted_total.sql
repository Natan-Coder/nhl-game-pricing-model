-- infra/db/migrations/V42__add_predicted_total.sql
ALTER TABLE game_pricing ADD COLUMN predicted_total NUMERIC(4,2);