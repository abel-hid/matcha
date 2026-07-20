'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { profileService } from '@/app/services/api';

interface ProfileTagsInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
}

const MAX_TAGS = 20;

export default function ProfileTagsInput({ value, onChange }: ProfileTagsInputProps) {
  const [inputValue, setInputValue] = useState('');
  const [allTags, setAllTags] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    profileService
      .getAllTags()
      .then((data) => setAllTags(data.tags.map((t: { name: string }) => t.name)))
      .catch(() => {
        // Autocomplete is a nice-to-have — if it fails to load, typing a new
        // tag from scratch still works fine, so fail silently here.
      });
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const normalize = (raw: string) => raw.trim().toLowerCase().replace(/^#+/, '');

  const addTag = (raw: string) => {
    const clean = normalize(raw);
    if (!clean || value.includes(clean) || value.length >= MAX_TAGS) return;
    onChange([...value, clean]);
    setInputValue('');
  };

  const removeTag = (tag: string) => {
    onChange(value.filter((t) => t !== tag));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag(inputValue);
    } else if (e.key === 'Backspace' && inputValue === '' && value.length > 0) {
      removeTag(value[value.length - 1]);
    }
  };

  const suggestions = useMemo(() => {
    const clean = normalize(inputValue);
    if (!clean) return [];
    return allTags
      .filter((t) => t.includes(clean) && !value.includes(t))
      .slice(0, 6);
  }, [inputValue, allTags, value]);

  return (
    <div ref={containerRef} className="relative">
      <div className="flex min-h-[46px] flex-wrap items-center gap-1.5 rounded-lg border border-[#332844] bg-[#1E1728] px-3 py-2 focus-within:border-[#FF4D7E] focus-within:ring-2 focus-within:ring-[#FF4D7E]/30">
        {value.map((tag) => (
          <span
            key={tag}
            className="flex items-center gap-1 rounded-full bg-[#FF4D7E]/15 px-2.5 py-1 text-xs font-medium text-[#FF8FAE]"
          >
            #{tag}
            <button
              type="button"
              onClick={() => removeTag(tag)}
              className="ml-0.5 text-[#FF8FAE] transition hover:text-[#FF4D7E]"
              aria-label={`Remove ${tag}`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setShowSuggestions(true)}
          placeholder={value.length === 0 ? 'Type an interest and press Enter…' : ''}
          className="min-w-[120px] flex-1 bg-transparent text-sm text-[#F5EFE9] placeholder-[#6E6180] outline-none"
          disabled={value.length >= MAX_TAGS}
        />
      </div>

      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-[#332844] bg-[#1E1728] shadow-lg">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => addTag(s)}
              className="block w-full px-3 py-2 text-left text-sm text-[#F5EFE9] transition hover:bg-[#332844]"
            >
              #{s}
            </button>
          ))}
        </div>
      )}

      <p className="mt-1.5 text-xs text-[#6E6180]">
        {value.length}/{MAX_TAGS} tags — press Enter or comma to add
      </p>
    </div>
  );
}