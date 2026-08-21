/**
 * A pass-through.
 *
 * This used to render the page heading and a tab strip of its own, which
 * made sense while each Settings pane was a separate route. Settings is now
 * one tabbed page (`page.tsx`) holding Organisation, Team, Sharing, API keys
 * and Profile, so a second header and a second tab row here would nest one
 * inside the other. The remaining child routes (`api-keys`, and the
 * `billing`/`integrations` redirects) render standalone.
 */
export default function SettingsLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <>{children}</>;
}
