import type { NextConfig } from "next";

/** Where the Next server proxies /api/* (orchestrator). Read at build/start time. */
const ORCHESTRATOR_URL = (process.env.ORCHESTRATOR_URL || "http://localhost:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // Self-contained server bundle for the Docker image deployed on the Vultr VM.
  output: "standalone",
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Browser calls same-origin /api/*; Next forwards to the orchestrator. No CORS, no hardcoded hosts.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${ORCHESTRATOR_URL}/:path*` }];
  },
};

export default nextConfig;
