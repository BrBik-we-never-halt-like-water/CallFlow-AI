'use client';

import {
  DotsThreeVerticalIcon,
  PencilSimpleIcon,
  PushPinIcon,
  TrashIcon,
} from '@phosphor-icons/react/dist/ssr';
import { cn } from '@/lib/cn';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

/**
 * One conversation in the list: draggable to reorder, with pin/rename/delete
 * behind a three-dot menu.
 *
 * **The menu, not a swipe.** A swipe is invisible until you try it, does not
 * exist for a mouse, and cannot be reached by keyboard at all - so the three
 * actions had to be duplicated as buttons anyway. One menu is the whole
 * affordance instead, and it names what it does.
 *
 * **Reordering** is native HTML drag-and-drop. The row under the pointer
 * shifts out of the way as you drag (`insertBefore`/`insertAfter`), so the
 * list shows where the row will land rather than only what is being carried.
 */

export type DropSide = 'before' | 'after';

export function ConversationRow({
  children,
  pinned,
  canPin,
  canManage,
  onOpen,
  onTogglePin,
  onRename,
  onRequestDelete,
  onDragStart,
  onDragEnter,
  onDragEnd,
  dragging,
  dropSide,
}: {
  children: React.ReactNode;
  pinned: boolean;
  /** False once three are pinned, so the item explains itself rather than
   *  failing on click. */
  canPin: boolean;
  /** Rename and delete are the channel creator's or an admin's. */
  canManage: boolean;
  onOpen: () => void;
  onTogglePin: () => void;
  onRename: () => void;
  onRequestDelete: () => void;
  onDragStart: () => void;
  onDragEnter: (side: DropSide) => void;
  onDragEnd: () => void;
  dragging: boolean;
  /** Which edge the carried row would land on, or null when this is not the
   *  current target. Drawn as a coral rule so the gap is visible. */
  dropSide: DropSide | null;
}) {
  return (
    <li
      draggable
      onDragStart={(event) => {
        // A payload is required or Firefox cancels the drag outright.
        event.dataTransfer.setData('text/plain', '');
        event.dataTransfer.effectAllowed = 'move';
        onDragStart();
      }}
      onDragOver={(event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
        // Which half of the row the pointer is over decides which side the
        // carried row lands on, so a drag reads as an insertion point rather
        // than a swap.
        const box = event.currentTarget.getBoundingClientRect();
        onDragEnter(
          event.clientY < box.top + box.height / 2 ? 'before' : 'after',
        );
      }}
      onDrop={(event) => {
        event.preventDefault();
        onDragEnd();
      }}
      onDragEnd={onDragEnd}
      className={cn(
        'group/row relative list-none rounded-xl transition-[opacity,transform] duration-(--dur-micro)',
        dragging && 'scale-[0.98] opacity-40',
      )}
    >
      {/* The insertion line. Sits in the gap between rows, so the list shows
          where the row will land. */}
      {dropSide ? (
        <span
          aria-hidden
          className="absolute inset-x-1 z-10 h-0.5 rounded-full"
          style={{
            background: 'var(--dash-brand)',
            [dropSide === 'before' ? 'top' : 'bottom']: '-5px',
          }}
        />
      ) : null}

      <div className="relative">
        <button
          type="button"
          onClick={onOpen}
          className="relative z-0 w-full text-left"
        >
          {children}
        </button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label="Conversation options"
              // Always visible, not hover-revealed: a control that only
              // appears under a cursor is invisible on touch and unfindable
              // for anyone who does not already know it is there. It sits at
              // the muted tier and lifts on hover instead.
              className="absolute right-1.5 top-1.5 z-20 flex size-6 items-center justify-center rounded-[6px] transition-colors hover:bg-[var(--dash-hover)] data-[state=open]:bg-[var(--dash-hover)]"
              style={{ color: 'var(--dash-text-mute)' }}
            >
              <DotsThreeVerticalIcon aria-hidden className="size-4" />
            </button>
          </DropdownMenuTrigger>

          <DropdownMenuContent
            align="end"
            className="dash-menu"
            style={{ width: 132, minWidth: 0 }}
          >
            <DropdownMenuItem
              onSelect={onTogglePin}
              disabled={!pinned && !canPin}
            >
              <PushPinIcon
                aria-hidden
                className="size-3.5 shrink-0"
                weight={pinned ? 'fill' : 'regular'}
              />
              {pinned ? 'Unpin' : 'Pin'}
            </DropdownMenuItem>

            {canManage ? (
              <DropdownMenuItem onSelect={onRename}>
                <PencilSimpleIcon aria-hidden className="size-3.5 shrink-0" />
                Rename
              </DropdownMenuItem>
            ) : null}

            {canManage ? (
              <DropdownMenuItem destructive onSelect={onRequestDelete}>
                <TrashIcon aria-hidden className="size-3.5 shrink-0" />
                Delete
              </DropdownMenuItem>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </li>
  );
}
