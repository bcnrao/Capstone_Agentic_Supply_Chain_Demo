import { Card, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { useDashboard } from "../context/DashboardContext";
import type { ImpactMap as ImpactMapModel } from "../types/state";

export default function ImpactMap() {
  const { state } = useDashboard();
  const columns: ColumnsType<ImpactMapModel> = [
    {
      title: "Suppliers",
      dataIndex: "affected_suppliers",
      key: "affected_suppliers",
      render: (value: string[]) => value.join(", "),
    },
    {
      title: "Lanes",
      dataIndex: "affected_lanes",
      key: "affected_lanes",
      render: (value: string[]) => value.join(", "),
    },
    {
      title: "Facilities",
      dataIndex: "affected_facilities",
      key: "affected_facilities",
      render: (value: string[]) => value.join(", "),
    },
    {
      title: "Products",
      dataIndex: "product_categories",
      key: "product_categories",
      render: (value: string[]) => value.join(", "),
    },
    { title: "Reasoning", dataIndex: "reasoning", key: "reasoning" },
  ];

  return (
    <Card title="Affected suppliers, lanes, and facilities" size="small">
      <Table
        rowKey="signal_id"
        size="small"
        columns={columns}
        dataSource={state?.impacts ?? []}
        pagination={{ pageSize: 8 }}
        locale={{ emptyText: "Run the pipeline to map impact" }}
      />
    </Card>
  );
}
