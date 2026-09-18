import { api } from "@/lib/api/client";
import type {
  BudgetCalculationRequest,
  BudgetCalculationResponse,
  OpticalProfileRead,
} from "./types";
import { listCustomers, listServiceLinks } from "../customers/api";
import type { CustomerRead, ServiceLinkRead } from "../customers/types";

/**
 * Calcula o balanço de potência óptica oficial fornecido pela API.
 */
export async function calculateOpticalBudget(
  payload: BudgetCalculationRequest
): Promise<BudgetCalculationResponse> {
  return api.post<BudgetCalculationResponse>("/optical/budgets", payload);
}

/**
 * Lista perfis ópticos disponíveis no catálogo da operadora.
 */
export async function listOpticalProfiles(): Promise<{
  items: OpticalProfileRead[];
  total: number;
}> {
  return api.get<{ items: OpticalProfileRead[]; total: number }>("/optical-profiles?page_size=100");
}

export { listCustomers, listServiceLinks };
export type { CustomerRead, ServiceLinkRead };
