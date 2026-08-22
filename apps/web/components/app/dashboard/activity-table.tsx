'use client';

import { Panel, PanelBody, PanelEmpty, PillSelect } from './panel';
import { StatusPill } from './status-pill';

export type ActivityTab = 'all' | 'runs' | 'needs_person' | 'completed';

/** One row of the activity table, whatever produced it. */
export interface ActivityRow {
  id: string;
  /** Which tab family this belongs to - drives filtering and the All column. */
  category: Exclude<ActivityTab, 'all'>;
  /** Who was called. `Outcome` has no timestamp, so this column replaced a
   *  `When` that could only ever render an em dash. */
  caller: string | null;
  /** Already masked by the API (`phone_masked`) - never a full number. */
  contact: string | null;
  agent: string | null;
  run: string | null;
  status: string;
}

const TABS: { value: ActivityTab; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'runs', label: 'Runs' },
  { value: 'needs_person', label: 'Needs a person' },
  { value: 'completed', label: 'Completed' },
];

const CATEGORY_LABEL: Record<Exclude<ActivityTab, 'all'>, string> = {
  runs: 'Run',
  needs_person: 'Needs a person',
  completed: 'Completed',
};

/**
 * Everything that happened, in one table, filtered by tab.
 *
 * Tabs carry counts because the count is the reason to switch: "Needs a
 * person 38" is a decision, "Needs a person" alone is a guess. Contact
 * numbers arrive already masked (`Outcome.phone_masked`) and are rendered
 * as received - revealing one is a separate, permissioned action that never
 * happens in a list, so no full number reaches this component at all.
 */
export function ActivityTable({
  rows,
  loading,
  tab,
  onTabChange,
  month,
  onMonthChange,
  monthOptions,
  className,
}: {
  rows: ActivityRow[] | null;
  loading: boolean;
  tab: ActivityTab;
  onTabChange: (tab: ActivityTab) => void;
  month: string;
  onMonthChange: (month: string) => void;
  monthOptions: { value: string; label: string }[];
  className?: string;
}) {
  const all = rows ?? [];
  const visible = tab === 'all' ? all : all.filter((row) => row.category === tab);

  function countFor(value: ActivityTab): number {
    return value === 'all'
      ? all.length
      : all.filter((row) => row.category === value).length;
  }

  return (
    <Panel className={className}>
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-2 px-4 pb-0 pt-2">
        <h2
          className="text-[0.6875rem] font-semibold uppercase tracking-[0.05em]"
          style={{ color: 'var(--dash-text)' }}
        >
          Activity
        </h2>

        <div className="flex flex-wrap items-center gap-1.5">
          <div
            role="tablist"
            aria-label="Filter activity"
            className="flex items-center gap-1"
          >
            {TABS.map((entry) => {
              const active = entry.value === tab;
              return (
                <button
                  key={entry.value}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => onTabChange(entry.value)}
                  className="cursor-pointer rounded-full px-2 py-0.5 text-[0.625rem] font-medium transition-colors duration-150"
                  style={
                    active
                      ? {
                          background: 'var(--dash-brand-soft)',
                          color: 'var(--dash-brand-ink)',
                        }
                      : { color: 'var(--dash-text-mute)' }
                  }
                >
                  {entry.label}
                  <span className="dash-num ml-1 opacity-70">
                    {countFor(entry.value)}
                  </span>
                </button>
              );
            })}
          </div>

          {monthOptions.length > 0 ? (
            <PillSelect
              label="Month"
              value={month}
              onChange={onMonthChange}
              options={monthOptions}
            />
          ) : null}
        </div>
      </header>

      <PanelBody label="Activity" className="px-0">
        {loading ? null : visible.length === 0 ? (
          <PanelEmpty message="Nothing to show here yet." />
        ) : (
          <table className="w-full border-collapse text-left">
            <thead className="sticky top-0 z-10">
              <tr style={{ background: 'var(--dash-surface)' }}>
                {['Caller', 'Contact', 'Agent', 'Run ID', 'Status'].map((heading) => (
                  <th
                    key={heading}
                    scope="col"
                    className="whitespace-nowrap border-b px-4 pb-1 pt-0.5 text-[0.5625rem] font-semibold uppercase tracking-wider"
                    style={{
                      borderColor: 'var(--dash-border)',
                      color: 'var(--dash-figure)',
                    }}
                  >
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <tr
                  key={row.id}
                  className="border-b last:border-b-0"
                  style={{ borderColor: 'var(--dash-border)' }}
                >
                  <td
                    className="max-w-[10rem] truncate px-4 py-1 text-[0.625rem]"
                    style={{ color: 'var(--dash-text)' }}
                  >
                    {row.caller ?? '—'}
                  </td>
                  <td
                    className="dash-num whitespace-nowrap px-4 py-1 text-[0.625rem]"
                    style={{ color: 'var(--dash-text)' }}
                  >
                    {row.contact ?? '—'}
                  </td>
                  <td
                    className="max-w-[10rem] truncate px-4 py-1 text-[0.625rem]"
                    style={{ color: 'var(--dash-text-dim)' }}
                  >
                    {row.agent ?? '—'}
                  </td>
                  <td
                    className="max-w-[10rem] truncate px-4 py-1 text-[0.625rem]"
                    style={{ color: 'var(--dash-text-dim)' }}
                  >
                    {/* On All, the run column also carries which family the
                        row came from - otherwise a mixed list gives no way
                        to tell an escalation from a completed call. */}
                    {tab === 'all'
                      ? (row.run ?? CATEGORY_LABEL[row.category])
                      : (row.run ?? '—')}
                  </td>
                  <td className="px-4 py-1">
                    <StatusPill status={row.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </PanelBody>
    </Panel>
  );
}
