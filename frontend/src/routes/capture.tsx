import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { AppShell, PageHeader } from "@/components/lm/AppShell";
import { isAuthed } from "@/lib/auth";
import {
  analyzeCapture,
  answerCapture,
  askCaptureQuestion,
  fetchCaptureInvoices,
  fetchCaptureVirements,
  formatMoney,
  type CaptureAnalyzeResult,
  type CaptureInvoice,
  type CaptureInvoiceItem,
  type CaptureTransfer,
  type CaptureVirementItem,
} from "@/lib/api";

export const Route = createFileRoute("/capture")({
  head: () => ({
    meta: [
      { title: "Documents — LedgerMind" },
      { name: "description", content: "Déposez vos factures, relevés et justificatifs." },
      { property: "og:title", content: "Documents — LedgerMind" },
      { property: "og:description", content: "Déposez vos factures, relevés et justificatifs." },
    ],
  }),
  component: CapturePage,
});

const PIPELINE = [
  "OCR",
  "Langue",
  "Extraction",
  "Analyse",
  "Classification",
  "Doublon",
  "Sauvegarde",
];

function pipelineStep(status: CaptureAnalyzeResult["status"] | null, idx: number): boolean {
  if (!status) return false;
  if (status === "erreur") return idx === 0;
  if (status === "en_attente_utilisateur") return idx < 3;
  return true;
}

function CapturePage() {
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CaptureAnalyzeResult | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [hitlAnswer, setHitlAnswer] = useState("");
  const [activite, setActivite] = useState("");
  const [invoices, setInvoices] = useState<CaptureInvoiceItem[]>([]);
  const [virements, setVirements] = useState<CaptureVirementItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedKind, setSelectedKind] = useState<"facture" | "virement">("facture");
  const [qaQuestion, setQaQuestion] = useState("");
  const [qaAnswer, setQaAnswer] = useState<string | null>(null);
  const [qaLoading, setQaLoading] = useState(false);

  async function refreshLists() {
    const [inv, vir] = await Promise.all([
      fetchCaptureInvoices().catch(() => [] as CaptureInvoiceItem[]),
      fetchCaptureVirements().catch(() => [] as CaptureVirementItem[]),
    ]);
    setInvoices(inv);
    setVirements(vir);
  }

  useEffect(() => {
    if (!isAuthed()) {
      navigate({ to: "/auth", replace: true });
      return;
    }
    refreshLists();
  }, [navigate]);

  async function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    const file = files[0];
    setLoading(true);
    setError(null);
    setResult(null);
    setQaAnswer(null);
    try {
      const res = await analyzeCapture(file, activite.trim() || undefined);
      setResult(res);
      setThreadId(res.thread_id);
      if (res.document_id) {
        setSelectedId(res.document_id);
        setSelectedKind(res.document_type === "virement" ? "virement" : "facture");
      }
      if (res.status === "completed") await refreshLists();
      if (res.status === "erreur") setError(res.error || "Erreur lors de l'analyse.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue.");
    } finally {
      setLoading(false);
    }
  }

  async function handleHitlSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!threadId || !hitlAnswer.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await answerCapture(threadId, hitlAnswer.trim());
      if (res.analyze) {
        setResult(res.analyze);
        if (res.analyze.document_id) setSelectedId(res.analyze.document_id);
        if (res.analyze.status === "completed") await refreshLists();
        if (res.analyze.status === "erreur") {
          setError(res.analyze.error || res.error || "Erreur.");
        }
      } else if (res.answer) {
        setQaAnswer(res.answer);
      }
      setHitlAnswer("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue.");
    } finally {
      setLoading(false);
    }
  }

  async function handleQa(e: React.FormEvent) {
    e.preventDefault();
    const docId = selectedId || result?.document_id;
    if (!docId || !qaQuestion.trim()) return;
    setQaLoading(true);
    setQaAnswer(null);
    try {
      const res = await askCaptureQuestion(docId, qaQuestion.trim());
      if (res.error) setError(res.error);
      else setQaAnswer(res.answer ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur Q&A.");
    } finally {
      setQaLoading(false);
    }
  }

  const activeInvoice =
    selectedKind === "facture"
      ? invoices.find((i) => i.document_id === selectedId)
      : undefined;
  const activeVirement =
    selectedKind === "virement"
      ? virements.find((v) => v.document_id === selectedId)
      : undefined;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Documents"
        title={
          <>
            Déposez, on <span className="italic font-normal">s&apos;occupe du reste.</span>
          </>
        }
        description="OCR → extraction complète → analyse → classification → détection de doublon → sauvegarde. Factures et virements."
      />

      <div className="grid lg:grid-cols-12 gap-10 items-start">
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-white border border-border rounded-2xl p-6 space-y-4">
            <div>
              <label className="text-xs uppercase tracking-widest text-ink/50 font-semibold">
                Activité (optionnel)
              </label>
              <input
                type="text"
                value={activite}
                onChange={(e) => setActivite(e.target.value)}
                placeholder="ex. influenceur BNC, prestation freelance…"
                className="w-full mt-2 px-0 py-3 bg-transparent border-b border-border text-base focus:outline-none focus:border-ink transition-colors"
              />
            </div>
            <label className="block bg-background border border-dashed border-border hover:border-teal-dark transition-colors rounded-2xl p-12 text-center cursor-pointer">
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.webp"
                className="sr-only"
                disabled={loading}
                onChange={(e) => handleFiles(e.target.files)}
              />
              <div className="mx-auto size-14 rounded-full bg-teal-dark/10 grid place-items-center mb-4">
                <span className="text-2xl text-teal-dark">↑</span>
              </div>
              <p className="font-semibold text-lg">
                {loading ? "Analyse en cours…" : "Glissez une facture ou un relevé"}
              </p>
              <p className="text-sm text-ink/50 mt-2">PDF ou image · 20 Mo max</p>
            </label>
          </div>

          {loading && (
            <div className="bg-white border border-border rounded-2xl p-8 text-center">
              <div className="inline-block size-8 border-[3px] border-ink/20 border-t-teal-dark rounded-full animate-spin" />
              <p className="text-sm text-ink/50 mt-4">
                OCR, extraction, analyse et classification… 30 à 90 secondes.
              </p>
            </div>
          )}

          {error && (
            <div className="bg-coral/10 border border-coral/30 rounded-2xl p-6 text-sm text-coral font-medium">
              {error}
            </div>
          )}

          {result && (
            <section className="bg-white border border-border rounded-2xl p-8 space-y-6 animate-slide-up">
              <ResultHeader result={result} />

              <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
                {PIPELINE.map((step, i) => (
                  <div key={step} className="space-y-2">
                    <div
                      className={`h-1.5 rounded-full ${
                        pipelineStep(result.status, i) ? "bg-teal-light" : "bg-border"
                      }`}
                    />
                    <span className="text-[9px] uppercase tracking-widest text-ink/40 font-semibold">
                      {step}
                    </span>
                  </div>
                ))}
              </div>

              {result.status === "en_attente_utilisateur" && result.pending && (
                <HitlPanel
                  pending={result.pending}
                  hitlAnswer={hitlAnswer}
                  setHitlAnswer={setHitlAnswer}
                  onSubmit={handleHitlSubmit}
                  loading={loading}
                />
              )}

              {result.status === "completed" && result.invoice && (
                <InvoiceReport
                  invoice={result.invoice}
                  expenseCategory={result.expense_category}
                  analysis={result.analysis}
                  incoherences={result.incoherences}
                  paid={result.paid}
                  paymentDate={result.payment_date}
                  paymentDaysUntil={result.payment_days_until}
                />
              )}

              {result.status === "completed" && result.transfer && (
                <TransferReport
                  transfer={result.transfer}
                  analysis={result.analysis}
                  incoherences={result.incoherences}
                />
              )}
            </section>
          )}

          {(selectedId || result?.document_id) && selectedKind === "facture" && (
            <section className="bg-white border border-border rounded-2xl p-8 space-y-4">
              <h3 className="text-lg font-semibold">Question sur ce document</h3>
              <p className="text-sm text-ink/50">
                Ancré sur l&apos;OCR et l&apos;historique — ex. « Cette facture est-elle déductible ? »
              </p>
              <form onSubmit={handleQa} className="space-y-3">
                <input
                  type="text"
                  value={qaQuestion}
                  onChange={(e) => setQaQuestion(e.target.value)}
                  placeholder="Votre question…"
                  className="w-full px-0 py-3 bg-transparent border-b border-border text-base focus:outline-none focus:border-ink"
                />
                <button
                  type="submit"
                  disabled={qaLoading || !qaQuestion.trim()}
                  className="px-8 py-4 bg-ink text-background rounded-xl font-semibold hover:bg-teal-dark transition-colors disabled:opacity-40"
                >
                  {qaLoading ? "Réponse…" : "Poser la question"}
                </button>
              </form>
              {qaAnswer && (
                <p className="text-sm text-ink/80 bg-background rounded-xl p-4 leading-relaxed whitespace-pre-wrap">
                  {qaAnswer}
                </p>
              )}
            </section>
          )}
        </div>

        <aside className="lg:col-span-5 lg:sticky lg:top-24 space-y-8">
          <SidebarList
            title="Mes factures"
            empty="Aucune facture analysée."
            items={invoices.map((inv) => ({
              id: inv.document_id,
              title: inv.invoice.issuer_name ?? "Facture",
              meta: `${inv.expense_category ?? "—"} · ${inv.invoice.issue_date ?? "date ?"}`,
              amount:
                inv.invoice.total_ttc != null
                  ? `${formatMoney(inv.invoice.total_ttc)} €`
                  : "—",
            }))}
            selectedId={selectedKind === "facture" ? selectedId : null}
            onSelect={(id) => {
              setSelectedId(id);
              setSelectedKind("facture");
              setQaAnswer(null);
              setResult(null);
            }}
          />

          <SidebarList
            title="Mes virements"
            empty="Aucun virement analysé."
            items={virements.map((v) => ({
              id: v.document_id,
              title: v.transfer.beneficiary_name || v.transfer.sender_name || "Virement",
              meta: `${v.transfer.direction ?? "—"} · ${v.transfer.execution_date ?? "date ?"}`,
              amount:
                v.transfer.amount != null
                  ? `${formatMoney(v.transfer.amount)} ${v.transfer.currency ?? "€"}`
                  : "—",
            }))}
            selectedId={selectedKind === "virement" ? selectedId : null}
            onSelect={(id) => {
              setSelectedId(id);
              setSelectedKind("virement");
              setQaAnswer(null);
              setResult(null);
            }}
          />

          {activeInvoice && !result && (
            <div className="bg-white border border-border rounded-2xl p-6">
              <InvoiceReport
                invoice={activeInvoice.invoice}
                expenseCategory={activeInvoice.expense_category}
                analysis={activeInvoice.analysis}
                incoherences={activeInvoice.incoherences}
                paid={activeInvoice.paid}
                paymentDate={activeInvoice.payment_date}
                paymentDaysUntil={activeInvoice.payment_days_until}
              />
            </div>
          )}

          {activeVirement && !result && (
            <div className="bg-white border border-border rounded-2xl p-6">
              <TransferReport
                transfer={activeVirement.transfer}
                analysis={activeVirement.analysis}
                incoherences={activeVirement.incoherences}
              />
            </div>
          )}
        </aside>
      </div>
    </AppShell>
  );
}

function ResultHeader({ result }: { result: CaptureAnalyzeResult }) {
  const statusLabel =
    result.status === "completed"
      ? "Terminé"
      : result.status === "en_attente_utilisateur"
        ? "Action requise"
        : "Erreur";
  const statusClass =
    result.status === "completed"
      ? "text-teal-dark"
      : result.status === "en_attente_utilisateur"
        ? "text-amber-600"
        : "text-coral";

  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 className="text-lg font-semibold">Résultat d&apos;analyse</h2>
        <p className="text-xs text-ink/40 font-mono mt-1">
          {result.document_type === "virement" ? "Virement" : "Facture"}
          {result.document_id ? ` · ${result.document_id.slice(0, 8)}…` : ""}
        </p>
      </div>
      <div className="flex flex-wrap gap-2 justify-end">
        <span className={`text-[10px] font-mono uppercase tracking-widest ${statusClass}`}>
          {statusLabel}
        </span>
        {result.saved === true && (
          <Badge tone="teal">Sauvegardée</Badge>
        )}
        {result.saved === false && result.duplicate_skipped && (
          <Badge tone="amber">Doublon ignoré</Badge>
        )}
        {result.expense_category && (
          <Badge tone="ink">{result.expense_category}</Badge>
        )}
      </div>
    </div>
  );
}

function Badge({
  children,
  tone,
}: {
  children: ReactNode;
  tone: "teal" | "amber" | "ink";
}) {
  const cls =
    tone === "teal"
      ? "bg-teal-dark/10 text-teal-dark border-teal-dark/20"
      : tone === "amber"
        ? "bg-amber-50 text-amber-700 border-amber-200"
        : "bg-background text-ink/70 border-border";
  return (
    <span
      className={`text-[10px] font-mono uppercase tracking-widest px-2.5 py-1 rounded-full border ${cls}`}
    >
      {children}
    </span>
  );
}

function HitlPanel({
  pending,
  hitlAnswer,
  setHitlAnswer,
  onSubmit,
  loading,
}: {
  pending: NonNullable<CaptureAnalyzeResult["pending"]>;
  hitlAnswer: string;
  setHitlAnswer: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  loading: boolean;
}) {
  const isDup = pending.type === "doublon";
  return (
    <div className="border-t border-border pt-6 space-y-5">
      <div>
        <p className="font-mono text-[10px] uppercase tracking-widest text-amber-600 mb-2">
          {isDup ? "Doublon possible" : "Champ manquant"}
          {pending.field ? ` · ${pending.field}` : ""}
        </p>
        <p className="text-sm font-medium leading-relaxed">{pending.question}</p>
      </div>

      {isDup && (pending.existing_invoice || pending.new_invoice) && (
        <div className="grid sm:grid-cols-2 gap-4">
          <MiniInvoiceCard title="Existant" data={pending.existing_invoice} />
          <MiniInvoiceCard title="Nouveau" data={pending.new_invoice} />
        </div>
      )}

      {pending.suggestions && pending.suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {pending.suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setHitlAnswer(s)}
              className="px-3 py-1.5 text-xs border border-border rounded-lg hover:border-ink transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {isDup && (
        <div className="flex flex-wrap gap-2">
          {["oui", "non"].map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setHitlAnswer(s)}
              className="px-4 py-2 text-xs border border-border rounded-lg hover:border-ink transition-colors capitalize"
            >
              {s === "oui" ? "Oui — c’est un doublon" : "Non — enregistrer quand même"}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-3">
        <input
          type="text"
          value={hitlAnswer}
          onChange={(e) => setHitlAnswer(e.target.value)}
          placeholder={isDup ? "oui / non" : "Votre réponse…"}
          className="w-full px-0 py-3 bg-transparent border-b border-border text-base focus:outline-none focus:border-ink"
        />
        <button
          type="submit"
          disabled={loading || !hitlAnswer.trim()}
          className="px-8 py-4 bg-ink text-background rounded-xl font-semibold hover:bg-teal-dark transition-colors disabled:opacity-40"
        >
          Valider
        </button>
      </form>
    </div>
  );
}

function MiniInvoiceCard({
  title,
  data,
}: {
  title: string;
  data?: CaptureInvoice | Record<string, unknown> | null;
}) {
  if (!data) return null;
  const inv = data as CaptureInvoice;
  return (
    <div className="bg-background border border-border rounded-xl p-4 space-y-2 text-sm">
      <p className="font-mono text-[10px] uppercase tracking-widest text-ink/40">{title}</p>
      <p className="font-semibold">{inv.issuer_name ?? "—"}</p>
      <p className="font-mono text-xs text-ink/60">{inv.invoice_number ?? "—"}</p>
      <p className="font-mono text-xs">
        {inv.total_ttc != null ? `${formatMoney(inv.total_ttc)} ${inv.currency ?? "€"}` : "—"}
      </p>
      <p className="text-xs text-ink/50">{inv.issue_date ?? "—"}</p>
    </div>
  );
}

function Field({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  const empty = value === null || value === undefined || value === "";
  return (
    <div>
      <p className="text-xs uppercase tracking-widest text-ink/40 font-semibold mb-1">{label}</p>
      <p className={`${mono ? "font-mono" : "font-medium"} text-sm break-words`}>
        {empty ? "—" : value}
      </p>
    </div>
  );
}

function money(n: number | null | undefined, currency?: string | null) {
  if (n == null) return null;
  return `${formatMoney(n)} ${currency ?? "€"}`;
}

function InvoiceReport({
  invoice,
  expenseCategory,
  analysis,
  incoherences,
  paid,
  paymentDate,
  paymentDaysUntil,
}: {
  invoice: CaptureInvoice;
  expenseCategory?: string | null;
  analysis?: string | null;
  incoherences?: string[] | null;
  paid?: boolean | null;
  paymentDate?: string | null;
  paymentDaysUntil?: number | null;
}) {
  const lines = invoice.line_items ?? [];
  const paidLabel =
    paid === true || invoice.paid === true
      ? "Oui"
      : paid === false || invoice.paid === false
        ? "Non"
        : null;

  return (
    <div className="space-y-8">
      <div>
        <p className="font-mono text-[10px] uppercase tracking-widest text-teal-dark mb-4">
          Champs extraits
        </p>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Émetteur" value={invoice.issuer_name} />
          <Field label="N° facture" value={invoice.invoice_number} mono />
          <Field label="Matricule fiscal / SIREN" value={invoice.issuer_tax_id} mono />
          <Field label="Client" value={invoice.client_name} />
          <Field label="Date d'émission" value={invoice.issue_date} mono />
          <Field label="Échéance" value={invoice.due_date} mono />
          <Field
            label="Délai de paiement"
            value={
              invoice.payment_terms_days != null
                ? `${invoice.payment_terms_days} jours`
                : null
            }
          />
          <Field label="Catégorie de dépense" value={expenseCategory} />
          <Field label="Sous-total HT" value={money(invoice.subtotal_ht, invoice.currency)} mono />
          <Field label="TVA" value={money(invoice.vat_amount, invoice.currency)} mono />
          <Field label="Total TTC" value={money(invoice.total_ttc, invoice.currency)} mono />
          <Field label="Devise" value={invoice.currency} mono />
        </div>
      </div>

      <div className="bg-background border border-border rounded-2xl p-5">
        <p className="font-mono text-[10px] uppercase tracking-widest text-ink/40 mb-4">
          Paiement
        </p>
        <div className="grid sm:grid-cols-3 gap-4">
          <Field label="Payée" value={paidLabel} />
          <Field label="Date d'échéance / paiement" value={paymentDate} mono />
          <Field
            label="Jours restants"
            value={paymentDaysUntil != null ? String(paymentDaysUntil) : null}
            mono
          />
        </div>
      </div>

      {lines.length > 0 && (
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-ink/40 mb-3">
            Lignes de facture ({lines.length})
          </p>
          <div className="overflow-x-auto border border-border rounded-xl">
            <table className="w-full text-sm min-w-[28rem]">
              <thead className="bg-background">
                <tr className="text-[10px] uppercase tracking-widest text-ink/40">
                  <th className="text-left px-4 py-3 font-semibold">Description</th>
                  <th className="text-right px-4 py-3 font-semibold">Qté</th>
                  <th className="text-right px-4 py-3 font-semibold">P.U.</th>
                  <th className="text-right px-4 py-3 font-semibold">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {lines.map((li, i) => (
                  <tr key={i}>
                    <td className="px-4 py-3">{li.description ?? "—"}</td>
                    <td className="px-4 py-3 text-right font-mono text-ink/70">
                      {li.quantity ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-ink/70">
                      {li.unit_price != null ? formatMoney(li.unit_price) : "—"}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {li.total != null ? formatMoney(li.total) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {analysis && (
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-ink/40 mb-2">
            Analyse comptable
          </p>
          <p className="text-sm text-ink/80 leading-relaxed whitespace-pre-wrap text-pretty">
            {analysis}
          </p>
        </div>
      )}

      {incoherences && incoherences.length > 0 && (
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-amber-600 mb-3">
            Incohérences détectées
          </p>
          <ul className="space-y-2">
            {incoherences.map((inc, i) => (
              <li
                key={i}
                className="text-sm text-amber-800 bg-amber-50 border border-amber-100 px-4 py-3 rounded-xl"
              >
                {inc}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function TransferReport({
  transfer,
  analysis,
  incoherences,
}: {
  transfer: CaptureTransfer;
  analysis?: string | null;
  incoherences?: string[] | null;
}) {
  return (
    <div className="space-y-8">
      <div>
        <p className="font-mono text-[10px] uppercase tracking-widest text-teal-dark mb-4">
          Champs extraits
        </p>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Référence" value={transfer.transfer_reference} mono />
          <Field label="Type" value={transfer.transfer_type} />
          <Field label="Sens" value={transfer.direction} />
          <Field label="Montant" value={money(transfer.amount ?? null, transfer.currency)} mono />
          <Field label="Date d'exécution" value={transfer.execution_date} mono />
          <Field label="Date de valeur" value={transfer.value_date} mono />
          <Field label="Donneur d'ordre" value={transfer.sender_name} />
          <Field label="IBAN émetteur" value={transfer.sender_iban} mono />
          <Field label="Bénéficiaire" value={transfer.beneficiary_name} />
          <Field label="IBAN bénéficiaire" value={transfer.beneficiary_iban} mono />
          <Field label="BIC / SWIFT" value={transfer.beneficiary_bic} mono />
          <Field label="Banque" value={transfer.bank_name} />
          <Field label="Motif" value={transfer.motif} />
          <Field label="Devise" value={transfer.currency} mono />
        </div>
      </div>
      {analysis && (
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-ink/40 mb-2">
            Analyse
          </p>
          <p className="text-sm text-ink/80 leading-relaxed whitespace-pre-wrap">{analysis}</p>
        </div>
      )}
      {incoherences && incoherences.length > 0 && (
        <ul className="space-y-2">
          {incoherences.map((inc, i) => (
            <li
              key={i}
              className="text-sm text-amber-800 bg-amber-50 border border-amber-100 px-4 py-3 rounded-xl"
            >
              {inc}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SidebarList({
  title,
  empty,
  items,
  selectedId,
  onSelect,
}: {
  title: string;
  empty: string;
  items: { id: string; title: string; meta: string; amount: string }[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="space-y-3">
      <h3 className="font-mono text-[11px] uppercase tracking-[0.25em] text-teal-dark">
        {title}
      </h3>
      {items.length === 0 ? (
        <div className="bg-white border border-border rounded-2xl p-6 text-center text-ink/40 text-sm">
          {empty}
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item.id)}
              className={`w-full text-left bg-white border rounded-2xl p-5 space-y-1 transition-colors ${
                selectedId === item.id
                  ? "border-teal-dark"
                  : "border-border hover:border-ink/30"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-sm truncate">{item.title}</span>
                <span className="font-mono text-xs text-ink/50 shrink-0">{item.amount}</span>
              </div>
              <p className="text-xs text-ink/50">{item.meta}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
