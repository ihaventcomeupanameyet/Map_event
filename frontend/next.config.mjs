const isStandaloneBuild = process.env.NEXT_STANDALONE === "true";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: isStandaloneBuild ? "standalone" : undefined,
};

export default nextConfig;
