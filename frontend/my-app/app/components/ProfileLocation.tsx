'use client';

import React, { useEffect, useState } from 'react';
import { profileService } from '@/app/services/api';

interface LocationValue {
  name: string | null;
  latitude: number | null;
  longitude: number | null;
}

interface LocationSearchResult {
  name: string;
  latitude: number;
  longitude: number;
}

interface LocationProfileUpdate {
  location: LocationValue | null;
  gpsConsent: boolean;
  fameRating: number;
  isProfileComplete: boolean;
}

interface ProfileLocationProps {
  location: LocationValue | null;
  gpsConsent: boolean;
  onChange: (profile: LocationProfileUpdate) => void;
}

export default function ProfileLocation({ location, gpsConsent, onChange }: ProfileLocationProps) {
  const [consentChecked, setConsentChecked] = useState(gpsConsent);
  const [permissionState, setPermissionState] = useState<PermissionState | null>(null);
  const [manualInput, setManualInput] = useState(location?.name || '');
  const [results, setResults] = useState<LocationSearchResult[]>([]);
  const [selectedResult, setSelectedResult] = useState<LocationSearchResult | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setConsentChecked(gpsConsent);
  }, [gpsConsent]);

  useEffect(() => {
    let permissionStatus: PermissionStatus | null = null;

    const loadPermission = async () => {
      if (!navigator.permissions?.query) return;

      try {
        permissionStatus = await navigator.permissions.query({ name: 'geolocation' });
        setPermissionState(permissionStatus.state);
        permissionStatus.onchange = () => setPermissionState(permissionStatus?.state || null);
      } catch {
        setPermissionState(null);
      }
    };

    loadPermission();

    return () => {
      if (permissionStatus) permissionStatus.onchange = null;
    };
  }, []);

  const handleUseGps = async () => {
    if (!consentChecked) {
      setError('Confirm GPS consent before requesting your location.');
      return;
    }

    if (!window.isSecureContext) {
      setError('GPS location requires HTTPS or localhost.');
      return;
    }

    if (!navigator.geolocation) {
      setError('Your browser doesn’t support location services. Enter your location manually instead.');
      return;
    }

    if (permissionState === 'denied') {
      setError(
        'Location is blocked in your browser or device settings. Allow location for this site, then try again.'
      );
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
          onChange(data.user);
          setPermissionState('granted');
          setManualInput(data.user.location?.name || '');
          setResults([]);
          setSelectedResult(null);
        } catch (err: any) {
          setError(err.response?.data?.message || 'Failed to save your location.');
        } finally {
          setSaving(false);
        }
      },
      (geoError) => {
        setRequesting(false);

        if (geoError.code === geoError.PERMISSION_DENIED) {
          setPermissionState('denied');
          setError(
            'Location is blocked in your browser or device settings. Allow location for this site, then try again.'
          );
        } else if (geoError.code === geoError.POSITION_UNAVAILABLE) {
          setError('Your device could not determine a location. Try again or use manual search.');
        } else if (geoError.code === geoError.TIMEOUT) {
          setError('Location lookup timed out. Try again or use manual search.');
        } else {
          setError('Couldn’t determine your location. Use manual search instead.');
        }
      },
      {
        enableHighAccuracy: false,
        timeout: 15000,
        maximumAge: 60000,
      }
    );
  };

  const handleManualSearch = async () => {
    const query = manualInput.trim();
    if (!query) {
      setError('Enter a city or neighborhood.');
      return;
    }

    setError('');
    setSearching(true);
    setResults([]);
    setSelectedResult(null);

    try {
      const data = await profileService.searchLocations(query);
      const nextResults = data.results as LocationSearchResult[];
      setResults(nextResults);

      if (nextResults.length === 0) {
        setError('No matching location was found. Add the city and country, then search again.');
      }
    } catch (err: any) {
      setError(err.response?.data?.message || 'Location search failed. Try again shortly.');
    } finally {
      setSearching(false);
    }
  };

  const handleManualSave = async () => {
    if (!selectedResult) {
      setError('Search for a location and select one result before saving.');
      return;
    }

    setError('');
    setSaving(true);
    try {
      const data = await profileService.updateLocationManual(
        selectedResult.name,
        selectedResult.latitude,
        selectedResult.longitude
      );
      onChange(data.user);
      setConsentChecked(false);
      setManualInput(data.user.location?.name || selectedResult.name);
      setResults([]);
      setSelectedResult(null);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to save your location.');
    } finally {
      setSaving(false);
    }
  };

  const hasCoordinates = (
    location !== null
    && location.latitude !== null
    && location.longitude !== null
  );

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-[#332844] bg-[#1E1728] px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-[#F5EFE9]">
              {gpsConsent
                ? 'Using GPS location'
                : hasCoordinates
                  ? 'Using manual location'
                  : 'Location not set'}
            </p>
            <p className="mt-0.5 text-xs text-[#9C8FA8]">
              {location?.name || (hasCoordinates ? 'Approximate location saved' : 'No location set')}
            </p>
          </div>
          <button
            type="button"
            onClick={handleUseGps}
            disabled={!consentChecked || requesting || saving}
            className="shrink-0 rounded-lg bg-[#FF4D7E] px-4 py-2 text-sm font-medium text-[#15101C] transition hover:bg-[#FF6A93] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {requesting ? 'Requesting…' : saving ? 'Saving…' : 'Use my location'}
          </button>
        </div>

        <label className="mt-3 flex cursor-pointer items-start gap-2 text-xs text-[#C8BCCF]">
          <input
            type="checkbox"
            checked={consentChecked}
            onChange={(event) => {
              setConsentChecked(event.target.checked);
              setError('');
            }}
            className="mt-0.5 h-4 w-4 accent-[#FF4D7E]"
          />
          <span>
            I consent to using my device location for approximate matching. I can use a manual
            location instead.
          </span>
        </label>

        {permissionState === 'denied' && (
          <p className="mt-2 text-xs text-[#FFB0A8]">
            Location is blocked for this site or by your device settings. Change the permission,
            then try again.
          </p>
        )}
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
          onChange={(event) => {
            setManualInput(event.target.value);
            setResults([]);
            setSelectedResult(null);
            setError('');
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              handleManualSearch();
            }
          }}
          maxLength={100}
          placeholder="Neighborhood, city, country"
          className="flex-1 rounded-lg border border-[#332844] bg-[#1E1728] px-4 py-2.5 text-sm text-[#F5EFE9] placeholder-[#6E6180] outline-none transition focus:border-[#FF4D7E] focus:ring-2 focus:ring-[#FF4D7E]/30"
        />
        <button
          type="button"
          onClick={handleManualSearch}
          disabled={searching || saving || requesting}
          className="shrink-0 rounded-lg border border-[#332844] px-4 py-2.5 text-sm font-medium text-[#F5EFE9] transition hover:border-[#FF4D7E]/50 disabled:opacity-50"
        >
          {searching ? 'Searching…' : 'Search'}
        </button>
      </div>

      {results.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-[#9C8FA8]">Select the correct result:</p>
          {results.map((result) => {
            const selected = (
              selectedResult?.latitude === result.latitude
              && selectedResult?.longitude === result.longitude
            );

            return (
              <button
                key={`${result.latitude}-${result.longitude}-${result.name}`}
                type="button"
                onClick={() => {
                  setSelectedResult(result);
                  setError('');
                }}
                aria-pressed={selected}
                className={`w-full rounded-lg border px-4 py-3 text-left text-sm transition ${
                  selected
                    ? 'border-[#FF4D7E] bg-[#FF4D7E]/10 text-[#F5EFE9]'
                    : 'border-[#332844] bg-[#1E1728] text-[#C8BCCF] hover:border-[#FF4D7E]/50'
                }`}
              >
                {result.name}
              </button>
            );
          })}

          <button
            type="button"
            onClick={handleManualSave}
            disabled={!selectedResult || saving || requesting}
            className="rounded-lg bg-[#FF4D7E] px-4 py-2.5 text-sm font-medium text-[#15101C] transition hover:bg-[#FF6A93] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save selected location'}
          </button>
        </div>
      )}

      <p className="text-xs text-[#6E6180]">
        Exact coordinates stay private and are used only for distance calculations.
        {' '}Location search data © OpenStreetMap contributors.
      </p>
      {error && <p className="text-sm text-[#FF8A80]">{error}</p>}
    </div>
  );
}
