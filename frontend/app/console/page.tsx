"use client";

import dynamic from "next/dynamic";

// Solo en el cliente: la sesión de la demo vive en sessionStorage.
const ConsoleScreen = dynamic(() => import("@/components/screens/console-screen"), { ssr: false });

export default function ConsolePage() {
  return <ConsoleScreen />;
}
