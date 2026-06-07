import { useMemo, useState } from "react";
import type { GenreCloudTimelineData } from "../api/trendApi";
import { DynamicWordCloud } from "./DynamicWordCloud";

type GenreCloudTimelineProps = {
  data: GenreCloudTimelineData;
  detail?: boolean;
};

export function GenreCloudTimeline({ data, detail = false }: GenreCloudTimelineProps) {
  const [activePeriod, setActivePeriod] = useState(data.clouds[data.clouds.length - 1]?.period || "");
  const activeCloud = useMemo(
    () => data.clouds.find((item) => item.period === activePeriod) || data.clouds[data.clouds.length - 1],
    [activePeriod, data.clouds]
  );
  const latest = data.clouds[data.clouds.length - 1];
  const previous = data.clouds[data.clouds.length - 2];

  if (!activeCloud) {
    return <div className="empty-panel">暂无流派词云数据</div>;
  }

  return (
    <div className={`genre-cloud-timeline ${detail ? "genre-cloud-detail" : ""}`}>
      <div className="month-tabs" role="tablist" aria-label="流派词云月份">
        {data.clouds.map((cloud) => (
          <button
            className={cloud.period === activeCloud.period ? "month-tab active" : "month-tab"}
            type="button"
            key={cloud.period}
            onClick={() => setActivePeriod(cloud.period)}
          >
            {cloud.period}
          </button>
        ))}
      </div>

      <div className="genre-cloud-body">
        <DynamicWordCloud words={activeCloud.genres} />
      </div>

      {detail && (
        <div className="genre-cloud-insights">
          <p>{data.summary || "按月份对比各流派月票热度，观察流派重心的迁移。"}</p>
          <div className="genre-compare-grid">
            {activeCloud.genres.slice(0, 12).map((genre) => (
              <article className="genre-compare-card" key={genre.name}>
                <span>{genre.name}</span>
                <strong>
                  {genre.value}
                  {data.unit || ""}
                </strong>
                <small>{describeGenreChange(genre.name, latest, previous, data.unit || "")}</small>
              </article>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function describeGenreChange(
  genre: string,
  latest: GenreCloudTimelineData["clouds"][number] | undefined,
  previous: GenreCloudTimelineData["clouds"][number] | undefined,
  unit: string
) {
  const latestValue = latest?.genres.find((item) => item.name === genre)?.value ?? 0;
  const previousValue = previous?.genres.find((item) => item.name === genre)?.value ?? 0;
  const delta = latestValue - previousValue;
  if (!previous) return `当前热度 ${latestValue}${unit}`;
  if (delta > 0) return `较上月 +${roundValue(delta)}${unit}`;
  if (delta < 0) return `较上月 ${roundValue(delta)}${unit}`;
  return "较上月持平";
}

function roundValue(value: number) {
  return Number.isInteger(value) ? value : value.toFixed(1);
}
