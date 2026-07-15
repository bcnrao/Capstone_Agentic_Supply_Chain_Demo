import { Card, Timeline, Typography } from "antd";
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
} from "@ant-design/icons";

import { useDashboard } from "../../context/DashboardContext";

const { Text } = Typography;

export default function ActivityTimeline() {
  const { activityLog } = useDashboard();

  return (
    <Card className="scd-card" title="Activity Timeline" bordered={false}>
      <Timeline
        items={activityLog.map((entry) => ({
          color:
            entry.kind === "success"
              ? "green"
              : entry.kind === "warning"
                ? "orange"
                : "blue",
          dot:
            entry.kind === "success" ? (
              <CheckCircleOutlined />
            ) : entry.kind === "warning" ? (
              <ExclamationCircleOutlined />
            ) : (
              <InfoCircleOutlined />
            ),
          children: (
            <div>
              <Text strong>{entry.time}</Text>
              <div>{entry.message}</div>
            </div>
          ),
        }))}
      />
      {activityLog.length === 0 && (
        <Text type="secondary">Activity will appear here after you run analysis.</Text>
      )}
    </Card>
  );
}
