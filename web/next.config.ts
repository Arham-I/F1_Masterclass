import type { NextConfig } from "next";

// Static export: the site is plain HTML/JS/JSON built from the files in data/ and public/data/.
// Nothing runs on a server, so there is no API, database or secret to protect.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  poweredByHeader: false,
};

export default nextConfig;
