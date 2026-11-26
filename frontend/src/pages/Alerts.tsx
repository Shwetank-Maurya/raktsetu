import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { endpoints } from "../api/endpoints";

import { Button, Card, ErrorBox, SevBadge, Spinner } from "../components/ui";
import { ist } from "../lib/format";
import { useAuth } from "../lib/auth-context";
import { enablePush, firebaseEnabled } from "../lib/firebase";
import { useI18n } from "../lib/i18n-context";
import { POLL_MS } from "../lib/live";

export default function Alerts() {
  const { t } = useI18n();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [status, setStatus] = useState("open,ack");
  const [push, setPush] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["alerts", status], queryFn: () => endpoints.alerts({ status, limit: 200 }), refetchInterval: POLL_MS });
  const ack = useMutation({ mutationFn: endpoints.ackAlert, onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }) });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><h1>{t("alerts")}</h1>
          <p className="text-sm text-muted">Tiers: info, warning, high, critical (only high and critical push). Deduplicated by facility + group + component + kind, 6 h cooldown, critical escalates to the coordinator after 30 min unacknowledged, auto-resolves after two calm cycles.</p></div>
        <div className="flex items-center gap-2">
          {firebaseEnabled && <Button variant="secondary" onClick={async () => setPush(await enablePush(user?.region_id ?? null))}>Enable push (FCM)</Button>}
          <select aria-label="Status filter" value={status} onChange={(e) => setStatus(e.target.value)} className="h-9 rounded-lg border border-line bg-white px-2.5 text-sm">
            <option value="open,ack">Active</option><option value="open">Unacknowledged</option><option value="resolved">Resolved</option>
          </select>
        </div>
      </div>
      {push && <div className="rounded bg-subtle p-2 text-sm">{push}</div>}
      <ErrorBox error={ack.error} />
      {q.isLoading ? <Spinner /> : (
        <Card>
          <ul className="divide-y divide-line-soft">
            {(q.data ?? []).map((a) => (
              <li key={a.id} className="flex flex-wrap items-start justify-between gap-2 py-3">
                <div className="flex min-w-0 flex-1 items-start gap-2">
                  <SevBadge sev={a.severity} />
                  <div className="min-w-0">
                    <div className="text-sm">{a.message}</div>
                    <div className="text-xs text-muted">{a.kind.replace("_", " ")} · first seen {ist(a.first_seen)} · last {ist(a.last_seen)}
                      {a.escalated_at && <span className="ml-1 font-semibold text-[#a34000]">escalated</span>}
                      {a.acknowledged_by && <span className="ml-1">· ack by {a.acknowledged_by}</span>}</div>
                  </div>
                </div>
                {a.status === "open" && <Button variant="secondary" onClick={() => ack.mutate(a.id)} disabled={ack.isPending}>Acknowledge</Button>}
              </li>
            ))}
            {q.data?.length === 0 && <li className="py-4 text-center text-sm text-muted">No alerts.</li>}
          </ul>
        </Card>
      )}
    </div>
  );
}
