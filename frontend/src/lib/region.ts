import { useQuery } from "@tanstack/react-query";
import { endpoints } from "../api/endpoints";

/** Centre of the top-level region from the DB (regions table); undefined until loaded. */
export function useNetworkCenter(): [number, number] | undefined {
  const q = useQuery({ queryKey: ["regions"], queryFn: endpoints.regions, staleTime: 3_600_000 });
  const state = (q.data ?? []).find((r) => r.level === "state" && r.lat != null && r.lng != null);
  return state?.lat != null && state.lng != null ? [state.lat, state.lng] : undefined;
}
