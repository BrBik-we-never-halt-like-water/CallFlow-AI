import { ImageResponse } from "next/og";

/**
 * Apple touch icon, generated rather than shipped as a raster.
 *
 * Every brand asset in this project is generated from the mark, so there is exactly one
 * definition of what the logo is. The previous version of this file was a JPEG.
 *
 * Light mark on white, matching `app/icon.svg`. A home-screen tile and a browser
 * tab are both chrome the site does not own, and a dark tile there reads as a
 * different product's icon than the one in the header. This was `#0B0F12` with
 * the dark-surface lamp values, which is right inside the app and wrong here.
 *
 * Lamp colours are the light-theme tokens verbatim (globals.css): jade #2f8f6b,
 * brass #c2871a, flare #d2402a. Keep them in step with `icon.svg`.
 */
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

const LAMPS = ["#2f8f6b", "#c2871a", "#d2402a"];

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 18,
          background: "#ffffff",
        }}
      >
        {LAMPS.map((fill) => (
          <div
            key={fill}
            style={{ width: 30, height: 30, borderRadius: 999, background: fill }}
          />
        ))}
      </div>
    ),
    size,
  );
}
