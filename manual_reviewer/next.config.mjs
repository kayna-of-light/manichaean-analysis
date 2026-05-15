/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  serverExternalPackages: ['better-sqlite3'],
  experimental: {
    // keep large image responses uncompressed for pixel-accurate review
  },
};

export default nextConfig;
