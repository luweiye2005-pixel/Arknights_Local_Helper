import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { Menu } from "antd";
import PanelPage from "./pages/PanelPage";
import DataPage from "./pages/DataPage";

const items = [
  { key: "/", label: <NavLink to="/">面板计算</NavLink> },
  { key: "/data", label: <NavLink to="/data">数据管理</NavLink> },
];

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <header className="app-header">
          <div className="brand">明日方舟 · 本地数据面板</div>
          <Menu
            mode="horizontal"
            selectable={false}
            items={items}
            style={{ flex: 1, minWidth: 0, background: "transparent", borderBottom: "none" }}
          />
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
