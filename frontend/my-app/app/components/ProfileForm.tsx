'use client';

import React, { useEffect, useState } from 'react';
import { profileService } from '@/app/services/api';
import { useAuth } from '@/app/context/AuthContext';
import { User } from '@/app/types';
import ProfilePhotos from './ProfilePhotos';
import ProfileTagsInput from './ProfileTagsInput';
import ProfileLocation from './ProfileLocation';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

const GENDER_OPTIONS = [
  { value: '', label: 'Select…' },
  { value: 'male', label: 'Male' },
  { value: 'female', label: 'Female' },
  { value: 'non-binary', label: 'Non-binary' },
] as const;

const PREFERENCE_OPTIONS = [
  { value: 'male', label: 'Men' },
  { value: 'female', label: 'Women' },
  { value: 'non-binary', label: 'Non-binary people' },
] as const;

const MISSING_FIELD_LABELS: Record<string, string> = {
  firstName: 'first name',
  lastName: 'last name',
  email: 'email',
  birthDate: 'birth date',
  gender: 'gender',
  sexualPreferences: 'sexual preferences',
  biography: 'biography',
  tags: 'at least one interest',
  profilePicture: 'a primary profile photo',
  location: 'location',
};

const inputClasses =
  'mt-1.5 w-full rounded-lg border border-[#332844] bg-[#1E1728] px-4 py-2.5 text-[#F5EFE9] placeholder-[#6E6180] outline-none transition focus:border-[#FF4D7E] focus:ring-2 focus:ring-[#FF4D7E]/30';

const labelClasses = 'block text-xs font-medium uppercase tracking-wide text-[#9C8FA8]';

type Gender = 'male' | 'female' | 'non-binary';

const MIN_PROFILE_AGE = 18;
const MAX_PROFILE_AGE = 80;

function formatDateInput(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');

  return `${year}-${month}-${day}`;
}

function dateYearsAgo(years: number) {
  const today = new Date();
  const targetYear = today.getFullYear() - years;
  const targetMonth = today.getMonth();
  const lastDay = new Date(targetYear, targetMonth + 1, 0).getDate();

  return new Date(
    targetYear,
    targetMonth,
    Math.min(today.getDate(), lastDay)
  );
}

function calculateProfileAge(value: string) {
  const [year, month, day] = value.split('-').map(Number);

  if (!year || !month || !day) {
    return null;
  }

  const today = new Date();
  let age = today.getFullYear() - year;

  if (
    today.getMonth() + 1 < month
    || (today.getMonth() + 1 === month && today.getDate() < day)
  ) {
    age -= 1;
  }

  return age;
}

const youngestAllowedBirthDate = formatDateInput(
  dateYearsAgo(MIN_PROFILE_AGE)
);

const oldestBirthDateBoundary = dateYearsAgo(MAX_PROFILE_AGE + 1);
oldestBirthDateBoundary.setDate(oldestBirthDateBoundary.getDate() + 1);

const oldestAllowedBirthDate = formatDateInput(
  oldestBirthDateBoundary
);

export default function ProfileForm() {
  const { user: authUser, updateUser } = useAuth();
  const [profile, setProfile] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [emailChangeNotice, setEmailChangeNotice] = useState(false);

  useEffect(() => {
    profileService
      .getProfile()
      .then((data) => {
        setProfile(data.user);
        updateUser(data.user);
      })
      .catch((err: any) => setError(err.response?.data?.message || 'Failed to load your profile.'))
      .finally(() => setLoading(false));
  }, [updateUser]);

  const applyProfileUpdate = (updatedProfile: User) => {
    setProfile(updatedProfile);
    updateUser(updatedProfile);
  };

  const updateField = <K extends keyof User>(key: K, value: User[K]) => {
    setProfile((previous) => (previous ? { ...previous, [key]: value } : previous));
    setSaved(false);
    setError('');
  };

  const togglePreference = (preference: Gender) => {
    if (!profile) return;

    const selected = profile.sexualPreferences.includes(preference);
    if (selected && profile.sexualPreferences.length === 1) {
      setError('Select at least one sexual preference.');
      return;
    }

    const nextPreferences = selected
      ? profile.sexualPreferences.filter((value) => value !== preference)
      : [...profile.sexualPreferences, preference];
    updateField('sexualPreferences', nextPreferences);
  };

  const validateUserInformation = () => {
    if (!profile) return false;

    if (!profile.firstName.trim()) {
      setError('First name is required.');
      return false;
    }
    if (!profile.lastName.trim()) {
      setError('Last name is required.');
      return false;
    }
    if (!profile.email.trim()) {
      setError('Email is required.');
      return false;
    }
    if (!profile.birthDate) {
      setError('Birth date is required.');
      return false;
    }

    const age = calculateProfileAge(profile.birthDate);
    if (age === null || age < MIN_PROFILE_AGE || age > MAX_PROFILE_AGE) {
      setError(
        `Age must be between ${MIN_PROFILE_AGE} and ${MAX_PROFILE_AGE} years old.`
      );
      return false;
    }
    if (!profile.gender) {
      setError('Gender is required.');
      return false;
    }
    if (profile.sexualPreferences.length === 0) {
      setError('Select at least one sexual preference.');
      return false;
    }
    if (!profile.biography?.trim()) {
      setError('Biography is required.');
      return false;
    }

    return true;
  };

  const handleSaveBasics = async () => {
    if (!profile || !validateUserInformation()) return;

    setSaving(true);
    setError('');
    setSaved(false);
    setEmailChangeNotice(false);
    try {
      const data = await profileService.updateProfile({
        firstName: profile.firstName,
        lastName: profile.lastName,
        email: profile.email,
        birthDate: profile.birthDate ?? '',
        gender: profile.gender ?? '',
        sexualPreferences: profile.sexualPreferences,
        biography: profile.biography ?? '',
      });
      applyProfileUpdate(data.user);
      setSaved(true);
      if (data.emailChanged) {
        setEmailChangeNotice(true);
      }
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to save your user information.');
    } finally {
      setSaving(false);
    }
  };

  const handleTagsChange = async (tagIds: number[]) => {
    const data = await profileService.setMyTags(tagIds);
    applyProfileUpdate(data.user);
  };

  if (loading) {
    return <div className="min-h-screen bg-[#15101C]" />;
  }

  if (!profile) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#15101C] px-6">
        <p className="text-sm text-[#FF8A80]">{error || 'Could not load your profile.'}</p>
      </div>
    );
  }

  const missingLabels = profile.missingProfileFields
    .map((field) => MISSING_FIELD_LABELS[field] || field)
    .join(', ');

  return (
    <div className="min-h-screen bg-[#15101C] px-6 py-12">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 flex items-start justify-between">
          <div>
            <h1 className="font-serif text-3xl text-[#F5EFE9]">Your profile</h1>
            <p className="mt-1 text-sm text-[#9C8FA8]">
              {authUser?.username && `@${authUser.username}`}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs uppercase tracking-wide text-[#9C8FA8]">Fame rating</p>
            <p className="font-serif text-2xl text-[#F2C879]">{profile.fameRating ?? 0}</p>
          </div>
        </div>

        {!profile.isProfileComplete && (
          <div className="mb-6 rounded-lg border border-[#FF4D7E]/30 bg-[#1E1728] px-4 py-3">
            <p className="text-sm font-medium text-[#FF8FAE]">Complete your profile to continue</p>
            <p className="mt-1 text-xs leading-relaxed text-[#9C8FA8]">
              Your account stays private and the rest of Matcha remains unavailable until every
              required field is complete.
            </p>
            {missingLabels && (
              <p className="mt-2 text-xs text-[#C8BCCF]">Still required: {missingLabels}.</p>
            )}
          </div>
        )}

        <div className="space-y-8">
          <section>
            <h2 className="mb-3 font-serif text-lg text-[#F5EFE9]">Photos</h2>
            <ProfilePhotos
              photos={profile.photos}
              apiBaseUrl={API_BASE_URL}
              onChange={applyProfileUpdate}
            />
          </section>

          <section>
            <h2 className="mb-3 font-serif text-lg text-[#F5EFE9]">User information</h2>
            <div className="space-y-4 rounded-lg border border-[#332844] bg-[#1E1728]/50 p-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className={labelClasses}>First name</label>
                  <input
                    type="text"
                    value={profile.firstName}
                    onChange={(event) => updateField('firstName', event.target.value)}
                    required
                    maxLength={50}
                    className={inputClasses}
                  />
                </div>
                <div>
                  <label className={labelClasses}>Last name</label>
                  <input
                    type="text"
                    value={profile.lastName}
                    onChange={(event) => updateField('lastName', event.target.value)}
                    required
                    maxLength={50}
                    className={inputClasses}
                  />
                </div>
              </div>

              <div>
                <label className={labelClasses}>Email</label>
                <input
                  type="email"
                  value={profile.email}
                  onChange={(event) => updateField('email', event.target.value)}
                  required
                  maxLength={100}
                  className={inputClasses}
                />
                <p className="mt-1 text-xs text-[#6E6180]">
                  Changing your email will require re-verification.
                </p>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className={labelClasses}>Birth date</label>
                  <input
                    type="date"
                    value={profile.birthDate || ''}
                    onChange={(event) => updateField('birthDate', event.target.value)}
                    required
                    min={oldestAllowedBirthDate}
                    max={youngestAllowedBirthDate}
                    className={inputClasses}
                  />
                  {profile.age !== null && (
                    <p className="mt-1 text-xs text-[#6E6180]">Current age: {profile.age}</p>
                  )}
                  <p className="mt-1 text-xs text-[#6E6180]">
                    You must be between 18 and 80 years old.
                  </p>
                </div>
                <div>
                  <label className={labelClasses}>Gender</label>
                  <select
                    value={profile.gender || ''}
                    onChange={(event) => updateField(
                      'gender',
                      event.target.value ? event.target.value as Gender : null
                    )}
                    required
                    className={inputClasses}
                  >
                    {GENDER_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className={labelClasses}>Sexual preferences</label>
                <div className="mt-2 flex flex-wrap gap-2">
                  {PREFERENCE_OPTIONS.map((option) => {
                    const selected = profile.sexualPreferences.includes(option.value);
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => togglePreference(option.value)}
                        aria-pressed={selected}
                        className={`rounded-lg border px-3 py-2 text-sm transition ${
                          selected
                            ? 'border-[#FF4D7E] bg-[#FF4D7E]/15 text-[#FF8FAE]'
                            : 'border-[#332844] bg-[#1E1728] text-[#9C8FA8]'
                        }`}
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
                <p className="mt-1.5 text-xs text-[#6E6180]">
                  Select at least one. All three selections represent interest in all genders.
                </p>
              </div>

              <div>
                <label className={labelClasses}>Biography</label>
                <textarea
                  value={profile.biography || ''}
                  onChange={(event) => updateField('biography', event.target.value)}
                  rows={4}
                  required
                  maxLength={500}
                  className={inputClasses + ' resize-none'}
                  placeholder="Tell people a bit about yourself…"
                />
                <p className="mt-1 text-right text-xs text-[#6E6180]">
                  {(profile.biography || '').length}/500
                </p>
              </div>

              {error && (
                <div className="rounded-lg border border-[#FF6B6B]/30 bg-[#FF6B6B]/10 px-3 py-2 text-sm text-[#FF8A80]">
                  {error}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-3 border-t border-[#332844] pt-4">
                <button
                  type="button"
                  onClick={handleSaveBasics}
                  disabled={saving}
                  className="rounded-lg bg-[#FF4D7E] px-6 py-2.5 text-sm font-medium text-[#15101C] transition hover:bg-[#FF6A93] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving ? 'Saving…' : 'Save user information'}
                </button>
                {saved && !emailChangeNotice && (
                  <span className="text-sm text-[#F2C879]">Saved.</span>
                )}
              </div>

              {emailChangeNotice && (
                <div className="rounded-lg border border-[#F2C879]/30 bg-[#F2C879]/10 px-4 py-3 text-sm text-[#F2C879]">
                  Your email was updated. Please check your inbox at <strong>{profile.email}</strong> and
                  verify your new address — you won&apos;t be able to log in until you do.
                </div>
              )}
            </div>
          </section>

          <section>
            <h2 className="mb-3 font-serif text-lg text-[#F5EFE9]">Interests</h2>
            <ProfileTagsInput value={profile.tags} onChange={handleTagsChange} />
          </section>

          <section>
            <h2 className="mb-3 font-serif text-lg text-[#F5EFE9]">Location</h2>
            <ProfileLocation
              location={
                profile.location
                  ? {
                      name: profile.location.name ?? null,
                      latitude: profile.location.latitude ?? null,
                      longitude: profile.location.longitude ?? null,
                    }
                  : null
              }
              gpsConsent={Boolean(profile.gpsConsent)}
              onChange={applyProfileUpdate}
            />
          </section>
        </div>
      </div>
    </div>
  );
}
