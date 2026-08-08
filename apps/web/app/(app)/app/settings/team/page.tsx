import { redirect } from 'next/navigation';

/**
 * Team management is its own page now - see `app/(app)/app/organisation/page.tsx`
 * (Team tab) - not a Settings pane.
 */
export default function TeamSettingsRedirectPage() {
  redirect('/app/organisation?tab=team');
}
