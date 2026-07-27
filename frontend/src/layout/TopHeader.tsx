import { useEffect, useRef } from "react";
import {
  App as AntApp,
  Badge,
  Button,
  Dropdown,
  Select,
  Space,
  Typography,
} from "antd";
import {
  CloudDownloadOutlined,
  DownloadOutlined,
  MoreOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SettingOutlined,
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

function downloadReport(state: unknown, scenarioLabel?: string) {
  const blob = new Blob([JSON.stringify(state, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  anchor.href = url;
  anchor.download = `supply-chain-copilot-report-${scenarioLabel ?? "default"}-${stamp}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function TopHeader() {
  const { message } = AntApp.useApp();
  const location = useLocation();
  const meta = metaForPath(location.pathname);
  const {
    state,
    scenarios,
    setScenarios,
    setState,
    lastUpdated,
    setLastUpdated,
    setMissionStep,
    addActivity,
    setConfigOpen,
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

  const handleExport = () => {
    if (!state) {
      message.warning("Run analysis first to export a report");
      return;
    }
    const scenarioLabel =
      scenarios.length === 0
        ? "default"
        : scenarios.length === 1
          ? scenarios[0]
          : `${scenarios.length}-scenarios`;
    downloadReport(state, scenarioLabel);
    addActivity("Report exported", "info");
    message.success("Report downloaded");
  };

  const overflowItems = {
    items: [
      {
        key: "collect",
        label: "Refresh external data",
        icon: <CloudDownloadOutlined />,
        onClick: handleCollect,
      },
    ],
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
        <Button icon={<DownloadOutlined />} onClick={handleExport}>
          Export Report
        </Button>
        <Button icon={<SettingOutlined />} onClick={() => setConfigOpen(true)}>
          Settings
        </Button>
        <Dropdown menu={overflowItems} trigger={["click"]}>
          <Button icon={<MoreOutlined />} />
        </Dropdown>
      </Space>
    </header>
  );
}
