'use client';

import React, { useRef, useState } from 'react';
import { profileService } from '@/app/services/api';

interface Photo {
  id: number;
  url: string;
  isPrimary: boolean;
  position: number;
}

interface ProfilePhotosProps {
  photos: Photo[];
  apiBaseUrl: string;
  onChange: (photos: Photo[]) => void;
}

const MAX_PHOTOS = 5;

export default function ProfilePhotos({ photos, apiBaseUrl, onChange }: ProfilePhotosProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState('');

  const sorted = [...photos].sort((a, b) => a.position - b.position);
  const slots = Array.from({ length: MAX_PHOTOS }, (_, i) => sorted[i] || null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;

    if (!['image/png', 'image/jpeg', 'image/gif'].includes(file.type)) {
      setError('Please choose a PNG, JPG, or GIF image.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('Images must be under 5MB.');
      return;
    }

    setError('');
    setUploading(true);
    try {
      const data = await profileService.uploadPhoto(file);
      onChange(data.photos);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to upload photo.');
    } finally {
      setUploading(false);
    }
  };

  const handleSetPrimary = async (photoId: number) => {
    setBusyId(photoId);
    setError('');
    try {
      const data = await profileService.setPrimaryPhoto(photoId);
      onChange(data.photos);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to update primary photo.');
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (photoId: number) => {
    setBusyId(photoId);
    setError('');
    try {
      const data = await profileService.deletePhoto(photoId);
      onChange(data.photos);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to delete photo.');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
        {slots.map((photo, i) =>
          photo ? (
            <div
              key={photo.id}
              className="group relative aspect-square overflow-hidden rounded-lg border border-[#332844] bg-[#1E1728]"
            >
              <img
                src={`${apiBaseUrl}${photo.url}`}
                alt="Profile"
                className="h-full w-full object-cover"
              />

              {photo.isPrimary && (
                <span className="absolute left-1.5 top-1.5 rounded-full bg-[#FF4D7E] px-2 py-0.5 text-[10px] font-medium text-[#15101C]">
                  Primary
                </span>
              )}

              <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 bg-[#15101C]/80 opacity-0 transition group-hover:opacity-100">
                {!photo.isPrimary && (
                  <button
                    type="button"
                    onClick={() => handleSetPrimary(photo.id)}
                    disabled={busyId === photo.id}
                    className="rounded-md bg-[#F2C879] px-2.5 py-1 text-[11px] font-medium text-[#15101C] transition hover:bg-[#F5D998] disabled:opacity-50"
                  >
                    Set primary
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => handleDelete(photo.id)}
                  disabled={busyId === photo.id}
                  className="rounded-md border border-[#FF6B6B]/50 px-2.5 py-1 text-[11px] font-medium text-[#FF8A80] transition hover:bg-[#FF6B6B]/10 disabled:opacity-50"
                >
                  {busyId === photo.id ? '…' : 'Remove'}
                </button>
              </div>
            </div>
          ) : (
            <button
              key={`empty-${i}`}
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="flex aspect-square flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-[#332844] bg-[#1E1728]/50 text-[#6E6180] transition hover:border-[#FF4D7E]/50 hover:text-[#9C8FA8] disabled:opacity-50"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
              {i === 0 && <span className="text-[10px]">Add photo</span>}
            </button>
          )
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/gif"
        className="hidden"
        onChange={handleFileSelect}
      />

      <p className="mt-2 text-xs text-[#6E6180]">
        {sorted.length} of {MAX_PHOTOS} photos {uploading && '— uploading…'}
      </p>

      {error && <p className="mt-2 text-sm text-[#FF8A80]">{error}</p>}
    </div>
  );
}