import type { Forecast, MitigationAction, Simulation } from "../types/state";

function money(value: number): string {
  return `$${Math.round(value).toLocaleString("en-US")}`;
}

function signedPct(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

// Fallback "why" for legacy runs where the backend did not stamp a rationale.
// Deliberately narrow: it asserts only the urgency band plus the simulation
// figures the frontend can actually see — never that the simulation consumed a
// forecast field it does not (delay / freight are forecast outputs, not inputs).
export function deriveRationale(
  action: MitigationAction,
  simulation?: Simulation | null,
): string {
  if (!simulation) {
    return `Ranked ${action.urgency} from the risk classification; no simulation output was available this run to quantify the exposure.`;
  }
  const stockout = `${Math.round(simulation.stockout_probability * 100)}% stockout probability`;
  const exposure = `~${money(simulation.revenue_impact)} revenue at risk over a ${simulation.recovery_time_days.toFixed(0)}-day recovery`;
  const urgency = action.urgency.toLowerCase();
  if (urgency.includes("critical")) {
    return `Ranked critical — the Monte-Carlo simulation projects a high ${stockout} with ${exposure}, calling for immediate action.`;
  }
  if (urgency.includes("high")) {
    return `Ranked high — a material ${stockout} (${exposure}) makes prompt mitigation worthwhile.`;
  }
  if (urgency.includes("low")) {
    return `Ranked low — the simulation shows limited exposure (${stockout}); acting mainly to stay ahead of the risk.`;
  }
  return `Ranked medium — with a contained ${stockout} this is a preventive safeguard ahead of any escalation.`;
}

export function rationaleFor(
  action: MitigationAction,
  simulation?: Simulation | null,
): string {
  const stamped = action.rationale?.trim();
  return stamped && stamped.length > 0 ? stamped : deriveRationale(action, simulation);
}

export interface DriverItem {
  label: string;
  value: string;
}

export interface DriverGroup {
  title: string;
  hint: string;
  items: DriverItem[];
}

// The concrete pipeline outputs that shaped the plan, grouped by stage. The
// forecast's adjusted demand curve and inventory cover feed the simulation;
// predicted delay and freight pressure are forecast *outputs*, so they sit in
// the forecast group with no arrow implied into the simulation.
export function decisionDrivers(
  forecast?: Forecast | null,
  simulation?: Simulation | null,
): DriverGroup[] {
  const groups: DriverGroup[] = [];

  if (forecast) {
    groups.push({
      title: "Demand forecast",
      hint: "Adjusted demand curve and inventory cover feed the simulation.",
      items: [
        { label: "Demand vs baseline", value: signedPct(forecast.demand_deviation_pct) },
        { label: "Inventory cover", value: `${forecast.inventory_days_left.toFixed(1)} days` },
        { label: "Predicted lead-time delay", value: `${forecast.predicted_delay_days.toFixed(1)} days` },
        { label: "Freight pressure", value: signedPct(forecast.freight_pressure_pct) },
      ],
    });
  }

  if (simulation) {
    groups.push({
      title: "Monte-Carlo simulation",
      hint: "Stockout probability helps set each action's urgency; revenue-at-risk quantifies the exposure.",
      items: [
        { label: "Stockout probability", value: `${Math.round(simulation.stockout_probability * 100)}%` },
        { label: "Revenue at risk", value: money(simulation.revenue_impact) },
        { label: "Recovery time", value: `${simulation.recovery_time_days.toFixed(0)} days` },
        { label: "Service level", value: `${Math.round(simulation.service_level * 100)}%` },
      ],
    });
  }

  return groups;
}
