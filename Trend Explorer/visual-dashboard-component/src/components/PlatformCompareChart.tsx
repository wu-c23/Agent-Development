import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { PlatformCompareItem } from "../api/trendApi";

type PlatformCompareChartProps = {
  data: PlatformCompareItem[];
};

export function PlatformCompareChart({ data }: PlatformCompareChartProps) {
  const option: EChartsOption = {
    color: ["#24c08b", "#f2b84b"],
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "#ffffff",
      borderColor: "#d8e0ea",
      textStyle: { color: "#111827" },
      formatter: (params) => {
        const rows = Array.isArray(params) ? params : [params];
        const index = rows[0]?.dataIndex ?? 0;
        const item = data[index];
        const tags = item?.topTags.join(" / ") || "";
        const status = item?.status === "active" ? "可用" : "待补充";
        return `${item.platform}<br/>热度：${item.heat}<br/>作品数：${item.works}<br/>状态：${status}<br/>标签：${tags}`;
      }
    },
    grid: {
      top: 18,
      left: 28,
      right: 18,
      bottom: 24,
      containLabel: true
    },
    xAxis: {
      type: "category",
      data: data.map((item) => item.platform),
      axisLine: { lineStyle: { color: "#d8e0ea" } },
      axisLabel: { color: "#64748b" }
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: "rgba(100, 116, 139, 0.16)" } },
      axisLabel: { color: "#64748b" }
    },
    series: [
      {
        name: "平台热度",
        type: "bar",
        barMaxWidth: 36,
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: (params) => (data[params.dataIndex]?.status === "active" ? "#24c08b" : "#cbd5e1")
        },
        label: {
          show: true,
          position: "top",
          color: "#334155",
          formatter: (params) => (Number(params.value) > 0 ? String(params.value) : "待导入")
        },
        data: data.map((item) => item.heat)
      }
    ]
  };

  return <ReactECharts option={option} className="chart-fill" notMerge lazyUpdate />;
}
