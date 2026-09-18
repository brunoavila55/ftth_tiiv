"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { listSegmentFibers, type CableRead, type CableSegmentRead } from "@/features/cables/api";
import { getFiberHierarchy, getColorForPosition } from "@/features/cables/utils/colors";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/ui/status-badge";
import { Layers } from "lucide-react";

export interface CableFibersViewProps {
  cable: CableRead;
  segments: CableSegmentRead[];
}

export function CableFibersView({ cable, segments }: CableFibersViewProps) {
  const [selectedSegmentId, setSelectedSegmentId] = React.useState<string>(
    segments[0]?.id || ""
  );
  const [tubeFilter, setTubeFilter] = React.useState<number | "all">("all");
  const [occupancyFilter, setOccupancyFilter] = React.useState<string>("all");

  React.useEffect(() => {
    if (segments.length > 0 && (!selectedSegmentId || !segments.some((s) => s.id === selectedSegmentId))) {
      setSelectedSegmentId(segments[0].id);
    }
  }, [segments, selectedSegmentId]);

  const {
    data: fibersData,
  } = useQuery({
    queryKey: ["cables", "segment-fibers", selectedSegmentId],
    queryFn: () => listSegmentFibers(selectedSegmentId, { page_size: 200 }),
    enabled: Boolean(selectedSegmentId),
  });

  // Agrupa fibras por número de tubo loose
  const fibersPerTube = Math.max(1, Math.ceil(cable.fiber_count / Math.max(1, cable.tube_count)));

  // Cria estrutura sintética de todos os tubos e fibras caso ainda não haja fibras cadastradas no segmento selecionado
  const tubesList = React.useMemo(() => {
    const list = [];
    for (let t = 1; t <= cable.tube_count; t++) {
      const tubeColor = getColorForPosition(t, cable.color_standard);
      list.push({
        number: t,
        color: tubeColor,
      });
    }
    return list;
  }, [cable]);

  // Lista consolidada de fibras combinando os dados da API com as regras de cores
  const consolidatedFibers = React.useMemo(() => {
    const fibers = fibersData?.items || [];
    const result = [];
    for (let globalNum = 1; globalNum <= cable.fiber_count; globalNum++) {
      const hierarchy = getFiberHierarchy(
        globalNum,
        cable.fiber_count,
        cable.tube_count,
        cable.color_standard
      );

      // Procura dados do segmento se disponível
      const segmentFiber = fibers.find((f) => f.fiber_number === globalNum);

      result.push({
        globalNumber: globalNum,
        tubeNumber: hierarchy.tubeNumber,
        fiberPositionInTube: hierarchy.fiberPositionInTube,
        tubeColor: hierarchy.tubeColor,
        fiberColor: hierarchy.fiberColor,
        occupancy: segmentFiber?.occupancy || "free",
        terminalA: segmentFiber?.terminal_a_id || null,
        terminalB: segmentFiber?.terminal_b_id || null,
      });
    }
    return result;
  }, [cable, fibersData?.items]);

  // Aplica filtros
  const filteredFibers = React.useMemo(() => {
    return consolidatedFibers.filter((f) => {
      if (tubeFilter !== "all" && f.tubeNumber !== tubeFilter) return false;
      if (occupancyFilter !== "all" && f.occupancy !== occupancyFilter) return false;
      return true;
    });
  }, [consolidatedFibers, tubeFilter, occupancyFilter]);

  // Agrupamento final por tubo filtrado
  const groupedByTube = React.useMemo(() => {
    const map = new Map<number, typeof filteredFibers>();
    filteredFibers.forEach((f) => {
      const arr = map.get(f.tubeNumber) || [];
      arr.push(f);
      map.set(f.tubeNumber, arr);
    });
    return map;
  }, [filteredFibers]);

  return (
    <div className="space-y-4">
      {/* Seletor de Segmento e Filtros */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-muted/30 p-3 rounded-lg border border-border">
        {segments.length > 0 ? (
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary shrink-0" />
            <label htmlFor="segment-select" className="text-xs font-semibold shrink-0">
              Trecho (Segmento):
            </label>
            <select
              id="segment-select"
              value={selectedSegmentId}
              onChange={(e) => setSelectedSegmentId(e.target.value)}
              className="h-8 rounded-md border border-input bg-background px-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {segments.map((seg, idx) => (
                <option key={seg.id} value={seg.id}>
                  Trecho {idx + 1} — {seg.effective_length_m.toFixed(1)}m ({seg.length_source})
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="text-xs text-muted-foreground italic">
            Nenhum trecho geográfico cadastrado para este cabo. Exibindo estrutura nominal de fábrica.
          </div>
        )}

        <div className="flex items-center gap-2">
          {/* Filtro por Tubo Loose */}
          <select
            value={tubeFilter}
            onChange={(e) => setTubeFilter(e.target.value === "all" ? "all" : Number(e.target.value))}
            className="h-8 rounded-md border border-input bg-background px-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            aria-label="Filtrar por tubo loose"
          >
            <option value="all">Todos os Tubos</option>
            {tubesList.map((t) => (
              <option key={t.number} value={t.number}>
                Tubo {t.number} ({t.color.name})
              </option>
            ))}
          </select>

          {/* Filtro por Ocupação */}
          <select
            value={occupancyFilter}
            onChange={(e) => setOccupancyFilter(e.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            aria-label="Filtrar por ocupação"
          >
            <option value="all">Todas as Ocupações</option>
            <option value="free">Livre</option>
            <option value="reserved">Reservada</option>
            <option value="connected">Conectada</option>
          </select>
        </div>
      </div>

      {/* Exibição dos Tubos Loose e Fibras */}
      {groupedByTube.size > 0 ? (
        <div className="space-y-4">
          {Array.from(groupedByTube.entries()).map(([tubeNum, tubeFibers]) => {
            const tubeColor = getColorForPosition(tubeNum, cable.color_standard);
            return (
              <div
                key={tubeNum}
                className="rounded-lg border border-border bg-card overflow-hidden shadow-sm"
              >
                {/* Cabeçalho do Tubo Loose com Swatch e Cor */}
                <div className="flex items-center justify-between px-4 py-2.5 bg-muted/50 border-b border-border">
                  <div className="flex items-center gap-2.5">
                    <span
                      className="h-4 w-4 rounded-full border border-border shadow-sm shrink-0"
                      style={{
                        backgroundColor: tubeColor.hex,
                        borderColor: tubeColor.border || tubeColor.hex,
                      }}
                      aria-hidden="true"
                    />
                    <span className="text-xs font-bold text-foreground">
                      Tubo Loose {tubeNum}: Cor {tubeColor.name}
                    </span>
                    <span className="text-[11px] text-muted-foreground">
                      ({tubeFibers.length} de {fibersPerTube} fibras)
                    </span>
                  </div>

                  <Badge variant="outline" className="text-[10px] font-mono">
                    Norma {cable.color_standard}
                  </Badge>
                </div>

                {/* Grid de Fibras do Tubo */}
                <div className="p-3 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2.5">
                  {tubeFibers.map((fiber) => (
                    <div
                      key={fiber.globalNumber}
                      className="flex items-center justify-between p-2 rounded-md border border-border bg-background hover:bg-muted/20 transition-colors text-xs"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        {/* Swatch de cor da fibra */}
                        <span
                          className="h-3.5 w-3.5 rounded-full border shrink-0"
                          style={{
                            backgroundColor: fiber.fiberColor.hex,
                            borderColor: fiber.fiberColor.border || fiber.fiberColor.hex,
                          }}
                          title={`Cor: ${fiber.fiberColor.name}`}
                          aria-hidden="true"
                        />
                        <div className="truncate">
                          <p className="font-mono font-bold text-foreground">
                            FO #{fiber.globalNumber}
                          </p>
                          <p className="text-[10px] text-muted-foreground truncate">
                            {fiber.fiberColor.name} (Tubo {fiber.tubeNumber}.{fiber.fiberPositionInTube})
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <StatusBadge
                          status={
                            fiber.occupancy === "connected"
                              ? "connected"
                              : fiber.occupancy === "reserved"
                              ? "reserved"
                              : "free"
                          }
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border p-8 text-center text-xs text-muted-foreground">
          Nenhuma fibra atende aos filtros selecionados.
        </div>
      )}
    </div>
  );
}
