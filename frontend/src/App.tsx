import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Menu } from "antd";
import PanelPage from "./pages/PanelPage";

const items = [
  { key: "/", label: "面板计算" },
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
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
