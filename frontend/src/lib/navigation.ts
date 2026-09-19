import type { LucideIcon } from "lucide-react";
import type { Permission } from "@/lib/permissions/rbac";
import {
  LayoutDashboard,
  Map,
  Building2,
  UtilityPole,
  Boxes,
  Box,
  Server,
  Cable,
  GitFork,
  Users,
  Network,
  Calculator,
  Gauge,
  Activity,
  FileText,
  Upload,
  Download,
  History,
  Settings,
  UserCog,
} from "lucide-react";

export interface NavItem {
  title: string;
  label: string;
  href: string;
  icon: LucideIcon;
  implemented: boolean;
  badge?: string;
  /** Permissão (do backend) necessária para ver o item; o servidor segue sendo a autoridade. */
  permission: Permission;
  description?: string;
}

export interface NavigationGroup {
  title: string;
  items: NavItem[];
}

export const NAVIGATION_GROUPS: NavigationGroup[] = [
  {
    title: "Visão Geral",
    items: [
      {
        title: "Painel",
        label: "Painel",
        href: "/dashboard",
        permission: "reports:read",
        icon: LayoutDashboard,
        implemented: true,
        description: "Métricas executivas e indicadores de saúde da rede",
      },
      {
        title: "Mapa Operacional",
        label: "Mapa Operacional",
        href: "/map",
        permission: "network:read",
        icon: Map,
        implemented: true,
        description: "Visualização geoespacial com camadas WebGL e snap",
      },
    ],
  },
  {
    title: "Rede Física",
    items: [
      {
        title: "Sites (POPs)",
        label: "Sites (POPs)",
        href: "/sites",
        permission: "network:read",
        icon: Building2,
        implemented: true,
        description: "Locais técnicos, datacenters e centrais",
      },
      {
        title: "Postes",
        label: "Postes",
        href: "/poles",
        permission: "network:read",
        icon: UtilityPole,
        implemented: true,
        description: "Infraestrutura aérea e pontos de fixação",
      },
      {
        title: "Caixas CEO",
        label: "Caixas CEO",
        href: "/ceos",
        permission: "network:read",
        icon: Boxes,
        implemented: true,
        description: "Caixas de emenda óptica de distribuição e tronco",
      },
      {
        title: "Caixas CTO",
        label: "Caixas CTO",
        href: "/ctos",
        permission: "network:read",
        icon: Box,
        implemented: true,
        description: "Caixas de terminação óptica para atendimento",
      },
      {
        title: "Dispositivos",
        label: "Dispositivos",
        href: "/devices",
        permission: "network:read",
        icon: Server,
        implemented: true,
        description: "OLTs, switches, DIOs e bastidores",
      },
      {
        title: "Cabos",
        label: "Cabos",
        href: "/cables",
        permission: "network:read",
        icon: Cable,
        implemented: true,
        description: "Cabos, tubos loose, fibras e código de cores",
      },
      {
        title: "Splitters",
        label: "Splitters",
        href: "/splitters",
        permission: "splitters:read",
        icon: GitFork,
        implemented: true,
        description: "Divisores ópticos balanceados e desbalanceados",
      },
      {
        title: "Clientes",
        label: "Clientes",
        href: "/customers",
        permission: "customers:read",
        icon: Users,
        implemented: true,
        description: "Assinantes e vínculos de atendimento em portas",
      },
    ],
  },
  {
    title: "Engenharia",
    items: [
      {
        title: "Topologia e Rastreamento",
        label: "Topologia e Rastreamento",
        href: "/topology",
        permission: "network:read",
        icon: Network,
        implemented: true,
        description: "Rastreamento óptico PON-ONU e detecção de loops",
      },
      {
        title: "Orçamento de Potência",
        label: "Orçamento de Potência",
        href: "/optical-budget",
        permission: "optical:read",
        icon: Calculator,
        implemented: true,
        description: "Cálculo determinístico de atenuação e sensibilidade",
      },
      {
        title: "Medições de Campo",
        label: "Medições de Campo",
        href: "/measurements",
        permission: "measurements:read",
        icon: Gauge,
        implemented: true,
        description: "Leituras de potência de campo e perda excedente",
      },
      {
        title: "Simulações de Rompimento",
        label: "Simulações de Rompimento",
        href: "/simulations",
        permission: "network:read",
        icon: Activity,
        implemented: true,
        description: "Simulação de impacto sem alteração no banco de dados",
      },
      {
        label: "Relatórios de Capacidade",
        title: "Relatórios de Capacidade",
        href: "/reports",
        permission: "reports:read",
        icon: FileText,
        implemented: true,
        description: "Ocupação de CTOs, balanço de fibras e anomalias",
      },
    ],
  },
  {
    title: "Administração",
    items: [
      {
        title: "Importação",
        label: "Importação",
        href: "/imports",
        permission: "imports:read",
        icon: Upload,
        implemented: true,
        description: "Importação com prévia segura GeoJSON, KML e CSV",
      },
      {
        title: "Exportação",
        label: "Exportação",
        href: "/exports",
        permission: "exports:read",
        icon: Download,
        implemented: true,
        description: "Exportação de dados vetoriais e tabelas com LGPD",
      },
      {
        title: "Auditoria",
        label: "Auditoria",
        href: "/audit",
        permission: "audit:read",
        icon: History,
        implemented: true,
        description: "Trilha de auditoria cronológica e imutável",
      },
      {
        title: "Configurações",
        label: "Configurações",
        href: "/settings",
        permission: "settings:read",
        icon: Settings,
        implemented: true,
        description: "Parâmetros operacionais e catálogos de normas",
      },
      {
        title: "Usuários e Acessos",
        label: "Usuários e Acessos",
        href: "/settings/users",
        permission: "users:read",
        icon: UserCog,
        implemented: true,
        description: "Gestão de perfis e operadores RBAC",
      },
    ],
  },
];

/** Grupos de navegação apenas com os itens que o usuário pode acessar (grupos vazios somem). */
export function visibleNavigationGroups(
  hasPermission: (permission: Permission) => boolean
): NavigationGroup[] {
  return NAVIGATION_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => hasPermission(item.permission)),
  })).filter((group) => group.items.length > 0);
}

/**
 * Permissão exigida para abrir uma rota da navegação (o item de `href` mais específico que
 * casa com o caminho). `null` para rotas fora do menu (ex.: `/profile`).
 */
export function requiredPermissionForPath(pathname: string): Permission | null {
  const path = pathname.split("?")[0].split("#")[0];
  let best: NavItem | null = null;
  for (const group of NAVIGATION_GROUPS) {
    for (const item of group.items) {
      const matches = path === item.href || path.startsWith(item.href + "/");
      if (matches && (!best || item.href.length > best.href.length)) best = item;
    }
  }
  return best ? best.permission : null;
}

export const ROUTE_SEGMENT_LABELS: Record<string, string> = {
  dashboard: "Painel",
  map: "Mapa Operacional",
  sites: "Sites",
  poles: "Postes",
  ceos: "Caixas CEO",
  ctos: "Caixas CTO",
  devices: "Dispositivos",
  cables: "Cabos",
  splitters: "Splitters",
  customers: "Clientes",
  topology: "Topologia",
  "optical-budget": "Orçamento Óptico",
  measurements: "Medições",
  simulations: "Simulações",
  reports: "Relatórios",
  imports: "Importação",
  exports: "Exportação",
  audit: "Auditoria",
  settings: "Configurações",
  users: "Usuários",
  edit: "Editar",
  new: "Novo",
  profile: "Perfil",
};

export interface BreadcrumbItem {
  label: string;
  href: string;
  isLast: boolean;
}

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function parseBreadcrumbs(pathname: string): BreadcrumbItem[] {
  const cleanPath = pathname.split("?")[0].split("#")[0];
  const segments = cleanPath.split("/").filter(Boolean);

  const crumbs: BreadcrumbItem[] = [
    {
      label: "Início",
      href: "/",
      isLast: segments.length === 0,
    },
  ];

  if (segments.length === 0) {
    return crumbs;
  }

  let accumulatedPath = "";
  for (let i = 0; i < segments.length; i++) {
    const segment = segments[i];
    accumulatedPath += `/${segment}`;
    const isLast = i === segments.length - 1;

    let label = ROUTE_SEGMENT_LABELS[segment];
    if (!label) {
      if (UUID_REGEX.test(segment)) {
        label = `#${segment.slice(0, 8)}…`;
      } else {
        label = segment.charAt(0).toUpperCase() + segment.slice(1);
      }
    }

    crumbs.push({
      label,
      href: accumulatedPath,
      isLast,
    });
  }

  return crumbs;
}
