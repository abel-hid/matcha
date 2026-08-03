'use client';

import React, { FormEvent, useEffect, useState } from 'react';

import UserCard from '@/app/components/UserCard';
import { discoverService, profileService } from '@/app/services/api';
import {
  DiscoverFilters,
  DiscoverProfile,
  DiscoverResponse,
  TagOption,
} from '@/app/types';

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL
  || 'http://localhost:5000'
);

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

export default function Dashboard() {
  const [draftFilters, setDraftFilters] = useState<DiscoverFilters>(
    DEFAULT_FILTERS
  );
  const [appliedFilters, setAppliedFilters] = useState<DiscoverFilters>(
    DEFAULT_FILTERS
  );
  const [profiles, setProfiles] = useState<DiscoverProfile[]>([]);
  const [tags, setTags] = useState<TagOption[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filterError, setFilterError] = useState('');

  useEffect(() => {
    profileService
      .getAllTags()
      .then((data) => setTags(data.tags))
      .catch(() => setError('The interest tags could not be loaded.'));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError('');

    discoverService
      .getProfiles(appliedFilters, page)
      .then((data: DiscoverResponse) => {
        setProfiles(data.profiles);
        setTotal(data.pagination.total);
        setTotalPages(data.pagination.totalPages);
      })
      .catch((err: any) => {
        setProfiles([]);
        setTotal(0);
        setTotalPages(0);
        setError(
          err.response?.data?.message
          || 'Suggested profiles could not be loaded.'
        );
      })
      .finally(() => setLoading(false));
  }, [appliedFilters, page]);

  const updateNumberFilter = (
    name: 'minAge' | 'maxAge' | 'minFame' | 'maxFame',
    value: string
  ) => {
    setDraftFilters((current) => ({
      ...current,
      [name]: Number(value),
    }));
  };

  const toggleTag = (tagId: number) => {
    setDraftFilters((current) => ({
      ...current,
      tagIds: current.tagIds.includes(tagId)
        ? current.tagIds.filter((id) => id !== tagId)
        : [...current.tagIds, tagId],
    }));
  };

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

    setPage(1);
    setAppliedFilters({
      ...draftFilters,
      location: draftFilters.location.trim(),
    });
  };

  const resetFilters = () => {
    setDraftFilters(DEFAULT_FILTERS);
    setAppliedFilters(DEFAULT_FILTERS);
    setFilterError('');
    setPage(1);
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <div className="max-w-2xl">
        <h1 className="font-serif text-3xl text-[#F5EFE9]">
          Discover
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-[#9C8FA8]">
          Suggested profiles are compatible with your preferences and ranked
          by geographical area, distance, common interests, and fame rating.
          Use the same page to search with specific criteria.
        </p>
      </div>

      <form
        onSubmit={applyFilters}
        className="mt-8 rounded-xl border border-[#332844] bg-[#1E1728] p-5"
      >
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-serif text-xl text-[#F5EFE9]">
              Search criteria
            </h2>
            <p className="mt-1 text-xs text-[#766A82]">
              Leave the default values to see the suggested list.
            </p>
          </div>

          <button
            type="button"
            onClick={resetFilters}
            className="mt-3 self-start text-sm text-[#9C8FA8] transition hover:text-[#F5EFE9] sm:mt-0"
          >
            Reset criteria
          </button>
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <NumberField
            label="Minimum age"
            value={draftFilters.minAge}
            min={18}
            max={80}
            onChange={(value) => updateNumberFilter('minAge', value)}
          />
          <NumberField
            label="Maximum age"
            value={draftFilters.maxAge}
            min={18}
            max={80}
            onChange={(value) => updateNumberFilter('maxAge', value)}
          />
          <NumberField
            label="Minimum fame"
            value={draftFilters.minFame}
            min={0}
            max={100}
            onChange={(value) => updateNumberFilter('minFame', value)}
          />
          <NumberField
            label="Maximum fame"
            value={draftFilters.maxFame}
            min={0}
            max={100}
            onChange={(value) => updateNumberFilter('maxFame', value)}
          />
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <label className="block md:col-span-1">
            <span className="text-xs uppercase tracking-wide text-[#9C8FA8]">
              Location
            </span>
            <input
              type="text"
              value={draftFilters.location}
              maxLength={100}
              placeholder="City or neighborhood"
              onChange={(event) => setDraftFilters((current) => ({
                ...current,
                location: event.target.value,
              }))}
              className="mt-1.5 w-full rounded-lg border border-[#332844] bg-[#15101C] px-3 py-2.5 text-sm text-[#F5EFE9] outline-none transition placeholder:text-[#5D5268] focus:border-[#FF4D7E]/60"
            />
          </label>

          <label className="block">
            <span className="text-xs uppercase tracking-wide text-[#9C8FA8]">
              Sort by
            </span>
            <select
              value={draftFilters.sort}
              onChange={(event) => setDraftFilters((current) => ({
                ...current,
                sort: event.target.value as DiscoverFilters['sort'],
              }))}
              className="mt-1.5 w-full rounded-lg border border-[#332844] bg-[#15101C] px-3 py-2.5 text-sm text-[#F5EFE9] outline-none focus:border-[#FF4D7E]/60"
            >
              <option value="recommended">Recommended</option>
              <option value="age">Age</option>
              <option value="distance">Location / distance</option>
              <option value="fame">Fame rating</option>
              <option value="commonTags">Common interests</option>
            </select>
          </label>

          <label className="block">
            <span className="text-xs uppercase tracking-wide text-[#9C8FA8]">
              Direction
            </span>
            <select
              value={draftFilters.order}
              disabled={draftFilters.sort === 'recommended'}
              onChange={(event) => setDraftFilters((current) => ({
                ...current,
                order: event.target.value as DiscoverFilters['order'],
              }))}
              className="mt-1.5 w-full rounded-lg border border-[#332844] bg-[#15101C] px-3 py-2.5 text-sm text-[#F5EFE9] outline-none disabled:cursor-not-allowed disabled:opacity-40 focus:border-[#FF4D7E]/60"
            >
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </select>
          </label>
        </div>

        <fieldset className="mt-5">
          <legend className="text-xs uppercase tracking-wide text-[#9C8FA8]">
            Interest tags
          </legend>
          <p className="mt-1 text-xs text-[#6E6180]">
            A result must contain every selected tag.
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            {tags.map((tag) => {
              const selected = draftFilters.tagIds.includes(tag.id);

              return (
                <button
                  key={tag.id}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => toggleTag(tag.id)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                    selected
                      ? 'border-[#FF4D7E]/60 bg-[#FF4D7E]/15 text-[#FF8FAE]'
                      : 'border-[#332844] text-[#9C8FA8] hover:border-[#FF4D7E]/30 hover:text-[#F5EFE9]'
                  }`}
                >
                  #{tag.name}
                </button>
              );
            })}
          </div>
        </fieldset>

        {filterError && (
          <div className="mt-4 rounded-lg border border-[#FF6B6B]/30 bg-[#FF6B6B]/10 px-3 py-2 text-sm text-[#FF8A80]">
            {filterError}
          </div>
        )}

        <div className="mt-5 flex justify-end">
          <button
            type="submit"
            className="rounded-lg bg-[#FF4D7E] px-5 py-2.5 text-sm font-medium text-[#15101C] transition hover:bg-[#FF6A93]"
          >
            Apply criteria
          </button>
        </div>
      </form>

      <section className="mt-9">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h2 className="font-serif text-2xl text-[#F5EFE9]">
              Profiles
            </h2>
            {!loading && !error && (
              <p className="mt-1 text-sm text-[#9C8FA8]">
                {total} compatible {total === 1 ? 'profile' : 'profiles'}
              </p>
            )}
          </div>

          {totalPages > 1 && (
            <p className="text-xs text-[#6E6180]">
              Page {page} of {totalPages}
            </p>
          )}
        </div>

        {error && (
          <div className="mt-5 rounded-lg border border-[#FF6B6B]/30 bg-[#FF6B6B]/10 px-4 py-3 text-sm text-[#FF8A80]">
            {error}
          </div>
        )}

        {loading ? (
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {Array.from({ length: 6 }, (_, index) => (
              <div
                key={index}
                className="h-28 animate-pulse rounded-xl border border-[#332844] bg-[#1E1728]"
              />
            ))}
          </div>
        ) : profiles.length > 0 ? (
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {profiles.map((profile) => (
              <UserCard
                key={profile.id}
                user={profile}
                apiBaseUrl={API_BASE_URL}
                meta={(
                  <>
                    {profile.age} years · {profile.location.name}
                    <br />
                    {profile.distanceKm} km away ·{' '}
                    {profile.commonTagCount}{' '}
                    {profile.commonTagCount === 1
                      ? 'common interest'
                      : 'common interests'}
                  </>
                )}
              />
            ))}
          </div>
        ) : !error ? (
          <div className="mt-5 rounded-xl border border-[#332844] bg-[#1E1728] px-6 py-12 text-center">
            <h3 className="font-serif text-xl text-[#F5EFE9]">
              No compatible profiles found
            </h3>
            <p className="mt-2 text-sm text-[#9C8FA8]">
              Change one or more search criteria and try again.
            </p>
          </div>
        ) : null}

        {totalPages > 1 && !loading && (
          <div className="mt-6 flex items-center justify-center gap-3">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((current) => current - 1)}
              className="rounded-lg border border-[#332844] px-4 py-2 text-sm text-[#9C8FA8] transition hover:border-[#FF4D7E]/40 hover:text-[#F5EFE9] disabled:cursor-not-allowed disabled:opacity-40"
            >
              Previous
            </button>

            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((current) => current + 1)}
              className="rounded-lg border border-[#332844] px-4 py-2 text-sm text-[#9C8FA8] transition hover:border-[#FF4D7E]/40 hover:text-[#F5EFE9] disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

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
      <span className="text-xs uppercase tracking-wide text-[#9C8FA8]">
        {label}
      </span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1.5 w-full rounded-lg border border-[#332844] bg-[#15101C] px-3 py-2.5 text-sm text-[#F5EFE9] outline-none transition focus:border-[#FF4D7E]/60"
      />
    </label>
  );
}
