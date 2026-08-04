# 明日方舟离线面板

非官方 Windows 离线桌面工具，用于计算干员、敌人、模组与集成战略藏品对面板和最终伤害的影响。

## 普通用户

1. 从 Releases 下载 `ArknightsOfflinePanel-win64.zip`。
2. 解压到任意可写目录。
3. 双击 `ArknightsOfflinePanel.exe`。

桌面版内置计算数据、藏品规则、图标和 WebView2 固定运行时，不需要安装 Python、Node、MySQL，也不会联网更新数据。用户配置保存在 `%LOCALAPPDATA%\ArknightsOfflinePanel\panel_state.json`。

计算采用简化模型，仅关注敌我面板与最终单次伤害；技力、部署费用、阻挡数、招募、资源和探索流程等效果不计算。结果仅供参考，不代表游戏官方结果。

## 项目结构

- `backend/app/combat`：Python 计算核心。
- `backend/app/data/json_db.py`：桌面版只读数据层。
- `frontend`：React 计算界面；桌面发布版不包含数据管理页面。
- `scripts/desktop_data.py`：开发者数据维护命令。
- `scripts/build_desktop.ps1`：Windows 测试、构建和打包。

## 开发者更新数据

开发环境在迁移期仍可使用 MySQL。复制 `backend/.env.example` 为 `backend/.env`，配置数据库后执行：

```powershell
# 拉取原始数据
backend\.venv\Scripts\python.exe scripts\desktop_data.py sync

# 应用人工审核规则并审计
cd backend
.\.venv\Scripts\python.exe ..\scripts\apply_relic_fix_plan.py
.\.venv\Scripts\python.exe ..\scripts\desktop_data.py audit

# 只允许 approved active 规则进入正式数据包
.\.venv\Scripts\python.exe ..\scripts\desktop_data.py build-data
```

迁移期间可用 `build-data --allow-pending` 生成对比测试包，但该选项不得用于正式 Release。

## 本地开发

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000

cd frontend
npm ci
npm run dev
```

## Windows 打包

将微软 WebView2 Fixed Version Runtime x64 解压到 `vendor/WebView2/`，然后执行：

```powershell
.\scripts\build_desktop.ps1
```

正式构建在存在未审核 active 藏品规则时会失败。`-AllowPending` 仅用于迁移期桌面冒烟测试。

## 数据来源与许可

源代码采用 MIT License。游戏数据和图片不适用 MIT License；发布前必须遵循 [THIRD_PARTY_NOTICE.md](THIRD_PARTY_NOTICE.md) 中的来源、版权和再分发要求。
