"use client";

import * as React from "react";
import {
  MousePointer,
  MapPin,
  Cable as CableIcon,
  Edit3,
  Undo2,
  Redo2,
  XCircle,
  CheckCircle,
  Magnet,
  ChevronDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { MapInteractionMode, PointKind } from "../types";
import type { SnapCandidate } from "../utils/geometry";

export interface DrawingToolbarProps {
  mode: MapInteractionMode;
  pointKind?: PointKind;
  verticesCount: number;
  canUndo: boolean;
  canRedo: boolean;
  currentLengthMeters: number;
  snapCandidate: SnapCandidate | null;
  onSetMode: (mode: MapInteractionMode, pointKind?: PointKind) => void;
  onUndo: () => void;
  onRedo: () => void;
  onCancel: () => void;
  onFinish: () => void;
}

export function DrawingToolbar({
  mode,
  pointKind,
  verticesCount,
  canUndo,
  canRedo,
  currentLengthMeters,
  snapCandidate,
  onSetMode,
  onUndo,
  onRedo,
  onCancel,
  onFinish,
}: DrawingToolbarProps) {
  const [pointMenuOpen, setPointMenuOpen] = React.useState(false);

  const isDrawing = mode !== "view";
  // Instrução contextual dinâmica
  let instruction = "Modo de navegação e consulta de ativos.";
  if (mode === "draw_point") {
    const label =
      pointKind === "site"
        ? "POP / Site"
        : pointKind === "cto"
        ? "CTO"
        : pointKind === "ceo"
        ? "CEO"
        : "Poste";
    instruction = `Clique no mapa para posicionar ${label}.`;
  } else if (mode === "draw_cable") {
    if (verticesCount === 0) {
      instruction = "Clique em um ponto ou no mapa para iniciar o traçado do cabo.";
    } else {
      instruction = `Adicionando vértices (${verticesCount} pontos, ~${currentLengthMeters}m). Clique duplo ou 'Finalizar' para concluir.`;
    }
  } else if (mode === "edit_geometry") {
    instruction = "Arraste os vértices para reajustar o traçado do cabo óptico.";
  }

  return (
    <div
      role="toolbar"
      aria-label="Ferramentas de desenho geográfico"
      className="absolute top-4 left-1/2 z-20 flex max-w-[calc(100vw-1rem)] -translate-x-1/2 flex-col items-center gap-1.5"
    >
      {/* Barra principal de botões */}
      <div className="flex max-w-full flex-wrap items-center justify-center gap-1.5 overflow-visible rounded-xl border border-border bg-card/95 p-1.5 text-xs shadow-2xl backdrop-blur-md">
        {/* Botão Modo Navegar */}
        <Button
          variant={mode === "view" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => {
            setPointMenuOpen(false);
            onSetMode("view");
          }}
          className="h-8 px-2.5 gap-1.5 font-medium"
          aria-pressed={mode === "view"}
          title="Modo de navegação e inspeção"
        >
          <MousePointer className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Navegar</span>
        </Button>

        {/* Menu Criar Ponto */}
        <div className="relative">
          <Button
            variant={mode === "draw_point" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setPointMenuOpen(!pointMenuOpen)}
            className="h-8 px-2.5 gap-1 font-medium"
            aria-pressed={mode === "draw_point"}
            aria-haspopup="menu"
            aria-expanded={pointMenuOpen}
            title="Adicionar POP, CTO, Poste ou CEO"
          >
            <MapPin className="h-3.5 w-3.5 text-primary" />
            <span className="hidden sm:inline">
              {mode === "draw_point" ? `Ponto (${pointKind?.toUpperCase()})` : "Criar Ponto"}
            </span>
            <ChevronDown className="h-3 w-3 opacity-60" />
          </Button>

          {pointMenuOpen && (
            <div
              role="menu"
              aria-label="Tipo de ponto"
              className="absolute top-full left-0 mt-1.5 w-40 rounded-lg border border-border bg-card p-1 shadow-xl z-30 animate-in fade-in-0 zoom-in-95"
            >
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  onSetMode("draw_point", "cto");
                  setPointMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-foreground hover:bg-accent"
              >
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                <span>CTO (Terminação)</span>
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  onSetMode("draw_point", "pole");
                  setPointMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-foreground hover:bg-accent"
              >
                <span className="h-2.5 w-2.5 rounded-full bg-slate-500" />
                <span>Poste / Suporte</span>
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  onSetMode("draw_point", "site");
                  setPointMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-foreground hover:bg-accent"
              >
                <span className="h-2.5 w-2.5 rounded-full bg-sky-600" />
                <span>POP / Site Central</span>
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  onSetMode("draw_point", "ceo");
                  setPointMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-foreground hover:bg-accent"
              >
                <span className="h-2.5 w-2.5 rounded-full bg-violet-600" />
                <span>CEO (Emenda)</span>
              </button>
            </div>
          )}
        </div>

        {/* Botão Traçar Cabo */}
        <Button
          variant={mode === "draw_cable" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => {
            setPointMenuOpen(false);
            onSetMode("draw_cable");
          }}
          className="h-8 px-2.5 gap-1.5 font-medium"
          aria-pressed={mode === "draw_cable"}
          title="Desenhar trecho de cabo óptico"
        >
          <CableIcon className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
          <span className="hidden sm:inline">Traçar Cabo</span>
        </Button>

        {/* Botão Editar Vértices */}
        <Button
          variant={mode === "edit_geometry" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => {
            setPointMenuOpen(false);
            onSetMode("edit_geometry");
          }}
          className="h-8 px-2.5 gap-1.5 font-medium"
          aria-pressed={mode === "edit_geometry"}
          title="Editar vértices de geometria"
        >
          <Edit3 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
          <span className="hidden sm:inline">Editar</span>
        </Button>

        {/* Separador se estiver em modo de desenho */}
        {isDrawing && <div className="h-5 w-[1px] bg-border mx-1" />}

        {/* Controles de Ação de Desenho */}
        {isDrawing && (
          <>
            <Button
              variant="ghost"
              size="sm"
              onClick={onUndo}
              disabled={!canUndo}
              className="h-8 w-8 p-0"
              title="Desfazer último vértice (Ctrl+Z)"
              aria-label="Desfazer"
            >
              <Undo2 className="h-3.5 w-3.5" />
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={onRedo}
              disabled={!canRedo}
              className="h-8 w-8 p-0"
              title="Refazer vértice"
              aria-label="Refazer"
            >
              <Redo2 className="h-3.5 w-3.5" />
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={onCancel}
              className="h-8 px-2 gap-1 text-destructive hover:bg-destructive/10 hover:text-destructive"
              title="Cancelar desenho (Esc)"
              aria-label="Cancelar desenho"
            >
              <XCircle className="h-3.5 w-3.5" />
              <span>Cancelar</span>
            </Button>

            <Button
              variant="default"
              size="sm"
              onClick={onFinish}
              disabled={
                (mode === "draw_cable" && verticesCount < 2) ||
                (mode === "draw_point" && verticesCount === 0)
              }
              className="h-8 px-3 gap-1.5 font-semibold shadow-sm"
              title="Concluir traçado e associar as estruturas"
              aria-label="Concluir traçado"
            >
              <CheckCircle className="h-3.5 w-3.5" />
              <span>Concluir</span>
            </Button>
          </>
        )}
      </div>

      {/* Caixa Flutuante de Instruções e Snap Info */}
      {isDrawing && (
        <div className="flex items-center gap-2 rounded-full border border-border/70 bg-card/90 px-3.5 py-1 text-[11px] shadow-lg backdrop-blur-sm animate-in fade-in">
          <span className="text-muted-foreground">{instruction}</span>

          {snapCandidate && (
            <Badge
              variant="secondary"
              className="gap-1 py-0 h-4 font-mono text-[10px] bg-primary/10 text-primary border-primary/20"
            >
              <Magnet className="h-2.5 w-2.5" />
              <span>Snap: {snapCandidate.code}</span>
            </Badge>
          )}
        </div>
      )}
    </div>
  );
}
