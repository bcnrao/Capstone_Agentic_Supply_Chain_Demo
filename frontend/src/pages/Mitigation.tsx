import { Card, List, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

import { useDashboard } from "../context/DashboardContext";
import type { MitigationAction } from "../types/state";

const { Paragraph } = Typography;

function urgencyColor(urgency: string): string {
  const lowered = urgency.toLowerCase();
  if (lowered.includes("high") || lowered.includes("immediate")) return "red";
  if (lowered.includes("medium")) return "orange";
  return "green";
}

export default function Mitigation() {
  const { state } = useDashboard();
  const rec = state?.recommendation;

  const columns: ColumnsType<MitigationAction> = [
    { title: "Action", dataIndex: "action", key: "action" },
    {
      title: "Urgency",
      dataIndex: "urgency",
      key: "urgency",
      render: (value: string) => <Tag color={urgencyColor(value)}>{value}</Tag>,
    },
    { title: "Expected impact", dataIndex: "expected_impact", key: "expected_impact" },
    { title: "Owner", dataIndex: "owner", key: "owner" },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title="Ranked action plan" size="small">
        {rec?.summary && <Paragraph strong>{rec.summary}</Paragraph>}
        <Table
          rowKey={(row) => row.action}
          size="small"
          columns={columns}
          dataSource={rec?.structured_actions ?? []}
          pagination={false}
          locale={{ emptyText: "Run the pipeline to generate a mitigation plan" }}
        />
      </Card>

      <Card title="Supporting evidence" size="small">
        <List
          size="small"
          dataSource={rec?.evidence ?? []}
          locale={{ emptyText: "No supporting evidence yet" }}
          renderItem={(item) => <List.Item>{item}</List.Item>}
        />
      </Card>
    </Space>
  );
}
