'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';

type FilterName = 'none' | 'grayscale' | 'sepia' | 'contrast';

interface PhotoEditorProps {
  sourceUrl: string;
  saving: boolean;
  externalError?: string;
  onCancel: () => void;
  onSave: (file: File) => Promise<void>;
}

const OUTPUT_SIZE = 900;

const FILTERS: { value: FilterName; label: string; canvas: string }[] = [
  { value: 'none', label: 'Original', canvas: 'none' },
  { value: 'grayscale', label: 'Black & white', canvas: 'grayscale(1)' },
  { value: 'sepia', label: 'Sepia', canvas: 'sepia(0.85)' },
  { value: 'contrast', label: 'Contrast', canvas: 'contrast(1.25) saturate(1.1)' },
];

function drawEditedImage(
  target: HTMLCanvasElement,
  image: HTMLImageElement,
  rotation: number,
  cropPercent: number,
  offsetX: number,
  offsetY: number,
  filter: FilterName,
  outputSize: number,
) {
  const normalizedRotation = ((rotation % 360) + 360) % 360;
  const rotated = document.createElement('canvas');
  const swapDimensions = normalizedRotation === 90 || normalizedRotation === 270;
  rotated.width = swapDimensions ? image.naturalHeight : image.naturalWidth;
  rotated.height = swapDimensions ? image.naturalWidth : image.naturalHeight;

  const rotatedContext = rotated.getContext('2d');
  if (!rotatedContext) {
    throw new Error('Canvas is unavailable');
  }

  rotatedContext.translate(rotated.width / 2, rotated.height / 2);
  rotatedContext.rotate((normalizedRotation * Math.PI) / 180);
  rotatedContext.drawImage(
    image,
    -image.naturalWidth / 2,
    -image.naturalHeight / 2,
  );

  const shortestSide = Math.min(rotated.width, rotated.height);
  const cropSide = Math.max(1, shortestSide * (cropPercent / 100));
  const availableX = Math.max(0, rotated.width - cropSide);
  const availableY = Math.max(0, rotated.height - cropSide);
  const sourceX = availableX * (offsetX / 100);
  const sourceY = availableY * (offsetY / 100);

  target.width = outputSize;
  target.height = outputSize;
  const context = target.getContext('2d');
  if (!context) {
    throw new Error('Canvas is unavailable');
  }

  context.clearRect(0, 0, outputSize, outputSize);
  context.filter = FILTERS.find((item) => item.value === filter)?.canvas || 'none';
  context.drawImage(
    rotated,
    sourceX,
    sourceY,
    cropSide,
    cropSide,
    0,
    0,
    outputSize,
    outputSize,
  );
  context.filter = 'none';
}

export default function PhotoEditor({
  sourceUrl,
  saving,
  externalError = '',
  onCancel,
  onSave,
}: PhotoEditorProps) {
  const previewRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [rotation, setRotation] = useState(0);
  const [cropPercent, setCropPercent] = useState(100);
  const [offsetX, setOffsetX] = useState(50);
  const [offsetY, setOffsetY] = useState(50);
  const [filter, setFilter] = useState<FilterName>('none');
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');

  const redraw = useCallback(() => {
    if (!ready || !imageRef.current || !previewRef.current) {
      return;
    }

    try {
      drawEditedImage(
        previewRef.current,
        imageRef.current,
        rotation,
        cropPercent,
        offsetX,
        offsetY,
        filter,
        600,
      );
      setError('');
    } catch {
      setError('This image could not be edited in your browser.');
    }
  }, [cropPercent, filter, offsetX, offsetY, ready, rotation]);

  useEffect(() => {
    setReady(false);
    const image = new Image();
    image.onload = () => {
      imageRef.current = image;
      setReady(true);
    };
    image.onerror = () => setError('The selected image could not be loaded.');
    image.src = sourceUrl;

    return () => {
      imageRef.current = null;
    };
  }, [sourceUrl]);

  useEffect(() => {
    redraw();
  }, [redraw]);

  const save = async () => {
    if (!imageRef.current || !ready) {
      return;
    }

    setError('');
    let file: File;
    try {
      const output = document.createElement('canvas');
      drawEditedImage(
        output,
        imageRef.current,
        rotation,
        cropPercent,
        offsetX,
        offsetY,
        filter,
        OUTPUT_SIZE,
      );

      const blob = await new Promise<Blob>((resolve, reject) => {
        output.toBlob(
          (result) => result ? resolve(result) : reject(new Error('Encoding failed')),
          'image/jpeg',
          0.9,
        );
      });
      file = new File([blob], 'edited-profile-photo.jpg', {
        type: 'image/jpeg',
      });
    } catch {
      setError('The edited image could not be encoded in your browser.');
      return;
    }

    await onSave(file);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="photo-editor-title"
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/75 p-4"
    >
      <div className="max-h-[calc(100vh-2rem)] w-full max-w-3xl overflow-y-auto rounded-2xl border border-[#332844] bg-[#15101C] p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="photo-editor-title" className="font-serif text-2xl text-[#F5EFE9]">
              Edit photo
            </h2>
            <p className="mt-1 text-sm text-[#9C8FA8]">
              Crop, rotate, and apply one controlled filter before saving.
            </p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            aria-label="Close photo editor"
            className="text-2xl text-[#766A82] hover:text-[#F5EFE9] disabled:opacity-50"
          >
            ×
          </button>
        </div>

        <div className="mt-5 grid gap-6 md:grid-cols-[minmax(0,1fr)_260px]">
          <div className="flex items-center justify-center rounded-xl border border-[#332844] bg-black/30 p-3">
            <canvas
              ref={previewRef}
              className="aspect-square w-full max-w-[520px] rounded-lg object-contain"
            />
          </div>

          <div className="space-y-5">
            <div>
              <p className="text-xs uppercase tracking-wide text-[#9C8FA8]">Rotation</p>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setRotation((value) => value - 90)}
                  className="rounded-lg border border-[#332844] px-3 py-2 text-sm text-[#F5EFE9] hover:border-[#FF4D7E]/50"
                >
                  Rotate left
                </button>
                <button
                  type="button"
                  onClick={() => setRotation((value) => value + 90)}
                  className="rounded-lg border border-[#332844] px-3 py-2 text-sm text-[#F5EFE9] hover:border-[#FF4D7E]/50"
                >
                  Rotate right
                </button>
              </div>
            </div>

            <RangeControl
              label="Crop size"
              value={cropPercent}
              min={35}
              max={100}
              suffix="%"
              onChange={setCropPercent}
            />
            <RangeControl
              label="Horizontal crop"
              value={offsetX}
              min={0}
              max={100}
              suffix="%"
              onChange={setOffsetX}
            />
            <RangeControl
              label="Vertical crop"
              value={offsetY}
              min={0}
              max={100}
              suffix="%"
              onChange={setOffsetY}
            />

            <div>
              <label className="text-xs uppercase tracking-wide text-[#9C8FA8]" htmlFor="photo-filter">
                Filter
              </label>
              <select
                id="photo-filter"
                value={filter}
                onChange={(event) => setFilter(event.target.value as FilterName)}
                className="mt-2 w-full rounded-lg border border-[#332844] bg-[#1E1728] px-3 py-2.5 text-sm text-[#F5EFE9] outline-none focus:border-[#FF4D7E]/60"
              >
                {FILTERS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {(error || externalError) && (
          <p className="mt-4 text-sm text-[#FF8A80]">
            {error || externalError}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className="rounded-lg border border-[#332844] px-4 py-2 text-sm text-[#9C8FA8] hover:text-[#F5EFE9] disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            disabled={!ready || saving}
            className="rounded-lg bg-[#FF4D7E] px-5 py-2 text-sm font-medium text-[#15101C] hover:bg-[#FF6A93] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save edited photo'}
          </button>
        </div>
      </div>
    </div>
  );
}

function RangeControl({
  label,
  value,
  min,
  max,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  suffix: string;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block">
      <span className="flex justify-between text-xs uppercase tracking-wide text-[#9C8FA8]">
        <span>{label}</span>
        <span>{value}{suffix}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-2 w-full accent-[#FF4D7E]"
      />
    </label>
  );
}
