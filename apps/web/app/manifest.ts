import type { MetadataRoute } from "next";

/**
 * Web app manifest. Vendor-neutral throughout, and the icons are generated from the
 * mark rather than shipped as rasters.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "CallFlow AI",
    short_name: "CallFlow",
    description:
      "An operations layer for outbound phone calls. Load a list, write a goal, and get typed results back.",
    start_url: "/app",
    display: "standalone",
    // Panel, because the app the manifest launches is the dashboard.
    background_color: "#0B0F12",
    theme_color: "#0B0F12",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
      { src: "/apple-icon", sizes: "180x180", type: "image/png" },
    ],
  };
}
