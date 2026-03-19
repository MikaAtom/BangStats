import { Link } from "react-router-dom";
import type { ScanJob, SyncJob } from "../../api";
import { EmptyState } from "../ui/EmptyState";

interface JobListProps {
  jobs: Array<ScanJob | SyncJob>;
  kind: "scan" | "sync";
}

export function JobList({ jobs, kind }: JobListProps) {
  if (!jobs.length) return <EmptyState text="No jobs yet." />;
  return (
    <ul className="job-list">
      {jobs.map((job) => (
        <li key={job.id}>
          <div>
            <strong>#{job.id}</strong> <span className={`status status-${job.status}`}>{job.status}</span>
          </div>
          <div className="inline-meta">
            {"total_files" in job ? `${job.processed}/${job.total_files} processed` : `${job.server.toUpperCase()} sync`}
          </div>
          {kind === "scan" && <Link to={`/scan/jobs/${job.id}`}>Open detail</Link>}
        </li>
      ))}
    </ul>
  );
}
