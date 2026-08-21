/**
 * Re-created on every navigation, so the `.page-enter` animation replays and
 * the page content fades in while the nav and tab bar stay put. See the
 * `.page-enter` note in globals.css.
 *
 * `flex min-h-0 flex-1 flex-col` is load-bearing, not cosmetic. This div sits
 * between the shell's `<main>` and every page, so a plain block here breaks
 * the height chain for the fixed-viewport routes: the dashboard grid and the
 * chat panes both resolve their height against their parent, and an
 * unbounded wrapper let them grow with their content instead of scrolling
 * inside it. On scrolling routes it is inert - a flex column with one child
 * lays out exactly as a block would.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <div className="page-enter flex min-h-0 flex-1 flex-col">{children}</div>
  );
}
