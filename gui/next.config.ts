import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow HMR (hot reload) from other devices on the local network.
  // Only applies in development — has no effect in production builds.
  allowedDevOrigins: ["192.168.0.101"],

  async redirects() {
    return [
      {
        source: "/tradereview",
        destination: "/tradeanalyzer",
        permanent: true, // 301 redirect — good for SEO
      },
    ];
  },
};

export default nextConfig;
