import { ArrowUpRight, ExternalLink } from "lucide-react";
import type { RisingWork } from "../api/trendApi";

type RisingWorksTableProps = {
  works: RisingWork[];
  mode?: "compact" | "detail";
};

export function RisingWorksTable({ works, mode = "compact" }: RisingWorksTableProps) {
  const isDetail = mode === "detail";

  return (
    <div className={`works-table works-table-${mode}`} role="table" aria-label="上升作品榜">
      <div className="works-row works-head" role="row">
        <span>作品</span>
        <span>平台</span>
        <span>榜单</span>
        <span>升幅</span>
      </div>
      {works.map((work) => (
        <div className="works-row" role="row" key={work.id}>
          <div className="work-title-cell">
            {work.detailUrl ? (
              <a className="work-title-link" href={work.detailUrl} target="_blank" rel="noreferrer">
                <strong>{work.title}</strong>
                <ExternalLink size={13} aria-hidden />
              </a>
            ) : (
              <strong>{work.title}</strong>
            )}
            <small>
              {work.author || "未知作者"} · {work.category || "未分类"}
            </small>
            <div className="tag-line">
              {work.tags.slice(0, isDetail ? 12 : 6).map((tag) => (
                <span key={tag}>{tag}</span>
              ))}
              {work.tags.length > (isDetail ? 12 : 6) && <span>+{work.tags.length - (isDetail ? 12 : 6)}</span>}
            </div>
            {isDetail && work.summary && <p className="work-summary">{work.summary}</p>}
          </div>
          <span className={work.platform.includes("起点") ? "muted-cell" : ""}>{work.platform}</span>
          <span>
            {work.listType}
            {isDetail && (
              <small className="cell-subtext">
                排名 {work.rank || "待补"} · 热度 {work.heatScore}
              </small>
            )}
          </span>
          <span className={work.rankChange > 0 ? "rank-rise" : "muted-cell"}>
            {work.rankChange > 0 && <ArrowUpRight size={15} aria-hidden />}
            {work.rankChange > 0 ? `+${work.rankChange}` : "待补"}
          </span>
        </div>
      ))}
    </div>
  );
}
