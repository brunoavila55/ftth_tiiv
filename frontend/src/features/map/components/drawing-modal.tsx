"use client";

import * as React from "react";
import {
  Building2,
  Box,
  Cable as CableIcon,
  X,
  Check,
  AlertTriangle,
  Loader2,
  Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { UnitInput } from "@/components/ui/unit-input";
import { CoordinateInput } from "@/components/ui/coordinate-input";
import {
  createSite,
  createStructure,
  listStructures,
  type StructureRead,
} from "@/features/inventory/api";
import { createCableSegment, listCables, type CableRead } from "@/features/cables/api";
import { calculateLineLength } from "../utils/geometry";
import { ApiError } from "@/lib/api/types";
import type { DrawingDraft } from "../types";

export interface DrawingModalProps {
  open: boolean;
  draft: DrawingDraft | null;
  onClose: () => void;
  onSuccess: (createdId: string) => void;
}

const STRUCTURES_PAGE_SIZE = 200;

async function loadAllStructures(): Promise<StructureRead[]> {
  const structures: StructureRead[] = [];

  for (let page = 1; ; page += 1) {
    const response = await listStructures({ page, page_size: STRUCTURES_PAGE_SIZE });
    structures.push(...response.items);
    if (response.items.length < STRUCTURES_PAGE_SIZE || structures.length >= response.total) break;
  }

  return structures;
}

function structureKindLabel(kind: string): string {
  const labels: Record<string, string> = {
    cto: "CTO",
    ceo: "CEO",
    pole: "Poste",
    manhole: "Caixa subterrânea",
    pedestal: "Pedestal",
    rack: "Rack",
  };
  return labels[kind] ?? kind.toUpperCase();
}

export function DrawingModal({ open, draft, onClose, onSuccess }: DrawingModalProps) {
  const [submitting, setSubmitting] = React.useState(false);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);

  // Campos de Ponto
  const [code, setCode] = React.useState("");
  const [name, setName] = React.useState("");
  const [statusVal, setStatusVal] = React.useState("installed");
  const [pointCoords, setPointCoords] = React.useState<[number, number]>([0, 0]);

  // Campos de Cabo
  const [cablesList, setCablesList] = React.useState<CableRead[]>([]);
  const [structuresList, setStructuresList] = React.useState<StructureRead[]>([]);
  const [loadingAssociations, setLoadingAssociations] = React.useState(false);
  const [selectedCableId, setSelectedCableId] = React.useState("");
  const [originStructureId, setOriginStructureId] = React.useState("");
  const [destStructureId, setDestStructureId] = React.useState("");
  const [measuredLength, setMeasuredLength] = React.useState<string>("");
  const [slackLength, setSlackLength] = React.useState<string>("10");
  const [cableVertices, setCableVertices] = React.useState<[number, number][]>([]);

  // Carrega cabos e todas as estruturas que podem ocupar as pontas do trecho.
  React.useEffect(() => {
    if (!open || draft?.mode !== "draw_cable") return;

    let cancelled = false;
    setLoadingAssociations(true);

    Promise.all([listCables({ page_size: 200 }), loadAllStructures()])
      .then(([cablesResponse, structures]) => {
        if (cancelled) return;
        setCablesList(cablesResponse.items);
        setStructuresList(
          structures.sort((a, b) => {
            if (a.kind === "cto" && b.kind !== "cto") return -1;
            if (a.kind !== "cto" && b.kind === "cto") return 1;
            return a.code.localeCompare(b.code, "pt-BR");
          })
        );
        setSelectedCableId(cablesResponse.items[0]?.id ?? "");
      })
      .catch(() => {
        if (!cancelled) {
          setErrorMsg("Não foi possível carregar os cabos e estruturas disponíveis.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingAssociations(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, draft?.mode]);

  // Inicializa dados com base no rascunho
  React.useEffect(() => {
    if (draft && open) {
      setErrorMsg(null);
      if (draft.mode === "draw_point" && draft.coordinates.length > 0) {
        setPointCoords(draft.coordinates[0]);
        const prefix =
          draft.pointKind === "site"
            ? "POP"
            : draft.pointKind === "cto"
            ? "CTO"
            : draft.pointKind === "ceo"
            ? "CEO"
            : "POSTE";
        setCode(`${prefix}-${Math.floor(100 + Math.random() * 900)}`);
        setName(draft.pointKind === "site" ? "Estação Central" : "");
      } else if (draft.mode === "draw_cable") {
        setCableVertices(draft.coordinates);
        setOriginStructureId(draft.originStructureId ?? "");
        setDestStructureId(draft.destinationStructureId ?? "");
        setMeasuredLength("");
        setSlackLength("10");
      }
    }
  }, [draft, open]);

  if (!open || !draft) return null;

  const isPoint = draft.mode === "draw_point";
  const isCable = draft.mode === "draw_cable";

  // Cálculo geodésico do comprimento do mapa
  const mapLengthMeters = isCable ? calculateLineLength(cableVertices) : 0;
  const parsedMeasured = parseFloat(measuredLength.replace(",", "."));
  const parsedSlack = parseFloat(slackLength.replace(",", ".")) || 0;
  const effectiveLengthMeters = !isNaN(parsedMeasured) && parsedMeasured > 0
    ? parsedMeasured
    : Math.round((mapLengthMeters + parsedSlack) * 10) / 10;

  const associateStructure = (endpoint: "origin" | "destination", structureId: string) => {
    if (endpoint === "origin") {
      setOriginStructureId(structureId);
    } else {
      setDestStructureId(structureId);
    }

    const structure = structuresList.find((item) => item.id === structureId);
    if (!structure) return;

    // A API exige que as pontas da geometria coincidam com as estruturas associadas.
    // Ao selecionar uma CTO/CEO/poste, encaixa a extremidade exatamente no ponto cadastrado.
    setCableVertices((current) => {
      if (current.length < 2) return current;
      const next = [...current];
      const coordinates = structure.location.coordinates as [number, number];
      if (endpoint === "origin") {
        next[0] = coordinates;
      } else {
        next[next.length - 1] = coordinates;
      }
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg(null);

    try {
      if (isPoint) {
        if (!code.trim()) {
          throw new Error("O código de identificação é obrigatório.");
        }

        if (draft.pointKind === "site") {
          const site = await createSite({
            code: code.trim(),
            name: name.trim() || code.trim(),
            kind: "pop",
            status: statusVal,
            location: {
              type: "Point",
              coordinates: pointCoords,
            },
          });
          onSuccess(site.id);
        } else {
          const structure = await createStructure({
            code: code.trim(),
            kind: draft.pointKind ?? "cto",
            status: statusVal,
            location: {
              type: "Point",
              coordinates: pointCoords,
            },
          });
          onSuccess(structure.id);
        }
      } else if (isCable) {
        if (!selectedCableId) {
          throw new Error("Selecione um cabo óptico associado.");
        }
        if (!originStructureId.trim() || !destStructureId.trim()) {
          throw new Error("As estruturas de origem e destino devem ser informadas.");
        }
        if (originStructureId === destStructureId) {
          throw new Error("A origem e o destino devem ser estruturas diferentes.");
        }

        const segment = await createCableSegment({
          cable_id: selectedCableId,
          origin_structure_id: originStructureId.trim(),
          destination_structure_id: destStructureId.trim(),
          geometry: {
            type: "LineString",
            coordinates: cableVertices,
          },
          measured_length_m: !isNaN(parsedMeasured) && parsedMeasured > 0 ? parsedMeasured : null,
          slack_length_m: parsedSlack,
        });

        onSuccess(segment.id);
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorMsg(err.detail || err.message);
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Ocorreu uma falha ao cadastrar a geometria no servidor.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="drawing-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in-0"
    >
      <div className="relative w-full max-w-lg rounded-xl border border-border bg-card shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        {/* Header do modal */}
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5 bg-muted/30">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              {isPoint ? (
                draft.pointKind === "site" ? (
                  <Building2 className="h-4 w-4" />
                ) : (
                  <Box className="h-4 w-4" />
                )
              ) : (
                <CableIcon className="h-4 w-4" />
              )}
            </div>
            <div>
              <h2 id="drawing-modal-title" className="text-sm font-bold text-foreground">
                {isPoint
                  ? `Cadastrar ${draft.pointKind?.toUpperCase()}`
                  : "Cadastrar Trecho de Cabo Óptico"}
              </h2>
              <p className="text-[11px] text-muted-foreground">
                Revisão geométrica e parâmetros técnicos para persistência
              </p>
            </div>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-7 w-7 p-0 rounded-full hover:bg-muted"
            aria-label="Fechar formulário"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Formulário com scroll */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4 overflow-y-auto text-xs flex-1">
          {errorMsg && (
            <div className="flex items-start gap-2 p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs">
              <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {isPoint && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="point-code">Código de Identificação *</Label>
                  <Input
                    id="point-code"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    required
                    placeholder="ex: CTO-01"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="point-status">Estado Operacional</Label>
                  <select
                    id="point-status"
                    value={statusVal}
                    onChange={(e) => setStatusVal(e.target.value)}
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    <option value="installed">Instalado / Ativo</option>
                    <option value="planned">Planejado / Projeto</option>
                    <option value="maintenance">Manutenção</option>
                  </select>
                </div>
              </div>

              {draft.pointKind === "site" && (
                <div className="space-y-1.5">
                  <Label htmlFor="site-name">Nome Amigável do POP</Label>
                  <Input
                    id="site-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="ex: Estação Central Matriz"
                  />
                </div>
              )}

              {/* Coordenadas com input acessível */}
              <div className="space-y-1.5 pt-1">
                <Label>Localização Geográfica (WGS-84)</Label>
                <CoordinateInput
                  value={{ lat: pointCoords[1], lon: pointCoords[0] }}
                  onChange={(coords) => {
                    if (coords.lon !== null && coords.lat !== null) {
                      setPointCoords([coords.lon, coords.lat]);
                    }
                  }}
                />
              </div>
            </>
          )}

          {isCable && (
            <>
              {/* Seleção do Cabo */}
              <div className="space-y-1.5">
                <Label htmlFor="cable-select">Cabo Óptico Pertencente *</Label>
                {cablesList.length > 0 ? (
                  <select
                    id="cable-select"
                    value={selectedCableId}
                    onChange={(e) => setSelectedCableId(e.target.value)}
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    {cablesList.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.code} — {c.model} ({c.fiber_count} FO)
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    id="cable-select"
                    value={selectedCableId}
                    onChange={(e) => setSelectedCableId(e.target.value)}
                    placeholder="UUID do Cabo Óptico"
                    required
                  />
                )}
              </div>

              {/* Estruturas de Origem e Destino */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="origin-struct">Estrutura Origem (A) *</Label>
                  <select
                    id="origin-struct"
                    value={originStructureId}
                    onChange={(e) => associateStructure("origin", e.target.value)}
                    disabled={loadingAssociations}
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                    required
                  >
                    <option value="">
                      {loadingAssociations ? "Carregando estruturas..." : "Selecione a origem"}
                    </option>
                    {structuresList.map((structure) => (
                      <option key={structure.id} value={structure.id}>
                        {structure.code} — {structureKindLabel(structure.kind)}
                      </option>
                    ))}
                  </select>
                  {draft.originStructureCode && (
                    <p className="text-[10px] text-primary">Snap: {draft.originStructureCode}</p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="dest-struct">Estrutura Destino (B) *</Label>
                  <select
                    id="dest-struct"
                    value={destStructureId}
                    onChange={(e) => associateStructure("destination", e.target.value)}
                    disabled={loadingAssociations}
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                    required
                  >
                    <option value="">
                      {loadingAssociations ? "Carregando estruturas..." : "Selecione o destino"}
                    </option>
                    {structuresList.map((structure) => (
                      <option key={structure.id} value={structure.id}>
                        {structure.code} — {structureKindLabel(structure.kind)}
                      </option>
                    ))}
                  </select>
                  {draft.destinationStructureCode && (
                    <p className="text-[10px] text-primary">Snap: {draft.destinationStructureCode}</p>
                  )}
                </div>
              </div>

              <p className="text-[10px] text-muted-foreground">
                Selecione as CTOs, CEOs ou postes das duas pontas. O traçado será encaixado
                automaticamente nas coordenadas das estruturas escolhidas.
              </p>

              {/* Painel Tripartido de Comprimentos Ópticos */}
              <div className="rounded-lg border border-border bg-muted/40 p-3 space-y-3">
                <div className="flex items-center justify-between text-muted-foreground font-medium">
                  <span>Métricas de Comprimento e Regra Óptica</span>
                  <span className="font-mono text-[11px] text-foreground font-semibold">
                    {cableVertices.length} vértices
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="rounded border border-border bg-background p-2">
                    <p className="font-bold text-foreground">{mapLengthMeters} m</p>
                    <p className="text-[10px] text-muted-foreground">Mapa (Geodésico)</p>
                  </div>
                  <div className="space-y-1 text-left">
                    <Label htmlFor="cable-measured" className="text-[10px]">Medido (Campo)</Label>
                    <UnitInput
                      id="cable-measured"
                      unit="m"
                      value={measuredLength}
                      onChange={(val) => setMeasuredLength(val)}
                      placeholder="Opcional"
                    />
                  </div>
                  <div className="space-y-1 text-left">
                    <Label htmlFor="cable-slack" className="text-[10px]">Reserva Técnica</Label>
                    <UnitInput
                      id="cable-slack"
                      unit="m"
                      value={slackLength}
                      onChange={(val) => setSlackLength(val)}
                      placeholder="10"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1 border-t border-border/50 text-[11px]">
                  <span className="flex items-center gap-1 text-muted-foreground">
                    <Info className="h-3 w-3" />
                    <span>Comprimento óptico efetivo adotado:</span>
                  </span>
                  <span className="font-mono font-bold text-primary">
                    {effectiveLengthMeters} metros
                  </span>
                </div>
              </div>
            </>
          )}

          {/* Rodapé do Modal */}
          <div className="pt-4 border-t border-border flex items-center justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onClose}
              disabled={submitting}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={submitting}
              className="gap-1.5 font-semibold"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Persistindo...</span>
                </>
              ) : (
                <>
                  <Check className="h-3.5 w-3.5" />
                  <span>Confirmar e Salvar</span>
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
