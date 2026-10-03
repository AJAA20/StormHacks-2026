import type { NextConfig } from "next";

// FastAPI backend (Person 3). Requests to /api/* are forwarded there, so the
// browser only talks to Next.js and CORS never applies. 127.0.0.1, not
// localhost: Node may resolve localhost to IPv6, which uvicorn does not bind.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
};

export default nextConfig;
