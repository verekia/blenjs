/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  reactCompiler: true,
  output: 'export',
  allowedDevOrigins: ['blenjs-app.dev'],
  // Workspace library packages ship TS source; Next transpiles them.
  transpilePackages: ['@blenjs/core', '@blenjs/runtime-three', '@blenjs/runtime-r3f'],
}

export default nextConfig
