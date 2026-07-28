## What changes

### Registration and validation

The backend now validates independently:

* JSON object type;
* username type, length and allowed characters;
* email type, format and maximum length;
* first and last names;
* password length and complexity;
* bcrypt’s 72-byte password limit;
* common passwords;
* passwords derived from username, email or names.

Frontend signup and reset forms use equivalent visible rules.

A local multilingual password list is added at:

```text
backend/app/common_passwords.txt
```

A finite list cannot literally contain every dictionary word in every language, but this follows the approved local-list design and is substantially stronger than the previous six-password check.

### Email delivery

Registration no longer returns success when the verification email fails.

The flow is now:

1. Create the account.
2. Attempt to send the verification email.
3. If sending succeeds, return `201`.
4. If sending fails, remove the new account and return controlled HTTP `503`.

Forgot-password and resend-verification responses are neutral, preventing account discovery.

Verification and reset tokens now contain a random nonce, expire after one hour and become unusable after successful use.

### Secure authentication sessions

Access and refresh JWTs are no longer returned in JSON or stored in JavaScript-readable cookies.

The backend sets:

```text
access_token_cookie
refresh_token_cookie
```

Both are `HttpOnly`.

Separate CSRF cookies remain readable by JavaScript so protected `POST`, `PUT` and `DELETE` requests can send the required CSRF header.

Each login creates a row in:

```text
auth_sessions
```

Every protected request verifies:

* the JWT signature;
* token expiration;
* user identity;
* session ID;
* session revocation state;
* session expiration;
* the user’s token version.

### Logout

Logout now:

1. Calls the backend.
2. Revokes the current `auth_sessions` row.
3. Disconnects Socket.IO connections belonging to that session.
4. Deletes access, refresh and CSRF cookies.
5. Makes copied old credentials unusable.

### Password reset

A successful password reset now performs one database transaction:

1. Hash the new password.
2. Increment `token_version`.
3. Revoke every session belonging to the account.
4. Disconnect the user’s active Socket.IO connections.
5. Clear authentication cookies.

All previous sessions become invalid immediately.

### OAuth

Google and 42 access/refresh tokens are no longer placed in the redirect URL.

The backend now sets the same secure authentication cookies used by local login and redirects only to:

```text
/oauth-callback
```

### Presence and notifications

Socket.IO no longer receives an access token through JavaScript:

```typescript
auth: { token }
```

The authenticated handshake now uses the `HttpOnly` access cookie and validates the associated server-side session.

Notification API requests also use the shared credentialed Axios client.

## Database change

A new table is added:

```sql
CREATE TABLE IF NOT EXISTS auth_sessions (
    id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    last_used_at TIMESTAMP NOT NULL DEFAULT now(),
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    CHECK (expires_at > created_at),
    CHECK (revoked_at IS NULL OR revoked_at >= created_at)
);
```

Indexes support user-session lookup and active-session validation.

A destructive reset is not required for this addition. Applying `schema.sql` creates the missing table while preserving existing data.

## Apply the patch

From the project root, preserve any local changes first:

```bash
git status --short
git diff > before-step2-local-changes.patch
```

Test the patch:

```bash
patch --dry-run -p1 < /path/to/matcha_step2.patch
```

When every hunk succeeds:

```bash
patch -p1 < /path/to/matcha_step2.patch
```

Inspect the result:

```bash
git diff --stat
git diff
```

Do not force the patch when the dry run reports `Hunk FAILED`. That means one of your local edits overlaps a Step 2 code block.

## Update your local `.env`

Keep all existing values and add:

```env
JWT_ACCESS_TOKEN_MINUTES=15
JWT_REFRESH_TOKEN_DAYS=7
JWT_COOKIE_SECURE=false
```

For the current local HTTP project, `JWT_COOKIE_SECURE` must remain `false`.

Use `true` only with HTTPS.

## Apply the schema

From `backend/`:

```bash
docker compose up -d db
```

Activate Python 3:

```bash
source venv/bin/activate
```

Confirm it:

```bash
python --version
which python
```

Apply the updated schema:

```bash
python initdb.py
```

Expected:

```text
Database schema applied successfully.
```

Confirm the session table:

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\d auth_sessions"'
```

## Backend tests

Run from `backend/` with `(venv)` visible:

```bash
python -m unittest discover -s tests -v
```

Expected total:

```text
Ran 20 tests

OK
```

The tests cover:

* configuration;
* malformed registration values;
* username and email normalization;
* common-password rejection;
* account-derived passwords;
* OAuth-only local login;
* `HttpOnly` login cookies;
* server-side logout revocation;
* neutral password-reset responses;
* registration email failure;
* password-reset session invalidation.

## Frontend verification

From `frontend/my-app/`:

```bash
npm ci
```

Then:

```bash
npm run lint
```

Then:

```bash
npm run build
```

Start it:

```bash
npm run dev
```

Use `localhost` consistently:

```text
Frontend: http://localhost:3000
Backend:  http://localhost:5000
```

Do not mix `localhost` and `127.0.0.1` in frontend/backend URLs because browser cookie rules treat them as different hosts.

## Manual verification

### 1. Registration validation

Try a six-character password.

Expected:

```text
Password must be at least 8 characters long
```

Try:

```text
Password1!
```

Expected:

```text
Password is too common
```

Try a password based on the username, such as:

```text
user42Matcha1!
```

Expected:

```text
Password must not be based on your account details
```

### 2. Verification email

Register with a valid account.

Expected:

* HTTP `201`;
* verification email received;
* first use of the link succeeds;
* second use reports that the link was already used.

### 3. Secure login cookies

Log in and open browser developer tools:

```text
Application → Cookies → http://localhost:5000
```

Expected authentication cookies:

```text
access_token_cookie
refresh_token_cookie
```

Both must show `HttpOnly`.

You should also see:

```text
csrf_access_token
csrf_refresh_token
```

These are intentionally not `HttpOnly`, because the frontend must copy their values into CSRF headers. They are not authentication credentials.

The login JSON response must not contain:

```text
token
refreshToken
```

### 4. Logout invalidation

Log in, then click **Log out**.

Expected:

* browser redirects to `/login`;
* authentication cookies are removed;
* the corresponding `auth_sessions.revoked_at` value is populated;
* requesting `/api/auth/me` returns `401`;
* the Socket.IO connection closes.

### 5. Password reset

1. Log in on two browser sessions.
2. Request a password-reset email.
3. Set a new password.
4. Return to both old sessions.

Expected:

* the reset link cannot be reused;
* both old sessions become unauthorized;
* all session rows for the user are revoked;
* the new password works;
* the old password fails.

### 6. Neutral forgot-password response

Submit one registered email and one unknown email.

Both responses must be:

```json
{
  "message": "Password reset email sent if account exists"
}
```

## Verification completed here

I verified:

* all backend Python files compile successfully;
* the patch applies cleanly to the Step 1 project;
* applying the patch reproduces the prepared Step 2 project exactly;
* `.env` is absent from the patch and archive;
* no legacy access or refresh token storage remains in frontend code.

I could not execute the complete Flask tests or Next.js build in this environment because the Python and Node project dependencies were not installed; therefore, I am not claiming that those runtime checks pass until you provide their output.
