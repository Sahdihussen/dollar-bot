function PalmTree({ className }: { className: string }) {
  return (
    <svg className={className} viewBox="0 0 130 220" aria-hidden="true">
      <path
        d="M66 218 C 60 150, 74 96, 64 36"
        stroke="#3e7a3e"
        strokeWidth="13"
        fill="none"
        strokeLinecap="round"
      />
      <g stroke="#2f6b2f" strokeWidth="11" strokeLinecap="round" fill="none">
        <path d="M64 40 C 18 30, 4 12, 6 -6" />
        <path d="M64 40 C 108 30, 124 14, 126 -4" />
        <path d="M64 40 C 34 10, 32 -8, 38 -20" />
        <path d="M64 40 C 92 10, 98 -8, 92 -20" />
        <path d="M64 40 C 64 12, 72 -8, 80 -16" />
      </g>
      <circle cx="64" cy="40" r="8" fill="#2f6b2f" />
    </svg>
  );
}

export default function Background() {
  return (
    <div className="stage" aria-hidden="true">
      <div className="scene">
        <div className="sun" />
        <div className="cloud cloud-1" />
        <div className="cloud cloud-2" />
        <div className="cloud cloud-3" />
        <svg className="hills" viewBox="0 0 800 320" preserveAspectRatio="none">
          <path
            d="M0 190 C 130 100, 260 80, 400 140 C 540 200, 660 130, 800 170 L 800 320 L 0 320 Z"
            fill="#8fd089"
            opacity="0.85"
          />
          <path
            d="M0 240 C 160 160, 320 180, 470 230 C 600 270, 700 220, 800 260 L 800 320 L 0 320 Z"
            fill="#55b06a"
            opacity="0.9"
          />
          <path
            d="M0 285 C 200 235, 420 270, 800 240 L 800 320 L 0 320 Z"
            fill="#3d8f57"
            opacity="0.92"
          />
        </svg>
        <svg className="road" viewBox="0 0 800 260" preserveAspectRatio="none">
          <path
            d="M410 0 C 290 100, 540 170, 430 260"
            fill="none"
            stroke="#eec06f"
            strokeWidth="58"
            strokeLinecap="round"
            opacity="0.95"
          />
          <path
            d="M410 0 C 290 100, 540 170, 430 260"
            fill="none"
            stroke="#fff3d0"
            strokeWidth="7"
            strokeDasharray="30 26"
            strokeLinecap="round"
            opacity="0.95"
          />
        </svg>
        <PalmTree className="palm palm-left" />
        <PalmTree className="palm palm-right" />
      </div>
    </div>
  );
}
