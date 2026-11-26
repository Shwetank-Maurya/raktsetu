// Auth context, hook and demo account list (the provider component lives in ./auth.tsx).
import { createContext, useContext } from "react";

export type User = { uid: string; role: string; name: string; facility_id: number | null; region_id: number | null; auth: string };
export type AuthValue = {
  user: User | null;
  loading: boolean;
  emailLogin: (email: string, pw: string) => Promise<void>;
  googleLogin: () => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  signup: (name: string, email: string, pw: string) => Promise<void>;
  /** Re-reads role claims (after an access request is approved). Returns the new role. */
  refreshAccess: () => Promise<string | null>;
  demoLogin: (who: string) => Promise<void>;
  logout: () => Promise<void>;
};
export const AuthCtx = createContext<AuthValue>(null as unknown as AuthValue);
export const useAuth = () => useContext(AuthCtx);

export const DEMO_ACCOUNTS = [
  { who: "coordinator", email: "coordinator@raktsetu.demo", label: "Regional coordinator" },
  { who: "bank", email: "bank@raktsetu.demo", label: "Blood bank manager" },
  { who: "hospital", email: "hospital@raktsetu.demo", label: "Hospital officer" },
] as const;
