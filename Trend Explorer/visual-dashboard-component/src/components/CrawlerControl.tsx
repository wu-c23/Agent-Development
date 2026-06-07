import { useEffect, useState } from "react";
import { Database, RefreshCw } from "lucide-react";
import {
  fetchCrawlerJob,
  isTrendApiEnabled,
  startCrawlerRefresh,
  type CrawlerJobStatus
} from "../api/trendApi";

type CrawlerControlProps = {
  onRefresh: () => Promise<void>;
};

export function CrawlerControl({ onRefresh }: CrawlerControlProps) {
  const apiEnabled = isTrendApiEnabled();
  const [job, setJob] = useState<CrawlerJobStatus | null>(null);
  const [message, setMessage] = useState(apiEnabled ? "API 已连接" : "当前为 Mock 模式");
  const running = job?.status === "queued" || job?.status === "running";

  useEffect(() => {
    if (!job || !running) return;

    const timer = window.setInterval(async () => {
      try {
        const latest = await fetchCrawlerJob(job.id);
        setJob(latest);
        setMessage(statusText(latest));
        if (latest.status === "succeeded") {
          window.clearInterval(timer);
          await onRefresh();
        }
        if (latest.status === "failed") {
          window.clearInterval(timer);
        }
      } catch (err) {
        window.clearInterval(timer);
        setMessage(err instanceof Error ? err.message : "采集状态查询失败");
      }
    }, 2200);

    return () => window.clearInterval(timer);
  }, [job, running, onRefresh]);

  async function handleCrawl() {
    if (!apiEnabled) {
      setMessage("请先设置 VITE_USE_MOCK=false 和 VITE_TREND_API_BASE_URL");
      return;
    }
    try {
      setMessage("正在提交采集任务...");
      const created = await startCrawlerRefresh("zongheng");
      setJob(created);
      setMessage(statusText(created));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "采集任务提交失败");
    }
  }

  async function handleRefreshOnly() {
    try {
      setMessage("正在刷新大屏数据...");
      await onRefresh();
      setMessage("大屏数据已刷新");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "刷新失败");
    }
  }

  return (
    <div className="crawler-control" aria-label="采集控制台">
      <button className="control-button primary" type="button" onClick={handleCrawl} disabled={!apiEnabled || running}>
        <Database size={15} aria-hidden />
        {running ? "采集中" : "采集更新"}
      </button>
      <button className="control-button" type="button" onClick={handleRefreshOnly} disabled={!apiEnabled || running}>
        <RefreshCw size={15} aria-hidden />
        刷新大屏
      </button>
      <span className={job?.status === "failed" ? "control-status status-error" : "control-status"}>{message}</span>
    </div>
  );
}

function statusText(job: CrawlerJobStatus) {
  if (job.status === "queued") return "采集任务排队中";
  if (job.status === "running") return "爬虫正在采集榜单";
  if (job.status === "succeeded") return "采集完成，正在刷新大屏";
  return job.message || "采集失败，请查看 API 日志";
}
