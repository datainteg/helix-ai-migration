import { Search } from "lucide-react";

interface DocsSearchProps {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
}

export function DocsSearch({ value, onChange, placeholder = "Search docs..." }: DocsSearchProps) {
  return (
    <label className="relative block">
      <span className="sr-only">Search documentation</span>
      <Search
        className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-4 pointer-events-none"
        aria-hidden="true"
      />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-8 pr-3 py-1.5 text-[12.5px] rounded-md border border-zinc-200 bg-surface placeholder:text-ink-4 text-ink-2 focus-ring"
      />
    </label>
  );
}
