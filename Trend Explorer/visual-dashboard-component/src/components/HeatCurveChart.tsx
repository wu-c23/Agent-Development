import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { HeatCurveData } from "../api/trendApi";

type HeatCurveChartProps = {
  data: HeatCurveData;
  className?: string;
};

export function HeatCurveChart({ data, className = "chart-fill" }: HeatCurveChartProps) {
  const maxValue = Math.max(...data.series.flatMap((item) => item.data), 0);
  const unit = data.unit || "";
  const option: EChartsOption = {
    color: ["#24c08b", "#f2b84b", "#5aa7ff", "#ff6b86"],
    tooltip: {
      trigger: "axis",
      backgroundColor: "#ffffff",
      borderColor: "#d8e0ea",
      textStyle: { color: "#111827" },
      valueFormatter: (value) => `${value}${unit}`
    },
    legend: {
      type: "scroll",
      top: 0,
      right: 0,
      left: 0,
      icon: "roundRect",
      pageIconColor: "#24c08b",
      pageIconInactiveColor: "#cbd5e1",
      pageTextStyle: { color: "#64748b" },
      textStyle: { color: "#64748b" }
    },
    grid: {
      top: 58,
      left: 32,
      right: 18,
      bottom: 24,
      containLabel: true
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: data.dates,
      axisLine: { lineStyle: { color: "#d8e0ea" } },
      axisLabel: { color: "#64748b" }
    },
    yAxis: {
      type: "value",
      min: 0,
      max: maxValue > 0 ? undefined : 100,
      splitLine: { lineStyle: { color: "rgba(100, 116, 139, 0.16)" } },
      axisLabel: { color: "#64748b", formatter: `{value}${unit}` }
    },
    series: data.series.map((item) => ({
      name: item.name,
      type: "line",
      smooth: true,
      symbolSize: 7,
      lineStyle: { width: 3 },
      areaStyle: { opacity: 0.12 },
      data: item.data
    }))
  };

  return <ReactECharts option={option} className={className} notMerge lazyUpdate />;
}
