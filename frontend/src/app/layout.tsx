import type { Metadata } from "next";
import { headers } from "next/headers";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

// O CSP com nonce é gerado por requisição (src/middleware.ts): o Next só aplica o nonce aos seus
// scripts em renderização dinâmica.
export const dynamic = "force-dynamic";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "FTTH Manager",
  description: "Sistema open source de documentação física e óptica de rede FTTH",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Nonce desta resposta (definido em src/middleware.ts): o script inline do next-themes o exige
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers nonce={nonce}>{children}</Providers>
      </body>
    </html>
  );
}
