interface SectionHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  align?: "left" | "center";
}

export function SectionHeader({ eyebrow, title, description, align = "left" }: SectionHeaderProps) {
  const a = align === "center" ? "text-center mx-auto" : "text-left";
  return (
    <div className={`max-w-[680px] ${a}`}>
      {eyebrow && <div className="eyebrow mb-2.5">{eyebrow}</div>}
      <h2 className="text-[28px] md:text-[34px] font-semibold tracking-tight text-ink leading-tight">{title}</h2>
      {description && <p className="text-[14.5px] text-ink-3 mt-3 leading-relaxed">{description}</p>}
    </div>
  );
}
