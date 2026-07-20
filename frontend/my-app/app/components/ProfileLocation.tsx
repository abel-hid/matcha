'use client';

import React, { useState } from 'react';
import { profileService } from '@/app/services/api';

interface LocationValue {
  name: string | null;
  latitude: number | null;
  longitude: number | null;
}

interface ProfileLocationProps {
  location: LocationValue | null;
  gpsConsent: boolean;
  onChange: (location: LocationValue, gpsConsent: boolean) => void;
}

export default function ProfileLocation({ location, gpsConsent, onChange }: ProfileLocationProps) {
  const [manualInput, setManualInput] = useState(location?.name || '');
  const [requesting, setRequesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleUseGps = () => {
    if (!navigator.geolocation) {
      setError('Your browser doesn\u2019t support location services. Enter your location manually instead.');
      return;
    }

    setError('');
    setRequesting(true);

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        setRequesting(false);
        setSaving(true);
        try {
          const data = await profileService.updateLocationGps(
            position.coords.latitude,
            position.coords.longitude
          );
          onChange(data.location, data.gpsConsent);
        } catch (err: any) {
          setError(err.response?.data?.message || 'Failed to save your location.');
        } finally {
          setSaving(false);
        }
      },
      (geoError) => {
        setRequesting(false);
        // Permission denied, unavailable, or timed out — all funnel to the
        // manual entry fallback, which is required by spec regardless.
        if (geoError.code === geoError.PERMISSION_DENIED) {
          setError('Location access was denied. Enter your city or neighborhood below instead.');
        } else {
          setError('Couldn\u2019t determine your location. Enter your city or neighborhood below instead.');
        }
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const handleManualSave = async () => {
    if (!manualInput.trim()) {
      setError('Enter a city or neighborhood.');
      return;
    }
    setError('');
    setSaving(true);
    try {
      const data = await profileService.updateLocationManual(manualInput.trim());
      onChange(data.location, data.gpsConsent);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to save your location.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between rounded-lg border border-[#332844] bg-[#1E1728] px-4 py-3">
        <div>
          <p className="text-sm font-medium text-[#F5EFE9]">
            {gpsConsent ? 'Using GPS location' : 'GPS location not enabled'}
          </p>
          <p className="mt-0.5 text-xs text-[#9C8FA8]">
            {location?.name || (location?.latitude ? 'Coordinates set, no name yet' : 'No location set')}
          </p>
        </div>
        <button
          type="button"
          onClick={handleUseGps}
          disabled={requesting || saving}
          className="shrink-0 rounded-lg bg-[#FF4D7E] px-4 py-2 text-sm font-medium text-[#15101C] transition hover:bg-[#FF6A93] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {requesting ? 'Requesting…' : saving ? 'Saving…' : 'Use my location'}
        </button>
      </div>

      <div className="flex items-center gap-2">
        <div className="h-px flex-1 bg-[#332844]" />
        <span className="text-xs text-[#6E6180]">or enter manually</span>
        <div className="h-px flex-1 bg-[#332844]" />
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={manualInput}
          onChange={(e) => setManualInput(e.target.value)}
          placeholder="City or neighborhood"
          className="flex-1 rounded-lg border border-[#332844] bg-[#1E1728] px-4 py-2.5 text-sm text-[#F5EFE9] placeholder-[#6E6180] outline-none transition focus:border-[#FF4D7E] focus:ring-2 focus:ring-[#FF4D7E]/30"
        />
        <button
          type="button"
          onClick={handleManualSave}
          disabled={saving}
          className="shrink-0 rounded-lg border border-[#332844] px-4 py-2.5 text-sm font-medium text-[#F5EFE9] transition hover:border-[#FF4D7E]/50 disabled:opacity-50"
        >
          Save
        </button>
      </div>

      {error && <p className="text-sm text-[#FF8A80]">{error}</p>}
    </div>
  );
}