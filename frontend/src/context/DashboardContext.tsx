import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { PipelineState } from "../types/state";

export type MissionStep =
  | "idle"
  | "ingest"
  | "classify"
  | "impact"
  | "forecast"
  | "simulate"
  | "recommend"
  | "complete";

export interface ActivityEntry {
  id: string;
  time: string;
  message: string;
  kind: "info" | "success" | "warning";
}

interface DashboardContextValue {
  state: PipelineState | undefined;
  setState: (state: PipelineState | undefined) => void;
  scenario: string | undefined;
  setScenario: (scenario: string | undefined) => void;
  lastUpdated: Date | undefined;
  setLastUpdated: (date: Date | undefined) => void;
  missionStep: MissionStep;
  setMissionStep: (step: MissionStep) => void;
  activityLog: ActivityEntry[];
  addActivity: (message: string, kind?: ActivityEntry["kind"]) => void;
  clearActivity: () => void;
  configOpen: boolean;
  setConfigOpen: (open: boolean) => void;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PipelineState | undefined>();
  const [scenario, setScenario] = useState<string | undefined>();
  const [lastUpdated, setLastUpdated] = useState<Date | undefined>();
  const [missionStep, setMissionStep] = useState<MissionStep>("idle");
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [configOpen, setConfigOpen] = useState(false);

  const addActivity = useCallback(
    (message: string, kind: ActivityEntry["kind"] = "info") => {
      setActivityLog((prev) => [
        {
          id: `${Date.now()}-${prev.length}`,
          time: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
          message,
          kind,
        },
        ...prev.slice(0, 19),
      ]);
    },
    [],
  );

  const clearActivity = useCallback(() => setActivityLog([]), []);

  const value = useMemo(
    () => ({
      state,
      setState,
      scenario,
      setScenario,
      lastUpdated,
      setLastUpdated,
      missionStep,
      setMissionStep,
      activityLog,
      addActivity,
      clearActivity,
      configOpen,
      setConfigOpen,
    }),
    [
      state,
      scenario,
      lastUpdated,
      missionStep,
      activityLog,
      addActivity,
      clearActivity,
      configOpen,
    ],
  );

  return (
    <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>
  );
}

export function useDashboard() {
  const ctx = useContext(DashboardContext);
  if (!ctx) {
    throw new Error("useDashboard must be used within DashboardProvider");
  }
  return ctx;
}
