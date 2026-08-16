import { redirect } from 'next/navigation';

/**
 * Integrations moved out of Settings and into the primary nav.
 *
 * Connecting a carrier and a speech vendor is what a new organisation has to do
 * before anything works at all, so it was the first task buried behind the
 * rarest menu. The old path stays as a redirect rather than a 404: it is in
 * people's history and in `SYSTEM.md`, and neither is worth breaking to save a
 * file.
 */
export default function MovedToTopLevel() {
  redirect('/app/integrations');
}
