import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { GenreMigrationTimelineData } from "../api/trendApi";

type MigrationTimelineChartProps = {
  data: GenreMigrationTimelineData;
  className?: string;
};

export function MigrationTimelineChart({ data, className = "chart-fill" }: MigrationTimelineChartProps) {
  const rows = data.flows.map((flow) => `${flow.source} -> ${flow.target}`);
  const points = data.flows.flatMap((flow, flowIndex) =>
    flow.values.map((value, periodIndex) => [periodIndex, flowIndex, value, flow.source, flow.target])
  );
  const maxValue = Math.max(...data.flows.flatMap((flow) => flow.values), 1);

  const option: EChartsOption = {
    tooltip: {
      trigger: "item",
      backgroundColor: "#ffffff",
      borderColor: "#d8e0ea",
      textStyle: { color: "#111827" },
      formatter: (params) => {
        const rawParams = params as unknown as { value: [number, number, number, string, string] };
        const value = rawParams.value;
        return `${data.periods[value[0]]}<br/>${value[3]} -> ${value[4]}<br/>迁移强度：${value[2]}`;
      }
    },
    grid: {
      top: 22,
      left: 24,
      right: 28,
      bottom: 26,
      containLabel: true
    },
    visualMap: {
      show: false,
      min: 0,
      max: maxValue,
      inRange: {
        color: ["#e2e8f0", "#5aa7ff", "#24c08b", "#f2b84b"]
      }
    },
    xAxis: {
      type: "category",
      name: "时间",
      nameTextStyle: { color: "#64748b" },
      data: data.periods,
      axisLine: { lineStyle: { color: "#d8e0ea" } },
      axisTick: { show: false },
      axisLabel: { color: "#64748b" }
    },
    yAxis: {
      type: "category",
      data: rows,
      inverse: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#334155",
        width: 150,
        overflow: "truncate"
      }
    },
    series: [
      {
        type: "scatter",
        data: points,
        symbolSize: (value) => {
          const row = value as [number, number, number];
          return Math.max(10, Math.min(32, row[2] * 1.2));
        },
        itemStyle: {
          borderColor: "rgba(15, 23, 42, 0.18)",
          borderWidth: 1,
          opacity: 0.92
        },
        emphasis: {
          focus: "series",
          scale: true
        }
      }
    ]
  };

  return <ReactECharts option={option} className={className} notMerge lazyUpdate />;
}
