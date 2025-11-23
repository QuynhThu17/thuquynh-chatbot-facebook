import { getAccessToken, getRefreshToken, saveTokens, clearTokens } from "./auth-storage";
import { tokenRefreshManager } from "./token-refresh";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:1975/api/v1").replace(/\/$/, "");

// Use the singleton instance from token-refresh.ts

function url(path: string) {
  const base = API_BASE || "";
  return `${base}${path}`;
}

async function handle<T>(res: Response): Promise<T> {
  const ct = res.headers.get("content-type") || "";
  const isJson = ct.toLowerCase().includes("application/json");
  const body = await res.text();
  const parsed = isJson && body ? JSON.parse(body) : body ? { message: body } : {};
  if (!res.ok) {
    const msg = (parsed as any)?.detail || (parsed as any)?.message || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return parsed as T;
}

export type LoginPayload = { email?: string; username?: string; password: string };
export type RegisterPayload = {
  name: string;
  email: string;
  password: string;
  verification_code: string;
  method?: "email_password" | "google";
};

export type TokensResponse = {
  access_token: string;
  refresh_token?: string;
  token_type: string;
};

export type LoginResponse = TokensResponse & { user: Record<string, unknown> };
export type RegisterResponse = { success: boolean; message?: string; user: Record<string, unknown>; tokens: TokensResponse };
export type RefreshResponse = { access_token: string; token_type: string };

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  const res = await apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const data = await handle<LoginResponse>(res);
  // Save tokens on successful login
  if (data.access_token) {
    saveTokens({
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      token_type: data.token_type,
      persist: true // Lưu ở localStorage để tránh tự thoát khi reload/tab mới
    });
  }
  return data;
}

export async function register(data: { name: string; email: string; password: string }): Promise<{ success: boolean; message?: string; data?: { access_token: string; refresh_token: string } }> {
  const res = await apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
  
  const result = await handle<{ success: boolean; message?: string; data?: { access_token: string; refresh_token: string } }>(res);
  
  if (result.success && result.data?.access_token && result.data?.refresh_token) {
    saveTokens({
      access_token: result.data.access_token,
      refresh_token: result.data.refresh_token,
      token_type: "Bearer",
      persist: false
    });
  }
  
  return result;
}

export async function sendVerificationEmail(email: string): Promise<{ success: boolean; message?: string }> {
  const res = await apiFetch("/auth/send-verification-email", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
  return handle(res);
}

export async function refreshToken(): Promise<{ success: boolean; message?: string; data?: { access_token: string } }> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error("No refresh token available");
  }
  
  const res = await fetch(url("/auth/refresh"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    credentials: "include",
  });
  
  const result = await handle<{ success: boolean; message?: string; data?: { access_token: string } }>(res);
  
  if (result.success && result.data?.access_token) {
    saveTokens({
      access_token: result.data.access_token,
      token_type: "Bearer",
      refresh_token: refreshToken
    });
  }
  
  return result;
}

export async function logout(): Promise<{ success: boolean; message?: string }> {
  const refreshToken = getRefreshToken();
  const res = await apiFetch("/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  
  // Clear tokens regardless of logout success
  clearTokens();
  
  return handle(res);
}

export async function verifyEmail(email: string, code: string): Promise<{ success: boolean; message?: string }> {
  const res = await fetch(url("/auth/verify-email"), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ email, code }),
  });
  return handle(res);
}

// Avatar API
export type AvatarInfo = { avatar_url?: string; url?: string };

export async function getAvatarInfo(): Promise<{ success: boolean; data?: AvatarInfo; message?: string }> {
  const res = await apiFetch("/avatar/avatar-info", { method: "GET" });
  return handle(res);
}

export async function uploadAvatar(file: File): Promise<{ success: boolean; data?: any; message?: string }> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await apiFetch("/avatar/upload-avatar", { method: "POST", body: fd });
  return handle(res);
}

async function apiFetch(path: string, options: RequestInit = {}) {
  const token = getAccessToken();
  const headers = new Headers(options.headers);
  const isFormData = typeof (options as any).body !== "undefined" && (options as any).body instanceof FormData;
  
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  
  try {
    const response = await fetch(url(path), {
      ...options,
      headers,
      credentials: "include"
    });
    
    // If token is expired, try to refresh it
    if (response.status === 401 && token) {
      try {
        await tokenRefreshManager.refreshAccessToken();
        
        // Retry the request with new token
        const newToken = getAccessToken();
        if (newToken) {
          headers.set("Authorization", `Bearer ${newToken}`);
        }
        
        const retryResponse = await fetch(url(path), {
          ...options,
          headers,
          credentials: "include"
        });
        
        if (!retryResponse.ok) {
          const error = new Error(`API Error: ${retryResponse.status}`);
          (error as any).status = retryResponse.status;
          (error as any).response = retryResponse;
          throw error;
        }
        
        return retryResponse;
      } catch (refreshError) {
        // If refresh fails, redirect to login
        if (typeof window !== 'undefined') {
          window.location.href = '/auth/login';
        }
        throw refreshError;
      }
    }
    
    if (!response.ok) {
      const error = new Error(`API Error: ${response.status}`);
      (error as any).status = response.status;
      (error as any).response = response;
      throw error;
    }
    
    return response;
  } catch (error: any) {
    // Network errors or other issues
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      throw new Error('Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối internet.');
    }
    throw error;
  }
}

export async function getCurrentUser(): Promise<{ success: boolean; data?: any; message?: string }> {
  const res = await apiFetch("/auth/me", { method: "GET" });
  return handle(res);
}

// Limits API
export async function getUserLimits(): Promise<{ success: boolean; data?: any; message?: string }> {
  const res = await apiFetch("/auth/limits", { method: "GET" });
  return handle(res);
}

export async function checkResourceLimit(resource_type: string): Promise<{ success: boolean; data?: any; message?: string }> {
  const res = await apiFetch(`/auth/limits/check/${encodeURIComponent(resource_type)}`, { method: "GET" });
  return handle(res);
}

// Bot Management API Functions
export interface Bot {
  id: string;
  name: string;
  role: string;
  target: string;
  mission: string;
  note?: string;
  status?: string;
  type?: string;
  language_code?: string;
  identity_id?: string;
  procedure_id?: string;
  knowledge?: any;
  connect?: any;
  created_at?: string;
  updated_at?: string;
}

export interface BotsResponse {
  success: boolean;
  data: Bot[];
  total: number;
  message?: string;
}

export async function getBots(params?: {
  status?: string;
  skip?: number;
  limit?: number;
}): Promise<BotsResponse> {
  const queryParams = new URLSearchParams();
  if (params?.status) queryParams.append("status", params.status);
  if (params?.skip !== undefined) queryParams.append("skip", params.skip.toString());
  if (params?.limit !== undefined) queryParams.append("limit", params.limit.toString());
  
  const queryString = queryParams.toString();
  const path = `/bots${queryString ? `?${queryString}` : ""}`;
  
  const res = await apiFetch(path, { method: "GET" });
  return handle(res);
}

// Knowledge & Documents API
export interface KnowledgeDocument {
  id: string | number;
  title?: string;
  file_name?: string;
  segments?: number;
  images?: number;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

export interface KnowledgeListResponse {
  success: boolean;
  data: KnowledgeDocument[];
  total?: number;
  message?: string;
}

export interface KnowledgeResponse {
  success: boolean;
  data: KnowledgeDocument;
  message?: string;
}

export async function getBotKnowledge(bot_id: string | number): Promise<KnowledgeListResponse> {
  const res = await apiFetch(`/bots/${bot_id}/knowledge`, { method: "GET" });
  const raw = await handle<any>(res);
  const rows: any[] = Array.isArray(raw?.data) ? raw.data : [];
  const data: KnowledgeDocument[] = rows.map((d: any) => ({
    id: d?.id ?? d?._id ?? d?.document_id ?? d?.uuid,
    title: d?.title ?? d?.name ?? d?.file_name ?? d?.filename ?? "",
    file_name: d?.file_name ?? d?.filename ?? undefined,
    segments: d?.segments ?? d?.chunks ?? undefined,
    images: d?.images ?? d?.image_count ?? undefined,
    status: d?.status ?? d?.state ?? undefined,
    created_at: d?.created_at,
    updated_at: d?.updated_at,
  }));
  return { success: !!raw?.success, data, total: raw?.total ?? data.length, message: raw?.message };
}

export async function updateBotKnowledge(
  bot_id: string | number,
  document_id: string | number,
  update: Partial<Pick<KnowledgeDocument, "title" | "status">>
): Promise<KnowledgeResponse> {
  const payload: any = { document_id };
  if (update.title !== undefined) payload.title = update.title;
  if (update.status !== undefined) payload.status = update.status;
  const res = await apiFetch(`/bots/${bot_id}/knowledge`, { method: "PUT", body: JSON.stringify(payload) });
  const raw = await handle<any>(res);
  const d = raw?.data ?? {};
  const mapped: KnowledgeDocument = {
    id: d?.id ?? d?._id ?? d?.document_id ?? d?.uuid,
    title: d?.title ?? d?.name ?? d?.file_name ?? d?.filename ?? "",
    file_name: d?.file_name ?? d?.filename ?? undefined,
    segments: d?.segments ?? d?.chunks ?? undefined,
    images: d?.images ?? d?.image_count ?? undefined,
    status: d?.status ?? d?.state ?? undefined,
    created_at: d?.created_at,
    updated_at: d?.updated_at,
  };
  return { success: !!raw?.success, data: mapped, message: raw?.message };
}

export async function addBotKnowledge(
  bot_id: string | number,
  document_id: string | number,
  extra?: Record<string, any>
): Promise<KnowledgeResponse> {
  const payload: any = { document_id, ...(extra || {}) };
  const res = await apiFetch(`/bots/${bot_id}/knowledge/add`, { method: "POST", body: JSON.stringify(payload) });
  const raw = await handle<any>(res);
  const d = raw?.data ?? {};
  const mapped: KnowledgeDocument = {
    id: d?.id ?? d?._id ?? d?.document_id ?? d?.uuid,
    title: d?.title ?? d?.name ?? d?.file_name ?? d?.filename ?? "",
    file_name: d?.file_name ?? d?.filename ?? undefined,
    segments: d?.segments ?? d?.chunks ?? undefined,
    images: d?.images ?? d?.image_count ?? undefined,
    status: d?.status ?? d?.state ?? undefined,
    created_at: d?.created_at,
    updated_at: d?.updated_at,
  };
  return { success: !!raw?.success, data: mapped, message: raw?.message };
}

export async function removeBotKnowledge(bot_id: string | number, document_id: string | number): Promise<{ success: boolean; message?: string }> {
  const res = await apiFetch(`/bots/${bot_id}/knowledge/${document_id}`, { method: "DELETE" });
  return handle(res);
}

// Documents API
export async function getDocuments(): Promise<KnowledgeListResponse> {
  const res = await apiFetch(`/documents`, { method: "GET" });
  const raw = await handle<any>(res);
  const rows: any[] = Array.isArray(raw?.data) ? raw.data : [];
  const data: KnowledgeDocument[] = rows.map((d: any) => ({
    id: d?.id ?? d?._id ?? d?.document_id ?? d?.uuid,
    title: d?.title ?? d?.name ?? d?.file_name ?? d?.filename ?? "",
    file_name: d?.file_name ?? d?.filename ?? undefined,
    segments: d?.segments ?? d?.chunks ?? undefined,
    images: d?.images ?? d?.image_count ?? undefined,
    status: d?.status ?? d?.state ?? undefined,
    created_at: d?.created_at,
    updated_at: d?.updated_at,
  }));
  return { success: !!raw?.success, data, total: raw?.total ?? data.length, message: raw?.message };
}

export async function uploadDocument(payload: { file: File; title?: string; company?: string | number }): Promise<KnowledgeResponse> {
  const fd = new FormData();
  fd.append("file", payload.file);
  if (payload.title !== undefined) fd.append("title", String(payload.title));
  if (payload.company !== undefined) fd.append("company", String(payload.company));
  const res = await apiFetch(`/documents/upload`, { method: "POST", body: fd });
  const raw = await handle<any>(res);
  const d = raw?.data ?? {};
  const mapped: KnowledgeDocument = {
    id: d?.id ?? d?._id ?? d?.document_id ?? d?.uuid,
    title: d?.title ?? d?.name ?? d?.file_name ?? d?.filename ?? "",
    file_name: d?.file_name ?? d?.filename ?? undefined,
    segments: d?.segments ?? d?.chunks ?? undefined,
    images: d?.images ?? d?.image_count ?? undefined,
    status: d?.status ?? d?.state ?? undefined,
    created_at: d?.created_at,
    updated_at: d?.updated_at,
  };
  return { success: !!raw?.success, data: mapped, message: raw?.message };
}

export async function deleteDocument(document_id: string | number): Promise<{ success: boolean; message?: string }> {
  const res = await apiFetch(`/documents/${document_id}`, { method: "DELETE" });
  return handle(res);
}

export async function getDocumentOptions(): Promise<{ success: boolean; data?: any; message?: string }> {
  const res = await apiFetch(`/documents/options`, { method: "GET" });
  return handle(res);
}

// Socials API
export interface SocialAccount {
  id: string | number;
  name: string;
  avatar_url?: string;
  connected_at?: string;
}

export async function connectSocial(social_id: string | number): Promise<{ success: boolean; message?: string; data?: any }> {
  const res = await apiFetch(`/socials/${social_id}/connect`, { method: "POST" });
  return handle(res);
}

export async function getSocialAccounts(social_id: string | number): Promise<{ success: boolean; data: SocialAccount[]; message?: string }> {
  const res = await apiFetch(`/socials/${social_id}/accounts`, { method: "GET" });
  const raw = await handle<any>(res);
  const rows_source: any = raw?.data ?? raw;
  const rows: any[] = Array.isArray(rows_source) ? rows_source : Array.isArray(rows_source?.accounts) ? rows_source.accounts : [];
  const data: SocialAccount[] = rows.map((a: any) => ({
    id: a?._id ?? a?.id ?? a?.account_id ?? a?.uuid,
    name: a?.social_account_name ?? a?.name ?? a?.title ?? a?.page_name ?? "",
    avatar_url: a?.social_account_avatar_url ?? a?.avatar_url ?? a?.picture ?? a?.image ?? undefined,
    connected_at: a?.connected_at ?? a?.created_at ?? a?.updated_at ?? undefined,
  }));
  return { success: !!raw?.success, data, message: raw?.message };
}

// Identity Management API Functions
export interface Identity {
  id: string | number;
  title: string;
  description?: string;
  examples?: number;
  created_at?: string;
  updated_at?: string;
}

export interface IdentitiesResponse {
  success: boolean;
  data: Identity[];
  total?: number;
  message?: string;
}

export interface IdentityResponse {
  success: boolean;
  data: Identity;
  message?: string;
}

export async function getIdentities(params?: {
  q?: string;
  skip?: number;
  limit?: number;
}): Promise<IdentitiesResponse> {
  const queryParams = new URLSearchParams();
  if (params?.q) queryParams.append("q", params.q);
  if (params?.skip !== undefined) queryParams.append("skip", params.skip.toString());
  if (params?.limit !== undefined) queryParams.append("limit", params.limit.toString());

  const queryString = queryParams.toString();
  const path = `/identities${queryString ? `?${queryString}` : ""}`;
  const res = await apiFetch(path, { method: "GET" });
  const raw = await handle<any>(res);
  const data: Identity[] = Array.isArray(raw?.data)
    ? raw.data.map((i: any) => ({
        id: i?.id ?? i?._id ?? i?.identity_id ?? i?.uuid,
        title: i?.title ?? i?.name ?? "",
        description: i?.description ?? i?.info ?? i?.style ?? i?.conversation_style ?? "",
        examples: Array.isArray(i?.conversation_example) ? i.conversation_example.length : i?.examples ?? 0,
        created_at: i?.created_at,
        updated_at: i?.updated_at,
      }))
    : [];
  return { success: !!raw?.success, data, total: raw?.total ?? data.length, message: raw?.message };
}

export async function getIdentity(identity_id: string | number): Promise<IdentityResponse> {
  const res = await apiFetch(`/identities/${identity_id}`, { method: "GET" });
  const raw = await handle<any>(res);
  const i = raw?.data ?? {};
  const data: Identity = {
    id: i?.id ?? i?._id ?? i?.identity_id ?? i?.uuid,
    title: i?.title ?? i?.name ?? "",
    description: i?.description ?? i?.info ?? i?.style ?? i?.conversation_style ?? "",
    examples: Array.isArray(i?.conversation_example) ? i.conversation_example.length : i?.examples ?? 0,
    created_at: i?.created_at,
    updated_at: i?.updated_at,
  };
  return { success: !!raw?.success, data, message: raw?.message };
}

export async function copyIdentity(identity_id: string | number): Promise<IdentityResponse> {
  const res = await apiFetch(`/identities/${identity_id}/copy`, { method: "POST" });
  const raw = await handle<any>(res);
  const i = raw?.data ?? {};
  const data: Identity = {
    id: i?.id ?? i?._id ?? i?.identity_id ?? i?.uuid,
    title: i?.title ?? i?.name ?? "",
    description: i?.description ?? i?.info ?? i?.style ?? i?.conversation_style ?? "",
    examples: Array.isArray(i?.conversation_example) ? i.conversation_example.length : i?.examples ?? 0,
    created_at: i?.created_at,
    updated_at: i?.updated_at,
  };
  return { success: !!raw?.success, data, message: raw?.message };
}

// Procedure (Workflow) Management API Functions
export interface Procedure {
  id: string | number;
  title: string;
  description?: string;
  type?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ProceduresResponse {
  success: boolean;
  data: Procedure[];
  total?: number;
  message?: string;
}

export interface ProcedureResponse {
  success: boolean;
  data: Procedure;
  message?: string;
}

export async function getProcedures(params?: { q?: string; skip?: number; limit?: number }): Promise<ProceduresResponse> {
  const queryParams = new URLSearchParams();
  if (params?.q) queryParams.append("q", params.q);
  if (params?.skip !== undefined) queryParams.append("skip", params.skip.toString());
  if (params?.limit !== undefined) queryParams.append("limit", params.limit.toString());
  const queryString = queryParams.toString();
  const path = `/procedures${queryString ? `?${queryString}` : ""}`;
  const res = await apiFetch(path, { method: "GET" });
  const raw = await handle<any>(res);
  const data: Procedure[] = Array.isArray(raw?.data)
    ? raw.data.map((i: any) => ({
        id: i?.id ?? i?._id ?? i?.procedure_id ?? i?.uuid,
        title: i?.title ?? i?.name ?? "",
        description: i?.description ?? i?.procedure ?? "",
        type: i?.type,
        created_at: i?.created_at,
        updated_at: i?.updated_at,
      }))
    : [];
  return { success: !!raw?.success, data, total: raw?.total ?? data.length, message: raw?.message };
}

export async function getProcedure(procedure_id: string | number): Promise<ProcedureResponse> {
  const res = await apiFetch(`/procedures/${procedure_id}`, { method: "GET" });
  const raw = await handle<any>(res);
  const i = raw?.data ?? {};
  const data: Procedure = {
    id: i?.id ?? i?._id ?? i?.procedure_id ?? i?.uuid,
    title: i?.title ?? i?.name ?? "",
    description: i?.description ?? i?.procedure ?? "",
    type: i?.type,
    created_at: i?.created_at,
    updated_at: i?.updated_at,
  };
  return { success: !!raw?.success, data, message: raw?.message };
}

export async function updateProcedure(
  procedure_id: string | number,
  data: Partial<Pick<Procedure, "title" | "description" | "type">>
): Promise<ProcedureResponse> {
  const payload: any = {};
  if (data.title !== undefined) payload.name = data.title;
  if (data.description !== undefined) payload.procedure = data.description;
  if (data.type !== undefined) payload.type = data.type;
  const res = await apiFetch(`/procedures/${procedure_id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  const raw = await handle<any>(res);
  const i = raw?.data ?? {};
  const mapped: Procedure = {
    id: i?.id ?? i?._id ?? i?.procedure_id ?? i?.uuid,
    title: i?.title ?? i?.name ?? "",
    description: i?.description ?? i?.procedure ?? "",
    type: i?.type,
    created_at: i?.created_at,
    updated_at: i?.updated_at,
  };
  return { success: !!raw?.success, data: mapped, message: raw?.message };
}

export async function deleteProcedure(procedure_id: string | number): Promise<{ success: boolean; message?: string }> {
  const res = await apiFetch(`/procedures/${procedure_id}`, { method: "DELETE" });
  return handle(res);
}

export async function copyProcedure(procedure_id: string | number): Promise<ProcedureResponse> {
  const res = await apiFetch(`/procedures/${procedure_id}/copy`, { method: "POST" });
  const raw = await handle<any>(res);
  const i = raw?.data ?? {};
  const data: Procedure = {
    id: i?.id ?? i?._id ?? i?.procedure_id ?? i?.uuid,
    title: i?.title ?? i?.name ?? "",
    description: i?.description ?? i?.procedure ?? "",
    type: i?.type,
    created_at: i?.created_at,
    updated_at: i?.updated_at,
  };
  return { success: !!raw?.success, data, message: raw?.message };
}