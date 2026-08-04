# 明日方舟本地数据面板

纯本地工具：同步游戏数值到 **MySQL**，浏览干员/敌人/藏品属性，按集成战略难度计算藏品加成后面板。

## 功能

- **拉取并入库**：下载 ArknightsGameData JSON → 结构化写入 MySQL `arknights_helper`
- **属性查看**：干员 / 敌人 / 藏品搜索与详情
- **面板计算**：精英/等级/模组 + 主题难度 + 多选藏品 → 基础面板 vs 加成后面板
- **难度**：藏品升级链（`difficultyUpgradeRelicGroups`）与难度规则修正（基础值 + 修正）

## 准备 MySQL

1. 启动本机 MySQL 服务（例如服务名 `MySQL80`）
2. 建库与账号（可按需改密码）：

```sql
CREATE DATABASE IF NOT EXISTS arknights_helper DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'arknights'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON arknights_helper.* TO 'arknights'@'localhost';
FLUSH PRIVILEGES;
```

3. 复制 `backend/.env.example` → `backend/.env`，填写 `MYSQL_*`
4. 可选：执行 `scripts/mysql_init.sql`（应用启动灌库时也会自动建表）

## 启动

```powershell
# 后端
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 前端（另开终端）
cd frontend
npm install --registry=https://registry.npmmirror.com
npm run dev
```

或运行 `scripts\start_local.ps1`。

- 前端：http://127.0.0.1:5173/
- API：http://127.0.0.1:8000/docs

## 使用

1. 打开「数据管理」→ **一键保存到本地（数据+图标）**（写入 MySQL + 下载图标）
2. 等待图标后台下载完成；也可命令行：

```powershell
backend\.venv\Scripts\python scripts\prepare_local.py
```

3. 本地目录：
   - `data/gamedata/` 游戏 JSON
   - MySQL 库 `arknights_helper`
   - `data/icons/relics/` 藏品 PNG
4. 「面板计算」选择主题难度与藏品，查看最终面板

浏览图标只读本地文件，不会在打开页面时访问外网。

## 数据来源

- [Kengxxiao/ArknightsGameData](https://github.com/Kengxxiao/ArknightsGameData)
- 藏品图标：优先 PRTS（`torappu.prts.wiki`）按 `iconId` 缓存到本地

## 说明

面板与藏品效果为简化模型（ATK%、攻速、伤害% 等，入库为 `relic_effects`）；复杂条件效果未完整模拟。
潜能按 `potentialRanks` 定值累加；天赋仅计入 blackboard 中可识别的常驻属性（条件触发类仍为近似）。
**更新代码后请在「数据管理」执行重建数据库**，以刷新难度修正、潜能与天赋表结构。
