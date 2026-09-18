import type { BudgetAssessment } from "./types";

/**
 * Formata potência óptica em dBm no padrão pt-BR, preservando o sinal explícito (+/-).
 * Regra estrita F13: Null ou undefined NUNCA vira zero.
 */
export function formatPowerDbm(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) {
    return "—";
  }
  const formatted = Math.abs(value).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const sign = value >= 0 ? "+" : "-";
  return `${sign}${formatted} dBm`;
}

/**
 * Formata atenuação / perda óptica em dB no padrão pt-BR.
 * Null ou undefined NUNCA vira zero.
 */
export function formatLossDb(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) {
    return "—";
  }
  const formatted = value.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${formatted} dB`;
}

/**
 * Formata margem de segurança ou folga em dB, preservando o sinal (+/-).
 */
export function formatMarginDb(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) {
    return "—";
  }
  const formatted = Math.abs(value).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const sign = value >= 0 ? "+" : "-";
  return `${sign}${formatted} dB`;
}

/**
 * Formata distância óptica em m ou km de forma legível.
 */
export function formatDistance(meters: number | null | undefined): string {
  if (meters === null || meters === undefined || isNaN(meters)) {
    return "—";
  }
  if (meters >= 1000) {
    const km = meters / 1000.0;
    return `${km.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} km`;
  }
  return `${meters.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} m`;
}

export interface AssessmentConfig {
  label: string;
  badgeClass: string;
  variant: "default" | "secondary" | "destructive" | "outline";
  description: string;
}

export const ASSESSMENT_CONFIGS: Record<BudgetAssessment, AssessmentConfig> = {
  pass: {
    label: "Aprovado",
    badgeClass: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30",
    variant: "default",
    description: "Enlace aprovado: nível de sinal seguro, acima da sensibilidade e com margem de engenharia preservada.",
  },
  low_margin: {
    label: "Margem Baixa",
    badgeClass: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30",
    variant: "secondary",
    description: "Potência prevista atinge a sensibilidade do receptor, porém viola a margem de segurança de engenharia de projeto.",
  },
  below_sensitivity: {
    label: "Abaixo da Sensibilidade",
    badgeClass: "bg-rose-500/15 text-rose-700 dark:text-rose-400 border-rose-500/30",
    variant: "destructive",
    description: "Sinal óptico insuficiente na recepção. O enlace ficará inoperante ou instável sob condições de degradação.",
  },
  overload: {
    label: "Sobrecarga / Saturação",
    badgeClass: "bg-purple-500/15 text-purple-700 dark:text-purple-400 border-purple-500/30",
    variant: "destructive",
    description: "Potência excessiva que excede o limite máximo de saturação do fotodiodo receptor.",
  },
  unknown: {
    label: "Dados Insuficientes",
    badgeClass: "bg-slate-500/15 text-slate-700 dark:text-slate-400 border-slate-500/30",
    variant: "outline",
    description: "Não foi possível concluir o cálculo devido a parâmetros ausentes ou circuito óptico sem continuidade documentada.",
  },
};
