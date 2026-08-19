import { redirect } from 'next/navigation';

/**
 * Billing moved out of Settings and onto the sidebar.
 *
 * This redirect stays because the old path is not only in bookmarks: it was the
 * `return_url` on every checkout session already minted at the payment provider,
 * and those are fixed once created. Someone completing one of those pre-existing
 * checkouts must still land somewhere real rather than on a 404 immediately after
 * paying.
 */
export default function BillingMoved() {
  redirect('/app/billing');
}
