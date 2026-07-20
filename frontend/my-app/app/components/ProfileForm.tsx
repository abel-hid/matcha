'use client';

import React, { useEffect, useState } from 'react';
import { profileService } from '@/app/services/api';
import { useAuth } from '@/app/context/AuthContext';
import ProfilePhotos from './ProfilePhotos';
import ProfileTagsInput from './ProfileTagsInput';
import ProfileLocation from './ProfileLocation';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

const GENDER_OPTIONS = [
  { value: '', label: 'Select…' },
  { value: 'male', label: 'Male' },
  { value: 'female', label: 'Female' },
  { value: 'other', label: 'Other' },
];

const PREFERENCE_OPTIONS = [
  { value: '', label: 'Select…' },
  { value: 'heterosexual', label: 'Heterosexual' },
  { value: 'homosexual', label: 'Homosexual' },
  { value: 'bisexual', label: 'Bisexual' },
];

const inputClasses =
  'mt-1.5 w-full rounded-lg border border-[#332844] bg-[#1E1728] px-4 py-2.5 text-[#F5EFE9] placeholder-[#6E6180] outline-none transition focus:border-[#FF4D7E] focus:ring-2 focus:ring-[#FF4D7E]/30';

const labelClasses = 'block text-xs font-medium uppercase tracking-wide text-[#9C8FA8]';

interface ProfileData {
  firstName: string;
  lastName: string;
  email: string;
  gender: string;
  sexualPreferences: string;
  biography: string;
  tags: string[];
  photos: { id: number; url: string; isPrimary: boolean; position: number }[];
  fameRating: number;
  isProfileComplete: boolean;
  location: { name: string | null; latitude: number | null; longitude: number | null } | null;
  gpsConsent: boolean;
}

export default function ProfileForm() {
  const { user: authUser } = useAuth();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    profileService
      .getProfile()
      .then((data) => setProfile(data.user))
      .catch((err: any) => setError(err.response?.data?.message || 'Failed to load your profile.'))
      .finally(() => setLoading(false));
  }, []);

  const updateField = <K extends keyof ProfileData>(key: K, value: ProfileData[K]) => {
    setProfile((prev) => (prev ? { ...prev, [key]: value } : prev));
    setSaved(false);
  };

  const handleSaveBasics = async () => {
    if (!profile) return;
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      const data = await profileService.updateProfile({
        firstName: profile.firstName,
        lastName: profile.lastName,
        email: profile.email,
        gender: profile.gender,
        sexualPreferences: profile.sexualPreferences,
        biography: profile.biography,
      });
      setProfile(data.user);
      setSaved(true);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to save your profile.');
    } finally {
      setSaving(false);
    }
  };

  const handleTagsChange = async (tags: string[]) => {
    updateField('tags', tags);
    try {
      const data = await profileService.setMyTags(tags);
      updateField('tags', data.tags);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to update tags.');
    }
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
          <div className="mb-6 rounded-lg border border-[#F2C879]/30 bg-[#F2C879]/10 px-4 py-3 text-sm text-[#F2C879]">
            Your profile isn&apos;t complete yet — add gender, preferences, a bio, at least one
            tag, one photo, and your location to be visible to other users.
          </div>
        )}

        <div className="space-y-8">
          <section>
            <h2 className="mb-3 font-serif text-lg text-[#F5EFE9]">Photos</h2>
            <ProfilePhotos
              photos={profile.photos}
              apiBaseUrl={API_BASE_URL}
              onChange={(photos) => updateField('photos', photos)}
            />
          </section>

          <section>
            <h2 className="mb-3 font-serif text-lg text-[#F5EFE9]">Basic info</h2>
            <div className="space-y-4 rounded-lg border border-[#332844] bg-[#1E1728]/50 p-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelClasses}>First name</label>
                  <input
                    type="text"
                    value={profile.firstName}
                    onChange={(e) => updateField('firstName', e.target.value)}
                    className={inputClasses}
                  />
                </div>
                <div>
                  <label className={labelClasses}>Last name</label>
                  <input
                    type="text"
                    value={profile.lastName}
                    onChange={(e) => updateField('lastName', e.target.value)}
                    className={inputClasses}
                  />
                </div>
              </div>

              <div>
                <label className={labelClasses}>Email</label>
                <input
                  type="email"
                  value={profile.email}
                  onChange={(e) => updateField('email', e.target.value)}
                  className={inputClasses}
                />
                <p className="mt-1 text-xs text-[#6E6180]">
                  Changing your email will require re-verification.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelClasses}>Gender</label>
                  <select
                    value={profile.gender || ''}
                    onChange={(e) => updateField('gender', e.target.value)}
                    className={inputClasses}
                  >
                    {GENDER_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className={labelClasses}>Sexual preferences</label>
                  <select
                    value={profile.sexualPreferences || ''}
                    onChange={(e) => updateField('sexualPreferences', e.target.value)}
                    className={inputClasses}
                  >
                    {PREFERENCE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className={labelClasses}>Biography</label>
                <textarea
                  value={profile.biography || ''}
                  onChange={(e) => updateField('biography', e.target.value)}
                  rows={4}
                  className={inputClasses + ' resize-none'}
                  placeholder="Tell people a bit about yourself…"
                />
              </div>
            </div>
          </section>

          <section>
            <h2 className="mb-3 font-serif text-lg text-[#F5EFE9]">Interests</h2>
            <ProfileTagsInput value={profile.tags} onChange={handleTagsChange} />
          </section>

          <section>
            <h2 className="mb-3 font-serif text-lg text-[#F5EFE9]">Location</h2>
            <ProfileLocation
              location={profile.location}
              gpsConsent={profile.gpsConsent}
              onChange={(location, gpsConsent) => {
                updateField('location', location);
                updateField('gpsConsent', gpsConsent);
              }}
            />
          </section>

          {error && (
            <div className="rounded-lg border border-[#FF6B6B]/30 bg-[#FF6B6B]/10 px-3 py-2 text-sm text-[#FF8A80]">
              {error}
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleSaveBasics}
              disabled={saving}
              className="rounded-lg bg-[#FF4D7E] px-6 py-2.5 text-sm font-medium text-[#15101C] transition hover:bg-[#FF6A93] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save changes'}
            </button>
            {saved && <span className="text-sm text-[#F2C879]">Saved.</span>}
          </div>
        </div>
      </div>
    </div>
  );
}