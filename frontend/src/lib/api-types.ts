/**
 * Helix API types — auto-generated from backend OpenAPI schema.
 * Regenerate with: npm run generate:types
 * Source: http://localhost:8000/openapi.json
 */

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface UserCreate {
  email: string;
  name: string;
  password: string;
}

export interface UserResponse {
  id: string;
  email: string;
  name: string;
  status: string;
  is_super_admin: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface UserLogin {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface OrganizationCreate {
  name: string;
  slug: string;
}

export interface OrganizationResponse {
  id: string;
  name: string;
  slug: string;
  status: string;
  created_at: string;
}

export interface FirstAdminSetup {
  email: string;
  name: string;
  password: string;
  organization_name: string;
  organization_slug: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirm {
  token: string;
  new_password: string;
}

// ── Projects ──────────────────────────────────────────────────────────────────

export interface ProjectCreate {
  name: string;
  description?: string | null;
  risk_level?: string;
  migration_type?: string | null;
}

export interface ProjectResponse {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  status: string;
  risk_level: string;
  migration_type: string | null;
  owner_id: string;
}

export interface SubProjectCreate {
  name: string;
  migration_domain?: string | null;
}

export interface SubProjectResponse {
  id: string;
  project_id: string;
  name: string;
  migration_domain: string | null;
  status: string;
}

export interface RequirementCreate {
  source_text: string;
}

export interface RequirementResponse {
  id: string;
  project_id: string;
  source_text: string;
  status: string;
  version: string;
}

export interface SchemaCreate {
  name: string;
  schema_type?: string;
}

export interface SchemaResponse {
  id: string;
  project_id: string;
  name: string;
  schema_type: string;
}

export interface TableCreate {
  name: string;
  row_count?: number | null;
}

export interface TableResponse {
  id: string;
  schema_id: string;
  name: string;
  row_count: number | null;
}

export interface ColumnCreate {
  name: string;
  data_type: string;
  nullable?: boolean;
  ordinal_position?: number | null;
}

export interface ColumnResponse {
  id: string;
  table_id: string;
  name: string;
  data_type: string;
  nullable: boolean;
  ordinal_position: number | null;
}

// ── LLM Providers ─────────────────────────────────────────────────────────────

export interface LLMProviderCreate {
  provider_type: string;
  name: string;
  api_key: string;
  base_url?: string | null;
  default_model?: string;
  temperature?: number;
  max_tokens?: number;
  timeout?: number;
}

export interface LLMProviderUpdate {
  name?: string | null;
  base_url?: string | null;
  default_model?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  timeout?: number | null;
  status?: string | null;
}

export interface LLMProviderResponse {
  id: string;
  organization_id: string;
  provider_type: string;
  name: string;
  base_url: string | null;
  default_model: string;
  temperature: number;
  max_tokens: number;
  timeout: number;
  status: string;
  api_key_masked: string | null;
}

export interface AgentMappingCreate {
  agent_type: string;
  provider_id: string;
  model: string;
  temperature?: number;
  max_tokens?: number;
}

export interface AgentMappingResponse {
  id: string;
  organization_id: string;
  agent_type: string;
  provider_id: string;
  model: string;
  temperature: number;
  max_tokens: number;
}

export interface KeyRotateRequest {
  new_api_key: string;
}

export interface TestConnectionResponse {
  success: boolean;
  message: string;
}

export interface CatalogueEntry {
  provider_type: string;
  models: string[];
  default_base_url: string;
}

// ── Agents ────────────────────────────────────────────────────────────────────

export interface AgentTaskCreate {
  agent_type: string;
  input_payload?: string | null;
}

export interface AgentTaskResponse {
  id: string;
  project_id: string;
  agent_type: string;
  status: string;
  llm_model: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface AgentOutputResponse {
  id: string;
  task_id: string;
  schema_name: string;
  schema_version: string;
  output_payload: string;
  confidence_score: number | null;
}

export interface PromptTemplateCreate {
  name: string;
  agent_type: string;
  template: string;
}

export interface PromptTemplateResponse {
  id: string;
  name: string;
  agent_type: string;
  template: string;
  status: string;
}

// ── Artifacts ─────────────────────────────────────────────────────────────────

export interface ArtifactResponse {
  id: string;
  organization_id: string;
  project_id: string;
  filename: string;
  file_type: string;
  storage_path: string;
  content_hash: string;
  status: string;
}

export interface ArtifactVersionResponse {
  id: string;
  artifact_id: string;
  version_number: string;
  content_hash: string;
  storage_path: string;
  generated_by_agent: string | null;
  llm_model: string | null;
  change_summary: string | null;
  approval_status: string;
  approved_by: string | null;
}

export interface ArtifactApprovalCreate {
  decision: string;
  notes?: string | null;
}

// ── Validation ────────────────────────────────────────────────────────────────

export interface ValidationRuleCreate {
  rule_type: string;
  target_table?: string | null;
  target_column?: string | null;
  parameters?: Record<string, unknown> | null;
}

export interface ValidationRuleResponse {
  id: string;
  project_id: string;
  rule_type: string;
  target_table: string | null;
  target_column: string | null;
  parameters: Record<string, unknown> | null;
  status: string;
}

export interface ValidationRunCreate {
  connector_configs?: Record<string, unknown>;
}

export interface ValidationRunResponse {
  id: string;
  project_id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  pass_count: number;
  fail_count: number;
  error_message: string | null;
}

export interface ValidationResultResponse {
  id: string;
  run_id: string;
  rule_id: string;
  status: string;
  actual_value: string | null;
  expected_value: string | null;
  row_count: number | null;
}

// ── Audit ─────────────────────────────────────────────────────────────────────

export interface AuditLogResponse {
  id: string;
  organization_id: string;
  user_id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string | null;
  created_at: string;
  entry_hash: string | null;
}

// ── System ────────────────────────────────────────────────────────────────────

export interface HealthComponent {
  status: "healthy" | "degraded" | "down" | "unavailable";
  latency_ms?: number;
  error?: string;
}

export interface HealthResponse {
  status: "ok" | "degraded" | "down";
  components: Record<string, HealthComponent>;
  version: string;
}

// ── Connectors ────────────────────────────────────────────────────────────────

export interface ConnectorConfig {
  connector_type: string;
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  password?: string;
  ssl_mode?: string;
  [key: string]: unknown;
}

export interface TestConnectionRequest {
  project_id: string;
  connector_type: string;
  config: ConnectorConfig;
}

// ── API error shape ───────────────────────────────────────────────────────────

export interface ApiError {
  detail: string | { msg: string; type: string }[];
}
