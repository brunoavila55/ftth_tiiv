import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import * as React from "react";
import { ApiClient } from "@/lib/api/client";
import { ApiError } from "@/lib/api/types";
import { ConnectionStatusBanner } from "@/components/layout/connection-status-banner";
import { useNetworkStatus } from "@/lib/hooks/use-network-status";
import { FiberColorBadge } from "@/features/cables/components/fiber-color-badge";
import { CopyableCoordinates } from "@/components/ui/copyable-coordinates";
import { MapFallbackTable } from "@/features/map/components/map-fallback-table";
import { AppShell } from "@/components/layout/app-shell";

// Mock de autenticação para AppShell
vi.mock("@/features/auth/auth-context", () => ({
  useAuth: () => ({
    user: { id: "u-1", name: "Operador de Campo", role: "technician" },
    logout: vi.fn(),
  }),
}));

// Mock de navegação Next.js
vi.mock("next/navigation", () => ({
  usePathname: () => "/map",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("F18 — Campo, Acessibilidade e Desempenho", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("1. Conectividade de Campo & Proteção contra Falso Salvo", () => {
    it("bloqueia mutações via ApiClient quando navigator.onLine é falso e lança ApiError amigável", async () => {
      const client = new ApiClient("/api/v1");

      // Simula modo offline
      vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);

      await expect(client.post("/structures", { name: "CTO Nova" })).rejects.toThrow(ApiError);

      try {
        await client.post("/structures", { name: "CTO Nova" });
      } catch (err) {
        const apiErr = err as ApiError;
        expect(apiErr.title).toBe("Sem conexão de rede");
        expect(apiErr.detail).toContain("As alterações e rascunhos foram mantidos em memória");
      }
    });

    it("permite requisições quando navigator.onLine é verdadeiro", async () => {
      const client = new ApiClient("/api/v1");
      vi.spyOn(navigator, "onLine", "get").mockReturnValue(true);

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ id: "cto-123" }),
      });

      const res = await client.post("/structures", { name: "CTO Online" });
      expect(res).toEqual({ id: "cto-123" });
    });

    it("exibe banner de alerta acessível (role=alert, aria-live=assertive) quando a rede cai", () => {
      vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);

      render(<ConnectionStatusBanner />);

      const banner = screen.getByRole("alert");
      expect(banner).toBeDefined();
      expect(screen.getByText(/Sem conexão de rede/i)).toBeDefined();
      expect(screen.getByText(/Rascunhos mantidos em memória/i)).toBeDefined();
    });

    it("limpa event listeners no unmount do hook useNetworkStatus sem memory leaks", () => {
      const addSpy = vi.spyOn(window, "addEventListener");
      const removeSpy = vi.spyOn(window, "removeEventListener");

      function TestComponent() {
        const { isOnline } = useNetworkStatus();
        return <div>{isOnline ? "online" : "offline"}</div>;
      }

      const { unmount } = render(<TestComponent />);

      expect(addSpy).toHaveBeenCalledWith("online", expect.any(Function));
      expect(addSpy).toHaveBeenCalledWith("offline", expect.any(Function));

      unmount();

      expect(removeSpy).toHaveBeenCalledWith("online", expect.any(Function));
      expect(removeSpy).toHaveBeenCalledWith("offline", expect.any(Function));
    });
  });

  describe("2. Acessibilidade para Daltonismo (Cores de Fibra com Nome e Número)", () => {
    it("renderiza FiberColorBadge com número da fibra, swatch e nome da cor por extenso (NBR)", () => {
      render(<FiberColorBadge fiberNumber={1} standard="NBR" />);

      // Deve exibir número e nome da cor (Verde para #1 na NBR)
      expect(screen.getByText("FO #1")).toBeDefined();
      expect(screen.getByText("(Verde)")).toBeDefined();

      const badge = screen.getByTitle(/Fibra #1, Cor Verde, Norma NBR/i);
      expect(badge).toBeDefined();
      expect(badge.getAttribute("aria-label")).toContain("Cor Verde");
    });

    it("renderiza FiberColorBadge com número da fibra e nome da cor para TIA-598", () => {
      // Na TIA-598, a fibra #1 é Azul e #2 é Laranja
      render(<FiberColorBadge fiberNumber={2} standard="TIA-598" />);

      expect(screen.getByText("FO #2")).toBeDefined();
      expect(screen.getByText("(Laranja)")).toBeDefined();
      expect(screen.getByTitle(/Fibra #2, Cor Laranja, Norma TIA-598/i)).toBeDefined();
    });

    it("renderiza hierarquia completa tubo-fibra quando solicitado", () => {
      render(
        <FiberColorBadge
          fiberNumber={13}
          standard="NBR"
          totalFibers={24}
          totalTubes={2}
          showTube={true}
        />
      );

      // Fibra 13 em cabo 24FO / 2 tubos pertence ao Tubo 2, Fibra 1 (Verde)
      expect(screen.getByText("FO #13")).toBeDefined();
      expect(screen.getByText("(Verde)")).toBeDefined();
      expect(screen.getByText(/Tubo 2/i)).toBeDefined();
    });
  });

  describe("3. Coordenadas Copiáveis e Navegação de Campo", () => {
    it("exibe latitude e longitude formatadas em WGS84", () => {
      render(
        <CopyableCoordinates
          latitude={-23.55052}
          longitude={-46.633308}
          entityId="struct-1"
        />
      );

      expect(screen.getByText(/Lat: -23.550520 \| Lon: -46.633308/i)).toBeDefined();
    });

    it("copia coordenadas para a área de transferência e emite anúncio acessível para leitores de tela", async () => {
      const writeTextMock = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, {
        clipboard: { writeText: writeTextMock },
      });

      render(
        <CopyableCoordinates
          latitude={-23.55052}
          longitude={-46.633308}
          entityId="struct-1"
        />
      );

      const copyBtn = screen.getByRole("button", { name: /Copiar latitude e longitude/i });
      await act(async () => {
        fireEvent.click(copyBtn);
      });

      expect(writeTextMock).toHaveBeenCalledWith("-23.550520, -46.633308");

      // Anúncio aria-live
      const srLive = screen.getByRole("status");
      expect(srLive.textContent).toContain("copiadas para a área de transferência");
      expect(screen.getByText("Copiado!")).toBeDefined();
    });

    it("fornece atalho para navegação externa via GPS / Google Maps", () => {
      render(
        <CopyableCoordinates
          latitude={-23.55052}
          longitude={-46.633308}
          entityId="struct-1"
        />
      );

      const gpsLink = screen.getByRole("link", { name: /Navegar GPS \(Campo\)/i });
      expect(gpsLink.getAttribute("href")).toContain(
        "https://www.google.com/maps/search/?api=1&query=-23.55052,-46.633308"
      );
      expect(gpsLink.getAttribute("target")).toBe("_blank");
      expect(gpsLink.getAttribute("rel")).toContain("noopener");
    });
  });

  describe("4. Resiliência do Mapa (Erro de WebGL não Bloqueia Inventário)", () => {
    it("renderiza tabela alternativa MapFallbackTable quando WebGL não está disponível", () => {
      const mockFeatures = [
        {
          type: "Feature" as const,
          id: "site-1",
          geometry: {
            type: "Point" as const,
            coordinates: [-46.6333, -23.5505] as [number, number],
          },
          properties: {
            entity_id: "site-1",
            code: "POP-CENTRAL",
            entity_type: "site",
            status: "active",
            version: 1,
          },
        },
        {
          type: "Feature" as const,
          id: "ceo-1",
          geometry: {
            type: "Point" as const,
            coordinates: [-46.635, -23.552] as [number, number],
          },
          properties: {
            entity_id: "ceo-1",
            code: "CEO-01",
            entity_type: "structure",
            status: "active",
            version: 1,
          },
        },
      ];

      render(
        <MapFallbackTable
          features={mockFeatures}
          onSelectFeature={vi.fn()}
        />
      );

      // A tabela deve exibir os dados de inventário sem falhar
      expect(screen.getByText("POP-CENTRAL")).toBeDefined();
      expect(screen.getByText("CEO-01")).toBeDefined();
      expect(screen.getByText("-23.55050, -46.63330")).toBeDefined();
      expect(screen.getByText("-23.55200, -46.63500")).toBeDefined();
    });
  });

  describe("5. Navegação por Teclado e Skip Link (WCAG 2.2 AA)", () => {
    it("AppShell contém link 'Pular para o conteúdo principal' apontando para #main-content", () => {
      render(
        <AppShell>
          <div data-testid="conteudo-teste">Conteúdo Operacional</div>
        </AppShell>
      );

      const skipLink = screen.getByRole("link", { name: /Pular para o conteúdo principal/i });
      expect(skipLink).toBeDefined();
      expect(skipLink.getAttribute("href")).toBe("#main-content");

      const mainElement = screen.getByRole("main");
      expect(mainElement.id).toBe("main-content");
    });
  });
});
