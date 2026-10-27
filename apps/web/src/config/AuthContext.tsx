import React, { createContext, useContext, useEffect, useState } from "react";
import { apiClient, UserProfile, DirectTokenPayload, StepUpPayload } from "@/api/client";

interface AuthContextType {
  user: UserProfile | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isSessionExpired: boolean;
  isForbidden: boolean;
  login: (credentials: DirectTokenPayload) => Promise<void>;
  logout: () => Promise<void>;
  stepUp: (payload: StepUpPayload) => Promise<void>;
  clearForbidden: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSessionExpired, setIsSessionExpired] = useState(false);
  const [isForbidden, setIsForbidden] = useState(false);

  const refreshUser = async () => {
    try {
      const profile = await apiClient.getMe();
      setUser(profile);
      setIsSessionExpired(false);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();

    const handleUnauthorized = () => {
      setIsSessionExpired(true);
      setUser(null);
    };

    const handleForbidden = () => {
      setIsForbidden(true);
    };

    window.addEventListener("elixir:unauthorized", handleUnauthorized);
    window.addEventListener("elixir:forbidden", handleForbidden);

    return () => {
      window.removeEventListener("elixir:unauthorized", handleUnauthorized);
      window.removeEventListener("elixir:forbidden", handleForbidden);
    };
  }, []);

  const login = async (credentials: DirectTokenPayload) => {
    setIsLoading(true);
    try {
      const profile = await apiClient.loginWithPassword(credentials);
      setUser(profile);
      setIsSessionExpired(false);
      setIsForbidden(false);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await apiClient.logout();
    } finally {
      setUser(null);
      setIsLoading(false);
    }
  };

  const stepUp = async (payload: StepUpPayload) => {
    await apiClient.stepUpMfa(payload);
    await refreshUser();
  };

  const clearForbidden = () => setIsForbidden(false);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        isSessionExpired,
        isForbidden,
        login,
        logout,
        stepUp,
        clearForbidden,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
