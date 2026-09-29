import type { Metadata } from "next";

import DesignScreen from "@/components/screens/design-screen";

export const metadata: Metadata = { title: "Sofía DS — sistema de diseño" };

export default function DesignPage() {
  return <DesignScreen />;
}
