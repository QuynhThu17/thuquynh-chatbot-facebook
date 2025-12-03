import { getAccessToken, getRefreshToken, saveTokens, clearTokens } from "./auth-storage";
import { tokenRefreshManager } from "./token-refresh";

const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:1975/api/v1`
    : "http://localhost:1975/api/v1")
).replace(/\/$/, "");

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
      refresh_token: refreshToken,
      persist: true
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

export async function updateAvatar(avatar_url: string): Promise<{ success: boolean; data?: any; message?: string }> {
  const res = await apiFetch("/avatar/update-avatar", { method: "PUT", body: JSON.stringify({ avatar_url }) });
  return handle(res);
}

export async function deleteAvatar(): Promise<{ success: boolean; message?: string }> {
  const res = await apiFetch("/avatar/delete-avatar", { method: "DELETE" });
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
        const refreshed = await tokenRefreshManager.refreshAccessToken();
        const newToken = getAccessToken();

        if (newToken && newToken !== token) {
          headers.set("Authorization", `Bearer ${newToken}`);
        } else {
          headers.delete("Authorization");
        }

        const retryResponse = await fetch(url(path), {
          ...options,
          headers,
          credentials: "include",
        });
        
        if (!retryResponse.ok) {
          const error = new Error(`API Error: ${retryResponse.status}`);
          (error as any).status = retryResponse.status;
          (error as any).response = retryResponse;
          throw error;
        }
        
        return retryResponse;
      } catch (refreshError) {
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
  const raw = await handle<any>(res);
  const rows: any[] = Array.isArray(raw?.data) ? raw.data : Array.isArray(raw) ? raw : [];
  const data: Bot[] = rows.map((b: any) => ({
    id: String(b?.id ?? b?._id ?? b?.bot_id ?? b?.uuid ?? ""),
    name: b?.name ?? b?.title ?? "",
    role: b?.role ?? b?.description ?? "",
    target: b?.target ?? b?.goal ?? "",
    mission: b?.mission ?? b?.task ?? "",
    note: b?.note ?? b?.notes ?? undefined,
    status: (() => {
      const rawStatus = ((): string | undefined => {
        if (typeof b?.status === "string") return b.status;
        if (typeof b?.state === "string") return b.state;
        if (typeof b?.active === "boolean") return b.active ? "active" : "inactive";
        return undefined;
      })();
      const s = String(rawStatus || "").toLowerCase();
      if (s === "on" || s === "active" || s === "running" || s === "enabled") return "active";
      if (s === "off" || s === "inactive" || s === "stopped" || s === "disabled") return "inactive";
      return s || undefined;
    })(),
    type: b?.type ?? b?.bot_type ?? undefined,
    language_code: b?.language_code ?? b?.language ?? undefined,
    identity_id: b?.identity_id ?? b?.identity?.id ?? b?.identity?._id ?? undefined,
    procedure_id: b?.procedure_id ?? b?.workflow_id ?? b?.workflow?.id ?? b?.procedure?.id ?? undefined,
    knowledge: b?.knowledge ?? b?.knowledge_docs ?? undefined,
    connect: b?.connect ?? b?.connection ?? undefined,
    created_at: b?.created_at,
    updated_at: b?.updated_at,
  }));
  return { success: !!raw?.success, data, total: raw?.total ?? data.length, message: raw?.message };
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

export interface BotKnowledgeData {
  bot_id?: string;
  bot_name?: string;
  knowledge_count?: number;
  documents: KnowledgeDocument[];
}

export interface KnowledgeListResponse {
  success: boolean;
  data: BotKnowledgeData;
  message?: string;
}

export interface DocumentsListResponse {
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
  const rows: any[] = Array.isArray(raw?.data?.documents) ? raw.data.documents : [];
  const documents: KnowledgeDocument[] = rows.map((d: any) => ({
    id: d?.document_id ?? d?.id ?? d?._id ?? d?.uuid,
    title: d?.document_name ?? d?.title ?? d?.name ?? d?.file_name ?? d?.filename ?? "",
    file_name: d?.file_name ?? d?.filename ?? undefined,
    segments: d?.segments ?? d?.chunks ?? undefined,
    images: d?.images ?? d?.image_count ?? undefined,
    status: d?.status ?? d?.state ?? undefined,
    created_at: d?.created_at ?? d?.create_at,
    updated_at: d?.updated_at,
  }));
  return { success: !!raw?.success, data: { bot_id: raw?.data?.bot_id, bot_name: raw?.data?.bot_name, knowledge_count: raw?.data?.knowledge_count ?? documents.length, documents }, message: raw?.message };
}

export async function setBotKnowledge(bot_id: string | number, document_ids: Array<string | number>): Promise<{ success: boolean; data?: any; message?: string }> {
  const payload = { knowledge: document_ids.map((x) => String(x)) };
  const res = await apiFetch(`/bots/${bot_id}/knowledge`, { method: "PUT", body: JSON.stringify(payload) });
  return handle(res);
}

export async function addBotKnowledge(bot_id: string | number, document_ids: Array<string | number>): Promise<{ success: boolean; data?: any; message?: string }> {
  const payload = { knowledge: document_ids.map((x) => String(x)) };
  const res = await apiFetch(`/bots/${bot_id}/knowledge/add`, { method: "POST", body: JSON.stringify(payload) });
  return handle(res);
}

export async function removeBotKnowledge(bot_id: string | number, document_id: string | number): Promise<{ success: boolean; message?: string }> {
  const res = await apiFetch(`/bots/${bot_id}/knowledge/${document_id}`, { method: "DELETE" });
  return handle(res);
}

// Documents API
export async function getDocuments(): Promise<DocumentsListResponse> {
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

export async function uploadDocument(payload: { file: File; title?: string; company_id?: string; process_images?: boolean; parser_engine?: string }): Promise<KnowledgeResponse> {
  const fd = new FormData();
  fd.append("file", payload.file);
  if (payload.title !== undefined) fd.append("name", String(payload.title));
  if (payload.company_id) fd.append("company_id", String(payload.company_id));
  fd.append("process_images", String(!!payload.process_images));
  fd.append("parser_engine", payload.parser_engine ? String(payload.parser_engine) : "ragflow");
  const res = await apiFetch(`/documents/upload`, { method: "POST", body: fd });
  const raw = await handle<any>(res);
  const d = raw?.data ?? {};
  const mapped: KnowledgeDocument = {
    id: d?.id ?? d?._id ?? d?.document_id ?? d?.uuid,
    title: d?.title ?? d?.name ?? d?.file_name ?? d?.filename ?? "",
    file_name: d?.file_name ?? d?.filename ?? undefined,
    segments: d?.segments ?? d?.chunks ?? d?.total_chunks ?? undefined,
    images: d?.images ?? d?.image_count ?? d?.total_images ?? undefined,
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

export interface SocialPlatform {
  id: string | number;
  name: string;
  active?: boolean;
}

export interface SocialPage {
  id: string | number;
  name: string;
  status?: string;
  is_connected?: boolean;
}

export async function getSocials(): Promise<{ success: boolean; data: SocialPlatform[]; message?: string }> {
  const res = await apiFetch(`/socials`, { method: "GET" });
  const raw = await handle<any>(res);
  const rows: any[] = Array.isArray(raw?.data) ? raw.data : Array.isArray(raw) ? raw : [];
  const data: SocialPlatform[] = rows.map((s: any) => ({
    id: s?.id ?? s?._id ?? s?.social_id ?? s?.uuid ?? s?.code ?? s?.key,
    name: s?.name ?? s?.title ?? s?.label ?? s?.platform_name ?? "",
    active: !!(s?.active ?? s?.enabled ?? s?.status === "active")
  }));
  return { success: !!raw?.success, data, message: raw?.message };
}

export async function getSocialPages(
  social_id: string | number,
  social_accounts_id: string | number
): Promise<{ success: boolean; data: SocialPage[]; message?: string }> {
  const query = new URLSearchParams({ social_accounts_id: String(social_accounts_id) }).toString();
  const res = await apiFetch(`/socials/${social_id}/pages?${query}`, { method: "GET" });
  const raw = await handle<any>(res);
  const rows_source: any = raw?.data ?? raw;
  const rows: any[] = Array.isArray(rows_source)
    ? rows_source
    : Array.isArray(rows_source?.pages)
    ? rows_source.pages
    : Array.isArray(rows_source?.social_pages)
    ? rows_source.social_pages
    : [];
  const data: SocialPage[] = rows.map((p: any) => {
    const pools = [p, p?.page, p?.social_page, p?.page?.page, p?.social_page?.page];
    const pick = (keys: string[]): any => {
      for (const obj of pools) {
        for (const k of keys) {
          const v = obj?.[k];
          if (v !== undefined && v !== null && v !== "") return v;
        }
      }
      for (const obj of pools) {
        if (obj && typeof obj === "object") {
          for (const k of Object.keys(obj)) {
            if (/^id$|_id$|id$|page_id$|social_page_id$/i.test(k)) {
              const v = (obj as any)[k];
              if (v !== undefined && v !== null && v !== "") return v;
            }
          }
        }
      }
      return undefined;
    };
    const pickName = (): string | undefined => {
      const val = pick(["name", "title", "page_name", "social_page_name", "fb_page_name", "display_name"]);
      if (typeof val === "string") return val;
      return undefined;
    };
    const pickId = (): string | number | undefined => {
      const val = pick(["id", "_id", "page_id", "social_page_id", "uuid"]);
      return val as any;
    };
    const pickStatus = (): string | undefined => {
      const val = pick(["status", "state"]);
      if (typeof val === "string") return val;
      return undefined;
    };
    const pickConnected = (): boolean | undefined => {
      const val = pick(["is_connected", "connected"]);
      if (typeof val === "boolean") return val;
      if (typeof val === "string") {
        const v = val.toLowerCase();
        if (/^(true|1|connected|connect)$/i.test(v)) return true;
        if (/^(false|0|disconnected|disconnect)$/i.test(v)) return false;
      }
      return undefined;
    };
    const id = pickId();
    const name = pickName() ?? (typeof id !== "undefined" ? String(id) : "");
    const status = pickStatus();
    const is_connected = pickConnected() ?? false;
    return { id: id as any, name, status, is_connected } as SocialPage;
  });
  return { success: !!raw?.success, data, message: raw?.message };
}

export type MajorTopItem = { major: string; count: number };
export type MajorsTimelineItem = { date: string; counts: Record<string, number> };
export type TopicItem = { topic: string; count: number };
export type PopularQuestionItem = { question: string; count: number; sample?: string };
export type HeatmapItem = { dow: number; hour: number; count: number };

export async function getStatisticsTopMajors(params?: {
  start_date?: string;
  end_date?: string;
  session_id?: string;
  customer_id?: string;
  bot_id?: string;
  social_id?: string;
  social_page_id?: string;
  limit?: number;
  auto_extract?: boolean;
}): Promise<{ success: boolean; data: MajorTopItem[]; message?: string }> {
  const qs = new URLSearchParams();
  if (params?.start_date) qs.append("start_date", params.start_date);
  if (params?.end_date) qs.append("end_date", params.end_date);
  if (params?.session_id) qs.append("session_id", params.session_id);
  if (params?.customer_id) qs.append("customer_id", params.customer_id);
  if (params?.bot_id) qs.append("bot_id", params.bot_id);
  if (params?.social_id) qs.append("social_id", params.social_id);
  if (params?.social_page_id) qs.append("social_page_id", params.social_page_id);
  if (params?.limit) qs.append("limit", String(params.limit));
  if (params?.auto_extract !== undefined) qs.append("auto_extract", String(params.auto_extract));
  const path = `/statistics/majors/top${qs.toString() ? `?${qs.toString()}` : ""}`;
  const res = await apiFetch(path, { method: "GET" });
  const raw = await handle<any>(res);
  const rows: any[] = Array.isArray(raw?.data) ? raw.data : [];
  const data: MajorTopItem[] = rows.map((r: any) => ({ major: String(r?.major ?? ""), count: Number(r?.count ?? 0) }));
  return { success: !!raw?.success, data, message: raw?.message };
}

export async function getStatisticsMajorsTimeline(params?: {
  start_date?: string;
  end_date?: string;
  session_id?: string;
  customer_id?: string;
  bot_id?: string;
  social_id?: string;
  social_page_id?: string;
  auto_extract?: boolean;
}): Promise<{ success: boolean; data: MajorsTimelineItem[]; message?: string }> {
  const qs = new URLSearchParams();
  if (params?.start_date) qs.append("start_date", params.start_date);
  if (params?.end_date) qs.append("end_date", params.end_date);
  if (params?.session_id) qs.append("session_id", params.session_id);
  if (params?.customer_id) qs.append("customer_id", params.customer_id);
  if (params?.bot_id) qs.append("bot_id", params.bot_id);
  if (params?.social_id) qs.append("social_id", params.social_id);
  if (params?.social_page_id) qs.append("social_page_id", params.social_page_id);
  if (params?.auto_extract !== undefined) qs.append("auto_extract", String(params.auto_extract));
  const path = `/statistics/majors/timeline${qs.toString() ? `?${qs.toString()}` : ""}`;
  const res = await apiFetch(path, { method: "GET" });
  const raw = await handle<any>(res);
  const rows: any[] = Array.isArray(raw?.data) ? raw.data : [];
  const data: MajorsTimelineItem[] = rows.map((r: any) => ({ date: String(r?.date ?? r?._id?.date ?? ""), counts: r?.counts ?? {} }));
  return { success: !!raw?.success, data, message: raw?.message };
}

export async function getStatisticsMajorTopics(params?: {
  start_date?: string;
  end_date?: string;
  major?: string;
  session_id?: string;
  customer_id?: string;
  bot_id?: string;
  social_id?: string;
  social_page_id?: string;
  limit?: number;
  auto_extract?: boolean;
}): Promise<{ success: boolean; data: TopicItem[]; message?: string }> {
  const qs = new URLSearchParams();
  if (params?.start_date) qs.append("start_date", params.start_date);
  if (params?.end_date) qs.append("end_date", params.end_date);
  if (params?.major) qs.append("major", params.major);
  if (params?.session_id) qs.append("session_id", params.session_id);
  if (params?.customer_id) qs.append("customer_id", params.customer_id);
  if (params?.bot_id) qs.append("bot_id", params.bot_id);
  if (params?.social_id) qs.append("social_id", params.social_id);
  if (params?.social_page_id) qs.append("social_page_id", params.social_page_id);
  if (params?.limit) qs.append("limit", String(params.limit));
  if (params?.auto_extract !== undefined) qs.append("auto_extract", String(params.auto_extract));
  const path = `/statistics/majors/topics${qs.toString() ? `?${qs.toString()}` : ""}`;
  const res = await apiFetch(path, { method: "GET" });
  const raw = await handle<any>(res);
  const rows: any[] = Array.isArray(raw?.data) ? raw.data : [];
  const data: TopicItem[] = rows.map((r: any) => ({ topic: String(r?.topic ?? ""), count: Number(r?.count ?? 0) }));
  return { success: !!raw?.success, data, message: raw?.message };
}

export async function getStatisticsPopularQuestions(params?: {
  start_date?: string;
  end_date?: string;
  session_id?: string;
  customer_id?: string;
  bot_id?: string;
  social_id?: string;
  social_page_id?: string;
  limit?: number;
  auto_extract?: boolean;
}): Promise<{ success: boolean; data: PopularQuestionItem[]; message?: string }> {
  const qs = new URLSearchParams();
  if (params?.start_date) qs.append("start_date", params.start_date);
  if (params?.end_date) qs.append("end_date", params.end_date);
  if (params?.session_id) qs.append("session_id", params.session_id);
  if (params?.customer_id) qs.append("customer_id", params.customer_id);
  if (params?.bot_id) qs.append("bot_id", params.bot_id);
  if (params?.social_id) qs.append("social_id", params.social_id);
  if (params?.social_page_id) qs.append("social_page_id", params.social_page_id);
  if (params?.limit) qs.append("limit", String(params.limit));
  if (params?.auto_extract !== undefined) qs.append("auto_extract", String(params.auto_extract));
  const path = `/statistics/questions/popular${qs.toString() ? `?${qs.toString()}` : ""}`;
  const res = await apiFetch(path, { method: "GET" });
  const raw = await handle<any>(res);
  const rows: any[] = Array.isArray(raw?.data) ? raw.data : [];
  const data: PopularQuestionItem[] = rows.map((r: any) => ({ question: String(r?.question ?? ""), count: Number(r?.count ?? 0), sample: r?.sample }));
  return { success: !!raw?.success, data, message: raw?.message };
}

export async function getStatisticsHeatmap(params?: {
  start_date?: string;
  end_date?: string;
  session_id?: string;
  customer_id?: string;
  bot_id?: string;
  social_id?: string;
  social_page_id?: string;
  auto_extract?: boolean;
}): Promise<{ success: boolean; data: HeatmapItem[]; message?: string }> {
  const qs = new URLSearchParams();
  if (params?.start_date) qs.append("start_date", params.start_date);
  if (params?.end_date) qs.append("end_date", params.end_date);
  if (params?.session_id) qs.append("session_id", params.session_id);
  if (params?.customer_id) qs.append("customer_id", params.customer_id);
  if (params?.bot_id) qs.append("bot_id", params.bot_id);
  if (params?.social_id) qs.append("social_id", params.social_id);
  if (params?.social_page_id) qs.append("social_page_id", params.social_page_id);
  if (params?.auto_extract !== undefined) qs.append("auto_extract", String(params.auto_extract));
  const path = `/statistics/heatmap${qs.toString() ? `?${qs.toString()}` : ""}`;
  const res = await apiFetch(path, { method: "GET" });
  const raw = await handle<any>(res);
  const rows: any[] = Array.isArray(raw?.data) ? raw.data : [];
  const data: HeatmapItem[] = rows.map((r: any) => ({ dow: Number(r?.dow ?? 0), hour: Number(r?.hour ?? 0), count: Number(r?.count ?? 0) }));
  return { success: !!raw?.success, data, message: raw?.message };
}

export async function connectBotToSocial(
  bot_id: string | number,
  payload: {
    social_id: string | number;
    social_page_id: string | number;
  }
): Promise<{ success: boolean; message?: string; data?: any }> {
  const body = {
    social_id: payload.social_id,
    social_page_id: payload.social_page_id,
  };
  const res = await apiFetch(`/bots/${bot_id}/connection`, { method: "PUT", body: JSON.stringify(body) });
  return handle(res);
}

export async function disconnectBotFromSocial(
  bot_id: string | number,
  social_page_id: string | number
): Promise<{ success: boolean; message?: string; data?: any }> {
  const res = await apiFetch(`/bots/${bot_id}/connections/${social_page_id}`, { method: "DELETE" });
  return handle(res);
}

export async function getSocialPageById(
  social_id: string | number,
  social_page_id: string | number
): Promise<{ success: boolean; data?: any; message?: string }> {
  const res = await apiFetch(`/socials/${social_id}/pages/${social_page_id}`, { method: "GET" });
  return handle(res);
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

export async function createProcedure(payload: { title: string; description: string; type?: string }): Promise<ProcedureResponse> {
  const body: any = {
    name: payload.title,
    procedure: payload.description,
    type: payload.type ?? "custom",
  };
  const res = await apiFetch(`/procedures`, { method: "POST", body: JSON.stringify(body) });
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

export async function createIdentity(payload: {
  title: string;
  description: string;
  style: string;
  conversation_examples?: { user: string; you: string }[];
}): Promise<IdentityResponse> {
  const body: any = {
    name: payload.title,
    info: payload.description,
    style: payload.style,
    conversation_style: payload.style,
    conversation_example: Array.isArray(payload.conversation_examples) ? payload.conversation_examples : [],
  };
  const res = await apiFetch(`/identities`, { method: "POST", body: JSON.stringify(body) });
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

export async function updateIdentity(
  identity_id: string | number,
  data: Partial<{ title: string; description: string; style: string; conversation_examples: { user: string; you: string }[] }>
): Promise<IdentityResponse> {
  const body: any = {};
  if (data.title !== undefined) body.name = data.title;
  if (data.description !== undefined) body.info = data.description;
  if (data.style !== undefined) {
    body.style = data.style;
    body.conversation_style = data.style;
  }
  if (data.conversation_examples !== undefined) body.conversation_example = data.conversation_examples;
  const res = await apiFetch(`/identities/${identity_id}`, { method: "PUT", body: JSON.stringify(body) });
  const raw = await handle<any>(res);
  const i = raw?.data ?? {};
  const mapped: Identity = {
    id: i?.id ?? i?._id ?? i?.identity_id ?? i?.uuid,
    title: i?.title ?? i?.name ?? "",
    description: i?.description ?? i?.info ?? i?.style ?? i?.conversation_style ?? "",
    examples: Array.isArray(i?.conversation_example) ? i.conversation_example.length : i?.examples ?? 0,
    created_at: i?.created_at,
    updated_at: i?.updated_at,
  };
  return { success: !!raw?.success, data: mapped, message: raw?.message };
}

export async function deleteIdentity(identity_id: string | number): Promise<{ success: boolean; message?: string }> {
  const res = await apiFetch(`/identities/${identity_id}`, { method: "DELETE" });
  return handle(res);
}

export async function updateBot(
  bot_id: string | number,
  data: Partial<Pick<Bot, "name" | "role" | "target" | "mission" | "note" | "type" | "language_code" | "identity_id" | "procedure_id" | "status" | "knowledge" | "connect">>
): Promise<{ success: boolean; data?: Bot; message?: string }> {
  const body: any = {};
  if (data.name !== undefined) body.name = data.name;
  if (data.language_code !== undefined) body.language_code = data.language_code;
  if (data.identity_id !== undefined) body.identity_id = data.identity_id;
  if (data.procedure_id !== undefined) body.procedure_id = data.procedure_id;
  if (data.role !== undefined) body.role = data.role;
  if (data.target !== undefined) body.target = data.target;
  if (data.mission !== undefined) body.mission = data.mission;
  if (data.note !== undefined) body.note = data.note;
  if (data.type !== undefined) body.type = data.type;
  if (data.status !== undefined) body.status = data.status;
  if (data.knowledge !== undefined) body.knowledge = data.knowledge;
  if (data.connect !== undefined) body.connect = data.connect;
  const res = await apiFetch(`/bots/${bot_id}`, { method: "PUT", body: JSON.stringify(body) });
  const raw = await handle<any>(res);
  const i = raw?.data ?? {};
  const mapped: Bot = {
    id: i?.id ?? i?._id ?? i?.bot_id ?? i?.uuid,
    name: i?.name ?? i?.title ?? "",
    role: i?.role ?? i?.description ?? "",
    target: i?.target ?? i?.goal ?? "",
    mission: i?.mission ?? i?.task ?? "",
    note: i?.note ?? i?.notes ?? undefined,
    status: i?.status ?? i?.state ?? (i?.active ? "active" : undefined),
    type: i?.type ?? i?.bot_type ?? undefined,
    language_code: i?.language_code ?? i?.language ?? undefined,
    identity_id: i?.identity_id ?? i?.identity?.id ?? i?.identity?._id ?? undefined,
    procedure_id: i?.procedure_id ?? i?.workflow_id ?? i?.workflow?.id ?? i?.procedure?.id ?? undefined,
    knowledge: i?.knowledge ?? i?.knowledge_docs ?? undefined,
    connect: i?.connect ?? i?.connection ?? undefined,
    created_at: i?.created_at,
    updated_at: i?.updated_at,
  };
  return { success: !!raw?.success, data: mapped, message: raw?.message };
}

export async function deleteBot(bot_id: string | number): Promise<{ success: boolean; message?: string }> {
  const res = await apiFetch(`/bots/${bot_id}`, { method: "DELETE" });
  return handle(res);
}

export async function activateBot(bot_id: string | number): Promise<{ success: boolean; data?: any; message?: string }> {
  const res = await apiFetch(`/bots/${bot_id}/activate`, { method: "PUT" });
  return handle(res);
}

export async function deactivateBot(bot_id: string | number): Promise<{ success: boolean; data?: any; message?: string }> {
  const res = await apiFetch(`/bots/${bot_id}/deactivate`, { method: "PUT" });
  return handle(res);
}

export interface HistoryRecord {
  id: string | number;
  session_id?: string;
  customer_id?: string | number;
  bot_id?: string | number;
  social_id?: string;
  social_page_id?: string | number;
  direction?: string;
  text?: string;
  query?: string;
  answer?: string;
  created_at?: string;
  updated_at?: string;
}

export interface HistoriesResponse {
  success: boolean;
  data: HistoryRecord[];
  total?: number;
  message?: string;
}

export async function getHistories(params?: {
  session_id?: string;
  customer_id?: string | number;
  bot_id?: string | number;
  social_id?: string;
  social_page_id?: string | number;
  skip?: number;
  limit?: number;
}): Promise<HistoriesResponse> {
  const q = new URLSearchParams();
  if (params?.session_id) q.append("session_id", String(params.session_id));
  if (params?.customer_id !== undefined) q.append("customer_id", String(params.customer_id));
  if (params?.bot_id !== undefined) q.append("bot_id", String(params.bot_id));
  if (params?.social_id) q.append("social_id", String(params.social_id));
  if (params?.social_page_id !== undefined) q.append("social_page_id", String(params.social_page_id));
  if (params?.skip !== undefined) q.append("skip", String(params.skip));
  if (params?.limit !== undefined) q.append("limit", String(params.limit));
  const path = `/crm/histories${q.toString() ? `?${q.toString()}` : ""}`;
  const res = await apiFetch(path, { method: "GET" });
  const raw = await handle<any>(res);
  const rows: any[] = Array.isArray(raw?.data) ? raw.data : Array.isArray(raw) ? raw : [];
  const data: HistoryRecord[] = rows.map((h: any) => ({
    id: h?.id ?? h?._id ?? h?.history_id ?? h?.uuid,
    session_id: h?.session_id ?? h?.session?.id ?? h?.session?._id,
    customer_id: h?.customer_id ?? h?.customer?.id ?? h?.customer?._id,
    bot_id: h?.bot_id ?? h?.bot?.id ?? h?.bot?._id,
    social_id: h?.social_id ?? h?.platform ?? h?.social?.id,
    social_page_id: h?.social_page_id ?? h?.page_id ?? h?.social_page?.id ?? h?.social_page?._id,
    direction: h?.direction ?? h?.dir ?? (typeof h?.sender !== "undefined" ? (h.sender === "user" ? "in" : "out") : (typeof h?.answer !== "undefined" ? "out" : (typeof h?.query !== "undefined" ? "in" : undefined))),
    text: h?.text ?? h?.message ?? h?.content ?? h?.prompt ?? h?.answer ?? h?.query,
    query: h?.query,
    answer: h?.answer,
    created_at: h?.created_at ?? h?.timestamp ?? h?.time,
    updated_at: h?.updated_at,
  }));
  return { success: !!raw?.success, data, total: raw?.total ?? data.length, message: raw?.message };
}

export interface SessionRecord {
  id: string | number;
  customer_id?: string | number;
  social_page_id?: string | number;
  count?: number;
  last_activity?: string;
}

export async function getHistorySessions(params?: { skip?: number; limit?: number }): Promise<{ success: boolean; data: SessionRecord[]; total?: number; message?: string }> {
  const q = new URLSearchParams();
  if (params?.skip !== undefined) q.append("skip", String(params.skip));
  if (params?.limit !== undefined) q.append("limit", String(params.limit));
  const res = await apiFetch(`/crm/histories/sessions${q.toString() ? `?${q.toString()}` : ""}`, { method: "GET" });
  const raw = await handle<any>(res);
  const rows: any[] = Array.isArray(raw?.data) ? raw.data : Array.isArray(raw) ? raw : [];
  const data: SessionRecord[] = rows.map((s: any) => ({
    id: s?.id ?? s?._id ?? s?.session_id ?? s?.uuid,
    customer_id: s?.customer_id ?? s?.customer?.id ?? s?.customer?._id,
    social_page_id: s?.social_page_id ?? s?.page_id ?? s?.social_page?.id ?? s?.social_page?._id,
    count: s?.count ?? s?.messages_count ?? s?.total,
    last_activity: s?.last_activity ?? s?.updated_at ?? s?.created_at,
  }));
  return { success: !!raw?.success, data, total: raw?.total ?? data.length, message: raw?.message };
}

export async function deleteHistorySession(session_id: string | number): Promise<{ success: boolean; message?: string }> {
  const res = await apiFetch(`/crm/histories/sessions/${session_id}`, { method: "DELETE" });
  return handle(res);
}

export interface NotificationItem {
  id: string | number;
  title?: string;
  content?: string;
  category?: string;
  type?: string;
  action?: string;
  priority?: number;
  is_read?: boolean;
  created_at?: string;
}

export async function getNotifications(params?: {
  is_read?: boolean;
  category?: string;
  type?: string;
  action?: string;
  priority?: number;
  skip?: number;
  limit?: number;
}): Promise<{ success: boolean; data: NotificationItem[]; total?: number; message?: string }> {
  const q = new URLSearchParams();
  if (typeof params?.is_read === "boolean") q.append("is_read", String(params.is_read));
  if (params?.category) q.append("category", params.category);
  if (params?.type) q.append("type", params.type);
  if (params?.action) q.append("action", params.action);
  if (typeof params?.priority === "number") q.append("priority", String(params.priority));
  if (params?.skip !== undefined) q.append("skip", String(params.skip));
  if (params?.limit !== undefined) q.append("limit", String(params.limit));
  const res = await apiFetch(`/notifications${q.toString() ? `?${q.toString()}` : ""}`, { method: "GET" });
  const raw = await handle<any>(res);
  const rows_source: any = raw?.data ?? raw;
  const rows: any[] = Array.isArray(rows_source) ? rows_source : Array.isArray(rows_source?.notifications) ? rows_source.notifications : [];
  const data: NotificationItem[] = rows.map((n: any) => ({
    id: n?.id ?? n?._id ?? n?.notification_id ?? n?.uuid,
    title: n?.title ?? n?.name ?? n?.subject ?? n?.message_title,
    content: n?.content ?? n?.message ?? n?.body,
    category: n?.category ?? n?.group,
    type: n?.type ?? n?.kind,
    action: n?.action ?? n?.event,
    priority: typeof n?.priority === "number" ? n.priority : undefined,
    is_read: !!(n?.is_read ?? n?.read),
    created_at: n?.created_at ?? n?.timestamp,
  }));
  return { success: !!raw?.success, data, total: raw?.total ?? data.length, message: raw?.message };
}

export async function markNotificationRead(notification_id: string | number): Promise<{ success: boolean; message?: string }> {
  const res = await apiFetch(`/notifications/${notification_id}/read`, { method: "PUT" });
  return handle(res);
}

export async function markNotificationUnread(notification_id: string | number): Promise<{ success: boolean; message?: string }> {
  const res = await apiFetch(`/notifications/${notification_id}/unread`, { method: "PUT" });
  return handle(res);
}

export async function markAllNotificationsRead(): Promise<{ success: boolean; message?: string }> {
  const res = await apiFetch(`/notifications/mark-all-read`, { method: "PUT" });
  return handle(res);
}

export async function getUnreadNotificationCount(): Promise<{ success: boolean; data?: number; message?: string }> {
  const res = await apiFetch(`/notifications/unread-count`, { method: "GET" });
  const raw = await handle<any>(res);
  const val = typeof raw?.data === "number" ? raw.data : typeof raw === "number" ? raw : raw?.count ?? raw?.unread ?? undefined;
  return { success: !!raw?.success, data: typeof val === "number" ? val : undefined, message: raw?.message };
}

export async function getUnreadCountByCategory(): Promise<{ success: boolean; data?: Record<string, number>; message?: string }> {
  const res = await apiFetch(`/notifications/unread-count-by-category`, { method: "GET" });
  const raw = await handle<any>(res);
  const map = raw?.data ?? raw;
  const data: Record<string, number> = {};
  if (map && typeof map === "object") {
    for (const k of Object.keys(map)) {
      const v = (map as any)[k];
      if (typeof v === "number") data[k] = v;
    }
  }
  return { success: !!raw?.success, data, message: raw?.message };
}

export async function deleteNotification(notification_id: string | number): Promise<{ success: boolean; message?: string }> {
  const res = await apiFetch(`/notifications/${notification_id}`, { method: "DELETE" });
  return handle(res);
}
