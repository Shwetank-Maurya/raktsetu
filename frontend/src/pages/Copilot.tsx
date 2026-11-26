import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bot, Send } from "lucide-react";
import { api } from "../api/client";
import { Button, Card, ErrorBox } from "../components/ui";
import { track } from "../lib/firebase";
import { useI18n } from "../lib/i18n";

type Msg = { role: "user" | "model"; text: string; meta?: any };
const SUGGEST = {
  en: ["Which blood group is most at risk in the next 48 hours?", "Find O- red cells near Arogya Multispeciality", "Show open alerts", "What transfers are pending?"],
  hi: ["अगले 48 घंटों में किस रक्त समूह को सबसे अधिक खतरा है?", "O- रेड सेल कहाँ उपलब्ध हैं?", "खुले अलर्ट दिखाओ", "कौन से ट्रांसफर लंबित हैं?"],
};

export default function Copilot() {
  const { t, lang } = useI18n();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const chat = useMutation({
    mutationFn: (text: string) => api.read("/api/copilot/chat", { message: text, language: lang, history: msgs.slice(-8).map((m) => ({ role: m.role, text: m.text })) }),
    onSuccess: (d) => { setMsgs((m) => [...m, { role: "model", text: d.answer, meta: d }]); track("copilot", { fallback: d.fallback }); },
  });
  const send = (text: string) => {
    if (!text.trim()) return;
    setMsgs((m) => [...m, { role: "user", text }]);
    setInput("");
    chat.mutate(text);
  };
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div><h1 className="text-xl font-bold">{t("copilot")}</h1>
        <p className="text-sm text-slate-500">Gemini answers only from read-only tool data. Every number is checked against the tool results; if a number cannot be verified, a template answer is shown instead.</p></div>
      <Card>
        <div className="max-h-[55vh] min-h-[300px] space-y-3 overflow-y-auto" aria-live="polite">
          {msgs.length === 0 && (
            <div className="flex flex-wrap gap-2">{SUGGEST[lang].map((s) => <button key={s} onClick={() => send(s)} className="rounded-full border border-slate-300 px-3 py-1 text-xs hover:bg-slate-50">{s}</button>)}</div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={m.role === "user" ? "text-right" : ""}>
              <div className={`inline-block max-w-[90%] whitespace-pre-wrap rounded-xl px-3 py-2 text-left text-sm ${m.role === "user" ? "bg-rose-700 text-white" : "bg-slate-100"}`}>
                {m.role === "model" && <Bot size={14} className="mb-1 inline text-rose-700" />} {m.text}
              </div>
              {m.meta && (
                <div className="mt-1 text-[11px] text-slate-500">
                  {m.meta.fallback ? "template answer (Gemini off / unverified)" : "Gemini, numbers verified"} · tools: {m.meta.tools_used.join(", ")}
                  <details className="inline"><summary className="ml-1 inline cursor-pointer underline">sources</summary>
                    <pre className="mt-1 max-h-48 overflow-auto rounded bg-slate-900 p-2 text-left text-[10px] text-slate-100">{JSON.stringify(m.meta.tool_payloads, null, 1)}</pre></details>
                </div>
              )}
            </div>
          ))}
          {chat.isPending && <div className="text-sm text-slate-500">Thinking with tools...</div>}
        </div>
        <ErrorBox error={chat.error} />
        <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); send(input); }}>
          <input aria-label="Ask the copilot" value={input} onChange={(e) => setInput(e.target.value)} maxLength={1000}
            placeholder={lang === "hi" ? "हिंदी या अंग्रेज़ी में पूछें..." : "Ask in English or Hindi..."} className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <Button type="submit" disabled={chat.isPending}><Send size={14} /> Send</Button>
        </form>
      </Card>
    </div>
  );
}
