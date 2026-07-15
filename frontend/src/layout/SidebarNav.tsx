import { NavLink } from "react-router-dom";
import { Layout, Progress, Typography } from "antd";

import { useDashboard } from "../context/DashboardContext";
import { MISSION_STEPS, NAV_GROUPS } from "./navigation";

const { Sider } = Layout;
const { Text } = Typography;

export default function SidebarNav() {
  const { missionStep } = useDashboard();

  const missionIndex =
    missionStep === "idle" || missionStep === "complete"
      ? missionStep === "complete"
        ? MISSION_STEPS.length
        : 0
      : MISSION_STEPS.findIndex((step) => step.key === missionStep) + 1;

  const missionPercent =
    missionStep === "complete"
      ? 100
      : missionStep === "idle"
        ? 0
        : Math.round((missionIndex / MISSION_STEPS.length) * 100);

  const missionLabel =
    missionStep === "complete"
      ? "Mission complete"
      : missionStep === "idle"
        ? "Ready to run"
        : MISSION_STEPS.find((s) => s.key === missionStep)?.label ?? "In progress";

  return (
    <Sider width={240} className="scd-sider" theme="light">
      <div className="scd-brand">
        <div className="scd-brand-icon">⬡</div>
        <div>
          <Text strong className="scd-brand-title">
            ASCDP
          </Text>
          <Text type="secondary" className="scd-brand-sub">
            Agentic Supply Chain
          </Text>
        </div>
      </div>

      <nav className="scd-nav">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="scd-nav-group">
            <Text className="scd-nav-group-label">{group.label}</Text>
            {group.items.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === "/"}
                  className={({ isActive }) =>
                    `scd-nav-item${isActive ? " scd-nav-item-active" : ""}`
                  }
                >
                  <Icon />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="scd-mission-card">
        <Text strong className="scd-mission-title">
          AI Mission
        </Text>
        <Text type="secondary" className="scd-mission-status">
          {missionLabel}
        </Text>
        <Progress
          percent={missionPercent}
          size="small"
          showInfo={false}
          strokeColor="#fa541c"
        />
      </div>
    </Sider>
  );
}
