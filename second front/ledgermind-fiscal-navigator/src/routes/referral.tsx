import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Copy, Mail } from "lucide-react";
import { AppShell, PageHeader } from "@/components/app-shell";
import { PremiumGate } from "@/components/paywall";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBlock,
  Field,
  Input,
  LoadingBlock,
  Spinner,
  Textarea,
  formatDate,
} from "@/components/ui-kit";
import { api, ApiError } from "@/lib/api";
import type { ReferralResult } from "@/lib/types";

export const Route = createFileRoute("/referral")({
  head: () => ({
    meta: [
      { title: "Mise en relation cabinets — LedgerMind" },
      {
        name: "description",
        content:
          "Des emails personnalisés, prêts à envoyer, vers des cabinets comptables proches de chez vous.",
      },
      { property: "og:title", content: "Mise en relation cabinets — LedgerMind" },
      { property: "og:description", content: "Emails prêts pour plusieurs cabinets." },
    ],
  }),
  component: Page,
});

function Page() {
  return (
    <PremiumGate
      feature="referral"
      title="Mise en relation avec des cabinets"
      pitch="Votre profil fiscal transformé en demande claire, envoyée aux bons interlocuteurs."
      benefits={[
        "Emails prêts pour 3 cabinets de votre ville",
        "Votre régime recommandé intégré à la demande",
        "Historique de vos prises de contact",
      ]}
      preview={
        <Card className="p-8">
          <Badge tone="accent">Email généré</Badge>
          <p className="mt-4 font-medium">Objet : Accompagnement micro-BNC — première année</p>
          <p className="mt-3 text-sm text-muted-foreground">
            Bonjour, je suis prestataire indépendant à Lyon, en micro-BNC depuis mars…
          </p>
        </Card>
      }
    >
      <Referral />
    </PremiumGate>
  );
}

function Referral() {
  const [ville, setVille] = useState("");
  const [demande, setDemande] = useState("");
  const [result, setResult] = useState<ReferralResult | null>(null);
  const [busy, setBusy] = useState(false);
  const history = useQuery({ queryKey: ["referral-history"], queryFn: () => api.referralHistory(), retry: false });

  const valid = ville.trim().length >= 2 && demande.trim().length >= 10;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Premium"
        title="Trouver un expert-comptable"
        description="LedgerMind rédige des emails personnalisés à partir de votre profil et de votre demande."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Card className="space-y-5 p-6">
            <Field label="Ville" htmlFor="ville">
              <Input id="ville" value={ville} onChange={(e) => setVille(e.target.value)} placeholder="Lyon" maxLength={80} />
            </Field>
            <Field label="Votre demande" htmlFor="demande" hint="10 caractères minimum.">
              <Textarea
                id="demande"
                rows={5}
                maxLength={1000}
                value={demande}
                onChange={(e) => setDemande(e.target.value)}
                placeholder="Ex. accompagnement pour ma première déclaration en micro-BNC, avec revenus étrangers."
              />
            </Field>
            <Button
              variant="safran"
              disabled={!valid || busy}
              onClick={async () => {
                setBusy(true);
                try {
                  setResult(await api.referralGenerate({ ville: ville.trim(), demande: demande.trim() }));
                  void history.refetch();
                } catch (err) {
                  toast.error(err instanceof ApiError ? err.message : "Génération impossible.");
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? <Spinner /> : <Mail />} Générer mes emails
            </Button>
          </Card>

          {result && (
            <div className="space-y-4">
              <Badge tone="success">{result.cabinets_count ?? result.emails.length} cabinet(s) identifié(s)</Badge>
              {result.emails.map((mail, i) => (
                <Card key={i} className="animate-rise p-6">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-medium">{mail.destinataire}</p>
                      <p className="text-xs text-muted-foreground">{mail.email}</p>
                    </div>
                    {mail.statut && <Badge>{mail.statut}</Badge>}
                  </div>
                  <p className="mt-4 font-medium">Objet : {mail.objet}</p>
                  <p className="mt-3 whitespace-pre-wrap text-sm text-muted-foreground">{mail.corps}</p>
                  <div className="mt-5 flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        void navigator.clipboard.writeText(`${mail.objet}\n\n${mail.corps}`);
                        toast.success("Email copié.");
                      }}
                    >
                      <Copy /> Copier
                    </Button>
                    <a
                      href={`mailto:${encodeURIComponent(mail.email ?? "")}?subject=${encodeURIComponent(mail.objet)}&body=${encodeURIComponent(mail.corps)}`}
                      className="inline-flex h-9 items-center gap-2 rounded-full bg-primary px-4 text-sm font-semibold text-primary-foreground"
                    >
                      <Mail className="size-4" /> Ouvrir dans ma messagerie
                    </a>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>

        <aside>
          <Card className="p-5">
            <h2 className="text-lg">Historique</h2>
            {history.isLoading && <LoadingBlock />}
            {history.isError && <ErrorBlock message="Historique indisponible." onRetry={() => void history.refetch()} />}
            {history.data?.length === 0 && (
              <EmptyState title="Aucune demande" description="Vos demandes apparaîtront ici." />
            )}
            <ul className="mt-3 space-y-2">
              {history.data?.map((h, i) => (
                <li key={i} className="rounded-xl border border-border p-3 text-sm">
                  <p className="font-medium">{h.ville}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(h.created_at)} · {h.cabinets_count ?? h.emails?.length ?? 0} cabinet(s)
                  </p>
                </li>
              ))}
            </ul>
          </Card>
        </aside>
      </div>
    </AppShell>
  );
}
