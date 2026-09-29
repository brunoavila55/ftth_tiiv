"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Edit, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState, LoadingState } from "@/components/ui/state-displays";
import { useAuth } from "@/features/auth/auth-context";
import { loadRadios, loadWirelessSites } from "../load-options";
import { ApiError } from "@/lib/api/types";
import { deleteRadioLink, listRadioLinks, type RadioLinkRead } from "../api";
import { RadioLinkFormDialog } from "./radio-link-form-dialog";

export function RadioLinksPanel() {
  const searchParams = useSearchParams();
  const siteId = searchParams.get("site_id") ?? undefined;
  const { hasPermission } = useAuth();
  const canWrite = hasPermission("network:write");
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [formOpen, setFormOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<RadioLinkRead | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [deletingId, setDeletingId] = React.useState<string | null>(null);

  const linksQuery = useQuery({
    queryKey: ["wireless", "links", page, search, siteId],
    queryFn: () => listRadioLinks({ page, page_size: 20, site_id: siteId, q: search || undefined }),
  });
  const sitesQuery = useQuery({
    queryKey: ["wireless", "sites-for-links"],
    queryFn: loadWirelessSites,
  });
  const radiosQuery = useQuery({
    queryKey: ["wireless", "radios-for-links"],
    queryFn: loadRadios,
  });

  const sites = sitesQuery.data ?? [];
  const radios = radiosQuery.data ?? [];
  const siteById = new Map(sites.map((site) => [site.id, site]));
  const radioById = new Map(radios.map((radio) => [radio.id, radio]));

  const remove = async (link: RadioLinkRead) => {
    if (!window.confirm(`Excluir o enlace ${link.code}?`)) return;
    setDeletingId(link.id);
    setActionError(null);
    try {
      await deleteRadioLink(link.id, link.version);
      if (linksQuery.data?.items.length === 1 && page > 1) setPage(page - 1);
      await linksQuery.refetch();
    } catch (cause) {
      setActionError(cause instanceof ApiError ? cause.detail ?? cause.message : "Não foi possível excluir o enlace.");
    } finally {
      setDeletingId(null);
    }
  };

  if (linksQuery.error) {
    return <ErrorState title="Falha ao carregar enlaces de rádio" error={linksQuery.error} onRetry={() => linksQuery.refetch()} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Input
          aria-label="Buscar enlaces"
          placeholder="Buscar enlace por código ou nome..."
          value={search}
          onChange={(event) => { setSearch(event.target.value); setPage(1); }}
          className="sm:max-w-sm"
        />
        {canWrite && <Button size="sm" onClick={() => { setEditing(null); setFormOpen(true); }}><Plus className="mr-1 h-4 w-4" />Novo Enlace</Button>}
      </div>
      {siteId && <p className="text-xs text-muted-foreground">Enlaces do ponto {siteById.get(siteId)?.code ?? siteId.slice(0, 8)} · <Link href="/wireless?type=links" className="text-primary hover:underline">Ver todos</Link></p>}

      {actionError && <p role="alert" className="rounded-md bg-destructive/10 p-3 text-xs text-destructive">{actionError}</p>}
      {(sitesQuery.error || radiosQuery.error) && <ErrorState title="Falha ao carregar pontos e rádios" error={sitesQuery.error ?? radiosQuery.error} onRetry={() => { void sitesQuery.refetch(); void radiosQuery.refetch(); }} />}
      {canWrite && !sitesQuery.isLoading && !radiosQuery.isLoading && sites.length < 2 && <p className="text-xs text-muted-foreground">Cadastre dois POPs ou torres para criar um enlace.</p>}
      {canWrite && !radiosQuery.isLoading && radios.length < 2 && <p className="text-xs text-muted-foreground">Cadastre um rádio em cada ponta antes de criar o enlace.</p>}

      <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full min-w-[780px] text-left text-xs">
          <thead className="border-b border-border bg-muted/50 text-foreground"><tr>
            <th className="px-3 py-3">Enlace</th><th className="px-3 py-3">Ponta A</th><th className="px-3 py-3">Ponta B</th>
            <th className="px-3 py-3">Frequência</th><th className="px-3 py-3">Canal</th><th className="px-3 py-3">Situação</th><th className="px-3 py-3">Ações</th>
          </tr></thead>
          <tbody className="divide-y divide-border">
            {linksQuery.isLoading && <tr><td colSpan={7} className="p-8"><LoadingState message="Carregando enlaces..." /></td></tr>}
            {!linksQuery.isLoading && linksQuery.data?.items.length === 0 && <tr><td colSpan={7} className="p-8 text-center text-muted-foreground">Nenhum enlace de rádio encontrado.</td></tr>}
            {linksQuery.data?.items.map((link) => <tr key={link.id}>
              <td className="px-3 py-3"><span className="font-mono font-semibold">{link.code}</span><span className="block text-muted-foreground">{link.name}</span></td>
              {(["a", "b"] as const).map((end) => {
                const siteId = link[`site_${end}_id`];
                const radioId = link[`radio_${end}_id`];
                return <td key={end} className="px-3 py-3">
                  <Link href={`/sites/${siteId}`} className="text-primary hover:underline">{siteById.get(siteId)?.code ?? siteId.slice(0, 8)}</Link>
                  <span className="block text-muted-foreground">{radioById.get(radioId)?.code ?? radioId.slice(0, 8)}</span>
                </td>;
              })}
              <td className="px-3 py-3">{link.frequency_mhz} MHz</td>
              <td className="px-3 py-3">{link.channel_width_mhz} MHz</td>
              <td className="px-3 py-3">{link.status === "installed" ? "Instalado" : link.status === "planned" ? "Planejado" : "Desativado"}</td>
              <td className="px-3 py-3"><div className="flex gap-1">
                {canWrite && <Button variant="ghost" size="sm" aria-label={`Editar ${link.code}`} onClick={() => { setEditing(link); setFormOpen(true); }}><Edit className="h-4 w-4" /></Button>}
                {canWrite && <Button variant="ghost" size="sm" aria-label={`Excluir ${link.code}`} disabled={deletingId === link.id} onClick={() => void remove(link)}><Trash2 className="h-4 w-4" /></Button>}
              </div></td>
            </tr>)}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{linksQuery.data?.total ?? 0} enlace(s)</span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button>
          <span className="self-center">Página {page}</span>
          <Button variant="outline" size="sm" disabled={!linksQuery.data || page * 20 >= linksQuery.data.total} onClick={() => setPage(page + 1)}>Próxima</Button>
        </div>
      </div>
      <RadioLinkFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        link={editing}
        sites={sites}
        radios={radios}
        onSuccess={() => { setPage(1); void linksQuery.refetch(); void radiosQuery.refetch(); }}
      />
    </div>
  );
}
