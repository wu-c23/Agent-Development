import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import "echarts-wordcloud";
import type { WordCloudItem } from "../api/trendApi";

type DynamicWordCloudProps = {
  words: WordCloudItem[];
};

export function DynamicWordCloud({ words }: DynamicWordCloudProps) {
  const option = {
    tooltip: {
      backgroundColor: "#ffffff",
      borderColor: "#d8e0ea",
      textStyle: { color: "#111827" }
    },
    series: [
      {
        type: "wordCloud",
        shape: "circle",
        left: "center",
        top: "center",
        width: "96%",
        height: "92%",
        sizeRange: [13, 34],
        rotationRange: [-24, 24],
        rotationStep: 12,
        gridSize: 8,
        drawOutOfBound: false,
        textStyle: {
          color: () => {
            const colors = ["#15946c", "#b7791f", "#2563eb", "#db2777", "#475569"];
            return colors[Math.floor(Math.random() * colors.length)];
          }
        },
        emphasis: {
          focus: "self",
          textStyle: {
            color: "#111827",
            textShadowBlur: 8,
            textShadowColor: "rgba(36, 192, 139, 0.22)"
          }
        },
        data: words
      }
    ]
  } as EChartsOption;

  return <ReactECharts option={option} className="chart-fill" notMerge lazyUpdate />;
}
