export interface ColorDef {
  name: string;
  enName?: string;
  hex: string;
  border?: string;
  textDark?: boolean;
}

export const NBR_COLORS: ColorDef[] = [
  { name: "Verde", enName: "Green", hex: "#16a34a" },
  { name: "Amarelo", enName: "Yellow", hex: "#eab308", textDark: true },
  { name: "Branco", enName: "White", hex: "#ffffff", border: "#94a3b8", textDark: true },
  { name: "Azul", enName: "Blue", hex: "#2563eb" },
  { name: "Vermelho", enName: "Red", hex: "#dc2626" },
  { name: "Violeta", enName: "Violet", hex: "#7c3aed" },
  { name: "Marrom", enName: "Brown", hex: "#78350f" },
  { name: "Rosa", enName: "Rose", hex: "#f43f5e" },
  { name: "Preto", enName: "Black", hex: "#0f172a" },
  { name: "Cinza", enName: "Slate", hex: "#64748b" },
  { name: "Laranja", enName: "Orange", hex: "#ea580c" },
  { name: "Aqua", enName: "Aqua", hex: "#06b6d4" },
];

export const TIA_598_COLORS: ColorDef[] = [
  { name: "Azul", enName: "Blue", hex: "#2563eb" },
  { name: "Laranja", enName: "Orange", hex: "#ea580c" },
  { name: "Verde", enName: "Green", hex: "#16a34a" },
  { name: "Marrom", enName: "Brown", hex: "#78350f" },
  { name: "Cinza", enName: "Slate", hex: "#64748b" },
  { name: "Branco", enName: "White", hex: "#ffffff", border: "#94a3b8", textDark: true },
  { name: "Vermelho", enName: "Red", hex: "#dc2626" },
  { name: "Preto", enName: "Black", hex: "#0f172a" },
  { name: "Amarelo", enName: "Yellow", hex: "#eab308", textDark: true },
  { name: "Violeta", enName: "Violet", hex: "#7c3aed" },
  { name: "Rosa", enName: "Rose", hex: "#f43f5e" },
  { name: "Aqua", enName: "Aqua", hex: "#06b6d4" },
];

/**
 * Retorna a definição de cor para um número ordinal (1-indexado) conforme o padrão
 */
export function getColorForPosition(
  position: number,
  standard: "NBR" | "TIA-598" | string = "NBR"
): ColorDef {
  const palette = standard.toUpperCase() === "TIA-598" ? TIA_598_COLORS : NBR_COLORS;
  const index = (position - 1) % palette.length;
  return palette[index] || palette[0];
}

/**
 * Calcula tubo e posição no tubo para uma fibra global
 */
export function getFiberHierarchy(
  globalNumber: number,
  totalFibers: number,
  totalTubes: number,
  standard: string = "NBR"
) {
  const fibersPerTube = Math.max(1, Math.ceil(totalFibers / Math.max(1, totalTubes)));
  const tubeNumber = Math.floor((globalNumber - 1) / fibersPerTube) + 1;
  const fiberPositionInTube = ((globalNumber - 1) % fibersPerTube) + 1;

  const tubeColor = getColorForPosition(tubeNumber, standard);
  const fiberColor = getColorForPosition(fiberPositionInTube, standard);

  return {
    tubeNumber,
    fiberPositionInTube,
    tubeColor,
    fiberColor,
  };
}
