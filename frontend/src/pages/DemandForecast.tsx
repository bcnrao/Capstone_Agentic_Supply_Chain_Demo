import { Card, Col, Empty, Row, Statistic, Table, Tooltip, Typography } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
import { Line } from "@ant-design/plots";
import type { ColumnsType } from "antd/es/table";

import { useDashboard } from "../context/DashboardContext";

const { Paragraph, Text } = Typography;

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
      <Card title="Baseline vs risk-adjusted demand forecast" size="small">
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
    { title: "Week of", dataIndex: "date", key: "date" },
    {
      title: "Baseline (units/wk)",
      dataIndex: "baseline",
      key: "baseline",
      render: (value: number) => value.toFixed(2),
    },
    {
      title: "Risk-adjusted (units/wk)",
      dataIndex: "risk_adjusted",
      key: "risk_adjusted",
      render: (value: number) => value.toFixed(2),
    },
    {
      title: "Delta",
      dataIndex: "delta",
      key: "delta",
      render: (value: number) => (
        <Text type={value < 0 ? "danger" : value > 0 ? "success" : undefined}>
          {value > 0 ? `+${value.toFixed(2)}` : value.toFixed(2)}
        </Text>
      ),
    },
  ];

  const deviation = forecast.demand_deviation_pct ?? 0;

  return (
    <Card title="Baseline vs risk-adjusted demand forecast" size="small">
      <Paragraph type="secondary" style={{ marginBottom: 16 }}>
        Projected <Text strong>aggregate weekly demand across all tracked SKUs</Text> for the next{" "}
        {forecast.dates.length} weeks (units/week).{" "}
        <Tooltip title="Expected demand assuming no active disruption — fitted on historical sales/stock data.">
          <Text strong>Baseline <InfoCircleOutlined /></Text>
        </Tooltip>{" "}
        is the no-disruption expectation;{" "}
        <Tooltip title="Baseline after applying the modeled impact of the current disruption (risk score, disruption type, and freight pressure), ramped over the horizon.">
          <Text strong>Risk-adjusted <InfoCircleOutlined /></Text>
        </Tooltip>{" "}
        is demand after the current disruption is factored in.
      </Paragraph>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}>
          <Statistic
            title="Demand vs baseline"
            value={deviation}
            precision={2}
            suffix="%"
            valueStyle={{ color: deviation < 0 ? "#cf1322" : deviation > 0 ? "#3f8600" : undefined }}
            prefix={deviation > 0 ? "+" : ""}
          />
        </Col>
        <Col xs={12} md={6}>
          <Statistic title="Inventory cover" value={forecast.inventory_days_left} precision={1} suffix="days" />
        </Col>
        <Col xs={12} md={6}>
          <Statistic title="Predicted delay" value={forecast.predicted_delay_days} precision={1} suffix="days" />
        </Col>
        <Col xs={12} md={6}>
          <Statistic title="Freight pressure" value={forecast.freight_pressure_pct} precision={2} suffix="%" />
        </Col>
      </Row>

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
      {forecast.note && (
        <Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0, fontSize: 12 }}>
          <Text strong>How this was produced:</Text> {forecast.note}
          {forecast.model_name ? ` (model: ${forecast.model_name})` : ""}
        </Paragraph>
      )}
    </Card>
  );
}
