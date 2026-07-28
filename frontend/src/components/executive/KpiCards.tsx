import { Card, Col, Row, Statistic } from "antd";
import {
  ClockCircleOutlined,
  InboxOutlined,
  WalletOutlined,
  WarningOutlined,
} from "@ant-design/icons";

import type { PipelineState } from "../../types/state";

interface Props {
  state?: PipelineState;
}

function formatMoney(value: number): string {
  if (value >= 10_000_000) return `₹${(value / 10_000_000).toFixed(1)} Cr`;
  if (value >= 100_000) return `₹${(value / 100_000).toFixed(1)} L`;
  if (value >= 1_000) return `₹${(value / 1_000).toFixed(0)}K`;
  return `₹${value.toFixed(0)}`;
}

export default function KpiCards({ state }: Props) {
  const classifications = state?.classifications ?? [];
  const maxSeverity = classifications.reduce(
    (acc, item) => Math.max(acc, item.severity),
    0,
  );
  const revenue = state?.simulation?.revenue_impact ?? 0;
  const inventory =
    state?.forecast?.inventory_days_left ??
    state?.simulation?.expected_shortage_units ??
    0;
  const recovery = state?.simulation?.recovery_time_days ?? 0;

  const items = [
    {
      title: "Revenue Exposure",
      value: state ? formatMoney(revenue) : "—",
      icon: <WalletOutlined />,
      iconClass: "scd-kpi-icon-orange",
    },
    {
      title: "Risk Index",
      value: state ? `${maxSeverity.toFixed(1)}/10` : "—",
      icon: <WarningOutlined />,
      iconClass: "scd-kpi-icon-red",
    },
    {
      title: "Inventory at Risk",
      value: state ? `${inventory.toFixed(0)} units` : "—",
      icon: <InboxOutlined />,
      iconClass: "scd-kpi-icon-blue",
    },
    {
      title: "Recovery Time",
      value: state ? `${recovery.toFixed(1)} days` : "—",
      icon: <ClockCircleOutlined />,
      iconClass: "scd-kpi-icon-green",
    },
  ];

  return (
    <Row gutter={[16, 16]}>
      {items.map((item) => (
        <Col xs={24} sm={12} xl={6} key={item.title}>
          <Card className="scd-card scd-kpi-card" bordered={false}>
            <div className={`scd-kpi-icon ${item.iconClass}`}>{item.icon}</div>
            <Statistic title={item.title} value={item.value} />
          </Card>
        </Col>
      ))}
    </Row>
  );
}
