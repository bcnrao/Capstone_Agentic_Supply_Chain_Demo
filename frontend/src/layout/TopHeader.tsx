import { useEffect, useRef } from "react";
import {
  App as AntApp,
  Badge,
  Button,
  Select,
  Space,
  Typography,
} from "antd";
import {
  PlayCircleOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useLocation } from "react-router-dom";

import { useCollect, useRunPipeline, useScenarios } from "../api/hooks";
import { useDashboard, type MissionStep } from "../context/DashboardContext";
import { metaForPath } from "./routes";

const { Title, Text } = Typography;

const MISSION_SEQUENCE: MissionStep[] = [
  "ingest",
  "classify",
  "impact",
  "forecast",
  "simulate",
  "recommend",
  "complete",
];

export default function TopHeader() {
  const { message } = AntApp.useApp();
  const location = useLocation();
  const meta = metaForPath(location.pathname);
  const {
    scenarios,
    setScenarios,
    setState,
    lastUpdated,
    setLastUpdated,
    setMissionStep,
    addActivity,
  } = useDashboard();

  const { data: availableScenarios } = useScenarios();
  const runPipeline = useRunPipeline();
  const collect = useCollect();
  const missionTimer = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (missionTimer.current) {
        window.clearInterval(missionTimer.current);
      }
    };
  }, []);

  const scenarioOptions = [
    { label: "Typhoon approaching Shanghai Port", value: "Typhoon approaching Shanghai Port" },
    ...(availableScenarios ?? [])
      .filter((name) => name !== "Typhoon approaching Shanghai Port")
      .map((name) => ({ label: name, value: name })),
  ];

  const startMissionAnimation = () => {
    let index = 0;
    setMissionStep(MISSION_SEQUENCE[0]);
    if (missionTimer.current) {
      window.clearInterval(missionTimer.current);
    }
    missionTimer.current = window.setInterval(() => {
      index += 1;
      if (index >= MISSION_SEQUENCE.length) {
        if (missionTimer.current) {
          window.clearInterval(missionTimer.current);
        }
        return;
      }
      setMissionStep(MISSION_SEQUENCE[index]);
    }, 900);
  };

  const handleRun = async () => {
    startMissionAnimation();
    addActivity("Pipeline run started", "info");
    try {
      const result = await runPipeline.mutateAsync({
        scenario_names: scenarios,
      });
      setState(result);
      setLastUpdated(new Date());
      setMissionStep("complete");
      addActivity("Pipeline completed", "success");
      message.success("Analysis complete");
    } catch {
      setMissionStep("idle");
      addActivity("Pipeline run failed", "warning");
      message.error("Analysis failed");
    }
  };

  const handleCollect = async () => {
    try {
      const result = await collect.mutateAsync();
      setLastUpdated(new Date());
      addActivity(
        `External data refreshed — ${result.totals.persisted} signals persisted`,
        "success",
      );
      message.success("External data refreshed");
    } catch {
      message.error("Failed to refresh external data");
    }
  };

  const liveLabel = lastUpdated
    ? `Last updated ${lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
    : "Awaiting first run";

  return (
    <header className="scd-top-header">
      <div className="scd-top-header-titles">
        <Title level={3} className="scd-page-title">
          {meta.title}
        </Title>
        <Text type="secondary">{meta.subtitle}</Text>
      </div>

      <Space wrap className="scd-top-header-actions">
        <Select
          className="scd-scenario-select"
          mode="multiple"
          allowClear
          maxTagCount="responsive"
          placeholder="No scenario — use live feed signals"
          options={scenarioOptions}
          value={scenarios}
          onChange={(value) => setScenarios(value)}
          style={{ width: 360 }}
        />
        <Badge status="processing" text={<Text type="secondary">{liveLabel}</Text>} />
        <Button icon={<ReloadOutlined />} onClick={handleCollect} loading={collect.isPending} />
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          loading={runPipeline.isPending}
          onClick={handleRun}
        >
          Run Analysis
        </Button>
      </Space>
    </header>
  );
}
