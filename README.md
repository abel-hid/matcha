# Matcha

This repository contains a Flask/PostgreSQL backend and a Next.js/TypeScript frontend.

`backend/schema.sql` is the complete database definition. This project does not use migrations.

## Docker runtime

PostgreSQL, schema setup, evaluation seeding, Flask, Socket.IO, and Next.js all run in Docker containers. The host needs only Docker Engine or Docker Desktop with Docker Compose.

The frontend is built in production mode. This removes Next.js development messages such as HMR and the React DevTools recommendation from the Chrome console. The application does not override `console`, suppress unhandled exceptions, or convert legitimate client errors into fake HTTP `200` responses. Normal successful flows should have a clean console, while controlled invalid actions still retain the appropriate HTTP status in the Network panel as required by the subject.

## Environment setup

From the repository root:

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and replace every placeholder secret. Google and 42 OAuth variables may remain empty. For either provider, set all three variables for that provider or leave all three empty.

Never commit `backend/.env`. Keep `JWT_COOKIE_SECURE=false` for the local HTTP setup. Use `true` only when the application is served through HTTPS.

## Start the complete application

From the repository root:

```bash
chmod +x start.sh
./start.sh
```

That single command:

1. validates the Docker and environment configuration;
2. builds the backend and production frontend images;
3. starts PostgreSQL and waits for it to become healthy;
4. applies `backend/schema.sql`;
5. regenerates exactly 500 deterministic evaluation profiles;
6. starts Flask, Socket.IO, and Next.js;
7. waits for the backend and frontend health checks.

Open:

```text
http://localhost:3000
```

The backend is available at:

```text
http://localhost:5000
```

View container status:

```bash
docker compose --env-file backend/.env ps
```

View service logs:

```bash
docker compose --env-file backend/.env logs -f backend frontend
```

Stop the application without deleting PostgreSQL data:

```bash
docker compose --env-file backend/.env down
```

The PostgreSQL and upload Docker named volumes persist between runs. The startup script reuses the previous database volume and replaces only accounts whose usernames begin with `seed_`.

## Database reset

The reset command deletes every table and every row in the PostgreSQL `public` schema, then recreates the database structure from `backend/schema.sql`.

From the repository root:

```bash
docker compose --env-file backend/.env run --rm schema python initdb.py --reset
```

After a reset, existing users, authentication sessions, photos, likes, blocks, visit history, notification suppressions, messages, reports and notifications are gone. The Step 5 seed command restores the required evaluation profiles.

Step 4 changes `user_views` from one row per viewer/profile pair to separate visit-history rows and adds notification suppression after a connected unlike. Upgrading from Step 3 therefore requires this destructive reset. Running `python initdb.py` without `--reset` cannot alter an existing table created by an older `CREATE TABLE IF NOT EXISTS` definition.


## Evaluation seed data

Step 5 provides one deterministic seed command for the required evaluation
dataset. It preserves non-seed accounts and replaces only usernames beginning
with `seed_`.

The normal Docker startup runs the seed automatically:

```bash
./start.sh
```

To rerun only the fixed seed manually:

```bash
docker compose --env-file backend/.env run --rm seed
```

The default command creates exactly 500 verified, complete profiles:

```text
seed_001
seed_002
...
seed_500
```

Every seed account uses this local evaluation password:

```text
lhfTYh6452fdHH9
```

This shared password is intentionally limited to generated local test data. It
does not change or weaken registration password validation.

The seed includes:

- ages from 18 through 80;
- all supported genders and varied sexual preferences;
- two to seven predefined interests per user;
- one to five generated PNG photos with one primary photo;
- Moroccan cities and neighborhoods with usable coordinates;
- deterministic pending likes and mutual matches;
- visit history and varied fame ratings.

The command is repeatable. Running it again removes old `seed_` accounts and
regenerates them without deleting manually registered users. Generated photos
are stored in the ignored `backend/uploads` directory.

`seed.py` accepts no command-line options and always generates exactly 500 profiles. This keeps the evaluation dataset and startup behavior deterministic.

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


## Discover and advanced research

The home page combines the subject's suggested-profile list and advanced research. Default results require mutual preference compatibility and exclude the current user, blocked users, unverified users, and incomplete profiles.

Suggested ordering is:

1. same city;
2. shortest geographical distance;
3. highest common-tag count;
4. highest fame rating.

The same page can filter by age range, fame range, city or neighborhood, and one or more predefined tags. It can sort by age, distance/location, fame, or common tags. Selecting multiple tags requires every selected tag to be present on the result profile.


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
- other profiles, activity, notifications, blocks, Discover, messages, and Socket.IO presence are unavailable;
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
GET    /api/users/by-username/<username>
POST   /api/users/<user_id>/like
DELETE /api/users/<user_id>/like
POST   /api/users/<user_id>/block
DELETE /api/users/<user_id>/block
POST   /api/users/<user_id>/report
```

### Discover and advanced research

```text
GET /api/discover
```

With no custom criteria, this endpoint returns suggested compatible profiles ranked by same city, distance, common tags, and fame rating. The same endpoint accepts age, fame, location, tags, sorting, and pagination parameters for advanced research.

### Messages

```text
GET  /api/messages
GET  /api/messages/unread-count
GET  /api/messages/<user_id>
POST /api/messages/<user_id>
PUT  /api/messages/<user_id>/read
```

Only mutually connected users can send messages. PostgreSQL stores every
message. A disconnected conversation remains available as read-only history,
while a blocked conversation is hidden completely.

### Notifications

```text
GET /api/notifications
GET /api/notifications/unread-count
PUT /api/notifications/<notification_id>/read
PUT /api/notifications/read-all
```

Notifications are persisted and delivered through authenticated Socket.IO.
When the socket is unavailable, the frontend refreshes notification state every
eight seconds so the mandatory ten-second delivery limit still has an HTTP
recovery path.

### OAuth

```text
GET /api/auth/oauth/42/login
GET /api/auth/oauth/42/callback
GET /api/auth/oauth/google/login
GET /api/auth/oauth/google/callback
```

### Dates

```text
GET  /api/dates
POST /api/dates/<user_id>
PUT  /api/dates/<event_id>/respond
PUT  /api/dates/<event_id>/cancel
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
/users/[username]
/messages
/dates
```

The `/` route is the combined Discover and advanced-research page. There are no separate `/browse` or `/search` pages. The `/messages` route lists current matches and previous unblocked conversations, delivers new messages in real time, and disables sending immediately after unlike or block.

## Socket.IO events

Events received by the backend:

```text
connect
disconnect
call_start
call_accept
call_decline
call_signal
call_end
```

Events emitted by the backend:

```text
presence
notification
message
conversation_status
call_incoming
call_accepted
call_declined
call_signal
call_ended
date_event
```

`message` delivers the stored PostgreSQL message to both participants.
`conversation_status` enables chat after a match and disables it immediately
after unlike or block.

## Baseline tests

From `backend/` with the virtual environment active:

```bash
python -m unittest discover -s tests -v
```


## Step 4 relationship correction

- Blocking removes likes in both directions and immediately disconnects a match.
- Profile reads are side-effect free; visits are recorded through `POST /api/users/<id>/visit` with a UUID idempotency key.
- `/api/profile/activity` separates visits, outgoing pending likes, incoming pending likes, and matches.

## Step 8 bonuses: OAuth, gallery editor, and user map

### OAuth configuration

Google and 42 remain optional. Leave all three variables for a provider empty to disable it, or configure the complete provider group in `backend/.env`.

```env
OAUTH_TIMEOUT_SECONDS=8
OAUTH_STATE_MAX_AGE_SECONDS=600

FORTYTWO_CLIENT_ID=...
FORTYTWO_CLIENT_SECRET=...
FORTYTWO_REDIRECT_URI=http://localhost:5000/api/auth/oauth/42/callback

GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:5000/api/auth/oauth/google/callback
```

The configured redirect URI must exactly match the URI registered with the provider. OAuth callbacks create the same HttpOnly-cookie session used by local login. Provider tokens are never placed in frontend URLs.

A user may link one Google identity and one 42 identity to the same Matcha account when the verified provider email matches the existing account email. Provider identities are stored in `oauth_identities`, not in the `users` row.

### Gallery editor

The profile gallery supports drag-and-drop upload, square cropping, 90-degree rotation, and four controlled filter choices. Browser editing creates a JPEG upload, but the backend still independently validates the image contents, dimensions, size, ownership, five-photo limit, and primary-photo invariant before re-encoding and storing it.

### Interactive map

The protected `/map` page uses the same compatibility, completion, block, age, fame, location, tag, and sorting rules as Discover. Exact candidate coordinates remain server-side. The API rounds marker coordinates before returning them. The current user can explicitly consent to refreshing their position through browser GPS or keep the manual location saved from Profile.

Map tiles default to OpenStreetMap and are displayed with attribution. A different compatible template can be selected with `NEXT_PUBLIC_MAP_TILE_URL`, using `{z}`, `{x}`, and `{y}` placeholders.

Because Step 8 adds the `oauth_identities` table and removes the old single-provider columns from `users`, recreate the database from `schema.sql`, then rerun the seed command.

## Step 9: audio calls and date scheduling

Step 9 intentionally implements audio only. The browser never requests camera
permission and no video track is created or transmitted.

Connected, non-blocked users can start an audio call from a public profile or
from the Messages conversation header. The global call interface remains
visible while navigating between protected pages. It supports incoming-call
accept/decline, outgoing ringing, a 30-second no-answer timeout, mute, elapsed
call time, and hang-up. Flask-SocketIO authorizes every invitation and WebRTC
signal against the current mutual connection. Unlike, block, logout,
disconnection, or a lost relationship ends the call immediately.

WebRTC uses the optional Docker build variable:

```env
NEXT_PUBLIC_WEBRTC_STUN_URL=stun:stun.l.google.com:19302
```

Set it to another STUN URL when required by the evaluation network. Media is
still peer-to-peer; Socket.IO carries only invitation and WebRTC signaling
data.

The protected `/dates` page lets connected users propose a future date with a
UTC-backed time, location, and optional note. The recipient can accept or
decline, either participant can cancel a pending or accepted future date, and
old proposals remain visible as history. New or changed proposals create a
persisted `date` notification and a real-time update.

### Date endpoints

```text
GET  /api/dates
POST /api/dates/<user_id>
PUT  /api/dates/<event_id>/respond
PUT  /api/dates/<event_id>/cancel
```

### Audio-call Socket.IO events

Received by the backend:

```text
call_start
call_accept
call_decline
call_signal
call_end
```

Emitted by the backend:

```text
call_incoming
call_accepted
call_declined
call_signal
call_ended
date_event
```

The schema update is non-destructive. Running `./start.sh` creates the new
`date_events` table and expands the notification-type constraint before the
fixed 500-profile seed and application services start.
