import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { Menu } from "antd";
import PanelPage from "./pages/PanelPage";
import DataPage from "./pages/DataPage";

const items = [
  { key: "/", label: "面板计算" },
  { key: "/data", label: "数据管理" },
];

function AppMenu() {
  const location = useLocation();
  return (
    <Menu
      mode="horizontal"
      selectedKeys={[location.pathname]}
      items={items}
      style={{ flex: 1, minWidth: 0, background: "transparent", borderBottom: "none" }}
    />
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <header className="app-header">
          <div className="brand">明日方舟 · 本地数据面板</div>
          <AppMenu />
        </header>
        <main className="app-main">
          <Routes>
            <Route path="/" element={<PanelPage />} />
            <Route path="/data" element={<DataPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
