import { Card, Space, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";

import { useDashboard } from "../context/DashboardContext";
import type { Classification } from "../types/state";

interface SignalRow {
  key: string;
  title: string;
  source: string;
  region: string;
  category: string;
  severity: number;
  risk_level: string;
  confidence: number;
}

function riskColor(level: string): string {
  switch (level) {
    case "HIGH":
      return "red";
    case "MEDIUM":
      return "orange";
    default:
      return "green";
  }
}

export default function RiskMonitor() {
  const { state } = useDashboard();

  const classById = new Map<string, Classification>(
    (state?.classifications ?? []).map((item) => [item.signal_id, item]),
  );

  const signalRows: SignalRow[] = (state?.new_signals ?? []).map((signal) => {
    const cls = classById.get(signal.signal_id);
    return {
      key: signal.signal_id,
      title: signal.title,
      source: signal.source,
      region: signal.location?.region ?? "",
      category: cls?.category ?? "",
      severity: cls?.severity ?? 0,
      risk_level: cls?.risk_level ?? "",
      confidence: cls?.confidence ?? 0,
    };
  });

  const signalColumns: ColumnsType<SignalRow> = [
    { title: "Title", dataIndex: "title", key: "title", ellipsis: true },
    { title: "Source", dataIndex: "source", key: "source" },
    { title: "Region", dataIndex: "region", key: "region" },
    { title: "Category", dataIndex: "category", key: "category" },
    {
      title: "Severity",
      dataIndex: "severity",
      key: "severity",
      render: (value: number) => value.toFixed(1),
      sorter: (a, b) => a.severity - b.severity,
    },
    {
      title: "Risk level",
      dataIndex: "risk_level",
      key: "risk_level",
      render: (level: string) =>
        level ? <Tag color={riskColor(level)}>{level}</Tag> : null,
    },
    {
      title: "Confidence",
      dataIndex: "confidence",
      key: "confidence",
      render: (value: number) => `${(value * 100).toFixed(0)}%`,
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title="Signals and classification" size="small">
        <Table
          rowKey="key"
          size="small"
          columns={signalColumns}
          dataSource={signalRows}
          pagination={{ pageSize: 20, hideOnSinglePage: true }}
          scroll={{ y: "calc(100vh - 260px)" }}
          locale={{ emptyText: "Run the pipeline to classify signals" }}
        />
      </Card>
    </Space>
  );
}
