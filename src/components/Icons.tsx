interface IconProps {
  size?: number;
}

const base = (size: number | undefined) => ({
  width: size ?? 24,
  height: size ?? 24,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2.4,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true as const,
});

export const IconUsers = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <circle cx="9" cy="8" r="3.4" />
    <path d="M3.5 19c.6-3.2 2.7-5 5.5-5s4.9 1.8 5.5 5" />
    <circle cx="16.8" cy="9" r="2.8" />
    <path d="M15.6 14.4c2.5-.3 4.2 1.4 4.9 4.1" />
  </svg>
);

export const IconRadar = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="8.2" />
    <circle cx="12" cy="12" r="4.4" />
    <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
    <path d="M12 12 L16.6 7.4" />
  </svg>
);

export const IconGear = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="3.2" />
    <path d="M12 2.8v3M12 18.2v3M2.8 12h3M18.2 12h3M5.5 5.5l2.1 2.1M16.4 16.4l2.1 2.1M18.5 5.5l-2.1 2.1M7.6 16.4l-2.1 2.1" />
  </svg>
);

export const IconHome = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M3.5 11 12 4l8.5 7" />
    <path d="M5.5 9.5V20h13V9.5" />
    <path d="M10 20v-5.5h4V20" />
  </svg>
);

export const IconChart = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M4 20V4" />
    <path d="M4 20h16" />
    <path d="M8 16v-5M12 16V7M16 16v-3" />
  </svg>
);

export const IconDoc = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M6.5 3.5h7L18 8v12.5h-11.5z" />
    <path d="M13.5 3.5V8H18" />
    <path d="M9 12.5h6M9 16h6" />
  </svg>
);

export const IconCoin = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="8.5" />
    <text
      x="12"
      y="15.6"
      textAnchor="middle"
      fontSize="10.5"
      fontWeight="800"
      fill="currentColor"
      stroke="none"
      fontFamily="Baloo 2, sans-serif"
    >
      $
    </text>
  </svg>
);

export const IconMosque = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M12 3.2 15 6H9z" />
    <path d="M4.5 6h15" />
    <path d="M4 6v9.5M20 6v9.5" />
    <path d="M6.5 6V19h11V6" />
    <circle cx="12" cy="10" r="2.2" fill="currentColor" stroke="none" />
  </svg>
);

export const IconCitadel = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M5 20V9.5L12 5l7 4.5V20" />
    <path d="M9 20v-6h6v6" />
    <path d="M3 20h18" />
    <path d="M7 9.5V6M17 9.5V6" />
  </svg>
);

export const IconSun = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="4.4" />
    <path d="M12 2.6v2.6M12 18.8v2.6M2.6 12h2.6M18.8 12h2.6M5.4 5.4l1.9 1.9M16.7 16.7l1.9 1.9M18.6 5.4l-1.9 1.9M7.3 16.7l-1.9 1.9" />
  </svg>
);

export const IconSend = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M21 3 10.5 13.5" />
    <path d="M21 3l-7 18-3.5-7.5L3 10z" />
  </svg>
);

export const IconRefresh = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M20 12a8 8 0 1 1-2.3-5.6" />
    <path d="M20 3.5V8h-4.5" />
  </svg>
);

export const IconPlus = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);

export const IconTrash = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M4.5 6.5h15" />
    <path d="M9 6.5V4.8h6v1.7" />
    <path d="M6.5 6.5 7.4 20h9.2l.9-13.5" />
    <path d="M10 10.5v6M14 10.5v6" />
  </svg>
);

export const IconCheck = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M4.5 12.5l5 5 10-11" />
  </svg>
);

export const IconBolt = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M13 2.5 4.5 13.5H11l-1 8 8.5-11H12z" />
  </svg>
);

export const IconSparkle = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M12 3.5 13.8 9l5.7 1.8-5.7 1.8L12 18.2 10.2 12.6 4.5 10.8 10.2 9z" />
    <path d="M18.5 15.5l.8 2.4 2.4.8-2.4.8-.8 2.4-.8-2.4-2.4-.8 2.4-.8z" />
  </svg>
);
