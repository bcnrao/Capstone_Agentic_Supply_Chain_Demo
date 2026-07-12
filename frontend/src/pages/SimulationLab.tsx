import { Card, Col, Empty, Row, Statistic, Typography } from "antd";

import { useDashboard } from "../context/DashboardContext";

const { Paragraph } = Typography;

export default function SimulationLab() {
  const { state } = useDashboard();
  const sim = state?.simulation;

  if (!sim) {
    return (
      <Card title="Simulation lab" size="small">
        <Empty description="No simulation has run yet for this route" />
      </Card>
    );
  }

  return (
    <Card title={`Simulation lab (engine: ${sim.engine || "local"})`} size="small">
      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Statistic
            title="Stockout probability"
            value={sim.stockout_probability * 100}
            precision={0}
            suffix="%"
          />
        </Col>
        <Col xs={12} md={6}>
          <Statistic
            title="Service level"
            value={sim.service_level * 100}
            precision={0}
            suffix="%"
          />
        </Col>
        <Col xs={12} md={6}>
          <Statistic
            title="Expected shortage"
            value={sim.expected_shortage_units}
            precision={0}
            suffix="units"
          />
        </Col>
        <Col xs={12} md={6}>
          <Statistic
            title="Recovery time"
            value={sim.recovery_time_days}
            precision={1}
            suffix="days"
          />
        </Col>
        <Col xs={12} md={6}>
          <Statistic title="Revenue impact (mean)" value={sim.revenue_impact} precision={0} />
        </Col>
        <Col xs={12} md={6}>
          <Statistic title="Revenue loss p50" value={sim.revenue_loss_p50} precision={0} />
        </Col>
        <Col xs={12} md={6}>
          <Statistic title="Revenue loss p90" value={sim.revenue_loss_p90} precision={0} />
        </Col>
        <Col xs={12} md={6}>
          <Statistic title="Iterations" value={sim.iterations} />
        </Col>
      </Row>
      {sim.assumptions && (
        <Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
          {sim.assumptions}
        </Paragraph>
      )}
    </Card>
  );
}
