import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { api, type User } from "./api";

type AuthState = {
  token: string | null;
  user: User | null;
  loading: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
};

const TOKEN_KEY = "bangstats.web.token";
const USER_KEY = "bangstats.web.user";

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as User;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState<boolean>(Boolean(token && user));

  useEffect(() => {
    api.setToken(token);
  }, [token]);

  useEffect(() => {
    api.setUnauthorizedHandler(() => {
      setToken(null);
      setUser(null);
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    });
  }, []);

  useEffect(() => {
    if (!token || !user) {
      setLoading(false);
      return;
    }
    void refresh();
  }, []);

  async function refresh() {
    if (!token || !user) return;
    setLoading(true);
    try {
      api.setToken(token);
      const fresh = await api.getUser(user.id);
      setUser(fresh);
      localStorage.setItem(USER_KEY, JSON.stringify(fresh));
    } finally {
      setLoading(false);
    }
  }

  function login(nextToken: string, nextUser: User) {
    api.setToken(nextToken);
    setToken(nextToken);
    setUser(nextUser);
    localStorage.setItem(TOKEN_KEY, nextToken);
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
  }

  function logout() {
    api.setToken(null);
    setToken(null);
    setUser(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  const value = useMemo<AuthState>(
    () => ({
      token,
      user,
      loading,
      login,
      logout,
      refreshUser: refresh,
    }),
    [token, user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
