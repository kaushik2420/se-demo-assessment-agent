"use client";
import { useState } from "react";

/**
 * SurveySparrow logo — uses the OFFICIAL brand SVG sitting in /public/logo.svg.
 *
 * The mark is transparent-background (no colored square), so we render the SVG
 * directly. If for any reason /logo.svg fails to load (CDN issue, broken path),
 * we fall back to Clearbit, then to an inline minimal teal mark.
 *
 * Brand teal (actual): #4A9CA6
 */

type Variant = "navbar" | "login";

const SOURCES = ["/logo.svg", "/logo.png", "https://logo.clearbit.com/surveysparrow.com"];

export function Logo({ variant = "navbar" }: { variant?: Variant }) {
  const [idx, setIdx] = useState(0);

  const sizes = {
    navbar: { mark: 36, wordmark: "text-[15px]", sub: "text-[11px]" },
    login:  { mark: 56, wordmark: "text-[20px]", sub: "text-[13px]" },
  }[variant];

  return (
    <div className="flex items-center gap-3">
      <div
        style={{ width: sizes.mark, height: sizes.mark }}
        className="flex-shrink-0 grid place-items-center"
      >
        {idx < SOURCES.length ? (
          <img
            src={SOURCES[idx]}
            alt="SurveySparrow"
            width={sizes.mark}
            height={sizes.mark}
            onError={() => setIdx(idx + 1)}
            className="object-contain w-full h-full"
          />
        ) : (
          <InlineFallback size={sizes.mark} />
        )}
      </div>

      <div className="leading-tight">
        <div className={`${sizes.wordmark} font-semibold text-ss-navy`}>SurveySparrow</div>
        <div className={`${sizes.sub} text-ss-navy-soft`}>SE Coach</div>
      </div>
    </div>
  );
}

function InlineFallback({ size }: { size: number }) {
  // Compact teal "S" — used only if all three image sources fail
  return (
    <svg viewBox="0 0 36 36" width={size} height={size} aria-label="SurveySparrow">
      <rect width="36" height="36" rx="8" fill="#4A9CA6" />
      <text x="50%" y="56%" dominantBaseline="middle" textAnchor="middle"
            fontFamily="-apple-system,BlinkMacSystemFont,Inter,sans-serif"
            fontSize="20" fontWeight="700" fill="#FFFFFF">S</text>
    </svg>
  );
}
