'use client';

import { useEffect } from 'react';

/**
 * Opens the disclosure inside whichever section the URL points at.
 *
 * The table of contents exists because this page is read by someone hunting one
 * answer - a retention window, a sub-processor category - far more often than it
 * is read top to bottom. Landing them on a heading with the detail still folded
 * away would make the collapse cost the exact reader it was meant to serve.
 *
 * A `<details>` cannot be opened by `:target`, so this is the one thing the
 * pattern genuinely needs script for.
 */
export function OpenOnHash() {
  useEffect(() => {
    const open = () => {
      const id = window.location.hash.slice(1);
      if (!id) return;
      const target = document.getElementById(id);
      target?.querySelector('details')?.setAttribute('open', '');
      // Re-anchor after the panel has laid out, or the browser's own scroll -
      // which ran against the collapsed height - leaves the heading off-screen.
      target?.scrollIntoView({ block: 'start' });
    };
    open();
    window.addEventListener('hashchange', open);
    return () => window.removeEventListener('hashchange', open);
  }, []);

  return null;
}
