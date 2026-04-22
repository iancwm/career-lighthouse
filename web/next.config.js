/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV !== "production"

module.exports = {
  output: "standalone",

  async headers() {
    const scriptSrc = ["'self'", "'unsafe-inline'"]
    if (isDev) {
      scriptSrc.push("'unsafe-eval'")
    }

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
            value:
              "default-src 'self'; " +
              `script-src ${scriptSrc.join(" ")}; ` +
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " +
              "font-src 'self' https://fonts.gstatic.com; " +
              "connect-src 'self' " +
              (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"),
          },
          // HSTS is intentionally omitted here; enable in production via
          // a reverse-proxy or environment-specific next.config override.
        ],
      },
    ];
  },
};
