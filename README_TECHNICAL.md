# Matcha Technical Architecture

This document explains how the final project works from the system architecture down to route helpers, SQL transactions, frontend contexts, Socket.IO events, and WebRTC signaling.

# 1. Architectural overview

```text
Chrome / Firefox
    │
    ├── HTTP pages and JavaScript ───────────────► Next.js :3000
    │
    ├── JSON, multipart, cookies ────────────────► Flask API :5000
    │                                                │
    ├── Socket.IO / WebSocket ──────────────────────┤
    │                                                │
    └── WebRTC audio ◄──────── peer-to-peer ───────►│ other browser
                                                     │
                                                     ▼
                                              PostgreSQL :5432
                                                     │
                                                     ▼
                                             named upload volume
```

The application deliberately separates responsibilities:

- **Next.js** renders pages, validates user input for usability, maintains browser state, and presents controlled errors.
- **Flask** is the authority for authentication, authorization, validation, business rules, and serialized API responses.
- **PostgreSQL** stores durable state and enforces relational integrity.
- **Socket.IO** delivers presence, messages, notifications, relationship changes, date changes, and call signaling.
- **WebRTC** carries audio directly between browsers after signaling.
- **Docker Compose** creates the repeatable local runtime used for evaluation.

# 2. Runtime services

## 2.1 PostgreSQL service

The `db` service uses PostgreSQL 16 and stores data in the named volume `backend_matcha_pg_data`. It is marked healthy only after `pg_isready` succeeds.

The database has no host port. Backend services reach it only through the internal Compose hostname `db`; manual inspection uses `docker compose exec db ...`.

## 2.2 Schema service

The `schema` service is a short-lived backend image running `python initdb.py`. It reads `backend/schema.sql` and applies idempotent `CREATE TABLE IF NOT EXISTS`, index, and constraint statements.

The project intentionally uses one canonical schema file rather than an ORM or migration framework. `initdb.py --reset` is the only destructive path and must be invoked explicitly.

## 2.3 Seed service

The `seed` service is another short-lived backend image. It always creates exactly 500 deterministic profiles named `seed_001` through `seed_500`.

It deletes only users whose usernames begin with `seed_`, preserving manually registered accounts. Photo files are generated in a temporary directory, database rows are inserted in a transaction, and successful files are moved into the persistent upload volume.

## 2.4 Backend service

The backend container runs `python run.py`. Startup resets stale online flags, creates the Flask application, and starts Flask-SocketIO on port 5000.

The supported local setup uses one backend process because presence connection sets and active audio-call state are stored in memory. Flask-SocketIO runs in `threading` mode and uses `simple-websocket` for WebSocket transport. PostgreSQL uses `ThreadedConnectionPool`, so simultaneous request and Socket.IO threads borrow separate database connections safely.

## 2.5 Frontend service

The Next.js Dockerfile has three stages:

1. `dependencies` runs `npm ci` from the lockfile;
2. `builder` runs `next build` with public API, Socket.IO, map, and STUN settings;
3. `runner` copies only standalone runtime files and executes `server.js` as an unprivileged `nextjs` user.

`output: 'standalone'` keeps the final runtime image smaller and independent of the source tree and full `node_modules` directory.

# 3. Backend source organization

```text
backend/app/
├── __init__.py          application factory and normalized errors
├── config.py            environment parsing and startup validation
├── db.py                pooled parameterized SQL primitives
├── extensions.py        JWT, mail, and CORS extension objects
├── request_helpers.py   current-user and JSON-body helpers
├── profile_access.py    complete-profile route guard
├── auth.py              local authentication and sessions
├── oauth.py             Google and 42 OAuth
├── profile.py           private profile, tags, photos, location, activity
├── users.py             public profiles and social actions
├── discover.py          browse, search, filters, sorting, map data
├── messages.py          conversations, messages, unread state
├── notifications.py     notification history and read state
├── dates.py             date proposals and transitions
├── sockets.py           presence, relationship events, and call signaling
├── validation.py        normalized field validation
├── utils.py             tokens, email, images, and geocoding
└── models.py            domain SQL and response serializers
```

## 3.1 Application factory

`create_app()` performs startup in a predictable order:

```text
validate environment
→ create Flask application
→ initialize PostgreSQL pool
→ initialize JWT, mail, CORS, and Socket.IO
→ register blueprints
→ register health and upload routes
→ register security headers
→ register normalized error handlers
```

The factory accepts a configuration class, which preserves testability and makes settings explicit.

## 3.2 Configuration

Docker Compose reads the private `backend/.env` file and passes only the required values into the containers. Local addresses, cookie mode, token lifetimes, database-pool sizes, and service ports are fixed in source so the evaluation setup has one predictable configuration.

Startup validation checks:

- application and JWT secrets;
- the Compose-provided database URL;
- mail server and sender settings;
- paired mail username/password values;
- paired OAuth client ID and secret values;
- replacement placeholder secrets.

Cookie configuration is centralized:

- JWTs are accepted only from cookies;
- access and refresh cookies are `HttpOnly`;
- CSRF protection is enabled;
- access and refresh paths are separated;
- `SameSite=Lax` reduces cross-site request risk;
- cookies are configured for the supported local HTTP addresses.

## 3.3 Database access layer

`db.py` exposes three query primitives:

```python
query_one(sql, params)
query_all(sql, params)
execute(sql, params, returning=False)
```

Every caller supplies SQL separately from its parameter tuple. Values are never interpolated into SQL strings. The few dynamic fragments used in discovery are selected from controlled allow-lists before SQL construction.

`get_conn()` is a context manager:

```text
borrow connection
→ execute work
→ commit on success
→ rollback on exception
→ always return connection to pool
```

Domain operations that require several dependent statements use `get_conn()` directly and one cursor, preserving atomicity.

# 4. Database model

## 4.1 `users`

Stores identity, protected password hash, profile fields, location, fame, verification, presence, timestamps, and `token_version`.

Important constraints:

- unique username and email;
- allowed gender values;
- one to three allowed sexual-preference values;
- fame between 0 and 100;
- coordinate ranges;
- latitude and longitude are both null or both present;
- non-negative token version.

Orientation defaults to all supported genders, implementing the subject’s default-bisexual rule until edited.

## 4.2 `auth_sessions`

Each local or OAuth login creates a UUID session row. The JWT contains its session ID. Authentication is valid only when:

```text
session exists
AND session belongs to JWT user
AND revoked_at is null
AND expires_at is in the future
AND users.token_version equals JWT version
```

This makes logout and password-reset revocation immediate rather than waiting for JWT expiration.

## 4.3 `oauth_identities`

Stores provider, provider user ID, provider email, and local user ID.

Two unique constraints prevent:

- one provider identity from belonging to multiple local users;
- one local user from holding two identities for the same provider.

## 4.4 `tags` and `user_tags`

`tags` contains the fixed reusable catalogue. `user_tags` is a many-to-many join table with a composite primary key.

Tag replacement validates all IDs first, then deletes and reinserts within one transaction.

## 4.5 `photos`

Stores random safe filenames, primary state, and display position. Position is bounded from zero to four. A partial unique index permits only one `is_primary = true` row per user.

The application uses a PostgreSQL advisory transaction lock per user when changing photo state. This prevents concurrent uploads, deletes, and primary changes from bypassing the five-photo and one-primary rules.

## 4.6 Social graph tables

`user_likes` stores directional likes. A match is derived from two rows in opposite directions.

`user_blocks` stores the blocker direction, while access queries check both directions.

`notification_suppressions` records the mandatory rule that a connected unlike stops future notifications from the disconnected person until the user likes them again.

`user_views` stores history rather than a single pair row. `visit_id` provides idempotency for one browser visit.

`reports` allows one `fake_account` report per reporter/target pair.

## 4.7 Messages and notifications

`messages` stores sender, receiver, content, read state, and creation time. Relationship state is checked when reading, sending, or marking a conversation; old rows are not deleted after unlike.

`notifications` stores the event type, optional source user, content, read state, and creation time. Socket.IO delivery supplements persistence rather than replacing it.

## 4.8 Date events

`date_events` stores proposer, recipient, UTC timestamp, location, note, status, and timestamps. Status is limited to `pending`, `accepted`, `declined`, or `cancelled`.

Action permissions are derived at serialization time from the viewing participant, current status, time, match state, and block state.

# 5. Authentication design

## 5.1 Registration password handling

`validation.py` validates password structure, maximum bcrypt byte length, account-detail similarity, and zxcvbn strength. The backend is authoritative even when the frontend already displayed the same rules.

`models.hash_password()` uses bcrypt with a random salt. `check_password()` catches malformed stored hashes rather than producing an unhandled error.

## 5.2 Verification and reset tokens

`utils.py` uses `itsdangerous` serializers with separate salts for verification and reset purposes. Tokens are signed and time-limited.

A reset token also includes the current `token_version`. After a successful reset, the account version increments. Reuse of an old token therefore fails even if its signature and expiry remain valid.

## 5.3 Cookies and CSRF

The browser never receives JWT text through JSON or a URL. Flask sets JWT cookies. JavaScript can read only the separate CSRF cookies.

For an unsafe request, the Axios interceptor selects:

```text
csrf_access_token   normal protected POST/PUT/PATCH/DELETE
csrf_refresh_token  refresh and bootstrap requests
```

It sends the value in `X-CSRF-TOKEN`. Flask-JWT-Extended requires the header and cookie value to agree.

## 5.4 Refresh retry

The frontend retries an eligible request once after a `401` or `422`. `_retry` prevents loops. Authentication endpoints are excluded. Refresh failure clears local CSRF hints and returns control to the UI.

## 5.5 OAuth

Provider state is stored in an `HttpOnly`, `SameSite=Lax` Flask session cookie. Callback state is consumed once and checked with constant-time comparison.

Provider HTTP requests have bounded timeouts and normalized transport/JSON errors. The provider access token is used only server-side for the immediate profile request and is not stored in the browser URL.

# 6. Validation and error handling

Every form has client validation for feedback and independent backend validation for security.

The backend normalizes:

- username and email;
- first and last name whitespace;
- birth date and adult age;
- gender and preferences;
- biography and location lengths;
- coordinates;
- tag arrays;
- message and date text;
- pagination, sorting, and search parameters.

The application factory registers JSON errors for standard HTTP failures. Database and unexpected errors are logged with stack traces inside the backend container but return only stable public messages.

Security headers are applied to API responses and frontend pages:

- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: DENY`;
- strict referrer policy;
- permissions policy disabling camera and allowing microphone/geolocation only for self.

# 7. Profile completion

`models.missing_profile_fields()` is the single backend calculation for mandatory profile state. `profile_access.complete_profile_required` uses it before dating features.

The frontend layout provides a second usability guard, but it is not the security boundary. Direct API calls from an incomplete account still receive `403 PROFILE_INCOMPLETE`.

Public-profile SQL and discovery SQL independently require all completion fields, preventing an incomplete account from becoming visible due to a frontend mistake.

# 8. Photo processing

`utils.save_image()` does not trust filename extensions or browser MIME declarations.

The controlled process is:

1. enforce upload byte limit;
2. read into memory with a bounded request size;
3. decode through Pillow;
4. verify JPEG or PNG decoded format;
5. reject excessive pixel or dimension counts;
6. normalize orientation;
7. convert to RGB or RGBA as appropriate;
8. create a bounded output image;
9. re-encode to a known format;
10. save under a UUID filename inside the upload directory.

Deletion resolves and checks the path against the configured upload root before unlinking.

The frontend editor performs only preview transformations. Server re-encoding remains mandatory because client processing is not trusted.

# 9. Location and map privacy

The owner’s private profile serializer may include exact coordinates. Public profile serializers include only a location name. Map serializers round coordinates to two decimal places.

Distance ranking uses the haversine formula directly in PostgreSQL. The SQL clamps floating-point input to valid trigonometric bounds.

Manual geocoding uses Nominatim through a configured URL, user agent, and timeout. Provider failures are handled without making valid stored coordinates unusable.

The custom map component implements Web Mercator projection, inverse projection, panning, zooming, marker positioning, popup selection, outside-click closing, and responsive layout without a heavy map dependency.

# 10. Discovery and research SQL

`models.discover_users()` uses two controlled CTEs:

- `current_profile` loads the viewing user’s gender, preferences, location, and identifier;
- `candidate_profiles` applies mandatory profile visibility and calculates age, shared tags, same-area state, and distance.

Compatibility requires both directions:

```text
candidate.gender is in current_user.sexual_preferences
AND current_user.gender is in candidate.sexual_preferences
```

Dynamic ordering is not taken directly from the request. The route maps accepted values to predefined SQL fragments. Numeric and tag filters remain parameters.

Suggested ordering combines several criteria instead of relying on a single score, keeping the subject logic easy to defend.

# 11. Social actions

## 11.1 Visit

The frontend keeps one visit UUID for the target during a page session. PostgreSQL’s unique `(viewer_id, visit_id)` rule makes repeated rendering idempotent. A new real visit creates a new UUID.

## 11.2 Like and match

`like_user()` inserts with `ON CONFLICT DO NOTHING`. The route distinguishes duplicate likes and then checks the reverse row.

A new match emits:

- persisted match notification to each user;
- Socket.IO notification event;
- conversation-status event enabling chat in open tabs.

## 11.3 Unlike

Before deleting, the model records whether the pair was connected. A connected unlike inserts notification suppression for the user performing the unlike.

The route emits the mandatory unlike notification before suppression affects later events, disables the conversation, and terminates calls.

## 11.4 Block

The block and deletion of both likes occur in one transaction. This prevents a partial state where the block exists but the match still exists.

Every visibility, message, date, notification, and call path checks blocks independently. Security does not rely on a profile disappearing from the UI.

# 12. Messaging

Conversation contacts are assembled with a SQL CTE and lateral subquery. Each row includes:

- user profile summary;
- current `can_message` state;
- latest message;
- unread count.

Message creation checks completion, target visibility, reciprocal likes, and content length before insert.

After insert:

```text
persist message
→ serialize message
→ emit `message` to sender and receiver rooms
→ persist recipient notification
→ emit recipient notification
```

Read marking returns affected message IDs. The route emits `message_read` to both rooms so the sender can show Seen without polling.

# 13. Notifications

Notification creation is centralized in `models.create_notification()`.

Before insert it checks:

- recipient profile completeness;
- source profile completeness;
- block in either direction;
- unlike notification suppression.

After insert it emits the serialized record to `user:<id>`.

The frontend `NotificationProvider` maintains the history and unread count. Toasts are stored independently, each with its own timeout and close action.

# 14. Socket.IO presence

The Socket.IO handshake reads the access JWT from its `HttpOnly` cookie. `decode_token()` is followed by the same server-side session and profile-completion checks used by HTTP routes.

Connection maps are protected by a lock:

```text
user_id     → set of socket IDs
session_id  → set of socket IDs
socket ID   → user ID and session ID
```

This supports multiple tabs and targeted disconnect after logout or password reset.

# 15. Audio-call implementation

## 15.1 Server state

The backend keeps:

```text
call_id → caller, recipient, state, owner socket IDs
user_id → active call_id
```

A lock protects both maps. This prevents two simultaneous calls for the same user and avoids stale state during disconnect races.

## 15.2 Authorization

Every call start and signaling action verifies:

- authenticated socket;
- valid bounded call ID;
- valid target;
- complete profiles;
- reciprocal likes;
- no block;
- participant ownership;
- bounded SDP or ICE payload.

## 15.3 Signaling

Socket.IO events:

```text
client → server: call_start, call_accept, call_decline, call_signal, call_end
server → client: call_incoming, call_accepted, call_declined, call_signal, call_ended
```

The backend does not inspect or store audio. It relays only SDP and ICE data after validation.

## 15.4 Browser media

`AudioCallProvider` requests `{ audio: true, video: false }`, creates one `RTCPeerConnection`, adds the microphone track, and attaches the remote stream to an audio element.

It handles offer collision, ICE arrival timing, ringing timeout, mute state, call duration, tab closure, socket reconnect/disconnect, media cleanup, and peer-connection failure.

# 16. Date scheduling

The REST routes own durable date state. Socket.IO only tells open pages to reload or merge the updated event.

Creation requires a future timezone-aware timestamp. The browser converts `datetime-local` to UTC ISO before sending it. PostgreSQL stores `TIMESTAMPTZ`, and serializers return UTC ISO values.

The model calculates action flags relative to the viewer:

- `canRespond` only for recipient on a pending event;
- `canCancel` only for a participant on pending or accepted future events;
- relationship and block state can remove all actions.

# 17. Frontend architecture

```text
app/
├── layout.tsx                    root metadata and providers
├── providers.tsx                 notification and audio providers
├── (auth)/                       public authentication route group
├── (dashboard)/                  protected complete-profile route group
├── components/                   reusable feature components
├── context/AuthContext.tsx       authentication bootstrap and actions
├── services/api.ts               Axios, CSRF, refresh, domain API clients
├── lib/apiError.ts               type-safe controlled error extraction
├── types/index.ts                shared response and state types
└── lib/authValidation.ts         registration/reset feedback schemas
```

## 17.1 Auth context

`AuthProvider` owns the authenticated user and loading state. It bootstraps once, exposes login/logout, and updates the user after profile changes.

The context does not store JWTs. Browser authentication comes entirely from cookies.

## 17.2 Protected layout

The dashboard layout:

- routes unauthenticated users to login;
- routes incomplete users to profile completion;
- provides responsive desktop/mobile navigation;
- renders notification access globally;
- renders semantic header, main, and footer sections.

The backend remains authoritative if a user bypasses the layout.

## 17.3 API service

`services/api.ts` centralizes:

- base URL;
- cookie credentials;
- CSRF selection;
- one-time refresh retry;
- typed payload shapes;
- domain service objects.

Components do not duplicate cookie logic.

`lib/apiError.ts` extracts controlled backend messages, reasons, HTTP statuses, and browser/library error codes from `unknown` failures. Components therefore avoid `any` in catch paths while still presenting useful API errors.

## 17.4 Real-time providers

Notification and audio providers are mounted once in `providers.tsx`, outside individual pages. This is why an incoming notification or call can appear from every protected route.

# 18. Security model

The main controls are layered:

| Threat | Control |
|---|---|
| Plain-text password | bcrypt hashing |
| Weak password | backend zxcvbn and account-detail rules |
| SQL injection | parameterized psycopg2 queries and controlled sort allow-lists |
| JWT theft through JavaScript | `HttpOnly` cookies |
| Cross-site unsafe request | CSRF cookie/header comparison and SameSite cookies |
| Stale JWT after logout | database session revocation |
| Stale JWT after reset | session revocation plus token version increment |
| OAuth login CSRF | random one-use expiring state |
| OAuth token leak | provider exchange only on backend; no JWT URL parameters |
| Malicious upload | byte, decode, format, pixel, dimension, path, and re-encoding checks |
| XSS through API data | React escaping and no raw HTML rendering |
| Broken access control | backend completion, relationship, ownership, and block checks |
| Exact location exposure | private serializer and rounded map coordinates |
| Clickjacking | `X-Frame-Options: DENY` |
| MIME confusion | `X-Content-Type-Options: nosniff` |
| Camera access | permissions policy and audio-only media request |
| Secret commit | root/backend ignores and example-only environment file |
