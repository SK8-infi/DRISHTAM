import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["leaflet", "react-leaflet"],

  // ── Security Headers ──────────────────────────────────────
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-XSS-Protection", value: "1; mode=block" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), payment=()",
          },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              // Next.js requires inline styles and scripts
              "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              // MapMyIndia / Leaflet tiles + API backend
              `img-src 'self' data: blob: https://*.mappls.com https://*.openstreetmap.org https://tile.openstreetmap.org https://*.basemaps.cartocdn.com`,
              `connect-src 'self' http://localhost:8000 ${process.env.NEXT_PUBLIC_API_URL || ""} https://*.mappls.com https://*.basemaps.cartocdn.com https://*.run.app`,
              "worker-src 'self' blob:",
              "frame-ancestors 'none'",
            ].join("; "),
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=31536000; includeSubDomains; preload",
          },
        ],
      },
    ];
  },

  // ── Disable X-Powered-By header ───────────────────────────
  poweredByHeader: false,

  // ── Enable gzip compression ───────────────────────────────
  compress: true,

  // ── Strict mode for development ───────────────────────────
  reactStrictMode: true,
};

export default nextConfig;
