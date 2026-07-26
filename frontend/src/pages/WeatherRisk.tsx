import { Card, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { useDashboard } from "../context/DashboardContext";
import type { WeatherRiskAssessment } from "../types/state";

export default function WeatherRisk() {
  const { state } = useDashboard();
  const columns: ColumnsType<WeatherRiskAssessment> = [
    {
      title: "Hub",
      dataIndex: "hub_port",
      key: "hub_port",
      render: (value?: string | null) => value ?? "",
    },
    {
      title: "Region",
      dataIndex: "region",
      key: "region",
      render: (value?: string | null) => value ?? "",
    },
    { title: "Horizon (days)", dataIndex: "horizon_days", key: "horizon_days" },
    {
      title: "Aggregate severity",
      dataIndex: "aggregate_severity",
      key: "aggregate_severity",
      render: (value: number) => value.toFixed(1),
    },
    {
      title: "Port disruption risk",
      dataIndex: "port_disruption_risk",
      key: "port_disruption_risk",
      render: (value: number) => `${(value * 100).toFixed(0)}%`,
    },
    {
      title: "Peak day",
      dataIndex: "peak_day",
      key: "peak_day",
      render: (value?: string | null) => value ?? "",
    },
    {
      title: "Operations",
      dataIndex: "affected_operations",
      key: "affected_operations",
      render: (ops: string[]) => ops.join(", "),
    },
  ];

  return (
    <Card title="7-day hub weather risk" size="small">
      <Table
        rowKey={(row) => `${row.signal_id}-${row.hub_port ?? row.region ?? ""}`}
        size="small"
        columns={columns}
        dataSource={state?.weather_risks ?? []}
        pagination={{ pageSize: 20, hideOnSinglePage: true }}
        scroll={{ y: "calc(100vh - 260px)" }}
        locale={{ emptyText: "Run the pipeline to assess hub weather risk" }}
      />
    </Card>
  );
}
