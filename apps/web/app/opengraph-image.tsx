import { ImageResponse } from "next/og";

/**
 * Social card: wordmark, headline, and a lamp strip on the Panel surface.
 *
 * No photography and no vendor mark. The strip is the whole idea of the product in one
 * row, which is the only thing worth putting on a card that gets seen at thumbnail size.
 */
export const alt = "CallFlow AI — every call comes back as data";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const LAMPS = [
  "#3E9E7A",
  "#3E9E7A",
  "#5B8FC7",
  "#3E9E7A",
  "#D69B2D",
  "#3E9E7A",
  "#DC4B34",
  "#3E9E7A",
  "#3E9E7A",
  "#37444B",
  "#37444B",
  "#37444B",
];

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#0B0F12",
          padding: 72,
        }}
      >
        {/* Wordmark */}
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              border: "2px solid #35434A",
              borderRadius: 999,
              padding: "10px 16px",
            }}
          >
            <div style={{ width: 14, height: 14, borderRadius: 999, background: "#3E9E7A" }} />
            <div style={{ width: 14, height: 14, borderRadius: 999, background: "#D69B2D" }} />
            <div style={{ width: 14, height: 14, borderRadius: 999, background: "#DC4B34" }} />
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              gap: 10,
              color: "#E8ECEA",
              fontSize: 34,
              fontWeight: 600,
              letterSpacing: "-0.02em",
            }}
          >
            CallFlow
            <span style={{ fontSize: 18, color: "#9AA6AC", letterSpacing: "0.4em" }}>AI</span>
          </div>
        </div>

        {/* Headline */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div
            style={{
              display: "flex",
              color: "#E8ECEA",
              fontSize: 82,
              fontWeight: 600,
              lineHeight: 1.02,
              letterSpacing: "-0.03em",
              maxWidth: 900,
            }}
          >
            Every call comes back as data.
          </div>
          <div
            style={{
              display: "flex",
              color: "#9AA6AC",
              fontSize: 30,
              lineHeight: 1.4,
              maxWidth: 860,
            }}
          >
            Clean calls close themselves. Only the ones that need a person reach one.
          </div>
        </div>

        {/* Lamp strip */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            {LAMPS.map((colour, i) => (
              <div
                key={i}
                style={{ width: 22, height: 22, borderRadius: 999, background: colour }}
              />
            ))}
          </div>
          <div
            style={{
              display: "flex",
              gap: 28,
              color: "#66737A",
              fontSize: 22,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
            }}
          >
            <span>9 closed</span>
            <span>1 retry</span>
            <span>1 needs a person</span>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
