// Real-time: listen to Firestore change pings written by the backend and refetch affected queries.
// Without Firebase, TanStack Query polling (refetchInterval) keeps screens fresh instead.
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { collection, onSnapshot } from "firebase/firestore";
import { db } from "./firebase";

// Firestore makes updates instant; slow polling stays on as a safety net if the listener is denied.
export const POLL_MS = db ? 60_000 : 20_000;

export function useLiveFeed(): { live: boolean; lastEvent: string | null } {
  const qc = useQueryClient();
  const [lastEvent, setLast] = useState<string | null>(null);
  useEffect(() => {
    if (!db) return;
    const unsub = onSnapshot(
      collection(db, "events"),
      (snap) => {
        snap.docChanges().forEach((ch) => {
          const kind = ch.doc.id;
          setLast(`${kind} @ ${new Date().toLocaleTimeString("en-IN")}`);
          if (kind === "stock" || kind === "cycle") {
            qc.invalidateQueries({ queryKey: ["matrix"] });
            qc.invalidateQueries({ queryKey: ["kpis"] });
            qc.invalidateQueries({ queryKey: ["risk"] });
            qc.invalidateQueries({ queryKey: ["map"] });
            qc.invalidateQueries({ queryKey: ["expiring"] });
          }
          if (kind === "transfers" || kind === "cycle") qc.invalidateQueries({ queryKey: ["transfers"] });
        });
      },
      () => setLast("live feed unavailable - polling"),
    );
    const unsubAlerts = onSnapshot(collection(db, "alerts"), () => qc.invalidateQueries({ queryKey: ["alerts"] }), () => {});
    return () => {
      unsub();
      unsubAlerts();
    };
  }, [qc]);
  return { live: Boolean(db), lastEvent };
}
