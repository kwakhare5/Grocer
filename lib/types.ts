export interface CustomerPersona {
  id: string;
  name: string;
  homeStoreCode?: string;
  homeStoreName?: string;
  address: string;
  avatar: string;
  householdSize: number;
  orderFrequencyDays: number;
  primaryDepletionItem?: string;
}


// ---------------------------------------------------------------------------
// OPERATIONS RESIDUE REMOVED — Phase 0 boundary cleanup
// The following types were removed because they belong to the dark-store
// operations product (kwakhare5/Dark-store-operator), not GROCER v2 consumer:
//   - RiskSeverity, ActionType, ActionStatus
//   - DarkStore (including inventoryHealth)
//   - RecommendationItem, RecommendationAlternative
//   - SimulationEvent, SimulationState, SimulationMetrics, ScenarioState
// Source: GROCER_V2_MASTER_SPEC.md §19
// ---------------------------------------------------------------------------
