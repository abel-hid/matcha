# Matcha Manual and Postman Verification Guide

This document is the complete manual-verification procedure for the final Matcha project. It covers normal behavior, controlled failures, authorization boundaries, browser-only real-time behavior, REST requests, and database evidence.

The delivery archive intentionally contains no automated test files. The procedures below are therefore the permanent human-readable acceptance suite for project evaluation and defense.

# 1. Verification principles

A case passes only when all of the following are true:

1. The visible behavior matches the expected result.
2. The HTTP status is appropriate to the result.
3. The response body is controlled JSON for API errors.
4. No Flask traceback is returned to the browser.
5. The page remains usable after a failed request.
6. Chrome or Firefox shows no unexpected JavaScript error in the Console.
7. The backend log contains no unexpected exception for a handled `4xx` case.
8. A blocked, incomplete, disconnected, or unauthorized user cannot bypass the rule by calling the API directly.

Expected client errors such as `400`, `401`, `403`, `404`, `409`, and `413` are valid results when the test intentionally creates that condition. A hidden `500`, a broken page, or a leaked stack trace is not valid.

# 2. Test environment

## 2.1 Required tools

Use:

- Docker Engine or Docker Desktop;
- Docker Compose v2;
- Chrome or Firefox;
- an incognito/private browser window for the second account;
- Postman Desktop for the REST collection;
- a working SMTP mailbox for registration, verification, email change, and password-reset cases;
- optional Google and 42 developer applications for OAuth cases.

Do not run Flask, Next.js, PostgreSQL, schema commands, seed commands, or package managers directly on the host.

## 2.2 Create private configuration

From the project root:

```bash
cp backend/.env.example backend/.env
```

Set real local values for at least:

```dotenv
SECRET_KEY=<long-random-value>
JWT_SECRET_KEY=<different-long-random-value>
POSTGRES_PASSWORD=<local-database-password>
MAIL_SERVER=<smtp-host>
MAIL_DEFAULT_SENDER=<sender-address>
```

When the SMTP server requires authentication:

```dotenv
MAIL_USERNAME=<smtp-user>
MAIL_PASSWORD=<smtp-password>
```

The Docker configuration fixes the browser and API addresses to `http://localhost:3000` and `http://localhost:5000`.

Keep `backend/.env` private. Never upload it, commit it, include it in a screenshot, or copy its secret values into Postman.

## 2.3 Start the complete application

```bash
chmod +x start.sh stop.sh
./start.sh
```

Expected terminal phases:

```text
[1/7] Checking local requirements
[2/7] Building backend and frontend images
[3/7] Starting PostgreSQL
[4/7] Applying the database schema
[5/7] Generating exactly 500 evaluation profiles
[6/7] Starting the API, Socket.IO, and Next.js services
[7/7] Waiting for service health checks
```

Expected final state:

```text
Matcha is ready for local testing.
  Frontend: http://localhost:3000
  Backend:  http://localhost:5000
  Profiles: seed_001 through seed_500
  Password: lhfTYh6452fdHH9@@
```

Check containers:

```bash
docker compose --env-file backend/.env ps
```

Expected service state:

```text
db         running (healthy)
backend    running (healthy)
frontend   running (healthy)
```

The `schema` and `seed` services are one-shot jobs and may show as exited after successful completion.

## 2.4 Baseline health request

```bash
curl -i http://localhost:5000/api/health
```

Expected:

```text
HTTP/1.1 200 OK
```

```json
{
  "status": "ok"
}
```

## 2.5 Browser sessions used throughout this guide

Open two independent sessions so their cookies do not mix:

```text
Browser A / normal window
username: seed_001
password: lhfTYh6452fdHH9@

Browser B / incognito or another browser profile
username: seed_002
password: lhfTYh6452fdHH9@
```

These users are deterministically seeded as a mutual match.

Open developer tools in both sessions:

- **Console**: keep it visible for unexpected JavaScript errors.
- **Network**: preserve requests while testing navigation and session refresh.
- **Application → Cookies**: inspect cookie flags without trying to read HttpOnly values from JavaScript.

# 3. Startup, persistence, and terminal-output cases

## START-01 - First startup

**Steps**

1. Ensure no Matcha containers are running.
2. Run `./start.sh`.
3. Wait for all seven phases.
4. Open the frontend and health endpoint.

**Expected**

- The script exits with code `0`.
- PostgreSQL, backend, and frontend become healthy.
- The frontend opens at `http://localhost:3000`.
- The health endpoint returns `200`.
- Exactly 500 `seed_` accounts exist.

## START-02 - Repeat startup without deleting volumes

**Steps**

1. Register one manual account or make a visible change.
2. Run `./start.sh` again.
3. Log in to the manual account.

**Expected**

- Existing named volumes are reused.
- Manual accounts remain.
- Only accounts beginning with `seed_` are regenerated.
- The upload volume remains available.

## START-03 - Missing environment file

**Steps**

1. Temporarily rename `backend/.env`.
2. Run `./start.sh`.
3. Restore the file.

**Expected**

- Startup stops during phase 1.
- The terminal clearly states that `backend/.env` is missing.
- No secret is printed.

## START-04 - Invalid Compose configuration

**Steps**

1. Temporarily remove a required PostgreSQL variable from `backend/.env`.
2. Run `./start.sh`.
3. Restore the variable.

**Expected**

- Compose validation fails before the services start.
- The error identifies the missing variable.
- Existing volumes are not deleted.

## START-05 - Graceful stop

```bash
./stop.sh
```

**Expected**

- Containers and network stop.
- PostgreSQL and upload named volumes remain.
- Running `./start.sh` restores the previous persistent state except regenerated seed accounts.

# 4. Authentication and account lifecycle

## AUTH-01 - Clean unauthenticated browser load

**Steps**

1. Clear Matcha cookies.
2. Open `/login`.
3. Inspect the Network panel.

**Expected**

- `POST /api/auth/refresh/bootstrap` returns `200`.
- Body contains `authenticated: false`.
- The console does not show an expected `401` error during normal bootstrap.
- Protected dashboard pages redirect to login.

## AUTH-02 - Successful local registration

**Prerequisite**: working SMTP configuration and an inbox you can access.

**Steps**

1. Open `/signup`.
2. Enter a unique username and email.
3. Enter valid first and last names.
4. Enter a strong password that is not based on the account data.
5. Submit.

**Expected**

- Backend returns `201`.
- The account is created as unverified.
- A unique verification email arrives.
- The UI asks the user to verify the email.
- Login is refused until verification.

## AUTH-03 - Registration validation failures

Test each case separately:

- missing JSON field;
- username shorter than 3 characters;
- username containing unsupported characters;
- malformed email;
- empty first or last name;
- name containing digits;
- password shorter than 8 characters;
- password without uppercase, lowercase, number, or supported special character;
- password over the bcrypt 72-byte limit;
- common or guessable password;
- password based on username, email local part, first name, or last name;
- duplicate username;
- duplicate email.

**Expected**

- Invalid values return `400`.
- Existing username or email returns `409`.
- No partial account remains after a verification-email delivery failure.
- Response uses `{ "message": "..." }` and never returns a traceback.

## AUTH-04 - Verification link success

**Steps**

1. Open the link from the verification email.
2. Allow the frontend to call `GET /api/auth/verify/<token>`.

**Expected**

- First use returns `200`.
- The account becomes verified.
- The user can log in.

## AUTH-05 - Verification link failure states

Test:

- changed or truncated token;
- expired token;
- already-used token;
- token generated for an email that no longer matches the account.

**Expected**

- Each returns controlled `400`.
- The response identifies `invalid`, `expired`, or `used` where applicable.
- The account is not incorrectly activated.

## AUTH-06 - Neutral resend response

**Steps**

1. Request resend for an unverified account.
2. Request resend for an unknown address.
3. Compare the visible responses.

**Expected**

- Both return `200` with the same neutral message.
- The unknown address is not disclosed.

## AUTH-07 - Successful login

**Steps**

1. Log in as `seed_001`.
2. Inspect cookies in developer tools.

**Expected**

- Login returns `200`.
- Access and refresh JWT cookies are `HttpOnly`.
- Separate CSRF cookies are readable for request headers.
- The refresh cookie is scoped to `/api/auth/refresh`.
- The user object is returned without exposing password hash or token values.
- The user reaches the application because the seed profile is complete.

## AUTH-08 - Login failure states

Test:

- wrong username;
- wrong password;
- password longer than 72 UTF-8 bytes;
- valid credentials for an unverified account;
- malformed request body.

**Expected**

- Invalid credentials return `401` with a generic message.
- Unverified account returns `401` asking for verification.
- Malformed input returns `400`.
- No cookie session is created.

## AUTH-09 - Access-token refresh

**Steps**

1. Log in.
2. Wait until the short access token expires, or remove only the access cookie.
3. Trigger a protected frontend request.

**Expected**

- The client performs one `POST /api/auth/refresh` using the refresh CSRF token.
- A new access cookie is set.
- The original request is retried once.
- The page remains usable.
- A failed refresh clears stale client CSRF hints and returns to login.

## AUTH-10 - Logout revokes the server session

**Steps**

1. Log in and open a protected page.
2. Click logout.
3. Attempt `GET /api/auth/me` using the same browser.
4. Observe the second browser if the same account was connected there under the same session.

**Expected**

- Logout returns `200`.
- Current session row is revoked.
- Cookies are cleared.
- Sockets belonging to that session are disconnected.
- The later protected request returns `401`.

## AUTH-11 - Neutral forgot-password behavior

Request reset for:

- a known address;
- an unknown address.

**Expected**

- Both return `200` with the same message.
- Only the known address receives mail.

## AUTH-12 - Password reset success

**Steps**

1. Request a reset email.
2. Open the reset link.
3. Submit a strong new password.
4. Try an old logged-in browser session.
5. Log in using old and new passwords.

**Expected**

- Token validation returns `200` before use.
- Reset returns `200`.
- All previous sessions are revoked.
- Existing sockets disconnect.
- Old password fails.
- New password succeeds.
- Reusing the same reset link returns controlled `400` with `used`.

## AUTH-13 - CSRF enforcement

**Postman or browser Network replay**

1. Log in.
2. Send an authenticated unsafe request without `X-CSRF-TOKEN`.
3. Repeat with a changed token.
4. Repeat with the correct token from the corresponding CSRF cookie.

**Expected**

- Missing or invalid CSRF is rejected with an authentication error.
- No database change occurs.
- Correct CSRF succeeds.
- `GET`, `HEAD`, and `OPTIONS` do not require the CSRF header.

# 5. Profile completion and editing

## PROFILE-01 - Incomplete account gate

Use a newly verified local account with no completed profile.

**Steps**

1. Log in.
2. Manually enter `/`, `/messages`, `/map`, `/dates`, or another dating page.
3. Call a protected dating endpoint directly.

**Expected**

- Frontend redirects to `/profile`.
- Backend returns `403` with:

```json
{
  "message": "Complete your profile before using Matcha",
  "code": "PROFILE_INCOMPLETE",
  "missingFields": ["..."]
}
```

- The incomplete account is absent from discovery and public-profile results.
- It does not connect to presence or receive dating notifications.

## PROFILE-02 - Required completion fields

Complete:

- first name;
- last name;
- email;
- birth date producing age 18–80;
- gender;
- at least one sexual preference;
- non-empty biography;
- at least one reusable tag;
- valid latitude and longitude with a location label;
- at least one photo, which becomes primary.

**Expected**

- `isProfileComplete` becomes true only after all requirements exist.
- Full navigation becomes available.

## PROFILE-03 - Identity edits

Edit first name, last name, birth date, gender, preferences, and biography.

**Expected**

- Valid fields return `200`.
- Empty required values return `400`.
- Birth date cannot represent age under 18 or over 80.
- Biography over 500 characters is rejected.
- Fame is recalculated for fields that affect completion.

## PROFILE-04 - Email change

**Prerequisite**: working SMTP.

**Steps**

1. Change to an unused email.
2. Check the new inbox.
3. Log out and try to log in before verification.
4. Verify the new email.

**Expected**

- Backend sends verification before committing the email change.
- Successful change returns `emailChanged: true`.
- Account becomes unverified until the new email is verified.
- Duplicate email returns `409`.
- Mail failure returns `503` and preserves the previous email.

## PROFILE-05 - Tags

Test:

- one valid tag;
- several unique tags;
- duplicate IDs;
- empty list;
- non-list body;
- boolean/string IDs;
- unknown IDs;
- more than 20 IDs.

**Expected**

- Valid selection replaces the old selection and returns `200`.
- Duplicate valid IDs are normalized.
- Empty or malformed selections return `400`.
- At least one tag remains mandatory.

# 6. Photo and gallery cases

## PHOTO-01 - Valid first upload

**Steps**

1. Use a genuine JPEG or PNG under 5 MB.
2. Upload it from the profile editor.

**Expected**

- Request returns `201`.
- Server verifies image content rather than filename extension.
- EXIF orientation is applied.
- Metadata is removed by re-encoding.
- Dimensions are bounded.
- A cryptographically random server filename is used.
- The first photo becomes primary automatically.

## PHOTO-02 - Maximum five photos

Upload until five photos exist, then attempt a sixth.

**Expected**

- First five succeed.
- Sixth returns `400`.
- Rejected file is removed from storage.
- Database still contains five photos.

## PHOTO-03 - Malicious or invalid upload cases

Test:

- text file renamed `.jpg`;
- unsupported GIF/WebP/PDF;
- empty file;
- file over 5 MB;
- decompression-bomb dimensions;
- corrupt/truncated image;
- missing multipart `photo` field.

**Expected**

- Invalid content returns `400` or `413` as appropriate.
- No database row or leftover file remains.
- The frontend shows a controlled message.
- The console has no unhandled Axios error.

## PHOTO-04 - Replace photo

Replace an owned photo with another valid image.

**Expected**

- Returns `200`.
- Photo ID, order, and primary state remain coherent.
- Old stored file is deleted after the database replacement succeeds.

## PHOTO-05 - Replace or delete another user’s photo

Call the endpoint using a photo ID not owned by the current account.

**Expected**

- Returns `404`.
- Other user’s file and database row remain unchanged.

## PHOTO-06 - Primary selection

Select each owned photo as primary.

**Expected**

- Exactly one row is primary at all times.
- Primary photo moves to position zero and displays first publicly.
- Unknown or foreign photo ID returns `404`.

## PHOTO-07 - Last-photo protection

Delete photos until one remains, then attempt to delete the final photo.

**Expected**

- Final deletion returns `400`.
- The profile retains one primary image.
- The profile does not silently become invalid.

## PHOTO-08 - Browser image editor bonus

Test drag-and-drop, preview, crop, 90-degree rotation, and each controlled filter.

**Expected**

- Preview reflects the edits.
- Saved output uploads as a normal secure image.
- Server-side validation remains authoritative even after client editing.

# 7. Location cases

## LOCATION-01 - Explicit GPS consent accepted

**Steps**

1. Enable the GPS consent checkbox.
2. Allow browser location permission.

**Expected**

- Browser sends `gpsConsent: true` and numeric coordinates.
- Latitude is within `[-90, 90]` and longitude within `[-180, 180]`.
- Reverse-geocoded label is saved when available.
- If reverse geocoding fails, valid coordinates remain saved with `Approximate GPS location`.

## LOCATION-02 - GPS denied

**Steps**

1. Enable consent.
2. Deny the browser permission.

**Expected**

- UI clearly states that permission was denied.
- No false success appears.
- Manual-location search remains available.
- No unhandled console error appears.

## LOCATION-03 - GPS unavailable or timed out

Test with location disabled, unsupported, or temporarily unavailable.

**Expected**

- UI distinguishes permission denial from unavailable/timeout when the browser supplies that information.
- User can continue with manual location.

## LOCATION-04 - Manual search and save

**Steps**

1. Search for `Rabat`.
2. Select one result.
3. Save it.

**Expected**

- Search returns up to five normalized results.
- Save sends `gpsConsent: false`, name, latitude, and longitude.
- Profile becomes location-complete.

## LOCATION-05 - Location provider failure

Temporarily configure an unreachable Nominatim URL.

**Expected**

- Search returns `503` with a controlled message.
- Backend logs one provider warning, not an application crash.
- Existing location remains unchanged.

## LOCATION-06 - Invalid coordinates

Test booleans, strings, latitude outside `[-90, 90]`, and longitude outside `[-180, 180]`.

**Expected**

- Each returns `400`.
- No invalid coordinate reaches PostgreSQL.

# 8. Browse, search, and map

## DISCOVER-01 - Suggested profiles

Log in as `seed_001` and open `/`.

**Expected**

- Results exclude the current user.
- Results include only verified, complete, mutually compatible profiles.
- Blocked relationships are excluded both ways.
- Default ranking considers same area, distance, common tags, fame, then stable ID.
- Each card shows age, primary photo, fame, tags, presence, location label, distance, and common-tag count as available.

## DISCOVER-02 - Pagination

Move through pages and change page size through the API.

**Expected**

- Page starts at 1.
- Page size accepts 1–24.
- Pagination metadata matches the returned rows.
- Invalid page values return `400`.

## DISCOVER-03 - Advanced search filters

Independently and together test:

- age range 18–80;
- fame range 0–100;
- partial location text;
- one tag;
- multiple tags;
- sort by age, distance, fame, common tags, and recommended;
- ascending and descending order.

**Expected**

- Backend revalidates all parameters.
- Multiple selected tags require the candidate to contain all selected tags.
- Invalid IDs, ranges, sort values, or order values return `400`.

## DISCOVER-04 - Map privacy

Open `/map`.

**Expected**

- Current and candidate coordinates are rounded before public serialization.
- Blocked and incompatible profiles are absent.
- Clicking a marker shows a profile popup.
- Clicking empty map space closes it.
- Clicking outside the map closes it.
- The removed sort-direction controls do not appear.
- Missing current-user location returns controlled `400`.

# 9. Public profiles, visits, likes, matches, blocks, and reports

## SOCIAL-01 - Public profile by username

Open `/users/seed_002` as `seed_001`.

**Expected**

- Stable username route loads the profile.
- Private email, birth date, exact coordinates, password data, and session data are absent.
- Relationship state shows `hasLikedThem`, `theyLikedMe`, and `isConnected`.

## SOCIAL-02 - Hidden profile behavior

Attempt to open:

- nonexistent username;
- incomplete account;
- account that blocked you;
- account you blocked.

**Expected**

- All behave as unavailable and return `404`.
- The response does not reveal which hidden condition applies.

## SOCIAL-03 - Visit idempotency

**Steps**

1. Open a target profile once.
2. Replay the exact same `visitId` UUID.
3. Open it again with a new visit ID.

**Expected**

- First new UUID returns `201` and `recorded: true`.
- Repeated UUID returns `200` and `recorded: false`.
- A new logical visit can be stored.
- Target receives one notification per new visit, not duplicates from one page load.

## SOCIAL-04 - Directional like

Use two users that are not already matched, or unlike the seeded pair first.

**Expected**

- First like returns `200`, `liked: true`.
- Recipient receives real-time and persisted `like` notification.
- Repeated same like returns `409`.
- Self-like returns `400`.
- Account without a primary photo cannot like.

## SOCIAL-05 - Mutual match

Have the recipient like back.

**Expected**

- Both users receive `match` notifications.
- `isConnected` becomes true.
- Conversation status is emitted to both browsers.
- Chat, audio call, and date proposal become available.

## SOCIAL-06 - Unlike connected user

Unlike while connected.

**Expected**

- Directional like is removed.
- Both users cease to be connected.
- Other user receives mandatory `unlike` notification.
- Chat input is disabled, but existing history can still be viewed when authorized.
- Active/ringing audio call ends.
- New date actions are forbidden.

## SOCIAL-07 - Block

**Steps**

1. Recreate a match.
2. Block the other user during normal use or an active call.

**Expected**

- Block returns `200`.
- Both directed likes are removed transactionally.
- Chat becomes unavailable.
- Active call ends immediately.
- Profiles disappear from public view, discovery, map, and activity.
- Notifications from that relationship are hidden/suppressed according to the application rules.

## SOCIAL-08 - Unblock

Unblock from `/settings/blocked`.

**Expected**

- Block row is removed.
- Deleted likes are not automatically restored.
- Users must like each other again to reconnect.

## SOCIAL-09 - Fake-account report

Click the one-step report control.

**Expected**

- First report returns `201`.
- No reason popup or free-text field appears.
- Reason is stored as `fake_account`.
- Repeating the report returns `409`.
- Self-report returns `400`.

# 10. Activity, presence, chat, and notifications

## ACTIVITY-01 - Categories

Open `/profile/activity`.

**Expected**

- Visits show profile viewers.
- `likedByMe` shows outgoing non-mutual likes.
- `likedMe` shows incoming non-mutual likes.
- Matches show mutual connections.
- Blocked profiles are absent.

## PRESENCE-01 - First and last tab behavior

**Steps**

1. Log in with Browser A.
2. Open a second tab for the same session.
3. Observe from Browser B.
4. Close one tab, then the final tab.

**Expected**

- User becomes online on first authenticated socket.
- Closing one of several tabs does not mark the user offline.
- Closing the final connection marks offline and updates last activity.
- Restarting backend resets stale online flags.

## CHAT-01 - Connected conversation

Using `seed_001` and `seed_002`:

1. Open `/messages` in both sessions.
2. Select the other user.
3. Send messages in both directions.

**Expected**

- Message returns `201`.
- It appears in real time in both sessions.
- Content is persisted.
- Latest-message and unread counters update.
- Only connected users can send.

## CHAT-02 - Message validation

Test:

- non-string content;
- empty string;
- whitespace-only string;
- more than 1000 characters;
- self/unknown/blocked target;
- disconnected target.

**Expected**

- Invalid content returns `400`.
- Disconnected send returns `403`.
- Hidden/blocked target returns `404`.
- No invalid message is inserted.

## CHAT-03 - Pagination and historical access

Create enough messages to use multiple pages, then unlike.

**Expected**

- Pages return chronological messages inside each page.
- Page size accepts 1–100.
- Existing history remains readable after unlike where conversation history exists.
- New message is forbidden.

## CHAT-04 - Read receipts

Keep Browser A on the conversation while Browser B sends a message.

**Expected**

- Mark-read endpoint returns changed message IDs.
- Sender receives `message_read` event.
- UI shows Seen only for messages actually marked read.
- Unread total becomes accurate.

## NOTIFICATION-01 - Mandatory notification types

Trigger each:

- profile view;
- like received;
- mutual match;
- message received;
- connected user unlike.

**Expected**

- Each is persisted in PostgreSQL.
- Each appears in real time.
- Unread badge increments.
- Multiple simultaneous popups stack rather than replacing one another.
- Every popup has an independent timeout and close button.

## NOTIFICATION-02 - Date bonus notifications

Trigger proposal, accept, decline, and cancel.

**Expected**

- `date` notifications are stored and emitted to the relevant user.
- The date page updates via `date_event`.

## NOTIFICATION-03 - Read states

Test one notification and then all notifications.

**Expected**

- One-read request updates only an owned ID.
- Read-all produces unread count zero.
- Refresh preserves read state.

# 11. Audio-only call bonus

The implementation must never request or transmit camera video.

## AUDIO-01 - Incoming and accepted call

**Steps**

1. Keep `seed_001` and `seed_002` connected.
2. Start an audio call from Browser A.
3. Accept in Browser B.
4. Grant microphone permission in both browsers.

**Expected**

- Browser requests microphone permission only.
- No camera permission appears.
- `getUserMedia` uses audio and explicitly disables video.
- Recipient sees incoming-call UI on any protected page.
- WebRTC audio connects peer to peer after Socket.IO signaling.
- Timer and connection state update.

## AUDIO-02 - Mute and unmute

Toggle microphone state in each browser.

**Expected**

- Local audio track `enabled` state changes.
- Call remains connected.
- UI accurately shows muted/unmuted state.

## AUDIO-03 - Decline

Decline a ringing call.

**Expected**

- Both interfaces close.
- Caller sees a controlled declined state.
- Call indexes are removed.

## AUDIO-04 - No answer

Do not answer for 30 seconds.

**Expected**

- Caller receives no-answer feedback.
- Recipient popup closes.
- Later calls can start; neither user remains busy.

## AUDIO-05 - Busy user

Start a call involving one user, then attempt another call involving the same user from another connected account.

**Expected**

- Second request is rejected as busy.
- Existing call remains unaffected.

## AUDIO-06 - Permission denied or missing device

Deny microphone permission or test a browser with no input device.

**Expected**

- Call closes safely.
- Clear user-facing error appears.
- No camera request occurs.
- The other participant is not left indefinitely ringing/connected.

## AUDIO-07 - Unlike or block during call

**Expected**

- Backend ends the call for both users immediately.
- Reason is propagated.
- New call signaling is rejected until a mutual connection is recreated.

## AUDIO-08 - Participating tab closes

Open two tabs for one account. Start/accept in one tab, then close that participating tab.

**Expected**

- Call ends even though another Matcha tab remains connected.
- Presence may remain online because another tab is still active.
- No permanent busy state remains.

## AUDIO-09 - Socket or network interruption

Disable network briefly or restart the backend.

**Expected**

- Call UI exits or reports connection failure.
- Media tracks stop.
- Reconnection does not reuse stale call IDs.

# 12. Date scheduling bonus

## DATE-01 - Create proposal

As a connected user, propose a future timezone-aware date, location, and optional note.

**Expected**

- Returns `201`.
- Timestamp is stored as `TIMESTAMPTZ` and returned as UTC ISO text.
- Recipient receives real-time update and notification.
- Both users see pending state.

## DATE-02 - Validation failures

Test:

- missing or non-string `scheduledFor`;
- invalid ISO date;
- timezone missing;
- past/current timestamp;
- empty location;
- location over 150 characters;
- non-string note;
- note over 500 characters;
- disconnected, blocked, incomplete, self, or unknown target.

**Expected**

- Malformed values return `400`.
- Disconnected relationship returns `403`.
- Hidden/unknown target returns `404`.
- No invalid event row is inserted.

## DATE-03 - Accept as recipient

**Expected**

- Recipient can accept pending proposal.
- Returns `200` and status `accepted`.
- Proposer receives real-time update and notification.
- Repeating response returns `409`.

## DATE-04 - Decline as recipient

Use a separate pending proposal.

**Expected**

- Status becomes `declined`.
- Event moves to history.
- Proposer is notified.

## DATE-05 - Unauthorized response

Try to respond as proposer or unrelated user.

**Expected**

- Event behaves as not found and returns `404`.
- Status is unchanged.

## DATE-06 - Cancel

Cancel a pending or accepted future date as either participant.

**Expected**

- Returns `200` and status `cancelled`.
- Other participant is notified.
- Declined, cancelled, completed/past, or otherwise non-cancellable state returns `409`.

## DATE-07 - Relationship changed

Unlike or block before responding/cancelling.

**Expected**

- New action returns `403`.
- Historical database row is not corrupted.
- Blocked relationship is hidden from visible date results.

# 13. OAuth bonus

OAuth requires provider credentials and exact callback URLs in `backend/.env` and provider consoles.

## OAUTH-01 - Provider not configured

Leave one provider group empty and open its login endpoint.

**Expected**

- Returns controlled `503`.
- Local authentication remains usable.

## OAUTH-02 - Google success

**Expected**

- Backend creates signed state in secure session cookie.
- User is redirected to Google.
- Callback validates provider and state.
- Token exchange has timeout and controlled failure handling.
- Existing account with the same email is safely linked when allowed.
- New account receives a unique username.
- Normal Matcha JWT cookies are set.
- No access or refresh token appears in callback URL.

## OAUTH-03 - 42 success

Repeat the Google sequence using the 42 provider.

**Expected**

- Provider identities remain unique.
- Same secure Matcha session mechanism is used.

## OAUTH-04 - OAuth failures

Test:

- user denies permission;
- missing code;
- missing state;
- changed state;
- expired state;
- provider timeout;
- malformed provider profile;
- provider identity already linked to another user.

**Expected**

- Frontend returns to login with a controlled error reason.
- No JWT is placed in a URL.
- No duplicate or partially linked account is created.

# 14. Security and negative checks

## SECURITY-01 - Secrets absent from source archive

```bash
find . -name '.env' -o -name '*.pem' -o -name '*.key'
```

**Expected**

- No real `.env` or private key is shipped.
- Only `backend/.env.example` exists.

Search for obvious placeholder mistakes:

```bash
grep -R "replace_with_" -n . --exclude='.env.example' --exclude='*.md'
```

Expected: no runtime source secret.

## SECURITY-02 - SQL injection probes

Send metacharacters and SQL-like strings through username, location, biography, message, and search fields.

**Expected**

- Inputs are treated as data.
- Queries use `%s` parameters.
- Database schema remains intact.
- Validation may reject malformed values with `400`.

## SECURITY-03 - XSS probes

Use values such as:

```text
<script>alert(1)</script>
<img src=x onerror=alert(1)>
```

in biography, message, location, and name where accepted by validation.

**Expected**

- React renders text, not executable HTML.
- Email first name is HTML escaped.
- No alert or injected element executes.

## SECURITY-04 - Path traversal

Request:

```text
/uploads/../../etc/passwd
```

and manipulate photo filenames where possible.

**Expected**

- Flask path handling and generated server filenames prevent arbitrary file access.
- Delete utility rejects basenames containing paths.
- Request returns `404`, never host file content.

## SECURITY-05 - Upload ownership and content

Confirm:

- foreign photo IDs cannot be modified;
- extension alone does not authorize image type;
- oversized/decompression-bomb files are rejected;
- EXIF metadata is not retained;
- maximum five and one-primary rules hold under repeated requests.

## SECURITY-06 - Public data minimization

Inspect discovery, map, public profile, chat contact, notification, and call user payloads.

**Expected**

They do not expose:

- password hash;
- token version;
- email for other users;
- birth date for other users;
- exact coordinates for other users;
- OAuth provider tokens;
- session identifiers;
- reset/verification tokens.

## SECURITY-07 - Security headers

```bash
curl -I http://localhost:5000/api/health
curl -I http://localhost:3000
```

Expected headers include protections such as:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
```

API responses should also use `Cache-Control: no-store`.

## SECURITY-08 - Controlled unknown routes and methods

Test an unknown API route and unsupported method.

**Expected**

- Unknown route returns JSON `404`.
- Unsupported method returns JSON `405`.
- No HTML debug page or stack trace appears.

# 15. Postman collection

## 15.1 Files

Import both:

```text
postman/Matcha.postman_collection.json
postman/Matcha.local.postman_environment.json
```

Select the **Matcha Local Docker** environment.

## 15.2 Cookie and CSRF behavior

The API uses:

- HttpOnly access JWT cookie;
- HttpOnly refresh JWT cookie;
- readable access CSRF cookie;
- readable refresh CSRF cookie.

Postman’s cookie jar stores `Set-Cookie` values after login. The collection-level pre-request script:

1. ignores safe `GET`, `HEAD`, and `OPTIONS` methods;
2. chooses `csrf_refresh_token` for `/api/auth/refresh...`;
3. chooses `csrf_access_token` for other unsafe requests;
4. places the value in `X-CSRF-TOKEN`.

Do not manually copy JWT values into an Authorization header. This application intentionally authenticates through cookies.

## 15.3 Recommended Postman order

1. `00 - Health and session bootstrap → Health check`
2. `01 - Authentication → Login seed account`
3. `01 - Authentication → Current private user`
4. `05 - Public profiles and relationships → Resolve target by username`
5. Run read-only profile/discover/activity/message/notification/date requests.
6. Run state-changing relationship or date requests in an order that preserves required preconditions.
7. Run `99 - Session cleanup → Logout and revoke session` last.

The login test script stores `currentUserId`. Resolving the target stores `targetUserId`. Notification, photo, and date requests store their latest relevant IDs when returned.

The collection generates `futureDate` 48 hours ahead whenever that environment variable is empty, invalid, or already past.

## 15.4 Two-user Postman workflows

A single Postman cookie jar represents one browser session. Tests requiring two authenticated users should use one of these approaches:

### Approach A - Browser plus Postman

- Keep `seed_001` logged in through Postman.
- Use Browser B for `seed_002` actions such as accept/decline, reciprocal like, and read receipt.

### Approach B - Duplicate environment and separate Postman workspace/profile

- Duplicate the environment as `Matcha Local - User B`.
- Use a separate Postman profile/workspace or clear cookies before switching.
- Login as `seed_002`.
- Keep the correct `targetUserId` for the opposite account.

Do not assume changing the username environment variable changes the already authenticated cookie session. You must log out or clear the cookie jar and log in again.

## 15.5 File upload requests

For upload and replace requests:

1. Open the request Body tab.
2. Keep `form-data`.
3. In the `photo` row, select **File**.
4. Choose a real local JPEG or PNG.
5. Postman calculates the multipart boundary automatically.

Do not manually force `Content-Type: multipart/form-data` with a missing boundary.

## 15.6 OAuth requests in Postman

OAuth is primarily browser-driven because provider consent, redirects, and state cookies are involved. The collection includes start and callback requests for completeness, but the correct end-to-end verification is the browser workflow in section 13.

## 15.7 Failure-case requests

The `10 - Controlled failure cases` folder intentionally expects client errors. A case passes when it receives the documented `4xx` JSON response without an application crash.

# 16. REST endpoint reference

Every protected unsafe endpoint requires the access JWT cookie and matching access CSRF header. Refresh endpoints use the refresh cookie and refresh CSRF header.

## 16.1 Health and authentication

| Method | Path | Success | Important controlled failures |
|---|---|---:|---|
| GET | `/api/health` | 200 | 500 only when database is genuinely unavailable |
| POST | `/api/auth/refresh/bootstrap` | 200 | Network/server failure remains a real failure |
| POST | `/api/auth/register` | 201 | 400 validation, 409 duplicate, 503 mail failure |
| GET | `/api/auth/verify/<token>` | 200 | 400 invalid/expired/used |
| POST | `/api/auth/resend-verification` | 200 | 400 malformed email |
| POST | `/api/auth/login` | 200 | 400 malformed, 401 invalid/unverified |
| GET | `/api/auth/me` | 200 | 401 missing/expired session, 404 missing user |
| POST | `/api/auth/refresh` | 200 | 401 invalid/revoked/expired refresh or CSRF |
| POST | `/api/auth/logout` | 200 | 401 missing/invalid access or CSRF |
| POST | `/api/auth/forgot-password` | 200 | 400 malformed email |
| GET | `/api/auth/verify-reset-token/<token>` | 200 | 400 invalid/expired/used |
| POST | `/api/auth/reset-password` | 200 | 400 invalid token/password |

Registration body:

```json
{
  "username": "new_user",
  "email": "new_user@example.com",
  "firstName": "New",
  "lastName": "User",
  "password": "Strong!Password6429"
}
```

## 16.2 Profile

| Method | Path | Success | Important controlled failures |
|---|---|---:|---|
| GET | `/api/profile` | 200 | 401, 404 |
| PUT | `/api/profile` | 200 | 400 validation, 409 email conflict, 503 mail failure |
| GET | `/api/profile/tags` | 200 | 401 |
| PUT | `/api/profile/tags` | 200 | 400 invalid/empty tags |
| POST | `/api/profile/photos` | 201 | 400 invalid/limit, 413 oversized |
| PUT | `/api/profile/photos/<photo_id>` | 200 | 400 invalid, 404 ownership/not found, 413 oversized |
| DELETE | `/api/profile/photos/<photo_id>` | 200 | 400 last photo, 404 ownership/not found |
| PUT | `/api/profile/photos/<photo_id>/primary` | 200 | 404 ownership/not found |
| GET | `/api/profile/location/search?q=...` | 200 | 400 invalid query, 503 provider unavailable |
| PUT | `/api/profile/location` | 200 | 400 consent/name/coordinate validation |
| GET | `/api/profile/viewers` | 200 | 403 incomplete |
| GET | `/api/profile/likes` | 200 | 403 incomplete |
| GET | `/api/profile/activity` | 200 | 403 incomplete |

Editable JSON fields are optional per update request:

```json
{
  "firstName": "First",
  "lastName": "Last",
  "email": "person@example.com",
  "birthDate": "1998-06-15",
  "gender": "male",
  "sexualPreferences": ["female", "non-binary"],
  "biography": "Profile text"
}
```

Manual location:

```json
{
  "gpsConsent": false,
  "locationName": "Agdal, Rabat",
  "latitude": 33.9904,
  "longitude": -6.848
}
```

GPS location:

```json
{
  "gpsConsent": true,
  "latitude": 33.9904,
  "longitude": -6.848
}
```

## 16.3 Discovery and map

| Method | Path | Success | Important controlled failures |
|---|---|---:|---|
| GET | `/api/discover` | 200 | 400 filter validation, 403 incomplete |
| GET | `/api/discover/map` | 200 | 400 filter/missing location, 403 incomplete |

Supported query parameters:

```text
minAge=18..80
maxAge=18..80
minFame=0..100
maxFame=0..100
location=<up to 100 characters>
tagIds=1,2,3
sort=recommended|age|distance|fame|commonTags
order=asc|desc
page>=1
pageSize=1..24
```

## 16.4 Public profiles and social actions

| Method | Path | Success | Important controlled failures |
|---|---|---:|---|
| GET | `/api/users/blocked` | 200 | 403 incomplete |
| GET | `/api/users/<user_id>` | 200 | 404 hidden/unavailable |
| GET | `/api/users/by-username/<username>` | 200 | 404 hidden/unavailable |
| POST | `/api/users/<user_id>/visit` | 201 or idempotent 200 | 400 self/UUID, 404 hidden |
| POST | `/api/users/<user_id>/like` | 200 | 400 self/no photo, 404 hidden, 409 duplicate |
| DELETE | `/api/users/<user_id>/like` | 200 | 400 self, 404 hidden, 409 absent |
| POST | `/api/users/<user_id>/block` | 200 | 400 self, 404 hidden |
| DELETE | `/api/users/<user_id>/block` | 200 | 404 absent |
| POST | `/api/users/<user_id>/report` | 201 | 400 self, 404 hidden, 409 duplicate |

Visit body:

```json
{
  "visitId": "a unique UUID generated once per logical page visit"
}
```

## 16.5 Messages

| Method | Path | Success | Important controlled failures |
|---|---|---:|---|
| GET | `/api/messages` | 200 | 403 incomplete |
| GET | `/api/messages/unread-count` | 200 | 403 incomplete |
| GET | `/api/messages/<user_id>` | 200 | 400 pagination, 403 no connection/history, 404 hidden |
| POST | `/api/messages/<user_id>` | 201 | 400 content, 403 disconnected, 404 hidden |
| PUT | `/api/messages/<user_id>/read` | 200 | 404 no visible conversation |

Message body:

```json
{
  "content": "One to 1000 non-whitespace characters"
}
```

## 16.6 Notifications

| Method | Path | Success | Important controlled failures |
|---|---|---:|---|
| GET | `/api/notifications` | 200 | 403 incomplete |
| GET | `/api/notifications/unread-count` | 200 | 403 incomplete |
| PUT | `/api/notifications/<notification_id>/read` | 200 | 403 incomplete |
| PUT | `/api/notifications/read-all` | 200 | 403 incomplete |

## 16.7 Date proposals

| Method | Path | Success | Important controlled failures |
|---|---|---:|---|
| GET | `/api/dates` | 200 | 403 incomplete |
| POST | `/api/dates/<user_id>` | 201 | 400 validation, 403 disconnected, 404 hidden |
| PUT | `/api/dates/<event_id>/respond` | 200 | 400 status, 403 relationship, 404 ownership, 409 state |
| PUT | `/api/dates/<event_id>/cancel` | 200 | 403 relationship, 404 ownership, 409 state |

Proposal body:

```json
{
  "scheduledFor": "2026-08-10T18:00:00.000Z",
  "location": "Coffee shop near the station",
  "note": "Optional note, maximum 500 characters"
}
```

Response body:

```json
{
  "status": "accepted"
}
```

or:

```json
{
  "status": "declined"
}
```

## 16.8 OAuth and uploads

| Method | Path | Normal result |
|---|---|---|
| GET | `/api/auth/oauth/42/login` | Provider redirect or 503 if not configured |
| GET | `/api/auth/oauth/42/callback` | Frontend redirect after state/code processing |
| GET | `/api/auth/oauth/google/login` | Provider redirect or 503 if not configured |
| GET | `/api/auth/oauth/google/callback` | Frontend redirect after state/code processing |
| GET | `/uploads/<generated_filename>` | Stored profile image or 404 |

# 17. Socket.IO event reference

The Socket.IO handshake authenticates using the HttpOnly access cookie and active server-side session. Incomplete or revoked accounts are rejected.

## 17.1 Server events consumed by the browser

| Event | Purpose |
|---|---|
| `presence` | Online/offline and last-activity updates |
| `notification` | Persisted real-time notification payload |
| `message` | New persisted chat message |
| `message_read` | Seen receipt with reader and message IDs |
| `conversation_status` | Match, unlike, or block changed chat authorization |
| `date_event` | Proposal created or status changed |
| `call_incoming` | Incoming audio invitation |
| `call_accepted` | Recipient accepted |
| `call_declined` | Recipient declined |
| `call_signal` | Validated WebRTC offer, answer, or ICE candidate |
| `call_ended` | Call ended with a controlled reason |

## 17.2 Audio-call client events

| Event | Minimum payload | Expected acknowledgement |
|---|---|---|
| `call_start` | `{ "recipientId": 2 }` | `{ ok, callId?, recipient?, message? }` |
| `call_accept` | `{ "callId": "uuid" }` | `{ ok, message? }` |
| `call_decline` | `{ "callId": "uuid" }` | `{ ok, message? }` |
| `call_signal` | `{ "callId", "type", "signal" }` | `{ ok, message? }` |
| `call_end` | `{ "callId": "uuid" }` | `{ ok, message? }` |

Allowed signal types are `offer`, `answer`, and `ice`. SDP and ICE candidate sizes are bounded before relay.

# 18. Database evidence

Open PostgreSQL only through Docker:

```bash
docker compose --env-file backend/.env exec db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

Because host shell expansion may not know the container variables, this form is more reliable:

```bash
docker compose --env-file backend/.env exec db sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

## 18.1 Confirm exactly 500 seed users

```sql
SELECT COUNT(*)
FROM users
WHERE username LIKE 'seed\_%' ESCAPE '\';
```

Expected:

```text
500
```

## 18.2 Confirm complete seed data

```sql
SELECT
    COUNT(*) FILTER (WHERE is_verified) AS verified,
    COUNT(*) FILTER (WHERE birth_date IS NOT NULL) AS with_birth_date,
    COUNT(*) FILTER (WHERE gender IS NOT NULL) AS with_gender,
    COUNT(*) FILTER (WHERE biography IS NOT NULL AND btrim(biography) <> '') AS with_bio,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL AND longitude IS NOT NULL) AS with_location
FROM users
WHERE username LIKE 'seed\_%' ESCAPE '\';
```

Each count should be `500`.

## 18.3 Confirm one primary photo per seeded user

```sql
SELECT COUNT(*) AS users_with_invalid_primary_count
FROM (
    SELECT user_id
    FROM photos
    JOIN users ON users.id = photos.user_id
    WHERE users.username LIKE 'seed\_%' ESCAPE '\'
    GROUP BY user_id
    HAVING COUNT(*) FILTER (WHERE is_primary) <> 1
) invalid;
```

Expected:

```text
0
```

## 18.4 Confirm deterministic match

```sql
SELECT
    a.username AS user_a,
    b.username AS user_b
FROM users a
JOIN users b ON b.username = 'seed_002'
WHERE a.username = 'seed_001'
  AND EXISTS (
      SELECT 1 FROM user_likes
      WHERE liker_id = a.id AND liked_id = b.id
  )
  AND EXISTS (
      SELECT 1 FROM user_likes
      WHERE liker_id = b.id AND liked_id = a.id
  );
```

Expected row:

```text
seed_001 | seed_002
```

## 18.5 Inspect important tables

```sql
\dt
```

The schema should include account/session, profile, social, messaging, notification, OAuth, and date tables documented in `README_TECHNICAL.md`.

# 19. Final acceptance gate

The project is ready for evaluation only after all of these are true:

- [ ] `./start.sh` completes all seven phases.
- [ ] PostgreSQL, backend, and frontend are healthy.
- [ ] Exactly 500 seed users exist.
- [ ] No real `.env` or secret exists in the source archive.
- [ ] Registration, verification, login, refresh, logout, and reset work.
- [ ] Incomplete accounts cannot access dating features.
- [ ] Profile, tags, location, and photo invariants hold.
- [ ] Discover, advanced search, sorting, filtering, and map work.
- [ ] Visits, likes, matches, unlike, blocks, and reports work.
- [ ] Chat is limited to connected users and Seen receipts work.
- [ ] All mandatory notifications arrive and persist.
- [ ] Audio calls request microphone only and end on unlike/block/disconnect.
- [ ] Date proposals support create, accept, decline, and cancel.
- [ ] Google and 42 OAuth work when configured.
- [ ] Handled failure cases return controlled `4xx` JSON.
- [ ] No unexpected backend traceback appears during normal testing.
- [ ] Browser Console remains free of unexpected errors.