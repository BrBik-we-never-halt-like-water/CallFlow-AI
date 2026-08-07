import createMDX from "@next/mdx";
import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // Docs pages are authored as MDX, so `.mdx` has to be a routable extension.
  pageExtensions: ["ts", "tsx", "mdx"],

  // There are lockfiles above this directory, so Next's workspace-root inference
  // picks the wrong one and warns. Pin it to `web/`, which is the actual app root.
  turbopack: {
    root: path.resolve(__dirname),
  },
};

const withMDX = createMDX({
  options: {
    // Named as a string rather than imported: Turbopack serialises loader options,
    // so a plugin passed as a function reference fails the build.
    remarkPlugins: [["remark-gfm", {}]],
  },
});

export default withMDX(nextConfig);
