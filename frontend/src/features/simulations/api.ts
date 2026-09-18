import { api } from "@/lib/api/client";
import type {
  ImpactAnalysisRequest,
  ImpactAnalysisResponse,
  OpticalSimulationRequest,
  OpticalSimulationResponse,
} from "./types";

export async function simulateOpticalBudget(
  payload: OpticalSimulationRequest
): Promise<OpticalSimulationResponse> {
  return api.post<OpticalSimulationResponse>("/optical/simulations", payload);
}

export async function simulateCableImpact(
  payload: ImpactAnalysisRequest
): Promise<ImpactAnalysisResponse> {
  return api.post<ImpactAnalysisResponse>("/topology/impact", payload);
}
