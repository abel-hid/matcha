# Matcha

This repository contains a Flask/PostgreSQL backend and a Next.js/TypeScript frontend.

`backend/schema.sql` is the complete database definition. This project does not use migrations.

## Current runtime

The current repository uses:

- Docker Compose for PostgreSQL;
- a local Python virtual environment for Flask;
- local Node.js 22 for Next.js.

The backend and frontend are not currently containerized. Changing that architecture requires a separate approved plan change.

## Environment setup

From the repository root:

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env` and replace every placeholder secret. Google and 42 OAuth variables may remain empty. For either provider, set all three variables for that provider or leave all three empty.

Never commit `backend/.env`. Keep `JWT_COOKIE_SECURE=false` for the local HTTP setup. Use `true` only when the backend is served through HTTPS.

## Start PostgreSQL

From `backend/`:

```bash
docker compose up -d db
```

Check the database health:

```bash
docker compose ps
```

## Start the backend

From `backend/`:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python initdb.py
python run.py
```

The backend listens on the configured `BACKEND_HOST` and `BACKEND_PORT`. The safe defaults are `127.0.0.1` and `5000`.

## Start the frontend

In another terminal, from `frontend/my-app/`:

```bash
npm ci
npm run dev
```

The frontend is available at `http://localhost:3000` by default.

## Database reset

The reset command deletes every table and every row in the PostgreSQL `public` schema, then recreates the database structure from `backend/schema.sql`.

From `backend/` with the virtual environment active:

```bash
python initdb.py --reset
```

After a reset, existing users, authentication sessions, photos, likes, blocks, visit history, notification suppressions, messages, reports and notifications are gone. The future seed command from Step 5 will restore the required evaluation profiles.

Step 4 changes `user_views` from one row per viewer/profile pair to separate visit-history rows and adds notification suppression after a connected unlike. Upgrading from Step 3 therefore requires this destructive reset. Running `python initdb.py` without `--reset` cannot alter an existing table created by an older `CREATE TABLE IF NOT EXISTS` definition.

## Authentication sessions

Access and refresh JWTs are stored only in `HttpOnly` cookies. JavaScript can read the separate CSRF cookies but cannot read the authentication tokens themselves.

Each login or OAuth login creates an `auth_sessions` row. Protected requests are accepted only when that server-side session is active and the token version still matches the user. Logout revokes the current session. Password reset increments the token version and revokes every existing session for that account.

The frontend automatically uses the refresh cookie when the short access token expires. Keep the frontend and backend on the same hostname during local development, using `localhost` for both URLs.

## Profile data model

The profile stores `birth_date` and calculates age dynamically. Gender uses `male`, `female`, or `non-binary`. Sexual preferences are stored as a PostgreSQL array of those same values. New users start with all three values for the required default-bisexual behavior, but profile editing cannot save an empty preference array.

The `tags` table is seeded with exactly 20 approved reusable interests. Users select existing tag IDs and cannot create arbitrary tags. Tag replacement runs in one transaction.

Exact latitude and longitude remain available only in the authenticated user's private profile response. Public profile responses contain the approximate location name but not exact coordinates.

Fame rating has one formula:

```text
received likes × 3
+ profile views × 0.5
+ profile-completion points from 0 to 10
```

Uploaded photos are validated by decoded image content, re-encoded as PNG or JPEG, saved under random names, and limited to five through a transaction-level PostgreSQL advisory lock.


Every valid public-profile visit creates a separate `user_views` row with its own timestamp. Mutual likes are derived from the two directional `user_likes` rows. A connected unlike removes only the current user's like, records the mandatory unlike notification, and suppresses future notifications from the disconnected user until the current user likes them again.

Blocking keeps historical visits, reports, and notifications, removes likes in both directions, and prevents profile access, interaction, and new notifications. Users can unblock from `/settings/blocked`, but old likes are not restored. Fake-account reporting remains one button and one unique report row per pair.

## Profile completion gate

After the first login, an incomplete account is restricted to `/profile`. The backend also enforces
this rule, so changing the URL or calling social endpoints directly does not bypass it.

Completion requires first name, last name, email, birth date, gender, at least one sexual preference,
a non-empty biography, at least one predefined tag, at least one photo with one primary photo, and a
usable GPS or manual location.

Until completion:

- the account is not returned as a public profile;
- other profiles, activity, notifications, blocks, browse, search, messages, and Socket.IO presence are unavailable;
- authentication and profile-completion routes remain available.

User information is saved with the button inside that section. Tags, photos, and location save
automatically. The final selected preference, tag, and photo cannot be removed. The primary photo is
ordered first and visibly marked in edit and public-profile views.

This correction does not change the database schema, so it does not require a database reset.

## Backend routes

### Authentication

```text
GET    /api/auth/me
POST   /api/auth/register
GET    /api/auth/verify/<token>
POST   /api/auth/resend-verification
POST   /api/auth/login
POST   /api/auth/refresh
POST   /api/auth/logout
POST   /api/auth/forgot-password
POST   /api/auth/reset-password
GET    /api/auth/verify-reset-token/<token>
```

### Profile

```text
GET    /api/profile
PUT    /api/profile
GET    /api/profile/tags
PUT    /api/profile/tags
POST   /api/profile/photos
DELETE /api/profile/photos/<photo_id>
PUT    /api/profile/photos/<photo_id>/primary
PUT    /api/profile/location
GET    /api/profile/viewers
GET    /api/profile/likes
```

### Users

```text
GET    /api/users/blocked
GET    /api/users/<user_id>
POST   /api/users/<user_id>/like
DELETE /api/users/<user_id>/like
POST   /api/users/<user_id>/block
DELETE /api/users/<user_id>/block
POST   /api/users/<user_id>/report
```

### Notifications

```text
GET /api/notifications
GET /api/notifications/unread-count
PUT /api/notifications/<notification_id>/read
PUT /api/notifications/read-all
```

### OAuth

```text
GET /api/auth/oauth/42/login
GET /api/auth/oauth/42/callback
GET /api/auth/oauth/google/login
GET /api/auth/oauth/google/callback
```

### Uploaded files

```text
GET /uploads/<filename>
```

## Frontend routes

Existing routes:

```text
/
/login
/signup
/verify
/forgot-password
/reset-password
/oauth-callback
/profile
/profile/activity
/settings/blocked
/users/[id]
```

Referenced but not implemented yet:

```text
/browse
/search
/messages
```

These missing routes belong to later approved plan steps.

## Socket.IO events

Events received by the backend:

```text
connect
disconnect
```

Events emitted by the backend:

```text
presence
notification
```

Chat events are not implemented yet and belong to Step 7.

## Baseline tests

From `backend/` with the virtual environment active:

```bash
python -m unittest discover -s tests -v
```


## Step 4 relationship correction

- Blocking removes likes in both directions and immediately disconnects a match.
- Profile reads are side-effect free; visits are recorded through `POST /api/users/<id>/visit` with a UUID idempotency key.
- `/api/profile/activity` separates visits, outgoing pending likes, incoming pending likes, and matches.
