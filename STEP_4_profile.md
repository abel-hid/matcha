# Step 4 correction — Show complete public-profile information

You are right. Empty fields should not disappear because that makes the profile look broken or incomplete without explaining why.

This correction moves only the **public-profile display** portion of Step 7 forward. It does not begin chat or notification work. The approved public profile includes all non-sensitive information while excluding email, exact birth date and exact coordinates.

## Files

[Download the public-profile correction patch](sandbox:/mnt/data/matcha_step4_public_profile_info_fix.patch)

[Download the corrected complete Step 4 project](sandbox:/mnt/data/matcha-step4-public-profile-info-updated.tar.gz)

The patch applies on top of the latest Step 4 relationship correction.

## New profile display

The page now always shows:

* first and last name;
* username;
* all photos;
* age;
* gender;
* sexual preferences;
* approximate location;
* online or last-seen state;
* fame rating;
* biography;
* interests;
* profile-completion status;
* like and match relationship state.

When information is absent, the page displays:

```text
Not provided
```

For example:

```text
Age
Not provided

Gender
Not provided

Location
Not provided

Biography
Not provided

Interests
Not provided
```

When the profile is incomplete, it also displays:

```text
Profile incomplete

Missing information is shown below instead of being hidden.
```

The photo section continues to display:

```text
No photos yet
```

when the user has not uploaded a picture.

## Privacy behavior

The page still does **not** display:

* email;
* password data;
* exact birth date;
* latitude or longitude;
* authentication sessions;
* internal security information.

Age remains calculated by the backend rather than exposing the birth date. Approximate location remains visible without exposing private coordinates.

## Exact file changed

```text
frontend/my-app/app/(dashboard)/users/[id]/page.tsx
```

No backend file changes were required because the public API already returns all the necessary non-sensitive fields.

No schema change is involved, so **do not reset the database**.

## Apply the patch

From the project root:

```bash
patch --dry-run -p1 < /path/to/matcha_step4_public_profile_info_fix.patch
```

Expected:

```text
checking file 'frontend/my-app/app/(dashboard)/users/[id]/page.tsx'
```

Apply it:

```bash
patch -p1 < /path/to/matcha_step4_public_profile_info_fix.patch
```

## Frontend verification

From:

```text
frontend/my-app
```

run:

```bash
npm run lint
```

Then:

```bash
npm run build
```

Restart Next.js:

```bash
npm run dev
```

I verified that:

* the patch applies cleanly;
* the changed TSX file passes TypeScript syntax transpilation;
* `.env` is not included in either artifact.

I have not executed the complete Next.js lint or build in your environment.

## Manual test

Open a complete user:

```text
http://localhost:3000/users/USER_ID
```

Expected:

* every public field appears;
* no duplicate age or location information;
* interests and biography appear in their own sections;
* relationship actions continue working.

Open an incomplete user.

Expected:

* an incomplete-profile notice appears;
* missing fields display `Not provided`;
* missing fields are not silently hidden;
* the page does not crash when arrays are empty or values are `null`;
* no unexpected browser-console error appears.

After this correction passes, Step 4 can be considered ready for final verification before Step 5.
