/** @type {import('next').NextConfig} */
const nextConfig = {
  distDir: process.env.PAO_BUILD_CHECK === '1' ? '.pao-build-check' : '.pao-next',
  async rewrites() {
    return [{ source: "/v1/:path*", destination: `${process.env.PAO_API_URL || "http://127.0.0.1:8000"}/v1/:path*` }];
  },
};

export default nextConfig;
