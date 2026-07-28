## Step 1 — Secure baseline, configuration, and database structure

### Application flow

No major visible feature changes. The purpose is to establish a safe application baseline before changing user functionality.

### Technical work

We will:

* record all existing backend routes;
* record all existing frontend routes;
* record existing Socket.IO events;
* confirm the current startup process;
* exclude `.env` from Git;
* create `.env.example`;
* remove hardcoded credentials;
* disable unsafe debug behavior;
* validate required environment variables;
* preserve optional Google and 42 configuration;
* make `schema.sql` the single database definition;
* document the database-reset procedure;
* add common database constraints and indexes needed by existing tables.

We will not create:

* migration files;
* migration commands;
* migration history tables.

### Why this step is first

Security and configuration errors affect every later feature. Database changes must also follow one agreed process from the beginning.

### Problems solved

* `.env` being included in the repository;
* database password written directly in configuration;
* debug information exposure;
* inconsistent schema setup;
* confusion about missing frontend routes;
* uncertainty about what currently works.

### Completion gate

A clean database starts successfully from `schema.sql`, and no real secret is stored in tracked files.

---

## Step 2 — Authentication, validation, sessions, and email flows

This merges the previous validation, password, session, logout, and email-security steps.

### User flow

#### Registration

* User enters email, username, first name, last name, and password.
* Frontend validates the visible rules.
* Backend independently validates every value.
* Account is created.
* Verification email is sent.
* User verifies the account.
* User logs in.

#### Password reset

* User requests a reset.
* The application returns a neutral response.
* User receives a unique reset link.
* User changes the password.
* The reset link becomes unusable.
* Previous sessions become invalid.

#### Logout

* User clicks logout from any page.
* The frontend calls the backend logout endpoint.
* The backend invalidates the session.
* The browser removes authentication state.
* Reusing an old credential fails.

These flows are mandatory.

### Technical work

We will implement:

* centralized validation helpers;
* controlled field types;
* maximum and minimum lengths;
* username validation;
* email validation;
* consistent password validation;
* a local common-password list;
* protection against passwords derived directly from account details;
* consistent frontend and backend rules;
* controlled JSON error responses;
* verification-token expiration and one-time use;
* reset-token expiration and one-time use;
* secure session storage;
* server-side logout invalidation;
* session invalidation after password reset;
* secure authentication cookies;
* removal of authentication tokens from URLs;
* protection against OAuth-only accounts crashing password login;
* controlled SMTP failure handling.

### Not included

We will not implement:

* IP-based rate limiting;
* failed-login counters;
* account locking;
* resend-email cooldowns;
* forgot-password cooldowns;
* upload cooldowns;
* report cooldowns;
* attempt-tracking systems.

These are outside the required scope of the subject and are not critical for the agreed local school-project setup.

### Problems solved

* malformed values causing HTTP `500`;
* signup and backend password rules being inconsistent;
* weak six-word password blacklist;
* registration reporting success when email delivery fails;
* verification or reset links remaining usable incorrectly;
* sessions surviving logout;
* sessions surviving password reset;
* authentication credentials appearing in OAuth callback URLs;
* OAuth accounts causing local password-login errors;
* stack traces or database errors reaching the frontend.

### Completion gate

Registration, verification, login, logout, and password reset work without unhandled errors. Verification and reset links expire correctly, old sessions stop working after logout or password reset, and authentication credentials are not exposed in URLs or JavaScript-readable storage.

---

## Step 3 — Complete profile, age, preferences, location, fame, tags, and photos

This combines all profile-data work into one complete profile step.

The subject requires gender, sexual preferences, biography, reusable tags, up to five pictures, one profile picture, editable identity information, viewers, likers, fame rating, and location handling.

### User flow

After login, the user completes:

1. Birth date.
2. Gender.
3. One or more preferred genders.
4. Biography.
5. Interests selected from the fixed tag list.
6. Up to five photos.
7. One primary photo.
8. GPS location with consent or manual location.

The profile becomes complete immediately when all required information exists.

### Birth date and age

We will store:

```sql
birth_date DATE
```

The backend calculates age dynamically.

The public API returns:

```json
{
  "age": 24
}
```

It does not need to expose the exact birth date to another user.

This enables mandatory age sorting, filtering, and search.

### Gender model

```text
male
female
non-binary
```

Only one value can be selected.

### Sexual-preference model

The user selects one or more:

```text
male
female
non-binary
```

An empty selection means all three.

### Fixed reusable tags

We will preinsert exactly 20 tags in `schema.sql`:

```text
music
movies
gaming
books
travel
fitness
cooking
photography
art
technology
nature
hiking
pets
sports
dancing
fashion
coffee
vegan
anime
volunteering
```

The user can only select from these values.

The user cannot:

* create a custom tag;
* rename a tag;
* enter arbitrary tag text.

This makes validation, searching, and common-tag ranking simpler while still satisfying reusable interest tags.

### Tag database behavior

We will keep:

```text
tags
user_tags
```

`tags` contains the 20 predefined rows.

Updating interests will happen in one database transaction:

1. Validate every selected tag ID.
2. Remove the user’s old selections.
3. Insert the new selections.
4. Roll back everything if anything fails.

### Location behavior

#### GPS enabled

* user explicitly consents;
* browser sends coordinates;
* backend validates ranges;
* exact coordinates remain private;
* frontend shows only approximate location information.

#### GPS disabled

* user must enter a city or neighborhood;
* geocoding must produce valid coordinates;
* unresolved locations return a controlled error;
* matching does not accept an unusable location.

We will correctly handle coordinate values such as `0.0`.

### Fame rating

We will define one simple formula and use it everywhere.

Proposed structure:

```text
received likes
+ profile views
+ profile-completion value
```

One authoritative backend function will calculate it.

The rating updates after:

* like;
* unlike;
* view;
* profile-completion change;
* photo change;
* tag change.

### Photo behavior

We will implement:

* actual image-content validation;
* consistent accepted formats;
* random unique filenames;
* maximum five photos;
* exactly one primary photo when photos exist;
* transaction-safe primary-photo changes;
* physical-file deletion;
* cleanup after failed uploads;
* controlled size and pixel limits;
* server-side image re-encoding.

### Problems solved

* no age support;
* no bisexual/default-preference model;
* arbitrary profile enum values;
* custom or invalid tags;
* inconsistent fame formulas;
* stale fame rating;
* false GPS consent;
* invalid coordinates;
* exact coordinates exposed;
* partial tag updates;
* more than five photos after concurrent uploads;
* multiple or missing primary pictures;
* abandoned uploaded files;
* profile-completion warning remaining until reload.

### Completion gate

A user can fully complete and edit the profile, and the same completion status appears immediately in the API and frontend.

---

## Step 4 — Profile visits, likes, matches, blocks, reports, and presence

This creates one consistent social-interaction system before browse and chat use it.

The subject requires recorded visits, likes, mutual connections, unlike, report, block, fame display, online state, and last connection.

### Profile visit behavior

Every valid profile visit creates a separate history record:

```text
visit 1: Alex viewed Sara at 10:00
visit 2: Alex viewed Sara at 12:30
```

The second visit does not overwrite the first.

The profile owner can see:

* viewer;
* viewing date and time.

### Like and connection behavior

* A user cannot like themselves.
* A user without a profile picture cannot like.
* One user can like another user once.
* Two mutual likes create a connection.
* Unlike removes the current user’s like.
* If the users were connected, unlike disconnects them.
* Connected-user unlike produces the mandatory notification.
* Chat becomes unavailable after disconnect.

### Block behavior

A user can block another user.

After A blocks B:

* A cannot open B’s profile;
* B cannot open A’s profile;
* neither appears to the other in browse;
* neither appears to the other in search;
* neither can like the other;
* neither can chat with the other;
* neither can generate notifications for the other;
* future map, call, and date functionality is disabled between them.

Blocking deletes both current like rows so the users are disconnected immediately. It does not delete historical visits, reports, or notifications. Access and interaction remain disabled while the block exists.

### Unblock behavior

Because blocked profiles cannot be opened, we will add a small blocked-users settings page:

```text
/settings/blocked
```

The page shows users blocked by the current user and provides an **Unblock** button.

After unblock:

* the block row is removed;
* profiles may appear again if compatibility rules allow;
* both users remain unliked and disconnected;
* either user may create a new like under the normal interaction rules.

This page supports the requested unblock behavior, but it will not be presented as an official subject bonus.

### Report behavior

The profile contains one button:

```text
Report as fake account
```

There is:

* no popup;
* no reason selection;
* no optional message;
* no report categories.

The database uses a unique pair:

```text
(reporter_id, reported_id)
```

Rules:

* user cannot report themselves;
* the first click inserts one report;
* another click does not insert another row;
* duplicate attempts return a controlled message;
* reporting does not automatically block;
* blocking and reporting remain separate actions.

### Presence behavior

The user is online when at least one authenticated Socket.IO connection is active.

Examples:

```text
Tab 1 open + Tab 2 open = online
Tab 1 closes + Tab 2 open = still online
Both close = offline and last_seen updated
```

Login alone will not mark the account online.

### Problems solved

* overwritten visit history;
* likes without profile photos;
* duplicate likes;
* inconsistent connection state;
* blocked users creating notifications;
* no way to unblock;
* duplicate fake-account reports;
* report-reason complexity;
* stale online status;
* one closed tab incorrectly marking a user offline.

### Completion gate

A relationship-state test confirms the correct behavior for unrelated, liked, connected, disconnected, blocked, unblocked, and reported users.

---

## Step 5 — Generate the 500 profiles

The subject requires at least 500 distinct profiles in the evaluation database.

### Technical work

We will build one easy seed command that populates the clean database created from `schema.sql`.

It will generate:

* more than 500 unique users;
* verified accounts;
* complete profiles;
* varied birth dates and ages;
* all three genders;
* single and multiple sexual preferences;
* the 20 predefined tags;
* varied locations;
* usable coordinates;
* different photos;
* different fame values;
* controlled likes and matches;
* selected view history.

### Why it comes here

After Step 3 and Step 4, the final user/profile/relationship schema is stable enough to generate meaningful records.

The same seed data will support:

* browse ranking;
* search;
* map;
* chat;
* notifications;
* defense demonstration.

### Problems solved

* empty evaluation database;
* manually recreating accounts after every database reset;
* weak browse/search test data;
* inconsistent demonstration results.

### Completion gate

Resetting the database and running the seed command produces at least 500 valid complete profiles.

---

## Step 6 — Suggested browsing and advanced search

This merges browse and search backend/frontend work.

The subject requires suggested profiles based on compatibility, proximity, common tags, and fame, plus sorting and filtering. It separately requires advanced search using age, fame, location, and tags.

### Suggested browsing flow

1. User opens Discover.
2. Backend removes invalid candidates.
3. Backend checks mutual gender preference.
4. Backend calculates distance.
5. Backend counts shared tags.
6. Backend reads fame rating.
7. Results are intelligently ordered.
8. User can filter and sort.
9. User opens a profile.

### Candidate exclusions

Browse and search must exclude:

* current user;
* blocked users in both directions;
* incomplete profiles;
* incompatible profiles.

### Default suggested ranking

Proposed transparent order:

1. Same city or approximate area.
2. Shortest distance.
3. Highest number of shared tags.
4. Highest fame rating.

This is easier to test and explain than an unexplained artificial score.

### Browse sorting

Users can sort by:

* age;
* distance/location;
* fame rating;
* common-tag count.

### Browse filtering

Users can filter by:

* minimum and maximum age;
* maximum distance or selected location;
* minimum and maximum fame;
* one or more tags.

### Advanced search

The `/search` page will support:

* age range;
* fame range;
* location;
* one or multiple predefined tags;
* combined criteria;
* the same sorting fields;
* the same blocked-user and compatibility rules.

### Frontend work

We will create or correct:

```text
/browse
/search
```

Both will include:

* reusable profile cards;
* filter controls;
* sort controls;
* loading state;
* error state;
* empty state;
* pagination;
* mobile layout.

The current dashboard can remain as a separate dashboard if useful, but it must no longer pretend to be Discover.

### Problems solved

* missing browse endpoint;
* missing matching algorithm;
* `/browse` 404;
* `/search` 404;
* no age filtering;
* no location ranking;
* no tag ranking;
* no fame sorting;
* blocked users not excluded from results.

### Completion gate

Prepared seed profiles appear in a deterministic, explainable order under known filters.

---

## Step 7 — Complete public profiles, text chat, and notifications

This combines the final mandatory user interaction flow.

### Public profile

The public profile will show all available non-sensitive information:

* username;
* first and last name;
* age;
* gender;
* sexual preferences;
* biography;
* selected tags;
* photos;
* approximate location;
* fame rating;
* online or last-seen state;
* whether the user liked the viewer;
* whether they are connected.

It will not expose:

* email;
* password data;
* exact birth date;
* exact coordinates;
* sessions or internal IDs that are unnecessary.

The subject requires all available profile information except email and password.

### Chat flow

1. Two users mutually like each other.
2. They become connected.
3. They can open a conversation.
4. Messages are saved in PostgreSQL.
5. Socket.IO delivers messages in real time.
6. Offline users receive stored messages after reconnect.
7. Unread messages are visible globally.
8. Unlike or block disables sending immediately.

### Chat technical design

We will implement:

* `/messages`;
* connected-user list;
* message-history endpoint;
* send-message endpoint;
* message length validation;
* read/unread state;
* pagination;
* Socket.IO delivery;
* reconnect synchronization;
* duplicate-send prevention;
* connection checks on every message;
* safe text rendering.

PostgreSQL remains the source of truth. Socket.IO is the real-time delivery mechanism.

### Notification events

The application will support all five mandatory events:

1. Received like.
2. Profile viewed.
3. Message received.
4. Mutual like.
5. Connected user unliked.

These are explicitly required.

### Notification reliability

We will implement:

* persisted notifications;
* authenticated Socket.IO delivery;
* unread count from every protected page;
* reconnect refresh;
* small HTTP recovery polling if the socket is unavailable;
* central block checks;
* central disconnect checks;
* mark-one-read;
* mark-all-read;
* proper handling when a read request fails.

### Problems solved

* incomplete public-profile information;
* `/messages` 404;
* messages table without functional chat;
* no message notification;
* disconnected users continuing to chat;
* blocked users generating notifications;
* unread count becoming incorrect;
* websocket interruption causing permanent missed notifications.

### Completion gate

Two users can complete the full mandatory sequence:

```text
discover → profile view → like → match → chat → message notification → unlike → chat disabled
```

---

# Official bonuses before final testing

The subject identifies five bonus categories, and they are only evaluated when the mandatory part is complete and functioning correctly.

We will implement the bonuses before the final full cleanup and defense test, as requested. However, the mandatory behavior must still be locally verified before bonus work is allowed to modify it.

---

## Step 8 — OAuth, advanced gallery editing, and interactive map bonuses

This merges three official bonuses that connect directly to existing authentication, photos, and location features.

### Part A — Google and 42 OAuth

We will complete the existing implementation:

* secure provider state;
* no tokens in URLs;
* same secure session system as local login;
* safe creation of new users;
* safe linking of existing accounts;
* unique provider identities;
* provider timeout handling;
* denied-login handling;
* OAuth-only user behavior;
* Google and 42 tested independently.

### Part B — Drag-and-drop gallery and image editing

The existing five-photo system will gain:

* drag-and-drop upload;
* image preview;
* crop;
* 90-degree rotation;
* a small controlled filter set;
* secure server-side validation;
* server-side re-encoding;
* continued five-photo enforcement;
* continued one-primary-photo enforcement.

The mandatory photo behavior stays unchanged underneath the bonus editor.

### Part C — Interactive user map

The map will show compatible browse/search profiles.

It will include:

* current-user approximate position;
* candidate markers;
* filters shared with browse/search;
* blocked-user exclusion;
* consent handling;
* manual-location fallback;
* mobile support.

Exact private coordinates will not be sent to other users. Markers will be approximated for privacy.

### Problems solved or features added

* incomplete OAuth bonus;
* insecure OAuth callback;
* missing drag-and-drop gallery;
* missing crop/rotate/filter tools;
* missing interactive map;
* map privacy rules.

### Completion gate

All three bonuses reuse the existing mandatory authorization, location, and upload rules without bypassing them.

---

## Step 9 — Audio/video calling and date scheduling bonuses

### Part A — Audio/video call flow

1. Connected user starts a call request.
2. Recipient receives a call invitation.
3. Recipient accepts or declines.
4. Browser requests microphone/camera access.
5. WebRTC establishes the media connection.
6. Either user can hang up.
7. Unlike or block ends the call.

### Technical work

We will implement:

* WebRTC media;
* Socket.IO signaling;
* offers and answers;
* ICE candidate exchange;
* call invitation;
* accept and decline;
* microphone permission handling;
* camera permission handling;
* unavailable-device handling;
* call termination;
* connection authorization;
* block/unlike enforcement.

We will build audio first and then add video using the same call system.

### Part B — Real-life date/event scheduling

Connected users can:

* propose a date;
* choose date and time;
* add a location;
* add an optional note;
* accept;
* decline;
* cancel;
* see upcoming proposals.

### Technical work

We will add:

* event table in `schema.sql`;
* proposer and recipient;
* status values;
* UTC date/time storage;
* create endpoint;
* respond endpoint;
* cancel endpoint;
* upcoming-events interface;
* event notifications;
* connected-user authorization;
* block/unlike restrictions.

Existing events can remain visible as history after disconnection, but no new changes are allowed while the users are disconnected or blocked.

### Completion gate

Only connected, non-blocked users can call or organize events together.

---

## Step 10 — Complete testing, security review, cleanup, and defense preparation

This is the final large testing and cleaning stage after mandatory and bonus implementation.

### Automated and technical checks

We will test:

* clean database creation from `schema.sql`;
* 500-profile seeding;
* malformed JSON;
* invalid field types;
* length validation;
* SQL injection attempts;
* HTML and JavaScript injection;
* password storage;
* session revocation;
* verification and reset-token reuse;
* identifier-based request cooldowns;
* unauthorized profile access;
* block and unblock;
* duplicate reports;
* duplicate likes;
* photo count concurrency;
* multiple primary-photo attempts;
* invalid uploads;
* message authorization;
* notification suppression;
* WebSocket reconnection;
* OAuth provider failures;
* map privacy;
* audio/video authorization;
* date/event authorization.

Security, proper form validation, safe uploads, and SQL-injection protection are mandatory evaluation concerns.

### Browser and responsive testing

The complete application will be tested in:

* latest Chrome;
* latest Firefox;
* desktop layout;
* tablet layout;
* mobile layout.

The subject requires Chrome and Firefox compatibility, a structured layout, and mobile-friendly behavior.

### Complete manual defense flow

1. Reset database from `schema.sql`.
2. Generate 500+ profiles.
3. Register a new user.
4. Verify the email.
5. Log in.
6. Complete the profile.
7. Select fixed tags.
8. Upload five photos.
9. Set the primary photo.
10. Test GPS consent.
11. Test manual location.
12. Browse suggested profiles.
13. Sort and filter.
14. Use advanced search.
15. View profiles.
16. Check visit history.
17. Like a user.
18. Create a mutual match.
19. Chat.
20. Receive all five notification types.
21. Unlike and confirm chat is disabled.
22. Block and confirm full exclusion.
23. Unblock through the blocked-users page.
24. Report once and confirm duplicate prevention.
25. Log out and confirm session revocation.
26. Test Google login.
27. Test 42 login.
28. Edit a gallery image.
29. Use the interactive map.
30. Start an audio/video call.
31. Propose and respond to a date.
32. Check browser console and server logs.

### Cleanup work

After functionality passes:

* remove dead routes;
* remove unused functions;
* remove duplicate fame logic;
* remove debug prints;
* remove obsolete token code;
* remove broken navigation links;
* remove abandoned test files;
* normalize error messages;
* document setup and defense commands;
* confirm no secrets are tracked.

### Completion gate

The project is ready only when:

* all mandatory features pass;
* all bonuses work without breaking mandatory features;
* no known security breach exists;
* no unexpected client or server error exists;
* clean setup works;
* at least 500 profiles exist;
* Chrome and Firefox pass;
* mobile layout passes.

---

# Final reduced step index

```text
01 Secure baseline, configuration, and schema workflow
02 Authentication, validation, sessions, and email
03 Complete profile, age, preferences, location, fame, tags, and photos
04 Visits, likes, matches, block/unblock, reports, and presence
05 Generate 500 profiles
06 Suggested browsing and advanced search
07 Public profiles, text chat, and notifications
08 OAuth, gallery editing, and interactive map bonuses
09 Audio/video and date-scheduling bonuses
10 Final tests, security review, cleanup, and defense
```

# Final agreed technical choices

| Area                        | Revised choice                                   |
| --------------------------- | ------------------------------------------------ |
| Database changes            | Edit `schema.sql`, then recreate the database    |
| Migration framework         | None                                             |
| Rate limiting               | No IP-based logic                                |
| Simple abuse control        | Username, email, or authenticated-user cooldowns |
| Gender                      | Single choice: male, female, non-binary          |
| Sexual preference           | Multi-select: male, female, non-binary           |
| Unspecified preference      | All three genders                                |
| Tags                        | Fixed list of 20 predefined reusable tags        |
| Custom tags                 | Not allowed                                      |
| Block                       | Mutual invisibility and interaction suppression  |
| Unblock                     | Available from `/settings/blocked`               |
| Block data behavior         | Keep history; disable access while blocked       |
| Fake-account report         | One button, one database record per pair         |
| Report reason               | None                                             |
| Duplicate report            | Rejected without another insertion               |
| Final comprehensive testing | After all bonuses                                |
| Per-step verification       | Still required before moving forward             |
| Official bonuses            | All five implemented                             |
