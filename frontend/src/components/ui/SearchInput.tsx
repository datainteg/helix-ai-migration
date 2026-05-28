"use client";

import { Search } from "lucide-react";
import { useId, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface SearchInputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  /** Accessible name. Falls back to the placeholder if omitted; one of the two
   *  MUST be provided so screen readers don't announce an anonymous "edit". */
  ariaLabel?: string;
  /** Override the leading icon (defaults to a magnifier). Pass null to drop it. */
  leadingIcon?: ReactNode;
  /** Wrapper class — control the width/flex from the call site. */
  wrapperClassName?: string;
}

/**
 * Shared search field primitive (UI-026). Consolidates the 4+ bespoke search
 * inputs that previously varied in size/shape/a11y across `/projects`,
 * `/knowledge`, `/connectors`, and `/developer-workspace`.
 *
 * Always carries an accessible name (`aria-label`) and the `focus-ring`
 * utility so keyboard users see focus and AT users hear a real label.
 */
export function SearchInput({
  ariaLabel,
  leadingIcon,
  wrapperClassName,
  className,
  placeholder,
  id,
  ...rest
}: SearchInputProps) {
  const autoId = useId();
  const inputId = id ?? `search-${autoId}`;
  const label = ariaLabel ?? placeholder ?? "Search";

  return (
    <div className={cn("relative", wrapperClassName)}>
      {leadingIcon !== null && (
        <span
          aria-hidden
          className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-4 pointer-events-none [&_svg]:h-3.5 [&_svg]:w-3.5"
        >
          {leadingIcon ?? <Search className="h-3.5 w-3.5" />}
        </span>
      )}
      <input
        id={inputId}
        type="search"
        aria-label={label}
        placeholder={placeholder}
        className={cn(
          "w-full h-8 rounded-[7px] border border-hx bg-surface text-[12.5px] text-ink focus-ring",
          leadingIcon === null ? "px-3" : "pl-8 pr-3",
          className
        )}
        {...rest}
      />
    </div>
  );
}
