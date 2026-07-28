# Step 4 — Profile visits, likes, matches, blocks, reports, and presence

This step creates the consistent relationship system required before browse and chat. It covers separate visit-history records, likes, mutual connections, disconnects, blocking, unblocking, fake-account reports, online presence and last connection.

## A. Files

[Download the Step 4 patch](sandbox:/mnt/data/matcha_step4.patch)

[Download the complete Step 4 project](sandbox:/mnt/data/matcha-step4-updated.tar.gz)

The patch is based on:

* completed Step 3;
* the location correction;
* your frontend image-content validation;
* the existing narrow refresh-cookie path.

It does not contain or modify `backend/.env`.

## B. Subject requirement

The subject requires:

* every profile visit to be recorded;
* likes and mutual connections;
* unlike/disconnect behavior;
* no like without a profile picture;
* online state and last connection;
* reporting fake accounts;
* blocking users from profiles, search, notifications and chat.

The approved plan also requires `/settings/blocked`, duplicate-report prevention and multi-tab presence behavior.

## C. Current flow before this change

Before Step 4:

1. Repeated visits from one viewer overwrote the previous timestamp.
2. The activity page could show only one entry per viewer.
3. Duplicate likes were checked before insertion but not protected against concurrent requests.
4. Unlike did not reject blocked relationships.
5. A blocked user could potentially generate an unlike notification through a direct request.
6. Notification creation did not centrally check blocks.
7. Connected unlike did not prevent future notifications from the disconnected user.
8. Reports checked for duplicates before insertion, leaving a race condition.
9. There was no blocked-users page.
10. Blocking redirected to the missing `/browse` route.
11. Presence events existed, but profile and activity pages did not consume live presence updates.
12. Stale `is_online=true` rows could survive a backend restart.

## D. Concept explanation

### Visits are events, not relationships

A like represents one current relationship:

```text
A currently likes B
```

A visit represents a historical event:

```text
A viewed B at 10:00
A viewed B at 12:30
```

Therefore, likes need a unique user pair, while visits need a separate row for every event.

### A connection is derived from two likes

No separate connection table is needed:

```text
A likes B
+
B likes A
=
connected
```

Removing either like immediately disconnects the users.

### Notification suppression after unlike

When A disconnects from B, A must stop receiving future notifications from B.

The new table stores:

```text
user_id = A
suppressed_user_id = B
```

If A later likes B again, that suppression is removed.

### Central block protection

Checking blocks only inside individual routes is fragile. Every notification now passes through one central check:

```text
blocked in either direction
→ do not insert notification
→ do not emit Socket.IO event
```

## E. Technical design

### Visit flow

1. A opens B’s profile.
2. Backend checks blocks.
3. A new `user_views` row is inserted.
4. A view notification is attempted.
5. Central notification rules check blocks and unlike suppression.
6. B’s fame rating is recalculated.
7. B’s activity page displays the viewer and exact viewing time.

### Like flow

1. Backend rejects self-like.
2. Backend checks target existence.
3. Backend checks blocks.
4. Backend verifies that the current user has a primary photo.
5. PostgreSQL inserts the like using `ON CONFLICT DO NOTHING`.
6. Old notification suppression from the current user toward the target is removed.
7. If the reverse like exists, both users receive a match notification.
8. Otherwise, the target receives a like notification.

### Unlike flow

1. Backend checks target and blocks.
2. Backend confirms the like exists.
3. It determines whether the users were connected.
4. The current user’s like is deleted.
5. When connected, notification suppression is created.
6. The other user receives the mandatory unlike notification.
7. The relationship becomes disconnected.

### Block flow

Blocking keeps existing likes and historical data but disables current access and interaction.

After blocking:

* public-profile access returns `404`;
* like and unlike return `404`;
* reporting through direct interaction returns `404`;
* notification insertion is centrally suppressed;
* the blocker can manage the block through `/settings/blocked`.

### Presence flow

The existing authenticated Socket.IO connection registry remains authoritative:

```text
one active connection  → online
multiple connections   → online
one connection closes  → still online
last connection closes → offline and lastActivity updated
```

At backend startup, stale online rows are reset before new Socket.IO connections are accepted.

## F. Exact files

### Created

`backend/tests/test_social_models.py`
Tests visit history, duplicate-safe likes, disconnect suppression and central notification blocking.

`backend/tests/test_social_routes.py`
Tests profile visits, duplicate likes, connected unlike, blocked unlike, duplicate reports and blocked-user listing.

`frontend/my-app/app/(dashboard)/settings/blocked/page.tsx`
Displays blocked users and provides the Unblock button.

### Edited

`backend/schema.sql`
Restructures visit history and adds notification suppression.

`backend/app/models.py`
Adds relationship, visit, block, suppression, report and serialization logic.

`backend/app/users.py`
Enforces the complete route-level relationship behavior.

`backend/app/profile.py`
Returns timestamped visit and like entries.

`backend/app/sockets.py`
Returns UTC-formatted last-activity values.

`backend/run.py`
Resets stale online states when the backend starts.

`frontend/my-app/app/services/api.ts`
Adds the blocked-users API method.

`frontend/my-app/app/components/ProfileActivity.tsx`
Displays every visit separately with its timestamp.

`frontend/my-app/app/components/NotificationBell.tsx`
Tracks live presence events through the existing Socket.IO connection.

`frontend/my-app/app/(dashboard)/users/[id]/page.tsx`
Uses live presence, correct report wording and valid block redirection.

`frontend/my-app/app/(dashboard)/layout.tsx`
Adds the Blocked users navigation link.

`README.md`
Documents the new schema, routes and behavior.

No files are deleted.

## G. Database changes

### `user_views`

Old definition:

```sql
PRIMARY KEY (viewer_id, viewed_id)
```

New structure:

```sql
CREATE TABLE IF NOT EXISTS user_views (
    id SERIAL PRIMARY KEY,
    viewer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    viewed_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    viewed_at TIMESTAMP NOT NULL DEFAULT now(),
    CHECK (viewer_id <> viewed_id)
);
```

Every visit now has:

* its own generated ID;
* viewer;
* viewed user;
* timestamp.

No uniqueness constraint prevents repeated visits.

### `notification_suppressions`

```sql
CREATE TABLE IF NOT EXISTS notification_suppressions (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    suppressed_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, suppressed_user_id),
    CHECK (user_id <> suppressed_user_id)
);
```

This table exists specifically to enforce the subject’s post-unlike notification rule.

### Indexes

Added:

```sql
CREATE INDEX IF NOT EXISTS idx_user_views_viewer_id
    ON user_views(viewer_id);

CREATE INDEX IF NOT EXISTS idx_notification_suppressions_suppressed
    ON notification_suppressions(suppressed_user_id);
```

The existing viewed-user timestamp index remains:

```sql
CREATE INDEX IF NOT EXISTS idx_user_views_viewed_at
    ON user_views(viewed_id, viewed_at DESC);
```

### Reports

The existing database unique constraint remains:

```sql
UNIQUE (reporter_id, reported_user_id)
```

The insertion now also uses:

```sql
ON CONFLICT (reporter_id, reported_user_id) DO NOTHING
```

This makes duplicate prevention safe even when two requests arrive together.

## H. Apply the patch

From the project root:

```bash
git status --short
```

Preserve local differences:

```bash
git diff > before-step4-local-changes.patch
```

Test the patch:

```bash
patch --dry-run -p1 < /path/to/matcha_step4.patch
```

Expected: every file reports `checking file` without `Hunk FAILED`.

Apply it:

```bash
patch -p1 < /path/to/matcha_step4.patch
```

Inspect the result:

```bash
git diff --stat
git diff
```

## I. Required database reset

This step changes the existing `user_views` primary-key structure. `CREATE TABLE IF NOT EXISTS` cannot modify the old table, so a clean reset is required.

This deletes all current accounts and data.

Stop Flask using `Ctrl+C`.

From `backend/`:

```bash
source venv/bin/activate
```

Start PostgreSQL:

```bash
docker compose up -d db
```

Reset the database:

```bash
python initdb.py --reset
```

Expected:

```text
Reset requested: all existing database data will be deleted.
Database reset and schema applied successfully.
```

Confirm the visit structure:

```bash
docker compose exec db sh -lc \
'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\d user_views"'
```

Confirm notification suppression:

```bash
docker compose exec db sh -lc \
'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\d notification_suppressions"'
```

## J. Tests

There were 44 existing tests. Step 4 adds 12 focused tests.

From `backend/` with `(venv)` visible:

```bash
python -m unittest discover -s tests -v
```

Expected:

```text
Ran 56 tests

OK
```

The Eventlet deprecation warning may still appear. It is not a test failure.

## K. Frontend checks

From `frontend/my-app/`:

```bash
npm run lint
```

Then:

```bash
npm run build
```

Start the frontend:

```bash
npm run dev
```

Start Flask in another terminal:

```bash
cd backend
source venv/bin/activate
python run.py
```

## L. Expected API behavior

### Blocked users

```http
GET /api/users/blocked
```

Response:

```json
{
  "blocks": [
    {
      "blockedAt": "2026-07-28T17:00:00Z",
      "user": {
        "id": 8,
        "username": "example"
      }
    }
  ]
}
```

### Duplicate like

```http
POST /api/users/8/like
```

Expected second attempt:

```http
409 CONFLICT
```

```json
{
  "message": "You already liked this user"
}
```

### Duplicate report

Expected second attempt:

```http
409 CONFLICT
```

```json
{
  "message": "You have already reported this user"
}
```

### Visit activity

```http
GET /api/profile/viewers
```

Response contains separate entries:

```json
{
  "viewers": [
    {
      "id": 12,
      "viewedAt": "2026-07-28T17:30:00Z",
      "viewer": {}
    },
    {
      "id": 11,
      "viewedAt": "2026-07-28T17:20:00Z",
      "viewer": {}
    }
  ]
}
```

## M. Manual verification

Use two verified users, A and B. Both need complete profiles and profile pictures.

### Visit history

1. Log in as A.
2. Open B’s profile.
3. Reload or reopen B’s profile.
4. Log in as B.
5. Open `/profile/activity`.

Expected:

* two separate visit entries;
* both entries show A;
* each entry has its own timestamp.

Database check:

```bash
docker compose exec db sh -lc \
'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT id, viewer_id, viewed_id, viewed_at
FROM user_views
ORDER BY id;
"'
```

### Like and match

1. A likes B.
2. Confirm B receives a like notification.
3. B likes A.
4. Confirm both profiles show connected.
5. Confirm match notifications appear.

### Connected unlike

1. A unlikes B.
2. Confirm A and B are no longer connected.
3. Confirm B receives the unlike notification.
4. B opens A’s profile afterward.
5. Confirm the visit is stored.
6. Confirm A does **not** receive another notification from B.

Check suppression:

```bash
docker compose exec db sh -lc \
'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT *
FROM notification_suppressions;
"'
```

### Block and unblock

1. A blocks B.
2. A is redirected to `/settings/blocked`.
3. Confirm B appears in the list.
4. Try opening each profile from the other account.
5. Confirm both directions return Profile not found.
6. Confirm direct like/unlike attempts return `404`.
7. Click **Unblock**.
8. Confirm B disappears from the blocked-users page.
9. Confirm existing like history was not deleted.

### Report

1. Open another user’s profile.
2. Click **Report as fake account**.
3. Confirm the button becomes **Reported as fake account**.
4. Confirm there is no popup, reason or text input.
5. Send a second direct request.
6. Confirm HTTP `409`.
7. Confirm the database contains one row.

```bash
docker compose exec db sh -lc \
'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT reporter_id, reported_user_id, reason, COUNT(*)
FROM reports
GROUP BY reporter_id, reported_user_id, reason;
"'
```

### Multi-tab presence

1. Open the application in two tabs as A.
2. Confirm A appears online.
3. Close one tab.
4. Confirm A remains online.
5. Close the final tab.
6. Confirm A becomes offline and `lastActivity` changes.

To prove login alone does not set online status, log in through curl without creating a Socket.IO connection and inspect `users.is_online`. It should remain `false`.

## N. Security and regression checks

Confirm:

* self-like, self-block and self-report return controlled `400`;
* duplicate like and report requests do not create duplicate rows;
* blocked users cannot trigger notifications;
* unlike suppression prevents future notifications from the disconnected user;
* old visits, likes and reports are not deleted when blocking;
* exact coordinates remain private;
* authentication cookies remain `HttpOnly`;
* no unexpected browser-console errors appear during normal UI flows;
* profile editing, tags, location and photo upload still work.

## O. Verification completed here

I verified:

* the patch applies cleanly to the corrected Step 3 project;
* applying the patch reproduces the prepared Step 4 project exactly;
* all backend Python files compile;
* all changed TypeScript and TSX files pass syntax transpilation;
* the patch does not include `.env`;
* the complete archive does not include `.env`.

I could not run the full 56-test suite because Flask dependencies were unavailable in this execution environment. I am not claiming the tests pass until you run them locally.

## P. Completion gate

Step 4 is complete only when:

* database reset succeeds;
* all 56 backend tests pass;
* frontend lint and build pass;
* repeated visits appear separately;
* like and mutual connection work;
* connected unlike sends the required notification;
* future notifications are suppressed after disconnect;
* blocks prevent access and notifications;
* `/settings/blocked` successfully unblocks;
* duplicate reports create one row only;
* multi-tab presence works;
* browser console contains no unexpected application error.

Send the command outputs and any failed behavior before moving to Step 5.
