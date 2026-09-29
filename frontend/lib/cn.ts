/** Une clases condicionales (el `clsx` de una línea; sin dependencias). */
export function cn(...parts: Array<string | false | null | undefined | 0>): string {
  return parts.filter(Boolean).join(" ");
}
