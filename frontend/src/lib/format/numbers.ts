export class NumberFormatError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NumberFormatError";
  }
}

export function isStrictZero(val: unknown): boolean {
  if (val === 0) return true;
  if (typeof val === "string") {
    const trimmed = val.trim();
    if (!trimmed) return false;
    // Checks if after replacing comma it parses to strictly 0
    const normalized = trimmed.replace(/\./g, "").replace(",", ".");
    const parsed = Number(normalized);
    return !Number.isNaN(parsed) && parsed === 0;
  }
  return false;
}

export function parsePtBrNumber(val: string | number | null | undefined): number | null {
  if (val === null || val === undefined) {
    return null;
  }

  if (typeof val === "number") {
    if (Number.isNaN(val)) return null;
    return val;
  }

  const trimmed = val.trim();
  if (trimmed === "") {
    return null;
  }

  // Check for Brazilian format: e.g. 1.234,56 or 10.500,75
  if (/^-?\d{1,3}(\.\d{3})+(,\d+)?$/.test(trimmed)) {
    const normalized = trimmed.replace(/\./g, "").replace(",", ".");
    const parsed = Number(normalized);
    if (Number.isNaN(parsed)) {
      throw new NumberFormatError(`Formato numérico inválido: "${val}"`);
    }
    return parsed;
  }

  // Check for comma decimal without thousand separators: e.g. 12,5 or -23,5505
  if (/^-?\d+(,\d+)?$/.test(trimmed)) {
    const normalized = trimmed.replace(",", ".");
    const parsed = Number(normalized);
    if (Number.isNaN(parsed)) {
      throw new NumberFormatError(`Formato numérico inválido: "${val}"`);
    }
    return parsed;
  }

  // Check for standard decimal point: e.g. 12.5 or 100.0 or 0
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
    const parsed = Number(trimmed);
    if (Number.isNaN(parsed)) {
      throw new NumberFormatError(`Formato numérico inválido: "${val}"`);
    }
    return parsed;
  }

  throw new NumberFormatError(`Formato numérico inválido: "${val}"`);
}

export interface FormatPtBrNumberOptions {
  minDecimals?: number;
  maxDecimals?: number;
}

export function formatPtBrNumber(
  val: number | null | undefined,
  options?: FormatPtBrNumberOptions
): string {
  if (val === null || val === undefined || Number.isNaN(val)) {
    return "—";
  }

  const minDecimals = options?.minDecimals;
  const maxDecimals = options?.maxDecimals;

  if (minDecimals === undefined && maxDecimals === undefined) {
    // Return standard pt-BR formatting with comma
    const parts = val.toString().split(".");
    const intPart = parts[0];
    const decPart = parts[1];
    return decPart ? `${intPart},${decPart}` : intPart;
  }

  return val.toLocaleString("pt-BR", {
    minimumFractionDigits: minDecimals ?? 0,
    maximumFractionDigits: maxDecimals ?? 20,
  });
}
