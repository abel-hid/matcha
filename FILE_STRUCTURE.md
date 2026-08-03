# Matcha File Structure

The project contains only the files used by the supported local Docker workflow, the application source, the official subject, documentation, and Postman assets. Runtime secrets, automated tests, generated dependencies, uploaded photos, database files, caches, logs, and editor metadata are excluded.

```text
matcha/
├── .gitignore
├── README.md
├── README_TECHNICAL.md
├── MANUAL_AND_POSTMAN_TESTING.md
├── FILE_STRUCTURE.md
├── SUBJECT.MD
├── docker-compose.yml
├── start.sh
├── stop.sh
├── postman/
│   ├── Matcha.postman_collection.json
│   └── Matcha.local.postman_environment.json
├── backend/
│   ├── .dockerignore
│   ├── .env.example
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── schema.sql
│   ├── initdb.py
│   ├── seed.py
│   ├── run.py
│   └── app/
│       ├── __init__.py
│       ├── auth.py
│       ├── config.py
│       ├── dates.py
│       ├── db.py
│       ├── discover.py
│       ├── extensions.py
│       ├── messages.py
│       ├── models.py
│       ├── notifications.py
│       ├── oauth.py
│       ├── profile.py
│       ├── profile_access.py
│       ├── request_helpers.py
│       ├── sockets.py
│       ├── users.py
│       ├── utils.py
│       └── validation.py
└── frontend/
    └── my-app/
        ├── .dockerignore
        ├── Dockerfile
        ├── package.json
        ├── package-lock.json
        ├── tsconfig.json
        ├── next.config.ts
        ├── eslint.config.mjs
        ├── postcss.config.mjs
        ├── public/
        │   └── 42_Logo.svg
        └── app/
            ├── globals.css
            ├── layout.tsx
            ├── providers.tsx
            ├── lib/
            │   ├── apiError.ts
            │   └── authValidation.ts
            ├── services/
            │   └── api.ts
            ├── types/
            │   └── index.ts
            ├── context/
            │   └── AuthContext.tsx
            ├── (auth)/
            │   ├── layout.tsx
            │   ├── login/page.tsx
            │   ├── signup/page.tsx
            │   ├── verify/page.tsx
            │   ├── forgot-password/page.tsx
            │   ├── reset-password/page.tsx
            │   └── oauth-callback/page.tsx
            ├── (dashboard)/
            │   ├── layout.tsx
            │   ├── page.tsx
            │   ├── DiscoverPage.tsx
            │   ├── map/page.tsx
            │   ├── messages/page.tsx
            │   ├── dates/page.tsx
            │   ├── profile/page.tsx
            │   ├── profile/activity/page.tsx
            │   ├── settings/blocked/page.tsx
            │   └── users/[username]/page.tsx
            └── components/
                ├── AudioCallProvider.tsx
                ├── NotificationBell.tsx
                ├── PhotoEditor.tsx
                ├── ProfileActivity.tsx
                ├── ProfileForm.tsx
                ├── ProfileLocation.tsx
                ├── ProfilePhotos.tsx
                ├── ProfileTagsInput.tsx
                ├── UserCard.tsx
                ├── UserMap.tsx
                └── auth/
                    ├── AuthShowcase.tsx
                    ├── ForgotPasswordForm.tsx
                    ├── LoginForm.tsx
                    ├── ResetPasswordForm.tsx
                    ├── SignupForm.tsx
                    └── VerifyEmailForm.tsx
```

# Root files

## `.gitignore`

Excludes private environment files, dependencies, build output, caches, uploads, logs, temporary patches, archives, and operating-system/editor files for the complete repository.

## `docker-compose.yml`

Defines the five local services:

- `db`: private PostgreSQL service with a persistent named volume;
- `schema`: one-shot schema application using the backend image;
- `seed`: one-shot creation of exactly 500 evaluation profiles;
- `backend`: Flask, Socket.IO, mail, OAuth, uploads, and PostgreSQL access;
- `frontend`: compiled Next.js application bound to localhost.

The database is not published to the host. The browser-facing services are bound only to `127.0.0.1` on ports 5000 and 3000.

## `start.sh`

Validates Docker and the private environment file, builds the two application images, starts PostgreSQL, applies the schema, regenerates the deterministic seed accounts, starts the backend and frontend, waits for health checks, and prints the local URLs and seed credentials.

## `stop.sh`

Stops the Compose services while preserving the PostgreSQL and upload named volumes.

## Documentation

- `README.md`: setup and complete user-facing flow;
- `README_TECHNICAL.md`: architecture and implementation decisions;
- `MANUAL_AND_POSTMAN_TESTING.md`: successful and failed manual cases;
- `FILE_STRUCTURE.md`: source organization;
- `SUBJECT.MD`: official Matcha 6.1 requirements.

## `postman/`

Contains one importable collection and one local environment template. The environment contains local URLs and variable placeholders but no credentials.

# Backend files

## `.env.example`

Documents only values that the user must supply or may configure locally: application secrets, PostgreSQL credentials, mail settings, the location provider, and optional Google/42 OAuth credentials. The real `backend/.env` is ignored and must remain private.

## `.dockerignore`

Prevents secrets, uploads, Python caches, and local metadata from entering backend image build contexts.

## `Dockerfile`

Builds the Python 3.11 image, installs the pinned runtime requirements, copies the backend source, creates the upload directory, and starts `python run.py`.

## `run.py`

Creates the Flask application, resets stale online flags left by a previous stop, prints the backend address, and starts Flask-SocketIO in the supported single-process threading mode.

## `app/__init__.py`

Creates the Flask application, initializes the connection pool and extensions, registers all blueprints, exposes health and upload routes, adds security headers, and normalizes API errors.

## `app/config.py`

Defines the fixed local runtime settings and validates private secrets, database access, mail configuration, and paired optional OAuth credentials.

## `app/db.py`

Owns the thread-safe PostgreSQL pool and the shared `query_one`, `query_all`, `execute`, and transactional connection helpers. All values are passed separately from SQL text.

## `app/extensions.py`

Creates the JWT, mail, and CORS extension objects and validates each JWT against its server-side session and token version.

## `app/request_helpers.py`

Contains the repeated authenticated-user lookup and JSON-object parsing used by route modules.

## `app/profile_access.py`

Provides the reusable complete-profile decorator that blocks dating features until all mandatory profile data exists.

## `app/auth.py`

Implements registration, verification, resend, login, bootstrap, refresh, logout, forgotten-password, password-reset, and reset-token validation routes.

## `app/oauth.py`

Implements provider configuration, state validation, provider HTTP exchanges, account linking or creation, and the Google and 42 routes.

## `app/profile.py`

Implements the private profile editor, email change, tags, photo upload/edit/delete/primary selection, GPS/manual location, viewers, likes, and activity routes.

## `app/users.py`

Implements public profile lookup, idempotent visits, likes, matches, unlike, block, unblock, and one-click fake-account reports.

## `app/discover.py`

Parses and validates suggestion/search filters, sorting, pagination, and map requests before calling the domain query layer.

## `app/messages.py`

Implements conversation lists, unread counts, paginated history, connected-user message sending, and read receipts.

## `app/notifications.py`

Implements persisted notification history, unread counts, one-item read, and read-all operations.

## `app/dates.py`

Implements connected-user date proposals, listing, accept/decline transitions, cancellation, notifications, and Socket.IO updates.

## `app/sockets.py`

Maintains authenticated presence and audio-call signaling for the single local backend process. It validates connection state, match state, blocks, call participation, SDP signals, ICE candidates, timeout, disconnect, unlike, and block termination.

## `app/validation.py`

Contains backend normalization and validation for account fields, passwords, profile fields, search values, and controlled request limits.

## `app/utils.py`

Contains signed verification/reset tokens, mail delivery, secure image decoding and re-encoding, safe file deletion, and location-provider requests.

## `app/models.py`

Contains the manually written parameterized SQL and serializers, grouped by domain: users, sessions, tags, photos, relationships, discovery, messages, reports, notifications, dates, and OAuth identities.

## `schema.sql`

Defines the complete idempotent relational schema, constraints, indexes, reusable interests, message/notification/date tables, and the single-primary-photo rule.

## `seed.py`

Creates exactly 500 deterministic, verified, complete profiles and generated photos. It replaces only `seed_` accounts and preserves manually registered accounts.

## `initdb.py`

Applies `schema.sql` normally and provides the explicit `--reset` path for destructive local database recreation.

# Frontend files

## `.dockerignore`

Excludes environment files, dependencies, Next.js output, coverage, logs, and local metadata from the frontend build context.

## `Dockerfile`

Installs locked dependencies, compiles the Next.js application, and runs the standalone output as an unprivileged user. `NODE_ENV=production` is required by the compiled Next.js runtime even though the application is used only on localhost.

## `app/layout.tsx` and `app/providers.tsx`

Define root metadata and mount authentication, global notifications, and global audio-call state once for the application.

## `app/(auth)/`

Contains the public authentication pages and shared layout for login, signup, verification, password recovery/reset, and OAuth callback handling.

## `app/(dashboard)/`

Contains the protected pages for discovery/search, map, chat, date proposals, profile editing, activity, blocked users, and public profiles. The shared layout applies authenticated and complete-profile navigation rules.

## `app/services/api.ts`

Defines the Axios client, CSRF handling, one-time refresh retry, and typed service methods for every REST domain.

## `app/context/AuthContext.tsx`

Performs session bootstrap and owns login, logout, OAuth completion, current-user state, and profile updates.

## `app/lib/apiError.ts`

Safely extracts backend messages, reasons, HTTP statuses, and browser/library codes from unknown failures.

## `app/lib/authValidation.ts`

Defines the client-side schemas and user-friendly validation feedback for authentication forms. Backend validation remains authoritative.

## `app/types/index.ts`

Contains the shared domain interfaces used by pages, components, and API clients.

## `app/components/NotificationBell.tsx`

Loads persisted notifications and unread state, consumes live Socket.IO events, and displays independently dismissible notification popups.

## `app/components/AudioCallProvider.tsx`

Implements microphone-only WebRTC, invitation/accept/decline UI, signaling, mute, duration, timeout, hang-up, and cleanup. It explicitly requests `video: false`.

## Profile and discovery components

- `ProfileForm.tsx`: profile fields and completion state;
- `ProfileTagsInput.tsx`: fixed reusable interests;
- `ProfilePhotos.tsx`: photo CRUD and primary selection;
- `PhotoEditor.tsx`: crop, rotation, and controlled filters;
- `ProfileLocation.tsx`: consent, GPS diagnostics, reverse geocoding, and manual fallback;
- `ProfileActivity.tsx`: views, outgoing likes, incoming likes, and matches;
- `UserCard.tsx`: reusable profile summary card;
- `UserMap.tsx`: interactive privacy-rounded map and marker popup behavior.

## Authentication components

The `components/auth/` directory keeps each form separate while sharing the same visual frame and validation/error helpers.
