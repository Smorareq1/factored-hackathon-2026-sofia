import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Imagen mínima para Cloud Run: containers/frontend.Dockerfile copia .next/standalone
  output: "standalone",
  // Sin el botón flotante de Next en dev: tapa la esquina del chat en las grabaciones de la demo.
  devIndicators: false,
};

export default nextConfig;
