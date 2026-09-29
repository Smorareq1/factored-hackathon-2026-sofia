"use client";

import dynamic from "next/dynamic";

// Solo en el cliente: la sesión de la demo vive en sessionStorage.
const ChatScreen = dynamic(() => import("@/components/screens/chat-screen"), { ssr: false });

export default function ChatPage() {
  return <ChatScreen />;
}
