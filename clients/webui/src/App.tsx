import type { ReactNode } from "react";
import { FormEvent, useEffect, useState } from "react";
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";

import { useAuth } from "./auth";
import {
  api,
  type ActivityResponse,
  type CalendarResponse,
  type DashboardResponse,
  type ErrorCategoryActionResponse,
  type ErrorDetail,
  type ErrorList,
  type EventStatsResponse,
  type FilenameDiffResponse,
  type InsightsResponse,
  type MilestonesResponse,
  type MetaSongConfigResponse,
  type ProgressionResponse,
  type RecapResponse,
  type SongRankingsResponse,
  type ScanJob,
  type ScanResult,
  type ScreenshotItem,
  type StatsRangeQuery,
  type SongJourneyResponse,
  type SongStatsResponse,
  type StatsOverview,
  type SyncJob,
  type UploadFileItem,
  type User,
} from "./api";

// Imported components
import { Card, MetricCard, LoadingCard, LoadingInline, EmptyState, SectionHeader, SecureImage, DateRangePicker, type DateRangeValue } from "./components/ui";
import { KeyValueList, JobList } from "./components/data-display";
import { BarChart, ActivityBars, CalendarHeatmap, TrendChart } from "./components/charts";
import { UploadGallery, ScreenshotGallery } from "./components/galleries";
import {
  formatDateRange,
  formatDateTime,
  formatDifficulty,
  formatEventBoundary,
  formatEventLabel,
  formatLiveType,
  formatShortDate,
  groupActiveHours,
  resolveEventName,
} from "./utils/format";

type Loadable<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
};

type AnalyticsView = "overview" | "progress" | "milestones" | "songs" | "events" | "recap" | "screenshots";

type SectionFilterState = {
  difficulty: string;
  liveType: string;
  includeMeta: boolean;
};

type SidebarItem = {
  to: string;
  label: string;
  isActive: (pathname: string) => boolean;
};

type RecapScope = "weekly" | "monthly" | "seasonal" | "yearly" | "event";

const DEFAULT_DATE_RANGE: DateRangeValue = {
  preset: "30d",
  from: "",
  to: "",
};

const ANALYTICS_VIEWS: AnalyticsView[] = ["overview", "progress", "milestones", "songs", "events", "recap", "screenshots"];
const DIFFICULTY_FILTERS = ["easy", "normal", "hard", "expert", "special"];
const LIVE_TYPE_FILTERS = ["normal_live", "event_live", "challenge_live", "multi_live", "vs_live", "free_live"];

function useLoadable<T>(loader: (() => Promise<T>) | null, deps: unknown[] = []): Loadable<T> & { reload: () => Promise<void> } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(loader));
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    if (!loader) return;
    setLoading(true);
    setError(null);
    try {
      const next = await loader();
      setData(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, deps);

  return { data, loading, error, reload };
}

function dateRangeToQuery(range: DateRangeValue) {
  if (range.preset === "custom") {
    return { from_date: range.from || undefined, to_date: range.to || undefined };
  }
  return { preset: range.preset };
}

function resolveAbsoluteDateRange(range: DateRangeValue): StatsRangeQuery | null {
  if (range.preset === "custom") {
    if (!range.from || !range.to) return null;
    return { from_date: range.from, to_date: range.to };
  }
  const end = new Date();
  const daysByPreset: Record<string, number> = { "7d": 7, "30d": 30, "90d": 90, "1y": 365 };
  const days = daysByPreset[range.preset];
  if (!days) return null;
  const start = new Date(end);
  start.setDate(end.getDate() - (days - 1));
  return {
    from_date: start.toISOString().slice(0, 10),
    to_date: end.toISOString().slice(0, 10),
  };
}

function sectionFiltersToQuery(filters: SectionFilterState) {
  return {
    difficulty: filters.difficulty || undefined,
    live_type: filters.liveType || undefined,
    include_meta: filters.includeMeta,
  };
}

function App() {
  const auth = useAuth();
  if (auth.loading) {
    return <div className="center-screen">Loading session...</div>;
  }
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/legacy-login" element={<LegacyLoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/*" element={<ProtectedLayout />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function ProtectedLayout() {
  const auth = useAuth();
  const location = useLocation();
  if (!auth.user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  const isAdmin = auth.user.role === "admin";
  const sidebarItems: SidebarItem[] = [
    { to: "/dashboard", label: "Dashboard", isActive: (pathname) => pathname.startsWith("/dashboard") || pathname === "/" },
    {
      to: "/scan",
      label: "Scan",
      isActive: (pathname) => pathname.startsWith("/scan") && !pathname.startsWith("/scan/errors"),
    },
    { to: "/scan/errors", label: "Error Inbox", isActive: (pathname) => pathname.startsWith("/scan/errors") },
    { to: "/stats", label: "Stats", isActive: (pathname) => pathname.startsWith("/stats") },
    { to: "/settings", label: "Settings", isActive: (pathname) => pathname.startsWith("/settings") || pathname.startsWith("/sync") },
    ...(isAdmin ? [{ to: "/admin", label: "Admin", isActive: (pathname: string) => pathname.startsWith("/admin") }] : []),
  ];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-kicker">Bang Dream Tracker</div>
          <h1>BangStats</h1>
          <p>Self-hosted stats, scans, screenshots, and maintenance tools.</p>
        </div>
        <nav className="nav">
          {sidebarItems.map((item) => (
            <NavLink key={item.to} to={item.to} className={item.isActive(location.pathname) ? "nav-link active" : "nav-link"}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-pill">
            <strong>{auth.user.username}</strong>
            <span>{auth.user.server.toUpperCase()} server</span>
          </div>
        </div>
      </aside>
      <main className="content">
        <header className="topbar">
          <div>
            <div className="topbar-title">{pageTitle(location.pathname)}</div>
            <div className="topbar-subtitle">Everything the CLI can do, with visuals on top.</div>
          </div>
          <button
            className="button ghost"
            onClick={() => {
              void api.logout().catch(() => undefined).finally(() => auth.logout());
            }}
          >
            Logout
          </button>
        </header>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/sync" element={<SyncPage />} />
          <Route path="/scan" element={<ScanPage />} />
          <Route path="/scan/jobs/:jobId" element={<ScanJobPage />} />
          <Route path="/scan/errors" element={<ErrorInboxPage />} />
          <Route path="/scan/errors/:errorType/:jsonFilename" element={<ErrorDetailPage />} />
          <Route path="/stats" element={<StatsPage />} />
          <Route path="/stats/song/:songId" element={<SongStatsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/admin" element={isAdmin ? <AdminPage /> : <Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function pageTitle(pathname: string) {
  if (pathname.startsWith("/scan/errors")) return "Scan Error Maintenance";
  if (pathname.startsWith("/scan/jobs")) return "Scan Job Detail";
  if (pathname.startsWith("/scan")) return "Scan Operations";
  if (pathname.startsWith("/stats/song")) return "Song Drilldown";
  if (pathname.startsWith("/stats")) return "Stats and Analytics";
  if (pathname.startsWith("/sync")) return "Reference Sync";
  if (pathname.startsWith("/settings")) return "Settings";
  if (pathname.startsWith("/admin")) return "Admin Tools";
  return "Dashboard";
}

function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [legacyGameId, setLegacyGameId] = useState("");
  const [showLegacySetup, setShowLegacySetup] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nextPath = ((location.state as { from?: string } | null)?.from) || "/dashboard";

  if (auth.user) {
    return <Navigate to={nextPath} replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const response = await api.login(username, password);
      auth.login(response.token, response.user);
      navigate(nextPath, { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed";
      setError(message);
      if (message.toLowerCase().includes("password setup")) {
        setShowLegacySetup(true);
      }
    }
  }

  async function onLegacySetup(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const response = await api.legacyPasswordSetup({
        username,
        game_id: legacyGameId,
        password,
      });
      auth.login(response.token, response.user);
      navigate(nextPath, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Legacy password setup failed");
    }
  }

  return (
    <AuthCard
      title="Welcome back"
      subtitle="Log into the BangStats server and pick up where your CLI workflow left off."
      footer={
        <div className="auth-links">
          <p>
            Need an account? <Link to="/register">Create one</Link>
          </p>
          <p>
            Old passwordless account? <Link to="/legacy-login">Use legacy login</Link>
          </p>
        </div>
      }
    >
      <form className="stack" onSubmit={onSubmit}>
        <label className="field">
          <span>Username</span>
          <input value={username} onChange={(event) => setUsername(event.target.value)} required />
        </label>
        <label className="field">
          <span>Password</span>
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>
        {error && <div className="notice error">{error}</div>}
        <button className="button primary" type="submit">
          Login
        </button>
      </form>
      {showLegacySetup && (
        <form className="stack legacy-box" onSubmit={onLegacySetup}>
          <div className="brand-kicker">Legacy account migration</div>
          <label className="field">
            <span>Game ID</span>
            <input value={legacyGameId} onChange={(event) => setLegacyGameId(event.target.value)} required />
          </label>
          <div className="inline-meta">
            This account exists from the old passwordless flow. Confirm your game ID and set the password above to activate it.
          </div>
          <button className="button accent" type="submit">
            Set password and continue
          </button>
        </form>
      )}
    </AuthCard>
  );
}

function LegacyLoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [gameId, setGameId] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (auth.user) {
    return <Navigate to="/dashboard" replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const response = await api.legacyLogin({ username, game_id: gameId });
      auth.login(response.token, response.user);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Legacy login failed");
    }
  }

  return (
    <AuthCard
      title="Legacy account login"
      subtitle="Temporary access path for older accounts that were created before passwords were required."
      footer={
        <div className="auth-links">
          <p>
            Want the normal flow? <Link to="/login">Back to login</Link>
          </p>
          <p>
            Want to set a password instead? Use the migration form on the standard login page.
          </p>
        </div>
      }
    >
      <form className="stack" onSubmit={onSubmit}>
        <label className="field">
          <span>Username</span>
          <input value={username} onChange={(event) => setUsername(event.target.value)} required />
        </label>
        <label className="field">
          <span>Game ID</span>
          <input value={gameId} onChange={(event) => setGameId(event.target.value)} required />
        </label>
        {error && <div className="notice error">{error}</div>}
        <button className="button accent" type="submit">
          Continue with legacy account
        </button>
      </form>
    </AuthCard>
  );
}

function RegisterPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", password: "", game_id: "", server: "en" as User["server"] });
  const [error, setError] = useState<string | null>(null);
  if (auth.user) {
    return <Navigate to="/dashboard" replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const response = await api.register(form);
      auth.login(response.token, response.user);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    }
  }

  return (
    <AuthCard
      title="Create account"
      subtitle="Register the same data the CLI asks for, then use the full web dashboard."
      footer={
        <p>
          Already registered? <Link to="/login">Log in</Link>
        </p>
      }
    >
      <form className="stack" onSubmit={onSubmit}>
        <div className="two-col">
          <label className="field">
            <span>Username</span>
            <input value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} required />
          </label>
          <label className="field">
            <span>Game ID</span>
            <input value={form.game_id} onChange={(event) => setForm({ ...form, game_id: event.target.value })} required />
          </label>
        </div>
        <div className="two-col">
          <label className="field">
            <span>Password</span>
            <input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required />
          </label>
          <label className="field">
            <span>Server</span>
            <select value={form.server} onChange={(event) => setForm({ ...form, server: event.target.value as User["server"] })}>
              {["en", "jp", "tw", "cn", "kr"].map((value) => (
                <option key={value} value={value}>
                  {value.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
        </div>
        {error && <div className="notice error">{error}</div>}
        <button className="button primary" type="submit">
          Register
        </button>
      </form>
    </AuthCard>
  );
}

function DashboardPage() {
  const auth = useAuth();
  const { data, loading, error, reload } = useLoadable<DashboardResponse>(
    auth.user ? () => api.getDashboard(auth.user!.id) : null,
    [auth.user?.id],
  );

  if (!auth.user) return null;

  return (
    <div className="page-grid">
      <SectionHeader title="Home" action={<button className="button ghost" onClick={() => void reload()}>Refresh</button>} />
      {loading && <LoadingCard label="Loading dashboard..." />}
      {error && <div className="notice error">{error}</div>}
      {data && (
        <>
          <div className="stats-grid">
            <MetricCard label="Songs" value={data.counts.songs} />
            <MetricCard label="Events" value={data.counts.events} />
            <MetricCard label="Bands" value={data.counts.bands} />
            <MetricCard label="Uploaded files" value={data.upload_usage.file_count} />
            <MetricCard label="Total plays" value={data.stats?.total_plays ?? 0} />
            <MetricCard label="Accuracy" value={data.stats?.accuracy ? `${data.stats.accuracy}%` : "No data"} />
          </div>
          <div className="layout-two">
            <Card title="Current event">
              {data.current_event ? (
                <CurrentEventCard data={data} server={auth.user.server} />
              ) : (
                <div className="stack">
                  <EmptyState text={data.current_event_status || "No current event returned for this server."} />
                  <div className="inline-meta">
                    Server {data.runtime.server.toUpperCase()} · DB {data.runtime.db_path}
                  </div>
                </div>
              )}
            </Card>
            <Card title="Runtime">
              <KeyValueList
                items={[
                  ["Server", data.runtime.server.toUpperCase()],
                  ["Environment", data.runtime.env],
                  ["DB path", data.runtime.db_path],
                  ["Legacy DB", data.runtime.legacy_db_exists ? data.runtime.legacy_db_path : "Not found"],
                  ["Storage usage", `${data.upload_usage.total_size_mb.toFixed(2)} MB`],
                ]}
              />
            </Card>
          </div>
          {data.scan_errors.total > 0 && (
            <Card title="Scan errors">
              <KeyValueList
                items={Object.entries(data.scan_errors.errors).map(([key, value]) => [key, String(value)])}
                emptyLabel="No current errors."
              />
              <Link className="text-link" to="/scan/errors">
                Open maintenance queue
              </Link>
            </Card>
          )}
          <div className="layout-two">
            <Card title="Recent scan jobs">
              <JobList jobs={data.scan_jobs} kind="scan" />
            </Card>
            <Card title="Recent sync jobs">
              <JobList jobs={data.sync_jobs} kind="sync" />
            </Card>
          </div>
          <Card title="Recent screenshots">
            <ScreenshotGallery items={data.recent_screenshots} />
          </Card>
        </>
      )}
    </div>
  );
}

function SyncPage() {
  const auth = useAuth();
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const jobs = useLoadable<{ jobs: SyncJob[] }>(auth.user ? () => api.listSyncJobs(20) : null, [auth.user?.id]);

  if (!auth.user) return null;
  const user = auth.user;

  async function startSync() {
    setCreating(true);
    setMessage(null);
    try {
      const job = await api.createSyncJob(user.server, user.id);
      setMessage(`Sync job #${job.id} queued.`);
      await jobs.reload();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to start sync");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="page-grid">
      <SectionHeader
        title="Reference data sync"
        action={
          <button className="button primary" disabled={creating} onClick={() => void startSync()}>
            {creating ? "Starting..." : "Start sync"}
          </button>
        }
      />
      {message && <div className="notice">{message}</div>}
      <Card title="Latest jobs">
        {jobs.loading && <LoadingInline />}
        {jobs.error && <div className="notice error">{jobs.error}</div>}
        {jobs.data && <JobList jobs={jobs.data.jobs} kind="sync" />}
      </Card>
    </div>
  );
}

function ScanPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [selectedSource, setSelectedSource] = useState<"upload" | "server_folder">("upload");
  const [folderPath, setFolderPath] = useState("");
  const [jsonFolderPath, setJsonFolderPath] = useState("");
  const [masterKey, setMasterKey] = useState("");
  const [parallelWorkers, setParallelWorkers] = useState("1");
  const [keysPerWorker, setKeysPerWorker] = useState("1");
  const [message, setMessage] = useState<string | null>(null);
  const [diffPreview, setDiffPreview] = useState<FilenameDiffResponse | null>(null);
  const uploads = useLoadable(auth.user ? () => api.listUploads(auth.user!.id) : null, [auth.user?.id]);
  const usage = useLoadable(auth.user ? () => api.getUploadUsage(auth.user!.id) : null, [auth.user?.id]);
  const capabilities = useLoadable(() => api.getScanCapabilities(), []);
  const jobs = useLoadable(auth.user ? () => api.listScanJobs(20) : null, [auth.user?.id]);

  if (!auth.user) return null;
  const user = auth.user;

  useEffect(() => {
    setFolderPath(user.screenshots_path || "");
    setSelectedSource(user.screenshots_source === "server_folder" ? "server_folder" : "upload");
  }, [user.id, user.screenshots_source, user.screenshots_path]);

  useEffect(() => {
    const currentJobs = jobs.data?.jobs || [];
    const hasActive = currentJobs.some((job) => ["queued", "running"].includes(job.status));
    if (!hasActive) return;
    const timer = window.setInterval(() => {
      void jobs.reload();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [jobs.data?.jobs]);

  async function refreshAll() {
    await Promise.all([uploads.reload(), usage.reload(), jobs.reload()]);
  }

  async function uploadSelected() {
    if (!selectedFiles.length) {
      setMessage("Choose screenshot files first.");
      return;
    }
    setMessage("Uploading files...");
    try {
      const payload = await api.uploadFiles(user.id, selectedFiles);
      setMessage(`Uploaded ${payload.uploaded_files} files.`);
      await refreshAll();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Upload failed");
    }
  }

  async function persistScanSettings(source: "upload" | "server_folder", path: string) {
    const updated = await api.updateUser(user.id, {
      screenshots_source: source === "server_folder" ? "server_folder" : "local",
      screenshots_path: path,
    });
    auth.login(localStorage.getItem("bangstats.web.token") || "", updated);
  }

  async function startUploadScan() {
    setDiffPreview(null);
    setMessage("Checking uploaded file diff...");
    try {
      await persistScanSettings("upload", folderPath);
      const candidates = (uploads.data?.items || []).map((item) => item.filename).filter(Boolean);
      if (!candidates.length) {
        setMessage("No uploaded files available to scan.");
        return;
      }
      const diff = await api.getScanFilenameDiff(user.id, candidates);
      setDiffPreview(diff);
      if (!diff.to_scan_count) {
        setMessage(`No new files to scan. Already indexed: ${diff.already_scanned_count}`);
        return;
      }
      const job = await api.createScanJob({
        user_id: user.id,
        source_type: "upload",
        filenames: diff.to_scan_filenames,
        parallel_workers: Number(parallelWorkers) || undefined,
        keys_per_worker: Number(keysPerWorker) || undefined,
      });
      setMessage(`Scan job #${job.id} queued (${diff.to_scan_count} new file(s)).`);
      await refreshAll();
      navigate(`/scan/jobs/${job.id}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to queue scan");
    }
  }

  async function authorizeAndRefresh() {
    try {
      await api.authorizeServerFolder(masterKey);
      await auth.refreshUser();
      setMessage("Server folder access authorized.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Authorization failed");
    }
  }

  async function startServerFolderScan() {
    setDiffPreview(null);
    try {
      await persistScanSettings("server_folder", folderPath);
      const validated = await api.checkLocalPath(folderPath, user.id);
      const job = await api.createScanJob({
        user_id: user.id,
        source_type: "server_folder",
        folder_path: validated.canonical_path || folderPath,
        parallel_workers: Number(parallelWorkers) || undefined,
        keys_per_worker: Number(keysPerWorker) || undefined,
      });
      setMessage(`Server-folder scan #${job.id} queued (${job.total_files} new file(s)).`);
      await jobs.reload();
      navigate(`/scan/jobs/${job.id}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Server-folder scan failed");
    }
  }

  async function importJson() {
    try {
      const result = await api.importJsonFolder(user.id, jsonFolderPath, true);
      setMessage(scanResultSummary(result, "Imported JSON scans"));
      await refreshAll();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "JSON import failed");
    }
  }

  return (
    <div className="page-grid">
      <SectionHeader title="Scanning" />
      {message && <div className="notice">{message}</div>}
      {diffPreview && (
        <div className="notice">
          Diff summary: requested {diffPreview.total_requested}, already scanned {diffPreview.already_scanned_count}, to scan {diffPreview.to_scan_count}.
        </div>
      )}
      <Card title="Scan settings">
        <div className="stack">
          <label className="field inline-field">
            <span>Scan source</span>
            <select value={selectedSource} onChange={(event) => setSelectedSource(event.target.value as "upload" | "server_folder") }>
              <option value="upload">Upload storage</option>
              <option value="server_folder">Server folder</option>
            </select>
          </label>
          <label className="field">
            <span>Folder path on server</span>
            <input value={folderPath} onChange={(event) => setFolderPath(event.target.value)} placeholder="/srv/screenshots/user1" />
          </label>
          <label className="field">
            <span>Parallel workers</span>
            <input value={parallelWorkers} onChange={(event) => setParallelWorkers(event.target.value)} />
          </label>
          <label className="field">
            <span>Keys per worker</span>
            <input value={keysPerWorker} onChange={(event) => setKeysPerWorker(event.target.value)} />
          </label>
          <div className="button-row">
            <button
              className="button accent"
              type="button"
              disabled={selectedSource === "server_folder" && !user.server_folder_authorized}
              onClick={() => {
                if (selectedSource === "server_folder") {
                  void startServerFolderScan();
                } else {
                  void startUploadScan();
                }
              }}
            >
              Start scan
            </button>
          </div>
        </div>
      </Card>
      <div className="layout-two">
        <Card title="1. Browser upload flow">
          <div className="stack">
            <label className="field">
              <span>Select screenshot files</span>
              <input
                type="file"
                accept=".png,.jpg,.jpeg,.heic,.heif"
                multiple
                onChange={(event) => setSelectedFiles(Array.from(event.target.files || []))}
              />
            </label>
            <div className="inline-meta">{selectedFiles.length} file(s) selected</div>
            <div className="button-row">
              <button className="button primary" onClick={() => void uploadSelected()}>
                Upload to storage
              </button>
            </div>
            {capabilities.data && (
              <div className="inline-meta">
                OCR: {capabilities.data.provider} | Google keys: {capabilities.data.available_google_keys}
              </div>
            )}
          </div>
        </Card>
        <Card title="2. Server-folder flow">
          <div className="stack">
            <label className="field">
              <span>Master key</span>
              <input type="password" value={masterKey} onChange={(event) => setMasterKey(event.target.value)} />
            </label>
            <button className="button ghost" onClick={() => void authorizeAndRefresh()}>
              Authorize server-folder access
            </button>
            <div className="inline-meta">
              Authorized: {user.server_folder_authorized ? "Yes" : "No"}
            </div>
          </div>
        </Card>
      </div>
      <div className="layout-two">
        <Card title="3. Legacy JSON import">
          <div className="stack">
            <label className="field">
              <span>JSON folder path</span>
              <input value={jsonFolderPath} onChange={(event) => setJsonFolderPath(event.target.value)} placeholder="/path/to/json/folder" />
            </label>
            <button className="button accent" onClick={() => void importJson()}>
              Import JSON scans
            </button>
          </div>
        </Card>
        <Card title="Upload storage">
          {usage.data ? (
            <KeyValueList
              items={[
                ["Files", String(usage.data.file_count)],
                ["Size", `${usage.data.total_size_mb} MB`],
                ["Oldest file age", `${usage.data.oldest_file_age_days} days`],
              ]}
            />
          ) : (
            <LoadingInline />
          )}
        </Card>
      </div>
      <div className="layout-two">
        <Card title="Uploaded screenshots">
          {uploads.loading && <LoadingInline />}
          {uploads.error && <div className="notice error">{uploads.error}</div>}
          {uploads.data && <UploadGallery items={uploads.data.items} />}
        </Card>
        <Card title="Recent scan jobs">
          {jobs.loading && <LoadingInline />}
          {jobs.error && <div className="notice error">{jobs.error}</div>}
          {jobs.data && <JobList jobs={jobs.data.jobs} kind="scan" />}
        </Card>
      </div>
    </div>
  );
}

function ScanJobPage() {
  const auth = useAuth();
  const { jobId } = useParams();
  const id = Number(jobId);
  const job = useLoadable(auth.user && Number.isFinite(id) ? () => api.getScanJob(id) : null, [auth.user?.id, id]);

  useEffect(() => {
    if (!job.data) return;
    if (["succeeded", "failed", "cancelled"].includes(job.data.status)) return;
    const timer = window.setInterval(() => {
      void job.reload();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [job.data?.id, job.data?.status]);

  if (!auth.user) return null;

  return (
    <div className="page-grid">
      <SectionHeader
        title={`Scan job #${id}`}
        action={
          job.data && !["succeeded", "failed", "cancelled"].includes(job.data.status) ? (
            <button className="button ghost" onClick={() => void api.cancelScanJob(id).then(job.reload)}>
              Cancel job
            </button>
          ) : undefined
        }
      />
      {job.loading && <LoadingCard label="Loading scan job..." />}
      {job.error && <div className="notice error">{job.error}</div>}
      {job.data && (
        <>
          <div className="stats-grid">
            <MetricCard label="Status" value={job.data.status} />
            <MetricCard label="Processed" value={`${job.data.processed}/${job.data.total_files}`} />
            <MetricCard label="Successful" value={job.data.successful} />
            <MetricCard label="Persisted" value={job.data.persisted} />
            <MetricCard label="Duplicates" value={job.data.skipped_duplicates} />
            <MetricCard label="Failed to persist" value={job.data.failed_to_persist} />
          </div>
          <Card title="Error buckets">
            <KeyValueList items={Object.entries(job.data.errors).map(([key, value]) => [key, String(value)])} emptyLabel="No job errors." />
          </Card>
          <Card title="Files by error type">
            <CodeBlock value={job.data.error_files} />
          </Card>
        </>
      )}
    </div>
  );
}

function ErrorInboxPage() {
  const auth = useAuth();
  const [message, setMessage] = useState<string | null>(null);
  const errors = useLoadable<ErrorList>(() => api.listErrors(), []);
  if (!auth.user) return null;
  const user = auth.user;

  async function runAction(kind: "revalidate" | "rescan", errorType: string) {
    try {
      let result: ErrorCategoryActionResponse;
      if (kind === "revalidate") {
        result = await api.revalidateErrorCategory(errorType, {
          user_id: user.id,
          persist_to_db: true,
          progress_every: 100,
        });
      } else {
        result = await api.rescanErrorCategory(errorType, {
          user_id: user.id,
          persist_to_db: true,
          progress_every: 50,
        });
      }
      setMessage(`${kind} complete: ${result.processed}/${result.total_files} processed.`);
      await errors.reload();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Category action failed");
    }
  }

  return (
    <div className="page-grid">
      <SectionHeader title="Error inbox" action={<button className="button ghost" onClick={() => void errors.reload()}>Refresh</button>} />
      {message && <div className="notice">{message}</div>}
      {errors.loading && <LoadingCard label="Loading error categories..." />}
      {errors.error && <div className="notice error">{errors.error}</div>}
      {errors.data && (
        <div className="card-grid">
          {Object.entries(errors.data.error_files).map(([errorType, files]) => (
            <Card
              key={errorType}
              title={`${errorType} (${files.length})`}
              actions={
                <div className="button-row">
                  <button className="button ghost" onClick={() => void runAction("revalidate", errorType)}>
                    Revalidate
                  </button>
                  <button className="button accent" onClick={() => void runAction("rescan", errorType)}>
                    Rescan
                  </button>
                </div>
              }
            >
              <ul className="list">
                {files.slice(0, 12).map((file) => (
                  <li key={file}>
                    <Link to={`/scan/errors/${encodeURIComponent(errorType)}/${encodeURIComponent(file)}`}>{file}</Link>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function ErrorDetailPage() {
  const auth = useAuth();
  const params = useParams();
  const errorType = decodeURIComponent(params.errorType || "");
  const jsonFilename = decodeURIComponent(params.jsonFilename || "");
  const detail = useLoadable<ErrorDetail>(() => api.getErrorDetail(errorType, jsonFilename), [errorType, jsonFilename]);
  const [payloadText, setPayloadText] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (detail.data) {
      setPayloadText(JSON.stringify(detail.data.scan_data, null, 2));
    }
  }, [detail.data?.json_filename]);

  if (!auth.user) return null;
  const user = auth.user;

  async function saveCorrection() {
    try {
      const payload = JSON.parse(payloadText) as Record<string, unknown>;
      const result = await api.correctError(errorType, jsonFilename, {
        user_id: user.id,
        corrected_scan_data: payload,
        persist_to_db: true,
      });
      setMessage(
        result.is_valid
          ? `Correction succeeded. Persisted=${result.persisted} duplicate=${result.skipped_duplicates}`
          : `Still invalid. Moved to ${result.error_type}.`,
      );
      await detail.reload();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Correction failed");
    }
  }

  return (
    <div className="page-grid">
      <SectionHeader title={jsonFilename} />
      {message && <div className="notice">{message}</div>}
      {detail.loading && <LoadingCard label="Loading error detail..." />}
      {detail.error && <div className="notice error">{detail.error}</div>}
      {detail.data && (
        <div className="layout-two">
          <Card title="Screenshot preview">
            <SecureImage
              className="viewer-image"
              path={`/api/scans/errors/${encodeURIComponent(errorType)}/${encodeURIComponent(jsonFilename)}/image`}
              alt={detail.data.image_filename}
            />
            <div className="inline-meta">{detail.data.image_filename}</div>
          </Card>
          <Card title="Validation">
            <CodeBlock value={detail.data.validation || { note: "No validation artifact found" }} />
          </Card>
          <Card title="Editable scan payload" className="span-2" actions={<button className="button primary" onClick={() => void saveCorrection()}>Save correction</button>}>
            <textarea className="editor" value={payloadText} onChange={(event) => setPayloadText(event.target.value)} />
          </Card>
        </div>
      )}
    </div>
  );
}

function StatsPage() {
  const [searchParams] = useSearchParams();
  const requestedView = searchParams.get("view");
  const view: AnalyticsView = ANALYTICS_VIEWS.includes(requestedView as AnalyticsView)
    ? (requestedView as AnalyticsView)
    : "overview";

  return (
    <div className="page-grid">
      <SectionHeader title="Analytics workspace" />
      <nav className="analytics-subnav">
        {ANALYTICS_VIEWS.map((item) => (
          <Link
            key={item}
            to={`/stats?view=${item}`}
            className={item === view ? "analytics-subnav-link active" : "analytics-subnav-link"}
          >
            {formatDifficulty(item)}
          </Link>
        ))}
      </nav>
      {view === "overview" && <OverviewAnalyticsView />}
      {view === "progress" && <ProgressAnalyticsView />}
      {view === "milestones" && <MilestonesAnalyticsView />}
      {view === "songs" && <SongsAnalyticsView />}
      {view === "events" && <EventsAnalyticsView />}
      {view === "recap" && <RecapAnalyticsView />}
      {view === "screenshots" && <ScreenshotsAnalyticsView />}
    </div>
  );
}

function OverviewAnalyticsView() {
  const auth = useAuth();
  const overview = useLoadable<StatsOverview>(auth.user ? () => api.getStats(auth.user!.id) : null, [auth.user?.id]);
  const milestones = useLoadable<MilestonesResponse>(auth.user ? () => api.getMilestones(auth.user!.id) : null, [auth.user?.id]);
  const progression = useLoadable<ProgressionResponse>(
    auth.user ? () => api.getProgression(auth.user!.id, "monthly", 6, new Date().toISOString().slice(0, 10)) : null,
    [auth.user?.id],
  );

  if (!auth.user) return null;

  return (
    <div className="page-grid">
      <Card title="Headline stats">
        {overview.data ? (
          <div className="stats-grid">
            <MetricCard label="Total plays" value={overview.data.summary.total_plays} />
            <MetricCard label="FC" value={overview.data.summary.total_fc} />
            <MetricCard label="AP" value={overview.data.summary.total_ap} />
            <MetricCard label="Accuracy" value={`${overview.data.summary.accuracy}%`} />
            <MetricCard label="Skill score" value={overview.data.summary.skill_score ?? 0} />
          </div>
        ) : (
          <LoadingInline />
        )}
      </Card>
      <div className="layout-two">
        <Card title="Current progress snapshot">
          {progression.data ? <TrendChart data={progression.data} summaryMode="list" /> : <LoadingInline />}
        </Card>
        <Card title="Recent meaningful plays">
          {overview.data ? <RecentPlayList items={overview.data.recent} /> : <LoadingInline />}
        </Card>
      </div>
      <div className="layout-two">
        <Card title="Latest milestones">
          {milestones.data ? <MilestoneTimeline items={milestones.data.milestones.slice(0, 6)} /> : <LoadingInline />}
        </Card>
        <Card title="Jump into analysis">
          <ul className="list">
            {[
              ["/stats?view=progress", "Open Progress to inspect skill trend, milestones, and practice periods."],
              ["/stats?view=milestones", "Open Milestones for a dedicated timeline focused on achievement progression."],
              ["/stats?view=songs", "Open Songs to search and rank songs with song-specific filters."],
              ["/stats?view=events", "Open Events to inspect a single event with one event selector."],
              ["/stats?view=recap", "Open Recap for scoped story views like weekly, monthly, or yearly."],
              ["/stats?view=screenshots", "Open Screenshots for image-backed browsing with its own filters."],
            ].map(([to, label]) => (
              <li key={to}>
                <Link to={to}>{label}</Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}

function ProgressAnalyticsView() {
  const auth = useAuth();
  const [range, setRange] = useState<DateRangeValue>(DEFAULT_DATE_RANGE);
  const [scope, setScope] = useState<"weekly" | "monthly" | "yearly">("monthly");
  const [pointCount, setPointCount] = useState(8);
  const [filters, setFilters] = useState<SectionFilterState>({ difficulty: "", liveType: "", includeMeta: false });
  const [calendarDate, setCalendarDate] = useState(() => new Date());
  const customRangeReady = range.preset !== "custom" || (Boolean(range.from) && Boolean(range.to));
  const filterQuery = sectionFiltersToQuery(filters);
  const rangeQuery = dateRangeToQuery(range);
  const anchorDate = resolveAbsoluteDateRange(range)?.to_date || new Date().toISOString().slice(0, 10);

  const activity = useLoadable<ActivityResponse>(
    auth.user && customRangeReady ? () => api.getActivity(auth.user!.id, { ...rangeQuery, ...filterQuery }) : null,
    [auth.user?.id, customRangeReady, range.preset, range.from, range.to, filters.difficulty, filters.liveType, filters.includeMeta],
  );
  const progression = useLoadable<ProgressionResponse>(
    auth.user ? () => api.getProgression(auth.user!.id, scope, pointCount, anchorDate, filterQuery) : null,
    [auth.user?.id, scope, pointCount, anchorDate, filters.difficulty, filters.liveType, filters.includeMeta],
  );
  const insights = useLoadable<InsightsResponse>(
    auth.user && customRangeReady ? () => api.getInsights(auth.user!.id, { ...rangeQuery, ...filterQuery }) : null,
    [auth.user?.id, customRangeReady, range.preset, range.from, range.to, filters.difficulty, filters.liveType, filters.includeMeta],
  );
  const calendar = useLoadable<CalendarResponse>(
    auth.user
      ? () => api.getCalendar(auth.user!.id, calendarDate.getFullYear(), calendarDate.getMonth() + 1, filterQuery)
      : null,
    [auth.user?.id, calendarDate.getFullYear(), calendarDate.getMonth(), filters.difficulty, filters.liveType, filters.includeMeta],
  );

  if (!auth.user) return null;

  return (
    <div className="page-grid">
      <Card title="Progression graph controls">
        <div className="analytics-section-controls">
          <div className="analytics-filter-row">
            <label className="field inline-field">
              <span>Trend scope</span>
              <select value={scope} onChange={(event) => setScope(event.target.value as "weekly" | "monthly" | "yearly")}>
                {["weekly", "monthly", "yearly"].map((value) => (
                  <option key={value} value={value}>
                    {formatDifficulty(value)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field inline-field trend-count-field">
              <span>Data points ({pointCount})</span>
              <input
                type="range"
                min={4}
                max={16}
                step={1}
                value={pointCount}
                onChange={(event) => setPointCount(Number(event.target.value))}
              />
            </label>
          </div>
          <div className="inline-meta">Scope and point count control only the Skill progression graph below.</div>
        </div>
      </Card>
      <Card title="Shared analytics filters">
        <div className="analytics-filter-row">
          <SectionFilterControls filters={filters} onChange={setFilters} />
        </div>
      </Card>
      <Card title="Time-window controls">
        <div className="analytics-section-controls">
          <DateRangePicker value={range} onChange={setRange} />
          <div className="inline-meta">Date range filters Activity summary and Practice patterns. Calendar has its own month selector.</div>
        </div>
      </Card>
      <Card title="Skill progression">
        {progression.data ? <TrendChart data={progression.data} /> : <LoadingInline />}
      </Card>
      <div className="layout-two">
        <Card title={activity.data ? `Activity summary (${formatDateRange(activity.data.from_date, activity.data.to_date)})` : "Activity summary"}>
          {activity.data ? <ActivityBars data={activity.data} /> : !customRangeReady ? <EmptyState text="Pick both custom dates to load activity." /> : <LoadingInline />}
        </Card>
        <Card title="Practice patterns">
          {insights.data ? <InsightsPanel data={insights.data} /> : !customRangeReady ? <EmptyState text="Pick both custom dates to load practice insights." /> : <LoadingInline />}
        </Card>
      </div>
      <Card
        title="Calendar"
        actions={
          <div className="button-row tight">
            <button className="button ghost" type="button" onClick={() => setCalendarDate((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1))}>
              Prev
            </button>
            <div className="toolbar-chip">
              {calendarDate.toLocaleDateString(undefined, { month: "long", year: "numeric" })}
            </div>
            <button className="button ghost" type="button" onClick={() => setCalendarDate((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1))}>
              Next
            </button>
          </div>
        }
      >
        {calendar.data ? <CalendarHeatmap data={calendar.data} /> : <LoadingInline />}
      </Card>
      <Card title="Milestones">
        <div className="inline-meta">
          Milestones moved to their own tab for focused browsing. <Link to="/stats?view=milestones">Open milestones tab</Link>.
        </div>
      </Card>
    </div>
  );
}

function MilestonesAnalyticsView() {
  const auth = useAuth();
  const [filters, setFilters] = useState<SectionFilterState>({ difficulty: "", liveType: "", includeMeta: false });
  const filterQuery = sectionFiltersToQuery(filters);
  const milestones = useLoadable<MilestonesResponse>(
    auth.user ? () => api.getMilestones(auth.user!.id, filterQuery) : null,
    [auth.user?.id, filters.difficulty, filters.liveType, filters.includeMeta],
  );

  if (!auth.user) return null;

  return (
    <div className="page-grid">
      <Card title="Milestone filters">
        <div className="analytics-filter-row">
          <SectionFilterControls filters={filters} onChange={setFilters} />
        </div>
      </Card>
      <Card title="Milestone timeline">
        {milestones.data ? <MilestoneTimeline items={milestones.data.milestones} /> : <LoadingInline />}
      </Card>
    </div>
  );
}

function SongsAnalyticsView() {
  const auth = useAuth();
  const [filters, setFilters] = useState<SectionFilterState>({ difficulty: "", liveType: "", includeMeta: false });
  const [sortBy, setSortBy] = useState("play_count");
  const [searchQuery, setSearchQuery] = useState("");
  const [results, setResults] = useState<Array<{ song_id: number; song_name: string }>>([]);
  const filterQuery = sectionFiltersToQuery(filters);
  const rankings = useLoadable<SongRankingsResponse>(
    auth.user ? () => api.getSongRankings(auth.user!.id, { ...filterQuery, sort_by: sortBy, limit: 40 }) : null,
    [auth.user?.id, sortBy, filters.difficulty, filters.liveType, filters.includeMeta],
  );

  if (!auth.user) return null;

  async function runSearch() {
    if (!searchQuery.trim()) {
      setResults([]);
      return;
    }
    try {
      const response = await api.searchSongs(auth.user!.id, searchQuery, auth.user!.server);
      setResults(response.results);
    } catch {
      setResults([]);
    }
  }

  return (
    <div className="page-grid">
      <Card title="Song controls">
        <div className="analytics-section-controls">
          <div className="analytics-filter-row">
            <label className="field song-search-field">
              <span>Song search</span>
              <div className="button-row tight">
                <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search song names" />
                <button className="button primary" type="button" onClick={() => void runSearch()}>
                  Search
                </button>
              </div>
            </label>
            <label className="field inline-field">
              <span>Sort songs by</span>
              <select value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
                <option value="play_count">Plays</option>
                <option value="skill_score">Skill score</option>
                <option value="fc_count">FC count</option>
                <option value="ap_count">AP count</option>
              </select>
            </label>
            <SectionFilterControls filters={filters} onChange={setFilters} />
          </div>
          {!!results.length && (
            <div className="toolbar-results">
              {results.slice(0, 8).map((song) => (
                <Link key={song.song_id} to={`/stats/song/${song.song_id}`} className="toolbar-result-link">
                  {song.song_name}
                </Link>
              ))}
            </div>
          )}
        </div>
      </Card>
      <Card title="Song rankings">
        {rankings.data ? <SongRankingsTable data={rankings.data} /> : <LoadingInline />}
      </Card>
    </div>
  );
}

function EventsAnalyticsView() {
  const auth = useAuth();
  const [selectedEventId, setSelectedEventId] = useState("");
  const [filters, setFilters] = useState<SectionFilterState>({ difficulty: "", liveType: "", includeMeta: false });
  const events = useLoadable(auth.user ? () => api.getReferenceEvents(1200) : null, [auth.user?.id]);
  const filterQuery = sectionFiltersToQuery(filters);
  const eventStats = useLoadable<EventStatsResponse>(
    auth.user && selectedEventId ? () => api.getEventStats(auth.user!.id, Number(selectedEventId), filterQuery) : null,
    [auth.user?.id, selectedEventId, filters.difficulty, filters.liveType, filters.includeMeta],
  );
  const recap = useLoadable<RecapResponse>(
    auth.user && selectedEventId ? () => api.getRecap(auth.user!.id, "event", Number(selectedEventId), undefined, filterQuery) : null,
    [auth.user?.id, selectedEventId, filters.difficulty, filters.liveType, filters.includeMeta],
  );

  if (!auth.user) return null;
  const recentEvents = ((events.data?.items || []) as Array<Record<string, unknown>>)
    .slice()
    .filter((event) => Number.isFinite(Number(event.event_id)) && Number(event.event_id) > 0)
    .sort((a, b) => Number(b.event_id || 0) - Number(a.event_id || 0))
    .slice(0, 48);

  return (
    <div className="page-grid">
      <Card title="Event controls">
        <div className="analytics-filter-row">
          <label className="field">
            <span>Event</span>
            <select value={selectedEventId} onChange={(event) => setSelectedEventId(event.target.value)}>
              <option value="">Select event</option>
              {recentEvents.map((event) => (
                <option key={String(event.event_id)} value={String(event.event_id)}>
                  {formatEventLabel(event, auth.user!.server)}
                </option>
              ))}
            </select>
          </label>
          <SectionFilterControls filters={filters} onChange={setFilters} />
        </div>
      </Card>
      <Card title="Event analysis">
        {!selectedEventId ? (
          <EmptyState text="Pick one event and this page will stay entirely event-focused." />
        ) : eventStats.loading ? (
          <LoadingInline />
        ) : eventStats.error ? (
          <div className="stack">
            <EmptyState text={`Could not load event analysis: ${eventStats.error}`} />
            <div className="button-row tight">
              <button className="button" type="button" onClick={() => void eventStats.reload()}>
                Retry
              </button>
            </div>
          </div>
        ) : eventStats.data ? (
          <EventFocusPanel stats={eventStats.data} recap={recap.data} />
        ) : (
          <EmptyState text="No event data returned for this selection." />
        )}
      </Card>
    </div>
  );
}

function RecapAnalyticsView() {
  const auth = useAuth();
  const [scope, setScope] = useState<RecapScope>("monthly");
  const [anchorDate, setAnchorDate] = useState(() => new Date());
  const [selectedEventId, setSelectedEventId] = useState("");
  const [filters, setFilters] = useState<SectionFilterState>({ difficulty: "", liveType: "", includeMeta: false });
  const events = useLoadable(auth.user ? () => api.getReferenceEvents(1200) : null, [auth.user?.id]);
  const filterQuery = sectionFiltersToQuery(filters);
  const recap = useLoadable<RecapResponse>(
    auth.user && (scope !== "event" || Boolean(selectedEventId))
      ? () =>
          api.getRecap(
            auth.user!.id,
            scope,
            scope === "event" ? Number(selectedEventId) : undefined,
            scope === "event" ? undefined : anchorDate.toISOString().slice(0, 10),
            filterQuery,
          )
      : null,
    [auth.user?.id, scope, selectedEventId, anchorDate.getFullYear(), anchorDate.getMonth(), filters.difficulty, filters.liveType, filters.includeMeta],
  );

  if (!auth.user) return null;
  const recentEvents = ((events.data?.items || []) as Array<Record<string, unknown>>)
    .slice()
    .sort((a, b) => Number(b.event_id || b.id || 0) - Number(a.event_id || a.id || 0))
    .slice(0, 48);

  return (
    <div className="page-grid">
      <Card title="Recap controls">
        <div className="analytics-filter-row">
          <label className="field inline-field">
            <span>Scope</span>
            <select value={scope} onChange={(event) => setScope(event.target.value as RecapScope)}>
              {["weekly", "monthly", "seasonal", "yearly", "event"].map((value) => (
                <option key={value} value={value}>
                  {formatDifficulty(value)}
                </option>
              ))}
            </select>
          </label>
          {scope === "event" ? (
            <label className="field">
              <span>Event</span>
              <select value={selectedEventId} onChange={(event) => setSelectedEventId(event.target.value)}>
                <option value="">Select event</option>
                {recentEvents.map((event) => (
                  <option key={String(event.event_id || event.id)} value={String(event.event_id || event.id)}>
                    {formatEventLabel(event, auth.user!.server)}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <div className="button-row tight analytics-month-nav">
              <button className="button ghost" type="button" onClick={() => setAnchorDate((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1))}>
                Prev
              </button>
              <div className="toolbar-chip">
                {anchorDate.toLocaleDateString(undefined, { month: "long", year: "numeric" })}
              </div>
              <button className="button ghost" type="button" onClick={() => setAnchorDate((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1))}>
                Next
              </button>
            </div>
          )}
          <SectionFilterControls filters={filters} onChange={setFilters} />
        </div>
      </Card>
      <Card title="Recap">
        {scope === "event" && !selectedEventId ? (
          <EmptyState text="Pick an event to build an event recap." />
        ) : recap.data ? (
          <RecapPanel data={recap.data} />
        ) : (
          <LoadingInline />
        )}
      </Card>
    </div>
  );
}

function ScreenshotsAnalyticsView() {
  const auth = useAuth();
  const [filters, setFilters] = useState<SectionFilterState>({ difficulty: "", liveType: "", includeMeta: false });
  const [songQuery, setSongQuery] = useState("");
  const [appliedSongQuery, setAppliedSongQuery] = useState("");
  const [songMatches, setSongMatches] = useState<Array<{ song_id: number; song_name: string }>>([]);
  const [sortBy, setSortBy] = useState<"timestamp" | "song_name" | "score" | "accuracy">("timestamp");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [limitByDate, setLimitByDate] = useState(false);
  const [range, setRange] = useState<DateRangeValue>(DEFAULT_DATE_RANGE);
  const [offset, setOffset] = useState(0);
  const absoluteRange = limitByDate ? resolveAbsoluteDateRange(range) : {};
  const customRangeReady = !limitByDate || range.preset !== "custom" || (Boolean(range.from) && Boolean(range.to));
  const screenshots = useLoadable(
    auth.user && customRangeReady
      ? () =>
          api.listScreenshots(auth.user!.id, {
            ...sectionFiltersToQuery(filters),
            ...absoluteRange,
            song_query: appliedSongQuery.trim() || undefined,
            sort_by: sortBy,
            sort_order: sortOrder,
            limit: 24,
            offset,
          })
      : null,
    [
      auth.user?.id,
      offset,
      limitByDate,
      range.preset,
      range.from,
      range.to,
      appliedSongQuery,
      sortBy,
      sortOrder,
      filters.difficulty,
      filters.liveType,
      filters.includeMeta,
    ],
  );

  if (!auth.user) return null;

  async function runSongSearch() {
    if (!songQuery.trim()) {
      setSongMatches([]);
      return;
    }
    try {
      const response = await api.searchSongs(auth.user!.id, songQuery.trim(), auth.user!.server);
      setSongMatches(response.results);
    } catch {
      setSongMatches([]);
    }
  }

  return (
    <div className="page-grid">
      <Card title="Screenshot controls">
        <div className="analytics-section-controls">
          <div className="analytics-filter-row">
            <label className="field song-search-field">
              <span>Song search</span>
              <div className="button-row tight">
                <input
                  value={songQuery}
                  onChange={(event) => {
                    setSongQuery(event.target.value);
                  }}
                  placeholder="Filter screenshots by song name"
                />
                <button
                  className="button primary"
                  type="button"
                  onClick={() => {
                    void runSongSearch();
                    setAppliedSongQuery(songQuery.trim());
                    setOffset(0);
                  }}
                >
                  Search
                </button>
              </div>
            </label>
            <label className="field inline-field">
              <span>Sort by</span>
              <select value={sortBy} onChange={(event) => { setSortBy(event.target.value as typeof sortBy); setOffset(0); }}>
                <option value="timestamp">Date</option>
                <option value="song_name">Song name</option>
                <option value="accuracy">Accuracy</option>
                <option value="score">Score</option>
              </select>
            </label>
            <label className="field inline-field">
              <span>Order</span>
              <select value={sortOrder} onChange={(event) => { setSortOrder(event.target.value as typeof sortOrder); setOffset(0); }}>
                <option value="desc">Descending</option>
                <option value="asc">Ascending</option>
              </select>
            </label>
          </div>
          {!!songMatches.length && (
            <div className="toolbar-results">
              {songMatches.map((song) => (
                <button
                  key={song.song_id}
                  className="button ghost"
                  type="button"
                  onClick={() => {
                    setSongQuery(song.song_name);
                    setAppliedSongQuery(song.song_name);
                    setOffset(0);
                  }}
                >
                  {song.song_name}
                </button>
              ))}
            </div>
          )}
          <label className="check analytics-toggle">
            <input
              type="checkbox"
              checked={limitByDate}
              onChange={(event) => {
                setLimitByDate(event.target.checked);
                setOffset(0);
              }}
            />
            <span>Limit by date range</span>
          </label>
          {limitByDate && <DateRangePicker value={range} onChange={(next) => { setRange(next); setOffset(0); }} />}
          <div className="analytics-filter-row">
            <SectionFilterControls filters={filters} onChange={(next) => { setFilters(next); setOffset(0); }} />
          </div>
        </div>
      </Card>
      <Card title="Screenshot browser">
        {!customRangeReady ? (
          <EmptyState text="Pick both custom dates to browse screenshots." />
        ) : screenshots.data ? (
          <div className="page-grid">
            <div className="inline-meta">
              Showing {screenshots.data.offset + 1}-{Math.min(screenshots.data.offset + screenshots.data.items.length, screenshots.data.total)} of {screenshots.data.total}
            </div>
            <ScreenshotGallery items={screenshots.data.items} />
            <div className="button-row">
              <button className="button ghost" type="button" disabled={offset === 0} onClick={() => setOffset((current) => Math.max(0, current - 24))}>
                Previous page
              </button>
              <button
                className="button ghost"
                type="button"
                disabled={offset + 24 >= screenshots.data.total}
                onClick={() => setOffset((current) => current + 24)}
              >
                Next page
              </button>
            </div>
          </div>
        ) : (
          <LoadingInline />
        )}
      </Card>
    </div>
  );
}

function SongStatsPage() {
  const auth = useAuth();
  const { songId } = useParams();
  const songIdNumber = Number(songId);
  const [difficulty, setDifficulty] = useState<string>("");
  const data = useLoadable<SongStatsResponse>(
    auth.user && Number.isFinite(songIdNumber)
      ? () => api.getSongStats(auth.user!.id, songIdNumber, difficulty || undefined)
      : null,
    [auth.user?.id, songIdNumber, difficulty],
  );
  const journey = useLoadable<SongJourneyResponse>(
    auth.user && Number.isFinite(songIdNumber)
      ? () => api.getSongJourney(auth.user!.id, songIdNumber, difficulty || undefined)
      : null,
    [auth.user?.id, songIdNumber, difficulty],
  );

  if (!auth.user) return null;

  return (
    <div className="page-grid">
      <SectionHeader title={`Song #${songIdNumber}`} />
      <label className="field inline-field">
        <span>Difficulty drilldown</span>
        <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
          <option value="">Overview only</option>
          {["easy", "normal", "hard", "expert", "special"].map((value) => (
            <option key={value} value={value}>
              {formatDifficulty(value)}
            </option>
          ))}
        </select>
      </label>
      {data.loading && <LoadingCard label="Loading song stats..." />}
      {data.error && <div className="notice error">{data.error}</div>}
      {data.data && (
        <div className="page-grid">
          <div className="layout-two">
            <Card title="Difficulty overview">
              <BarChart items={data.data.difficulty_overview.map((item) => ({ label: item.difficulty, value: item.total_plays }))} />
            </Card>
            <Card title="Detailed metrics">
              {data.data.detail ? (
                <KeyValueList
                  items={[
                    ["Total plays", String(data.data.detail.total_plays)],
                    ["Accuracy", `${data.data.detail.accuracy}%`],
                    ["Skill score", String(data.data.detail.skill_score)],
                    ["Sessions", String(data.data.detail.total_sessions)],
                    ["Avg plays/session", String(data.data.detail.avg_plays_per_session)],
                    ["Longest session", `${data.data.detail.longest_session_minutes} min / ${data.data.detail.longest_session_plays} plays`],
                    ["Estimated time", data.data.detail.estimated_time_played_human],
                  ]}
                />
              ) : (
                <EmptyState text="Pick a difficulty to load drilldown metrics." />
              )}
            </Card>
          </div>
          <div className="layout-two">
            <Card title="Milestone captures">
              {data.data.detail ? (
                <MilestoneGallery
                  items={[
                    data.data.detail.first_played ? { label: "First play", meta: data.data.detail.first_played } : null,
                    data.data.detail.first_fc ? { label: "First FC", meta: data.data.detail.first_fc } : null,
                    data.data.detail.first_ap ? { label: "First AP", meta: data.data.detail.first_ap } : null,
                  ].filter(Boolean) as Array<{ label: string; meta: { timestamp?: string | null; filename?: string | null; image_url?: string | null } }>}
                />
              ) : (
                <EmptyState text="Milestone screenshots appear here when that difficulty has them." />
              )}
            </Card>
            <Card title="Road to FC / AP">
              {journey.data ? <JourneySummary data={journey.data} /> : <LoadingInline />}
            </Card>
          </div>
          <Card title="Progression timeline">
            {journey.data ? <TimelinePanel items={journey.data.timeline} /> : <LoadingInline />}
          </Card>
        </div>
      )}
    </div>
  );
}

function SettingsPage() {
  const auth = useAuth();
  const [form, setForm] = useState<Partial<User>>({});
  const [excludedSongIds, setExcludedSongIds] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [importText, setImportText] = useState("");
  const [transferMessage, setTransferMessage] = useState<string | null>(null);
  const metaSongConfig = useLoadable<MetaSongConfigResponse>(auth.user ? () => api.getMetaSongConfig(auth.user!.id) : null, [auth.user?.id]);

  useEffect(() => {
    if (auth.user) {
      setForm(auth.user);
      setExcludedSongIds((auth.user.excluded_song_ids || []).join(", "));
    }
  }, [auth.user?.id]);

  if (!auth.user) return null;
  const user = auth.user;

  async function save() {
    try {
      const parsedExcluded = excludedSongIds
        .split(",")
        .map((item) => Number(item.trim()))
        .filter((value) => Number.isFinite(value) && value > 0);
      const updated = await api.updateUser(user.id, { ...form, excluded_song_ids: parsedExcluded });
      auth.login(localStorage.getItem("bangstats.web.token") || "", updated);
      setMessage("Settings saved.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to save settings");
    }
  }

  async function exportData() {
    try {
      const payload = await api.exportUserData(user.id);
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `bangstats-export-user-${user.id}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setTransferMessage("Export created.");
    } catch (err) {
      setTransferMessage(err instanceof Error ? err.message : "Export failed");
    }
  }

  async function importData() {
    try {
      const payload = JSON.parse(importText) as Record<string, unknown>;
      const result = await api.importUserData(user.id, payload);
      setTransferMessage(
        `Import complete: ${result.restored_screenshots} restored, ${result.skipped_screenshots} skipped, ${result.unresolved_screenshot_references.length} unresolved image refs.`,
      );
      await auth.refreshUser();
    } catch (err) {
      setTransferMessage(err instanceof Error ? err.message : "Import failed");
    }
  }

  return (
    <div className="page-grid">
      <SectionHeader title="User settings" />
      {message && <div className="notice">{message}</div>}
      <div className="layout-two">
        <Card title="Reference sync">
          <div className="stack">
            <p className="muted">Reference sync controls were moved under Settings to keep top-level navigation focused on daily workflows.</p>
            <Link className="button ghost" to="/sync">
              Open sync workspace
            </Link>
          </div>
        </Card>
        <Card title="Profile and scan source">
          <div className="stack">
            <div className="two-col">
              <label className="field">
                <span>Username</span>
                <input value={form.username || ""} onChange={(event) => setForm({ ...form, username: event.target.value })} />
              </label>
              <label className="field">
                <span>Game ID</span>
                <input value={form.game_id || ""} onChange={(event) => setForm({ ...form, game_id: event.target.value })} />
              </label>
            </div>
            <div className="two-col">
              <label className="field">
                <span>Server</span>
                <select value={form.server || "en"} onChange={(event) => setForm({ ...form, server: event.target.value as User["server"] })}>
                  {["en", "jp", "tw", "cn", "kr"].map((value) => (
                    <option key={value} value={value}>
                      {value.toUpperCase()}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Screenshot source</span>
                <select
                  value={form.screenshots_source || "local"}
                  onChange={(event) => setForm({ ...form, screenshots_source: event.target.value as User["screenshots_source"] })}
                >
                  <option value="local">Local / upload</option>
                  <option value="server_folder">Server folder</option>
                </select>
              </label>
            </div>
            <label className="field">
              <span>Screenshot path</span>
              <input value={form.screenshots_path || ""} onChange={(event) => setForm({ ...form, screenshots_path: event.target.value })} />
            </label>
            <label className="field">
              <span>Sync command</span>
              <input value={form.sync_command || ""} onChange={(event) => setForm({ ...form, sync_command: event.target.value })} />
            </label>
            <label className="field">
              <span>Personal meta-song exclusions</span>
              <input
                value={excludedSongIds}
                onChange={(event) => setExcludedSongIds(event.target.value)}
                placeholder="Comma-separated internal song IDs"
              />
            </label>
            {metaSongConfig.data && (
              <div className="inline-meta">Server defaults: {metaSongConfig.data.server_meta_song_ids.join(", ") || "None"}</div>
            )}
            <button className="button primary" onClick={() => void save()}>
              Save settings
            </button>
          </div>
        </Card>
        <Card title="Data import / export">
          <div className="stack">
            {transferMessage && <div className="notice">{transferMessage}</div>}
            <button className="button primary" onClick={() => void exportData()}>
              Export analytics JSON
            </button>
            <label className="field">
              <span>Import JSON payload</span>
              <textarea
                value={importText}
                onChange={(event) => setImportText(event.target.value)}
                placeholder="Paste exported BangStats JSON here"
              />
            </label>
            <button className="button accent" onClick={() => void importData()}>
              Import analytics JSON
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}

function AdminPage() {
  const [message, setMessage] = useState<string | null>(null);
  const health = useLoadable(() => api.health(), []);
  const [flush, setFlush] = useState({ remote_cache: false, scan_cache: false, db: false });

  async function runFlush() {
    try {
      const result = await api.flush(flush);
      setMessage(`Flush finished. Backup: ${result.backup_root}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Flush failed");
    }
  }

  return (
    <div className="page-grid">
      <SectionHeader title="Admin tools" />
      {message && <div className="notice">{message}</div>}
      <div className="layout-two">
        <Card title="Health">
          {health.data ? (
            <KeyValueList
              items={[
                ["Status", health.data.status],
                ["Mode", health.data.mode],
                ["DB path", health.data.db_path],
                ["Legacy DB", health.data.legacy_db_exists ? health.data.legacy_db_path : "Not found"],
              ]}
            />
          ) : <LoadingInline />}
        </Card>
        <Card title="Flush storage">
          <div className="stack">
            {[
              ["remote_cache", "Remote cache"],
              ["scan_cache", "Scan cache"],
              ["db", "SQLite DB"],
            ].map(([key, label]) => (
              <label className="check" key={key}>
                <input
                  type="checkbox"
                  checked={flush[key as keyof typeof flush]}
                  onChange={(event) => setFlush({ ...flush, [key]: event.target.checked })}
                />
                <span>{label}</span>
              </label>
            ))}
            <button className="button danger" onClick={() => void runFlush()}>
              Flush selected targets
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}

function AuthCard({
  title,
  subtitle,
  footer,
  children,
}: {
  title: string;
  subtitle: string;
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="brand-kicker">BangStats Web UI</div>
        <h1>{title}</h1>
        <p className="muted">{subtitle}</p>
        {children}
        {footer && <div className="auth-footer">{footer}</div>}
      </div>
    </div>
  );
}

// Remaining helper components (not yet extracted)

function InsightsPanel({ data }: { data: InsightsResponse }) {
  return (
    <div className="stack">
      <div className="inline-meta">{formatDateRange(data.from_date, data.to_date)}</div>
      <KeyValueList
        items={[
          ["Observed plays", String(data.data_quality.observed_plays)],
          ["Sessions", String(data.sessions.total_sessions)],
          ["Avg session minutes", String(data.sessions.avg_session_minutes)],
          ["Avg plays/session", String(data.sessions.avg_plays_per_session)],
          ["Longest session", `${data.sessions.longest_session_minutes} min`],
        ]}
      />
      <ul className="list">
        {data.practice_periods.slice(0, 5).map((item) => (
          <li key={`${item.song_id}-${item.latest_burst_at || "burst"}`}>
            <strong>{item.song_name || `Song ${item.song_id}`}</strong>: {item.total_plays} plays, max burst {item.max_burst_plays}, {item.estimated_time_played_human}
            {item.latest_burst_at && <span className="inline-meta"> · latest burst {formatDateTime(item.latest_burst_at)}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function SectionFilterControls({
  filters,
  onChange,
}: {
  filters: SectionFilterState;
  onChange: (filters: SectionFilterState) => void;
}) {
  return (
    <>
      <label className="field inline-field">
        <span>Difficulty</span>
        <select value={filters.difficulty} onChange={(event) => onChange({ ...filters, difficulty: event.target.value })}>
          <option value="">All difficulties</option>
          {DIFFICULTY_FILTERS.map((value) => (
            <option key={value} value={value}>
              {formatDifficulty(value)}
            </option>
          ))}
        </select>
      </label>
      <label className="field inline-field">
        <span>Live type</span>
        <select value={filters.liveType} onChange={(event) => onChange({ ...filters, liveType: event.target.value })}>
          <option value="">All live types</option>
          {LIVE_TYPE_FILTERS.map((value) => (
            <option key={value} value={value}>
              {formatLiveType(value)}
            </option>
          ))}
        </select>
      </label>
      <label className="check analytics-toggle">
        <input
          type="checkbox"
          checked={filters.includeMeta}
          onChange={(event) => onChange({ ...filters, includeMeta: event.target.checked })}
        />
        <span>Include meta songs</span>
      </label>
    </>
  );
}

function ExclusionPill({
  config,
}: {
  config:
    | {
        server_meta_song_ids?: number[];
        user_excluded_song_ids?: number[];
        effective_song_ids?: number[];
        is_active?: boolean;
      }
    | null;
}) {
  if (!config || !config.effective_song_ids?.length) {
    return <span className="pill">No meta-song exclusions</span>;
  }
  return <span className="pill">Excluding {config.effective_song_ids.length} meta-song IDs</span>;
}

function RecentPlayList({
  items,
}: {
  items: Array<{ song_id: number; song_name?: string | null; difficulty: string; timestamp?: string | null; filename?: string | null; live_type?: string | null; image_url?: string | null }>;
}) {
  if (!items.length) return <EmptyState text="No recent plays found." />;
  return (
    <div className="list-grid">
      {items.map((item, index) => (
        <div key={`${item.song_id}-${item.timestamp || index}`} className="list-card">
          <div>
            <strong>{item.song_name || `Song #${item.song_id}`}</strong>
            <div className="inline-meta">
              {formatDifficulty(item.difficulty)} | {formatLiveType(item.live_type)}
            </div>
          </div>
          <div className="inline-meta">{formatDateTime(item.timestamp)}</div>
          {item.image_url ? <SecureImage path={item.image_url} alt={item.filename || `play-${index}`} className="thumb-image" /> : <div className="gallery-placeholder thumb-image">No image</div>}
        </div>
      ))}
    </div>
  );
}

function SongRankingsTable({ data }: { data: SongRankingsResponse }) {
  if (!data.items.length) return <EmptyState text="No ranked songs found for the current filters." />;
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Song</th>
            <th>Plays</th>
            <th>FC</th>
            <th>AP</th>
            <th>Skill</th>
            <th>Latest</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((item) => (
            <tr key={item.song_id}>
              <td>
                <Link to={`/stats/song/${item.song_id}`}>{item.song_name || `Song #${item.song_id}`}</Link>
              </td>
              <td>{item.play_count}</td>
              <td>{item.fc_count}</td>
              <td>{item.ap_count}</td>
              <td>{item.skill_score}</td>
              <td>{formatShortDate(item.latest_play?.timestamp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RecapPanel({ data }: { data: RecapResponse }) {
  return (
    <div className="stack">
      <div className="inline-meta">{formatDateRange(data.from_date, data.to_date)}</div>
      <div className="stats-grid compact">
        <MetricCard label="Scope" value={data.title} />
        <MetricCard label="Skill score" value={data.skill_score} />
        <MetricCard label="Delta" value={data.skill_score_delta} />
        <MetricCard label="Sessions" value={data.sessions.total_sessions || 0} />
      </div>
      <div className="card-grid recap-grid">
        {data.highlights.map((item) => (
          <div className="highlight-card" key={item.title}>
            <span className="brand-kicker">{item.title}</span>
            <strong>{item.value}</strong>
            <p>{item.detail}</p>
            {item.screenshot?.image_url && <SecureImage path={item.screenshot.image_url} alt={item.screenshot.filename || item.title} className="highlight-image" />}
          </div>
        ))}
      </div>
      <div className="layout-two">
        <div>
          <div className="subheading">Top songs</div>
          <BarChart items={data.top_songs.map((item) => ({ label: item.song_name || `#${item.song_id}`, value: item.play_count }))} />
        </div>
        <div>
          <div className="subheading">Most practiced</div>
          <BarChart items={data.most_practiced.map((item) => ({ label: item.song_name || `#${item.song_id}`, value: item.play_count }))} />
        </div>
      </div>
      <div className="layout-two">
        <div>
          <div className="subheading">Live types</div>
          <BarChart items={Object.entries(data.live_types).map(([label, value]) => ({ label: formatLiveType(label), value }))} />
        </div>
        <div>
          <div className="subheading">Active hours</div>
          <BarChart items={groupActiveHours(data.active_hours)} />
        </div>
      </div>
    </div>
  );
}

function EventStatsPanel({ data }: { data: EventStatsResponse }) {
  return (
    <div className="stack">
      <div className="inline-meta">{formatDateRange(data.from_date, data.to_date)}</div>
      <div className="stats-grid compact">
        <MetricCard label="Event" value={data.event_name || `#${data.event_id}`} />
        <MetricCard label="Skill score" value={data.skill_score} />
        <MetricCard label="Sessions" value={data.total_sessions} />
        <MetricCard label="Longest session" value={`${data.longest_session_minutes}m`} />
      </div>
      <div className="layout-two">
        <div>
          <div className="subheading">Most played songs</div>
          <BarChart items={data.top_songs.map((item) => ({ label: item.song_name || `#${item.song_id}`, value: item.play_count }))} />
        </div>
        <div>
          <div className="subheading">Live types</div>
          <BarChart items={Object.entries(data.live_types).map(([label, value]) => ({ label: formatLiveType(label), value }))} />
        </div>
      </div>
      <div>
        <div className="subheading">Hours active</div>
        <BarChart items={groupActiveHours(data.active_hours)} />
      </div>
    </div>
  );
}

function EventFocusPanel({
  stats,
  recap,
}: {
  stats: EventStatsResponse;
  recap: RecapResponse | null;
}) {
  return (
    <div className="stack">
      <EventStatsPanel data={stats} />
      {recap && recap.highlights.length > 0 && (
        <div className="stack">
          <div className="subheading">Event highlights</div>
          <div className="card-grid recap-grid">
            {recap.highlights.map((item) => (
              <div className="highlight-card" key={`${stats.event_id}-${item.title}`}>
                <span className="brand-kicker">{item.title}</span>
                <strong>{item.value}</strong>
                <p>{item.detail}</p>
                {item.screenshot?.image_url && <SecureImage path={item.screenshot.image_url} alt={item.screenshot.filename || item.title} className="highlight-image" />}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function CurrentEventCard({
  data,
  server,
}: {
  data: DashboardResponse;
  server: User["server"];
}) {
  if (!data.current_event) {
    return (
      <div className="stack">
        <EmptyState text={data.current_event_status || "No event found for this server at current UTC time."} />
        <div className="inline-meta">Server {server.toUpperCase()} · DB {data.runtime.db_path}</div>
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="event-summary">
        <div>
          <div className="brand-kicker">Current event</div>
          <h4>{resolveEventName(data.current_event, server)}</h4>
        </div>
        <div className="toolbar-chip">{data.current_event_status}</div>
      </div>
      <KeyValueList
        items={[
          ["Event ID", String((data.current_event.event_id as number | string | undefined) || "Not found in repo")],
          ["Type", String(data.current_event.event_type || "Not found in repo")],
          ["Start", formatEventBoundary(data.current_event.event_start_at, server)],
          ["End", formatEventBoundary(data.current_event.event_end_at, server)],
          ["Diagnostics", `Server ${data.runtime.server.toUpperCase()} · DB ${data.runtime.db_path}`],
        ]}
      />
    </div>
  );
}

function MilestoneTimeline({
  items,
}: {
  items: MilestonesResponse["milestones"];
}) {
  if (!items.length) return <EmptyState text="No milestones yet." />;
  return (
    <div className="timeline milestone-timeline">
      {items.map((item, index) => (
        <div key={`${item.type}-${item.play_count}-${index}`} className="timeline-item">
          <div className="timeline-marker" />
          <div className="timeline-content milestone-row">
            {item.meta?.image_url ? (
              <SecureImage path={item.meta.image_url} alt={item.label} className="thumb-image" />
            ) : (
              <div className="gallery-placeholder thumb-image">No image</div>
            )}
            <div className="stack">
              <strong>{item.label}</strong>
              <div className="inline-meta">Play #{item.play_count}</div>
              <div className="inline-meta">{formatDateTime(item.meta?.timestamp)}</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function MilestoneGallery({
  items,
}: {
  items: Array<{ label: string; meta: { timestamp?: string | null; filename?: string | null; image_url?: string | null } }>;
}) {
  if (!items.length) return <EmptyState text="No milestone images available." />;
  return (
    <div className="gallery milestone-gallery">
      {items.map((item) => (
        <div className="gallery-card" key={item.label}>
          {item.meta.image_url ? <SecureImage path={item.meta.image_url} alt={item.meta.filename || item.label} className="gallery-image" /> : <div className="gallery-placeholder">No image</div>}
          <div className="gallery-meta">
            <strong>{item.label}</strong>
            <span>{item.meta.timestamp ? new Date(item.meta.timestamp).toLocaleString() : "Unknown date"}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function JourneySummary({ data }: { data: SongJourneyResponse }) {
  return (
    <KeyValueList
      items={[
        ["Difficulty", formatDifficulty(data.difficulty)],
        ["Total plays", String(data.total_plays)],
        ["Skill score", String(data.skill_score)],
        ["Plays before FC", data.plays_before_fc == null ? "Not found" : String(data.plays_before_fc)],
        ["Plays before AP", data.plays_before_ap == null ? "Not found" : String(data.plays_before_ap)],
        ["Practice windows", String(data.practice_periods.length)],
      ]}
    />
  );
}

function TimelinePanel({
  items,
}: {
  items: Array<{ type: string; label: string; timestamp?: string | null; filename?: string | null; image_url?: string | null; details: Record<string, unknown> }>;
}) {
  if (!items.length) return <EmptyState text="No timeline items found." />;
  return (
    <div className="timeline">
      {items.map((item, index) => (
        <div className="timeline-item" key={`${item.type}-${item.timestamp || index}`}>
          <div className="timeline-marker" />
          <div className="timeline-content">
            <strong>{item.label}</strong>
            <div className="inline-meta">{item.timestamp ? new Date(item.timestamp).toLocaleString() : "No timestamp"}</div>
            {item.image_url && <SecureImage path={item.image_url} alt={item.filename || item.label} className="thumb-image" />}
            {!!Object.keys(item.details || {}).length && <CodeBlock value={item.details} />}
          </div>
        </div>
      ))}
    </div>
  );
}

function CodeBlock({ value }: { value: unknown }) {
  return <pre className="code-block">{JSON.stringify(value, null, 2)}</pre>;
}

function scanResultSummary(result: ScanResult, prefix: string) {
  return `${prefix}: ${result.total_scanned} scanned, ${result.successful} successful, ${result.persisted} persisted, ${result.skipped_duplicates} duplicates.`;
}

export default App;
