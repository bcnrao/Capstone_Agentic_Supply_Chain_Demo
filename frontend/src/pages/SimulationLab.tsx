import type { ComponentProps } from "react";
import { Card, Col, Empty, Row, Statistic, Tooltip, Typography } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";

import { useDashboard } from "../context/DashboardContext";

const { Paragraph, Text } = Typography;

function StatWithHelp({
  title,
  help,
  ...rest
}: { title: string; help: string } & Omit<ComponentProps<typeof Statistic>, "title">) {
  return (
    <Statistic
      title={
        <Tooltip title={help}>
          <span>
            {title} <InfoCircleOutlined style={{ opacity: 0.55 }} />
          </span>
        </Tooltip>
      }
      {...rest}
    />
  );
}

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

  // The assumptions string is a "; "-separated list of the fixed scenario
  // parameters that were held constant across every Monte Carlo run.
  const scenarioParams = (sim.assumptions || "")
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean);

  return (
    <Card title={`Simulation lab (engine: ${sim.engine || "local"})`} size="small">
      <Paragraph type="secondary" style={{ marginBottom: 20 }}>
        Simulate <Text strong>Supplier → Port → Warehouse → Retailer</Text> network over a
        90-day window under the current disruption, running it{" "}
        <Text strong>{sim.iterations.toLocaleString()} times</Text>. Each run is one possible future
        with random lead times, port delays, and transit times — the metrics below are the{" "}
        <Text strong>distribution across those runs</Text>, not a single guess. The scenario itself
        (risk, affected nodes, lane) is fixed; only the random draws change per run.
      </Paragraph>

      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Stockout probability"
            help="Share of simulated runs that ran out of stock at some point in the 90-day window."
            value={sim.stockout_probability * 100}
            precision={0}
            suffix="%"
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Service level"
            help="Average share of demand that was fulfilled across all runs (100% = no unmet demand)."
            value={sim.service_level * 100}
            precision={0}
            suffix="%"
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Expected shortage"
            help="Mean number of demand units left unmet per run."
            value={sim.expected_shortage_units}
            precision={0}
            suffix="units"
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Recovery time"
            help="80th-percentile time for replenishment to catch up and normal service to resume."
            value={sim.recovery_time_days}
            precision={1}
            suffix="days"
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Revenue impact (mean)"
            help="Average revenue lost to shortages across all runs."
            value={sim.revenue_impact}
            precision={0}
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Revenue loss p50"
            help="Median (typical-case) revenue loss — half of runs are below this."
            value={sim.revenue_loss_p50}
            precision={0}
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Revenue loss p90"
            help="Tail-risk revenue loss — only 1 in 10 runs is worse than this."
            value={sim.revenue_loss_p90}
            precision={0}
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Iterations"
            help="Number of Monte Carlo runs behind these statistics."
            value={sim.iterations}
          />
        </Col>
      </Row>

      {scenarioParams.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <Text strong style={{ fontSize: 13 }}>
            Scenario parameters{" "}
            <Tooltip title="Held constant across every run — these define the disruption being stress-tested.">
              <InfoCircleOutlined style={{ opacity: 0.55 }} />
            </Tooltip>
          </Text>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
            {scenarioParams.map((param, index) => (
              <li key={index}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {param}
                </Text>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
