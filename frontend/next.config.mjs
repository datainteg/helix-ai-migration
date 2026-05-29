/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Same-origin API proxy: the browser calls the frontend origin (/api/*),
  // and the Next server forwards to the backend over the internal docker
  // network. Keeps requests same-origin so the HttpOnly SameSite=strict
  // session cookie is sent (cross-origin http cannot carry it).
  async rewrites() {
    const backend = process.env.BACKEND_PROXY_URL || "http://helix-backend:8000";
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
    ];
  },
};

export default nextConfig;
