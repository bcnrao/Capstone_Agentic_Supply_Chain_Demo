import { Card, Empty } from "antd";

import { useDashboard } from "../context/DashboardContext";

export default function TraceJson() {
  const { state } = useDashboard();
  return (
    <Card title="Trace JSON" size="small">
      {state ? (
        <pre className="scd-json">{JSON.stringify(state, null, 2)}</pre>
      ) : (
        <Empty description="Run the pipeline to view the full trace" />
      )}
    </Card>
  );
}
