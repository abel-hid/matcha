'use client';

import Link from 'next/link';
import {
  PointerEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import type {
  MapLocation,
  MapProfile,
} from '@/app/types';

interface UserMapProps {
  currentUserLocation: MapLocation;
  profiles: MapProfile[];
  apiBaseUrl: string;
}

interface Point {
  x: number;
  y: number;
}

const TILE_SIZE = 256;
const MAP_TILE_URL = (
  process.env.NEXT_PUBLIC_MAP_TILE_URL
  || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
);
const MIN_ZOOM = 3;
const MAX_ZOOM = 17;
const MAX_MERCATOR_LATITUDE = 85.05112878;


/** Keep a number inside the specified minimum and maximum values. */
function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}


/** Return the full Web Mercator world size for the selected zoom level. */
function worldSize(zoom: number) {
  return TILE_SIZE * (2 ** zoom);
}


/** Project geographic coordinates into Web Mercator pixel coordinates. */
function project(latitude: number, longitude: number, zoom: number): Point {
  const size = worldSize(zoom);
  const safeLatitude = clamp(
    latitude,
    -MAX_MERCATOR_LATITUDE,
    MAX_MERCATOR_LATITUDE,
  );
  const sine = Math.sin((safeLatitude * Math.PI) / 180);

  return {
    x: ((longitude + 180) / 360) * size,
    y: (
      0.5
      - Math.log((1 + sine) / (1 - sine)) / (4 * Math.PI)
    ) * size,
  };
}


/** Convert Web Mercator pixel coordinates back to latitude and longitude. */
function unproject(point: Point, zoom: number): MapLocation {
  const size = worldSize(zoom);
  const longitude = (point.x / size) * 360 - 180;
  const normalizedY = 0.5 - point.y / size;
  const latitude = (
    90
    - (360 * Math.atan(Math.exp(-normalizedY * 2 * Math.PI))) / Math.PI
  );

  return {
    name: '',
    latitude: clamp(
      latitude,
      -MAX_MERCATOR_LATITUDE,
      MAX_MERCATOR_LATITUDE,
    ),
    longitude: ((longitude + 540) % 360) - 180,
  };
}


/** Build the accessible label shown for a map profile marker. */
function markerTitle(profile: MapProfile) {
  return `${profile.firstName} ${profile.lastName}, ${profile.age}`;
}


/** Render an interactive map with panning, zooming, markers, and profile popups. */
export default function UserMap({
  currentUserLocation,
  profiles,
  apiBaseUrl,
}: UserMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    center: Point;
  } | null>(null);

  const [dimensions, setDimensions] = useState({
    width: 800,
    height: 560,
  });
  const [center, setCenter] = useState({
    latitude: currentUserLocation.latitude,
    longitude: currentUserLocation.longitude,
  });
  const [zoom, setZoom] = useState(11);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    /** Close the profile popup when the user clicks outside the map. */
    const handleOutsidePointerDown = (
      event: globalThis.PointerEvent,
    ) => {
      const mapElement = containerRef.current;

      if (
        mapElement
        && event.target instanceof Node
        && !mapElement.contains(event.target)
      ) {
        setSelectedId(null);
      }
    };

    document.addEventListener(
      'pointerdown',
      handleOutsidePointerDown,
    );

    return () => {
      document.removeEventListener(
        'pointerdown',
        handleOutsidePointerDown,
      );
    };
  }, []);

  useEffect(() => {
    const element = containerRef.current;

    if (!element) {
      return;
    }

    const observer = new ResizeObserver(([entry]) => {
      setDimensions({
        width: Math.max(320, entry.contentRect.width),
        height: Math.max(420, entry.contentRect.height),
      });
    });

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    const locations = [
      currentUserLocation,
      ...profiles.map((profile) => profile.location),
    ];

    if (
      !locations.length
      || dimensions.width <= 0
      || dimensions.height <= 0
    ) {
      return;
    }

    let selectedZoom = MIN_ZOOM;
    let selectedCenter = {
      latitude: currentUserLocation.latitude,
      longitude: currentUserLocation.longitude,
    };

    for (
      let candidateZoom = MAX_ZOOM;
      candidateZoom >= MIN_ZOOM;
      candidateZoom -= 1
    ) {
      const points = locations.map((location) => project(
        location.latitude,
        location.longitude,
        candidateZoom,
      ));

      const minimumX = Math.min(
        ...points.map((point) => point.x),
      );
      const maximumX = Math.max(
        ...points.map((point) => point.x),
      );
      const minimumY = Math.min(
        ...points.map((point) => point.y),
      );
      const maximumY = Math.max(
        ...points.map((point) => point.y),
      );

      if (
        maximumX - minimumX <= dimensions.width - 100
        && maximumY - minimumY <= dimensions.height - 120
      ) {
        selectedZoom = candidateZoom;

        const geographicCenter = unproject({
          x: (minimumX + maximumX) / 2,
          y: (minimumY + maximumY) / 2,
        }, candidateZoom);

        selectedCenter = {
          latitude: geographicCenter.latitude,
          longitude: geographicCenter.longitude,
        };

        break;
      }
    }

    setZoom(selectedZoom);
    setCenter(selectedCenter);
  }, [
    currentUserLocation,
    dimensions.height,
    dimensions.width,
    profiles,
  ]);

  const centerPoint = useMemo(
    () => project(
      center.latitude,
      center.longitude,
      zoom,
    ),
    [
      center.latitude,
      center.longitude,
      zoom,
    ],
  );

  const viewportLeft = centerPoint.x - dimensions.width / 2;
  const viewportTop = centerPoint.y - dimensions.height / 2;
  const tileCount = 2 ** zoom;

  const tiles = useMemo(() => {
    const minimumTileX = Math.floor(
      viewportLeft / TILE_SIZE,
    );
    const maximumTileX = Math.floor(
      (viewportLeft + dimensions.width) / TILE_SIZE,
    );
    const minimumTileY = Math.max(
      0,
      Math.floor(viewportTop / TILE_SIZE),
    );
    const maximumTileY = Math.min(
      tileCount - 1,
      Math.floor(
        (viewportTop + dimensions.height) / TILE_SIZE,
      ),
    );

    const result: {
      key: string;
      sourceX: number;
      sourceY: number;
      left: number;
      top: number;
    }[] = [];

    for (
      let tileY = minimumTileY;
      tileY <= maximumTileY;
      tileY += 1
    ) {
      for (
        let tileX = minimumTileX;
        tileX <= maximumTileX;
        tileX += 1
      ) {
        const wrappedX = (
          (tileX % tileCount) + tileCount
        ) % tileCount;

        result.push({
          key: `${zoom}-${tileX}-${tileY}`,
          sourceX: wrappedX,
          sourceY: tileY,
          left: tileX * TILE_SIZE - viewportLeft,
          top: tileY * TILE_SIZE - viewportTop,
        });
      }
    }

    return result;
  }, [
    dimensions.height,
    dimensions.width,
    tileCount,
    viewportLeft,
    viewportTop,
    zoom,
  ]);

  /** Project geographic coordinates into the visible map viewport. */
  const markerPosition = (location: MapLocation) => {
    const point = project(
      location.latitude,
      location.longitude,
      zoom,
    );

    return {
      x: point.x - viewportLeft,
      y: point.y - viewportTop,
    };
  };

  /** Clamp zoom changes to the map's supported zoom range. */
  const changeZoom = (nextZoom: number) => {
    setZoom(clamp(
      nextZoom,
      MIN_ZOOM,
      MAX_ZOOM,
    ));
  };

  useEffect(() => {
    const mapElement = containerRef.current;

    if (!mapElement) {
      return;
    }

    /**
     * Use a native non-passive wheel listener because React wheel listeners
     * may be passive and cannot reliably call preventDefault().
     */
    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();

      setZoom((currentZoom) => clamp(
        currentZoom + (event.deltaY < 0 ? 1 : -1),
        MIN_ZOOM,
        MAX_ZOOM,
      ));
    };

    mapElement.addEventListener(
      'wheel',
      handleWheel,
      {
        passive: false,
      },
    );

    return () => {
      mapElement.removeEventListener(
        'wheel',
        handleWheel,
      );
    };
  }, []);

  /** Start map dragging or close the popup when the empty map is clicked. */
  const handlePointerDown = (
    event: PointerEvent<HTMLDivElement>,
  ) => {
    if (event.button !== 0) {
      return;
    }

    if (event.target === event.currentTarget) {
      setSelectedId(null);
    }

    event.currentTarget.setPointerCapture(
      event.pointerId,
    );

    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      center: centerPoint,
    };
  };

  /** Pan the map while an active pointer drag gesture is moving. */
  const handlePointerMove = (
    event: PointerEvent<HTMLDivElement>,
  ) => {
    const drag = dragRef.current;

    if (
      !drag
      || drag.pointerId !== event.pointerId
    ) {
      return;
    }

    const geographicCenter = unproject({
      x: drag.center.x - (
        event.clientX - drag.startX
      ),
      y: drag.center.y - (
        event.clientY - drag.startY
      ),
    }, zoom);

    setCenter({
      latitude: geographicCenter.latitude,
      longitude: geographicCenter.longitude,
    });
  };

  /** Finish the current pointer drag operation. */
  const stopDragging = (
    event: PointerEvent<HTMLDivElement>,
  ) => {
    if (
      dragRef.current?.pointerId
      === event.pointerId
    ) {
      dragRef.current = null;
    }
  };

  const selectedProfile = profiles.find(
    (profile) => profile.id === selectedId,
  ) || null;

  const selectedPosition = selectedProfile
    ? markerPosition(selectedProfile.location)
    : null;

  return (
    <div
      ref={containerRef}
      className="relative h-[65vh] min-h-[460px] w-full touch-none overflow-hidden rounded-2xl border border-[#332844] bg-[#171D24] select-none"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={stopDragging}
      onPointerCancel={stopDragging}
    >
      {tiles.map((tile) => (
        <img
          key={tile.key}
          src={MAP_TILE_URL
            .replace('{z}', String(zoom))
            .replace('{x}', String(tile.sourceX))
            .replace('{y}', String(tile.sourceY))}
          alt=""
          draggable={false}
          className="pointer-events-none absolute h-64 w-64 max-w-none"
          style={{
            left: tile.left,
            top: tile.top,
          }}
        />
      ))}

      <MapMarker
        label="You"
        title={`Your approximate location: ${currentUserLocation.name}`}
        position={markerPosition(currentUserLocation)}
        current
        onClick={() => setSelectedId(null)}
      />

      {profiles.map((profile) => (
        <MapMarker
          key={profile.id}
          label={profile.firstName
            .slice(0, 1)
            .toUpperCase()}
          title={markerTitle(profile)}
          position={markerPosition(profile.location)}
          selected={selectedId === profile.id}
          onClick={() => setSelectedId(profile.id)}
        />
      ))}

      {selectedProfile && selectedPosition && (
        <div
          className="absolute z-30 w-64 -translate-x-1/2 rounded-xl border border-[#FF4D7E]/30 bg-[#15101C] p-3 shadow-2xl"
          style={{
            left: clamp(
              selectedPosition.x,
              140,
              dimensions.width - 140,
            ),
            top: clamp(
              selectedPosition.y - 150,
              12,
              dimensions.height - 170,
            ),
          }}
          onPointerDown={(event) => {
            event.stopPropagation();
          }}
        >
          <div className="flex gap-3">
            <div className="h-12 w-12 shrink-0 overflow-hidden rounded-full bg-[#332844]">
              {selectedProfile.profilePicture ? (
                <img
                  src={`${apiBaseUrl}${selectedProfile.profilePicture}`}
                  alt=""
                  draggable={false}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full items-center justify-center text-[#F5EFE9]">
                  {selectedProfile.firstName
                    .slice(0, 1)
                    .toUpperCase()}
                </div>
              )}
            </div>

            <div className="min-w-0">
              <p className="truncate font-medium text-[#F5EFE9]">
                {selectedProfile.firstName}{' '}
                {selectedProfile.lastName},{' '}
                {selectedProfile.age}
              </p>

              <p className="mt-0.5 truncate text-xs text-[#9C8FA8]">
                {selectedProfile.location.name}
              </p>

              <p className="mt-1 text-xs text-[#F2C879]">
                {selectedProfile.distanceKm} km
                {' · '}
                fame {selectedProfile.fameRating}
              </p>
            </div>
          </div>

          <Link
            href={`/users/${encodeURIComponent(selectedProfile.username)}`}
            className="mt-3 block rounded-lg bg-[#FF4D7E] px-3 py-2 text-center text-sm font-medium text-[#15101C] hover:bg-[#FF6A93]"
          >
            Open profile
          </Link>
        </div>
      )}

      <div
        className="absolute right-3 top-3 z-40 flex flex-col overflow-hidden rounded-lg border border-[#332844] bg-[#15101C]/95 shadow-lg"
        onPointerDown={(event) => {
          event.stopPropagation();
        }}
      >
        <button
          type="button"
          onClick={() => changeZoom(zoom + 1)}
          disabled={zoom >= MAX_ZOOM}
          aria-label="Zoom in"
          className="h-10 w-10 text-xl text-[#F5EFE9] hover:bg-[#332844] disabled:opacity-40"
        >
          +
        </button>

        <button
          type="button"
          onClick={() => changeZoom(zoom - 1)}
          disabled={zoom <= MIN_ZOOM}
          aria-label="Zoom out"
          className="h-10 w-10 border-t border-[#332844] text-xl text-[#F5EFE9] hover:bg-[#332844] disabled:opacity-40"
        >
          -
        </button>
      </div>

      <div className="absolute bottom-2 right-2 z-40 rounded bg-white/90 px-1.5 py-0.5 text-[10px] text-black">
        ©{' '}
        <a
          href="https://www.openstreetmap.org/copyright"
          target="_blank"
          rel="noreferrer"
          className="underline"
        >
          OpenStreetMap
        </a>{' '}
        contributors
      </div>
    </div>
  );
}


/** Render one profile marker at its calculated map position. */
function MapMarker({
  label,
  title,
  position,
  current = false,
  selected = false,
  onClick,
}: {
  label: string;
  title: string;
  position: Point;
  current?: boolean;
  selected?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      onPointerDown={(event) => {
        event.stopPropagation();
      }}
      className={`absolute z-20 flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 text-xs font-bold shadow-lg transition hover:scale-110 ${
        current
          ? 'h-10 w-10 border-white bg-[#2F80ED] text-white'
          : selected
            ? 'h-11 w-11 border-white bg-[#FF4D7E] text-[#15101C]'
            : 'h-9 w-9 border-[#F5EFE9] bg-[#FF4D7E] text-[#15101C]'
      }`}
      style={{
        left: position.x,
        top: position.y,
      }}
    >
      {label}
    </button>
  );
}