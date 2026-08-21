'use client';

import { Panel, PanelBody, PanelEmpty, PanelHeader, PillSelect } from './panel';
import { StatusPill } from './status-pill';
import type { RunSummary, VoiceAgent } from '@/lib/api';
import type { Scope, ScopeOption } from './scope';

/**
 * The runs and agents panels.
 *
 * Both are fixed-height and scroll internally, and both carry a scope
 * toggle whose available options depend on the signed-in role - the caller
 * passes only the options that role may choose, so a role that cannot see
 * the team never renders the control at all.
 *
 * Scope filtering here is presentation over rows the API already returned:
 * RLS decides what a request can see, this decides what the panel shows of
 * it. A scope option that would widen the result set past the caller's
 * permission is never offered, because the data behind it was never sent.
 */

function ScopeControl({
  scope,
  onScopeChange,
  options,
  label,
}: {
  scope: Scope;
  onScopeChange: (scope: Scope) => void;
  options: ScopeOption[];
  label: string;
}) {
  if (options.length < 2) return null;
  return (
    <PillSelect
      label={label}
      value={scope}
      onChange={onScopeChange}
      options={options}
    />
  );
}

export function RunsPanel({
  runs,
  loading,
  scope,
  onScopeChange,
  scopeOptions,
  className,
}: {
  runs: RunSummary[] | null;
  loading: boolean;
  scope: Scope;
  onScopeChange: (scope: Scope) => void;
  scopeOptions: ScopeOption[];
  className?: string;
}) {
  const rows = runs ?? [];

  return (
    <Panel className={className}>
      <PanelHeader title="Runs">
        <ScopeControl
          label="Whose runs to show"
          scope={scope}
          onScopeChange={onScopeChange}
          options={scopeOptions}
        />
      </PanelHeader>

      <PanelBody label="Runs" className="px-4 pb-3">
        {loading ? null : rows.length === 0 ? (
          <PanelEmpty
            message="No runs yet."
            hint="Start one from Runs to see it here."
          />
        ) : (
          <ul className="flex flex-col">
            {rows.map((run) => (
              <li
                key={run.id}
                className="flex items-center justify-between gap-3 border-b py-2 last:border-b-0"
                style={{ borderColor: 'var(--dash-border)' }}
              >
                <div className="min-w-0 flex-1">
                  <p
                    className="truncate text-[0.75rem] font-medium"
                    style={{ color: 'var(--dash-text)' }}
                  >
                    {run.name ?? run.agent_name ?? 'Untitled run'}
                  </p>
                  <p
                    className="dash-num truncate text-[0.6875rem]"
                    style={{ color: 'var(--dash-text-mute)' }}
                  >
                    {run.completed.toLocaleString()} of{' '}
                    {run.total.toLocaleString()} calls
                  </p>
                </div>
                <StatusPill status={run.status} />
              </li>
            ))}
          </ul>
        )}
      </PanelBody>
    </Panel>
  );
}

export function AgentsPanel({
  agents,
  loading,
  scope,
  onScopeChange,
  scopeOptions,
  className,
}: {
  agents: VoiceAgent[] | null;
  loading: boolean;
  scope: Scope;
  onScopeChange: (scope: Scope) => void;
  scopeOptions: ScopeOption[];
  className?: string;
}) {
  const rows = agents ?? [];

  return (
    <Panel className={className}>
      <PanelHeader title="Agents">
        <ScopeControl
          label="Whose agents to show"
          scope={scope}
          onScopeChange={onScopeChange}
          options={scopeOptions}
        />
      </PanelHeader>

      <PanelBody label="Agents" className="px-4 pb-3">
        {loading ? null : rows.length === 0 ? (
          <PanelEmpty
            message="No agents yet."
            hint="Build one from Agents to see it here."
          />
        ) : (
          <ul className="flex flex-col">
            {rows.map((agent) => (
              <li
                key={agent.id}
                className="flex items-center justify-between gap-3 border-b py-2 last:border-b-0"
                style={{ borderColor: 'var(--dash-border)' }}
              >
                <div className="min-w-0 flex-1">
                  <p
                    className="truncate text-[0.75rem] font-medium"
                    style={{ color: 'var(--dash-text)' }}
                  >
                    {agent.name}
                  </p>
                  <p
                    className="truncate text-[0.6875rem]"
                    style={{ color: 'var(--dash-text-mute)' }}
                  >
                    {agent.created_by_name ?? 'Unknown author'}
                  </p>
                </div>
                <StatusPill
                  status={agent.kind === 'prebuilt' ? 'active' : 'neutral'}
                  label={agent.kind === 'prebuilt' ? 'Prebuilt' : 'Custom'}
                />
              </li>
            ))}
          </ul>
        )}
      </PanelBody>
    </Panel>
  );
}
