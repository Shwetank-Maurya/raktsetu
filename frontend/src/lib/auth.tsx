import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { onIdTokenChanged, signInWithEmailAndPassword, signInWithPopup, GoogleAuthProvider, signOut } from "firebase/auth";
import { api, getStoredToken, setTokenProvider, storeToken } from "../api/client";
import { auth } from "./firebase";

export type User = { uid: string; role: string; name: string; facility_id: number | null; region_id: number | null; auth: string };
type Ctx = {
  user: User | null;
  loading: boolean;
  demoLogin: (who: string) => Promise<void>;
  emailLogin: (email: string, pw: string) => Promise<void>;
  googleLogin: () => Promise<void>;
  logout: () => Promise<void>;
};
const AuthCtx = createContext<Ctx>(null as unknown as Ctx);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = async () => {
    try {
      setUser(await api.get<User>("/api/auth/me"));
    } catch {
      storeToken(null);
      setUser(null);
    }
  };

  useEffect(() => {
    if (getStoredToken()) loadMe().finally(() => setLoading(false));
    else setLoading(false);
    if (!auth) return;
    // Firebase ID tokens refresh hourly; the provider always hands the API a fresh one.
    return onIdTokenChanged(auth, async (fbUser) => {
      if (fbUser) {
        setTokenProvider(() => fbUser.getIdToken());
        await loadMe();
      } else if (!getStoredToken()) {
        setTokenProvider(null);
        setUser(null);
      }
      setLoading(false);
    });
  }, []);

  const value: Ctx = {
    user,
    loading,
    demoLogin: async (who) => {
      const r = await api.read<{ token: string; user: User }>("/api/auth/demo-login", { user: who });
      setTokenProvider(null);
      storeToken(r.token);
      setUser(r.user);
    },
    emailLogin: async (email, pw) => {
      if (!auth) throw new Error("Firebase Auth is not configured");
      storeToken(null);
      await signInWithEmailAndPassword(auth, email, pw);
    },
    googleLogin: async () => {
      if (!auth) throw new Error("Firebase Auth is not configured");
      storeToken(null);
      await signInWithPopup(auth, new GoogleAuthProvider());
    },
    logout: async () => {
      storeToken(null);
      setTokenProvider(null);
      if (auth) await signOut(auth);
      setUser(null);
    },
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}
