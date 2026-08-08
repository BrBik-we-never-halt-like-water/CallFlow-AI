import { redirect } from "next/navigation";

/**
 * Organisation and Team moved out of Settings entirely — they're their own page,
 * `/app/organisation`, since both are about the workspace you're switching between,
 * not the product's configuration. `/app/settings` still needs to resolve to
 * something for the generic "Settings" links in the nav and user menu, so it lands
 * on the first real tab instead of 404ing.
 */
export default function SettingsIndexPage() {
  redirect("/app/settings/safety");
}
