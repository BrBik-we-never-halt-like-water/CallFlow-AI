import { ImageResponse } from "next/og";

/**
 * Apple touch icon, generated rather than shipped as a raster.
 *
 * Every brand asset in this project is generated from the mark, so there is exactly one
 * definition of what the logo is. The previous version of this file was a JPEG.
 */
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

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
          background: "#0B0F12",
        }}
      >
        <div style={{ width: 30, height: 30, borderRadius: 999, background: "#3E9E7A" }} />
        <div style={{ width: 30, height: 30, borderRadius: 999, background: "#D69B2D" }} />
        <div style={{ width: 30, height: 30, borderRadius: 999, background: "#DC4B34" }} />
      </div>
    ),
    size,
  );
}
