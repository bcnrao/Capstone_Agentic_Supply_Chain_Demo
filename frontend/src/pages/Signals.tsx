import { Card, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { useDashboard } from "../context/DashboardContext";
import type { DisruptionSignal } from "../types/state";

function formatDate(value?: string | null): string {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toLocaleString();
}

export default function Signals() {
  const { state } = useDashboard();

  const columns: ColumnsType<DisruptionSignal> = [
    {
      title: "Event date",
      key: "event_date",
      width: 180,
      render: (_, row) => formatDate(row.event_time ?? row.fetched_at),
    },
    { title: "Title", dataIndex: "title", key: "title", ellipsis: true },
    { title: "Source", dataIndex: "source", key: "source", width: 130 },
    { title: "Type", dataIndex: "source_type", key: "source_type", width: 110 },
    {
      title: "Region",
      key: "region",
      width: 130,
      render: (_, row) => row.location?.region ?? "",
    },
  ];

  return (
    <Card title="Raw signals ingested this run" size="small">
      <Table
        rowKey="signal_id"
        size="small"
        columns={columns}
        dataSource={state?.new_signals ?? []}
        pagination={{ pageSize: 20, hideOnSinglePage: true }}
        scroll={{ y: "calc(100vh - 260px)" }}
        locale={{ emptyText: "Run the pipeline to ingest signals" }}
      />
    </Card>
  );
}
