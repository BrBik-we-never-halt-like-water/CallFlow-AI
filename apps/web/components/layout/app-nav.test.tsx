import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import {
  AppTabBar,
  isActive,
  NAV_ITEMS,
  PLATFORM_NAV_ITEM,
  PRIMARY_NAV_ITEMS,
} from './app-nav';

vi.mock('next/navigation', () => ({
  usePathname: () => '/app/runs',
}));

vi.mock('./user-menu', () => ({
  UserMenu: () => <div data-testid="user-menu" />,
}));

describe('isActive', () => {
  it('matches the dashboard only on the exact root path', () => {
    expect(isActive('/app', '/app')).toBe(true);
    expect(isActive('/app/runs', '/app')).toBe(false);
  });

  it('matches a section and its sub-paths', () => {
    expect(isActive('/app/runs', '/app/runs')).toBe(true);
    expect(isActive('/app/runs/new', '/app/runs')).toBe(true);
    expect(isActive('/app/runsomethingelse', '/app/runs')).toBe(false);
  });
});

describe('nav item composition', () => {
  it('keeps Organisation and Settings out of the primary nav list', () => {
    const hrefs = PRIMARY_NAV_ITEMS.map((i) => i.href);
    expect(hrefs).not.toContain('/app/organisation');
    expect(hrefs).not.toContain('/app/settings');
  });

  it('never includes the platform-only entry in the regular nav list', () => {
    expect(NAV_ITEMS.some((i) => i.href === PLATFORM_NAV_ITEM.href)).toBe(false);
  });
});

describe('AppTabBar', () => {
  it('renders only the four mobile destinations plus the account menu', () => {
    render(<AppTabBar escalationCount={0} profile={null} loading={false} />);

    expect(screen.getByRole('link', { name: /Dashboard/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Runs/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Needs you/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Agents/ })).toBeInTheDocument();
    // Contacts is in the primary list but not the mobile tab bar.
    expect(screen.queryByRole('link', { name: /^Contacts/ })).not.toBeInTheDocument();
    expect(screen.getByTestId('user-menu')).toBeInTheDocument();
  });

  it('marks the current section as the active tab', () => {
    render(<AppTabBar escalationCount={0} profile={null} loading={false} />);
    expect(screen.getByRole('link', { name: /Runs/ })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('surfaces the escalation count to assistive tech without a numeric pill', () => {
    render(<AppTabBar escalationCount={3} profile={null} loading={false} />);
    expect(screen.getByText('3 waiting for a person')).toBeInTheDocument();
  });
});
