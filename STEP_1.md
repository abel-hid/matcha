# Step 1 — Secure baseline, configuration, and database structure

## F. Concepts

### Environment variables

A tracked `.env.example` documents which values the application needs without containing real secrets.

The real `.env` remains only on the developer’s computer and is ignored by Git.

### Required versus optional configuration

Some configuration is necessary for the application to operate:

* database connection;
* Flask secret;
* JWT secret;
* mail server;
* default sender;
* frontend URL.

OAuth is optional. Google or 42 configuration may be completely absent, but partially configured providers should be rejected because incomplete credentials create confusing runtime failures.

### Fail-fast configuration

A fail-fast application validates configuration during startup and reports exactly which values are missing.

This is better than starting successfully and failing later inside an unrelated registration, database or OAuth request.

### Database constraints

Backend validation improves error messages, but database constraints protect the final stored state.

For example, even if a future route accidentally attempts to insert a self-like, this constraint rejects it:

```sql
CHECK (liker_id <> liked_id)
```

### Indexes

An index helps PostgreSQL find rows without scanning the entire table.

For example, the `user_likes` primary key begins with `liker_id`, but the activity page searches by `liked_id`. A separate index on `liked_id` supports that query direction.

## G. Technical design

### Configuration flow

After the change:

1. `config.py` loads only `backend/.env`.
2. Boolean and integer configuration receives controlled parsing.
3. `Config.validate()` checks required values.
4. Mail credentials must be provided together or both omitted.
5. Each OAuth provider must have all three values or none.
6. `create_app()` validates configuration before initializing PostgreSQL.
7. Database initialization receives the validated database URL.

### OAuth flow

OAuth routes remain registered.

When a provider is absent:

```json
{
  "message": "Google OAuth is not configured"
}
```

The endpoint returns HTTP `503` instead of crashing the entire application.

This step intentionally does **not** change the existing OAuth token redirect flow. Authentication-token transport belongs to the later approved authentication/OAuth security work.

### Database flow

Normal schema application:

```bash
python initdb.py
```

This applies any missing `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` definitions without intentionally deleting data.

Clean reset:

```bash
python initdb.py --reset
```

This executes:

```sql
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
```

It then rebuilds the database entirely from `schema.sql`.

## J. Database changes

### `users`

Added:

* non-empty checks for username, email, first name and last name;
* `fame_rating NOT NULL`;
* `fame_rating >= 0`;
* valid latitude range;
* valid longitude range;
* latitude and longitude must both be null or both be present;
* non-null status and timestamp defaults;
* nonnegative `token_version`;
* OAuth provider and OAuth ID must be set together.

### `tags`

Tag names cannot be blank.

This does not yet enforce the approved list of 20 tags. That belongs to Step 3.

### `photos`

Added:

* non-empty filename;
* nonnegative position;
* partial unique index allowing at most one primary photo per user.

The maximum-five-photo guarantee still belongs to Step 3 because it requires transaction-level behavior beyond a simple row check.

### `user_likes`

Added:

```sql
CHECK (liker_id <> liked_id)
```

Also added an index on `liked_id`.

### `user_blocks`

Added:

```sql
CHECK (blocker_id <> blocked_id)
```

Also added an index on `blocked_id`.

### `user_views`

Added:

```sql
CHECK (viewer_id <> viewed_id)
```

Also added an index on:

```sql
(viewed_id, viewed_at DESC)
```

The current composite primary key remains temporarily. Separate historical visits are a Step 4 change.

### `messages`

Added:

* sender cannot equal receiver;
* message content cannot be blank;
* unread-message and conversation indexes.

These constraints do not implement chat.

### `reports`

Added:

* reporter cannot report themselves;
* reason must remain `fake_account`;
* index on the reported user.

### `notifications`

Allowed types are restricted to the five subject events:

```text
like
view
message
match
unlike
```

Indexes support recent and unread notification retrieval.

### OAuth identity

Added a partial unique index:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_oauth_identity
    ON users(oauth_provider, oauth_id)
    WHERE oauth_provider IS NOT NULL AND oauth_id IS NOT NULL;
```

This prevents two users from sharing the same provider identity.

## K. Tests

The patch creates:

```text
backend/tests/test_config.py
```

It verifies:

1. valid required configuration is accepted;
2. a missing required secret is rejected;
3. OAuth providers may be absent;
4. partial Google configuration is rejected;
5. mail username/password must be configured together.

From `backend/`, after activating the virtual environment:

```bash
python -m unittest discover -s tests -v
```

Expected result:

```text
test_mail_credentials_must_be_set_together ... ok
test_missing_required_configuration_is_rejected ... ok
test_optional_oauth_configuration_may_be_absent ... ok
test_partial_google_oauth_configuration_is_rejected ... ok
test_required_configuration_is_accepted ... ok

Ran 5 tests

OK
```

I verified Python and shell syntax in the inspection environment. I could not run the complete unit suite there because the extracted archive did not have Flask dependencies installed. Docker was also unavailable, so I am not claiming database or application runtime success.

## L. Commands

### 2. Generate new application secrets

Run twice:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use one output for:

```text
SECRET_KEY
```

Use the other for:

```text
JWT_SECRET_KEY
```

Do not reuse the same value.

Because the uploaded archive contained real-looking email and OAuth credentials, those credentials should also be regenerated in their respective provider accounts.

### 3. Validate Compose

From `backend/`:

```bash
docker compose config
```

Expected:

* no missing-variable error;
* PostgreSQL values come from `.env`;
* no password is written literally in `docker-compose.yml`.

### 4. Recreate PostgreSQL

This removes all current database data:

```bash
cd backend
docker compose down -v
docker compose up -d db
```

Check health:

```bash
docker compose ps
```

Expected database status:

```text
healthy
```

### 5. Install backend dependencies

From `backend/`:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

### 6. Run configuration tests

```bash
python -m unittest discover -s tests -v
```

### 7. Reset the database from `schema.sql`

```bash
python initdb.py --reset
```

Expected:

```text
Reset requested: all existing database data will be deleted.
Database reset and schema applied successfully.
```

### 8. Start Flask

```bash
python run.py
```

Expected safe default address:

```text
http://127.0.0.1:5000
```

Debug mode should be disabled when:

```text
FLASK_DEBUG=false
```

### 9. Start Next.js

From a second terminal:

```bash
cd frontend/my-app
./start-dev.sh
```

Expected:

```text
http://localhost:3000
```

## M. Expected results

After successful completion:

* `backend/.env` is ignored;
* `.env.example` is tracked and contains placeholders only;
* Compose reads PostgreSQL configuration from `.env`;
* missing required configuration produces a clear startup error;
* absent OAuth providers do not crash Flask;
* partial OAuth configuration is rejected;
* Flask debug mode is controlled by `FLASK_DEBUG`;
* Flask binds to `127.0.0.1` by default;
* the database can be recreated from one `schema.sql`;
* self-like, self-block and self-report rows are rejected by PostgreSQL;
* duplicate OAuth identities are rejected;
* two primary photos for the same user are rejected;
* existing routes and missing routes are documented;
* the five configuration tests pass.

## N. Manual verification after the fix

### Required-variable negative test

Temporarily remove `SECRET_KEY` from `backend/.env` and run:

```bash
python run.py
```

Expected controlled startup failure:

```text
RuntimeError: Missing required environment variables: SECRET_KEY
```

Restore it before continuing.

### Optional OAuth test

Leave all Google values empty:

```text
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=
```

Start the application.

Expected:

* Flask starts normally;
* opening `/api/auth/oauth/google/login` returns HTTP `503`;
* response:

```json
{
  "message": "Google OAuth is not configured"
}
```

### Partial OAuth negative test

Set only:

```text
GOOGLE_CLIENT_ID=test
```

Leave the other two empty and start Flask.

Expected startup failure mentioning:

```text
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI
```

### Database constraint tests

From `backend/`:

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Create a temporary user:

```sql
INSERT INTO users (
    username,
    email,
    password_hash,
    first_name,
    last_name
)
VALUES (
    'step1_test',
    'step1_test@example.com',
    'temporary',
    'Step',
    'Test'
)
RETURNING id;
```

Use the returned ID in this query:

```sql
INSERT INTO user_likes (liker_id, liked_id)
VALUES (1, 1);
```

Expected PostgreSQL result:

```text
violates check constraint
```

Test coordinate validation:

```sql
UPDATE users
SET latitude = 999,
    longitude = 10
WHERE username = 'step1_test';
```

Expected:

```text
violates check constraint
```

Test one-primary-photo protection:

```sql
INSERT INTO photos (user_id, filename, is_primary)
SELECT id, 'first.jpg', TRUE
FROM users
WHERE username = 'step1_test';

INSERT INTO photos (user_id, filename, is_primary)
SELECT id, 'second.jpg', TRUE
FROM users
WHERE username = 'step1_test';
```

Expected second insert:

```text
duplicate key value violates unique constraint
```

Clean the test account:

```sql
DELETE FROM users
WHERE username = 'step1_test';
```

Exit:

```sql
\q
```

Run the commands above and send the complete outputs for `docker compose ps`, the five tests, `python initdb.py --reset`, and the Flask startup. After those results are confirmed, the next approved work is Step 2 rather than changing any later feature early.
