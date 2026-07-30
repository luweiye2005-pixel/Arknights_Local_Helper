import { useEffect, useRef, useState } from "react";
import { Alert, Button, Card, Descriptions, Progress, Space, Typography, message } from "antd";
import {
  assetsStatus,
  knowledgeStatus,
  prepareLocal,
  prefetchRelicIcons,
  rebuildDb,
  refreshThemeEnemies,
  reloadGamedata,
  syncGamedata,
} from "../api/client";

const { Title, Paragraph, Text } = Typography;

export default function DataPage() {
  const [status, setStatus] = useState<any>();
  const [loading, setLoading] = useState(false);
  const [dl, setDl] = useState<any>();
  const pollRef = useRef<number>();

  async function refresh() {
    const s = await knowledgeStatus();
    setStatus(s);
    setDl(s.download || (await assetsStatus()));
  }

  useEffect(() => {
    refresh().catch((e) => message.error(e.message));
    return () => window.clearInterval(pollRef.current);
  }, []);

  function startPolling() {
    window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      try {
        const a = await assetsStatus();
        setDl(a);
        if (!a.running) {
          window.clearInterval(pollRef.current);
          await refresh();
        }
      } catch {
        /* ignore */
      }
    }, 1500);
  }

  function showCounts(r: any) {
    const c = r.db_counts || r.counts || {};
    message.success(`库内：干员 ${c.operators ?? "-"} / 敌人 ${c.enemies ?? "-"} / 藏品 ${c.relics ?? "-"}`);
  }

  async function onPrepare() {
    setLoading(true);
    try {
      message.info("正在准备本地数据（JSON + 数据库 + 后台下图标）…");
      const r = await prepareLocal(true);
      await refresh();
      showCounts(r.data || r);
      startPolling();
      message.success(r.message || "已开始本地化");
    } catch (e: any) {
      message.error(String(e?.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }

  async function onSync() {
    setLoading(true);
    try {
      const r = await syncGamedata();
      await refresh();
      showCounts(r);
    } catch (e: any) {
      message.error(String(e?.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }

  async function onReload() {
    setLoading(true);
    try {
      const r = await reloadGamedata();
      await refresh();
      showCounts(r);
    } catch (e: any) {
      message.error(String(e?.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }

  async function onRebuild() {
    setLoading(true);
    try {
      const r = await rebuildDb();
      await refresh();
      showCounts(r);
    } catch (e: any) {
      message.error(String(e?.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }

  async function onPrefetch() {
    setLoading(true);
    try {
      const r = await prefetchRelicIcons(true);
      setDl(r);
      startPolling();
      message.success("已开始补全藏品图标（会重试之前的占位图）");
    } catch (e: any) {
      message.error(String(e?.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }

  async function onRefreshThemeEnemies() {
    setLoading(true);
    try {
      message.info("正在同步关卡并刷新主题敌人池（可能较久）…");
      const r = await refreshThemeEnemies(true);
      await refresh();
      const c = r.counts || {};
      message.success(`主题敌人已刷新：共 ${c.theme_enemies ?? "-"} 条`);
    } catch (e: any) {
      message.error(String(e?.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }

  const mem = status?.memory_counts || {};
  const dbc = status?.db_counts || status?.counts || {};
  const icons = status?.icons || dl?.icons || {};
  const progress =
    dl?.total > 0 ? Math.round(((dl.done || 0) / dl.total) * 100) : icons.relics_in_db
      ? Math.round(((icons.cached || 0) / Math.max(icons.relics_in_db, 1)) * 100)
      : 0;

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <div>
        <Title level={3} style={{ marginBottom: 4 }}>
          数据管理
        </Title>
        <Paragraph className="muted">
          将游戏 JSON 与藏品图标提前保存到本地：
          <Text code>data/gamedata</Text>、MySQL（<Text code>arknights_helper</Text>）、
          <Text code>data/icons/relics</Text>。之后可离线使用。
        </Paragraph>
      </div>

      {status && (
        <Alert
          type={status.local_ready ? "success" : status.in_sync ? "info" : "warning"}
          showIcon
          message={
            status.local_ready
              ? "本地数据较完整（数据库 + 过半图标已缓存）"
              : status.in_sync
                ? "数据库已就绪，建议继续下载藏品图标到本地"
                : "内存与数据库不一致：请重载或重建"
          }
        />
      )}

      <Card className="panel" bordered={false} loading={!status}>
        {status && (
          <Descriptions column={1} size="small">
            <Descriptions.Item label="JSON 目录">{status.gamedata_dir}</Descriptions.Item>
            <Descriptions.Item label="MySQL">{status.mysql_dsn || "-"}</Descriptions.Item>
            <Descriptions.Item label="图标目录">{status.icons_dir}</Descriptions.Item>
            <Descriptions.Item label="内存解析">
              干员 {mem.operators ?? "-"} / 敌人 {mem.enemies ?? "-"} / 藏品 {mem.relics ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="数据库">
              干员 {dbc.operators ?? "-"} / 敌人 {dbc.enemies ?? "-"} / 藏品 {dbc.relics ?? "-"} / 模组{" "}
              {dbc.modules ?? "-"} / 主题敌人 {dbc.theme_enemies ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="本地图标">
              已缓存 {icons.cached ?? 0} / 库内藏品 {icons.relics_in_db ?? 0}
              （真图 {icons.png ?? 0} · 占位 {icons.placeholder ?? 0} · 缺失 {icons.missing ?? "-"}）
            </Descriptions.Item>
            <Descriptions.Item label="图标下载">
              {dl?.running ? (
                <div style={{ maxWidth: 420 }}>
                  <div>
                    {dl.message}（成功 {dl.ok} / 跳过 {dl.skipped} / 失败 {dl.fail}）
                  </div>
                  <Progress percent={progress} status="active" />
                </div>
              ) : (
                <span>
                  {dl?.message || "空闲"} · 覆盖率约 {progress}%
                </span>
              )}
            </Descriptions.Item>
          </Descriptions>
        )}
        <Space style={{ marginTop: 16 }} wrap>
          <Button type="primary" loading={loading} onClick={onPrepare}>
            一键保存到本地（数据+图标）
          </Button>
          <Button loading={loading} onClick={onSync}>
            仅拉取 JSON 并入库
          </Button>
          <Button loading={loading} onClick={onReload}>
            从本地 JSON 重载
          </Button>
          <Button loading={loading} onClick={onRebuild}>
            仅重建 SQLite
          </Button>
          <Button loading={loading} onClick={onPrefetch} disabled={!!dl?.running}>
            下载全部藏品图标
          </Button>
          <Button loading={loading} onClick={onRefreshThemeEnemies}>
            刷新主题敌人池
          </Button>
          <Button onClick={() => refresh()}>刷新状态</Button>
        </Space>
      </Card>
    </Space>
  );
}
