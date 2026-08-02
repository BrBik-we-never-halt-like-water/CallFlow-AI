"use client";

import { useEffect } from "react";

/**
 * Wakes the backend as soon as someone lands on the marketing page.
 *
 * The free tier sleeps after inactivity. A visitor typically spends 30-60
 * seconds reading before clicking through to the dashboard, which is roughly
 * how long a cold start takes — so starting the wake here usually means the
 * API is already warm on arrival.
 *
 * Renders nothing and never surfaces an error; this is opportunistic only.
 */
export default function Prewarm() {
  useEffect(() => {
    void fetch("/api/wake", { cache: "no-store" }).catch(() => {});
  }, []);

  return null;
}
