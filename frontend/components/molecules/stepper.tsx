import { DrawnCheck, Icon } from "@/components/atoms/icon";
import { cn } from "@/lib/cn";

export type StepState = "done" | "current" | "upcoming" | "error";

export interface Step {
  label: string;
  state: StepState;
}

const DOT: Record<StepState, string> = {
  done: "bg-brand text-white",
  current: "bg-ink text-on-ink",
  upcoming: "bg-surface-3 text-ink-3",
  error: "bg-danger text-white",
};

/** Pasos conectados; los completos dibujan su check en secuencia y la línea se llena hacia el siguiente. */
export function Stepper({ steps, labels = "right", stagger = 260, className }: { steps: Step[]; labels?: "right" | "below"; stagger?: number; className?: string }) {
  return (
    <ol className={cn("flex w-full items-start", className)}>
      {steps.map((step, i) => {
        const last = i === steps.length - 1;
        return (
          <li key={step.label} className={cn("flex items-center", !last && "flex-1", labels === "below" && "items-start")}>
            <div className={cn("flex items-center gap-2", labels === "below" && "w-14 flex-col gap-1.5 text-center")}>
              <span
                className={cn("relative grid size-6 shrink-0 place-items-center rounded-full text-[11px] font-bold transition-colors duration-300", DOT[step.state])}
                aria-current={step.state === "current" ? "step" : undefined}
              >
                {step.state === "done" && <DrawnCheck size={12} delay={i * stagger} />}
                {step.state === "error" && <Icon name="x" size={12} strokeWidth={3} />}
                {(step.state === "current" || step.state === "upcoming") && i + 1}
                {step.state === "current" && <span aria-hidden className="absolute inset-0 animate-ping-soft rounded-full ring-2 ring-ink" />}
              </span>
              <span
                className={cn(
                  "text-xs leading-tight font-semibold",
                  step.state === "upcoming" ? "text-ink-3" : step.state === "error" ? "text-danger-ink" : "text-ink",
                  labels === "below" && "text-[11px]",
                )}
              >
                {step.label}
              </span>
            </div>
            {!last && (
              <span className={cn("mx-2 h-[3px] flex-1 overflow-hidden rounded-full bg-surface-3", labels === "below" && "mx-0 mt-3 -translate-y-1/2")}>
                <span
                  className={cn(
                    "block h-full origin-left rounded-full bg-brand transition-transform duration-500 ease-out-soft",
                    step.state === "done" ? "scale-x-100" : "scale-x-0",
                  )}
                  style={{ transitionDelay: `${i * stagger + 150}ms` }}
                />
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
