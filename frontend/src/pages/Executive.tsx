import { Col, Row } from "antd";

import { useDashboard } from "../context/DashboardContext";
import ActivityTimeline from "../components/executive/ActivityTimeline";
import AiMissionProgress from "../components/executive/AiMissionProgress";
import CriticalRisksList from "../components/executive/CriticalRisksList";
import ImpactMapChart from "../components/executive/ImpactMapChart";
import KpiCards from "../components/executive/KpiCards";
import RecentScenariosTable from "../components/executive/RecentScenariosTable";
import TopRecommendation from "../components/executive/TopRecommendation";

export default function Executive() {
  const { state } = useDashboard();

  return (
    <div className="scd-executive">
      <KpiCards state={state} />

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} xl={10}>
          <TopRecommendation state={state} />
        </Col>
        <Col xs={24} md={12} xl={7}>
          <CriticalRisksList state={state} />
        </Col>
        <Col xs={24} md={12} xl={7}>
          <AiMissionProgress />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} xl={14}>
          <ImpactMapChart state={state} />
        </Col>
        <Col xs={24} xl={10}>
          <RecentScenariosTable />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <ActivityTimeline />
        </Col>
      </Row>
    </div>
  );
}
