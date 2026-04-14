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
          { key: "Content-Security-Policy", value: "default-src 'self'" },
          // HSTS is intentionally omitted here; enable in production via
          // a reverse-proxy or environment-specific next.config override.
        ],
      },
    ];
  },
};
