import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserCheck } from "lucide-react";
import { api } from "../api/client";
import { Button, Card, EmptyState, ErrorBox, PageHeader, Spinner, Tabs } from "../components/ui";
import { ist } from "../lib/format";

const ROLE: Record<string, string> = { hospital_user: "Hospital staff", bank_manager: "Blood bank staff" };

export default function AccessRequests() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("pending");
  const q = useQuery({ queryKey: ["access-requests", status], queryFn: () => api.get(`/api/access-requests?status=${status}`) });
  const act = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "approve" | "reject" }) => api.post(`/api/access-requests/${id}/${action}`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["access-requests"] }),
  });
  return (
    <div>
      <PageHeader title="Access requests" description="People who signed up and asked to join a facility in your region. Approving grants their role on sign-in."
        actions={<Tabs value={status} onChange={setStatus} options={[["pending", "Pending"], ["approved", "Approved"], ["rejected", "Declined"]]} />} />
      <ErrorBox error={act.error} />
      {q.isLoading ? <Spinner /> : (q.data ?? []).length === 0 ? (
        <EmptyState title={status === "pending" ? "No pending requests" : "Nothing here yet"} icon={UserCheck}>New sign-ups appear here for approval.</EmptyState>
      ) : (
        <Card padded={false}>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line"><th className="px-5 py-2.5">Person</th><th>Requested</th><th>Facility</th><th>Requested at</th><th className="pr-5" /></tr></thead>
            <tbody>
              {(q.data ?? []).map((r: any) => (
                <tr key={r.id} className="border-b border-line-soft last:border-0">
                  <td className="px-5 py-3"><div className="font-medium text-ink">{r.name}</div>{r.note && <div className="text-xs text-muted">{r.note}</div>}</td>
                  <td className="text-body">{ROLE[r.requested_role] ?? r.requested_role}</td>
                  <td><div className="text-ink">{r.facility_name}</div><div className="text-xs text-muted">{r.facility_code}</div></td>
                  <td className="text-xs text-muted">{ist(r.created_at)}</td>
                  <td className="pr-5 text-right">
                    {r.status === "pending" ? (
                      <div className="flex justify-end gap-2">
                        <Button size="sm" variant="secondary" disabled={act.isPending} onClick={() => act.mutate({ id: r.id, action: "reject" })}>Decline</Button>
                        <Button size="sm" disabled={act.isPending} onClick={() => act.mutate({ id: r.id, action: "approve" })}>Approve</Button>
                      </div>
                    ) : <span className="text-xs capitalize text-muted">{r.status}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
