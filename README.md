# Matcha

Matcha is a full-stack dating web application built as a 42 school project. Users create an account, fill out a profile with photos, interests and a location, then browse suggested profiles. When two users like each other, they match and can chat in real time, start audio calls, and plan dates.

| Layer     | Technology |
|-----------|------------|
| Frontend  | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, React Hook Form + Zod, Axios, Socket.IO client |
| Backend   | Python 3.11, Flask 3, Flask-SocketIO, Flask-JWT-Extended, Flask-Mail, Pillow, zxcvbn |
| Database  | PostgreSQL 16, queried with raw SQL through `psycopg2` and a connection pool (no ORM) |
| Real-time | Socket.IO for chat, notifications and presence; WebRTC for audio calls |
| External  | OpenStreetMap tiles and Nominatim geocoding, 42 and Google OAuth, an SMTP server for email |
| Infra     | Docker Compose |

---

## Table of contents

1. [Quick start](#quick-start)
2. [Configuration](#configuration)
3. [Architecture](#architecture)
4. [Features](#features)
5. [Matching and fame rating](#matching-and-fame-rating)
6. [Database schema](#database-schema)
7. [REST API](#rest-api)
8. [Socket.IO events](#socketio-events)
9. [Security](#security)
10. [Project structure](#project-structure)
11. [Useful commands](#useful-commands)

---

## Quick start

**Requirements:** Docker with the Compose plugin, and Bash (on Windows, use Git Bash or WSL).

1. Create `backend/.env` (see [Configuration](#configuration)).
2. Run:

   ```bash
   ./start.sh
   ```

The script does five things:

1. Builds the backend and frontend images.
2. Starts PostgreSQL and waits until it is healthy.
3. Applies `backend/schema.sql` (`initdb.py`).
4. Generates **500 seeded profiles** with photos, tags, locations, likes and views (`seed.py`).
5. Starts the backend and frontend and waits for their health checks to pass.

When it finishes:

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:3000 |
| Backend  | http://localhost:5000 (health check: `/api/health`) |

You can log in with any seeded account from `seed_001` to `seed_500`. The shared password is printed at the end of `start.sh` and defined in `backend/seed.py`.

> Both ports are bound to `127.0.0.1`, so the app is only reachable from the local machine.

---

## Configuration

All backend settings come from `backend/.env`. Docker Compose also reads this file to configure the PostgreSQL container. On startup, `Config.validate()` in `backend/app/config.py` checks the values and refuses to start if something required is missing or unsafe.

| Variable | Required | Notes |
|----------|----------|-------|
| `SECRET_KEY` | yes | Random value of at least 32 characters |
| `JWT_SECRET_KEY` | yes | At least 32 characters, and different from `SECRET_KEY` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | yes | Compose builds `DATABASE_URL` from these |
| `MAIL_SERVER`, `MAIL_DEFAULT_SENDER` | yes | SMTP server for verification and password-reset emails |
| `MAIL_PORT`, `MAIL_USE_TLS` | no | Defaults: `587`, `true` |
| `MAIL_USERNAME`, `MAIL_PASSWORD` | no | Must be set together |
| `NOMINATIM_URL`, `NOMINATIM_USER_AGENT`, `NOMINATIM_TIMEOUT_SECONDS` | no | Geocoding service. Defaults to the public OpenStreetMap instance |
| `FORTYTWO_CLIENT_ID`, `FORTYTWO_CLIENT_SECRET` | no | Turns on "Log in with 42". Both must be set |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | no | Turns on "Log in with Google". Both must be set |

The OAuth redirect URIs are fixed in the config:

- `http://localhost:5000/api/auth/oauth/42/callback`
- `http://localhost:5000/api/auth/oauth/google/callback`

The frontend's public settings (API URL, Socket URL, map tile URL, STUN server) are passed as build arguments in `docker-compose.yml`.

---

## Architecture

```
 Browser ──► Next.js frontend (:3000)
    │
    ├── REST (Axios, JWT in cookies + CSRF header) ──► Flask API (:5000) ──► PostgreSQL (:5432)
    ├── Socket.IO (chat, notifications, presence, call signalling) ──► Flask-SocketIO
    ├── WebRTC (peer-to-peer audio, via a STUN server)
    └── OpenStreetMap tiles (map page)

 Flask API ──► SMTP (emails), Nominatim (geocoding), 42 / Google (OAuth)
```

Docker Compose runs these services:

| Service    | Role |
|------------|------|
| `db`       | PostgreSQL 16. Data is stored in the `backend_matcha_pg_data` volume |
| `schema`   | One-off job that runs `python initdb.py` |
| `seed`     | One-off job that runs `python seed.py` and writes generated photos to the `matcha_uploads` volume |
| `backend`  | Flask + Socket.IO server (`python run.py`). Serves `/api/*` and `/uploads/*` |
| `frontend` | Next.js standalone production server |

**Backend.** `create_app()` in `backend/app/__init__.py` sets up the database pool, JWT, mail, CORS and Socket.IO. It then registers one blueprint per domain (`auth`, `oauth`, `profile`, `users`, `discover`, `messages`, `notifications`, `dates`), adds security headers, and turns every error into a JSON response. All SQL lives in `app/models.py`. Input checks live in `app/validation.py`.

**Frontend.** The app uses two route groups:

- `(auth)`: login, signup, email verification, forgot/reset password, OAuth callback.
- `(dashboard)`: the logged-in app (discover, map, messages, dates, profile, activity, blocked users, other users' profiles).

Global state lives in `AuthContext`, `NotificationBell` (which also owns the socket connection) and `AudioCallProvider`. All HTTP calls go through `app/services/api.ts`.

---

## Features

### Accounts and authentication
- Sign up with username, email, first and last name, and password. Passwords must be at least 8 characters with upper case, lower case, a digit and a symbol. They must also score at least 3 in **zxcvbn** and must not be based on the username, email or name.
- Email verification with a signed, time-limited link. The link can be resent.
- Login, logout, and silent token refresh.
- Forgot password and reset password by email. A reset revokes every existing session.
- OAuth login with **42** and **Google**. Each provider identity is linked to exactly one local account.

### Profile
- Gender, sexual preferences (any of male, female, non-binary), birth date (age 18–80) and a biography of up to 500 characters.
- Interests chosen from a fixed list of 20 tags.
- Up to **5 photos** (JPEG or PNG, at most 5 MB each). Each upload is re-encoded and resized to fit 1600×1600. Photos can be edited in the browser, and one is marked as the profile picture.
- Location set from browser GPS (only with consent) or by searching an address through Nominatim.
- Activity page showing who viewed your profile and who liked you.
- **Discovery, messaging and the other social features stay locked until the profile is complete.** The API returns `403 PROFILE_INCOMPLETE` with the list of missing fields.

### Discovery
- A paginated list of suggested profiles. Filters: age range, fame range, location text and shared tags. Sort options: recommended, age, distance, fame, common tags (ascending or descending).
- A map view showing nearby profiles at approximate positions, using OpenStreetMap tiles.

### Interactions
- **Like / unlike.** A like sent back by the other user creates a **match** ("connected"), and both users are notified. Unliking a match notifies the other user and closes the chat.
- **Profile views** are recorded once per visit and count toward fame.
- **Block.** Hides both users from each other everywhere and turns off all interactions between them. Blocked users can be managed in Settings.
- **Report** a profile as a fake account (once per pair of users).
- **Online status.** Shows whether a user is online now, or when they were last active.

### Real-time
- **Chat** between matched users, with unread counts and read receipts.
- **Notifications** for likes, views, messages, matches, unlikes and date events. They are saved in the database and pushed live, so unread state survives a page reload.
- **Audio calls** between matched users using WebRTC. Socket.IO carries the call setup messages, and an unanswered call stops ringing after 30 seconds.

### Bonus: dates
- Matched users can propose a date with a time, a place and a note. The other user can accept or decline, and the proposer can cancel. Both sides are notified at each step.

---

## Matching and fame rating

### Who appears in discovery
A candidate profile is shown only if **all** of the following are true:

- Their email is verified and their profile is complete (profile picture, bio, tags, location, gender, birth date).
- Their gender is in your preferences, **and** your gender is in theirs.
- Neither of you has blocked the other.

### Recommended order
Recommended results are sorted by these keys, in this order:

1. **Same area.** The city part of `location_name` matches yours.
2. **Distance.** Calculated in SQL with the Haversine formula, closest first.
3. **Number of shared tags**, most first.
4. **Fame rating**, highest first.

### Fame rating (0–100)
```
fame = 3 × likes received
     + 0.5 × profile views received
     + profile completion points (up to 10)
```
Completion points: birth date 1, gender 1, preferences 1, biography 2, at least one tag 1, at least one photo 2, location 2. The score is recalculated whenever the inputs change and is capped at 100.

---

## Database schema

`backend/schema.sql` is idempotent: it can be run again safely on an existing database. Run `python initdb.py --reset` to drop everything and start from an empty schema.

| Table | Purpose |
|-------|---------|
| `users` | Account, profile, location, presence, fame and `token_version` |
| `auth_sessions` | Server-side sessions, so logout and password resets take effect immediately |
| `oauth_identities` | Links between 42/Google accounts and local users |
| `tags`, `user_tags` | The fixed interest list and each user's chosen tags |
| `photos` | Up to 5 ordered photos per user. A unique index allows only one profile picture |
| `user_likes` | One-way likes. Two opposite rows mean a match |
| `user_blocks` | Blocks, applied in both directions |
| `user_views` | Profile visits. `visit_id` makes sure a visit is counted once |
| `notification_suppressions` | Mutes notifications from a user after you unlike a match |
| `messages` | Chat history with read state |
| `date_events` | Date proposals with status `pending`, `accepted`, `declined` or `cancelled` |
| `reports` | Fake-account reports |
| `notifications` | Saved notifications with read state |

The data rules are enforced in the database itself through `CHECK` constraints, foreign keys with `ON DELETE CASCADE`, and indexes built for the discovery, chat and unread-count queries.

---

## REST API

All routes start with `/api`. Logged-in requests send the JWT in an HTTP-only cookie. Requests that change data (`POST`, `PUT`, `DELETE`) must also send the CSRF token header. Routes marked ★ require a complete profile.

### Auth: `/api/auth`
| Method | Path | Description |
|--------|------|-------------|
| POST | `/register` | Create an account and send a verification email |
| GET | `/verify/<token>` | Verify an email address |
| POST | `/resend-verification` | Send the verification email again |
| POST | `/login` | Log in and set the JWT cookies |
| POST | `/refresh` | Get a new access token |
| POST | `/refresh/bootstrap` | Refresh the session when the app first loads |
| POST | `/logout` | Revoke the current session |
| GET | `/me` | Get the current user |
| POST | `/forgot-password` | Send a password-reset email |
| GET | `/verify-reset-token/<token>` | Check whether a reset link is valid |
| POST | `/reset-password` | Set a new password and revoke all sessions |
| GET | `/oauth/{42,google}/login` | Start an OAuth login |
| GET | `/oauth/{42,google}/callback` | OAuth callback |

### Profile: `/api/profile`
| Method | Path | Description |
|--------|------|-------------|
| GET / PUT | `` | Read or update your own profile |
| GET / PUT | `/tags` | List the available tags or set your tags |
| POST | `/photos` | Upload a photo |
| PUT / DELETE | `/photos/<id>` | Replace or delete a photo |
| PUT | `/photos/<id>/primary` | Make a photo your profile picture |
| GET | `/location/search?q=` | Search an address (Nominatim) |
| PUT | `/location` | Save your location |
| GET | `/viewers`, `/likes`, `/activity` | Who viewed you, who liked you, combined activity |

### Users: `/api/users` ★
| Method | Path | Description |
|--------|------|-------------|
| GET | `/<id>`, `/by-username/<username>` | View a profile |
| POST | `/<id>/visit` | Record a profile view |
| POST / DELETE | `/<id>/like` | Like or unlike |
| POST / DELETE | `/<id>/block` | Block or unblock |
| POST | `/<id>/report` | Report a fake account |
| GET | `/blocked` | List the users you blocked |

### Discover: `/api/discover` ★
| Method | Path | Description |
|--------|------|-------------|
| GET | `` | Paginated suggestions. Query: `minAge`, `maxAge`, `minFame`, `maxFame`, `location`, `tagIds`, `sort`, `order`, `page`, `pageSize` |
| GET | `/map` | Same filters, returns up to 500 profiles at approximate positions |

### Messages: `/api/messages` ★
| Method | Path | Description |
|--------|------|-------------|
| GET | `` | List conversations |
| GET | `/unread-count` | Number of unread messages |
| GET / POST | `/<userId>` | Read message history or send a message (matched users only) |
| PUT | `/<userId>/read` | Mark a conversation as read |

### Notifications: `/api/notifications`
| Method | Path | Description |
|--------|------|-------------|
| GET | `` | List notifications |
| GET | `/unread-count` | Number of unread notifications |
| PUT | `/<id>/read`, `/read-all` | Mark one or all as read |

### Dates: `/api/dates` ★
| Method | Path | Description |
|--------|------|-------------|
| GET | `` | List your dates |
| POST | `/<userId>` | Propose a date |
| PUT | `/<id>/respond` | Accept or decline |
| PUT | `/<id>/cancel` | Cancel a date you proposed |

### Other
- `GET /api/health`: checks that the database is reachable. Used by the Docker health check.
- `GET /uploads/<filename>`: serves uploaded photos.

---

## Socket.IO events

The socket connection is authenticated with the same JWT cookie as the REST API. After connecting, each user joins a private room named `user:<id>`.

| Direction | Event | Purpose |
|-----------|-------|---------|
| server → client | `notification` | A new notification was created |
| server → client | `message`, `message_read` | A new chat message, or a read receipt |
| server → client | `conversation_status` | A chat was opened or closed (after a match, unlike or block) |
| server → client | `presence` | A user came online or went offline |
| server → client | `date_event` | A date was created or its status changed |
| client → server | `call_start`, `call_accept`, `call_decline`, `call_signal`, `call_end` | Audio call setup and teardown |
| server → client | `call_incoming`, `call_accepted`, `call_declined`, `call_signal`, `call_ended` | The matching events delivered to the other user |

---

## Security

- Passwords are hashed with **bcrypt** and checked for strength with zxcvbn.
- JWTs are stored in **HTTP-only cookies** with `SameSite=Lax` and double-submit **CSRF** protection. The refresh token cookie is only sent to `/api/auth/refresh`.
- Every token carries a session id and a `token_version`, both checked on every request. This means logout, password resets and revoked sessions take effect immediately.
- All SQL queries use bound parameters. User input is validated on the server, and the database adds its own `CHECK` constraints.
- Uploaded images are opened with Pillow, limited by format, file size and pixel count, then re-encoded. The original file is never stored as-is.
- Both servers send `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy` and `Permissions-Policy` headers. API responses are sent with `Cache-Control: no-store`.
- OAuth uses a signed `state` value that expires after 10 minutes.
- CORS only allows `http://localhost:3000`.

> The cookie flags (`JWT_COOKIE_SECURE=False`, `SameSite=Lax`) and the Werkzeug development server are set up for **local** use. For a production deployment, serve the app over HTTPS, turn on secure cookies, and run the app behind a production WSGI server.

---

## Project structure

```
matcha/
├── start.sh                 # One-command build, migrate, seed and run
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── run.py               # Entry point (Socket.IO server)
│   ├── initdb.py            # Applies schema.sql (--reset to wipe)
│   ├── schema.sql           # Full database schema
│   ├── seed.py              # Generates 500 test profiles with photos
│   └── app/
│       ├── __init__.py      # App factory, blueprints, headers, error handlers
│       ├── config.py        # Environment-based config and its validation
│       ├── extensions.py    # JWT, Mail, CORS and session revocation hooks
│       ├── db.py            # psycopg2 connection pool helpers
│       ├── models.py        # All SQL: users, discovery, fame, notifications…
│       ├── validation.py    # Input and password validation
│       ├── auth.py          # Register, login, verify, reset, refresh
│       ├── oauth.py         # 42 and Google OAuth
│       ├── profile.py       # Profile, tags, photos, location, activity
│       ├── profile_access.py# @complete_profile_required decorator
│       ├── users.py         # View, like, block, report
│       ├── discover.py      # Suggestions and map
│       ├── messages.py      # Chat
│       ├── notifications.py
│       ├── dates.py         # Bonus: date planning
│       ├── sockets.py       # Socket.IO: presence, rooms, call signalling
│       └── utils.py         # Images, email, tokens, geocoding helpers
└── frontend/my-app/
    ├── Dockerfile
    ├── next.config.ts
    └── app/
        ├── (auth)/          # login, signup, verify, forgot/reset password, oauth-callback
        ├── (dashboard)/     # discover, map, messages, dates, profile, users/[username], settings
        ├── components/      # UserCard, UserMap, PhotoEditor, NotificationBell, AudioCallProvider…
        ├── context/         # AuthContext
        ├── services/api.ts  # Axios client with CSRF handling
        ├── lib/             # Validation and error helpers
        └── types/           # Shared TypeScript types
```

---

## Useful commands

```bash
# Show logs
docker compose --env-file backend/.env logs -f backend frontend

# Stop everything (data is kept)
docker compose --env-file backend/.env down

# Stop everything and delete the database and uploaded photos
docker compose --env-file backend/.env down -v

# Wipe the database and apply the schema again
docker compose --env-file backend/.env run --rm schema python initdb.py --reset

# Generate the seed profiles again
docker compose --env-file backend/.env run --rm seed

# Lint the frontend
cd frontend/my-app && npm run lint
```
