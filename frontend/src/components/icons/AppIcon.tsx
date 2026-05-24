"use client";

/**
 * AppIcon — brand icon for data systems (databases, warehouses, lakes, ETL).
 *
 * Uses simple-icons SVG paths when the brand is available. For trademark-
 * restricted brands that simple-icons omits (Oracle, AWS, IBM, Salesforce,
 * SAS, SQL Server, OpenAI, dbt, Iceberg), falls back to a colored letter
 * tile keyed off `FALLBACKS`. Output is always a square tile so it lines up
 * cleanly in tables and list rows.
 */

import * as si from "simple-icons";

interface SimpleIcon {
  title: string;
  hex: string;
  path: string;
}

type Slug =
  // Real simple-icons brands
  | "snowflake" | "postgresql" | "mysql" | "mongodb" | "databricks" | "googlebigquery"
  | "apachehive" | "apachekafka" | "apachespark" | "apachecassandra" | "redis" | "elasticsearch"
  // Trademark-restricted (letter fallback)
  | "oracle" | "sqlserver" | "db2" | "salesforce" | "s3" | "sas" | "dbt"
  | "iceberg" | "datastage";

const SI_MAP: Partial<Record<Slug, SimpleIcon>> = {
  snowflake:        (si as Record<string, SimpleIcon>).siSnowflake,
  postgresql:       (si as Record<string, SimpleIcon>).siPostgresql,
  mysql:            (si as Record<string, SimpleIcon>).siMysql,
  mongodb:          (si as Record<string, SimpleIcon>).siMongodb,
  databricks:       (si as Record<string, SimpleIcon>).siDatabricks,
  googlebigquery:   (si as Record<string, SimpleIcon>).siGooglebigquery,
  apachehive:       (si as Record<string, SimpleIcon>).siApachehive,
  apachekafka:      (si as Record<string, SimpleIcon>).siApachekafka,
  apachespark:      (si as Record<string, SimpleIcon>).siApachespark,
  apachecassandra:  (si as Record<string, SimpleIcon>).siApachecassandra,
  redis:            (si as Record<string, SimpleIcon>).siRedis,
  elasticsearch:    (si as Record<string, SimpleIcon>).siElasticsearch,
};

const FALLBACKS: Record<string, { letter: string; bg: string; fg?: string }> = {
  oracle:     { letter: "O", bg: "#E11D48" },
  sqlserver:  { letter: "M", bg: "#A91D22" },
  db2:        { letter: "D", bg: "#1F70C1" },
  salesforce: { letter: "S", bg: "#00A1E0" },
  s3:         { letter: "S", bg: "#FF9900" },
  sas:        { letter: "S", bg: "#0070C0" },
  dbt:        { letter: "d", bg: "#F47F45" },
  iceberg:    { letter: "I", bg: "#2E7AB6" },
  datastage:  { letter: "D", bg: "#054ADA" },
  bigquery:   { letter: "B", bg: "#4285F4" },
  hive:       { letter: "H", bg: "#FDEE21", fg: "#000" },
  mongo:      { letter: "M", bg: "#13AA52" },
  unknown:    { letter: "?", bg: "#888" },
};

// Accept common aliases used across the app/backend (lowercase keys).
const ALIASES: Record<string, Slug> = {
  postgres:        "postgresql",
  pg:              "postgresql",
  mongo:           "mongodb",
  bigquery:        "googlebigquery",
  hive:            "apachehive",
  kafka:           "apachekafka",
  spark:           "apachespark",
  cassandra:       "apachecassandra",
  "sql-server":    "sqlserver",
  mssql:           "sqlserver",
  "ms-sql":        "sqlserver",
  "ibm-db2":       "db2",
};

function resolve(name: string): Slug | string {
  const k = name.trim().toLowerCase();
  return (ALIASES[k] as Slug | undefined) ?? (k as Slug);
}

interface AppIconProps {
  /** System name — e.g. "snowflake", "postgres", "oracle", "salesforce". Case-insensitive. */
  name: string;
  size?: number;
  /** Override the rounded tile chrome — useful for inline use. */
  bare?: boolean;
  className?: string;
}

export function AppIcon({ name, size = 18, bare, className }: AppIconProps) {
  const slug = resolve(name);
  const brand = SI_MAP[slug as Slug];

  if (brand) {
    const tileBg = `#${brand.hex}`;
    if (bare) {
      return (
        <svg
          viewBox="0 0 24 24"
          width={size}
          height={size}
          fill={tileBg}
          className={className}
          aria-label={brand.title}
          role="img"
        >
          <path d={brand.path} />
        </svg>
      );
    }
    return (
      <div
        className={
          "grid place-items-center rounded-[4px] flex-shrink-0 " + (className ?? "")
        }
        style={{ width: size, height: size, background: tileBg }}
        aria-label={brand.title}
      >
        <svg viewBox="0 0 24 24" width={size * 0.65} height={size * 0.65} fill="#FFFFFF" role="img">
          <path d={brand.path} />
        </svg>
      </div>
    );
  }

  const f = FALLBACKS[slug] ?? FALLBACKS.unknown;
  return (
    <div
      className={
        "grid place-items-center rounded-[4px] font-mono font-bold flex-shrink-0 " + (className ?? "")
      }
      style={{
        width: size,
        height: size,
        background: f.bg,
        color: f.fg ?? "#FFFFFF",
        fontSize: size * 0.55,
        letterSpacing: "-0.03em",
      }}
      aria-label={name}
    >
      {f.letter}
    </div>
  );
}
