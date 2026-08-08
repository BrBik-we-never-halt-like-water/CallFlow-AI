"use client";

import * as RadixToast from "@radix-ui/react-toast";
import { XIcon } from "@phosphor-icons/react/dist/ssr";
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { Lamp } from "@/components/brand/lamp";
import type { LampState } from "@/lib/lamp";

export type ToastTone = "info" | "success" | "warning" | "error";

/**
 * Toast tones borrow the lamp colours, which is consistent rather than a breach
 * of the discipline rule: a toast reports the result of an action on a call, so
 * it is reporting state. The lamp is always paired with text.
 */
const TONE_LAMP: Record<ToastTone, LampState> = {
  info: "ice",
  success: "jade",
  warning: "brass",
  error: "flare",
};

export interface ToastOptions {
  title: string;
  /** One line on what to do next, where there is something to do. */
  body?: string;
  tone?: ToastTone;
  action?: { label: string; onClick: () => void };
}

interface ToastRecord extends ToastOptions {
  id: number;
}

const ToastContext = createContext<((options: ToastOptions) => void) | null>(null);

/** Maximum simultaneous toasts. Older ones are dropped, not queued. */
const STACK_MAX = 3;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  // A ref rather than state: the counter only ever needs to produce a unique key, and
  // rendering does not depend on its value.
  const nextId = useRef(1);

  const push = useCallback((options: ToastOptions) => {
    const id = nextId.current;
    nextId.current += 1;
    setToasts((current) => [...current, { ...options, id }].slice(-STACK_MAX));
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const value = useMemo(() => push, [push]);

  return (
    <ToastContext.Provider value={value}>
      <RadixToast.Provider duration={5000} swipeDirection="right">
        {children}

        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onDismiss={() => dismiss(toast.id)} />
        ))}

        <RadixToast.Viewport
          className={cn(
            "fixed right-0 top-0 z-100 flex w-[min(400px,calc(100vw-24px))] flex-col gap-2 p-3",
            // Clip horizontally so a toast animating in/out from off-screen right
            // (translate-x-full) can't extend the document width and add a
            // horizontal scrollbar on mobile. `clip` (not `hidden`) keeps the
            // vertical axis visible   no stray scrollbar on the viewport itself.
            "overflow-x-clip outline-none",
          )}
        />
      </RadixToast.Provider>
    </ToastContext.Provider>
  );
}

/**
 * `const toast = useToast()` then `toast({ title: "Run started" })`.
 *
 * Toast titles keep the verb of the action that produced them: `Start run`
 * produces `Run started`, `Mark resolved` produces `Marked resolved`. That
 * consistency is what lets someone confirm at a glance that the thing they
 * clicked is the thing that happened.
 */
export function useToast(): (options: ToastOptions) => void {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used inside <ToastProvider>");
  }
  return context;
}

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: ToastRecord;
  onDismiss: () => void;
}) {
  const tone = toast.tone ?? "info";
  const isError = tone === "error";

  return (
    <RadixToast.Root
      onOpenChange={(open) => {
        if (!open) onDismiss();
      }}
      // An error interrupts; everything else waits its turn in the reading order.
      type={isError ? "foreground" : "background"}
      duration={isError ? 10000 : 5000}
      className={cn(
        "flex items-start gap-3 rounded-md border border-rule-strong bg-surface-raised p-3 shadow-overlay",
        "data-[state=open]:animate-in data-[swipe=end]:translate-x-full",
      )}
    >
      <span className="mt-1">
        <Lamp state={TONE_LAMP[tone]} size="sm" />
      </span>

      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <RadixToast.Title className="text-small font-medium text-text">
          {toast.title}
        </RadixToast.Title>
        {toast.body ? (
          <RadixToast.Description className="text-small text-text-dim">
            {toast.body}
          </RadixToast.Description>
        ) : null}
      </div>

      {toast.action ? (
        <RadixToast.Action
          asChild
          altText={toast.action.label}
          onClick={toast.action.onClick}
        >
          <button
            type="button"
            className="shrink-0 cursor-pointer rounded-sm border border-rule px-2 py-1 text-small font-medium text-text hover:bg-surface-hover"
          >
            {toast.action.label}
          </button>
        </RadixToast.Action>
      ) : null}

      <RadixToast.Close
        aria-label="Dismiss"
        className="-m-1 flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-sm text-text-mute hover:bg-surface-hover hover:text-text"
      >
        <XIcon aria-hidden className="size-3.5" />
      </RadixToast.Close>
    </RadixToast.Root>
  );
}
