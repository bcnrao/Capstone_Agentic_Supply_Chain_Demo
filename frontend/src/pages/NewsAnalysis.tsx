import { Card, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { useDashboard } from "../context/DashboardContext";
import type { EventAnalysis } from "../types/state";

export default function NewsAnalysis() {
  const { state } = useDashboard();
  const columns: ColumnsType<EventAnalysis> = [
    { title: "Event type", dataIndex: "event_type", key: "event_type", width: 140 },
    {
      title: "Region",
      dataIndex: "extracted_region",
      key: "extracted_region",
      width: 120,
      render: (value?: string | null) => value ?? "",
    },
    {
      title: "Severity hint",
      dataIndex: "severity_hint",
      key: "severity_hint",
      width: 120,
      render: (value?: string | null) => value ?? "",
    },
    {
      title: "Entities",
      dataIndex: "entities",
      key: "entities",
      width: 220,
      ellipsis: true,
      render: (entities: string[]) => entities.join(", "),
    },
    { title: "Summary", dataIndex: "summary", key: "summary", ellipsis: true },
  ];

  return (
    <Card title="Event extraction and summarization" size="small">
      <Table
        rowKey="signal_id"
        size="small"
        columns={columns}
        dataSource={state?.event_analyses ?? []}
        pagination={{ pageSize: 20, hideOnSinglePage: true }}
        scroll={{ y: "calc(100vh - 260px)" }}
        locale={{ emptyText: "Run the pipeline to analyze news and events" }}
      />
    </Card>
  );
}
