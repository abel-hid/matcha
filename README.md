# Matcha

Matcha is a full-stack dating application built for the **Web Matcha 6.1** subject. It covers the mandatory path from account creation to a real-time conversation and adds the approved OAuth, photo editing, map, audio-call, and date-planning bonuses.

The project uses Flask, manually written PostgreSQL queries, Next.js with TypeScript, Socket.IO, WebRTC audio, and Docker Compose. The normal runtime is fully containerized; the host requires only Docker Engine or Docker Desktop with Docker Compose.

## Documentation set

This archive contains four project guides plus the official subject:

| Document | Purpose |
|---|---|
| `README.md` | Installation, operation, and the complete user-facing flow |
| `README_TECHNICAL.md` | Architecture and implementation from system level down to individual mechanisms |
| `MANUAL_AND_POSTMAN_TESTING.md` | Browser, API, Postman, Socket.IO, and failure-case verification |
| `FILE_STRUCTURE.md` | Final source tree and the responsibility of every important file |

The importable Postman files are stored under `postman/`.

## Source policy

The delivery archive intentionally excludes:

- `backend/.env` and all real credentials;
- `.git` history;
- backend and frontend automated test files;
- `node_modules`, `.next`, caches, logs, and generated build output;
- local uploaded photos and PostgreSQL volume data;
- obsolete planning files, patch rejects, default Next.js assets, and editor-specific files.

`backend/.env.example` is safe to commit. Create a private `backend/.env` before starting the application.

## Main features

### Mandatory Matcha flow

- Local registration with email, username, first name, last name, and strong password validation.
- Unique email verification link before local login.
- Login, short access session, refresh session, server-side revocation, single-click logout, and password reset.
- Mandatory profile completion gate.
- Gender, sexual preferences, biography, reusable interests, birth date, location, and up to five profile photos.
- Exactly one primary profile photo.
- GPS with explicit consent and manual location fallback.
- Fame rating, viewers, incoming likes, outgoing likes, and matches.
- Compatible profile suggestions ranked by geography, common interests, and fame.
- Advanced search and filtering by age, fame, location, and one or more tags.
- Public profiles, visit history, like, mutual match, unlike, block, unblock, and fake-account report.
- Online status and last activity.
- Real-time text chat for connected users only.
- Real-time notifications for views, likes, matches, messages, and connected unlikes.
- Persistent unread notification and unread message state.
- Exactly 500 deterministic evaluation profiles.

### Approved bonuses

- Google and 42 OAuth using state validation and the same secure cookie session system.
- Drag-and-drop photo upload with preview, crop, rotation, and controlled filters.
- Interactive user map with privacy-rounded public coordinates.
- Audio-only WebRTC calls between connected users.
- Real-life date proposals with accept, decline, cancel, upcoming, and history states.

## Project structure

```text
matcha/
├── README.md
├── README_TECHNICAL.md
├── MANUAL_AND_POSTMAN_TESTING.md
├── FILE_STRUCTURE.md
├── SUBJECT.MD
├── docker-compose.yml
├── start.sh
├── stop.sh
├── postman/
├── backend/
│   ├── app/
│   ├── schema.sql
│   ├── seed.py
│   ├── initdb.py
│   ├── run.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
└── frontend/
    └── my-app/
        ├── app/
        ├── public/
        ├── package.json
        ├── package-lock.json
        ├── next.config.ts
        ├── tsconfig.json
        └── Dockerfile
```

See `FILE_STRUCTURE.md` for the complete tree.

# 1. Local evaluation startup

## 1.1 Requirements

Install only:

- Docker Engine or Docker Desktop;
- Docker Compose v2;
- a recent Firefox or Chrome browser.

Python, Node.js, PostgreSQL, package managers, and project dependencies run inside containers.

## 1.2 Create private environment configuration

From the repository root:

```bash
cp backend/.env.example backend/.env
```

Replace every `replace_with_...` value. At minimum, configure:

```dotenv
SECRET_KEY=<long-random-secret>
JWT_SECRET_KEY=<different-long-random-secret>
POSTGRES_PASSWORD=<strong-local-database-password>
MAIL_SERVER=<working-smtp-server>
MAIL_DEFAULT_SENDER=<sender-address>
```

For authenticated SMTP, set both:

```dotenv
MAIL_USERNAME=<smtp-username>
MAIL_PASSWORD=<smtp-password>
```

The Docker configuration fixes the application to the local addresses `http://localhost:3000` and `http://localhost:5000`. Google and 42 OAuth are optional. For a provider, set both the client ID and client secret or leave both empty. The local callback URLs are fixed in the backend configuration.

## 1.3 Start everything

```bash
chmod +x start.sh stop.sh
./start.sh
```

The script prints seven explicit phases. It:

1. validates Docker and environment configuration;
2. builds the backend and frontend images, then validates backend configuration;
3. starts PostgreSQL and waits for health;
4. applies `backend/schema.sql`;
5. replaces only `seed_` accounts and creates exactly 500 evaluation profiles;
6. starts Flask, Socket.IO, and the compiled Next.js server;
7. waits for backend and frontend health checks.

Open:

```text
http://localhost:3000
```

Backend health endpoint:

```text
http://localhost:5000/api/health
```

## 1.4 Evaluation accounts

```text
Usernames: seed_001 through seed_500
Password:  lhfTYh6452fdHH9@
```

`seed_001` and `seed_002` are a deterministic mutual match, which makes them useful for chat, audio-call, notification, and date tests.

## 1.5 Stop without deleting data

```bash
./stop.sh
```

PostgreSQL and uploaded-image named volumes remain intact.

## 1.6 View service state and logs

```bash
docker compose --env-file backend/.env ps
```

```bash
docker compose --env-file backend/.env logs -f backend frontend
```

## 1.7 Destructive database reset

This removes all accounts, sessions, relationships, messages, dates, reports, and notifications before reapplying the schema:

```bash
docker compose --env-file backend/.env run --rm schema python initdb.py --reset
```

Regenerate the required evaluation dataset afterward:

```bash
docker compose --env-file backend/.env run --rm seed
```

# 2. Complete application flow

## 2.1 First browser load and authentication bootstrap

The frontend does not call a protected endpoint merely to discover whether the browser is logged in. `AuthProvider` calls:

```text
POST /api/auth/refresh/bootstrap
```

Possible outcomes:

- A valid refresh cookie and active server-side session return `authenticated: true`, the private user object, and a fresh access cookie.
- Missing, expired, malformed, or revoked refresh state returns HTTP `200` with `authenticated: false` and clears stale cookies.
- Unexpected network or server failures remain real failures and are shown as controlled UI state; they are not converted to fake successful responses.

An authenticated incomplete user is sent to `/profile`. A complete user can enter the full application.

## 2.2 Local registration

The registration form requires:

- username;
- email;
- first name;
- last name;
- password.

The frontend provides immediate feedback, but the backend independently validates every value. The backend normalizes the email and username, rejects malformed names, rejects weak or common passwords, rejects account-detail similarity, enforces the bcrypt byte limit, and checks uniqueness.

Successful sequence:

```text
submit registration
→ validate all fields
→ insert unverified account
→ send unique verification email
→ return HTTP 201
```

Failure sequence:

- Invalid shape or field: HTTP `400`.
- Existing username or email: HTTP `409`.
- Verification email cannot be sent: the newly inserted account is removed and HTTP `503` is returned.

No password is ever stored in plain text.

## 2.3 Email verification

The email contains a signed, expiring token. Opening `/verify?token=...` causes the frontend to call:

```text
GET /api/auth/verify/<token>
```

The backend checks signature, age, user identifier, and email address. A valid unused token marks the account verified. Invalid, expired, already-used, or account-mismatched links return controlled HTTP `400` responses with a reason code.

The resend endpoint uses a neutral response so callers cannot determine whether an address exists.

## 2.4 Login and session creation

Local login checks the username, password hash, and verification state. Successful login creates:

- one `auth_sessions` database row;
- one short-lived access JWT in an `HttpOnly` cookie;
- one longer-lived refresh JWT in an `HttpOnly` cookie;
- readable CSRF cookies used only to authorize unsafe requests.

The JWT includes:

- user ID;
- server-side session ID;
- user token version.

Every protected request is rejected when the session is expired or revoked, or when the token version no longer matches the user.

Login failures:

- Missing username/password: `400`.
- Wrong credentials: `401`.
- Unverified account: `401` with verification guidance.

## 2.5 Automatic refresh

The Axios response interceptor retries one eligible request after an access-session failure. It sends the refresh CSRF token to `/api/auth/refresh`, receives a new access cookie, updates the access CSRF header, and retries the original request once.

It never recursively refreshes authentication endpoints. A failed refresh clears readable cookie hints and returns the original failure to the caller.

## 2.6 Logout

Logout works from every authenticated page:

```text
click Log out
→ POST /api/auth/logout
→ revoke auth_sessions row
→ disconnect every Socket.IO connection for that session
→ clear JWT and CSRF cookies
→ route to /login
```

A copied old access token cannot pass the server-side session check after logout.

## 2.7 Forgotten password

The forgot-password endpoint always returns the same successful message for valid email syntax, whether or not the account exists. Existing users receive a signed reset link.

The reset flow validates:

- token signature and expiration;
- token email against a real account;
- token version against the current account version;
- replacement password strength and account-detail similarity.

Successful reset changes the password, increments the token version, revokes every existing session, disconnects all user sockets, and clears browser cookies. Reusing the same reset link returns `reason: used`.

## 2.8 OAuth login and account linking

Google and 42 use the same flow:

```text
select provider
→ create short-lived random state in an HttpOnly Flask session
→ redirect to provider
→ validate callback state once
→ exchange code with timeout
→ fetch provider profile
→ normalize verified email and identity
→ login linked account, link matching email, or create a verified account
→ create normal Matcha cookie session
→ redirect to /oauth-callback
```

JWTs never appear in the URL. Provider failures are converted to controlled login error codes. One provider identity cannot be linked to multiple accounts, and one account cannot have two identities from the same provider.

## 2.9 Mandatory profile-completion gate

After first login, an incomplete account can use only authentication and its own profile-completion functions. Both frontend routing and backend decorators enforce the rule.

Completion requires:

- non-empty first and last name;
- valid email;
- adult birth date;
- gender;
- at least one sexual preference;
- non-empty biography;
- at least one predefined reusable tag;
- at least one profile photo;
- exactly one primary photo;
- valid latitude, longitude, and location label.

Until all fields exist:

- `/profile` remains available;
- Discover, map, activity, blocks, public profiles, messages, dates, notifications, presence, and calls remain unavailable;
- the account is not returned to other users.

## 2.10 Editing identity and profile information

The user can update first name, last name, email, birth date, gender, sexual preferences, and biography. Empty mandatory values are rejected.

Changing email is special:

1. the new address is validated and checked for uniqueness;
2. a verification email is sent before the database update is finalized;
3. the account becomes unverified;
4. the user must verify the new email.

Profile changes that influence fame rating trigger a recalculation.

## 2.11 Reusable interests

The database contains exactly the approved reusable catalogue. The frontend loads those tag records and submits their numeric IDs.

The backend rejects:

- a non-list body;
- an empty list;
- booleans or non-integer IDs;
- more than 20 values;
- identifiers not present in the catalogue.

Replacement occurs in one database transaction, so the user never temporarily has a partially updated set.

## 2.12 Profile photos and editor

A user can store one to five photos. The first inserted photo becomes primary. A partial unique PostgreSQL index guarantees no more than one primary row per user.

Upload pipeline:

```text
browser selects or drops image
→ optional crop/rotation/filter preview
→ multipart upload
→ reject oversized input
→ decode image content with Pillow
→ reject unsupported or decompression-bomb input
→ normalize orientation and dimensions
→ re-encode as PNG or JPEG
→ save random filename
→ insert photo under per-user advisory lock
```

Changing the primary photo moves it to position zero. Deleting a primary photo promotes the next image. Deleting the final photo is rejected because the profile must retain one image.

A text file renamed `.jpg` fails decoded-content validation.

## 2.13 Location and consent

The location section has explicit GPS consent.

When consent is enabled:

1. the browser requests geolocation permission;
2. cached low-accuracy location may be tried first;
3. a fresh higher-accuracy request follows;
4. coordinates are validated against latitude and longitude ranges;
5. reverse geocoding attempts to create a neighborhood or city label;
6. valid coordinates remain usable even if reverse geocoding is unavailable.

When consent is disabled or browser permission is denied, manual search remains mandatory. The user selects a geocoded city or neighborhood, and the same validated coordinates are saved with `gpsConsent: false`.

Exact coordinates appear only in the owner’s private profile. Public profiles expose a location name, and the map receives rounded coordinates.

## 2.14 Fame rating

The fame score is consistent and bounded between 0 and 100:

```text
received likes × 3
+ profile views × 0.5
+ profile completion points from 0 to 10
```

The rating is recalculated when relevant profile data, likes, views, photos, tags, or blocks change.

## 2.15 Discover and advanced search

The home route combines suggestions and advanced research.

A candidate must be:

- verified;
- complete;
- not the current user;
- not blocked in either direction;
- compatible with both users’ gender preferences.

Default ordering gives priority to:

1. same geographical area;
2. shortest calculated distance;
3. most common tags;
4. highest fame rating;
5. stable ID tie-breaker.

Filtering supports:

- minimum and maximum age;
- minimum and maximum fame;
- city or neighborhood text;
- one or multiple reusable tags.

When multiple tags are selected, every selected tag must exist on the candidate profile. Results can be sorted by age, distance/location, fame, or common tags in ascending or descending order. Pagination parameters are bounded.

## 2.16 Interactive map

The map reuses the same compatibility and filter rules as Discover. It receives rounded candidate coordinates, never exact private coordinates.

The user can pan, zoom, select a marker, open the profile, and close the profile popup by clicking an empty map area or outside the map. The removed sort-direction controls do not affect discovery filtering.

## 2.17 Public profile and visits

Public URLs use:

```text
/users/<username>
```

A public response excludes email, password hash, exact coordinates, session data, and OAuth identifiers. It includes profile details, photos, interests, fame, presence, last activity, and relationship state.

Each page visit uses a browser-generated UUID. Repeating the same logical visit is idempotent; a later real visit uses a new UUID and creates another history row. A successful new visit creates the mandatory real-time view notification and updates fame rating.

## 2.18 Likes, matches, and unlike

A complete user with a primary photo can like another visible profile.

- First directional like: target receives a `like` notification.
- Opposite like already exists: both users receive `match` notifications and chat becomes available immediately.
- Duplicate like: `409`.
- Self-like: `400`.

Unlike removes only the current user’s directional like. When the users were connected, it also:

- creates the mandatory `unlike` notification for the other user;
- disables chat in both open browsers;
- ends an active or ringing audio call;
- suppresses future notifications from the disconnected user until the current user likes them again.

Historical messages remain stored but cannot be extended while disconnected.

## 2.19 Block, unblock, and report

Blocking performs one transaction that creates the block and removes both users’ likes. It then disables chat and ends calls in real time.

A blocked user:

- disappears from Discover, search, map, activity relationship lists, and public-profile access;
- cannot send messages or calls;
- cannot create notifications;
- is represented as unavailable rather than revealing block direction.

Unblocking removes only the block. Old likes are not restored.

Reporting is one click and stores only `fake_account`. The unique pair constraint prevents duplicate reports.

## 2.20 Activity

The Activity page separates:

- profile visits;
- profiles liked by the user without a return like;
- users who liked the profile without a return like;
- mutual matches.

Blocked users are excluded from the visible lists.

## 2.21 Presence

Socket.IO authenticates the access JWT cookie during the handshake and independently checks the server-side session and profile completion.

Presence is tab-aware:

- first connected tab marks the user online;
- additional tabs do not duplicate the change;
- closing one of several tabs keeps the user online;
- final tab disconnect marks the user offline and stores last activity.

Stale online flags are reset when the backend process starts.

## 2.22 Real-time text chat

Chat is available only while reciprocal likes exist and neither user is blocked.

Send flow:

```text
submit message
→ validate target and relationship
→ validate trimmed content and 1000-character limit
→ persist message
→ emit message to both user rooms
→ create recipient notification
→ update unread state
```

Opening a conversation marks incoming messages read and emits read receipts. The UI shows delivered/seen state and live presence. Network interruption falls back to API reload and unread counters rather than silently discarding persisted messages.

## 2.23 Notifications

Persisted notification types are:

```text
like, view, message, match, unlike, date
```

The global provider receives Socket.IO events from any protected page. Each popup has its own timer and close button, so several notifications can appear simultaneously. The bell shows unread count and recent history.

Blocks, incomplete profiles, and unlike suppression are checked before a notification row is created.

## 2.24 Audio-only calls

Calls are available only between connected, complete, non-blocked users.

The browser requests:

```ts
navigator.mediaDevices.getUserMedia({ audio: true, video: false })
```

No camera permission, camera track, video element, or video signaling exists.

Call sequence:

```text
caller sends invitation
→ recipient receives global popup
→ recipient accepts or declines
→ microphone permission is requested
→ Socket.IO relays offer, answer, and ICE candidates
→ WebRTC carries peer-to-peer audio
→ either participant can mute or end
```

Calls end on decline, no answer, hang up, participating-tab close, Socket.IO disconnect, relationship loss, block, unlike, microphone failure, or WebRTC failure.

Call state is transient and kept in the single backend worker. Call media is not stored.

## 2.25 Date proposals

Connected users can propose a future date with:

- timezone-aware date and time;
- required location;
- optional note.

Status transitions:

```text
pending → accepted
pending → declined
pending → cancelled
accepted future date → cancelled
```

Only the recipient can accept or decline. Either participant can cancel an allowed pending or future accepted event. Past or terminal events cannot be changed.

Date notifications are persisted and delivered live. Historical proposals remain visible after unlike but become non-actionable. Blocking hides related date records while the block exists.

# 3. HTTP behavior and error contract

Successful API responses use the status appropriate to the operation, commonly `200`, `201`, or `204` where applicable. Controlled failures use real HTTP statuses:

| Status | Meaning in Matcha |
|---|---|
| `400` | Malformed JSON, invalid field, invalid transition, self-action, invalid upload |
| `401` | Missing, invalid, expired, or revoked authentication |
| `403` | Complete-profile or relationship authorization failure, CSRF failure |
| `404` | Missing or deliberately unavailable resource |
| `409` | Duplicate username/email, like, or report |
| `413` | Request or upload exceeds configured size |
| `503` | Required email or OAuth upstream service is unavailable |
| `500` | Unexpected server or PostgreSQL failure; details remain in server logs only |

Every public error response is JSON and does not expose a stack trace.

# 4. Manual and Postman verification

See `MANUAL_AND_POSTMAN_TESTING.md` for:

- complete browser scenarios;
- successful and failed API cases;
- cookie and CSRF behavior;
- two-user chat, notification, call, and date testing;
- upload security tests;
- PostgreSQL integrity checks;
- instructions for importing and using the Postman collection.
