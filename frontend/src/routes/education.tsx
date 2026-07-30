import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { AppShell, PageHeader } from "@/components/lm/AppShell";
import { isAuthed } from "@/lib/auth";
import {
  askEducationQuestion,
  deleteEducationConversation,
  fetchEducationConversation,
  fetchEducationConversations,
  fetchEducationRagStatus,
  type EducationAskResult,
  type EducationConversationSummary,
  type EducationSource,
} from "@/lib/api";

export const Route = createFileRoute("/education")({
  head: () => ({
    meta: [
      { title: "Éducation fiscale — LedgerMind" },
      {
        name: "description",
        content: "Posez vos questions fiscales, réponses sourcées et alignées sur votre diagnostic.",
      },
      { property: "og:title", content: "Éducation fiscale — LedgerMind" },
    ],
  }),
  component: EducationPage,
});

const SUGGESTIONS = [
  { tag: "Cadeaux", q: "Les cadeaux reçus comptent-ils dans mon CA micro ?" },
  { tag: "Statut", q: "Micro-BNC ou micro-BIC : comment choisir ?" },
  { tag: "TVA", q: "Quand dois-je facturer la TVA ?" },
  { tag: "Début", q: "Que déclarer si je débute cette année ?" },
];

type Turn = { question: string; result: EducationAskResult };

function EducationPage() {
  const navigate = useNavigate();
  const bottomRef = useRef<HTMLDivElement>(null);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<Turn[]>([]);
  const [corpusChunks, setCorpusChunks] = useState<number | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<EducationConversationSummary[]>([]);
  const [regimeHint, setRegimeHint] = useState<string | null>(null);

  async function refreshConversations() {
    try {
      setConversations(await fetchEducationConversations());
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    if (!isAuthed()) {
      navigate({ to: "/auth", replace: true });
      return;
    }
    fetchEducationRagStatus()
      .then((s) => setCorpusChunks(s.corpus_chunks))
      .catch(() => {});
    refreshConversations();
  }, [navigate]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [history, loading]);

  async function loadConversation(id: string) {
    setError(null);
    try {
      const row = await fetchEducationConversation(id);
      setConversationId(row.id);
      const turns: Turn[] = [];
      const msgs = row.messages || [];
      for (let i = 0; i < msgs.length; i++) {
        if (msgs[i].role === "user") {
          const asst = msgs[i + 1]?.role === "assistant" ? msgs[i + 1] : null;
          turns.push({
            question: msgs[i].content,
            result: {
              answer: asst?.content || "",
              sources: (asst?.sources as EducationSource[]) || [],
              freshness_warning: false,
              corpus_empty: false,
              bofip_live_used: false,
              conversation_id: row.id,
            },
          });
        }
      }
      setHistory(turns);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Impossible de charger la conversation");
    }
  }

  async function submit(q: string) {
    const trimmed = q.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    setError(null);
    try {
      const historique = history.flatMap((t) => [
        { role: "user", content: t.question },
        { role: "assistant", content: t.result.answer },
      ]);
      const result = await askEducationQuestion(trimmed, historique, {
        conversationId,
      });
      if (result.conversation_id) setConversationId(result.conversation_id);
      if (result.regime_verdict) setRegimeHint(result.regime_verdict);
      setHistory((prev) => [...prev, { question: trimmed, result }]);
      setQuestion("");
      await refreshConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors de la question.");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    submit(question);
  }

  function newConversation() {
    setHistory([]);
    setConversationId(null);
    setError(null);
    setRegimeHint(null);
  }

  async function removeConversation(id: string) {
    try {
      await deleteEducationConversation(id);
      if (conversationId === id) newConversation();
      await refreshConversations();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Suppression impossible");
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Éducation"
        title={
          <>
            Posez vos questions, <span className="italic font-normal">réponses sourcées.</span>
          </>
        }
        description="Assistant pédagogique fiscal (RAG). Si vous avez un diagnostic guidance, les réponses s'alignent sur le verdict déterministe de régime."
      />

      {corpusChunks === 0 && (
        <div className="mb-8 bg-amber-fiscal/10 border border-amber-fiscal/30 rounded-2xl p-6 text-sm text-amber-fiscal font-medium">
          Le corpus documentaire est vide. Lancez{" "}
          <code className="font-mono text-xs bg-background/60 px-1.5 py-0.5 rounded">
            python -m scripts.seed_pedagogue_corpus
          </code>{" "}
          depuis le dossier backend, puis rechargez cette page.
        </div>
      )}

      {regimeHint && (
        <div className="mb-6 text-xs font-mono uppercase tracking-widest text-teal-dark">
          Aligné sur votre verdict guidance : {regimeHint}
        </div>
      )}

      <div className="grid lg:grid-cols-12 gap-10 items-start">
        <aside className="lg:col-span-3 space-y-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-mono text-[11px] uppercase tracking-[0.25em] text-teal-dark">
              Historique
            </h3>
            <button
              type="button"
              onClick={newConversation}
              className="text-[11px] font-mono uppercase tracking-widest text-ink/40 hover:text-ink"
            >
              Nouveau
            </button>
          </div>
          <ul className="space-y-2 max-h-96 overflow-y-auto">
            {conversations.length === 0 && (
              <li className="text-sm text-ink/40">Aucune conversation sauvegardée</li>
            )}
            {conversations.map((c) => (
              <li key={c.id} className="group flex items-start gap-2">
                <button
                  type="button"
                  onClick={() => loadConversation(c.id)}
                  className={`flex-1 text-left text-sm px-3 py-2 rounded-xl border transition-colors ${
                    conversationId === c.id
                      ? "border-teal-dark bg-teal-dark/5"
                      : "border-border hover:border-ink"
                  }`}
                >
                  <span className="line-clamp-2 font-medium">{c.title}</span>
                </button>
                <button
                  type="button"
                  onClick={() => removeConversation(c.id)}
                  className="opacity-0 group-hover:opacity-100 text-xs text-coral px-1"
                  aria-label="Supprimer"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <div className="lg:col-span-6 space-y-6">
          <section className="bg-white border border-border rounded-2xl overflow-hidden animate-slide-up">
            <div className="px-8 py-5 border-b border-border flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Conversation</h2>
                <p className="text-xs text-ink/40 mt-0.5">
                  {history.length === 0
                    ? "Aucune question pour l’instant"
                    : `${history.length} échange${history.length > 1 ? "s" : ""}`}
                </p>
              </div>
            </div>

            <div className="px-8 py-8 min-h-80 max-h-112 overflow-y-auto space-y-8">
              {history.length === 0 && !loading ? (
                <EmptyState onPick={submit} disabled={loading} />
              ) : (
                history.map((turn, idx) => (
                  <TurnBlock key={idx} index={idx + 1} turn={turn} />
                ))
              )}

              {loading && (
                <div className="flex items-center gap-4 text-ink/50">
                  <div className="inline-block size-6 border-[3px] border-ink/20 border-t-teal-dark rounded-full animate-spin shrink-0" />
                  <p className="text-sm">Recherche dans le corpus et rédaction de la réponse…</p>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </section>

          {error && (
            <div className="bg-coral/10 border border-coral/30 rounded-2xl p-6 text-sm text-coral font-medium">
              {error}
            </div>
          )}

            {history.length > 0 && !loading && (
              <div className="flex flex-wrap gap-2 px-8 pb-4">
                {[
                  "Je n'ai pas compris, peux-tu reformuler ?",
                  "Peux-tu donner un exemple concret ?",
                  "Peux-tu expliquer plus simplement ?",
                ].map((label) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => submit(label)}
                    className="rounded-full border border-border px-3 py-1.5 text-xs text-ink/60 hover:border-ink hover:text-ink transition-colors"
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}

          <form
            onSubmit={handleSubmit}
            className="bg-white border border-border rounded-2xl p-8 space-y-5"
          >
            <div>
              <label className="text-xs uppercase tracking-widest text-ink/50 font-semibold">
                Votre question
              </label>
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ex. Les cadeaux reçus comptent-ils dans mon CA ?"
                className="w-full mt-2 px-0 py-3 bg-transparent border-b border-border text-lg focus:outline-none focus:border-ink transition-colors"
                disabled={loading}
              />
            </div>
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="px-8 py-4 bg-ink text-background rounded-xl font-semibold hover:bg-teal-dark transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? "Recherche en cours…" : "Poser la question"}
            </button>
          </form>
        </div>

        <aside className="lg:col-span-3 lg:sticky lg:top-24 space-y-6">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.25em] text-teal-dark">
            Suggestions
          </h3>
          <div className="space-y-3">
            {SUGGESTIONS.map((s) => (
              <button
                key={s.q}
                type="button"
                onClick={() => submit(s.q)}
                disabled={loading}
                className="w-full text-left bg-white border border-border rounded-2xl p-5 hover:border-ink transition-colors disabled:opacity-50 group"
              >
                <p className="font-mono text-[10px] uppercase tracking-widest text-teal-dark mb-2">
                  {s.tag}
                </p>
                <p className="text-sm font-medium leading-snug group-hover:text-teal-dark transition-colors">
                  {s.q}
                </p>
              </button>
            ))}
          </div>

          <div className="bg-white border border-border rounded-2xl p-6 space-y-3">
            <p className="font-mono text-[10px] uppercase tracking-widest text-ink/40">Corpus</p>
            {corpusChunks == null ? (
              <p className="text-sm text-ink/40">Chargement…</p>
            ) : corpusChunks > 0 ? (
              <>
                <p className="text-2xl font-extrabold tracking-tighter text-teal-dark">
                  {corpusChunks}
                </p>
                <p className="text-sm text-ink/50">extraits indexés · sources officielles</p>
              </>
            ) : (
              <p className="text-sm text-amber-fiscal">Aucun extrait indexé</p>
            )}
          </div>
        </aside>
      </div>
    </AppShell>
  );
}

function EmptyState({
  onPick,
  disabled,
}: {
  onPick: (q: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="text-center py-6 space-y-6">
      <div className="mx-auto size-14 rounded-full bg-teal-dark/10 grid place-items-center">
        <span className="text-teal-dark text-xl font-semibold">?</span>
      </div>
      <div>
        <p className="font-semibold text-lg">Par où commencer ?</p>
        <p className="text-sm text-ink/50 mt-2 max-w-sm mx-auto leading-relaxed">
          Choisissez une suggestion, ou tapez votre question ci-dessous.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {SUGGESTIONS.slice(0, 2).map((s) => (
          <button
            key={s.q}
            type="button"
            disabled={disabled}
            onClick={() => onPick(s.q)}
            className="px-4 py-2 text-xs border border-border rounded-full hover:border-ink transition-colors disabled:opacity-50"
          >
            {s.tag}
          </button>
        ))}
      </div>
    </div>
  );
}

function TurnBlock({ index, turn }: { index: number; turn: Turn }) {
  return (
    <article className="space-y-4 animate-slide-up">
      <div className="flex gap-4 items-start">
        <div className="shrink-0 size-9 rounded-full bg-background border border-border font-mono grid place-items-center text-xs font-medium text-ink/50">
          {String(index).padStart(2, "0")}
        </div>
        <div className="min-w-0 pt-1.5">
          <p className="font-semibold leading-snug">{turn.question}</p>
        </div>
      </div>
      <div className="pl-13 space-y-4">
        <p className="text-sm text-ink/80 leading-relaxed whitespace-pre-wrap text-pretty">
          {turn.result.answer}
        </p>
        {turn.result.freshness_warning && (
          <p className="text-xs text-amber-fiscal font-medium">
            Certaines sources peuvent être périmées — vérifiez la date de publication.
          </p>
        )}
        {turn.result.sources.length > 0 && <SourceList sources={turn.result.sources} />}
        {turn.result.bofip_live_used && (
          <p className="text-[10px] font-mono uppercase tracking-widest text-ink/30">
            Complété via BOFiP (live)
          </p>
        )}
      </div>
    </article>
  );
}

function SourceList({ sources }: { sources: EducationSource[] }) {
  return (
    <div className="space-y-2">
      <p className="text-[10px] font-mono uppercase tracking-widest text-ink/40">Sources</p>
      <ul className="flex flex-wrap gap-2">
        {sources.map((s, i) => {
          const label = [s.source, s.titre].filter(Boolean).join(" — ");
          const inner = (
            <span className="inline-flex items-center px-3 py-1.5 bg-background border border-border rounded-full text-xs text-ink/60 hover:border-teal-dark hover:text-teal-dark transition-colors max-w-full truncate">
              {label || "Source"}
            </span>
          );
          return (
            <li key={`${s.url}-${i}`} className="max-w-full">
              {s.url ? (
                <a href={s.url} target="_blank" rel="noreferrer">
                  {inner}
                </a>
              ) : (
                inner
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
