import { redirect } from 'next/navigation';

/** Billing moved to its own top-level route. The old URL keeps working -
 *  same treatment as settings/integrations, which moved the same way. */
export default function BillingMovedPage() {
  redirect('/app/billing');
}
