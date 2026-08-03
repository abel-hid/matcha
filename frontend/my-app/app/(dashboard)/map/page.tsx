'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState } from 'react';
import { apiErrorMessage, errorCode } from '@/app/lib/apiError';
import UserMap from '@/app/components/UserMap';
import { discoverService, profileService } from '@/app/services/api';
import type {
  DiscoverFilters,
  MapResponse,
  TagOption,
} from '@/app/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

const DEFAULT_FILTERS: DiscoverFilters = {
  minAge: 18,
  maxAge: 80,
  minFame: 0,
  maxFame: 100,
  location: '',
  tagIds: [],
  sort: 'recommended',
  order: 'asc',
};

/** Load privacy-rounded compatible profiles and render the interactive user map. */
export default function MapPage() {
  const [draftFilters, setDraftFilters] = useState(DEFAULT_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState(DEFAULT_FILTERS);
  const [mapData, setMapData] = useState<MapResponse | null>(null);
  const [tags, setTags] = useState<TagOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filterError, setFilterError] = useState('');
  const [gpsConsent, setGpsConsent] = useState(false);
  const [locating, setLocating] = useState(false);
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    profileService
      .getAllTags()
      .then((data) => setTags(data.tags ?? []))
      .catch(() => setError('The interest tags could not be loaded.'));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError('');
    discoverService
      .getMapProfiles(appliedFilters)
      .then((data: MapResponse) => setMapData(data))
      .catch((requestError: unknown) => {
        setMapData(null);
        setError(
          apiErrorMessage(requestError, 'The user map could not be loaded.')
        );
      })
      .finally(() => setLoading(false));
  }, [appliedFilters, reloadVersion]);

  /** Update one numeric map filter while retaining the remaining filter draft. */
  const updateNumber = (field: 'minAge' | 'maxAge' | 'minFame' | 'maxFame', value: string) => {
    setDraftFilters((current) => ({
      ...current,
      [field]: Number(value),
    }));
  };

  /** Toggle an interest tag used to filter map markers. */
  const toggleTag = (tagId: number) => {
    setDraftFilters((current) => ({
      ...current,
      tagIds: current.tagIds.includes(tagId)
        ? current.tagIds.filter((id) => id !== tagId)
        : [...current.tagIds, tagId],
    }));
  };

  /** Apply the current map filters and request a fresh marker set. */
  const applyFilters = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFilterError('');

    if (
      draftFilters.minAge < 18
      || draftFilters.maxAge > 80
      || draftFilters.minAge > draftFilters.maxAge
    ) {
      setFilterError('Choose an age range between 18 and 80.');
      return;
    }

    if (
      draftFilters.minFame < 0
      || draftFilters.maxFame > 100
      || draftFilters.minFame > draftFilters.maxFame
    ) {
      setFilterError('Choose a fame range between 0 and 100.');
      return;
    }

    setAppliedFilters({
      ...draftFilters,
      location: draftFilters.location.trim(),
    });
  };

  /** Request explicit GPS consent and refresh markers around the saved position. */
  const usePreciseGps = async () => {
    if (!gpsConsent) {
      setError('Confirm GPS consent before requesting your location.');
      return;
    }
    if (!window.isSecureContext) {
      setError('GPS location requires HTTPS or localhost.');
      return;
    }
    if (!navigator.geolocation) {
      setError('This browser does not support location services.');
      return;
    }

    setLocating(true);
    setError('');
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 12_000,
          maximumAge: 30_000,
        });
      });
      await profileService.updateLocationGps(
        position.coords.latitude,
        position.coords.longitude,
      );
      setReloadVersion((value) => value + 1);
    } catch (locationError: unknown) {
      if (errorCode(locationError) === 1) {
        setError('Location permission was denied. Allow it in the browser or use a manual location from your profile.');
      } else {
        setError(apiErrorMessage(locationError, 'Your current location could not be obtained.'));
      }
    } finally {
      setLocating(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <h1 className="font-serif text-3xl text-[#F5EFE9]">User map</h1>
          <p className="mt-2 text-sm leading-relaxed text-[#9C8FA8]">
            Explore the same compatible, complete, and non-blocked profiles as Discover.
            Candidate markers use approximate coordinates rather than exposing exact locations.
          </p>
        </div>
        <div className="rounded-xl border border-[#332844] bg-[#1E1728] p-3 lg:max-w-sm">
          <label className="flex items-start gap-2 text-xs text-[#C8BCCF]">
            <input
              type="checkbox"
              checked={gpsConsent}
              onChange={(event) => setGpsConsent(event.target.checked)}
              className="mt-0.5 accent-[#FF4D7E]"
            />
            I consent to updating my location with precise browser GPS. Exact coordinates remain private.
          </label>
          <button
            type="button"
            onClick={usePreciseGps}
            disabled={!gpsConsent || locating}
            className="mt-3 w-full rounded-lg bg-[#FF4D7E] px-4 py-2 text-sm font-medium text-[#15101C] hover:bg-[#FF6A93] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {locating ? 'Updating location…' : 'Use precise GPS for my position'}
          </button>
        </div>
      </div>

      <form
        onSubmit={applyFilters}
        className="mt-6 rounded-xl border border-[#332844] bg-[#1E1728] p-4"
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <NumberField label="Min age" value={draftFilters.minAge} min={18} max={80} onChange={(value) => updateNumber('minAge', value)} />
          <NumberField label="Max age" value={draftFilters.maxAge} min={18} max={80} onChange={(value) => updateNumber('maxAge', value)} />
          <NumberField label="Min fame" value={draftFilters.minFame} min={0} max={100} onChange={(value) => updateNumber('minFame', value)} />
          <NumberField label="Max fame" value={draftFilters.maxFame} min={0} max={100} onChange={(value) => updateNumber('maxFame', value)} />
          <label className="block">
            <span className="text-xs uppercase tracking-wide text-[#9C8FA8]">Location</span>
            <input
              type="text"
              value={draftFilters.location}
              maxLength={100}
              placeholder="City or neighborhood"
              onChange={(event) => setDraftFilters((current) => ({
                ...current,
                location: event.target.value,
              }))}
              className="mt-1.5 w-full rounded-lg border border-[#332844] bg-[#15101C] px-3 py-2 text-sm text-[#F5EFE9] outline-none placeholder:text-[#5D5268] focus:border-[#FF4D7E]/60"
            />
          </label>
        </div>

        <fieldset className="mt-4">
          <legend className="text-xs uppercase tracking-wide text-[#9C8FA8]">Interest tags</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {tags.map((tag) => {
              const selected = draftFilters.tagIds.includes(tag.id);
              return (
                <button
                  key={tag.id}
                  type="button"
                  onClick={() => toggleTag(tag.id)}
                  className={`rounded-full border px-3 py-1 text-xs transition ${
                    selected
                      ? 'border-[#FF4D7E] bg-[#FF4D7E]/15 text-[#FF8FAE]'
                      : 'border-[#332844] text-[#9C8FA8] hover:border-[#4A3D58]'
                  }`}
                >
                  {tag.name}
                </button>
              );
            })}
          </div>
        </fieldset>

        {filterError && <p className="mt-3 text-sm text-[#FF8A80]">{filterError}</p>}
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="submit"
            className="rounded-lg bg-[#FF4D7E] px-5 py-2 text-sm font-medium text-[#15101C] hover:bg-[#FF6A93]"
          >
            Apply to map
          </button>
          <button
            type="button"
            onClick={() => {
              setDraftFilters(DEFAULT_FILTERS);
              setAppliedFilters(DEFAULT_FILTERS);
              setFilterError('');
            }}
            className="rounded-lg border border-[#332844] px-5 py-2 text-sm text-[#9C8FA8] hover:text-[#F5EFE9]"
          >
            Reset
          </button>
        </div>
      </form>

      {error && (
        <div className="mt-5 rounded-xl border border-[#FF6B6B]/25 bg-[#FF6B6B]/10 p-4 text-sm text-[#FFB0A8]">
          <p>{error}</p>
          {error.includes('location') && (
            <Link href="/profile" className="mt-2 inline-block font-medium text-[#F5EFE9] underline">
              Set a manual location in Profile
            </Link>
          )}
        </div>
      )}

      <div className="mt-6">
        {loading ? (
          <div className="flex h-[60vh] min-h-[460px] items-center justify-center rounded-2xl border border-[#332844] bg-[#1E1728] text-sm text-[#9C8FA8]">
            Loading map…
          </div>
        ) : mapData ? (
          <>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-[#766A82]">
              <span>{mapData.total} compatible profile{mapData.total === 1 ? '' : 's'}</span>
              {mapData.truncated && <span>Showing the first 500 ordered results.</span>}
            </div>
            <UserMap
              currentUserLocation={mapData.currentUserLocation}
              profiles={mapData.profiles}
              apiBaseUrl={API_BASE_URL}
            />
          </>
        ) : null}
      </div>
    </div>
  );
}

/** Render a controlled numeric filter input. */
function NumberField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs uppercase tracking-wide text-[#9C8FA8]">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1.5 w-full rounded-lg border border-[#332844] bg-[#15101C] px-3 py-2 text-sm text-[#F5EFE9] outline-none focus:border-[#FF4D7E]/60"
      />
    </label>
  );
}
