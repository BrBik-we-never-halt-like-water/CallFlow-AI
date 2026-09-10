import { useEffect } from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { TooltipProvider } from '@/components/ui/tooltip';
import NewRunPage from './page';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/api', () => ({
  api: {
    listVoiceAgents: vi.fn().mockResolvedValue([]),
    listNumbers: vi.fn().mockResolvedValue([]),
    startRun: vi.fn(),
  },
}));

vi.mock('@/components/ui/toast', () => ({
  useToast: () => vi.fn(),
}));

vi.mock('@/lib/app-store', () => ({
  useAppStore: () => ({
    health: { calling_available: true },
    phase: 'up',
    refresh: vi.fn(),
  }),
}));

vi.mock('@/lib/hooks/use-session', () => ({
  useSession: () => ({
    status: 'signed-in',
    profile: { permissions: ['runs:start'] },
    refresh: vi.fn(),
  }),
}));

vi.mock('@/lib/hooks/use-org-scoped-effect', () => ({
  // Pass-through stand-in for the real hook: deps are caller-supplied, same as
  // the real useOrgScopedEffect (lib/hooks/use-org-scoped-effect.ts).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useOrgScopedEffect: (effect: () => void, deps: unknown[]) => useEffect(effect, deps),
}));

describe('the run composer', () => {
  it('rejects an empty form: Start run stays disabled with no agent, numbers, or contacts', async () => {
    render(
      <TooltipProvider>
        <NewRunPage />
      </TooltipProvider>,
    );

    const startButton = await screen.findByRole('button', { name: 'Start run' });
    expect(startButton).toBeDisabled();
  });
});
