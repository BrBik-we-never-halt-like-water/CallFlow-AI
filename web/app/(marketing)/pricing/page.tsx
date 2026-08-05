import type { Metadata } from "next";
import { PricingClient } from "./pricing-client";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Start free with unlimited dry runs, then pay for the calls that actually connect. Compare CallFlow against hiring a tele-caller.",
};

export default function PricingPage() {
  return <PricingClient />;
}
