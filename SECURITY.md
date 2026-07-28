# 1. Critical security failures

## 1.1 Secrets are inside the repository

### Current problem

The archive contains:

```text
backend/.env
```

But `backend/.gitignore` contains only:

```text
venv
uploads
```

It does not ignore `.env`. The PostgreSQL password is also written directly in:

```text
backend/docker-compose.yml
```

### How it can fail manually

1. Open the project archive.
2. Open `backend/.env`.
3. Confirm that secrets and API credentials are included.
4. Check `.gitignore`.
5. Confirm that `.env` is not excluded.

### Why this can fail the project

The subject explicitly requires credentials, API keys and environment variables to be stored locally in `.env` and excluded from Git. Publicly stored credentials may result in project failure.

### Required correction

* Ignore `.env`.
* Remove secrets from Git history.
* Rotate all exposed secrets.
* Move the database password out of Compose.
* Keep only placeholders in `.env.example`.

---

## 1.2 Flask debug mode is enabled

### Current problem

`backend/run.py:7` contains:

```python
socketio.run(app, debug=True, host='0.0.0.0', port=5000)
```

### When it can fail

When an exception occurs, development/debug information may be exposed. The server also listens on every network interface.

### Why this matters

The subject forbids unexpected errors, exposed stack traces and security vulnerabilities.

Debug mode must not be used in the defense runtime.

---

## 1.3 OAuth exposes access and refresh tokens in the URL

### Current problem

`backend/app/oauth.py:24` redirects using:

```text
/oauth-callback?token=ACCESS_TOKEN&refreshToken=REFRESH_TOKEN
```

The frontend then reads those values from the URL.

### How it can fail manually

1. Log in with Google or 42.
2. Inspect the callback URL.
3. Check browser history.
4. Observe both credentials in the URL.

### Why this is dangerous

The tokens can leak through:

* browser history;
* logs;
* screenshots;
* copied links;
* analytics;
* referrer information.

OAuth exists as an official bonus, but the current implementation is not secure enough to count as completed.

---

## 1.4 Authentication tokens are readable by JavaScript

### Current problem

`AuthContext.tsx` uses `js-cookie` to store:

```text
token
refreshToken
user
```

JavaScript-created cookies cannot use the `HttpOnly` protection.

### When it can fail

Any successful JavaScript injection could read and send the access and refresh tokens elsewhere.

### Why this matters

The subject explicitly forbids HTML/JavaScript injection vulnerabilities and states that a security breach can result in a score of zero.

---

## 1.5 Logout does not invalidate the token

### Current problem

The frontend logout function only deletes local cookies:

```typescript
logout: () => {
  Cookies.remove('token');
  Cookies.remove('refreshToken');
  Cookies.remove('user');
}
```

It does not call:

```text
POST /api/auth/logout
```

Even the backend logout endpoint does not revoke the JWT.

### How it can fail manually

1. Log in.
2. Copy the access token.
3. Click **Log out**.
4. Use the copied token to request:

```text
GET /api/auth/me
```

5. The token can remain valid.

The access token currently lasts seven days.

### Additional problem

Resetting the password increments `token_version`, but JWT authentication never checks that version. An old JWT can therefore remain usable after a password reset.

### Why this fails

The interface says the user logged out, but the server credential is still valid. That is incomplete logout behavior and a security defect.

---

# 2. Input validation and unhandled-error failures

The subject requires legitimate errors to return appropriate status codes and all forms to have proper validation.

## 2.1 Incorrect input types can cause HTTP 500

Examples:

### Numeric email

Sending:

```json
{
  "username": "john",
  "email": 123,
  "firstName": "John",
  "lastName": "Doe",
  "password": "StrongPassword1!"
}
```

can reach:

```python
re.match(pattern, email)
```

with an integer and cause an exception.

### Numeric password

A numeric or structured password can reach:

```python
len(password)
password.encode(...)
```

and cause an exception.

### Why this fails

Malformed user input should return a controlled `400`, not an internal `500`.

---

## 2.2 Overlong fields are not validated

Database limits include:

```text
username: 50
email: 100
first name: 50
last name: 50
tag name: 50
location name: 100
```

The backend does not consistently validate these lengths before inserting them.

### Manual example

Submit a username longer than 50 characters.

PostgreSQL can raise a length error, and the application returns a database-related `500` instead of a meaningful `400`.

---

## 2.3 Gender and sexual preferences accept arbitrary values

`backend/app/profile.py` directly stores supplied values:

```python
updates['gender'] = data['gender']
updates['sexual_preferences'] = data['sexualPreferences']
```

A direct API request can therefore store values such as:

```json
{
  "gender": "invalid-value",
  "sexualPreferences": "anything"
}
```

This will later break matching logic because browse compatibility requires controlled values.

---

## 2.4 GPS consent validation is incorrect

The route uses:

```python
'gps_consent': bool(gps_consent)
```

In Python:

```python
bool("false") == True
```

### Manual failure

Send:

```json
{
  "gpsConsent": "false",
  "locationName": "Rabat"
}
```

The backend interprets consent as enabled and enters the GPS branch.

---

## 2.5 Invalid coordinates are accepted

Latitude and longitude are converted to floats but are not limited to:

```text
latitude: -90 to 90
longitude: -180 to 180
```

Values such as `999` can be stored.

That will break mandatory proximity calculations.

---

## 2.6 Valid zero coordinates are mishandled

`models.user_to_dict` uses:

```python
if user['latitude'] and user['longitude']
```

A valid coordinate such as longitude `0.0` is considered false.

`calculate_distance` has the same problem:

```python
if not all([lat1, lon1, lat2, lon2]):
    return float('inf')
```

### When it fails

Users located around the Greenwich meridian or equator can be treated as having no usable coordinates or infinite distance.

---

# 3. Registration and authentication defects

The subject requires registration, email verification, login, reset and one-click logout. It also requires rejection of commonly used dictionary passwords regardless of language.

## 3.1 Dictionary-password protection is insufficient

The backend checks only:

```python
[
    'password',
    '123456',
    'qwerty',
    'admin',
    'letmein',
    'welcome'
]
```

It compares exact values only.

### Manual failure

A password such as:

```text
Password1!
```

is accepted even though it is a common password based directly on a dictionary word.

Common passwords from other languages are also accepted.

---

## 3.2 Signup and reset validation disagree

Signup frontend:

```typescript
password: z.string().min(6)
```

Backend and reset frontend:

```text
minimum 8 characters
uppercase
lowercase
number
special character
```

### Manual failure

Enter a six-character password in signup. The frontend accepts the form, but the backend rejects it.

This is inconsistent form validation.

---

## 3.3 Registration can claim success when no verification email was sent

The registration route catches email failures and only prints them:

```python
try:
    send_verification_email(user)
except Exception as e:
    print(...)
```

It still returns HTTP `201` and tells the user to check their inbox.

### Manual failure

1. Use invalid SMTP credentials.
2. Register.
3. The application displays registration success.
4. No verification email arrives.
5. The user cannot log in.

### Why this fails

The subject requires the user to receive a unique verification link.

The same problem exists after changing an email address.

---

## 3.4 OAuth accounts can crash local login

OAuth-created users have:

```text
password_hash = NULL
```

Local login still calls:

```python
models.check_password(password, user['password_hash'])
```

which eventually calls:

```python
password_hash.encode(...)
```

### Manual failure

1. Create an account with Google or 42.
2. Try local username/password login with that account.
3. The backend can return HTTP `500`.

This violates the no-unhandled-errors requirement.

---

## 3.5 Verification resend allows account discovery

`/resend-verification` returns different responses for:

* unknown email;
* verified email;
* unverified email.

An attacker can use those differences to determine whether an account exists.

---

# 4. Profile defects and incomplete behavior

The subject requires gender, sexual preference, biography, reusable tags, up to five pictures, editable identity information, viewers, likers, fame rating and location.

## 4.1 Age cannot be implemented with the current database

There is no:

* birth-date column;
* age field;
* birth-date form;
* age calculation.

### Why this is mandatory

Browsing and research must support:

* sorting by age;
* filtering by age;
* searching by an age range.

That is impossible with the current schema.

A birth date should eventually be stored and age calculated from it.

---

## 4.2 Fame rating has two different formulas

`backend/app/models.py` uses:

```text
likes × 3
views × 0.5
profile-completion bonuses
```

`backend/app/utils.py` uses:

```text
likes × 2
views × 0.5
```

### Manual failure

Calculate fame using both functions for the same account. The results can differ.

### Additional problem

The stored fame rating is recalculated after:

* views;
* likes;
* unlikes.

It is not recalculated after:

* adding a biography;
* changing gender/preferences;
* adding tags;
* adding photos.

Those values contribute to the selected fame formula, so the stored rating becomes stale.

### Why this fails

The subject allows you to define fame rating, but the criteria must be consistent.

---

## 4.3 Visit history is overwritten

The table uses:

```sql
PRIMARY KEY (viewer_id, viewed_id)
```

Repeated views update the existing row rather than creating a new visit.

### Manual failure

1. User A visits User B.
2. Wait.
3. User A visits User B again.
4. Query `user_views`.
5. Only one row exists.

The endpoint also returns viewers without the view timestamp.

### Why this is a defense risk

The subject states that viewing a profile must be recorded in visit history.

Current behavior keeps only the most recent visit for each viewer/profile pair.

---

## 4.4 Exact latitude and longitude are public

The public profile serializer returns:

```json
{
  "location": {
    "name": "...",
    "latitude": 00.000,
    "longitude": 00.000
  }
}
```

### Why this is unsafe

The mandatory application needs neighborhood-level matching. Other users do not need exact coordinates. Exact values should be retained server-side for distance calculations.

---

## 4.5 Manual locations can be accepted without usable coordinates

If geocoding fails, `geocode_location` returns:

```python
(None, None)
```

The route still stores the location name and returns success.

### When it fails

If Nominatim is unavailable or the location cannot be found:

* the profile appears to have a location;
* mandatory proximity matching cannot use it.

---

## 4.6 Photo limits can fail under concurrent requests

The code:

1. counts photos;
2. checks whether the count is below five;
3. inserts the photo in a later query.

These operations are not one transaction and the database has no maximum-photo constraint.

### Manual failure scenario

1. A user has four photos.
2. Two upload requests arrive simultaneously.
3. Both see a count of four.
4. Both insert.
5. The user now has six photos.

That violates the maximum of five pictures.

---

## 4.7 The database does not guarantee one primary photo

There is no unique partial index such as one `is_primary = true` row per user.

Changing primary photo also uses two separate committed updates:

```python
UPDATE photos SET is_primary = false ...
UPDATE photos SET is_primary = true ...
```

If the second operation fails, the profile can have no primary picture.

Concurrent first-photo uploads can also create multiple primary photos.

---

## 4.8 Uploaded filenames can collide

Filename generation uses:

```text
current date/time to the second + original filename
```

Two uploads with the same filename during the same second can use the same path.

That can overwrite an earlier image while multiple database records reference it.

---

## 4.9 Deleting a photo leaves the file on disk

The database row is deleted, but the file itself is not removed from `uploads`.

This creates abandoned files and privacy/storage problems.

---

## 4.10 Tag updates are not atomic

The update process:

1. deletes all existing user tags;
2. creates/finds each new tag;
3. inserts each relationship using separate committed operations.

### Failure example

Send:

```json
{
  "tags": [
    "music",
    "travel",
    "a-tag-longer-than-the-database-limit..."
  ]
}
```

The deletion and earlier inserts may already be committed before the final tag fails. The user can be left with a partial tag list.

---

## 4.11 Profile completion can remain visually incorrect

After adding the final missing:

* photo;
* tag;
* location;

the frontend updates that individual field but does not refresh `isProfileComplete`.

The incomplete-profile warning may remain until reload.

---

# 5. Mandatory browsing is missing

The subject requires suggested profiles selected using compatibility, proximity, common tags and fame rating, with same-area priority and sorting/filtering.

## Current behavior

The `/` route shows a statistics dashboard.

The **Discover people** button points to `/`, which returns the same dashboard.

There is no backend suggested-profile endpoint.

## Missing behavior

* gender compatibility;
* sexual-preference compatibility;
* bisexual matching;
* unspecified preference treated as bisexual;
* mutual compatibility;
* geographic proximity;
* common-tag ranking;
* fame-rating ranking;
* same-area priority;
* sorting by age, location, fame and common tags;
* filtering by age, location, fame and tags;
* blocked-user exclusion;
* incomplete-profile exclusion.

This whole mandatory section is currently unimplemented.

---

# 6. Mandatory advanced search is missing

The navigation links to:

```text
/search
```

but no page or backend endpoint exists.

### Manual failure

Click **Search**. The route returns a Next.js 404.

Missing criteria include:

* age range;
* fame-rating range;
* location;
* one or multiple tags;
* combined criteria;
* result sorting;
* result filtering.

The subject requires these independently from suggested browsing.

---

# 7. Profile-view behavior is incomplete

## 7.1 Public page does not show all available information

The backend returns:

* gender;
* sexual preference.

The public profile page does not display them.

Age is also unavailable.

The subject says the profile should show all available information except email and password.

---

## 7.2 Unlike does not stop future notifications from that user

The subject states that removing a like must prevent further notifications from that user and disable chat.

### Manual failure

1. A and B mutually like each other.
2. A unlikes B.
3. B opens A’s profile.
4. A receives a view notification from B.

There is no notification-suppression rule after unlike.

---

## 7.3 A blocked user can still create an unlike notification

### Manual failure

1. A and B are connected.
2. A blocks B.
3. B directly requests:

```text
DELETE /api/users/A/like
```

4. The unlike route does not check whether the users are blocked.
5. Because their old likes remain, B can generate an unlike notification for A.

This violates the rule that a blocked user must no longer generate notifications.

---

## 7.4 Block cannot yet be applied to search or chat

The direct profile route checks blocks, but mandatory search and chat do not exist.

Therefore, the application cannot yet prove that blocked users:

* disappear from search;
* cannot chat;
* cannot generate message notifications.

---

## 7.5 Online status can become stale

Login immediately sets:

```text
is_online = true
```

before the Socket.IO connection is confirmed.

### Failure scenarios

* WebSocket is blocked and never connects.
* The browser closes before establishing a socket.
* The backend restarts while database rows remain marked online.
* The frontend logout does not call the backend logout route.

The server emits presence events, but public profile components do not subscribe to them. A currently open profile does not update live.

---

## 7.6 Blocking redirects to a missing page

After blocking, the frontend executes:

```typescript
router.push('/browse')
```

The unavailable-profile page also links to `/browse`.

No `/browse` route exists.

### Manual failure

Block a user and arrive at a 404 page.

---

# 8. Mandatory chat is missing

The database contains a `messages` table and unused model functions, but there are no:

* chat API routes;
* conversation list;
* connection authorization;
* Socket.IO message events;
* messages page;
* conversation interface;
* read/unread handling;
* message synchronization;
* block/unlike chat enforcement.

The navigation links to `/messages`, but that route does not exist.

The subject requires connected users to chat in real time with a maximum ten-second delay. 

---

# 9. Notifications are incomplete

## Current coverage

| Required event         | Current-L204 state |
| ---------------------- | ------------------ |
| Received like          | Implemented        |
| Profile viewed         | Implemented        |
| Message received       | Missing            |
| Mutual like            | Implemented        |
| Connected user unliked | Implemented        |

The five events are mandatL202

## 9.1 No message notifications

The frontend recognizes the string `"message"`, but no message route creates such a notification.

---

## 9.2 Ten-second delivery is not guaranteed

The Socket.IO client forces:

```typescript
transports: ['websocket']
```

There is no HTTP polling fallback.

The backend has an `/unread-count` endpoint intended for polling, but the frontend never uses it.

### Manual failure

1. Block WebSocket traffic while keeping HTTP functional.
2. Trigger a view or like from another user.
3. The recipient may receive nothing until manually refreshing/opening the notification list.

That can exceed the maximum delay of ten seconds.

---

## 9.3 Notification suppression is not centralized

`create_notification` always inserts and emits. It does not check:

* block status;
* unlike suppression;
* whether the relationship still permits the event.

This is the root cause of several block/unlike failures and will affect future message notifications.

---

## 9.4 Read state can become incorrect

The frontend marks notifications read optimistically before confirming the HTTP request.

It also does not treat a non-2xx `fetch` response as an error.

### Manual failure

1. Disconnect the backend.
2. Click **Mark all read**.
3. The frontend shows zero unread.
4. Reconnect and reload.
5. The database still reports unread notifications.

The subject requires a reliable unread indicator from any pL210

---

# 10. Required evaluation data is missing

The database must contain at least 500 distinct profi-L85

There is no profile generator or seed process.

The future generator must create useful combinations of:

* ages;
* genders;
* sexual preferences;
* locations;
* tags;
* fame ratings;
* photos.

Otherwise browsing and search cannot be demonstrated properly.

---

# 11. Browser and mobile status

The source includes responsive styling and a header/main/footer layout, so there is a foundation.

However, latest Chrome, latest Firefox and small-screen behavior have not been verified.

Static areas requiring manual verification include:

* fixed-width notification dropdown;
* two-column fields on narrow screens;
* image controls;
* future browse filters;
* future search forms;
* chat;
* map;
* audio/video calls.

This is an **unverified acceptance criterion**, not a confirmed static failure.

---

# 12. Official bonus audit

The subject lists five official bonus categories. Bonuses are evaluated only after all mandatory functionality is perfL233

## OAuth strategies — partially implemented

Google and 42 OAuth exist, but completion is blocked by:

* JWTs in URL parameters;
* JavaScript-readable tokens;
* no provider-request timeouts;
* malformed provider responses potentially causing exceptions;
* OAuth configuration required at module import;
* one provider overwriting another;
* no unique OAuth identity constraint;
* OAuth accounts crashing local password login.

## Drag-and-drop gallery and image editing — missing

Current upload is basic mandatory photo management.

Missing bonus behavior:

* drag and drop;
* crop;
* rotation;
* filters.

## Interactive map — missing

No map, markers or privacy-safe map behavior exists.

## Audio/video chat — missing

No WebRTC, signaling, call invitation, media permission or call interface exists.

## Date/event scheduling — missing

No date proposal, acceptance, decline, cancellation, timezone or event-notification system exists.

---

# Final classification

## Mandatory features completely missing

* 500-profile seed;
* age support;
* suggested browsing;
* advanced research/search;
* real-time text chat;
* message notifications.

## Implemented but not handled correctly

* password validation;
* verification delivery;
* logout/session invalidation;
* profile visit history;
* fame rating;
* location;
* photo limits and primary photo;
* tag updates;
* unlike notification suppression;
* block notification suppression;
* online presence;
* ten-second notification reliability;
* form/error validation.

## Security blockers

* `.env` inside repository;
* hardcoded credentials;
* debug mode;
* OAuth tokens in URLs;
* JavaScript-readable tokens;
* reusable JWTs after logout/reset;
* HTML injection in email;
* exact coordinates exposed publicly;
* upload race/resource risks.

## Official bonus status

* OAuth: partial and insecure.
* Gallery editing: missing.
* Interactive map: missing.
* Audio/video: missing.
* Date scheduling: missing.