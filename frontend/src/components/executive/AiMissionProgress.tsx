import { Card, Steps, Typography } from "antd";
import { CheckCircleOutlined, LoadingOutlined } from "@ant-design/icons";

import { useDashboard } from "../../context/DashboardContext";
import { MISSION_STEPS } from "../../layout/navigation";

const { Text } = Typography;

export default function AiMissionProgress() {
  const { missionStep } = useDashboard();

  const currentIndex =
    missionStep === "complete"
      ? MISSION_STEPS.length
      : missionStep === "idle"
        ? -1
        : MISSION_STEPS.findIndex((step) => step.key === missionStep);

  const items = MISSION_STEPS.map((step, index) => {
    let status: "wait" | "process" | "finish" | "error" = "wait";
    if (missionStep === "complete" || index < currentIndex) {
      status = "finish";
    } else if (index === currentIndex) {
      status = "process";
    }
    return {
      title: step.label,
      status,
      icon:
        status === "finish" ? (
          <CheckCircleOutlined />
        ) : status === "process" ? (
          <LoadingOutlined />
        ) : undefined,
    };
  });

  return (
    <Card className="scd-card" title="AI Mission Progress" bordered={false}>
      <Text type="secondary" style={{ display: "block", marginBottom: 16 }}>
        {missionStep === "complete"
          ? "All agents completed successfully"
          : missionStep === "idle"
            ? "Ready to orchestrate the agent pipeline"
            : "Agents are working through the disruption scenario"}
      </Text>
      <Steps direction="vertical" size="small" items={items} />
    </Card>
  );
}
