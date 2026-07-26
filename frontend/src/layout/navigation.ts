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
  ThunderboltOutlined,
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
    label: "OVERVIEW",
    items: [{ path: "/", label: "Executive", icon: DashboardOutlined }],
  },
  {
    label: "INPUTS",
    items: [
      { path: "/signals", label: "Signals", icon: ThunderboltOutlined },
      { path: "/news", label: "News Analysis", icon: FileTextOutlined },
      { path: "/weather", label: "Weather Risk", icon: CloudOutlined },
    ],
  },
  {
    label: "ANALYSIS",
    items: [
      { path: "/risk", label: "Classification", icon: AlertOutlined },
      { path: "/impact", label: "Impact Map", icon: GlobalOutlined },
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
