import React from "react";
import { cn } from "@/lib/utils";

interface CommonProps {
  children?: React.ReactNode;
  className?: string;
}

/** Plain semantic table primitives that adopt the console look. */
export function Table({ children, className, minWidth }: CommonProps & { minWidth?: number }) {
  return (
    <div className="w-full overflow-x-auto">
      <table
        className={cn("w-full border-collapse text-[12.5px]", className)}
        style={minWidth ? { minWidth } : undefined}
      >
        {children}
      </table>
    </div>
  );
}

export function THead({ children, className }: CommonProps) {
  return <thead className={cn("bg-surface-hi", className)}>{children}</thead>;
}

export function TBody({ children, className }: CommonProps) {
  return <tbody className={className}>{children}</tbody>;
}

export function TR({
  children,
  className,
  onClick,
  hover = false,
}: CommonProps & { onClick?: () => void; hover?: boolean }) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        "border-b border-hx last:border-b-0",
        hover && "hover:bg-surface-hi",
        onClick && "cursor-pointer",
        className
      )}
    >
      {children}
    </tr>
  );
}

export function TH({
  children,
  className,
  align = "left",
  width,
}: CommonProps & { align?: "left" | "right" | "center"; width?: number | string }) {
  return (
    <th
      className={cn(
        "px-3.5 py-2.5 font-medium text-ink-4 text-[10.5px] uppercase tracking-[0.08em] font-mono border-b border-hx",
        align === "right" && "text-right",
        align === "center" && "text-center",
        align === "left" && "text-left",
        className
      )}
      style={width ? { width } : undefined}
    >
      {children}
    </th>
  );
}

export function TD({
  children,
  className,
  align = "left",
  mono = false,
}: CommonProps & { align?: "left" | "right" | "center"; mono?: boolean }) {
  return (
    <td
      className={cn(
        "px-3.5 py-3 align-middle",
        align === "right" && "text-right",
        align === "center" && "text-center",
        mono && "font-mono",
        className
      )}
    >
      {children}
    </td>
  );
}
