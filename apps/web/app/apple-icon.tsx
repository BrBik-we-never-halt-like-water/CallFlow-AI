import { ImageResponse } from "next/og";
import { BRAND } from "@/lib/brand-assets";

/**
 * Apple touch icon, generated rather than shipped as a raster.
 *
 * Every brand asset in this project is generated from the mark, so there is exactly one
 * definition of what the logo is. The previous version of this file was a JPEG.
 *
 * The colours come from `lib/brand-assets` because `next/og` resolves no CSS custom
 * properties. That claim above was briefly untrue: this file held its own copy of the
 * palette and kept rendering the pre-dark-pivot one.
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
          background: BRAND.plate,
        }}
      >
        {[BRAND.lamp.jade, BRAND.lamp.brass, BRAND.lamp.flare].map((colour) => (
          <div
            key={colour}
            style={{ width: 30, height: 30, borderRadius: 999, background: colour }}
          />
        ))}
      </div>
    ),
    size,
  );
}
