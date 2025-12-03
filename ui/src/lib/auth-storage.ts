export type Tokens = {
  access_token: string;
  refresh_token?: string | null;
  token_type?: string;
};

const ACCESS_KEY = "mkai_access_token";
const REFRESH_KEY = "mkai_refresh_token";
const TYPE_KEY = "mkai_token_type";

export function saveTokens(tokens: Tokens & { persist?: boolean }) {
  if (typeof window === "undefined") return;
  const ls = window.localStorage;
  const ss = window.sessionStorage;
  try {
    const primary = tokens.persist ? ls : ss;
    const secondary = tokens.persist ? ss : ls;

    secondary.removeItem(ACCESS_KEY);
    secondary.removeItem(REFRESH_KEY);
    secondary.removeItem(TYPE_KEY);

    primary.setItem(ACCESS_KEY, tokens.access_token);
    if (tokens.refresh_token) primary.setItem(REFRESH_KEY, tokens.refresh_token);
    if (tokens.token_type) primary.setItem(TYPE_KEY, tokens.token_type);
  } catch {}
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_KEY) || window.sessionStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY) || window.sessionStorage.getItem(REFRESH_KEY);
}

export function clearTokens() {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(ACCESS_KEY);
    window.sessionStorage.removeItem(REFRESH_KEY);
    window.sessionStorage.removeItem(TYPE_KEY);
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
    window.localStorage.removeItem(TYPE_KEY);
  } catch {}
}
