import { Card, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";

import { useRuns } from "../../api/hooks";
import type { RecentRun } from "../../types/state";

function riskFromSeverity(value?: number): { color: string; label: string } {
  const severity = value ?? 0;
  if (severity >= 8) return { color: "red", label: "HIGH" };
  if (severity >= 5) return { color: "orange", label: "MEDIUM" };
  return { color: "green", label: "LOW" };
}

export default function RecentScenariosTable() {
  const { data: runs, isLoading } = useRuns();

  const columns: ColumnsType<RecentRun> = [
    {
      title: "Scenario Name",
      key: "scenario",
      render: (_, row) => (
        <div>
          <div>{row.scenario_name ?? "Default run"}</div>
          <div style={{ fontSize: 12, color: "#667085" }}>
            {row.created_at ? new Date(row.created_at).toLocaleDateString() : "—"}
          </div>
        </div>
      ),
    },
    {
      title: "Risk Level",
      dataIndex: "max_severity",
      key: "max_severity",
      render: (value?: number) => {
        const tag = riskFromSeverity(value);
        return <Tag color={tag.color}>{tag.label}</Tag>;
      },
    },
    {
      title: "Status",
      key: "status",
      render: () => <Tag color="success">Completed</Tag>,
    },
  ];

  return (
    <Card className="scd-card" title="Recent Scenarios" bordered={false}>
      <Table
        rowKey="run_id"
        size="small"
        loading={isLoading}
        columns={columns}
        dataSource={runs ?? []}
        pagination={{ pageSize: 5, hideOnSinglePage: true }}
      />
    </Card>
  );
}
