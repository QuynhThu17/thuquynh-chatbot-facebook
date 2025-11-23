export type Tokens = {
  access_token: string;
  refresh_token?: string | null;
  token_type?: string;
};

const ACCESS_KEY = "mkai_access_token";
const REFRESH_KEY = "mkai_refresh_token";
const TYPE_KEY = "mkai_token_type";

export function saveTokens(tokens: Tokens & { persist?: boolean }) {
  const storage = tokens.persist ? localStorage : sessionStorage;
  try {
    storage.setItem(ACCESS_KEY, tokens.access_token);
    if (tokens.refresh_token) storage.setItem(REFRESH_KEY, tokens.refresh_token);
    if (tokens.token_type) storage.setItem(TYPE_KEY, tokens.token_type);
  } catch {}
}

export function getAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_KEY) || localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_KEY) || localStorage.getItem(REFRESH_KEY);
}

export function clearTokens() {
  try {
    sessionStorage.removeItem(ACCESS_KEY);
    sessionStorage.removeItem(REFRESH_KEY);
    sessionStorage.removeItem(TYPE_KEY);
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(TYPE_KEY);
  } catch {}
}