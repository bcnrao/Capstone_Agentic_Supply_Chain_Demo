import { Card, List, Tag, Typography } from "antd";
import { AlertOutlined, CloudOutlined } from "@ant-design/icons";

import type { PipelineState } from "../../types/state";

const { Text } = Typography;

interface Props {
  state?: PipelineState;
}

interface RiskRow {
  id: string;
  title: string;
  description: string;
  severity: number;
  level: string;
  icon: "alert" | "weather";
}

function riskTag(severity: number): { color: string; label: string } {
  if (severity >= 8) return { color: "red", label: "CRITICAL" };
  if (severity >= 6) return { color: "orange", label: "HIGH" };
  if (severity >= 4) return { color: "gold", label: "MEDIUM" };
  return { color: "green", label: "LOW" };
}

export default function CriticalRisksList({ state }: Props) {
  const rows: RiskRow[] = [];

  for (const item of state?.classifications ?? []) {
    const signal = state?.new_signals?.find((row) => row.signal_id === item.signal_id);
    rows.push({
      id: item.signal_id,
      title: signal?.title ?? item.category,
      description: item.rationale || `${item.category} risk on ${item.route}`,
      severity: item.severity,
      level: item.risk_level,
      icon: "alert",
    });
  }

  for (const risk of state?.weather_risks ?? []) {
    rows.push({
      id: `weather-${risk.signal_id}`,
      title: `${risk.hub_port ?? risk.region ?? "Hub"} weather disruption`,
      description: risk.summary || `Peak day ${risk.peak_day ?? "unknown"}`,
      severity: risk.aggregate_severity,
      level: risk.aggregate_severity >= 7 ? "HIGH" : "MEDIUM",
      icon: "weather",
    });
  }

  rows.sort((a, b) => b.severity - a.severity);

  return (
    <Card className="scd-card" title="Critical Risks" bordered={false}>
      <List
        dataSource={rows.slice(0, 5)}
        locale={{ emptyText: "Run analysis to surface critical risks" }}
        renderItem={(item) => {
          const tag = riskTag(item.severity);
          return (
            <List.Item>
              <List.Item.Meta
                avatar={
                  item.icon === "weather" ? (
                    <CloudOutlined style={{ color: "#1677ff", fontSize: 18 }} />
                  ) : (
                    <AlertOutlined style={{ color: "#fa541c", fontSize: 18 }} />
                  )
                }
                title={item.title}
                description={item.description}
              />
              <div style={{ textAlign: "right", minWidth: 72 }}>
                <Tag color={tag.color}>{tag.label}</Tag>
                <div>
                  <Text strong>{item.severity.toFixed(1)}</Text>
                </div>
              </div>
            </List.Item>
          );
        }}
      />
    </Card>
  );
}
