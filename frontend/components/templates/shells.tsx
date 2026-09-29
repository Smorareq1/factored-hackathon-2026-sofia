// Plantillas: la estructura de cada tipo de pantalla, sin datos. Las pantallas (screens/) las llenan.
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/** Pantallas de entrada: página blanca, contenido centrado y una franja opcional a todo el ancho al pie. */
export function AuthShell({ top, children, bottom }: { top: ReactNode; children: ReactNode; bottom?: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-surface">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-5 pt-6 sm:px-8">{top}</header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-5 pt-10 pb-14 sm:px-8 lg:pt-14">{children}</main>
      {bottom}
    </div>
  );
}

export function AppHeader({ left, right, className }: { left: ReactNode; right: ReactNode; className?: string }) {
  return (
    <header className={cn("relative z-20 flex h-16 shrink-0 items-center justify-between gap-3 border-b border-line bg-surface px-4 sm:px-6", className)}>
      <div className="flex min-w-0 items-center gap-4">{left}</div>
      <div className="flex shrink-0 items-center gap-2">{right}</div>
    </header>
  );
}

/** Espacio de trabajo: encabezado + contenido + panel lateral (columna en escritorio, cajón en móvil). */
export function WorkspaceShell({
  header,
  aside,
  asideOpen = false,
  onCloseAside,
  children,
}: {
  header: ReactNode;
  aside?: ReactNode;
  asideOpen?: boolean;
  onCloseAside?: () => void;
  children: ReactNode;
}) {
  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-bg">
      {header}
      <div className="relative flex min-h-0 flex-1">
        <main className="flex min-w-0 flex-1 flex-col">{children}</main>
        {aside && asideOpen && (
          <>
            <div aria-hidden onClick={onCloseAside} className="fixed inset-0 z-30 animate-fade bg-scrim lg:hidden" />
            <aside className="fixed inset-y-0 right-0 z-40 w-[min(460px,100vw)] animate-slide-left shadow-pop lg:static lg:z-auto lg:w-[460px] lg:shrink-0 lg:shadow-none">
              {aside}
            </aside>
          </>
        )}
      </div>
    </div>
  );
}
