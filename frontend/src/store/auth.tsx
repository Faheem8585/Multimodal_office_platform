import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api, setAccessToken, setAuthFailureHandler } from "@/api/client";
import type { RoleName, TokenPair, User } from "@/lib/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (role: RoleName) => boolean;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

const ROLE_RANK: Record<RoleName, number> = {
  viewer: 0,
  dept_member: 1,
  dept_manager: 2,
  admin: 3,
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    const me = await api.get<User>("/auth/me");
    setUser(me.data);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api.post<TokenPair>("/auth/login", { email, password });
      setAccessToken(res.data.access_token);
      await loadMe();
    },
    [loadMe],
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout", {});
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  // On boot: try to silently restore a session via the refresh cookie.
  useEffect(() => {
    setAuthFailureHandler(() => {
      setAccessToken(null);
      setUser(null);
    });
    (async () => {
      try {
        const res = await api.post<TokenPair>("/auth/refresh", {});
        setAccessToken(res.data.access_token);
        await loadMe();
      } catch {
        setAccessToken(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [loadMe]);

  const hasRole = useCallback(
    (role: RoleName) =>
      !!user && Math.max(...user.roles.map((r) => ROLE_RANK[r])) >= ROLE_RANK[role],
    [user],
  );

  const value = useMemo(
    () => ({ user, loading, login, logout, hasRole }),
    [user, loading, login, logout, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
