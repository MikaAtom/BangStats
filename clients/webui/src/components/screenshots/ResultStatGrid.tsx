import type { User } from "../../api";
import { formatDateTime, formatLiveType, webLocale } from "../../utils/format";

export type ResultStatSource = {
  perfect?: number;
  great?: number;
  good?: number;
  bad?: number;
  miss?: number;
  fast?: number;
  slow?: number;
  max_combo?: number;
  accuracy?: number;
  live_type?: string;
  timestamp?: string | null;
  score?: number;
};

export function ResultStatGrid({
  item,
  server,
  showMetaFooter = true,
}: {
  item: ResultStatSource;
  server: User["server"];
  /** When false, omit live type / timestamp / prominent score (compact cards). */
  showMetaFooter?: boolean;
}) {
  const n = (v: number | undefined) => (typeof v === "number" && Number.isFinite(v) ? v : 0);
  const loc = webLocale(server);
  return (
    <div className="stack">
      {showMetaFooter && item.score != null && item.score > 0 ? (
        <div className="result-screen__scoreline">
          <span className="result-screen__label">Score</span>
          <span className="result-screen__value result-screen__value--score">{item.score.toLocaleString(loc)}</span>
        </div>
      ) : null}
      <div className="result-screen result-screen--split">
        <div className="result-screen__col result-screen__col--judgments">
          <div className="result-screen__cell">
            <span className="result-screen__label">Perfect</span>
            <span className="result-screen__value">{n(item.perfect)}</span>
          </div>
          <div className="result-screen__cell">
            <span className="result-screen__label">Great</span>
            <span className="result-screen__value">{n(item.great)}</span>
          </div>
          <div className="result-screen__cell">
            <span className="result-screen__label">Good</span>
            <span className="result-screen__value">{n(item.good)}</span>
          </div>
          <div className="result-screen__cell">
            <span className="result-screen__label">Bad</span>
            <span className="result-screen__value">{n(item.bad)}</span>
          </div>
          <div className="result-screen__cell">
            <span className="result-screen__label">Miss</span>
            <span className="result-screen__value">{n(item.miss)}</span>
          </div>
        </div>
        <div className="result-screen__col result-screen__col--timing">
          <div className="result-screen__cell">
            <span className="result-screen__label">Fast</span>
            <span className="result-screen__value">{n(item.fast)}</span>
          </div>
          <div className="result-screen__cell">
            <span className="result-screen__label">Slow</span>
            <span className="result-screen__value">{n(item.slow)}</span>
          </div>
          <div className="result-screen__cell">
            <span className="result-screen__label">Max combo</span>
            <span className="result-screen__value">{n(item.max_combo)}</span>
          </div>
        </div>
      </div>
      {typeof item.accuracy === "number" && (
        <div className="inline-meta">Accuracy {item.accuracy}%</div>
      )}
      {showMetaFooter && (
        <div className="inline-meta">
          {item.live_type ? `${formatLiveType(item.live_type)} · ` : ""}
          {item.timestamp ? formatDateTime(item.timestamp, server) : ""}
        </div>
      )}
    </div>
  );
}
