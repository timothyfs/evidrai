import type { NextConfig } from 'next';

const frontendBuild = process.env.NEXT_PUBLIC_APP_BUILD || process.env.VERCEL_GIT_COMMIT_SHA?.slice(0, 7) || 'local';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_APP_BUILD: frontendBuild,
  },
};

export default nextConfig;
