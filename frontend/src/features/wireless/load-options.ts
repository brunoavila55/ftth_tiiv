import { listDevices, listSites, type DeviceRead } from "@/features/inventory/api";
import type { PaginatedResult, SiteRead } from "@/lib/api/types";

async function collectPages<T>(loadPage: (page: number) => Promise<PaginatedResult<T>>): Promise<T[]> {
  const first = await loadPage(1);
  const items = [...first.items];
  for (let page = 2; items.length < first.total; page += 1) {
    const next = await loadPage(page);
    if (next.items.length === 0) break;
    items.push(...next.items);
  }
  return items;
}

export async function loadWirelessSites(): Promise<SiteRead[]> {
  const [pops, towers] = await Promise.all([
    collectPages((page) => listSites({ kind: "wireless_pop", page, page_size: 200 })),
    collectPages((page) => listSites({ kind: "radio_tower", page, page_size: 200 })),
  ]);
  return [...pops, ...towers];
}

export function loadRadios(): Promise<DeviceRead[]> {
  return collectPages((page) => listDevices({ kind: "radio", page, page_size: 200 }));
}
