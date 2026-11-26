import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

/** Centre of the top-level region from the DB (regions table); undefined until loaded. */
export function useNetworkCenter(): [number, number] | undefined {
  const q = useQuery({ queryKey: ["regions"], queryFn: () => api.get("/api/regions"), staleTime: 3_600_000 });
  const state = (q.data ?? []).find((r: any) => r.level === "state" && r.lat != null);
  return state ? [state.lat, state.lng] : undefined;
}
