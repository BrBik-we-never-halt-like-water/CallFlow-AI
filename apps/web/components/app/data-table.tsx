"use client";

import {
  CaretDownIcon,
  CaretUpDownIcon,
  CaretUpIcon,
  CaretRightIcon,
  DownloadSimpleIcon,
  SlidersHorizontalIcon,
} from "@phosphor-icons/react/dist/ssr";
import { useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

export interface Column<T> {
  id: string;
  header: string;
  cell: (row: T) => React.ReactNode;
  /**
   * Plain-text value. Used for CSV export and as the accessible fallback, so a
   * column whose `cell` renders a lamp still exports something meaningful.
   */
  value?: (row: T) => string | number | null;
  /** Numeric, phone, and timestamp columns are right-aligned and mono. */
  align?: "left" | "right";
  mono?: boolean;
  sortable?: boolean;
  /** Hidden until the operator turns it on in the column control. */
  defaultHidden?: boolean;
  /** Tailwind width class, e.g. `w-40`. */
  width?: string;
}

export interface SortState {
  id: string;
  dir: "asc" | "desc";
}

export interface DataTableProps<T> {
  /** Required. A table with no caption is unusable with a screen reader. */
  caption: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;

  loading?: boolean;
  /** Shown in place of the body when there are no rows. */
  empty?: React.ReactNode;

  selectable?: boolean;
  selectedIds?: Set<string>;
  onSelectionChange?: (ids: Set<string>) => void;
  /** Actions for the sticky selection bar. */
  selectionActions?: React.ReactNode;

  /** Sorting is server-driven; the table only reports intent. */
  sort?: SortState | null;
  onSortChange?: (sort: SortState) => void;

  /** Pagination is server-driven too. Omit `totalRows` to hide the controls. */
  page?: number;
  pageSize?: number;
  totalRows?: number;
  onPageChange?: (page: number) => void;
  onPageSizeChange?: (size: number) => void;

  onRowClick?: (row: T) => void;
  /**
   * Card body for the mobile list. Below 768px the table becomes a stacked list
   * rather than a horizontally-scrolling table — an ops manager checking
   * escalations on a phone should never have to scroll sideways.
   */
  mobileCard?: (row: T) => React.ReactNode;

  /** Enables "Export CSV" in the toolbar. */
  exportFileName?: string;
  /** Extra controls, rendered at the left of the toolbar. */
  toolbar?: React.ReactNode;
  className?: string;
}

const ROWS_PER_PAGE = ["25", "50", "100"];

export function DataTable<T>({
  caption,
  columns,
  rows,
  rowKey,
  loading = false,
  empty,
  selectable = false,
  selectedIds,
  onSelectionChange,
  selectionActions,
  sort,
  onSortChange,
  page = 1,
  pageSize = 25,
  totalRows,
  onPageChange,
  onPageSizeChange,
  onRowClick,
  mobileCard,
  exportFileName,
  toolbar,
  className,
}: DataTableProps<T>) {
  const [hidden, setHidden] = useState<Set<string>>(
    () => new Set(columns.filter((c) => c.defaultHidden).map((c) => c.id)),
  );

  const visible = useMemo(
    () => columns.filter((c) => !hidden.has(c.id)),
    [columns, hidden],
  );

  const selected = selectedIds ?? new Set<string>();
  const allKeys = rows.map(rowKey);
  const selectedOnPage = allKeys.filter((k) => selected.has(k)).length;
  const headerChecked: boolean | "indeterminate" =
    selectedOnPage === 0 ? false : selectedOnPage === allKeys.length ? true : "indeterminate";

  function toggleAll(next: boolean) {
    if (!onSelectionChange) return;
    const updated = new Set(selected);
    for (const key of allKeys) {
      if (next) updated.add(key);
      else updated.delete(key);
    }
    onSelectionChange(updated);
  }

  function toggleRow(key: string, next: boolean) {
    if (!onSelectionChange) return;
    const updated = new Set(selected);
    if (next) updated.add(key);
    else updated.delete(key);
    onSelectionChange(updated);
  }

  function requestSort(column: Column<T>) {
    if (!column.sortable || !onSortChange) return;
    const dir = sort?.id === column.id && sort.dir === "asc" ? "desc" : "asc";
    onSortChange({ id: column.id, dir });
  }

  function exportCsv() {
    const header = visible.map((c) => c.header);
    const body = rows.map((row) =>
      visible.map((c) => {
        const raw = c.value ? c.value(row) : "";
        return raw == null ? "" : String(raw);
      }),
    );
    const csv = [header, ...body]
      .map((line) =>
        line
          .map((cell) => (/[",\n]/.test(cell) ? `"${cell.replace(/"/g, '""')}"` : cell))
          .join(","),
      )
      .join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${exportFileName}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const totalPages = totalRows != null ? Math.max(1, Math.ceil(totalRows / pageSize)) : null;
  const showToolbar = Boolean(toolbar) || columns.length > 1 || Boolean(exportFileName);

  return (
    <div className={cn("flex flex-col", className)}>
      {showToolbar ? (
        <div className="flex flex-wrap items-center justify-between gap-2 pb-3">
          <div className="flex min-w-0 flex-wrap items-center gap-2">{toolbar}</div>

          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="secondary" size="sm">
                  <SlidersHorizontalIcon aria-hidden className="size-4" />
                  Columns
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuLabel>Show columns</DropdownMenuLabel>
                {columns.map((column) => (
                  <DropdownMenuCheckboxItem
                    key={column.id}
                    checked={!hidden.has(column.id)}
                    onCheckedChange={(next) =>
                      setHidden((current) => {
                        const updated = new Set(current);
                        if (next) updated.delete(column.id);
                        else updated.add(column.id);
                        return updated;
                      })
                    }
                  >
                    {column.header}
                  </DropdownMenuCheckboxItem>
                ))}
                {exportFileName ? (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onSelect={exportCsv}>
                      <DownloadSimpleIcon aria-hidden className="size-4" />
                      Export CSV
                    </DropdownMenuItem>
                  </>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      ) : null}

      {/* ---- Desktop table ------------------------------------------------ */}
      <div className="panel-glass hidden overflow-x-auto rounded-md border border-rule/70 md:block">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">{caption}</caption>

          <thead className="sticky top-0 z-10 bg-surface-sunken">
            <tr className="border-b border-rule">
              {selectable ? (
                <th scope="col" className="w-10 px-3 py-2">
                  <Checkbox
                    checked={headerChecked}
                    onCheckedChange={toggleAll}
                    label="Select all rows on this page"
                    id="dt-select-all"
                    className="[&>label]:sr-only"
                  />
                </th>
              ) : null}

              {visible.map((column) => {
                const isSorted = sort?.id === column.id;
                return (
                  <th
                    key={column.id}
                    scope="col"
                    aria-sort={
                      column.sortable
                        ? isSorted
                          ? sort.dir === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                        : undefined
                    }
                    className={cn(
                      "px-3 py-2 text-small font-medium text-text-mute",
                      column.align === "right" && "text-right",
                      column.width,
                    )}
                  >
                    {column.sortable ? (
                      <button
                        type="button"
                        onClick={() => requestSort(column)}
                        className={cn(
                          "inline-flex cursor-pointer items-center gap-1 transition-colors hover:text-text",
                          column.align === "right" && "flex-row-reverse",
                        )}
                      >
                        {column.header}
                        {isSorted ? (
                          sort.dir === "asc" ? (
                            <CaretUpIcon aria-hidden className="size-3" />
                          ) : (
                            <CaretDownIcon aria-hidden className="size-3" />
                          )
                        ) : (
                          <CaretUpDownIcon aria-hidden className="size-3 opacity-50" />
                        )}
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>

          <tbody>
            {loading ? (
              // Six skeleton rows, header still visible: the shape of the answer
              // arrives before the answer does.
              Array.from({ length: 6 }, (_, i) => (
                <tr key={i} className="border-b border-rule last:border-0">
                  {selectable ? (
                    <td className="px-3 py-3">
                      <Skeleton className="size-4" />
                    </td>
                  ) : null}
                  {visible.map((column) => (
                    <td key={column.id} className="px-3 py-3">
                      <Skeleton className="h-3.5 w-full max-w-32" />
                    </td>
                  ))}
                </tr>
              ))
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={visible.length + (selectable ? 1 : 0)}>{empty}</td>
              </tr>
            ) : (
              rows.map((row) => {
                const key = rowKey(row);
                const isSelected = selected.has(key);
                return (
                  <tr
                    key={key}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    className={cn(
                      "h-11 border-b border-rule transition-colors duration-(--dur-micro) last:border-0",
                      // No zebra striping and no transform on hover — rows are
                      // separated by a rule, and the surface is what reacts.
                      "hover:bg-surface-sunken",
                      isSelected && "bg-surface-sunken",
                      onRowClick && "cursor-pointer",
                    )}
                  >
                    {selectable ? (
                      <td
                        className="px-3"
                        // Clicking the checkbox must not also open the row.
                        onClick={(event) => event.stopPropagation()}
                      >
                        <Checkbox
                          checked={isSelected}
                          onCheckedChange={(next) => toggleRow(key, next)}
                          label={`Select row ${key}`}
                          id={`dt-row-${key}`}
                          className="[&>label]:sr-only"
                        />
                      </td>
                    ) : null}

                    {visible.map((column) => (
                      <td
                        key={column.id}
                        className={cn(
                          "px-3 py-2 text-small text-text",
                          column.align === "right" && "text-right",
                          column.mono && "font-mono text-data tabular-nums",
                        )}
                      >
                        {column.cell(row)}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ---- Mobile card list --------------------------------------------- */}
      <div className="flex flex-col gap-2 md:hidden">
        {loading ? (
          Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="panel-glass rounded-md border border-rule/70 p-3">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="mt-2 h-3 w-24" />
            </div>
          ))
        ) : rows.length === 0 ? (
          <div className="panel-glass rounded-md border border-rule/70">{empty}</div>
        ) : (
          rows.map((row) => {
            const key = rowKey(row);
            const content = mobileCard ? (
              mobileCard(row)
            ) : (
              <div className="flex flex-col gap-1">
                {visible.slice(0, 3).map((column) => (
                  <div key={column.id} className="flex items-baseline justify-between gap-3">
                    <span className="text-small font-medium text-text-mute">{column.header}</span>
                    <span className={cn("text-small text-text", column.mono && "font-mono text-data")}>
                      {column.cell(row)}
                    </span>
                  </div>
                ))}
              </div>
            );

            if (!onRowClick) {
              return (
                <div
                  key={key}
                  className="panel-glass rounded-md border border-rule/70 p-3"
                >
                  {content}
                </div>
              );
            }

            return (
              <button
                key={key}
                type="button"
                onClick={() => onRowClick(row)}
                className="panel-glass flex w-full cursor-pointer items-center gap-3 rounded-md border border-rule/70 p-3 text-left transition-colors hover:bg-surface-hover"
              >
                <span className="min-w-0 flex-1">{content}</span>
                <CaretRightIcon aria-hidden className="size-4 shrink-0 text-text-mute" />
              </button>
            );
          })
        )}
      </div>

      {/* ---- Pagination --------------------------------------------------- */}
      {totalRows != null && totalPages != null ? (
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3">
          <div className="flex items-center gap-2">
            <label htmlFor="dt-page-size" className="text-small text-text-dim">
              Rows per page
            </label>
            <Select
              id="dt-page-size"
              value={String(pageSize)}
              onValueChange={(next) => onPageSizeChange?.(Number(next))}
              options={ROWS_PER_PAGE.map((n) => ({ value: n, label: n }))}
              className="h-8 w-20"
              mono
            />
          </div>

          <div className="flex items-center gap-2">
            <p className="font-mono text-data tabular-nums text-text-dim">
              Page {page} of {totalPages}
            </p>
            <Button
              variant="secondary"
              size="sm"
              disabled={page <= 1}
              onClick={() => onPageChange?.(page - 1)}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => onPageChange?.(page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}

      {/* ---- Selection bar ------------------------------------------------ */}
      {selectable && selected.size > 0 ? (
        <div
          role="region"
          aria-label="Selection actions"
          className={cn(
            "fixed inset-x-0 bottom-0 z-40 border-t border-rule-strong bg-surface-raised p-3 shadow-overlay",
            "flex flex-wrap items-center justify-between gap-3",
          )}
        >
          <p className="font-mono text-data tabular-nums text-text">
            {selected.size} selected
          </p>
          <div className="flex flex-wrap items-center gap-2">
            {selectionActions}
            <Button variant="ghost" size="sm" onClick={() => onSelectionChange?.(new Set())}>
              Clear
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
