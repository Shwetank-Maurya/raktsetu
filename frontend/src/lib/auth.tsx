// Authentication: Firebase Auth (email/password, optional Google) is the primary path. The ID token
// is sent to the API, which verifies it and reads the role custom claims (role, facility_id,
// region_id). If Firebase is not configured, the legacy signed demo tokens keep the app usable.
import { useEffect, useState, type ReactNode } from "react";
import {
  createUserWithEmailAndPassword, GoogleAuthProvider, onIdTokenChanged, sendEmailVerification, sendPasswordResetEmail,
  signInWithEmailAndPassword, signInWithPopup, signOut, updateProfile,
} from "firebase/auth";
import { api, getStoredToken, setTokenProvider, storeToken } from "../api/client";
import { AuthCtx, DEMO_ACCOUNTS, type AuthValue, type User } from "./auth-context";
import { auth, firebaseEnabled } from "./firebase";

const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD as string | undefined;

function friendly(e: unknown): Error {
  const code = (e as { code?: string })?.code ?? "";
  const map: Record<string, string> = {
    "auth/invalid-credential": "Email or password is incorrect.",
    "auth/wrong-password": "Email or password is incorrect.",
    "auth/user-not-found": "Email or password is incorrect.",
    "auth/invalid-email": "Enter a valid email address.",
    "auth/user-disabled": "This account has been disabled.",
    "auth/too-many-requests": "Too many attempts. Try again in a few minutes.",
    "auth/popup-closed-by-user": "Sign-in window was closed.",
    "auth/operation-not-allowed": "This sign-in method is not enabled for the project.",
    "auth/network-request-failed": "Network error. Check your connection.",
    "auth/email-already-in-use": "An account with this email already exists. Sign in instead.",
    "auth/weak-password": "Use at least 8 characters for your password.",
  };
  return new Error(map[code] ?? (e as Error)?.message ?? "Sign-in failed");
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(() => firebaseEnabled || Boolean(getStoredToken()));

  const loadMe = async () => {
    try {
      const me = await api.get<User>("/api/auth/me");
      setUser(me);
    } catch {
      setUser(null);
    }
  };

  useEffect(() => {
    if (!firebaseEnabled || !auth) {
      // Legacy demo token (no Firebase): resolve the session; state updates happen in promise callbacks.
      if (getStoredToken()) {
        api.get<User>("/api/auth/me").then(setUser, () => setUser(null)).finally(() => setLoading(false));
      }
      return;
    }
    // Firebase refreshes ID tokens hourly; the provider always hands the API a fresh one.
    return onIdTokenChanged(auth, async (fbUser) => {
      if (fbUser) {
        storeToken(null);
        setTokenProvider(() => fbUser.getIdToken());
        await loadMe();
      } else {
        setTokenProvider(null);
        setUser(null);
      }
      setLoading(false);
    });
  }, []);

  const value: AuthValue = {
    user,
    loading,
    emailLogin: async (email, pw) => {
      if (!auth) throw new Error("Firebase Authentication is not configured.");
      try { await signInWithEmailAndPassword(auth, email.trim(), pw); } catch (e) { throw friendly(e); }
    },
    googleLogin: async () => {
      if (!auth) throw new Error("Firebase Authentication is not configured.");
      try { await signInWithPopup(auth, new GoogleAuthProvider()); } catch (e) { throw friendly(e); }
    },
    resetPassword: async (email) => {
      if (!auth) throw new Error("Firebase Authentication is not configured.");
      try { await sendPasswordResetEmail(auth, email.trim()); } catch (e) { throw friendly(e); }
    },
    signup: async (name, email, pw) => {
      if (!auth) throw new Error("Firebase Authentication is not configured.");
      if (name.trim().length < 2) throw new Error("Enter your full name.");
      if (pw.length < 8) throw new Error("Use at least 8 characters for your password.");
      try {
        const cred = await createUserWithEmailAndPassword(auth, email.trim(), pw);
        await updateProfile(cred.user, { displayName: name.trim() });
        sendEmailVerification(cred.user).catch(() => undefined); // best effort
        // Do not wait for the observer to run: the next API request must use this new
        // Firebase account, which the API deliberately maps to the pending role.
        setTokenProvider(() => cred.user.getIdToken());
        await cred.user.getIdToken(true); // include the display name in the token
        await loadMe();
      } catch (e) { throw friendly(e); }
    },
    refreshAccess: async () => {
      if (auth?.currentUser) await auth.currentUser.getIdToken(true);
      try {
        const me = await api.get<User>("/api/auth/me");
        setUser(me);
        return me.role;
      } catch { return null; }
    },
    demoLogin: async (who) => {
      const acct = DEMO_ACCOUNTS.find((a) => a.who === who);
      if (auth && acct && DEMO_PASSWORD) {
        try { await signInWithEmailAndPassword(auth, acct.email, DEMO_PASSWORD); } catch (e) { throw friendly(e); }
        return;
      }
      // No Firebase: signed demo token from the API (local development only).
      const r = await api.read<{ token: string; user: User }>("/api/auth/demo-login", { user: who });
      setTokenProvider(null);
      storeToken(r.token);
      setUser(r.user);
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
