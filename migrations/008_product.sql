-- Add a product dimension so non-USD/IQD quotes (silver per kg, Dubai gold lira)
-- are captured separately and never mix with the USD/IQD consensus.
ALTER TABLE observations ADD COLUMN IF NOT EXISTS product TEXT;
