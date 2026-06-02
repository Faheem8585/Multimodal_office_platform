// Shared types mirroring the backend's Pydantic schemas.

export type Department =
  | "hr"
  | "finance"
  | "it"
  | "operations"
  | "marketing"
  | "legal"
  | "procurement";

export type RoleName = "admin" | "dept_manager" | "dept_member" | "viewer";

export interface User {
  id: string;
  email: string;
  full_name: string;
  department: Department;
  is_active: boolean;
  roles: RoleName[];
  last_login_at: string | null;
}

export interface TokenPair {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface StatCard {
  key: string;
  label: string;
  value: number;
  unit?: string | null;
  link?: string | null;
}

export interface ActivityEvent {
  id: string;
  verb: string;
  summary: string;
  department: Department | null;
  resource_type: string | null;
  created_at: string;
}

export interface Dashboard {
  department: Department;
  role_tier: string;
  stats: StatCard[];
  recent_activity: ActivityEvent[];
}

export interface DocumentItem {
  id: string;
  title: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  department: Department;
  status: "uploaded" | "processing" | "indexed" | "failed";
  error?: string | null;
  created_at: string;
}

export interface SearchHit {
  chunk_id: string;
  document_id: string;
  content: string;
  score: number;
}

export interface ChatSource {
  document_id: string;
  content: string;
  score: number;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
}

export interface ApprovalStep {
  order_index: number;
  name: string;
  required_role: RoleName;
  required_department: Department | null;
  decision: "pending" | "approved" | "rejected";
  decided_by: string | null;
  comment: string | null;
}

export interface ApprovalRequest {
  id: string;
  resource_type: string;
  resource_id: string;
  department: Department;
  status: "pending" | "approved" | "rejected" | "cancelled";
  current_step: number;
  requested_by: string | null;
  context: Record<string, unknown>;
  steps: ApprovalStep[];
  created_at: string;
}

export interface Notification {
  id: string;
  title: string;
  body: string;
  category: string;
  link: string | null;
  read: boolean;
  created_at: string;
}
