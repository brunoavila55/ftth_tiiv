import type { components } from "./api-types";

export interface ValidationErrorItem {
  field?: string;
  code?: string;
  message: string;
}

export interface ProblemDetails {
  type?: string;
  title?: string;
  status: number;
  detail?: string;
  code?: string;
  errors?: ValidationErrorItem[];
  request_id?: string;
  [key: string]: unknown;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly code?: string;
  public readonly title?: string;
  public readonly detail?: string;
  public readonly errors?: ValidationErrorItem[];
  public readonly requestId?: string;
  public readonly problem?: ProblemDetails;

  constructor(
    statusOrProblem: number | Partial<ProblemDetails>,
    problemOrStatus?: Partial<ProblemDetails> | number,
    message?: string
  ) {
    let status: number;
    let problem: Partial<ProblemDetails> | undefined;

    if (typeof statusOrProblem === "number") {
      status = statusOrProblem;
      problem = typeof problemOrStatus === "object" ? problemOrStatus : undefined;
    } else {
      problem = statusOrProblem;
      status = typeof problemOrStatus === "number" ? problemOrStatus : (problem?.status ?? 500);
    }

    super(message || problem?.detail || problem?.title || `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.code = problem?.code;
    this.title = problem?.title;
    this.detail = problem?.detail;
    this.errors = problem?.errors;
    this.requestId = (problem?.request_id as string) || (problem?.requestId as string);
    this.problem = problem as ProblemDetails;
  }
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages?: number;
}

export type PaginatedResult<T> = PaginatedResponse<T>;

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  user: MeResponse;
  expires_at?: string;
}

export interface MeResponse {
  id: string;
  email: string;
  name: string;
  role: string;
  permissions: string[];
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export type SiteRead = components["schemas"]["SiteRead"];
export type StructureRead = components["schemas"]["StructureRead"];
export type CableRead = components["schemas"]["CableRead"];
export type CableSegmentRead = components["schemas"]["CableSegmentRead"];
export type DeviceRead = components["schemas"]["DeviceRead"];
export type PortRead = components["schemas"]["PortRead"];
