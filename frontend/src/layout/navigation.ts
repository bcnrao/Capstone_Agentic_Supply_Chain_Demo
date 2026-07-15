import type { ComponentType } from "react";
import {
  AlertOutlined,
  ApiOutlined,
  BarChartOutlined,
  CloudOutlined,
  DashboardOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  GlobalOutlined,
  MessageOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";

export interface NavItem {
  path: string;
  label: string;
  icon: ComponentType;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "SITUATION",
    items: [
      { path: "/", label: "Executive", icon: DashboardOutlined },
      { path: "/risk", label: "Risk Monitor", icon: AlertOutlined },
      { path: "/impact", label: "Impact Map", icon: GlobalOutlined },
    ],
  },
  {
    label: "ANALYSIS",
    items: [
      { path: "/news", label: "News Analysis", icon: FileTextOutlined },
      { path: "/weather", label: "Weather Risk", icon: CloudOutlined },
      { path: "/forecast", label: "Demand Forecast", icon: BarChartOutlined },
      { path: "/simulation", label: "Simulation", icon: ExperimentOutlined },
    ],
  },
  {
    label: "ACTION",
    items: [{ path: "/mitigation", label: "Mitigation", icon: SafetyCertificateOutlined }],
  },
  {
    label: "EXPLAIN",
    items: [
      { path: "/trace", label: "Trace JSON", icon: ApiOutlined },
      { path: "/ask", label: "Ask AI", icon: MessageOutlined },
    ],
  },
];

export const MISSION_STEPS = [
  { key: "ingest", label: "Ingesting disruption signals" },
  { key: "classify", label: "Classifying risk severity" },
  { key: "impact", label: "Mapping supply chain impact" },
  { key: "forecast", label: "Forecasting demand impact" },
  { key: "simulate", label: "Running mitigation simulations" },
  { key: "recommend", label: "Generating recommendations" },
] as const;
