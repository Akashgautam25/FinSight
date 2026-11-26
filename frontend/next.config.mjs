/** @type {import('next').NextConfig} */

// A unique id per build. The browser compares it with the running server's id
// (GET /api/build-id) and reloads when they differ, so a tab left open across a
// rebuild never mixes JavaScript from two different builds ("version skew").
// next.config is evaluated several times during one build (main process + workers);
// storing the id in the environment makes every evaluation (and child process) agree.
if (!process.env.NEXT_BUILD_ID) process.env.NEXT_BUILD_ID = Date.now().toString(36);
const BUILD_ID = process.env.NEXT_BUILD_ID;

const nextConfig = {
  reactStrictMode: true,
  output: "standalone", // used by the production Docker image
  generateBuildId: async () => BUILD_ID,
  env: { NEXT_PUBLIC_BUILD_ID: BUILD_ID },
  productionBrowserSourceMaps: true, // readable stack traces in client error reports
};

export default nextConfig;
