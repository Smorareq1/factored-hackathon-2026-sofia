import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

import { Icon, type IconName } from "./icon";
import { Spinner } from "./spinner";

export type ButtonVariant = "primary" | "ink" | "secondary" | "soft" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

const VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-brand text-white hover:bg-brand-strong",
  ink: "bg-ink text-on-ink hover:bg-ink-2",
  secondary: "bg-surface text-ink ring-[1.5px] ring-line-strong ring-inset hover:ring-ink",
  soft: "bg-surface-3 text-ink hover:bg-line-strong",
  ghost: "text-ink-2 hover:bg-surface-3 hover:text-ink",
  danger: "bg-danger text-white hover:bg-danger-ink",
};

// Deshabilitado: gris sólido (no el color de marca apagado). Mientras carga conserva su color.
const DISABLED: Record<ButtonVariant, string> = {
  primary: "bg-surface-3 text-ink-4",
  ink: "bg-surface-3 text-ink-4",
  secondary: "bg-surface text-ink-4 ring-[1.5px] ring-line ring-inset",
  soft: "bg-surface-3 text-ink-4",
  ghost: "text-ink-4",
  danger: "bg-surface-3 text-ink-4",
};

const SIZE: Record<ButtonSize, string> = {
  sm: "h-8 gap-1.5 rounded-full px-3.5 text-xs",
  md: "h-10 gap-2 rounded-full px-5 text-sm",
  lg: "h-12 gap-2 rounded-full px-6 text-[15px]",
};

const ICON_SIZE: Record<ButtonSize, number> = { sm: 14, md: 16, lg: 18 };

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: IconName;
  iconRight?: IconName;
  loading?: boolean;
  block?: boolean;
}

export function Button({
  variant = "primary",
  size = "md",
  icon,
  iconRight,
  loading = false,
  block = false,
  disabled,
  className,
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "relative inline-flex select-none items-center justify-center font-semibold whitespace-nowrap",
        "transition-[background-color,border-color,color,box-shadow,transform] duration-200 ease-out-soft",
        "active:scale-[0.97] disabled:pointer-events-none",
        disabled && !loading ? DISABLED[variant] : VARIANT[variant],
        SIZE[size],
        block && "w-full",
        className,
      )}
      {...rest}
    >
      {loading ? <Spinner size={ICON_SIZE[size]} /> : icon && <Icon name={icon} size={ICON_SIZE[size]} />}
      {children}
      {iconRight && !loading && <Icon name={iconRight} size={ICON_SIZE[size]} />}
    </button>
  );
}

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  icon: IconName;
  /** Obligatorio: es el nombre accesible y el tooltip nativo. */
  label: string;
  pressed?: boolean;
  variant?: "ghost" | "secondary";
  spinning?: boolean;
}

export function IconButton({
  icon,
  label,
  pressed,
  variant = "secondary",
  spinning = false,
  className,
  type = "button",
  ...rest
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      className={cn(
        "inline-grid size-10 shrink-0 place-items-center rounded-full text-ink-2 transition duration-200 ease-out-soft",
        "hover:text-ink active:scale-95 disabled:pointer-events-none disabled:opacity-45",
        pressed
          ? "bg-ink text-on-ink hover:text-on-ink"
          : variant === "secondary"
            ? "bg-surface ring-[1.5px] ring-line ring-inset hover:ring-ink"
            : "hover:bg-surface-3",
        className,
      )}
      {...rest}
    >
      <Icon name={icon} size={18} className={spinning ? "animate-orbit" : undefined} />
    </button>
  );
}
