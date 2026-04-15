/** @type {import('next').NextConfig} */
module.exports = {
  output: "standalone",

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-XSS-Protection", value: "1; mode=block" },
          {
            key: "Content-Security-Policy",
            // 'unsafe-inline' is required for Next.js's inline hydration scripts
            // and Tailwind's inline styles. script-src also allows same-origin
            // static chunks; connect-src allows browser → API calls.
            value: "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self' " + (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"),
          },
          // HSTS is intentionally omitted here; enable in production via
          // a reverse-proxy or environment-specific next.config override.
        ],
      },
    ];
  },
};
