import { useState } from "react";
import { Button, Card, Col, Row, Space, Statistic, Tag, Typography } from "antd";
import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";

import type { PipelineState } from "../../types/state";

const { Paragraph, Text, Title } = Typography;

interface Props {
  state?: PipelineState;
}

const URGENCY_COLOR: Record<string, string> = {
  CRITICAL: "red",
  HIGH: "volcano",
  MEDIUM: "gold",
  LOW: "green",
};

export default function TopRecommendation({ state }: Props) {
  const actions = state?.recommendation?.structured_actions ?? [];
  const [index, setIndex] = useState(0);

  if (actions.length === 0) {
    return (
      <Card className="scd-card scd-recommendation-card" title="Top Recommendations" bordered={false}>
        <Paragraph type="secondary">
          Run analysis to generate ranked mitigation recommendations.
        </Paragraph>
      </Card>
    );
  }

  const action = actions[index % actions.length];
  const sim = state?.simulation;

  // Revenue at risk uses the MEAN (revenue_impact), not the P50. The P50 is the
  // median across Monte Carlo iterations, so whenever stockout probability is
  // below 50% more than half the iterations end with no shortage and the median
  // is exactly 0 — which made this tile read ₹0 on most live-feed runs while the
  // mean and P90 were both material. The P90 is shown alongside as the tail.
  const atRisk = sim?.revenue_impact ?? 0;
  const tailRisk = sim?.revenue_loss_p90 ?? 0;
  const recovery = sim?.recovery_time_days ?? 0;

  const confidence = Math.round(
    (state?.classifications?.[0]?.confidence ?? 0.75) * 100,
  );

  return (
    <Card
      className="scd-card scd-recommendation-card"
      title="Top Recommendations"
      bordered={false}
      extra={
        <Text type="secondary">
          {index + 1} of {actions.length}
        </Text>
      }
    >
      <Space align="start" style={{ marginBottom: 4 }}>
        <Tag color={URGENCY_COLOR[action.urgency?.toUpperCase()] ?? "default"}>
          {action.urgency || "PLANNED"}
        </Tag>
        <Text type="secondary">Owner: {action.owner || "Unassigned"}</Text>
      </Space>
      <Title level={4} style={{ marginTop: 4 }}>
        {action.action}
      </Title>
      <Paragraph type="secondary">
        {action.rationale || action.expected_impact || state?.recommendation?.summary}
      </Paragraph>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Statistic title="Revenue at Risk" value={atRisk} prefix="₹" precision={0} />
          <Text type="secondary" style={{ fontSize: 12 }}>
            P90 ₹{Math.round(tailRisk).toLocaleString("en-IN")}
          </Text>
        </Col>
        <Col span={8}>
          <Statistic title="Recovery Time" value={recovery} suffix=" days" precision={1} />
        </Col>
        <Col span={8}>
          <Statistic title="Confidence" value={confidence} suffix="%" />
        </Col>
      </Row>
      <Space>
        <Button icon={<CheckCircleOutlined />}>Approve Action</Button>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => setIndex((value) => (value - 1 + actions.length) % actions.length)}
        />
        <Button
          icon={<ArrowRightOutlined />}
          onClick={() => setIndex((value) => (value + 1) % actions.length)}
        />
      </Space>
    </Card>
  );
}
