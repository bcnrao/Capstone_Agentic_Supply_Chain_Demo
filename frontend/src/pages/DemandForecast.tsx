import { Card, Empty, Table } from "antd";
import { Line } from "@ant-design/plots";
import type { ColumnsType } from "antd/es/table";

import { useDashboard } from "../context/DashboardContext";

interface ForecastRow {
  key: number;
  date: string;
  baseline: number;
  risk_adjusted: number;
  delta: number;
}

export default function DemandForecast() {
  const { state } = useDashboard();
  const forecast = state?.forecast;

  if (!forecast || forecast.dates.length === 0) {
    return (
      <Card title="Baseline vs risk-adjusted forecast" size="small">
        <Empty description="Run the pipeline to generate a demand forecast" />
      </Card>
    );
  }

  const rows: ForecastRow[] = forecast.dates.map((date, index) => ({
    key: index,
    date,
    baseline: forecast.baseline[index] ?? 0,
    risk_adjusted: forecast.adjusted[index] ?? 0,
    delta: Number(
      ((forecast.adjusted[index] ?? 0) - (forecast.baseline[index] ?? 0)).toFixed(2),
    ),
  }));

  const chartData = rows.flatMap((row) => [
    { date: row.date, series: "Baseline", value: row.baseline },
    { date: row.date, series: "Risk-adjusted", value: row.risk_adjusted },
  ]);

  const columns: ColumnsType<ForecastRow> = [
    { title: "Date", dataIndex: "date", key: "date" },
    {
      title: "Baseline",
      dataIndex: "baseline",
      key: "baseline",
      render: (value: number) => value.toFixed(2),
    },
    {
      title: "Risk-adjusted",
      dataIndex: "risk_adjusted",
      key: "risk_adjusted",
      render: (value: number) => value.toFixed(2),
    },
    { title: "Delta", dataIndex: "delta", key: "delta" },
  ];

  return (
    <Card title="Baseline vs risk-adjusted forecast" size="small">
      <Line
        data={chartData}
        xField="date"
        yField="value"
        colorField="series"
        seriesField="series"
        legend={{ color: { position: "top" } }}
        height={320}
        point={{ sizeField: 3 }}
      />
      <Table
        style={{ marginTop: 16 }}
        rowKey="key"
        size="small"
        columns={columns}
        dataSource={rows}
        pagination={{ pageSize: 8 }}
      />
    </Card>
  );
}
