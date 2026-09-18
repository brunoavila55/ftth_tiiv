import { DevFeatureState } from "@/components/ui/state-displays";
import { NAVIGATION_GROUPS, ROUTE_SEGMENT_LABELS } from "@/lib/navigation";

interface PageProps {
  params: Promise<{ slug: string[] }>;
}

export default async function CatchAllDevPage({ params }: PageProps) {
  const { slug } = await params;
  const path = "/" + slug.join("/");

  // Procura correspondência nos itens de navegação
  let matchedItem = null;

  for (const group of NAVIGATION_GROUPS) {
    for (const item of group.items) {
      if (item.href === path || path.startsWith(item.href + "/")) {
        matchedItem = item;
        break;
      }
    }
    if (matchedItem) break;
  }

  // Se não estiver nos grupos mapeados, gera título amigável ou 404
  const pageTitle =
    matchedItem?.title ||
    ROUTE_SEGMENT_LABELS[slug[slug.length - 1]] ||
    slug[slug.length - 1].charAt(0).toUpperCase() + slug[slug.length - 1].slice(1);

  const pageDescription =
    matchedItem?.description ||
    `Página em desenvolvimento para o módulo "${pageTitle}". O backend FTTH Manager e as entidades PostGIS estão sincronizados via OpenAPI 3.1.`;

  return (
    <div className="max-w-4xl mx-auto py-8">
      <DevFeatureState
        title={pageTitle}
        stageName={matchedItem?.badge || "Em breve"}
        description={pageDescription}
      />
    </div>
  );
}
