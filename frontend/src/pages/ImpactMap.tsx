import { Alert, Card, Space, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { useDashboard } from "../context/DashboardContext";
import type { ImpactMap as ImpactMapModel } from "../types/state";

interface DontCareRow {
  key: string;
  event: string;
  category: string;
  reason: string;
}

export default function ImpactMap() {
  const { state } = useDashboard();
  const impacts = state?.impacts ?? [];
  const catById = new Map((state?.classifications ?? []).map((c) => [c.signal_id, c.category]));
  const titleById = new Map((state?.new_signals ?? []).map((s) => [s.signal_id, s.title]));

  const material = impacts.filter((i) => (i.affected_entities?.length ?? 0) > 0);
  const dontcare = impacts.filter((i) => (i.affected_entities?.length ?? 0) === 0);

  const fallbackHeadline =
    `${material.length} event(s) materially impact the network` +
    (dontcare.length > 0 ? `; ${dontcare.length} are don't-cares outside our footprint` : "") +
    ".";

  const materialColumns: ColumnsType<ImpactMapModel> = [
    { title: "Suppliers", dataIndex: "affected_suppliers", key: "suppliers", render: (v: string[]) => v.join(", ") },
    { title: "Lanes", dataIndex: "affected_lanes", key: "lanes", render: (v: string[]) => v.join(", ") },
    { title: "Facilities", dataIndex: "affected_facilities", key: "facilities", render: (v: string[]) => v.join(", ") },
    { title: "Products", dataIndex: "product_categories", key: "products", render: (v: string[]) => v.join(", ") },
    { title: "Reasoning", dataIndex: "reasoning", key: "reasoning" },
  ];

  const dontcareColumns: ColumnsType<DontCareRow> = [
    { title: "Event", dataIndex: "event", key: "event", ellipsis: true },
    { title: "Category", dataIndex: "category", key: "category" },
    { title: "Reason", dataIndex: "reason", key: "reason" },
  ];
  const dontcareRows: DontCareRow[] = dontcare.map((i) => ({
    key: i.signal_id,
    event: titleById.get(i.signal_id) ?? "",
    category: catById.get(i.signal_id) ?? "",
    reason: i.reasoning,
  }));

  const summaryText =
    impacts.length === 0
      ? "Run the pipeline to see the impact assessment."
      : state?.impact_summary ?? fallbackHeadline;

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Alert
        type={material.length ? "warning" : "info"}
        showIcon
        message="🧠 Impact summary"
        description={<div style={{ whiteSpace: "pre-line" }}>{summaryText}</div>}
      />

      <Card title="Affected entities (material impact)" size="small">
        <Table
          rowKey="signal_id"
          size="small"
          columns={materialColumns}
          dataSource={material}
          pagination={{ pageSize: 8 }}
          locale={{ emptyText: "No material impact this run" }}
        />
      </Card>

      {dontcareRows.length > 0 && (
        <Card title="Don't-care (no material impact — monitored only)" size="small">
          <Table
            rowKey="key"
            size="small"
            columns={dontcareColumns}
            dataSource={dontcareRows}
            pagination={{ pageSize: 8 }}
          />
        </Card>
      )}
    </Space>
  );
}
