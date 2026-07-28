# Step 3 — Complete profile, age, preferences, location, fame, tags, and photos

This step implements the approved profile model: birth date and calculated age, controlled gender and preferences, fixed reusable tags, privacy-safe location, one fame-rating formula, and secure five-photo management.

## A. Files

[Download the Step 3 patch](sandbox:/mnt/data/matcha_step3.patch)

[Download the complete Step 3 project](sandbox:/mnt/data/matcha-step3-updated.tar.gz)

The real `backend/.env` is not included or modified.

The patch assumes the previous logout-test correction is already present. The complete archive contains that correction.

## B. Subject requirement

The subject requires users to provide and edit:

* gender;
* sexual preferences;
* biography;
* reusable interests;
* up to five photos with one profile picture;
* location through GPS consent or manual entry;
* a consistent fame rating.

Age is also needed for mandatory browse and search sorting and filtering.

## C. Previous application flow

Before this step:

1. There was no birth date or age.
2. Gender accepted unsupported values such as `other`.
3. Sexual preference was one orientation string.
4. Users could create arbitrary tags.
5. Tag updates used multiple separately committed queries.
6. `"gpsConsent": "false"` became `True`.
7. Invalid coordinates could be stored.
8. Manual locations succeeded even when geocoding failed.
9. Public responses exposed exact latitude and longitude.
10. Photo validation trusted extensions and used predictable filenames.
11. Concurrent uploads could exceed five photos.
12. Deleted photo files remained on disk.
13. Two different fame formulas existed.
14. Profile completion could remain stale until reload.

## D. Technical concepts

### Birth date instead of stored age

Age changes automatically every birthday. Storing `birth_date` lets the backend calculate the correct age whenever it builds the response.

Public users receive:

```json
{
  "age": 25
}
```

Only the authenticated owner receives:

```json
{
  "birthDate": "2001-04-17"
}
```

### Preference arrays

Preferences are now stored as a PostgreSQL array containing one or more of:

```text
male
female
non-binary
```

An empty submitted selection becomes all three values, representing the subject’s default bisexual behavior.

Mutual compatibility itself will be applied during Step 6 browse/search.

### Database transactions

Replacing tags now happens as one operation:

1. Validate all selected tag IDs.
2. Delete previous relationships.
3. Insert the new relationships.
4. Roll back everything if any operation fails.

A failed update therefore cannot leave half of the requested tags saved.

### Advisory locking for photos

PostgreSQL locks photo modifications for one user during the transaction.

When two uploads arrive simultaneously, the second transaction waits for the first before counting photos. It cannot independently see an outdated count and insert a sixth photo.

### Image re-encoding

Uploaded files are decoded through Pillow and then saved again under a random filename.

This:

* verifies actual image content;
* rejects GIF and non-image data;
* removes original metadata;
* prevents filename collisions;
* limits dimensions and pixel count;
* accepts only PNG and JPEG output.

## E. Technical design

### Backend

The backend now:

* validates birth dates;
* calculates age dynamically;
* restricts gender values;
* accepts preference arrays;
* normalizes empty preferences to all genders;
* limits biographies to 500 characters;
* validates tag IDs;
* updates tags transactionally;
* validates GPS consent as an actual Boolean;
* validates coordinate types and ranges;
* rejects unresolved manual locations;
* keeps exact coordinates private;
* re-encodes images;
* uses random upload names;
* deletes physical files;
* protects the five-photo limit transactionally;
* guarantees at most one primary image;
* refreshes profile completion and fame immediately.

### Frontend

The profile form now contains:

* birth-date input;
* displayed calculated age;
* `male`, `female`, and `non-binary` gender choices;
* multi-select preference buttons;
* biography character counter;
* exactly 20 selectable interests;
* PNG/JPEG-only photo input;
* clearer location privacy information.

### Error behavior

Examples:

```json
{
  "message": "Gender must be male, female, or non-binary"
}
```

```json
{
  "message": "gpsConsent must be true or false"
}
```

```json
{
  "message": "Location could not be found. Enter a city or neighborhood."
}
```

```json
{
  "message": "Upload a valid PNG or JPEG image"
}
```

## F. Database changes

`schema.sql` remains the single source of truth; no migration system is introduced.

### `users.birth_date`

```sql
birth_date DATE
```

The database stores a date. The backend calculates age.

### `users.gender`

```sql
gender VARCHAR(20)
CHECK (
    gender IS NULL
    OR gender IN ('male', 'female', 'non-binary')
)
```

### `users.sexual_preferences`

```sql
sexual_preferences TEXT[] NOT NULL
DEFAULT ARRAY['male', 'female', 'non-binary']::TEXT[]
```

The check ensures:

* one to three values;
* only approved gender values.

### `users.biography`

Changed to:

```sql
biography VARCHAR(500)
```

### Fixed tags

`schema.sql` inserts exactly:

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

Custom tag creation has been removed.

### Profile indexes

Added:

```text
users.birth_date
users.gender
users.latitude + users.longitude
```

These support later age, compatibility and location queries.

### Photo position

Photo positions are restricted to:

```text
0–4
```

The existing partial unique index still permits at most one primary photo for each user.

## G. Fame-rating formula

There is now one authoritative formula:

```text
received likes × 3
+ profile views × 0.5
+ profile-completion points
```

Profile-completion points total a maximum of 10:

| Field              | Points |
| ------------------ | -----: |
| Birth date         |      1 |
| Gender             |      1 |
| Preferences        |      1 |
| Biography          |      2 |
| Interests          |      1 |
| Photo              |      2 |
| Usable coordinates |      2 |

The rating is recalculated after:

* profile information changes;
* tag changes;
* photo upload or deletion;
* location changes;
* likes;
* unlikes;
* profile views.

## H. Exact files

### Created

```text
backend/tests/test_profile_models.py
backend/tests/test_profile_routes.py
backend/tests/test_profile_validation.py
```

### Edited

```text
README.md
backend/schema.sql
backend/app/config.py
backend/app/models.py
backend/app/profile.py
backend/app/utils.py
backend/app/validation.py
frontend/my-app/app/services/api.ts
frontend/my-app/app/types/index.ts
frontend/my-app/app/components/ProfileForm.tsx
frontend/my-app/app/components/ProfileTagsInput.tsx
frontend/my-app/app/components/ProfilePhotos.tsx
frontend/my-app/app/components/ProfileLocation.tsx
frontend/my-app/app/(dashboard)/users/[id]/page.tsx
```

No files are deleted.

## I. Apply the patch

From the project root:

```bash
git status --short
```

Preserve local changes:

```bash
git diff > before-step3-local-changes.patch
```

Test the patch:

```bash
patch --dry-run -p1 < /path/to/matcha_step3.patch
```

Apply it only when the dry run shows no failed hunks:

```bash
patch -p1 < /path/to/matcha_step3.patch
```

Inspect everything:

```bash
git diff --stat
git diff
```

## J. Required database reset

This step changes existing column types. Running only `python initdb.py` cannot modify tables already created with older definitions.

The reset deletes all database data.

Stop Flask first with `Ctrl+C`.

From `backend/`:

```bash
source venv/bin/activate
```

Confirm Python 3:

```bash
python --version
which python
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

Remove files belonging to the deleted database accounts:

```bash
mkdir -p uploads
find uploads -mindepth 1 -maxdepth 1 -type f -delete
```

Your current test account will be removed and must be registered again. The 500-profile seed command belongs to Step 5.

## K. Verify the schema

Confirm the new columns:

```bash
docker compose exec db sh -lc \
'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = '\''users'\''
  AND column_name IN (
      '\''birth_date'\'',
      '\''gender'\'',
      '\''sexual_preferences'\'',
      '\''biography'\''
  )
ORDER BY column_name;
"'
```

Confirm exactly 20 tags:

```bash
docker compose exec db sh -lc \
'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT COUNT(*) AS tag_count FROM tags;
"'
```

Expected:

```text
tag_count
---------
20
```

Display them:

```bash
docker compose exec db sh -lc \
'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT id, name FROM tags ORDER BY name;
"'
```

## L. Tests

From `backend/` with `(venv)` visible:

```bash
python -m unittest discover -s tests -v
```

Expected:

```text
Ran 40 tests

OK
```

The new tests verify:

* future birth dates are rejected;
* only approved genders are accepted;
* empty preferences become all genders;
* invalid preferences are rejected;
* `0.0` coordinates remain valid;
* exact coordinates are absent from public responses;
* birth date is available only in the private response;
* the fame formula is consistent;
* malformed GPS consent is rejected;
* unresolved manual locations are rejected;
* invalid tag IDs do not replace existing tags;
* image content is validated;
* random image filenames are generated;
* invalid image bytes are rejected;
* upload path traversal is rejected.

Eventlet’s deprecation warning may still appear. It is not a test failure.

## M. Frontend checks

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

I verified:

* the patch applies cleanly;
* all Python files compile;
* all TypeScript/TSX files pass syntax transpilation;
* shell scripts pass syntax checks;
* `.env` is absent from both artifacts.

I could not execute the complete Python test suite or Next.js build in this environment because project dependencies and PostgreSQL were unavailable, so runtime success still depends on your output.

## N. Manual verification

### Basic profile

1. Register and verify a new user.
2. Log in.
3. Open `/profile`.
4. Enter a birth date.
5. Select `non-binary`.
6. Select multiple preferred genders.
7. Enter a biography.
8. Save.

Expected:

* age appears after saving;
* preferences remain selected;
* no `other`, `heterosexual`, `homosexual`, or `bisexual` database values are used;
* fame changes immediately.

### Fixed tags

1. Open Interests.
2. Confirm only the 20 predefined buttons appear.
3. Select multiple tags.
4. Reload.

Expected:

* selections remain;
* there is no custom-text input;
* `user_tags` contains only existing tag IDs.

### Location negative tests

Through the browser console or an API client, submit:

```json
{
  "gpsConsent": "false",
  "locationName": "Rabat"
}
```

Expected HTTP `400`:

```json
{
  "message": "gpsConsent must be true or false"
}
```

Try:

```json
{
  "gpsConsent": true,
  "latitude": 999,
  "longitude": 0
}
```

Expected HTTP `400`.

Enter an unresolvable manual location.

Expected:

* controlled error;
* previous location remains unchanged.

### Coordinate privacy

Use two accounts.

Open the other account’s public profile response:

```text
GET /api/users/<id>
```

Expected:

```json
{
  "location": {
    "name": "Neighborhood, City"
  }
}
```

It must not contain:

```text
latitude
longitude
birthDate
email
```

The current user’s private endpoint may contain exact coordinates:

```text
GET /api/profile
```

### Photos

1. Upload a PNG.
2. Upload a JPEG.
3. Try a GIF.
4. Try a text file renamed to `.jpg`.
5. Upload five valid images.
6. Attempt a sixth.
7. Change the primary photo.
8. Delete the primary photo.

Expected:

* PNG and JPEG succeed;
* GIF and invalid data fail;
* generated filenames are random;
* the sixth upload fails;
* only one photo is primary;
* deleting the primary promotes another photo;
* the deleted physical file disappears from `backend/uploads`;
* completion and fame update without reloading.

This step does not yet implement browse/search matching, visit-history restructuring, blocks/reports restructuring, chat, or full notification reliability. Those remain in their approved later steps.













----------



when I upload a text file with .jpg extentieen it worked in frentend it give me



Upload a valid PNG or JPEG image



but in consl



POST http://localhost:5000/api/profile/photos 400 (BAD REQUEST)

dispatchXhrRequest @ xhr.js:226

xhr @ xhr.js:17

dispatchRequest @ dispatchRequest.js:48

Promise.then (async)

_request @ Axios.js:198

request @ Axios.js:41

httpMethod @ Axios.js:259

wrap @ bind.js:12

uploadPhoto @ api.ts:166

handleFileSelect @ ProfilePhotos.tsx:53

executeDispatch @ react-dom-client.development.js:20610

runWithFiberInDEV @ react-dom-client.development.js:986

processDispatchQueue @ react-dom-client.development.js:20660

(anonymous) @ react-dom-client.development.js:21234

batchedUpdates$1 @ react-dom-client.development.js:3377

dispatchEventForPluginEventSystem @ react-dom-client.development.js:20814

dispatchEvent @ react-dom-client.development.js:25817

dispatchDiscreteEvent @ react-dom-client.development.js:25785

Show 15 more frames

Show less