import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { GenreMigrationData } from "../api/trendApi";

type GenreMigrationGraphProps = {
  data: GenreMigrationData;
  className?: string;
};

export function GenreMigrationGraph({ data, className = "chart-fill" }: GenreMigrationGraphProps) {
  const option: EChartsOption = {
    color: ["#24c08b", "#f2b84b", "#5aa7ff", "#ff6b86", "#b7c2d0"],
    tooltip: {
      trigger: "item",
      backgroundColor: "#ffffff",
      borderColor: "#d8e0ea",
      textStyle: { color: "#111827" }
    },
    series: [
      {
        type: "sankey",
        left: 8,
        right: 16,
        top: 12,
        bottom: 12,
        nodeWidth: 14,
        nodeGap: 10,
        draggable: false,
        emphasis: { focus: "adjacency" },
        lineStyle: {
          color: "gradient",
          curveness: 0.46,
          opacity: 0.38
        },
        label: {
          color: "#334155",
          fontSize: 12
        },
        data: data.nodes,
        links: data.links
      }
    ]
  };

  return <ReactECharts option={option} className={className} notMerge lazyUpdate />;
}
