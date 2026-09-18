export function formatMeters(
  val: number | null | undefined,
  options?: { showKm?: boolean }
): string {
  if (val === null || val === undefined) {
    return "Não informado";
  }

  if (options?.showKm) {
    const km = val / 1000;
    const formatted = km.toLocaleString("pt-BR", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 3,
    });
    return `${formatted} km`;
  }

  const formatted = val.toLocaleString("pt-BR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
  return `${formatted} m`;
}

export function formatLossDb(val: number | null | undefined): string {
  if (val === null || val === undefined) {
    return "Não informado";
  }

  const formatted = val.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${formatted} dB`;
}

export function formatPowerDbm(val: number | null | undefined): string {
  if (val === null || val === undefined) {
    return "Não informado";
  }

  const sign = val > 0 ? "+" : "";
  const formatted = val.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${sign}${formatted} dBm`;
}

export function formatWavelength(val: number | null | undefined): string {
  if (val === null || val === undefined) {
    return "Não informado";
  }

  return `${val} nm`;
}
