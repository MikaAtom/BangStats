import type { ReactNode } from "react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
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

import { useLoadable } from "./hooks/useLoadable";
import { useThumbnailPrewarm } from "./hooks/useThumbnailPrewarm";
import { useAuth } from "./auth";
import {
  api,
  type ActivityResponse,
  type CalendarResponse,
  type CalendarYearResponse,
  type DashboardResponse,
  type ErrorCategoryActionResponse,
  type ErrorDetail,
  type ErrorList,
  type EventStatsResponse,
  type FilenameDiffResponse,
  type MilestonesResponse,
  type MetaSongConfigResponse,
  type ProgressionResponse,
  type RecentPlayOverview,
  type RecapResponse,
  type ReferenceSongItem,
  type SongRankingsResponse,
  type ScanJob,
  type ScanResult,
  type ScreenshotItem,
  type SongJourneyResponse,
  type SongStatsResponse,
  type StatsOverview,
  type SyncJob,
  type UploadFileItem,
  type User,
} from "./api";

import { Card, MetricCard, LoadingCard, LoadingInline, EmptyState, SectionHeader, SecureImage, DateRangePicker, type DateRangeValue } from "./components/ui";
import { KeyValueList, JobList } from "./components/data-display";
import { BarChart, ActivitySummary, TrendChart } from "./components/charts";
import { UploadGallery, ScreenshotGallery } from "./components/galleries";
import {
  formatDateRange,
  formatDateTime,
  formatDifficulty,
  formatEventBoundary,
  formatEventLabel,
  formatEventLabelDateOnly,
  formatLiveType,
  formatShortDate,
  groupActiveHours,
  resolveEventName,
  webLocale,
} from "./utils/format";
import { dateRangeToQuery, resolveAbsoluteDateRange, sectionFiltersToQuery, type SectionFilterState } from "./stats/statsQuery";
import { recapNavLabel, stepRecapAnchor, type RecapScope } from "./stats/recapNav";
import { ScreenshotModal, type ScreenshotModalItem } from "./components/screenshots/ScreenshotModal";
import {
  CalendarExplorerModal,
  calendarRangeForMode,
  type CalendarExplorerMode,
} from "./components/calendar/CalendarExplorerModal";

type AnalyticsView = "overview" | "progress" | "milestones" | "songs" | "recap" | "calendar" | "screenshots";

type SidebarItem = {
  to: string;
  label: string;
  isActive: (pathname: string) => boolean;
};

const DEFAULT_DATE_RANGE: DateRangeValue = {
  preset: "30d",
  from: "",
  to: "",
};

const ANALYTICS_VIEWS: AnalyticsView[] = ["overview", "progress", "milestones", "songs", "recap", "calendar", "screenshots"];
const DIFFICULTY_FILTERS = ["easy", "normal", "hard", "expert", "special"];
const LIVE_TYPE_FILTERS = ["normal_live", "event_live", "challenge_live", "multi_live", "vs_live", "free_live"];
const CORRECTION_DIFFICULTIES = ["easy", "normal", "hard", "expert", "special"] as const;
const CORRECTION_LIVE_TYPES = ["free live", "multi live", "challenge live", "team live battle", "medley live"] as const;
const SONG_RANKING_SORT_KEYS = ["play_count", "fc_count", "ap_count", "skill_score"] as const;

type SongRankingRow = SongRankingsResponse["items"][number];
type SongRankingSortKey = (typeof SONG_RANKING_SORT_KEYS)[number];
type SortOrder = "asc" | "desc";

type CorrectionFormState = {
  song_name_from_top_bar_text: string;
  difficulty: string;
  live_type: string;
  perfect: number;
  great: number;
  good: number;
  bad: number;
  miss: number;
  fast: number;
  slow: number;
  max_combo: number;
  score: number;
  high_score: number;
  score_rank: string;
  is_new_record: boolean;
  anomaly: boolean;
};

type CorrectionIssue = {
  title: string;
  detail: string;
  tone?: "default" | "warning" | "error";
};

function parseBool(value: unknown, fallback = false) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") {
    return ["1", "true", "yes", "on", "y"].includes(value.trim().toLowerCase());
  }
  return fallback;
}

function songRankingSortValue(item: SongRankingRow, sortBy: SongRankingSortKey) {
  switch (sortBy) {
    case "skill_score":
      return [Number(item.skill_score || 0), Number(item.play_count || 0)];
    case "fc_count":
      return [Number(item.fc_count || 0), Number(item.play_count || 0)];
    case "ap_count":
      return [Number(item.ap_count || 0), Number(item.play_count || 0)];
    case "play_count":
    default:
      return [Number(item.play_count || 0), Number(item.skill_score || 0)];
  }
}

function compareSongRankingRows(a: SongRankingRow, b: SongRankingRow, sortBy: SongRankingSortKey, sortOrder: SortOrder) {
  const [aPrimary, aSecondary] = songRankingSortValue(a, sortBy);
  const [bPrimary, bSecondary] = songRankingSortValue(b, sortBy);
  const direction = sortOrder === "asc" ? 1 : -1;

  if (aPrimary !== bPrimary) return direction * (aPrimary - bPrimary);
  if (aSecondary !== bSecondary) return direction * (aSecondary - bSecondary);

  const aName = String(a.song_name || "").toLowerCase();
  const bName = String(b.song_name || "").toLowerCase();
  if (aName !== bName) return aName.localeCompare(bName);
  return Number(a.song_id || 0) - Number(b.song_id || 0);
}

function sortSongRankingRows(items: SongRankingsResponse["items"], sortBy: SongRankingSortKey, sortOrder: SortOrder) {
  return [...items].sort((a, b) => compareSongRankingRows(a, b, sortBy, sortOrder));
}

function parseNumber(value: unknown, fallback = 0) {
  if (typeof value === "number" && Number.isFinite(value)) return Math.trunc(value);
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function parseCorrectionForm(scanData: Record<string, unknown>): CorrectionFormState {
  return {
    song_name_from_top_bar_text: String(scanData.song_name_from_top_bar_text || ""),
    difficulty: String(scanData.difficulty || "expert").toLowerCase(),
    live_type: String(scanData.live_type || "free live").toLowerCase(),
    perfect: parseNumber(scanData.perfect, 0),
    great: parseNumber(scanData.great, 0),
    good: parseNumber(scanData.good, 0),
    bad: parseNumber(scanData.bad, 0),
    miss: parseNumber(scanData.miss, 0),
    fast: parseNumber(scanData.fast, 0),
    slow: parseNumber(scanData.slow, 0),
    max_combo: parseNumber(scanData.max_combo, 0),
    score: parseNumber(scanData.score, 0),
    high_score: parseNumber(scanData.high_score, -1),
    score_rank: String(scanData.score_rank || ""),
    is_new_record: parseBool(scanData.is_new_record, false),
    anomaly: parseBool(scanData.anomaly, false),
  };
}

function correctionFormToPayload(form: CorrectionFormState): Record<string, unknown> {
  return {
    song_name_from_top_bar_text: form.song_name_from_top_bar_text,
    difficulty: form.difficulty,
    live_type: form.live_type,
    perfect: form.perfect,
    great: form.great,
    good: form.good,
    bad: form.bad,
    miss: form.miss,
    fast: form.fast,
    slow: form.slow,
    max_combo: form.max_combo,
    score: form.score,
    high_score: form.high_score,
    score_rank: form.score_rank,
    is_new_record: form.is_new_record,
    anomaly: form.anomaly,
  };
}

function correctionSongName(song: ReferenceSongItem, server: User["server"]) {
  return (
    song.name[server] ||
    song.name.en ||
    song.name.jp ||
    song.name.tw ||
    song.name.cn ||
    song.name.kr ||
    String(song.internal_song_id)
  );
}

function songSupportsSpecial(song: ReferenceSongItem | null) {
  return Boolean(song?.special && typeof song.special === "object" && (song.special as Record<string, unknown>).available);
}

function getExpectedNotes(song: ReferenceSongItem | null, difficulty: string) {
  if (!song) return null;
  const raw = song.note_counts?.[difficulty];
  if (typeof raw === "number") {
    return Number.isFinite(raw) ? Math.trunc(raw) : null;
  }
  if (Array.isArray(raw) && raw.length > 0) {
    const first = raw[0];
    return typeof first === "number" && Number.isFinite(first) ? Math.trunc(first) : null;
  }
  return null;
}

function getSongValidationIssues(
  form: CorrectionFormState,
  selectedSong: ReferenceSongItem | null,
  backendValidation: Record<string, unknown> | null | undefined,
): CorrectionIssue[] {
  const issues: CorrectionIssue[] = [];
  const currentNotes = form.perfect + form.great + form.good + form.bad + form.miss;
  const expectedNotes = getExpectedNotes(selectedSong, form.difficulty);
  const totalFastSlow = form.fast + form.slow;
  const totalMissable = form.great + form.good + form.bad + form.miss;

  if (!form.song_name_from_top_bar_text.trim()) {
    issues.push({ title: "Song name missing", detail: "Search and select a song before saving.", tone: "error" });
  } else if (!selectedSong) {
    issues.push({ title: "Song not resolved", detail: "Pick an exact match from the search suggestions so note counts can be validated.", tone: "error" });
  }

  if (!form.difficulty || !CORRECTION_DIFFICULTIES.includes(form.difficulty as (typeof CORRECTION_DIFFICULTIES)[number])) {
    issues.push({ title: "Invalid difficulty", detail: "Pick easy, normal, hard, expert, or special.", tone: "error" });
  } else if (form.difficulty === "special" && !songSupportsSpecial(selectedSong)) {
    issues.push({ title: "Special difficulty unavailable", detail: "The selected song does not expose a special chart.", tone: "error" });
  }

  if (!form.live_type.trim()) {
    issues.push({ title: "Live type missing", detail: "Choose the live type from the dropdown.", tone: "error" });
  }

  if (expectedNotes !== null && currentNotes !== expectedNotes) {
    issues.push({
      title: "Note count mismatch",
      detail: `Expected ${expectedNotes} total notes, current sum is ${currentNotes} (${form.perfect}+${form.great}+${form.good}+${form.bad}+${form.miss}).`,
      tone: "error",
    });
  }

  if (totalFastSlow !== totalMissable) {
    issues.push({
      title: "Fast/slow mismatch",
      detail: `Expected fast + slow to match great + good + bad + miss. Current is ${totalFastSlow} vs ${totalMissable}.`,
      tone: "warning",
    });
  }

  if (form.perfect < 0 || form.great < 0 || form.good < 0 || form.bad < 0 || form.miss < 0 || form.fast < 0 || form.slow < 0 || form.max_combo < 0 || form.score < 0 || form.high_score < -1) {
    issues.push({ title: "Negative values", detail: "Score and count fields must be zero or positive.", tone: "error" });
  }

  const rawReasons = backendValidation?.reasons;
  const reasons = Array.isArray(rawReasons) ? rawReasons.filter((item): item is string => typeof item === "string") : [];
  if (backendValidation?.error_type && reasons.length > 0) {
    issues.push({
      title: "Backend validation",
      detail: `${String(backendValidation.error_type)}: ${reasons.join(" • ")}`,
      tone: "warning",
    });
  }

  return issues;
}

function getSongOptions(songs: ReferenceSongItem[], query: string, server: User["server"]) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return songs.slice(0, 10);
  }
  return songs
    .filter((song) => correctionSongName(song, server).toLowerCase().includes(normalized))
    .slice(0, 12);
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
      isActive: (pathname) => pathname === "/scan" || pathname.startsWith("/scan/jobs"),
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
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/scan"}
              className={item.isActive(location.pathname) ? "nav-link active" : "nav-link"}
            >
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
            <ScreenshotGallery items={data.recent_screenshots} server={auth.user.server} userId={auth.user.id} />
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
          {uploads.data && <UploadGallery items={uploads.data.items} userId={user.id} />}
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
        <div className="card-grid error-inbox-grid">
          {Object.entries(errors.data.error_files).map(([errorType, files]) => (
            <Card
              key={errorType}
              className="error-category-card"
              title={`${errorType} (${files.length})`}
              actions={
                <div className="button-row error-card-actions">
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
  const navigate = useNavigate();
  const params = useParams();
  const errorType = decodeURIComponent(params.errorType || "");
  const jsonFilename = decodeURIComponent(params.jsonFilename || "");
  const detail = useLoadable<ErrorDetail>(() => api.getErrorDetail(errorType, jsonFilename), [errorType, jsonFilename]);
  const referenceSongs = useLoadable<{ max_id: number; items: ReferenceSongItem[] }>(
    auth.user ? () => api.getReferenceSongs(0, 5000) : null,
    [auth.user?.id],
  );
  const [form, setForm] = useState<CorrectionFormState | null>(null);
  const [payloadText, setPayloadText] = useState("");
  const [advancedMode, setAdvancedMode] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (detail.data) {
      const nextForm = parseCorrectionForm(detail.data.scan_data);
      setForm(nextForm);
      setPayloadText(JSON.stringify(correctionFormToPayload(nextForm), null, 2));
      setAdvancedMode(false);
    }
  }, [detail.data?.json_filename]);

  useEffect(() => {
    if (form && !advancedMode) {
      setPayloadText(JSON.stringify(correctionFormToPayload(form), null, 2));
    }
  }, [form, advancedMode]);

  if (!auth.user) return null;
  const user = auth.user;

  const songs = referenceSongs.data?.items || [];
  const songQuery = form?.song_name_from_top_bar_text || "";
  const songMatches = getSongOptions(songs, songQuery, user.server);
  const selectedSong =
    form && songQuery.trim()
      ? songs.find((song) => correctionSongName(song, user.server).toLowerCase() === songQuery.trim().toLowerCase()) || null
      : null;
  const availableDifficulties = selectedSong && songSupportsSpecial(selectedSong)
    ? [...CORRECTION_DIFFICULTIES]
    : CORRECTION_DIFFICULTIES.filter((item) => item !== "special");
  const backendValidation = detail.data?.validation as Record<string, unknown> | null | undefined;
  const issues = form ? getSongValidationIssues(form, selectedSong, backendValidation) : [];
  const blockingIssues = issues.filter((issue) => issue.tone !== "warning");
  const rawJsonError = advancedMode
    ? (() => {
        try {
          JSON.parse(payloadText);
          return null;
        } catch (err) {
          return err instanceof Error ? err.message : "Invalid JSON";
        }
      })()
    : null;
  const canSave = Boolean(form) && !rawJsonError && (form?.anomaly || blockingIssues.length === 0);

  function updateFormField<K extends keyof CorrectionFormState>(field: K, value: CorrectionFormState[K]) {
    setForm((current) => (current ? { ...current, [field]: value } : current));
  }

  function selectSong(song: ReferenceSongItem) {
    updateFormField("song_name_from_top_bar_text", correctionSongName(song, user.server));
  }

  async function saveCorrection() {
    try {
      const payload = advancedMode ? (JSON.parse(payloadText) as Record<string, unknown>) : correctionFormToPayload(form || parseCorrectionForm({}));
      const result = await api.correctError(errorType, jsonFilename, {
        user_id: user.id,
        corrected_scan_data: payload,
        persist_to_db: true,
        anomaly: Boolean((payload as Record<string, unknown>).anomaly),
      });
      setMessage(
        result.is_valid
          ? result.saved_as_anomaly
            ? `Saved as anomaly. Persisted=${result.persisted} duplicate=${result.skipped_duplicates}`
            : `Correction succeeded. Persisted=${result.persisted} duplicate=${result.skipped_duplicates}`
          : `Still invalid. Moved to ${result.error_type || "unchanged"}.`,
      );
      if (result.saved_as_anomaly || result.is_valid) {
        navigate("/scan/errors");
        return;
      }
      if (result.error_type && result.error_type !== errorType) {
        navigate(`/scan/errors/${encodeURIComponent(result.error_type)}/${encodeURIComponent(result.image_filename)}`);
        return;
      }
      await detail.reload();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Correction failed");
    }
  }

  async function deleteError() {
    const confirmed = window.confirm("Delete this error entry and matching DB row? This cannot be undone.");
    if (!confirmed) return;
    try {
      const result = await api.deleteError(errorType, jsonFilename, { user_id: user.id });
      setMessage(`Deleted error entry. Removed DB rows: ${result.removed_db_rows}`);
      navigate("/scan/errors");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div className="page-grid">
      <SectionHeader title={jsonFilename} action={<button className="button ghost" onClick={() => void deleteError()}>Delete</button>} />
      {message && <div className="notice">{message}</div>}
      {detail.loading && <LoadingCard label="Loading error detail..." />}
      {detail.error && <div className="notice error">{detail.error}</div>}
      {detail.data && form && (
        <div className="layout-two">
          <Card title="Screenshot preview">
            <SecureImage
              className="viewer-image"
              path={`/api/scans/errors/${encodeURIComponent(errorType)}/${encodeURIComponent(jsonFilename)}/image`}
              alt={detail.data.image_filename}
            />
            <div className="inline-meta">{detail.data.image_filename}</div>
          </Card>
          <Card title="Validation" actions={<button className="button ghost" onClick={() => setAdvancedMode((current) => !current)}>{advancedMode ? "Hide raw JSON" : "Show raw JSON"}</button>}>
            <div className="stack">
              <KeyValueList
                items={[
                  ["Song", selectedSong ? correctionSongName(selectedSong, user.server) : form.song_name_from_top_bar_text || "Not selected"],
                  ["Difficulty", form.difficulty || "--"],
                  ["Live type", form.live_type || "--"],
                  ["Expected notes", String(getExpectedNotes(selectedSong, form.difficulty) ?? "--")],
                  ["Current notes", String(form.perfect + form.great + form.good + form.bad + form.miss)],
                  ["Fast + slow", String(form.fast + form.slow)],
                ]}
                emptyLabel="No validation summary."
              />
              <div className="stack">
                {issues.length === 0 ? (
                  <div className="notice success">No blocking issues detected.</div>
                ) : (
                  issues.map((issue) => (
                    <div key={`${issue.title}-${issue.detail}`} className={issue.tone === "error" ? "notice error" : "notice"}>
                      <strong>{issue.title}.</strong> {issue.detail}
                    </div>
                  ))
                )}
              </div>
              {backendValidation && (
                <details>
                  <summary>Validation artifact</summary>
                  <CodeBlock value={backendValidation} />
                </details>
              )}
            </div>
          </Card>
          <Card
            title="Correction form"
            className="span-2"
            actions={
              <div className="button-row">
                <button className="button primary" onClick={() => void saveCorrection()} disabled={!canSave}>
                  Save correction
                </button>
              </div>
            }
          >
            <div className="stack">
              {!canSave && !form.anomaly && <div className="notice error">Fix the highlighted issues before saving, or mark the item as an anomaly.</div>}
              {form.anomaly && <div className="notice">Anomaly mode is enabled. Save is allowed even if validation still fails.</div>}
              <div className="layout-two">
                <div className="field">
                  <label htmlFor="song_name_from_top_bar_text">Song name</label>
                  <input
                    id="song_name_from_top_bar_text"
                    list="correction-song-options"
                    value={form.song_name_from_top_bar_text}
                    onChange={(event) => updateFormField("song_name_from_top_bar_text", event.target.value)}
                    placeholder="Search and select a song"
                  />
                  <datalist id="correction-song-options">
                    {songMatches.map((song) => (
                      <option key={song.id} value={correctionSongName(song, user.server)} />
                    ))}
                  </datalist>
                  <div className="inline-meta">Search results: {songMatches.length}</div>
                  <div className="button-row wrap">
                    {songMatches.slice(0, 6).map((song) => (
                      <button key={song.id} className="button ghost" type="button" onClick={() => selectSong(song)}>
                        {correctionSongName(song, user.server)}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="field">
                  <label htmlFor="difficulty">Difficulty</label>
                  <select
                    id="difficulty"
                    value={form.difficulty}
                    onChange={(event) => updateFormField("difficulty", event.target.value)}
                  >
                    {availableDifficulties.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="layout-two">
                <div className="field">
                  <label htmlFor="live_type">Live type</label>
                  <select id="live_type" value={form.live_type} onChange={(event) => updateFormField("live_type", event.target.value)}>
                    {CORRECTION_LIVE_TYPES.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="check">
                  <input
                    id="anomaly"
                    type="checkbox"
                    checked={form.anomaly}
                    onChange={(event) => updateFormField("anomaly", event.target.checked)}
                  />
                  <label htmlFor="anomaly">Mark as anomaly</label>
                </div>
              </div>

              <div className="stats-grid">
                {[
                  ["perfect", form.perfect],
                  ["great", form.great],
                  ["good", form.good],
                  ["bad", form.bad],
                  ["miss", form.miss],
                  ["fast", form.fast],
                  ["slow", form.slow],
                  ["max_combo", form.max_combo],
                  ["score", form.score],
                  ["high_score", form.high_score],
                ].map(([field, value]) => (
                  <div className="field" key={String(field)}>
                    <label htmlFor={String(field)}>{String(field).replace(/_/g, " ")}</label>
                    <input
                      id={String(field)}
                      type="number"
                      value={String(value)}
                      onChange={(event) => updateFormField(field as keyof CorrectionFormState, parseNumber(event.target.value, Number(value)))}
                    />
                  </div>
                ))}
              </div>

              <div className="layout-two">
                <div className="field">
                  <label htmlFor="score_rank">Score rank</label>
                  <input
                    id="score_rank"
                    value={form.score_rank}
                    onChange={(event) => updateFormField("score_rank", event.target.value)}
                    placeholder="SS, S, A, ..."
                  />
                </div>
                <div className="check">
                  <input
                    id="is_new_record"
                    type="checkbox"
                    checked={form.is_new_record}
                    onChange={(event) => updateFormField("is_new_record", event.target.checked)}
                  />
                  <label htmlFor="is_new_record">New record</label>
                </div>
              </div>

              {advancedMode && (
                <div className="field">
                  <label htmlFor="payloadText">Advanced raw JSON</label>
                  <textarea className="editor" id="payloadText" value={payloadText} onChange={(event) => setPayloadText(event.target.value)} />
                  {rawJsonError && <div className="notice error">{rawJsonError}</div>}
                </div>
              )}

              {!advancedMode && (
                <details>
                  <summary>Advanced raw JSON</summary>
                  <textarea className="editor" value={payloadText} readOnly />
                </details>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

function StatsPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const requestedView = searchParams.get("view");

  useEffect(() => {
    if (requestedView === "events") {
      navigate("/stats?view=recap&scope=event", { replace: true });
    }
  }, [requestedView, navigate]);

  const view: AnalyticsView = ANALYTICS_VIEWS.includes(requestedView as AnalyticsView)
    ? (requestedView as AnalyticsView)
    : "overview";

  return (
    <div className="page-grid">
      <SectionHeader title="Analytics workspace" />
      <nav className="analytics-subnav analytics-tabbar">
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
      {view === "recap" && <RecapAnalyticsView />}
      {view === "calendar" && <CalendarAnalyticsView />}
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
  const server = auth.user.server;

  const milestoneTeaserItems = useMemo(() => {
    const list = milestones.data?.milestones;
    if (!list?.length) return [];
    return [...list]
      .sort((a, b) => {
        const ta = a.meta?.timestamp ? new Date(a.meta.timestamp).getTime() : 0;
        const tb = b.meta?.timestamp ? new Date(b.meta.timestamp).getTime() : 0;
        return tb - ta;
      })
      .slice(0, 2);
  }, [milestones.data?.milestones]);

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
      <div className="overview-layout">
        <div className="overview-layout__primary">
          <Card title="Current progress snapshot" className="overview-card overview-card--chart">
            {progression.data ? <TrendChart data={progression.data} variant="overview" server={server} /> : <LoadingInline />}
          </Card>
          <div className="overview-layout__secondary">
            <Card title="This month" className="overview-card overview-card--activity">
              {progression.data ? <OverviewActivitySnippet data={progression.data} server={server} /> : <LoadingInline />}
            </Card>
            <Card
              title="Latest milestones"
              className="overview-card overview-card--milestones"
              actions={<Link to="/stats?view=milestones">View all milestones</Link>}
            >
              {milestones.data ? <MilestoneTimeline items={milestoneTeaserItems} server={server} /> : <LoadingInline />}
            </Card>
          </div>
        </div>
        <Card title="Recent lives" className="overview-card overview-card--recent">
          {overview.data ? <RecentPlayList items={overview.data.recent} server={server} userId={auth.user.id} /> : <LoadingInline />}
        </Card>
      </div>
    </div>
  );
}

function OverviewActivitySnippet({
  data,
  server,
}: {
  data: ProgressionResponse;
  server: User["server"];
}) {
  const current = data.points[data.points.length - 1] ?? null;
  if (!current) return <EmptyState text="No monthly progression data yet." />;

  return (
    <div className="overview-activity">
      <div className="overview-activity__header">
        <strong>{current.label}</strong>
        <span>{formatDateRange(current.from_date, current.to_date, server)}</span>
      </div>
      <div className="overview-activity__stats">
        <div className="overview-activity__stat">
          <span>Plays</span>
          <strong>{current.plays}</strong>
        </div>
        <div className="overview-activity__stat">
          <span>FC</span>
          <strong>{current.fc}</strong>
        </div>
        <div className="overview-activity__stat">
          <span>AP</span>
          <strong>{current.ap}</strong>
        </div>
        <div className="overview-activity__stat">
          <span>Accuracy</span>
          <strong>{current.accuracy}%</strong>
        </div>
      </div>
      <div className="overview-activity__footer">
        <span className="overview-activity__delta-label">Delta vs previous</span>
        <div className="overview-activity__delta-row">
          <strong>Skill {data.delta_skill_score >= 0 ? "+" : ""}{data.delta_skill_score}</strong>
          <span>Accuracy {data.delta_accuracy >= 0 ? "+" : ""}{data.delta_accuracy}%</span>
        </div>
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

  if (!auth.user) return null;
  const server = auth.user.server;

  return (
    <div className="page-grid">
      <Card
        title="Scope & filters"
        actions={
          <Link className="button primary" to="/stats?view=calendar">
            Open calendar
          </Link>
        }
      >
        <p className="inline-meta progress-analytics-toolbar__hint">
          Play filters apply to progression, activity, and calendar. Trend scope and data points only change the skill chart. Activity window sets the date range for metrics below.
        </p>
        <div className="progress-analytics-toolbar">
          <div className="progress-analytics-toolbar__row progress-analytics-toolbar__row--trend">
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
          <div className="progress-analytics-toolbar__row progress-analytics-toolbar__row--filters">
            <SectionFilterControls filters={filters} onChange={setFilters} />
          </div>
          <div className="progress-analytics-toolbar__row progress-analytics-toolbar__row--activity">
            <span className="progress-analytics-toolbar__activity-label">Activity window</span>
            <div className="progress-analytics-toolbar__activity-picker">
              <DateRangePicker value={range} onChange={setRange} />
            </div>
          </div>
          <div className="inline-meta progress-analytics-toolbar__footer">
            <Link to="/stats?view=calendar">Calendar</Link>
            {" · "}
            <Link to="/stats?view=milestones">Milestone timeline</Link>
          </div>
        </div>
      </Card>
      <Card title="Skill trend" subtitle="Hover points for details; per-period breakdown below the chart">
        {progression.data ? <TrendChart data={progression.data} /> : <LoadingInline />}
      </Card>
      <Card
        title="Activity"
        subtitle={
          activity.data
            ? formatDateRange(activity.data.from_date, activity.data.to_date, server)
            : "Summary for the selected activity window"
        }
      >
        {activity.data ? (
          <ActivitySummary data={activity.data} />
        ) : !customRangeReady ? (
          <EmptyState text="Pick both custom dates to load activity." />
        ) : (
          <LoadingInline />
        )}
      </Card>
    </div>
  );
}

function CalendarAnalyticsView() {
  const auth = useAuth();
  const [searchParams] = useSearchParams();
  const [filters, setFilters] = useState<SectionFilterState>({ difficulty: "", liveType: "", includeMeta: false });
  const filterQuery = sectionFiltersToQuery(filters);
  const [anchorDate, setAnchorDate] = useState(() => new Date());
  const [mode, setMode] = useState<CalendarExplorerMode>("month");
  const [selectedEventId, setSelectedEventId] = useState("");
  const [eventSearch, setEventSearch] = useState("");

  const songIdRaw = searchParams.get("songId");
  const songIdNumber = songIdRaw && /^\d+$/.test(songIdRaw) ? Number(songIdRaw) : undefined;

  const events = useLoadable(auth.user ? () => api.getReferenceEvents(1200) : null, [auth.user?.id]);

  useEffect(() => {
    const d = searchParams.get("calDay");
    if (d && /^\d{4}-\d{2}-\d{2}$/.test(d)) {
      setAnchorDate(new Date(`${d}T00:00:00`));
    }
    const m = searchParams.get("calMode");
    if (m === "year" || m === "month" || m === "week" || m === "day" || m === "event") {
      setMode(m);
    }
    const eid = searchParams.get("eventId");
    if (eid) setSelectedEventId(eid);
  }, [searchParams]);

  const eventStats = useLoadable<EventStatsResponse>(
    auth.user && selectedEventId
      ? () => api.getEventStats(auth.user!.id, Number(selectedEventId), filterQuery)
      : null,
    [auth.user?.id, selectedEventId, filters.difficulty, filters.liveType, filters.includeMeta],
  );

  const calendarEventWindow =
    selectedEventId && eventStats.data
      ? { from_date: eventStats.data.from_date, to_date: eventStats.data.to_date }
      : null;

  useEffect(() => {
    if (mode === "event" && !calendarEventWindow) {
      setMode("month");
    }
  }, [mode, calendarEventWindow]);

  const screenshotRange = useMemo(() => {
    if (mode === "event") {
      return calendarEventWindow;
    }
    return calendarRangeForMode(mode, anchorDate, null);
  }, [mode, anchorDate, calendarEventWindow]);

  const calendarMonth = useLoadable<CalendarResponse>(
    auth.user && (mode === "month" || mode === "week" || mode === "day")
      ? () => api.getCalendar(auth.user!.id, anchorDate.getFullYear(), anchorDate.getMonth() + 1, filterQuery, songIdNumber)
      : null,
    [
      auth.user?.id,
      mode,
      anchorDate.getFullYear(),
      anchorDate.getMonth(),
      filters.difficulty,
      filters.liveType,
      filters.includeMeta,
      songIdNumber,
    ],
  );

  const calendarYear = useLoadable<CalendarYearResponse>(
    auth.user && mode === "year"
      ? () => api.getCalendarYear(auth.user!.id, anchorDate.getFullYear(), filterQuery, songIdNumber)
      : null,
    [auth.user?.id, mode, anchorDate.getFullYear(), filters.difficulty, filters.liveType, filters.includeMeta, songIdNumber],
  );

  const calendarShots = useLoadable(
    auth.user && mode !== "year" && screenshotRange
      ? () =>
          api.listScreenshots(auth.user!.id, {
            ...filterQuery,
            ...(songIdNumber ? { songId: songIdNumber } : {}),
            ...screenshotRange,
            limit: mode === "day" ? 80 : 200,
            offset: 0,
            sort_by: "timestamp",
            sort_order: "desc",
          })
      : null,
    [
      auth.user?.id,
      mode,
      anchorDate.getFullYear(),
      anchorDate.getMonth(),
      anchorDate.getDate(),
      screenshotRange?.from_date,
      screenshotRange?.to_date,
      filters.difficulty,
      filters.liveType,
      filters.includeMeta,
      songIdNumber,
    ],
  );

  if (!auth.user) return null;
  const server = auth.user.server;
  const recentEvents = ((events.data?.items || []) as Array<Record<string, unknown>>)
    .slice()
    .filter((event) => Number.isFinite(Number(event.event_id || event.id)) && Number(event.event_id || event.id) > 0)
    .sort((a, b) => Number(b.event_id || b.id || 0) - Number(a.event_id || a.id || 0));
  const q = eventSearch.trim().toLowerCase();
  const filteredEvents = q
    ? recentEvents.filter((event) => formatEventLabelDateOnly(event, server).toLowerCase().includes(q))
    : recentEvents;

  const subtitle =
    songIdNumber != null
      ? `Filtered to song #${songIdNumber}`
      : selectedEventId
        ? "Pick Event mode after the event window loads to browse the full event range."
        : "Year, month, week, day, and optional event window.";

  return (
    <div className="page-grid">
      <Card title="Calendar filters" subtitle="Same play filters as other analytics views.">
        <div className="analytics-filter-row">
          <SectionFilterControls filters={filters} onChange={setFilters} />
        </div>
      </Card>
      <Card title="Event (optional)" subtitle="Select an event to enable Event mode in the explorer.">
        <div className="stack">
          <label className="field">
            <span>Search events</span>
            <input value={eventSearch} onChange={(e) => setEventSearch(e.target.value)} placeholder="Filter by name or date" />
          </label>
          <label className="field inline-field">
            <span>Event</span>
            <select
              value={selectedEventId}
              onChange={(event) => {
                setSelectedEventId(event.target.value);
                if (!event.target.value) setMode((m) => (m === "event" ? "month" : m));
              }}
            >
              <option value="">None (hide Event dates)</option>
              {filteredEvents.slice(0, 200).map((event) => (
                <option key={String(event.event_id || event.id)} value={String(event.event_id || event.id)}>
                  {formatEventLabelDateOnly(event, server)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </Card>
      <Card title="Explorer" subtitle={subtitle}>
        <CalendarExplorerModal
          open
          variant="inline"
          title="Calendar"
          server={server}
          mode={mode}
          anchorDate={anchorDate}
          onModeChange={setMode}
          onAnchorDateChange={setAnchorDate}
          onClose={() => {}}
          yearState={calendarYear}
          monthState={calendarMonth}
          shotsState={calendarShots}
          showEventMode={Boolean(selectedEventId)}
          eventRange={calendarEventWindow}
        />
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
        {milestones.data ? <MilestoneTimeline items={milestones.data.milestones} server={auth.user.server} /> : <LoadingInline />}
      </Card>
    </div>
  );
}

function SongsAnalyticsView() {
  const auth = useAuth();
  const [filters, setFilters] = useState<SectionFilterState>({ difficulty: "", liveType: "", includeMeta: false });
  const [sortBy, setSortBy] = useState<SongRankingSortKey>("play_count");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [results, setResults] = useState<Array<{ song_id: number; song_name: string }>>([]);
  const [rows, setRows] = useState<SongRankingsResponse["items"]>([]);
  const [totalRanked, setTotalRanked] = useState(0);
  const [loadingRankings, setLoadingRankings] = useState(true);
  const [refreshingRankings, setRefreshingRankings] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const requestVersionRef = useRef(0);
  const filterQuery = useMemo(
    () => sectionFiltersToQuery(filters),
    [filters.difficulty, filters.liveType, filters.includeMeta],
  );
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const pageSize = 50;

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(searchQuery.trim()), 350);
    return () => window.clearTimeout(t);
  }, [searchQuery]);

  useEffect(() => {
    if (!auth.user) return;
    const requestVersion = ++requestVersionRef.current;
    let cancelled = false;
    const hasExistingRows = rows.length > 0;
    setLoadingMore(false);
    setLoadingRankings(!hasExistingRows);
    setRefreshingRankings(hasExistingRows);
    void (async () => {
      try {
        const first = await api.getSongRankings(auth.user!.id, { ...filterQuery, sort_by: sortBy, limit: pageSize, offset: 0, sort_order: sortOrder });
        if (cancelled || requestVersion !== requestVersionRef.current) return;
        setRows(first.items);
        setTotalRanked(first.total);
      } catch {
        if (!cancelled && requestVersion === requestVersionRef.current) {
          setRows([]);
          setTotalRanked(0);
        }
      } finally {
        if (!cancelled && requestVersion === requestVersionRef.current) {
          setLoadingRankings(false);
          setRefreshingRankings(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [auth.user?.id, filterQuery, sortBy, sortOrder]);

  const loadMore = useCallback(async () => {
    if (!auth.user || loadingRankings || refreshingRankings || loadingMore || rows.length >= totalRanked) return;
    const requestVersion = requestVersionRef.current;
    setLoadingMore(true);
    try {
      const next = await api.getSongRankings(auth.user.id, {
        ...filterQuery,
        sort_by: sortBy,
        sort_order: sortOrder,
        limit: pageSize,
        offset: rows.length,
      });
      if (requestVersion !== requestVersionRef.current) return;
      setRows((prev) => [...prev, ...next.items]);
    } catch {
      /* ignore */
    } finally {
      if (requestVersion === requestVersionRef.current) {
        setLoadingMore(false);
      }
    }
  }, [auth.user, filterQuery, loadingMore, loadingRankings, refreshingRankings, rows.length, sortBy, sortOrder, totalRanked]);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const obs = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting) void loadMore();
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, [loadMore]);

  useEffect(() => {
    if (!auth.user || !debouncedSearch) {
      setResults([]);
      return;
    }
    let cancelled = false;
    void api
      .searchSongs(auth.user.id, debouncedSearch, auth.user.server)
      .then((response) => {
        if (!cancelled) setResults(response.results);
      })
      .catch(() => {
        if (!cancelled) setResults([]);
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedSearch, auth.user]);

  if (!auth.user) return null;

  function toggleSort(key: SongRankingSortKey) {
    const nextSortBy = key;
    const nextSortOrder: SortOrder = sortBy === key ? (sortOrder === "asc" ? "desc" : "asc") : "desc";
    setSortBy(nextSortBy);
    setSortOrder(nextSortOrder);
    setRows((current) => sortSongRankingRows(current, nextSortBy, nextSortOrder));
  }

  return (
    <div className="page-grid">
      <Card title="Song controls">
        <div className="analytics-section-controls">
          <div className="analytics-filter-row">
            <label className="field song-search-field">
              <span>Song search</span>
              <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search song names" />
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
        <SongRankingsTable
          items={rows}
          sortBy={sortBy}
          sortOrder={sortOrder}
          onSort={toggleSort}
          total={totalRanked}
          server={auth.user.server}
          initialLoading={loadingRankings}
          refreshing={refreshingRankings}
        />
        <div ref={sentinelRef} style={{ height: 1 }} />
        {loadingMore && <LoadingInline />}
      </Card>
    </div>
  );
}

function RecapAnalyticsView() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const readScope = (value: string | null): RecapScope => {
    if (value === "weekly" || value === "monthly" || value === "yearly" || value === "event") return value;
    return "monthly";
  };
  const [scope, setScope] = useState<RecapScope>(() => readScope(searchParams.get("scope")));
  const [anchorDate, setAnchorDate] = useState(() => new Date());
  const [selectedEventId, setSelectedEventId] = useState("");
  const [eventSearch, setEventSearch] = useState("");
  const [filters, setFilters] = useState<SectionFilterState>({ difficulty: "", liveType: "", includeMeta: false });
  const events = useLoadable(auth.user ? () => api.getReferenceEvents(1200) : null, [auth.user?.id]);
  const filterQuery = sectionFiltersToQuery(filters);

  useEffect(() => {
    setScope(readScope(searchParams.get("scope")));
  }, [searchParams]);

  const recapGeneral = useLoadable<RecapResponse>(
    auth.user && scope !== "event"
      ? () => api.getRecap(auth.user!.id, scope, undefined, anchorDate.toISOString().slice(0, 10), filterQuery)
      : null,
    [auth.user?.id, scope, anchorDate.getTime(), filters.difficulty, filters.liveType, filters.includeMeta],
  );

  const recapEvent = useLoadable<RecapResponse>(
    auth.user && scope === "event" && Boolean(selectedEventId)
      ? () => api.getRecap(auth.user!.id, "event", Number(selectedEventId), undefined, filterQuery)
      : null,
    [auth.user?.id, scope, selectedEventId, filters.difficulty, filters.liveType, filters.includeMeta],
  );

  const eventStats = useLoadable<EventStatsResponse>(
    auth.user && scope === "event" && Boolean(selectedEventId)
      ? () => api.getEventStats(auth.user!.id, Number(selectedEventId), filterQuery)
      : null,
    [auth.user?.id, scope, selectedEventId, filters.difficulty, filters.liveType, filters.includeMeta],
  );

  useEffect(() => {
    if (scope === "event") {
      const fd = recapEvent.data?.from_date ?? eventStats.data?.from_date;
      if (fd) setAnchorDate(new Date(`${fd}T00:00:00`));
    }
  }, [scope, recapEvent.data?.from_date, eventStats.data?.from_date]);

  if (!auth.user) return null;
  const server = auth.user.server;
  const recentEvents = ((events.data?.items || []) as Array<Record<string, unknown>>)
    .slice()
    .filter((event) => Number.isFinite(Number(event.event_id || event.id)) && Number(event.event_id || event.id) > 0)
    .sort((a, b) => Number(b.event_id || b.id || 0) - Number(a.event_id || a.id || 0));
  const q = eventSearch.trim().toLowerCase();
  const filteredEvents = q
    ? recentEvents.filter((event) => formatEventLabelDateOnly(event, server).toLowerCase().includes(q))
    : recentEvents;

  function updateScope(next: RecapScope) {
    setScope(next);
    const p = new URLSearchParams(searchParams);
    p.set("view", "recap");
    p.set("scope", next);
    setSearchParams(p, { replace: true });
  }

  const calendarLink =
    scope === "event" && selectedEventId
      ? `/stats?view=calendar&eventId=${encodeURIComponent(selectedEventId)}&calMode=event`
      : "/stats?view=calendar";

  return (
    <div className="page-grid">
      <Card
        title="Recap controls"
        subtitle="Scope and filters for recap summaries. Open the Calendar tab for the play explorer."
        actions={
          scope === "event" && !selectedEventId ? (
            <button className="button primary" type="button" disabled>
              Open calendar
            </button>
          ) : (
            <Link className="button primary" to={calendarLink}>
              Open calendar
            </Link>
          )
        }
      >
        <div className="analytics-control-rail">
          <div className="analytics-control-rail__cluster">
            <label className="field inline-field">
              <span>Scope</span>
              <select
                value={scope}
                onChange={(event) => {
                  updateScope(event.target.value as RecapScope);
                }}
              >
                {(["weekly", "monthly", "yearly", "event"] as const).map((value) => (
                  <option key={value} value={value}>
                    {formatDifficulty(value)}
                  </option>
                ))}
              </select>
            </label>
            {scope === "event" ? (
              <>
                <label className="field">
                  <span>Search events</span>
                  <input value={eventSearch} onChange={(e) => setEventSearch(e.target.value)} placeholder="Filter by name or date" />
                </label>
                <label className="field">
                  <span>Event</span>
                  <select value={selectedEventId} onChange={(event) => setSelectedEventId(event.target.value)}>
                    <option value="">Select event</option>
                    {filteredEvents.slice(0, 200).map((event) => (
                      <option key={String(event.event_id || event.id)} value={String(event.event_id || event.id)}>
                        {formatEventLabelDateOnly(event, server)}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : (
              <div className="button-row tight analytics-month-nav">
                <button
                  className="button ghost"
                  type="button"
                  onClick={() => setAnchorDate((prev) => stepRecapAnchor(scope, prev, -1))}
                >
                  Prev
                </button>
                <div className="toolbar-chip">{recapNavLabel(scope, anchorDate, server)}</div>
                <button
                  className="button ghost"
                  type="button"
                  onClick={() => setAnchorDate((prev) => stepRecapAnchor(scope, prev, 1))}
                >
                  Next
                </button>
              </div>
            )}
          </div>
          <div className="analytics-control-rail__cluster analytics-control-rail__cluster--end">
            <SectionFilterControls filters={filters} onChange={setFilters} />
          </div>
        </div>
      </Card>
      <Card title="Recap">
        {scope === "event" && !selectedEventId ? (
          <EmptyState text="Pick an event to build an event recap." />
        ) : scope === "event" ? (
          eventStats.loading || recapEvent.loading ? (
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
            <EventFocusPanel stats={eventStats.data} recap={recapEvent.data} />
          ) : (
            <EmptyState text="No event data returned for this selection." />
          )
        ) : recapGeneral.data ? (
          <RecapPanel
            data={recapGeneral.data}
            server={server}
            scope={scope}
            onOpenCalendarDay={(date) => {
              navigate(`/stats?view=calendar&calDay=${encodeURIComponent(date)}&calMode=day`);
            }}
          />
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
            <ScreenshotGallery items={screenshots.data.items} server={auth.user.server} userId={auth.user.id} />
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
  const server = auth.user.server;

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
          <Card
            title="Song calendar"
            subtitle="Browse plays for this song in the Calendar tab."
            actions={
              <Link className="button primary" to={`/stats?view=calendar&songId=${songIdNumber}`}>
                Open calendar
              </Link>
            }
          >
            <div className="inline-meta">The Calendar tab loads the same explorer, scoped to this song via the URL.</div>
          </Card>
          <div className="layout-two">
            <Card title="Milestone captures">
              {data.data.detail ? (
                <MilestoneGallery
                  server={server}
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
          <Card title="Journey timeline" subtitle="Vertical progression through the song's milestone screenshots and events.">
            {journey.data ? <TimelinePanel items={journey.data.timeline} server={server} /> : <LoadingInline />}
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
  server,
  userId,
}: {
  items: RecentPlayOverview[];
  server: User["server"];
  userId: number;
}) {
  const [active, setActive] = useState<number | null>(null);
  const prewarmIds = useMemo(() => {
    const ids: number[] = [];
    for (const item of items) {
      const u = item.image_url;
      if (!u) continue;
      const m = u.match(/\/screenshots\/(\d+)\/image(?:\?|$)/);
      if (!m) continue;
      const n = Number(m[1]);
      if (Number.isFinite(n) && n > 0) ids.push(n);
    }
    return ids;
  }, [items]);
  useThumbnailPrewarm(userId, prewarmIds);

  if (!items.length) return <EmptyState text="No recent plays found." />;
  const visibleItems = items.slice(0, 5);
  const modalItems: ScreenshotModalItem[] = visibleItems.map((item) => ({
    song_id: item.song_id,
    song_name: item.song_name,
    difficulty: item.difficulty,
    live_type: item.live_type ?? "",
    timestamp: item.timestamp ?? null,
    filename: item.filename ?? null,
    image_url: item.image_url ?? null,
    image_available: Boolean(item.image_url),
    score: item.score ?? 0,
    accuracy: item.accuracy ?? 0,
    perfect: item.perfect,
    great: item.great,
    good: item.good,
    bad: item.bad,
    miss: item.miss,
    fast: item.fast,
    slow: item.slow,
    max_combo: item.max_combo,
    level: item.level ?? undefined,
    full_combo: Boolean(item.full_combo),
    all_perfect: Boolean(item.all_perfect),
    anomaly: Boolean(item.anomaly),
  }));
  const locale = webLocale(server);
  const formatCount = (value: number | undefined) => (typeof value === "number" && Number.isFinite(value) ? value.toLocaleString(locale) : "0");
  const formatAccuracyValue = (value: number | undefined) =>
    typeof value === "number" && Number.isFinite(value) ? `${value}%` : "No accuracy";

  return (
    <>
      <div className="recent-lives-list">
        {visibleItems.map((item, index) => (
          <button type="button" key={`${item.song_id}-${item.timestamp || index}`} className="recent-live-row" onClick={() => setActive(index)}>
            <div className="recent-live-row__thumb">
              {item.image_url ? (
                <SecureImage path={item.image_url} alt={item.filename || `play-${index}`} className="recent-live-row__image" variant="thumb" />
              ) : (
                <div className="gallery-placeholder recent-live-row__image">No image</div>
              )}
            </div>
            <div className="recent-live-row__main">
              <div className="recent-live-row__title-block">
                <strong>{item.song_name || `Song ${item.song_id}`}</strong>
                <div className="recent-live-row__meta">
                  <span>{formatDifficulty(item.difficulty)}</span>
                  {item.live_type ? <span>{formatLiveType(item.live_type)}</span> : null}
                </div>
              </div>
              <div className="recent-live-row__stats-line">
                <span>P {formatCount(item.perfect)}</span>
                <span>Gr {formatCount(item.great)}</span>
                <span>Go {formatCount(item.good)}</span>
                <span>B {formatCount(item.bad)}</span>
                <span>M {formatCount(item.miss)}</span>
                <span>Fast {formatCount(item.fast)}</span>
                <span>Slow {formatCount(item.slow)}</span>
              </div>
            </div>
            <div className="recent-live-row__aside">
              <div className="recent-live-row__badges">
                <div className="badge-row">
                  {item.full_combo ? <span className="badge fc">FC</span> : null}
                  {item.all_perfect ? <span className="badge ap">AP</span> : null}
                  {item.anomaly ? <span className="badge warn">Anomaly</span> : null}
                </div>
              </div>
              <div className="recent-live-row__summary">
                <strong>{formatAccuracyValue(item.accuracy)}</strong>
                <span>Max combo {formatCount(item.max_combo)}</span>
              </div>
              <div className="recent-live-row__timestamp">{formatDateTime(item.timestamp, server)}</div>
            </div>
          </button>
        ))}
      </div>
      {active != null && (
        <ScreenshotModal items={modalItems} index={active} server={server} onClose={() => setActive(null)} onIndexChange={setActive} />
      )}
    </>
  );
}

function SongRankingsTable({
  items,
  sortBy,
  sortOrder,
  onSort,
  total,
  server,
  initialLoading,
  refreshing,
}: {
  items: SongRankingsResponse["items"];
  sortBy: SongRankingSortKey;
  sortOrder: SortOrder;
  onSort: (key: SongRankingSortKey) => void;
  total: number;
  server: User["server"];
  initialLoading?: boolean;
  refreshing?: boolean;
}) {
  if (initialLoading && !items.length) return <LoadingCard label="Loading ranked songs..." />;
  if (!items.length) return <EmptyState text="No ranked songs found for the current filters." />;
  return (
    <div className={`table-wrap song-rankings-table-wrap${refreshing ? " is-refreshing" : ""}`}>
      <table className="data-table">
        <colgroup>
          <col className="song-rankings-col song-rankings-col--song" />
          <col className="song-rankings-col song-rankings-col--metric" />
          <col className="song-rankings-col song-rankings-col--metric" />
          <col className="song-rankings-col song-rankings-col--metric" />
          <col className="song-rankings-col song-rankings-col--metric" />
          <col className="song-rankings-col song-rankings-col--latest" />
        </colgroup>
        <thead>
          <tr>
            <th className="song-rankings-cell song-rankings-cell--song">Song</th>
            <th className="song-rankings-cell song-rankings-cell--metric">
              <button type="button" className="th-sort" onClick={() => onSort("play_count")}>
                <span className="th-sort__label">Plays</span>
                <span className="th-sort__arrow">{sortBy === "play_count" ? (sortOrder === "asc" ? "▲" : "▼") : ""}</span>
              </button>
            </th>
            <th className="song-rankings-cell song-rankings-cell--metric">
              <button type="button" className="th-sort" onClick={() => onSort("fc_count")}>
                <span className="th-sort__label">FC</span>
                <span className="th-sort__arrow">{sortBy === "fc_count" ? (sortOrder === "asc" ? "▲" : "▼") : ""}</span>
              </button>
            </th>
            <th className="song-rankings-cell song-rankings-cell--metric">
              <button type="button" className="th-sort" onClick={() => onSort("ap_count")}>
                <span className="th-sort__label">AP</span>
                <span className="th-sort__arrow">{sortBy === "ap_count" ? (sortOrder === "asc" ? "▲" : "▼") : ""}</span>
              </button>
            </th>
            <th className="song-rankings-cell song-rankings-cell--metric">
              <button type="button" className="th-sort" onClick={() => onSort("skill_score")}>
                <span className="th-sort__label">Skill</span>
                <span className="th-sort__arrow">{sortBy === "skill_score" ? (sortOrder === "asc" ? "▲" : "▼") : ""}</span>
              </button>
            </th>
            <th className="song-rankings-cell song-rankings-cell--latest">Latest</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.song_id}>
              <td className="song-rankings-cell song-rankings-cell--song">
                <Link to={`/stats/song/${item.song_id}`} className="song-rankings-link">
                  {item.song_name || `Song #${item.song_id}`}
                </Link>
              </td>
              <td className="song-rankings-cell song-rankings-cell--metric">{item.play_count}</td>
              <td className="song-rankings-cell song-rankings-cell--metric">{item.fc_count}</td>
              <td className="song-rankings-cell song-rankings-cell--metric">{item.ap_count}</td>
              <td className="song-rankings-cell song-rankings-cell--metric">{item.skill_score}</td>
              <td className="song-rankings-cell song-rankings-cell--latest">{formatShortDate(item.latest_play?.timestamp, server)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="inline-meta">Loaded {items.length} of {total}</div>
      {refreshing ? <div className="inline-meta">Refreshing rankings...</div> : null}
    </div>
  );
}

function RecapPanel({
  data,
  server,
  scope,
  onOpenCalendarDay,
}: {
  data: RecapResponse;
  server: User["server"];
  scope: RecapScope;
  onOpenCalendarDay: (date: string) => void;
}) {
  const digest = data.daily_digest ?? [];
  const maxPlays = Math.max(1, ...digest.map((d) => d.plays));
  const showDailyTable = scope === "weekly" || scope === "event";
  const showHeatStrip = scope === "monthly" || scope === "yearly";
  const [hlIndex, setHlIndex] = useState<number | null>(null);
  const hlItems: ScreenshotModalItem[] = useMemo(
    () =>
      data.highlights
        .filter((h) => h.screenshot?.image_url)
        .map((h) => ({
          song_name: h.value,
          difficulty: "",
          live_type: "",
          timestamp: h.screenshot?.timestamp ?? null,
          filename: h.screenshot?.filename ?? null,
          image_url: h.screenshot?.image_url ?? null,
          image_available: true,
          accuracy: 0,
          score: 0,
          full_combo: false,
          all_perfect: false,
          anomaly: false,
        })),
    [data.highlights],
  );

  return (
    <div className="stack">
      <div className="inline-meta">{formatDateRange(data.from_date, data.to_date, server)}</div>
      <div className="stats-grid compact">
        <MetricCard label="Scope" value={data.title} />
        <MetricCard label="Total plays" value={data.summary.total_plays ?? 0} />
        <MetricCard label="Skill score" value={data.skill_score} />
        <MetricCard label="Delta" value={data.skill_score_delta} />
      </div>
      {showDailyTable && digest.length > 0 && (
        <div className="stack">
          <div className="subheading">Daily plays</div>
          <div className="table-wrap">
            <table className="data-table recap-daily-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Plays</th>
                  <th>FC</th>
                  <th>AP</th>
                </tr>
              </thead>
              <tbody>
                {digest.map((row) => (
                  <tr key={row.date}>
                    <td>{formatShortDate(row.date, server)}</td>
                    <td>{row.plays}</td>
                    <td>{row.fc}</td>
                    <td>{row.ap}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {showHeatStrip && digest.length > 0 && (
        <div className="stack">
          <div className="subheading">Activity heatmap (click opens Calendar tab)</div>
          <div className="recap-heatmap-mini">
            {digest.map((row) => {
              const intensity = row.plays / maxPlays;
              const alpha = 0.15 + intensity * 0.85;
              return (
                <button
                  key={row.date}
                  type="button"
                  className="recap-heatmap-mini__cell"
                  title={`${row.date}: ${row.plays} plays`}
                  style={{ background: `rgba(124, 92, 255, ${alpha})` }}
                  onClick={() => onOpenCalendarDay(row.date)}
                />
              );
            })}
          </div>
        </div>
      )}
      <div className="card-grid recap-grid">
        {data.highlights.map((item, idx) => (
          <button
            type="button"
            className="highlight-card interactive"
            key={item.title}
            onClick={() => {
              if (!item.screenshot?.image_url) return;
              const i = data.highlights.filter((h) => h.screenshot?.image_url).findIndex((h) => h.title === item.title);
              setHlIndex(i >= 0 ? i : null);
            }}
          >
            <span className="brand-kicker">{item.title}</span>
            <strong>{item.value}</strong>
            <p>{item.detail}</p>
            {item.screenshot?.image_url && (
              <SecureImage path={item.screenshot.image_url} alt={item.screenshot.filename || item.title} className="highlight-image" variant="thumb" />
            )}
          </button>
        ))}
      </div>
      {hlIndex != null && hlItems.length > 0 && (
        <ScreenshotModal
          items={hlItems}
          index={hlIndex}
          server={server}
          onClose={() => setHlIndex(null)}
          onIndexChange={setHlIndex}
        />
      )}
      <div className="layout-two">
        <div>
          <div className="subheading">Top songs</div>
          <BarChart items={data.top_songs.map((item) => ({ label: item.song_name || `#${item.song_id}`, value: item.play_count }))} />
        </div>
        <div>
          <div className="subheading">Live types</div>
          <BarChart items={Object.entries(data.live_types).map(([label, value]) => ({ label: formatLiveType(label), value }))} />
        </div>
      </div>
      <div>
        <div className="subheading">Active hours</div>
        <BarChart items={groupActiveHours(data.active_hours)} />
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
        <MetricCard label="FC gains" value={data.fc_gains} />
        <MetricCard label="AP gains" value={data.ap_gains} />
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
                {item.screenshot?.image_url && (
                  <SecureImage path={item.screenshot.image_url} alt={item.screenshot.filename || item.title} className="highlight-image" variant="thumb" />
                )}
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
  server,
}: {
  items: MilestonesResponse["milestones"];
  server: User["server"];
}) {
  if (!items.length) return <EmptyState text="No milestones yet." />;
  return (
    <div className="timeline milestone-timeline">
      {items.map((item, index) => (
        <div key={`${item.type}-${item.play_count}-${index}`} className="timeline-item">
          <div className="timeline-marker" />
          <div className="timeline-content milestone-row">
            {item.meta?.image_url ? (
              <SecureImage path={item.meta.image_url} alt={item.label} className="thumb-image" variant="thumb" />
            ) : (
              <div className="gallery-placeholder thumb-image">No image</div>
            )}
            <div className="stack">
              <strong>{item.label}</strong>
              <div className="inline-meta">Play #{item.play_count}</div>
              <div className="inline-meta">{formatDateTime(item.meta?.timestamp, server)}</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function MilestoneGallery({
  items,
  server,
}: {
  items: Array<{ label: string; meta: { timestamp?: string | null; filename?: string | null; image_url?: string | null } }>;
  server: User["server"];
}) {
  if (!items.length) return <EmptyState text="No milestone images available." />;
  return (
    <div className="gallery milestone-gallery">
      {items.map((item) => (
        <div className="gallery-card" key={item.label}>
          {item.meta.image_url ? (
            <SecureImage path={item.meta.image_url} alt={item.meta.filename || item.label} className="gallery-image" variant="thumb" />
          ) : (
            <div className="gallery-placeholder">No image</div>
          )}
          <div className="gallery-meta">
            <strong>{item.label}</strong>
            <span>{item.meta.timestamp ? formatDateTime(item.meta.timestamp, server) : "Unknown date"}</span>
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
      ]}
    />
  );
}

function TimelinePanel({
  items,
  server,
}: {
  items: Array<{ type: string; label: string; timestamp?: string | null; filename?: string | null; image_url?: string | null; details: Record<string, unknown> }>;
  server: User["server"];
}) {
  const [active, setActive] = useState(0);
  const [modalOpen, setModalOpen] = useState(false);
  if (!items.length) return <EmptyState text="No timeline items found." />;
  const modalItems: ScreenshotModalItem[] = items.map((item) => ({
    song_name: item.label,
    difficulty: "",
    live_type: "",
    timestamp: item.timestamp ?? null,
    filename: item.filename ?? null,
    image_url: item.image_url ?? null,
    image_available: Boolean(item.image_url),
    accuracy: typeof item.details?.accuracy === "number" ? (item.details.accuracy as number) : 0,
    score: 0,
    full_combo: false,
    all_perfect: false,
    anomaly: false,
  }));
  return (
    <>
      <div className="timeline journey-timeline">
        {items.map((item, index) => (
          <button
            type="button"
            key={`${item.type}-${item.timestamp || index}`}
            className={active === index ? "timeline-item journey-timeline__item active" : "timeline-item journey-timeline__item"}
            onClick={() => {
              setActive(index);
              if (item.image_url) setModalOpen(true);
            }}
          >
            <div className="timeline-marker" />
            <div className="timeline-content journey-timeline__content">
              <div className="journey-timeline__head">
                <div>
                  <div className="brand-kicker">{item.type.replace(/_/g, " ")}</div>
                  <strong>{item.label}</strong>
                </div>
                <div className="inline-meta">{item.timestamp ? formatDateTime(item.timestamp, server) : "No timestamp"}</div>
              </div>
              {Object.entries(item.details).length > 0 ? (
                <div className="inline-meta">
                  {Object.entries(item.details)
                    .filter(([, value]) => value != null && value !== "")
                    .map(([key, value]) => {
                      const label = key.replace(/_/g, " ");
                      const display = typeof value === "number" && key === "accuracy" ? `${value}%` : String(value);
                      return `${label}: ${display}`;
                    })
                    .join(" · ")}
                </div>
              ) : null}
              {item.image_url ? <SecureImage path={item.image_url} alt={item.filename || item.label} className="journey-timeline__image" variant="thumb" /> : null}
            </div>
          </button>
        ))}
      </div>
      {modalOpen && modalItems[active]?.image_url ? (
        <ScreenshotModal items={modalItems} index={active} server={server} onClose={() => setModalOpen(false)} onIndexChange={setActive} />
      ) : null}
    </>
  );
}

function CodeBlock({ value }: { value: unknown }) {
  return <pre className="code-block">{JSON.stringify(value, null, 2)}</pre>;
}

function scanResultSummary(result: ScanResult, prefix: string) {
  return `${prefix}: ${result.total_scanned} scanned, ${result.successful} successful, ${result.persisted} persisted, ${result.skipped_duplicates} duplicates.`;
}

export default App;
