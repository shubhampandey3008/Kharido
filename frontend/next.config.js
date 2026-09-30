/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy /api/* to the FastAPI backend during development
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
