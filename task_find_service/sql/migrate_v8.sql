BEGIN;

-- Accounts without a MAX identity cannot sign in after this migration.
-- Their sessions and solved-task records are removed by foreign-key cascades.
DELETE FROM users WHERE max_id IS NULL;

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_identity_check;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_password_check;
DROP INDEX IF EXISTS users_email_lower_idx;
ALTER TABLE users DROP COLUMN IF EXISTS email;
ALTER TABLE users DROP COLUMN IF EXISTS password_hash;
ALTER TABLE users ALTER COLUMN max_id SET NOT NULL;

COMMIT;
