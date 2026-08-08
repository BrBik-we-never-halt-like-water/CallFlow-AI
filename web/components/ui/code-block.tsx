"use client";

import { CheckIcon, CopyIcon, DownloadSimpleIcon } from "@phosphor-icons/react/dist/ssr";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

/**
 * Monospace block for machine output   JSON results, schemas, payloads.
 *
 * The JSON colouring is monochrome on purpose: it separates tokens by weight and
 * dimming rather than by hue. Introducing a syntax palette would put arbitrary
 * colour on screen, and this design spends colour only on call state. Structure
 * still reads clearly, and the block never competes with a lamp beside it.
 *
 * `variant="terminal"` adds a title bar with window dots   used in docs for
 * shell commands and sample files, where a terminal frame reads as "this runs
 * on your machine" versus the plain block's "this is data the API returned".
 */
export function CodeBlock({
  code,
  language = "json",
  /** Caption above the block, in mono. Ignored by the terminal variant, which shows `title` in its bar instead. */
  label,
  copyable = true,
  bare = false,
  className,
  maxHeight,
  variant = "plain",
  /** Terminal title bar text, e.g. a filename or command. Terminal variant only. */
  title,
  /** Offers a download of `code` as this filename. Terminal variant only. */
  downloadFilename,
}: {
  code: string;
  language?: "json" | "text";
  label?: string;
  copyable?: boolean;
  /** Drop the border and background so the block can sit inside another surface. */
  bare?: boolean;
  className?: string;
  /** Tailwind max-height class, e.g. `max-h-72`. Adds its own scroll. */
  maxHeight?: string;
  variant?: "plain" | "terminal";
  title?: string;
  downloadFilename?: string;
}) {
  if (variant === "terminal") {
    return (
      <div className={cn("flex flex-col gap-1.5", className)}>
        <div className="overflow-hidden rounded-md border border-rule bg-surface-inverse">
          <div className="flex items-center justify-between gap-3 border-b border-white/10 px-3 py-2">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5" aria-hidden>
                <span className="size-2.5 rounded-full bg-lamp-flare" />
                <span className="size-2.5 rounded-full bg-lamp-brass" />
                <span className="size-2.5 rounded-full bg-lamp-jade" />
              </div>
              {title ? (
                <p className="font-mono text-data text-white/60">{title}</p>
              ) : null}
            </div>

            <div className="flex items-center gap-1.5">
              {downloadFilename ? (
                <DownloadButton code={code} filename={downloadFilename} />
              ) : null}
              {copyable ? <CopyButton value={code} className="border-white/15 bg-white/5 text-white/60 hover:bg-white/10 hover:text-white" /> : null}
            </div>
          </div>

          <pre
            className={cn(
              "overflow-x-auto p-4 font-mono text-data leading-[1.6] text-white",
              maxHeight && `${maxHeight} overflow-y-auto`,
            )}
          >
            <code>{language === "json" ? <Json code={code} dark /> : code}</code>
          </pre>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label ? <p className="eyebrow text-text-mute">{label}</p> : null}

      <div
        className={cn(
          "relative",
          bare ? "" : "rounded-md border border-rule bg-surface-sunken",
        )}
      >
        {copyable ? (
          <div className="absolute right-1.5 top-1.5 z-10">
            <CopyButton value={code} />
          </div>
        ) : null}

        <pre
          className={cn(
            "overflow-x-auto p-4 font-mono text-data leading-[1.6] text-text",
            copyable && "pr-14",
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
function Json({ code, dark = false }: { code: string; dark?: boolean }) {
  const tokens = code.split(
    /("(?:\\.|[^"\\])*"\s*:|"(?:\\.|[^"\\])*"|\b-?\d+(?:\.\d+)?(?:e[+-]?\d+)?\b|\btrue\b|\bfalse\b|\bnull\b)/gi,
  );

  const keyColor = dark ? "text-white" : "text-text";
  const punctColor = dark ? "text-white/45" : "text-text-mute";
  const stringColor = dark ? "text-white/70" : "text-text-dim";
  const valueColor = dark
    ? "text-white decoration-white/30"
    : "text-text decoration-rule-strong";

  return (
    <>
      {tokens.map((token, i) => {
        if (!token) return null;

        // A quoted string followed by a colon is a key.
        if (/^"(?:\\.|[^"\\])*"\s*:$/.test(token)) {
          const colonAt = token.lastIndexOf(":");
          return (
            <span key={i}>
              <span className={cn("font-medium", keyColor)}>{token.slice(0, colonAt)}</span>
              <span className={punctColor}>{token.slice(colonAt)}</span>
            </span>
          );
        }

        if (/^"/.test(token)) {
          return (
            <span key={i} className={stringColor}>
              {token}
            </span>
          );
        }

        if (/^(-?\d|true$|false$|null$)/i.test(token)) {
          return (
            <span key={i} className={cn("underline decoration-dotted underline-offset-2", valueColor)}>
              {token}
            </span>
          );
        }

        // Braces, brackets, commas, whitespace.
        return (
          <span key={i} className={punctColor}>
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

/**
 * Saves `code` as a local file. Client-side only   a Blob URL, no request to
 * any backend   so a sample CSV/JSON in the docs can be grabbed as a real file
 * rather than copy-pasted into one.
 */
function DownloadButton({ code, filename }: { code: string; filename: string }) {
  function download() {
    const blob = new Blob([code], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <button
      type="button"
      onClick={download}
      className={cn(
        "inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-sm border border-white/15 bg-white/5 px-2",
        "font-mono text-label uppercase tracking-[0.14em] text-white/60",
        "transition-colors duration-(--dur-micro) hover:bg-white/10 hover:text-white",
      )}
    >
      <DownloadSimpleIcon aria-hidden className="size-3.5" />
      <span>Download</span>
    </button>
  );
}
