"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken, clearTokens } from "./auth-storage";
import { tokenRefreshManager } from "./token-refresh";
import { logout as logoutAPI } from "./api";

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [isAuth, setIsAuth] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Use the singleton instance from token-refresh.ts

  const checkAuth = async () => {
    try {
      const authenticated = !!getAccessToken();
      setIsAuth(authenticated);
      
      if (authenticated) {
        // Start token refresh monitoring
        tokenRefreshManager.startMonitoring();
      }
    } catch (error) {
      console.error("Auth check failed:", error);
      setIsAuth(false);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      setIsLoading(true);
      tokenRefreshManager.stopMonitoring();
      await logoutAPI();
      clearTokens();
      setIsAuth(false);
      router.push("/auth/login");
    } catch (error) {
      console.error("Logout failed:", error);
      clearTokens();
      setIsAuth(false);
      router.push("/auth/login");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    checkAuth();
    setIsLoading(false);

    // Monitor token refresh
    const handleTokenRefresh = () => {
      checkAuth();
    };

    tokenRefreshManager.on('tokenRefreshed', handleTokenRefresh);
    tokenRefreshManager.on('tokenRefreshFailed', handleTokenRefresh);

    return () => {
      tokenRefreshManager.off('tokenRefreshed', handleTokenRefresh);
      tokenRefreshManager.off('tokenRefreshFailed', handleTokenRefresh);
      tokenRefreshManager.stopMonitoring();
    };
  }, []);

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: isAuth,
        isLoading,
        logout,
        checkAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}