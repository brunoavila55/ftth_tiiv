#!/usr/bin/env node
// MapLibre GL v6 exige setWorkerUrl() em bundlers (webpack/Next.js): a resolução automática via
// import.meta.url não funciona dentro do grafo de módulos do webpack. O worker (maplibre-gl-worker.mjs)
// importa por caminho relativo o seu companheiro maplibre-gl-shared.mjs — os dois precisam ser
// servidos juntos, do mesmo diretório. Copiamos ambos para public/ (mesma origem) antes de
// dev/build; ver setWorkerUrl() em operational-map.tsx.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const srcDir = join(__dirname, "..", "node_modules", "maplibre-gl", "dist");
const destDir = join(__dirname, "..", "public", "maplibre");

mkdirSync(destDir, { recursive: true });

for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(join(srcDir, file), join(destDir, file));
}

console.log(`[copy-maplibre-worker] copiado para ${destDir}`);
