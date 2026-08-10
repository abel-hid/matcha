'use client';

import React, { DragEvent, useRef, useState } from 'react';
import { apiErrorMessage, errorCode } from '@/app/lib/apiError';
import PhotoEditor from '@/app/components/PhotoEditor';
import { profileService } from '@/app/services/api';
import type { Photo, User } from '@/app/types';

interface ProfilePhotosProps {
  photos: Photo[];
  apiBaseUrl: string;
  onChange: (profile: User) => void;
}

interface EditorState {
  sourceUrl: string;
  photoId: number | null;
}

const MAX_PHOTOS = 5;
const MAX_FILE_SIZE = 5 * 1024 * 1024;
const MAX_IMAGE_DIMENSION = 8_000;
const MAX_IMAGE_PIXELS = 20_000_000;


const hasSupportedImageSignature = async (file: File) => {
  const bytes = new Uint8Array(await file.slice(0, 12).arrayBuffer());
  const isPng = (
    bytes.length >= 8
    && bytes[0] === 0x89
    && bytes[1] === 0x50
    && bytes[2] === 0x4E
    && bytes[3] === 0x47
    && bytes[4] === 0x0D
    && bytes[5] === 0x0A
    && bytes[6] === 0x1A
    && bytes[7] === 0x0A
  );
  const isJpeg = (
    bytes.length >= 3
    && bytes[0] === 0xFF
    && bytes[1] === 0xD8
    && bytes[2] === 0xFF
  );
  return isPng || isJpeg;
};


const validateImageFile = async (file: File) => {
  if (file.size > MAX_FILE_SIZE) {
    return 'Images must be under 5MB.';
  }

  try {
    if (!(await hasSupportedImageSignature(file))) {
      return 'Upload a valid PNG or JPEG image.';
    }

    const image = await createImageBitmap(file);
    try {
      if (
        image.width <= 0
        || image.height <= 0
        || image.width > MAX_IMAGE_DIMENSION
        || image.height > MAX_IMAGE_DIMENSION
        || image.width * image.height > MAX_IMAGE_PIXELS
      ) {
        return 'Image dimensions are too large.';
      }
    } finally {
      image.close();
    }
  } catch {
    return 'Upload a valid PNG or JPEG image.';
  }

  return null;
};


export default function ProfilePhotos({ photos, apiBaseUrl, onChange }: ProfilePhotosProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState('');

  const sorted = [...photos].sort((a, b) => (
    Number(b.isPrimary) - Number(a.isPrimary)
    || a.position - b.position
    || a.id - b.id
  ));
  const slots = Array.from({ length: MAX_PHOTOS }, (_, index) => sorted[index] || null);

  
  const closeEditor = () => {
    if (editor) {
      URL.revokeObjectURL(editor.sourceUrl);
    }
    setEditor(null);
  };

  
  const openFileEditor = async (file: File) => {
    setError('');
    const validationError = await validateImageFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }

    if (sorted.length >= MAX_PHOTOS) {
      setError(`You can have at most ${MAX_PHOTOS} photos.`);
      return;
    }

    setEditor({
      sourceUrl: URL.createObjectURL(file),
      photoId: null,
    });
  };

  
  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file) {
      await openFileEditor(file);
    }
  };

  
  const handleDrop = async (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) {
      await openFileEditor(file);
    }
  };

  
  const handleEdit = async (photo: Photo) => {
    setBusyId(photo.id);
    setError('');
    try {
      const response = await fetch(`${apiBaseUrl}${photo.url}`);
      if (!response.ok) {
        throw new Error('Photo fetch failed');
      }
      const blob = await response.blob();
      setEditor({
        sourceUrl: URL.createObjectURL(blob),
        photoId: photo.id,
      });
    } catch {
      setError('The photo could not be opened for editing.');
    } finally {
      setBusyId(null);
    }
  };

  
  const saveEditedPhoto = async (file: File) => {
    if (!editor) {
      return;
    }

    setSaving(true);
    setError('');
    try {
      const data = editor.photoId === null
        ? await profileService.uploadPhoto(file)
        : await profileService.replacePhoto(editor.photoId, file);
      onChange(data.user);
      closeEditor();
    } catch (err: unknown) {
      const fallback = errorCode(err) === 'ERR_NETWORK'
        ? 'The backend is unavailable. Try again when it is running.'
        : 'Failed to save the edited photo.';
      setError(apiErrorMessage(err, fallback));
    } finally {
      setSaving(false);
    }
  };

  
  const handleSetPrimary = async (photoId: number) => {
    setBusyId(photoId);
    setError('');
    try {
      const data = await profileService.setPrimaryPhoto(photoId);
      onChange(data.user);
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Failed to update primary photo.'));
    } finally {
      setBusyId(null);
    }
  };

  
  const handleDelete = async (photoId: number) => {
    if (sorted.length === 1) {
      setError('At least one profile photo is required.');
      return;
    }

    setBusyId(photoId);
    setError('');
    try {
      const data = await profileService.deletePhoto(photoId);
      onChange(data.user);
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Failed to delete photo.'));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      <div
        onDragEnter={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (event.currentTarget === event.target) {
            setDragging(false);
          }
        }}
        onDrop={handleDrop}
        className={`rounded-xl border p-3 transition ${
          dragging
            ? 'border-[#FF4D7E] bg-[#FF4D7E]/5'
            : 'border-[#332844] bg-[#15101C]/30'
        }`}
      >
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
          {slots.map((photo, index) => photo ? (
            <div
              key={photo.id}
              className="group relative aspect-square overflow-hidden rounded-lg border border-[#332844] bg-[#1E1728]"
            >
              <img
                src={`${apiBaseUrl}${photo.url}`}
                alt={photo.isPrimary ? 'Primary profile photo' : 'Profile photo'}
                className="h-full w-full object-cover"
              />
              {photo.isPrimary && (
                <span className="absolute left-1.5 top-1.5 rounded-full bg-[#FF4D7E] px-2 py-0.5 text-[10px] font-medium text-[#15101C]">
                  Primary
                </span>
              )}
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 bg-[#15101C]/85 opacity-0 transition group-hover:opacity-100 group-focus-within:opacity-100">
                <button
                  type="button"
                  onClick={() => handleEdit(photo)}
                  disabled={busyId === photo.id}
                  className="rounded-md border border-[#F5EFE9]/30 px-2.5 py-1 text-[11px] font-medium text-[#F5EFE9] hover:bg-white/10 disabled:opacity-50"
                >
                  Edit
                </button>
                {!photo.isPrimary && (
                  <button
                    type="button"
                    onClick={() => handleSetPrimary(photo.id)}
                    disabled={busyId === photo.id}
                    className="rounded-md bg-[#F2C879] px-2.5 py-1 text-[11px] font-medium text-[#15101C] hover:bg-[#F5D998] disabled:opacity-50"
                  >
                    Set primary
                  </button>
                )}
                {sorted.length > 1 && (
                  <button
                    type="button"
                    onClick={() => handleDelete(photo.id)}
                    disabled={busyId === photo.id}
                    className="rounded-md border border-[#FF6B6B]/50 px-2.5 py-1 text-[11px] font-medium text-[#FF8A80] hover:bg-[#FF6B6B]/10 disabled:opacity-50"
                  >
                    Remove
                  </button>
                )}
              </div>
            </div>
          ) : (
            <button
              key={`empty-${index}`}
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={sorted.length >= MAX_PHOTOS}
              className="flex aspect-square flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-[#332844] bg-[#1E1728]/50 text-[#6E6180] transition hover:border-[#FF4D7E]/50 hover:text-[#9C8FA8] disabled:opacity-50"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
              {index === 0 && <span className="text-[10px]">Add photo</span>}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={sorted.length >= MAX_PHOTOS}
          className="mt-3 w-full rounded-lg border border-dashed border-[#4A3D58] px-4 py-3 text-sm text-[#9C8FA8] transition hover:border-[#FF4D7E]/50 hover:text-[#F5EFE9] disabled:cursor-not-allowed disabled:opacity-40"
        >
          Drop a PNG or JPEG here, or click to choose one
        </button>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg"
        className="hidden"
        onChange={handleFileSelect}
      />

      <p className="mt-2 text-xs text-[#6E6180]">
        {sorted.length} of {MAX_PHOTOS} photos. The backend validates and re-encodes every saved image.
      </p>
      <p className="mt-1 text-xs text-[#6E6180]">
        At least one photo is required. The primary photo is always displayed first. Changes are saved automatically.
      </p>

      {error && <p className="mt-2 text-sm text-[#FF8A80]">{error}</p>}

      {editor && (
        <PhotoEditor
          sourceUrl={editor.sourceUrl}
          saving={saving}
          externalError={error}
          onCancel={closeEditor}
          onSave={saveEditedPhoto}
        />
      )}
    </div>
  );
}
