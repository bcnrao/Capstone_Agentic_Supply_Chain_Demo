import { Layout } from "antd";
import { Outlet } from "react-router-dom";

import ConfigModal from "../components/ConfigModal";
import { useDashboard } from "../context/DashboardContext";
import SidebarNav from "./SidebarNav";
import TopHeader from "./TopHeader";

const { Content } = Layout;

export default function AppShell() {
  const { configOpen, setConfigOpen } = useDashboard();

  return (
    <Layout className="scd-app-layout">
      <SidebarNav />
      <Layout>
        <TopHeader />
        <Content className="scd-content">
          <Outlet />
        </Content>
      </Layout>
      <ConfigModal open={configOpen} onClose={() => setConfigOpen(false)} />
    </Layout>
  );
}
