export interface RouteMeta {
  path: string;
  title: string;
  subtitle: string;
}

export const ROUTE_META: Record<string, RouteMeta> = {
  "/": {
    path: "/",
    title: "Executive Overview",
    subtitle: "Real-time supply chain risk intelligence and mitigation recommendations",
  },
  "/signals": {
    path: "/signals",
    title: "Signals",
    subtitle: "Raw disruption signals ingested this run",
  },
  "/risk": {
    path: "/risk",
    title: "Classification",
    subtitle: "Signals and classification",
  },
  "/impact": {
    path: "/impact",
    title: "Impact Map",
    subtitle: "Affected suppliers, lanes, and facilities",
  },
  "/news": {
    path: "/news",
    title: "News Analysis",
    subtitle: "Event extraction and summarization",
  },
  "/weather": {
    path: "/weather",
    title: "Weather Risk",
    subtitle: "7-day hub weather risk assessments",
  },
  "/forecast": {
    path: "/forecast",
    title: "Demand Forecast",
    subtitle: "Baseline vs risk-adjusted forecast",
  },
  "/simulation": {
    path: "/simulation",
    title: "Simulation Lab",
    subtitle: "Monte Carlo stockout and revenue impact",
  },
  "/mitigation": {
    path: "/mitigation",
    title: "Mitigation",
    subtitle: "Ranked action plan and supporting evidence",
  },
  "/trace": {
    path: "/trace",
    title: "Trace JSON",
    subtitle: "Full pipeline state for debugging",
  },
  "/ask": {
    path: "/ask",
    title: "Ask AI",
    subtitle: "Query the local supply-chain knowledge base",
  },
};

export function metaForPath(pathname: string): RouteMeta {
  return ROUTE_META[pathname] ?? ROUTE_META["/"];
}
