import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { LogoutBubble } from "@/components/lm/AppShell";
import {
  cacheDiagnosticResult,
  chooseParcours,
  downloadSessionRoadmapPdf,
  fetchSessionDetail,
  getStoredSessionId,
  loadCachedDiagnosticResult,
  patchDiagnosticProfile,
  saveRoadmapChecked,
  type DiagnosticProfile,
  type SessionDetail,
  type UserProfile,
} from "@/lib/api";

export const Route = createFileRoute("/onboarding/diagnostic/resultat")({
  validateSearch: (search: Record<string, unknown>): { session?: string } => ({
    session: typeof search.session === "string" ? search.session : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Votre diagnostic — LedgerMind" },
      {
        name: "description",
        content: "Feuille de route déterministe, checklist interactive et export PDF.",
      },
      { property: "og:title", content: "Votre diagnostic — LedgerMind" },
    ],
  }),
  component: ResultatPage,
});

type RoadmapEtape = {
  id?: string;
  titre?: string;
  detail?: string;
  lien?: string;
  obligatoire?: boolean;
  duree?: string;
  cout?: string;
  phase?: string;
  parcours?: string;
};

type RoadmapPhase = {
  id?: string;
  titre?: string;
  etapes?: RoadmapEtape[];
};

type RoadmapBandeau = {
  titre?: string;
  texte?: string;
  type?: string;
};

type RoadmapSeuil = {
  label?: string;
  position?: number;
  seuil?: number;
};

const PHASE_LABELS: Record<string, string> = {
  preparer: "Préparer",
  creer: "Créer",
  faire_vivre: "Faire vivre",
};

const DURABILITE_LABELS: Record<string, string> = {
  eligible_stable: "Éligibilité stable",
  depassement_ponctuel: "Dépassement ponctuel",
  depassement_durable: "Dépassement durable",
  indetermine: "À confirmer",
};

function formatCa(n: number | null | undefined): string {
  if (n == null) return "Non renseigné";
  return `≈ ${Math.round(n).toLocaleString("fr-FR")} € / an`;
}

function situationFrom(
  diag: DiagnosticProfile | null,
  profile: UserProfile,
): { activite: string; revenus: string; anciennete: string; sources: string[] } {
  const sources: string[] = [];
  if (diag?.vend_produits) sources.push("Vente de produits");
  if (diag?.recoit_cadeaux) sources.push("Cadeaux / dotations");
  if (diag?.activite) sources.push(diag.activite);
  const activityTypes = profile.activity_types ?? [];
  if (sources.length === 0 && activityTypes.length) sources.push(...activityTypes);
  return {
    activite: diag?.activite || activityTypes[0] || "Activité créative / freelance",
    revenus: formatCa(diag?.ca_estime_annuel) || profile.estimated_annual_revenue || "Non renseigné",
    anciennete: diag?.anciennete || "Non renseignée",
    sources: sources.length ? sources : ["À préciser"],
  };
}

function ResultatPage() {
  const { session: sessionFromUrl } = Route.useSearch();
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [editCa, setEditCa] = useState("");
  const [editActivite, setEditActivite] = useState("");

  useEffect(() => {
    const cached = loadCachedDiagnosticResult();
    if (cached?.roadmap || (cached?.profile.recommended_actions?.length ?? 0) > 0) {
      setDetail(cached);
      setChecked(cached.roadmap_checked ?? {});
      setEditCa(
        cached.diagnostic_profile?.ca_estime_annuel != null
          ? String(cached.diagnostic_profile.ca_estime_annuel)
          : "",
      );
      setEditActivite(cached.diagnostic_profile?.activite || "");
    }

    const id = sessionFromUrl || getStoredSessionId() || cached?.session_id || null;
    if (!id) {
      if (!cached) setError("Aucune session de diagnostic trouvée. Recommencez le diagnostic.");
      return;
    }

    fetchSessionDetail(id)
      .then((d) => {
        setDetail(d);
        cacheDiagnosticResult(d);
        setChecked(d.roadmap_checked ?? {});
        setEditCa(
          d.diagnostic_profile?.ca_estime_annuel != null
            ? String(d.diagnostic_profile.ca_estime_annuel)
            : "",
        );
        setEditActivite(d.diagnostic_profile?.activite || "");
        setError(null);
      })
      .catch((e) => {
        if (cached) return;
        setError(e instanceof Error ? e.message : "Erreur de chargement");
      });
  }, [sessionFromUrl]);

  const roadmap = detail?.roadmap as
    | {
        bandeau?: RoadmapBandeau;
        etapes?: RoadmapEtape[];
        phases?: RoadmapPhase[];
        parcours?: string;
        durabilite?: string;
        seuil_micro?: number;
        seuils_profil?: RoadmapSeuil[];
        comparatif?: {
          colonnes?: string[];
          lignes?: string[][];
          regle_franchissement?: string;
        };
        regime_recommande?: string;
      }
    | null
    | undefined;

  const situation = detail ? situationFrom(detail.diagnostic_profile, detail.profile) : null;
  const phases = useMemo(() => {
    if (roadmap?.phases?.length) return roadmap.phases;
    if (roadmap?.etapes?.length) return [{ id: "all", titre: "Étapes", etapes: roadmap.etapes }];
    return [];
  }, [roadmap]);

  const regimeNom =
    detail?.profile.recommended_regime ||
    roadmap?.bandeau?.titre ||
    "Régime à préciser";
  const regimePourquoi =
    roadmap?.bandeau?.texte ||
    roadmap?.regime_recommande ||
    "Votre feuille de route a été construite à partir de votre situation déclarée.";
  const seuilFromProfile = roadmap?.seuils_profil?.[0]?.seuil;
  const plafond =
    detail?.profile.regime_plafond ||
    (roadmap?.seuil_micro != null
      ? `${Math.round(roadmap.seuil_micro).toLocaleString("fr-FR")} €`
      : seuilFromProfile != null
        ? `${Math.round(seuilFromProfile).toLocaleString("fr-FR")} €`
        : "—");

  async function toggleEtape(id: string) {
    if (!detail) return;
    const next = { ...checked, [id]: !checked[id] };
    setChecked(next);
    try {
      const saved = await saveRoadmapChecked(detail.session_id, next);
      setChecked(saved);
      cacheDiagnosticResult({ ...detail, roadmap_checked: saved });
    } catch (e) {
      setChecked(checked);
      setError(e instanceof Error ? e.message : "Impossible d'enregistrer la case");
    }
  }

  async function onChoix(choix: "micro" | "societe") {
    if (!detail) return;
    setBusy("choix");
    setError(null);
    try {
      const d = await chooseParcours(detail.session_id, choix);
      setDetail(d);
      setChecked(d.roadmap_checked ?? {});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Choix impossible");
    } finally {
      setBusy(null);
    }
  }

  async function onPdf() {
    if (!detail) return;
    setBusy("pdf");
    setError(null);
    try {
      const blob = await downloadSessionRoadmapPdf(detail.session_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "roadmap_ledgermind.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export PDF impossible");
    } finally {
      setBusy(null);
    }
  }

  async function onSaveProfil() {
    if (!detail) return;
    setBusy("profil");
    setError(null);
    try {
      const ca = editCa.trim() ? Number(editCa.replace(/\s/g, "").replace(",", ".")) : null;
      const d = await patchDiagnosticProfile(detail.session_id, {
        activite: editActivite.trim() || null,
        ca_estime_annuel: ca != null && !Number.isNaN(ca) ? ca : null,
        rebuild_roadmap: true,
      });
      setDetail(d);
      setChecked(d.roadmap_checked ?? {});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Mise à jour du profil impossible");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="min-h-screen px-6 py-16 max-w-6xl mx-auto">
      <div className="flex justify-end mb-6">
        <LogoutBubble />
      </div>
      <header className="mb-12 animate-slide-up flex flex-col md:flex-row md:items-end md:justify-between gap-6">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-teal-dark mb-4">
            Résultat de votre diagnostic
          </p>
          <h1 className="text-4xl md:text-6xl font-extrabold tracking-tighter text-balance max-w-3xl">
            Voici votre situation, <span className="italic font-normal">clairement.</span>
          </h1>
        </div>
        {detail?.roadmap && (
          <button
            type="button"
            onClick={onPdf}
            disabled={busy === "pdf"}
            className="shrink-0 px-6 py-3 bg-ink text-background rounded-xl font-semibold hover:bg-teal-dark transition-colors disabled:opacity-40"
          >
            {busy === "pdf" ? "PDF…" : "Télécharger le PDF"}
          </button>
        )}
      </header>

      {error && (
        <div className="mb-6 bg-coral/10 border border-coral/30 rounded-2xl p-4 text-sm text-coral font-medium">
          {error}
        </div>
      )}

      {!detail && !error ? (
        <div className="text-ink/40 font-mono text-sm">Analyse en cours…</div>
      ) : detail && situation ? (
        <>
          <div className="grid lg:grid-cols-2 gap-6">
            <Card index="01" label="Fiche de situation">
              <dl className="space-y-4">
                <Row k="Activité" v={situation.activite} />
                <Row k="Revenus estimés" v={situation.revenus} />
                <Row k="Ancienneté" v={situation.anciennete} />
                <div>
                  <dt className="text-xs uppercase tracking-widest text-ink/40 mb-2">
                    Sources / nature
                  </dt>
                  <dd className="flex flex-wrap gap-2">
                    {situation.sources.map((s) => (
                      <span
                        key={s}
                        className="px-3 py-1 bg-background border border-border rounded-full text-xs font-medium"
                      >
                        {s}
                      </span>
                    ))}
                  </dd>
                </div>
              </dl>
            </Card>

            <Card index="02" label="Profil live (éditable)">
              <p className="text-sm text-ink/55 mb-4 leading-relaxed">
                Ajustez activité ou CA : la feuille de route se recalcule de façon déterministe.
              </p>
              <div className="space-y-3">
                <label className="block text-xs uppercase tracking-widest text-ink/40">
                  Activité
                  <input
                    value={editActivite}
                    onChange={(e) => setEditActivite(e.target.value)}
                    className="mt-1 w-full px-3 py-2 border border-border rounded-lg bg-background"
                  />
                </label>
                <label className="block text-xs uppercase tracking-widest text-ink/40">
                  CA estimé annuel (€)
                  <input
                    value={editCa}
                    onChange={(e) => setEditCa(e.target.value)}
                    className="mt-1 w-full px-3 py-2 border border-border rounded-lg bg-background font-mono"
                  />
                </label>
                <button
                  type="button"
                  onClick={onSaveProfil}
                  disabled={busy === "profil"}
                  className="px-5 py-2.5 border border-border rounded-xl text-sm font-semibold hover:border-teal-dark disabled:opacity-40"
                >
                  {busy === "profil" ? "Recalcul…" : "Recalculer la feuille de route"}
                </button>
              </div>
            </Card>

            <Card index="03" label="Régime & durabilité" span="lg:col-span-2">
              <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div>
                  <h2 className="text-3xl font-extrabold tracking-tighter">{regimeNom}</h2>
                  <p className="mt-3 text-ink/70 max-w-2xl leading-relaxed">{regimePourquoi}</p>
                  {roadmap?.durabilite && (
                    <p className="mt-3 font-mono text-xs uppercase tracking-widest text-teal-dark">
                      {DURABILITE_LABELS[roadmap.durabilite] || roadmap.durabilite}
                    </p>
                  )}
                </div>
                <div className="shrink-0">
                  <p className="text-xs uppercase tracking-widest text-ink/40">Plafond</p>
                  <p className="font-mono text-2xl font-medium mt-1">{plafond}</p>
                </div>
              </div>
              {(roadmap?.seuils_profil || []).length > 0 && (
                <div className="mt-8 space-y-3">
                  {roadmap!.seuils_profil!.slice(0, 3).map((s, i) => {
                    const ratio =
                      s.seuil && s.position != null ? Math.min(1, s.position / s.seuil) : 0;
                    return (
                      <div key={i}>
                        <div className="flex justify-between text-xs text-ink/50 mb-1">
                          <span>{s.label}</span>
                          <span className="font-mono">
                            {Math.round(s.position || 0).toLocaleString("fr-FR")} /{" "}
                            {Math.round(s.seuil || 0).toLocaleString("fr-FR")} €
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full bg-background overflow-hidden">
                          <div
                            className="h-full bg-teal-dark rounded-full"
                            style={{ width: `${Math.max(2, ratio * 100)}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          </div>

          {detail.options?.kind === "choix_parcours" && (
            <section className="mt-6 bg-amber-fiscal/10 border border-amber-fiscal/30 rounded-2xl p-8 animate-slide-up">
              <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-amber-fiscal mb-3">
                Zone d&apos;arbitrage
              </p>
              <h3 className="text-xl font-semibold mb-2">{detail.options.prompt}</h3>
              <p className="text-sm text-ink/60 mb-6 max-w-2xl">
                Votre situation est proche du plafond micro. Choisissez un parcours pour recomposer
                les étapes (le moteur reste 100 % déterministe).
              </p>
              <div className="flex flex-wrap gap-3">
                {detail.options.choices.map((c) => (
                  <button
                    key={c.value}
                    type="button"
                    disabled={busy === "choix"}
                    onClick={() => onChoix(c.value as "micro" | "societe")}
                    className="px-6 py-3 bg-ink text-background rounded-xl font-semibold hover:bg-teal-dark disabled:opacity-40"
                  >
                    {c.label}
                  </button>
                ))}
              </div>
              {roadmap?.comparatif?.lignes && (
                <div className="mt-8 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs uppercase tracking-widest text-ink/40">
                        {(roadmap.comparatif.colonnes || []).map((c) => (
                          <th key={c} className="pb-3 pr-4 font-semibold">
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {roadmap.comparatif.lignes.map((row, i) => (
                        <tr key={i}>
                          {row.map((cell, j) => (
                            <td key={j} className="py-3 pr-4 align-top text-ink/70">
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {roadmap.comparatif.regle_franchissement && (
                    <p className="mt-3 text-xs italic text-ink/45">
                      {roadmap.comparatif.regle_franchissement}
                    </p>
                  )}
                </div>
              )}
            </section>
          )}

          <Card index="04" label="Feuille de route interactive" span="mt-6">
            {phases.length === 0 ? (
              <p className="text-ink/50 text-sm">Aucune étape disponible pour le moment.</p>
            ) : (
              <div className="space-y-10">
                {phases.map((phase, pi) => (
                  <div key={phase.id || pi}>
                    <h3 className="font-mono text-[11px] uppercase tracking-[0.25em] text-teal-dark mb-4">
                      Phase {pi + 1} —{" "}
                      {PHASE_LABELS[phase.id || ""] || phase.titre || "Étapes"}
                    </h3>
                    <ul className="space-y-4">
                      {(phase.etapes || []).map((e, ei) => {
                        const id = e.id || `p${pi}-e${ei}`;
                        const done = !!checked[id];
                        return (
                          <li
                            key={id}
                            className="flex gap-4 items-start border border-border rounded-xl p-4 bg-background/40"
                          >
                            <input
                              type="checkbox"
                              checked={done}
                              onChange={() => toggleEtape(id)}
                              className="mt-1 size-4 accent-teal-dark"
                              aria-label={`Marquer ${e.titre}`}
                            />
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className={`font-semibold ${done ? "line-through opacity-60" : ""}`}>
                                  {e.titre || `Étape ${ei + 1}`}
                                </p>
                                <span
                                  className={`text-[10px] uppercase tracking-widest font-semibold px-2 py-0.5 rounded-full border ${
                                    e.obligatoire
                                      ? "border-amber-fiscal/40 text-amber-fiscal"
                                      : "border-border text-ink/40"
                                  }`}
                                >
                                  {e.obligatoire ? "Obligatoire" : "Recommandé"}
                                </span>
                                {e.duree && (
                                  <span className="text-xs text-ink/40 font-mono">{e.duree}</span>
                                )}
                                {e.cout && (
                                  <span className="text-xs text-ink/40 font-mono">{e.cout}</span>
                                )}
                              </div>
                              {e.detail && (
                                <p className="text-sm text-ink/60 mt-1 leading-relaxed">{e.detail}</p>
                              )}
                              {e.lien && (
                                <a
                                  href={e.lien}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-block mt-2 text-xs text-teal-dark hover:underline break-all"
                                >
                                  {e.lien}
                                </a>
                              )}
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <div className="mt-12 flex flex-wrap justify-center gap-4">
            <Link
              to="/education"
              className="px-8 py-4 border border-border rounded-xl font-semibold hover:border-teal-dark transition-colors"
            >
              Poser une question fiscale
            </Link>
            <Link
              to="/onboarding/diagnostic"
              className="px-8 py-4 border border-border rounded-xl font-semibold hover:border-teal-dark transition-colors"
            >
              Refaire le diagnostic
            </Link>
            <Link
              to="/dashboard"
              className="px-10 py-5 bg-ink text-background rounded-xl font-semibold hover:bg-teal-dark transition-colors"
            >
              Accéder à mon dashboard →
            </Link>
          </div>
        </>
      ) : null}
    </div>
  );
}

function Card({
  index,
  label,
  children,
  span = "",
}: {
  index: string;
  label: string;
  children: React.ReactNode;
  span?: string;
}) {
  return (
    <section
      className={`bg-white border border-border rounded-2xl p-8 animate-slide-up ${span}`}
    >
      <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-ink/40 mb-6">
        {index} · {label}
      </p>
      {children}
    </section>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-widest text-ink/40">{k}</dt>
      <dd className="mt-1 font-medium">{v}</dd>
    </div>
  );
}
