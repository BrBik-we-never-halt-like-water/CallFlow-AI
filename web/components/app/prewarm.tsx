"use client";

import { useEffect } from "react";

/**
 * Wakes the service as soon as someone lands on a marketing page.
 *
 * A sleeping instance takes a while to start, and a visitor typically spends
 * 30–60 seconds reading before clicking through   which is roughly how long a cold
 * start takes. Beginning the wake here usually means the dashboard is already warm
 * on arrival.
 *
 * Renders nothing and never surfaces an error; this is opportunistic only.
 */
export function Prewarm() {
  useEffect(() => {
    void fetch("/api/wake", { cache: "no-store" }).catch(() => {});
  }, []);

  return null;
}
