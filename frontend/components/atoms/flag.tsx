"use client";

import { useId } from "react";

import { Icon } from "./icon";

export type Country = "MX" | "CO" | "AR";

const NAMES: Record<Country, string> = { MX: "México", CO: "Colombia", AR: "Argentina" };

/** Banderas dibujadas a mano y simplificadas (los emojis cambian según el sistema operativo). */
export function Flag({ country, size = 16 }: { country: Country | null | undefined; size?: number }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  if (!country) return <Icon name="globe" size={size} />;
  const width = Math.round(size * 1.4);
  return (
    <svg viewBox="0 0 21 15" width={width} height={size} role="img" aria-label={NAMES[country]} className="shrink-0">
      <defs>
        <clipPath id={`${id}-clip`}>
          <rect width="21" height="15" rx="2.6" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${id}-clip)`}>
        {country === "MX" && (
          <>
            <rect width="7" height="15" fill="#0b6b47" />
            <rect x="7" width="7" height="15" fill="#fff" />
            <rect x="14" width="7" height="15" fill="#ce2b37" />
            <circle cx="10.5" cy="7.4" r="1.9" fill="#8a6a32" />
            <path d="M8.9 8.8a1.9 1.9 0 0 0 3.2 0" fill="none" stroke="#0b6b47" strokeWidth=".7" />
          </>
        )}
        {country === "CO" && (
          <>
            <rect width="21" height="7.5" fill="#fcd116" />
            <rect y="7.5" width="21" height="3.75" fill="#1a3f99" />
            <rect y="11.25" width="21" height="3.75" fill="#ce1126" />
          </>
        )}
        {country === "AR" && (
          <>
            <rect width="21" height="15" fill="#75aadb" />
            <rect y="5" width="21" height="5" fill="#fff" />
            <circle cx="10.5" cy="7.5" r="1.6" fill="#f6b40e" />
            <circle cx="10.5" cy="7.5" r="2.3" fill="none" stroke="#f6b40e" strokeWidth=".6" strokeDasharray=".6 .55" />
          </>
        )}
      </g>
      <rect x=".25" y=".25" width="20.5" height="14.5" rx="2.4" fill="none" stroke="rgb(12 21 36 / .12)" strokeWidth=".5" />
    </svg>
  );
}
