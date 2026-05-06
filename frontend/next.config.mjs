const isStandaloneBuild = process.env.NEXT_STANDALONE === "true";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: isStandaloneBuild ? "standalone" : undefined,
  env: {
    NEXT_PUBLIC_BACKEND_URL: process.env.BACKEND_URL ?? "http://localhost:8000",
  },
};

export default nextConfig;
