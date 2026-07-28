import { useState } from "react";
import { Button, Card, Col, Row, Space, Statistic, Typography } from "antd";
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
  const savings = state?.simulation?.revenue_loss_p50 ?? 0;
  const delay = state?.simulation?.recovery_time_days ?? 0;
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
      <Title level={4} style={{ marginTop: 0 }}>
        {action.action}
      </Title>
      <Paragraph type="secondary">{state?.recommendation?.summary}</Paragraph>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Statistic title="Savings" value={savings} prefix="₹" precision={0} />
        </Col>
        <Col span={8}>
          <Statistic title="Delay Reduction" value={Math.max(0, 14 - delay)} suffix=" days" />
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
