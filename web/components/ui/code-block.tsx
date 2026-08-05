"use client";

import { CheckIcon, CopyIcon } from "@phosphor-icons/react/dist/ssr";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

/**
 * Monospace block for machine output — JSON results, schemas, payloads.
 *
 * The JSON colouring is monochrome on purpose: it separates tokens by weight and
 * dimming rather than by hue. Introducing a syntax palette would put arbitrary
 * colour on screen, and this design spends colour only on call state. Structure
 * still reads clearly, and the block never competes with a lamp beside it.
 */
export function CodeBlock({
  code,
  language = "json",
  /** Caption above the block, in mono. */
  label,
  copyable = true,
  className,
  maxHeight,
}: {
  code: string;
  language?: "json" | "text";
  label?: string;
  copyable?: boolean;
  className?: string;
  /** Tailwind max-height class, e.g. `max-h-72`. Adds its own scroll. */
  maxHeight?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label ? <p className="eyebrow text-text-mute">{label}</p> : null}

      <div className="relative rounded-md border border-rule bg-surface-sunken">
        {copyable ? (
          <div className="absolute right-1.5 top-1.5 z-10">
            <CopyButton value={code} />
          </div>
        ) : null}

        <pre
          className={cn(
            "overflow-x-auto p-3 font-mono text-data text-text",
            copyable && "pr-12",
            maxHeight && `${maxHeight} overflow-y-auto`,
          )}
        >
          <code>{language === "json" ? <Json code={code} /> : code}</code>
        </pre>
      </div>
    </div>
  );
}

/**
 * Minimal JSON tokeniser. Deliberately not a full parser: it styles well-formed
 * output the product itself produced, and falls through to plain text for
 * anything it does not recognise rather than mangling it.
 */
function Json({ code }: { code: string }) {
  const tokens = code.split(
    /("(?:\\.|[^"\\])*"\s*:|"(?:\\.|[^"\\])*"|\b-?\d+(?:\.\d+)?(?:e[+-]?\d+)?\b|\btrue\b|\bfalse\b|\bnull\b)/gi,
  );

  return (
    <>
      {tokens.map((token, i) => {
        if (!token) return null;

        // A quoted string followed by a colon is a key.
        if (/^"(?:\\.|[^"\\])*"\s*:$/.test(token)) {
          const colonAt = token.lastIndexOf(":");
          return (
            <span key={i}>
              <span className="font-medium text-text">{token.slice(0, colonAt)}</span>
              <span className="text-text-mute">{token.slice(colonAt)}</span>
            </span>
          );
        }

        if (/^"/.test(token)) {
          return (
            <span key={i} className="text-text-dim">
              {token}
            </span>
          );
        }

        if (/^(-?\d|true$|false$|null$)/i.test(token)) {
          return (
            <span key={i} className="text-text underline decoration-rule-strong decoration-dotted underline-offset-2">
              {token}
            </span>
          );
        }

        // Braces, brackets, commas, whitespace.
        return (
          <span key={i} className="text-text-mute">
            {token}
          </span>
        );
      })}
    </>
  );
}

/**
 * Copy control with an explicit confirmation.
 *
 * The confirmation is the whole point: copying a value is silent, and an
 * operator who is not sure it worked will click again and paste twice.
 */
export function CopyButton({
  value,
  label = "Copy",
  className,
}: {
  value: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be refused outright (insecure context, denied
      // permission). Say so rather than showing a success state that lied.
      setCopied(false);
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      className={cn(
        "inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-sm border border-rule bg-surface-raised px-2",
        "font-mono text-label uppercase tracking-[0.14em] text-text-dim",
        "transition-colors duration-(--dur-micro) hover:bg-surface-hover hover:text-text",
        className,
      )}
    >
      {copied ? (
        <CheckIcon aria-hidden className="size-3.5" />
      ) : (
        <CopyIcon aria-hidden className="size-3.5" />
      )}
      <span aria-live="polite">{copied ? "Copied" : label}</span>
    </button>
  );
}
