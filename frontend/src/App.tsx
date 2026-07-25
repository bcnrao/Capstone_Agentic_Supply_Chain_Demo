import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { DashboardProvider } from "./context/DashboardContext";
import AppShell from "./layout/AppShell";
import Executive from "./pages/Executive";
import Signals from "./pages/Signals";
import RiskMonitor from "./pages/RiskMonitor";
import NewsAnalysis from "./pages/NewsAnalysis";
import WeatherRisk from "./pages/WeatherRisk";
import ImpactMap from "./pages/ImpactMap";
import DemandForecast from "./pages/DemandForecast";
import SimulationLab from "./pages/SimulationLab";
import Mitigation from "./pages/Mitigation";
import TraceJson from "./pages/TraceJson";
import AskKb from "./pages/AskKb";

export default function App() {
  return (
    <DashboardProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Executive />} />
            <Route path="signals" element={<Signals />} />
            <Route path="risk" element={<RiskMonitor />} />
            <Route path="impact" element={<ImpactMap />} />
            <Route path="news" element={<NewsAnalysis />} />
            <Route path="weather" element={<WeatherRisk />} />
            <Route path="forecast" element={<DemandForecast />} />
            <Route path="simulation" element={<SimulationLab />} />
            <Route path="mitigation" element={<Mitigation />} />
            <Route path="trace" element={<TraceJson />} />
            <Route path="ask" element={<AskKb />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </DashboardProvider>
  );
}
