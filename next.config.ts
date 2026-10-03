import type { NextConfig } from "next";

const backendUrl = process.env.LOCAL_BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    return [
      {
        source: "/api/simulator/:path*",
        destination: `${backendUrl}/api/simulator/:path*`,
      },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: [{ key: "Referrer-Policy", value: "no-referrer" }] }];
  },
};

export default nextConfig;
