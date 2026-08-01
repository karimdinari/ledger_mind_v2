import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell, PageHeader } from "@/components/lm/AppShell";
import { isAuthed } from "@/lib/auth";
import {
  deleteEducationConversation,
  deleteOrchestratorSession,
  fetchEducationConversations,
  fetchMySessions,
  type EducationConversationSummary,
} from "@/lib/api";

export const Route = createFileRoute("/historique")({
  head: () => ({
    meta: [
      { title: "Historique — LedgerMind" },
      {
        name: "description",
        content: "Sessions guidance/intake et conversations pédagogiques.",
      },
      { property: "og:title", content: "Historique — LedgerMind" },
    ],
  }),
  component: HistoriquePage,
});

type SessionRow = {
  session_id: string;
  branch: string | null;
  phase: string | null;
  updated_at: string;
  title?: string | null;
};

function HistoriquePage() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [conversations, setConversations] = useState<EducationConversationSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [s, c] = await Promise.all([
        fetchMySessions(),
        fetchEducationConversations(),
      ]);
      setSessions(s);
      setConversations(c);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chargement impossible");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!isAuthed()) {
      navigate({ to: "/auth", replace: true });
      return;
    }
    load();
  }, [navigate]);

  async function removeSession(id: string) {
    await deleteOrchestratorSession(id);
    await load();
  }

  async function removeConversation(id: string) {
    await deleteEducationConversation(id);
    await load();
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Historique"
        title={
          <>
            Vos parcours, <span className="italic font-normal">conservés.</span>
          </>
        }
        description="Sessions d'onboarding / guidance et conversations de l'assistant fiscal."
      />

      {error && (
        <div className="mb-6 bg-coral/10 border border-coral/30 rounded-2xl p-4 text-sm text-coral">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-ink/40 font-mono text-sm">Chargement…</p>
      ) : (
        <div className="grid lg:grid-cols-2 gap-8">
          <section className="bg-white border border-border rounded-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-border">
              <h2 className="font-semibold">Guidance & intake</h2>
              <p className="text-xs text-ink/40 mt-1">Sessions orchestrateur</p>
            </div>
            {sessions.length === 0 ? (
              <p className="p-6 text-sm text-ink/45">Aucune session pour l’instant.</p>
            ) : (
              <ul className="divide-y divide-border">
                {sessions.map((s) => (
                  <li key={s.session_id} className="px-6 py-4 flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="font-medium truncate">
                        {s.title ||
                          (s.branch === "guidance" ? "Diagnostic sans SIREN" : "Profil SIREN")}
                      </p>
                      <p className="text-xs text-ink/40 font-mono mt-1">
                        {s.branch || "—"} · {s.phase || "—"} ·{" "}
                        {s.updated_at ? new Date(s.updated_at).toLocaleString("fr-FR") : ""}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {s.branch === "guidance" && (
                          <Link
                            to="/onboarding/diagnostic/resultat"
                            search={{ session: s.session_id }}
                            className="text-xs text-teal-dark hover:underline"
                          >
                            Voir la feuille de route
                          </Link>
                        )}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeSession(s.session_id)}
                      className="text-xs text-coral shrink-0"
                    >
                      Supprimer
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="bg-white border border-border rounded-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-border flex items-center justify-between">
              <div>
                <h2 className="font-semibold">Assistant fiscal</h2>
                <p className="text-xs text-ink/40 mt-1">Conversations pédagogiques</p>
              </div>
              <Link to="/education" className="text-xs text-teal-dark hover:underline">
                Ouvrir
              </Link>
            </div>
            {conversations.length === 0 ? (
              <p className="p-6 text-sm text-ink/45">Aucune conversation sauvegardée.</p>
            ) : (
              <ul className="divide-y divide-border">
                {conversations.map((c) => (
                  <li key={c.id} className="px-6 py-4 flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <Link
                        to="/education"
                        className="font-medium hover:text-teal-dark line-clamp-2"
                      >
                        {c.title}
                      </Link>
                      <p className="text-xs text-ink/40 font-mono mt-1">
                        {c.updated_at
                          ? new Date(c.updated_at).toLocaleString("fr-FR")
                          : ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeConversation(c.id)}
                      className="text-xs text-coral shrink-0"
                    >
                      Supprimer
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </AppShell>
  );
}
