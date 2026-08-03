'use client';

import React, { useEffect, useState } from 'react';
import { profileService } from '@/app/services/api';

interface TagOption {
  id: number;
  name: string;
}

interface ProfileTagsInputProps {
  value: string[];
  onChange: (tagIds: number[]) => Promise<void>;
}

export default function ProfileTagsInput({ value, onChange }: ProfileTagsInputProps) {
  const [allTags, setAllTags] = useState<TagOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    profileService
      .getAllTags()
      .then((data) => setAllTags(data.tags))
      .catch((err: any) => setError(err.response?.data?.message || 'Failed to load interests.'))
      .finally(() => setLoading(false));
  }, []);

  const toggleTag = async (tag: TagOption) => {
    const selectedIds = allTags
      .filter((option) => value.includes(option.name))
      .map((option) => option.id);
    const selected = selectedIds.includes(tag.id);

    if (selected && selectedIds.length === 1) {
      setError('Select at least one interest.');
      return;
    }

    const nextIds = selected
      ? selectedIds.filter((id) => id !== tag.id)
      : [...selectedIds, tag.id];

    setError('');
    setSaving(true);
    try {
      await onChange(nextIds);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to update interests.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <p className="text-sm text-[#9C8FA8]">Loading interests…</p>;
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {allTags.map((tag) => {
          const selected = value.includes(tag.name);
          return (
            <button
              key={tag.id}
              type="button"
              onClick={() => toggleTag(tag)}
              disabled={saving}
              className={`rounded-full border px-3 py-1.5 text-sm transition disabled:cursor-not-allowed disabled:opacity-50 ${
                selected
                  ? 'border-[#FF4D7E] bg-[#FF4D7E]/15 text-[#FF8FAE]'
                  : 'border-[#332844] bg-[#1E1728] text-[#9C8FA8] hover:border-[#FF4D7E]/50'
              }`}
            >
              #{tag.name}
            </button>
          );
        })}
      </div>

      <p className="mt-2 text-xs text-[#6E6180]">
        Select at least one reusable interest. Changes are saved automatically.
      </p>
      {error && <p className="mt-2 text-sm text-[#FF8A80]">{error}</p>}
    </div>
  );
}
