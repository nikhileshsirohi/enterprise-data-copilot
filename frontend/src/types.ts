export type ChatSession = {
  session_id: string;
  user_id: number;
  username: string;
  title: string;
  is_active: boolean;
  message_count: number;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: number;
  role: "USER" | "ASSISTANT" | "SYSTEM" | "TOOL" | string;
  content: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type ChatSessionDetail = {
  session_id: string;
  user_id: number;
  username: string;
  title: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
};

export type AskResponse = {
  question: string;
  answer: string;
  answer_source: "database" | "policy" | string;
  sql: string | null;
  is_sql_valid: boolean;
  validation_reason: string | null;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  truncated: boolean;
  metadata: Record<string, unknown>[];
  execution_error: string | null;
  retry_count: number;
  persisted: boolean;
  session_id: string | null;
  user_message_id: number | null;
  assistant_message_id: number | null;
  cache_hit: boolean;
  cache_similarity: number | null;
  workflow_run_id: string | null;
  policy_sources: Record<string, unknown>[];
  citations: Record<string, unknown>[];
};

export type AuthUser = {
  _id: number;
  username: string;
  email: string;
  is_staff: boolean;
  is_superuser: boolean;
};

export type AuthSession = {
  access: string;
  refresh: string;
  session_id: string;
  token_type: string;
};
