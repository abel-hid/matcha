'use client';


interface AuthShowcaseProps {
  eyebrow: string;
  headline: string;
  subhead: string;
}

const NODES = [
  { x: 60, y: 80 }, { x: 160, y: 40 }, { x: 260, y: 110 },
  { x: 90, y: 200 }, { x: 220, y: 220 }, { x: 320, y: 180 },
  { x: 40, y: 320 }, { x: 180, y: 340 }, { x: 300, y: 300 },
  { x: 130, y: 260 }, { x: 260, y: 400 }, { x: 70, y: 420 },
];

const LINKS: [number, number][] = [
  [0, 1], [1, 2], [1, 3], [3, 4], [2, 5], [4, 5],
  [3, 9], [4, 9], [6, 7], [7, 8], [7, 9], [8, 10],
  [6, 11], [7, 11], [10, 8],
];

const PULSE_INDICES = [1, 4, 7, 10];

/** Render the shared visual introduction used by authentication pages. */
export default function AuthShowcase({ eyebrow, headline, subhead }: AuthShowcaseProps) {
  return (
    <div className="relative hidden lg:flex lg:w-[44%] flex-col justify-between overflow-hidden bg-[#15101C] px-12 py-14">
      <div className="pointer-events-none absolute -left-24 -top-24 h-96 w-96 rounded-full bg-[#FF4D7E] opacity-[0.12] blur-[100px]" />
      <div className="pointer-events-none absolute bottom-[-6rem] right-[-4rem] h-80 w-80 rounded-full bg-[#F2C879] opacity-[0.10] blur-[110px]" />

      <div className="relative z-10">
        <span className="text-[11px] font-medium uppercase tracking-[0.28em] text-[#F2C879]">
          {eyebrow}
        </span>
      </div>

      <svg
        viewBox="0 0 360 460"
        className="relative z-10 w-full max-w-[320px] self-center opacity-90"
        aria-hidden="true"
      >
        {LINKS.map(([a, b], i) => (
          <line
            key={i}
            x1={NODES[a].x}
            y1={NODES[a].y}
            x2={NODES[b].x}
            y2={NODES[b].y}
            stroke="#4A3B5C"
            strokeWidth="1"
          />
        ))}
        {NODES.map((n, i) => (
          <circle
            key={i}
            cx={n.x}
            cy={n.y}
            r={PULSE_INDICES.includes(i) ? 5 : 3}
            fill={PULSE_INDICES.includes(i) ? '#FF4D7E' : '#8A7A9C'}
            className={PULSE_INDICES.includes(i) ? 'animate-pulse' : ''}
          />
        ))}
      </svg>

      <div className="relative z-10 max-w-sm">
        <h2 className="font-serif text-[2.15rem] leading-[1.15] text-[#F5EFE9]">
          {headline}
        </h2>
        <p className="mt-4 text-[15px] leading-relaxed text-[#9C8FA8]">
          {subhead}
        </p>
      </div>
    </div>
  );
}
