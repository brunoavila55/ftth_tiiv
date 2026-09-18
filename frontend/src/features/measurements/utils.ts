import type { MeasurementDirection, MeasurementOrigin } from "./types";

/**
 * Formata potência óptica em dBm no padrão pt-BR, preservando o sinal explícito (+/-).
 * Regra estrita F13/F14: Null ou undefined NUNCA vira zero.
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
 * Formata perda excedente em dB com sinal explícito.
 * Perda excedente positiva (+6,10 dB) indica que o medidor recebeu menos luz que o previsto.
 * Null ou undefined NUNCA vira zero.
 */
export function formatExcessLossDb(value: number | null | undefined): string {
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
 * Formata atenuação em dB simples.
 */
export function formatLossDb(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) {
    return "—";
  }
  return `${value.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} dB`;
}

/**
 * Formata data e hora ISO para exibição amigável pt-BR com timestamp visível.
 */
export function formatDateTime(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return new Intl.DateTimeFormat("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(d);
  } catch {
    return isoString;
  }
}

export function getOriginLabel(origin: MeasurementOrigin): string {
  switch (origin) {
    case "field_power_meter":
      return "Power Meter de Campo";
    case "otdr":
      return "Reflectômetro (OTDR)";
    case "manual_entry":
    default:
      return "Leitura Manual";
  }
}

export function getDirectionLabel(dir: MeasurementDirection): string {
  switch (dir) {
    case "downstream":
      return "Downstream (OLT → Cliente)";
    case "upstream":
      return "Upstream (Cliente → OLT)";
    default:
      return dir;
  }
}
