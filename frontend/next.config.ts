import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Imagen mínima para Cloud Run: containers/frontend.Dockerfile copia .next/standalone
  output: "standalone",
};

export default nextConfig;
