import { 
  getAccessToken, 
  getRefreshToken, 
  saveTokens, 
  clearTokens 
} from "./auth-storage";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:1975/api/v1").replace(/\/$/, "");
async function requestRefresh(refresh_token: string): Promise<any> {
  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token }),
    credentials: "include",
  });
  const ct = res.headers.get("content-type") || "";
  const isJson = ct.toLowerCase().includes("application/json");
  const bodyText = await res.text();
  const parsed = isJson && bodyText ? JSON.parse(bodyText) : bodyText ? { message: bodyText } : {};
  if (!res.ok) {
    const msg = (parsed as any)?.detail || (parsed as any)?.message || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return parsed;
}

class TokenRefreshManager {
  private isRefreshing = false;
  private failedQueue: Array<{
    resolve: (value: string) => void;
    reject: (error: Error) => void;
  }> = [];
  private monitoringInterval: NodeJS.Timeout | null = null;
  private eventListeners: Map<string, Array<(...args: any[]) => void>> = new Map();

  async refreshAccessToken(): Promise<string> {
    if (this.isRefreshing) {
      return new Promise((resolve, reject) => {
        this.failedQueue.push({ resolve, reject });
      });
    }

    this.isRefreshing = true;
    const refreshTokenValue = getRefreshToken();

    if (!refreshTokenValue) {
      this.isRefreshing = false;
      throw new Error("No refresh token available");
    }

    try {
      const response = await requestRefresh(refreshTokenValue);

      const pick = (obj: any): string | undefined => {
        const cands = [
          obj?.access_token,
          obj?.token,
          obj?.data?.access_token,
          obj?.data?.token,
          obj?.result?.access_token,
          obj?.payload?.access_token,
        ];
        for (const v of cands) {
          if (typeof v === "string" && v) return v;
        }
        return undefined;
      };

      const newAccessToken = pick(response);

      if (newAccessToken) {
        saveTokens({
          access_token: newAccessToken,
          token_type: "Bearer",
          refresh_token: refreshTokenValue,
          persist: true,
        });

        this.failedQueue.forEach(({ resolve }) => {
          resolve(newAccessToken);
        });
        this.failedQueue = [];

        return newAccessToken;
      }

      this.failedQueue.forEach(({ resolve }) => {
        resolve("");
      });
      this.failedQueue = [];

      return "";
    } catch (error) {
      // Process failed queue
      this.failedQueue.forEach(({ reject }) => {
        reject(error instanceof Error ? error : new Error("Token refresh failed"));
      });
      this.failedQueue = [];

      this.emit('tokenRefreshFailed');
      throw error;
    } finally {
      this.isRefreshing = false;
    }
  }

  startMonitoring(): void {
    if (this.monitoringInterval) {
      return; // Already monitoring
    }

    // Check token expiration every minute
    this.monitoringInterval = setInterval(() => {
      const accessToken = getAccessToken();
      if (!accessToken) {
        this.stopMonitoring();
        return;
      }

      try {
        // Decode JWT token to check expiration
        const payload = JSON.parse(atob(accessToken.split('.')[1]));
        const exp = payload.exp * 1000; // Convert to milliseconds
        const now = Date.now();
        const timeUntilExpiry = exp - now;

        // Refresh token if it expires in less than 5 minutes
        if (timeUntilExpiry < 5 * 60 * 1000) {
          this.refreshAccessToken()
            .then(() => this.emit('tokenRefreshed'))
            .catch(() => this.emit('tokenRefreshFailed'));
        }
      } catch (error) {
        console.error('Token monitoring error:', error);
        this.emit('tokenRefreshFailed');
      }
    }, 60000); // Check every minute
  }

  stopMonitoring(): void {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = null;
    }
  }

  on(event: string, callback: (...args: any[]) => void): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event)!.push(callback);
  }

  off(event: string, callback: (...args: any[]) => void): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      const index = listeners.indexOf(callback);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  private emit(event: string, ...args: any[]): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.forEach(callback => callback(...args));
    }
  }
}

export const tokenRefreshManager = new TokenRefreshManager();
