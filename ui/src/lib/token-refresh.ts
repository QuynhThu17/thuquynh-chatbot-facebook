import { 
  getAccessToken, 
  getRefreshToken, 
  saveTokens, 
  clearTokens 
} from "./auth-storage";
import { refreshToken } from "./api";

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
      const response = await refreshToken();
      
      if (response.success && response.data?.access_token) {
        const newAccessToken = response.data.access_token;
        saveTokens({
          access_token: newAccessToken,
          token_type: "Bearer",
          refresh_token: refreshTokenValue
        });

        // Process queued requests
        this.failedQueue.forEach(({ resolve }) => {
          resolve(newAccessToken);
        });
        this.failedQueue = [];

        return newAccessToken;
      } else {
        throw new Error("Invalid refresh token response");
      }
    } catch (error) {
      // Process failed queue
      this.failedQueue.forEach(({ reject }) => {
        reject(error instanceof Error ? error : new Error("Token refresh failed"));
      });
      this.failedQueue = [];

      // Không xoá token ngay lập tức để tránh tự thoát do lỗi mạng tạm thời
      // Việc chuyển hướng sẽ được xử lý tại api layer nếu server trả 401 liên tục
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