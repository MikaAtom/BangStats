export type User = {
  id: number;
  game_id: string;
  username: string;
  role: "user" | "admin";
  server: "en" | "jp" | "tw" | "cn" | "kr";
  screenshots_source: "local" | "server_folder";
  screenshots_path: string;
  server_folder_authorized: boolean;
  sync_command?: string | null;
  excluded_song_ids?: number[];
};

export type AuthResponse = {
  token: string;
  user: User;
};

export type Counts = {
  songs: number;
  events: number;
  bands: number;
};

export type SyncJob = {
  id: number;
  server: string;
  status: string;
  requested_by_user_id?: number | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  songs?: number | null;
  events?: number | null;
  bands?: number | null;
  error_message?: string | null;
};

export type ScanJob = {
  id: number;
  user_id: number;
  status: string;
  source_type: string;
  folder_path?: string | null;
  cancelled: boolean;
  total_files: number;
  processed: number;
  successful: number;
  validated: number;
  persisted: number;
  failed_to_persist: number;
  skipped_duplicates: number;
  errors: Record<string, number>;
  error_files: Record<string, string[]>;
  parallel_workers?: number | null;
  keys_per_worker?: number | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
};

export type ScanResult = {
  total_scanned: number;
  successful: number;
  errors: Record<string, number>;
  error_files: Record<string, string[]>;
  validated: number;
  persisted: number;
  failed_to_persist: number;
  skipped_duplicates: number;
  additional: Record<string, unknown>;
};

export type UploadUsage = {
  file_count: number;
  total_size_mb: number;
  oldest_file_age_days: number;
};

export type FilenameDiffResponse = {
  user_id: number;
  total_requested: number;
  already_scanned_count: number;
  to_scan_count: number;
  already_scanned_filenames: string[];
  to_scan_filenames: string[];
};

export type UploadFileItem = {
  filename: string;
  size_bytes: number;
  modified_at: string;
  image_url: string;
};

export type UploadFileList = {
  total: number;
  items: UploadFileItem[];
};

export type ErrorList = {
  total: number;
  errors: Record<string, number>;
  error_files: Record<string, string[]>;
};

export type ErrorDetail = {
  error_type: string;
  json_filename: string;
  image_filename: string;
  scan_data: Record<string, unknown>;
  validation?: Record<string, unknown> | null;
};

export type ErrorCorrectionResponse = {
  image_filename: string;
  is_valid: boolean;
  error_type?: string | null;
  persisted: boolean;
  skipped_duplicates: boolean;
  failed_to_persist: boolean;
  saved_as_anomaly?: boolean;
};

export type DeleteErrorEntryResponse = {
  deleted: boolean;
  removed_db_rows: number;
  image_filename?: string | null;
};

export type ReferenceSongItem = {
  id: number;
  internal_song_id: number;
  tag: string;
  name: Record<string, string>;
  note_counts: Record<string, number | number[]>;
  special?: Record<string, unknown> | null;
  levels?: Record<string, number[]>;
  band_id?: number;
};

export type ErrorCategoryActionResponse = {
  total_files: number;
  processed: number;
  successful: number;
  persisted: number;
  skipped_duplicates: number;
  failed_to_persist: number;
  missing_image: number;
  scan_failed: number;
  errors: Record<string, number>;
};

export type StatsOverview = {
  summary: Record<string, number>;
  top_songs: Array<{ song_id: number; song_name?: string | null; play_count: number }>;
  recent: Array<{ song_id: number; song_name?: string | null; difficulty: string; timestamp?: string | null; filename?: string | null; live_type?: string | null; image_url?: string | null }>;
  exclusion_context: {
    server_meta_song_ids: number[];
    user_excluded_song_ids: number[];
    effective_song_ids: number[];
    is_active: boolean;
  };
};

export type SongSearchResponse = {
  query: string;
  limit: number;
  results: Array<{ song_id: number; song_name: string }>;
};

export type SongStatsResponse = {
  song_id: number;
  requested_difficulty?: string | null;
  difficulty_overview: Array<{
    difficulty: string;
    total_plays: number;
    first_played?: { timestamp?: string | null; filename?: string | null; image_url?: string | null } | null;
    estimated_time_played_seconds: number;
    estimated_time_played_human: string;
  }>;
  detail?: {
    total_plays: number;
    total_fc: number;
    total_ap: number;
    accuracy: number;
    total_sessions: number;
    avg_plays_per_session: number;
    longest_session_minutes: number;
    longest_session_plays: number;
    plays_before_fc?: number | null;
    plays_before_ap?: number | null;
    estimated_time_played_human: string;
    skill_score: number;
    first_played?: { timestamp?: string | null; filename?: string | null; image_url?: string | null } | null;
    first_fc?: { timestamp?: string | null; filename?: string | null; image_url?: string | null } | null;
    first_ap?: { timestamp?: string | null; filename?: string | null; image_url?: string | null } | null;
  } | null;
  exclusion_context: {
    server_meta_song_ids: number[];
    user_excluded_song_ids: number[];
    effective_song_ids: number[];
    is_active: boolean;
  };
};

export type MilestonesResponse = {
  milestones: Array<{
    type: string;
    label: string;
    play_count: number;
    meta?: { timestamp?: string | null; filename?: string | null; image_url?: string | null } | null;
  }>;
  best_streak_days: number;
  current_streak_days: number;
};

export type StatsRangeQuery = {
  preset?: string;
  from_date?: string;
  to_date?: string;
};

export type AnalyticsFilterQuery = StatsRangeQuery & {
  difficulty?: string;
  live_type?: string;
  include_meta?: boolean;
};

export type ActivityResponse = {
  from_date: string;
  to_date: string;
  days: number;
  summary: Record<string, number>;
  active_days: number;
  avg_plays_per_day: number;
  range_streak_days: number;
  delta_vs_previous: {
    plays_delta: number;
    plays_delta_pct: number;
    accuracy_delta: number;
  };
};

export type CalendarResponse = {
  year: number;
  month: number;
  total_days_with_plays: number;
  days: Array<{
    date: string;
    plays: number;
    fc: number;
    ap: number;
    accuracy: number;
    difficulties: Record<string, number>;
  }>;
};

export type InsightsResponse = {
  from_date: string;
  to_date: string;
  session_gap_minutes: number;
  data_quality: {
    observed_plays: number;
    min_recommended_plays: number;
    sparse_data: boolean;
  };
  sessions: {
    total_sessions: number;
    avg_session_minutes: number;
    avg_plays_per_session: number;
    longest_session_minutes: number;
    longest_session_plays: number;
    recent_cadence_days: number;
  };
  recent_sessions: Array<{
    started_at?: string | null;
    ended_at?: string | null;
    plays: number;
    unique_songs: number;
    duration_minutes: number;
  }>;
  practice_periods: Array<{
    song_id: number;
    song_name?: string | null;
    total_plays: number;
    burst_count: number;
    max_burst_plays: number;
    latest_burst_at?: string | null;
    estimated_time_played_human: string;
  }>;
  repetition: {
    total_plays: number;
    repeated_plays: number;
    repeated_ratio: number;
    most_looped_songs: Array<{
      song_id: number;
      song_name?: string | null;
      play_count: number;
      repeated_plays: number;
      repeat_ratio: number;
      estimated_time_played_human: string;
    }>;
  };
  recommendations: Array<{
    title: string;
    detail: string;
    song_id?: number | null;
    song_name?: string | null;
  }>;
};

export type ProgressionResponse = {
  scope: string;
  points: Array<{
    label: string;
    from_date: string;
    to_date: string;
    plays: number;
    accuracy: number;
    skill_score: number;
    fc: number;
    ap: number;
  }>;
  delta_skill_score: number;
  delta_accuracy: number;
  exclusion_context: {
    server_meta_song_ids: number[];
    user_excluded_song_ids: number[];
    effective_song_ids: number[];
    is_active: boolean;
  };
};

export type EventStatsResponse = {
  event_id: number;
  event_name?: string | null;
  event_type?: string | null;
  from_date: string;
  to_date: string;
  summary: Record<string, number>;
  live_types: Record<string, number>;
  active_hours: Record<string, number>;
  top_songs: Array<{
    song_id: number;
    song_name?: string | null;
    play_count: number;
    fc_count: number;
    ap_count: number;
    skill_score: number;
  }>;
  total_sessions: number;
  longest_session_minutes: number;
  fc_gains: number;
  ap_gains: number;
  skill_score: number;
  exclusion_context: {
    server_meta_song_ids: number[];
    user_excluded_song_ids: number[];
    effective_song_ids: number[];
    is_active: boolean;
  };
};

export type SongJourneyResponse = {
  song_id: number;
  song_name?: string | null;
  difficulty: string;
  total_plays: number;
  first_played?: { timestamp?: string | null; filename?: string | null; image_url?: string | null } | null;
  first_fc?: { timestamp?: string | null; filename?: string | null; image_url?: string | null } | null;
  first_ap?: { timestamp?: string | null; filename?: string | null; image_url?: string | null } | null;
  plays_before_fc?: number | null;
  plays_before_ap?: number | null;
  skill_score: number;
  practice_periods: Array<Record<string, unknown>>;
  timeline: Array<{
    type: string;
    label: string;
    timestamp?: string | null;
    filename?: string | null;
    image_url?: string | null;
    details: Record<string, unknown>;
  }>;
  exclusion_context: {
    server_meta_song_ids: number[];
    user_excluded_song_ids: number[];
    effective_song_ids: number[];
    is_active: boolean;
  };
};

export type RecapResponse = {
  scope: string;
  title: string;
  from_date: string;
  to_date: string;
  event_id?: number | null;
  event_name?: string | null;
  summary: Record<string, number>;
  skill_score: number;
  skill_score_delta: number;
  top_songs: Array<{
    song_id: number;
    song_name?: string | null;
    play_count: number;
    fc_count: number;
    ap_count: number;
    skill_score: number;
    latest_play?: { timestamp?: string | null; filename?: string | null; image_url?: string | null } | null;
  }>;
  new_songs: Array<{
    song_id: number;
    song_name?: string | null;
    play_count: number;
    fc_count: number;
    ap_count: number;
    skill_score: number;
    latest_play?: { timestamp?: string | null; filename?: string | null; image_url?: string | null } | null;
  }>;
  most_practiced: Array<{
    song_id: number;
    song_name?: string | null;
    play_count: number;
    fc_count: number;
    ap_count: number;
    skill_score: number;
    latest_play?: { timestamp?: string | null; filename?: string | null; image_url?: string | null } | null;
  }>;
  live_types: Record<string, number>;
  active_hours: Record<string, number>;
  highlights: Array<{
    title: string;
    value: string;
    detail: string;
    screenshot?: { timestamp?: string | null; filename?: string | null; image_url?: string | null } | null;
  }>;
  streaks: Record<string, number>;
  sessions: Record<string, number>;
  exclusion_context: {
    server_meta_song_ids: number[];
    user_excluded_song_ids: number[];
    effective_song_ids: number[];
    is_active: boolean;
  };
};

export type SongRankingsResponse = {
  sort_by: string;
  difficulty?: string | null;
  live_type?: string | null;
  items: Array<{
    song_id: number;
    song_name?: string | null;
    play_count: number;
    fc_count: number;
    ap_count: number;
    skill_score: number;
    latest_play?: { timestamp?: string | null; filename?: string | null; image_url?: string | null } | null;
  }>;
  exclusion_context: {
    server_meta_song_ids: number[];
    user_excluded_song_ids: number[];
    effective_song_ids: number[];
    is_active: boolean;
  };
};

export type MetaSongConfigResponse = {
  server_meta_song_ids: number[];
  user_excluded_song_ids: number[];
  effective_song_ids: number[];
};

export type UserDataExportResponse = {
  exported_at: string;
  user: Record<string, unknown>;
  screenshots: Array<Record<string, unknown>>;
  screenshot_references: Array<{ filename?: string | null; path?: string | null; image_available: boolean }>;
  meta_song_config: MetaSongConfigResponse;
  stats_summary: Record<string, unknown>;
};

export type UserDataImportResponse = {
  restored_screenshots: number;
  skipped_screenshots: number;
  unresolved_screenshot_references: string[];
  updated_user_settings: string[];
};

export type ReferenceChunkResponse = {
  max_id: number;
  items: Array<Record<string, unknown>>;
};

export type ScreenshotItem = {
  id: number;
  filename?: string | null;
  song_id: number;
  song_name?: string | null;
  difficulty: string;
  live_type: string;
  score: number;
  accuracy: number;
  full_combo: boolean;
  all_perfect: boolean;
  anomaly: boolean;
  timestamp: string;
  image_available: boolean;
  image_url?: string | null;
};

export type ScreenshotListResponse = {
  total: number;
  limit: number;
  offset: number;
  items: ScreenshotItem[];
};

export type DashboardResponse = {
  user: User;
  counts: Counts;
  current_event?: Record<string, unknown> | null;
  current_event_status: string;
  runtime: {
    db_path: string;
    env: string;
    legacy_db_path: string;
    legacy_db_exists: boolean;
    server: string;
  };
  upload_usage: UploadUsage;
  stats?: Record<string, number> | null;
  scan_jobs: ScanJob[];
  sync_jobs: SyncJob[];
  scan_errors: ErrorList;
  recent_screenshots: ScreenshotItem[];
};

function appendRangeQuery(params: URLSearchParams, range?: StatsRangeQuery) {
  if (!range) return;
  if (range.preset) params.set("preset", range.preset);
  if (range.from_date) params.set("from_date", range.from_date);
  if (range.to_date) params.set("to_date", range.to_date);
}

function appendAnalyticsFilters(params: URLSearchParams, filters?: AnalyticsFilterQuery) {
  appendRangeQuery(params, filters);
  if (!filters) return;
  if (filters.difficulty) params.set("difficulty", filters.difficulty);
  if (filters.live_type) params.set("live_type", filters.live_type);
  if (typeof filters.include_meta === "boolean") params.set("include_meta", String(filters.include_meta));
}

type UnauthorizedHandler = () => void;

class ApiClient {
  private token: string | null = null;
  private unauthorizedHandler: UnauthorizedHandler | null = null;
  private readonly cacheTtlMs = 2 * 60 * 1000;
  private readonly maxBlobConcurrency = 4;
  private readonly jsonCache = new Map<string, { expiresAt: number; value: unknown }>();
  private readonly inFlightJson = new Map<string, Promise<unknown>>();
  private readonly blobCache = new Map<string, { expiresAt: number; value: Blob }>();
  private readonly inFlightBlob = new Map<string, Promise<Blob>>();
  private activeBlobRequests = 0;
  private readonly blobQueue: Array<() => void> = [];

  private buildCacheKey(path: string, method: string) {
    return `${method}::${path}::${this.token || "anon"}`;
  }

  private isCacheableGetPath(path: string) {
    const volatilePrefixes = [
      "/api/scans/jobs",
      "/api/sync/jobs",
    ];
    return !volatilePrefixes.some((prefix) => path.startsWith(prefix));
  }

  private clearCaches() {
    this.jsonCache.clear();
    this.blobCache.clear();
  }

  private async acquireBlobSlot() {
    if (this.activeBlobRequests < this.maxBlobConcurrency) {
      this.activeBlobRequests += 1;
      return;
    }
    await new Promise<void>((resolve) => {
      this.blobQueue.push(() => {
        this.activeBlobRequests += 1;
        resolve();
      });
    });
  }

  private releaseBlobSlot() {
    this.activeBlobRequests = Math.max(0, this.activeBlobRequests - 1);
    const next = this.blobQueue.shift();
    if (next) next();
  }

  setToken(token: string | null) {
    if (this.token !== token) {
      this.clearCaches();
    }
    this.token = token;
  }

  setUnauthorizedHandler(handler: UnauthorizedHandler) {
    this.unauthorizedHandler = handler;
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const method = (init.method || "GET").toUpperCase();
    const isGet = method === "GET";
    const useGetCache = isGet && this.isCacheableGetPath(path);
    const cacheKey = this.buildCacheKey(path, method);

    if (useGetCache) {
      const cached = this.jsonCache.get(cacheKey);
      if (cached && cached.expiresAt > Date.now()) {
        return cached.value as T;
      }
      this.jsonCache.delete(cacheKey);

      const pending = this.inFlightJson.get(cacheKey);
      if (pending) {
        return (await pending) as T;
      }
    }

    const execute = async (): Promise<T> => {
    const headers = new Headers(init.headers);
    if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (this.token) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }
    const requestInit: RequestInit = useGetCache
      ? { ...init, headers }
      : { ...init, headers, cache: "no-store" };
    const response = await fetch(path, requestInit);
    if (response.status === 401 && this.unauthorizedHandler) {
      this.unauthorizedHandler();
    }
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const raw = await response.text();
        if (raw) {
          try {
            const payload = JSON.parse(raw) as { detail?: string };
            detail = payload.detail || raw || detail;
          } catch {
            detail = raw;
          }
        }
      } catch {
        detail = response.statusText;
      }
      throw new Error(detail || "Request failed");
    }
    if (response.status === 204) {
      return undefined as T;
    }
      const payload = (await response.json()) as T;
      if (useGetCache) {
        this.jsonCache.set(cacheKey, {
          expiresAt: Date.now() + this.cacheTtlMs,
          value: payload,
        });
      } else {
        this.clearCaches();
      }
      return payload;
    };

    if (!useGetCache) {
      return execute();
    }

    const inFlight = execute();
    this.inFlightJson.set(cacheKey, inFlight as Promise<unknown>);
    try {
      return await inFlight;
    } finally {
      this.inFlightJson.delete(cacheKey);
    }
  }

  async secureBlob(path: string) {
    const method = "GET";
    const cacheKey = this.buildCacheKey(path, method);
    const cached = this.blobCache.get(cacheKey);
    if (cached && cached.expiresAt > Date.now()) {
      return cached.value;
    }
    this.blobCache.delete(cacheKey);

    const pending = this.inFlightBlob.get(cacheKey);
    if (pending) {
      return await pending;
    }

    const execute = async () => {
    await this.acquireBlobSlot();
    try {
    const headers = new Headers();
    if (this.token) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }
    const response = await fetch(path, { headers });
    if (!response.ok) {
      throw new Error("Image request failed");
    }
      const blob = await response.blob();
      this.blobCache.set(cacheKey, {
        expiresAt: Date.now() + this.cacheTtlMs,
        value: blob,
      });
      return blob;
    } finally {
      this.releaseBlobSlot();
    }
    };

    const inFlight = execute();
    this.inFlightBlob.set(cacheKey, inFlight);
    try {
      return await inFlight;
    } finally {
      this.inFlightBlob.delete(cacheKey);
    }
  }

  login(username: string, password: string) {
    return this.request<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  }

  register(payload: { username: string; password: string; game_id: string; server: User["server"] }) {
    return this.request<AuthResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  legacyPasswordSetup(payload: { username: string; game_id: string; password: string }) {
    return this.request<AuthResponse>("/api/auth/legacy-password-setup", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  legacyLogin(payload: { username: string; game_id: string }) {
    return this.request<AuthResponse>("/api/auth/legacy-login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  logout() {
    return this.request("/api/auth/logout", { method: "POST" });
  }

  getUser(userId: number) {
    return this.request<User>(`/api/users/${userId}`);
  }

  updateUser(userId: number, payload: Partial<User>) {
    return this.request<User>(`/api/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  getDashboard(userId: number) {
    return this.request<DashboardResponse>(`/api/users/${userId}/dashboard`);
  }

  getCounts() {
    return this.request<Counts>("/api/db/counts");
  }

  getCurrentEvent(server: User["server"]) {
    return this.request<Record<string, unknown> | null>(`/api/events/current?server=${server}`);
  }

  listUploads(userId: number) {
    return this.request<UploadFileList>(`/api/users/${userId}/uploads`);
  }

  uploadFiles(userId: number, files: File[]) {
    const form = new FormData();
    form.append("user_id", String(userId));
    files.forEach((file) => form.append("files", file));
    return this.request<{ uploaded_files: number; total_uploaded_for_user: number; total_storage_mb_for_user: number }>(
      "/api/scans/upload",
      {
        method: "POST",
        body: form,
      },
    );
  }

  getUploadUsage(userId: number) {
    return this.request<UploadUsage>(`/api/scans/upload-usage?user_id=${userId}`);
  }

  createScanJob(payload: {
    user_id: number;
    source_type: "upload" | "server_folder";
    folder_path?: string;
    filenames?: string[];
    parallel_workers?: number;
    keys_per_worker?: number;
  }) {
    return this.request<ScanJob>("/api/scans/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listScanJobs(limit = 50) {
    return this.request<{ jobs: ScanJob[] }>(`/api/scans/jobs?limit=${limit}`);
  }

  getScanJob(jobId: number) {
    return this.request<ScanJob>(`/api/scans/jobs/${jobId}`);
  }

  cancelScanJob(jobId: number) {
    return this.request<ScanJob>(`/api/scans/jobs/${jobId}/cancel`, { method: "POST" });
  }

  getScanCapabilities() {
    return this.request<{ provider: string; available_google_keys: number }>("/api/scans/capabilities");
  }

  authorizeServerFolder(master_key: string) {
    return this.request<{ authorized: boolean }>("/api/scans/authorize-server-folder", {
      method: "POST",
      body: JSON.stringify({ master_key }),
    });
  }

  checkLocalPath(folder_path: string, user_id: number) {
    return this.request<{ is_local: boolean; canonical_path?: string | null }>("/api/scans/check-local-path", {
      method: "POST",
      body: JSON.stringify({ folder_path, user_id }),
    });
  }

  getScanFilenameDiff(user_id: number, filenames: string[]) {
    return this.request<FilenameDiffResponse>("/api/scans/filename-diff", {
      method: "POST",
      body: JSON.stringify({ user_id, filenames }),
    });
  }

  importJsonFolder(user_id: number, folder_path: string, persist_to_db = true) {
    return this.request<ScanResult>("/api/scans/import-json-folder", {
      method: "POST",
      body: JSON.stringify({ user_id, folder_path, persist_to_db }),
    });
  }

  listErrors() {
    return this.request<ErrorList>("/api/scans/errors");
  }

  getErrorDetail(errorType: string, jsonFilename: string) {
    return this.request<ErrorDetail>(`/api/scans/errors/${encodeURIComponent(errorType)}/${encodeURIComponent(jsonFilename)}`);
  }

  correctError(errorType: string, jsonFilename: string, payload: { user_id: number; corrected_scan_data: Record<string, unknown>; persist_to_db: boolean; anomaly?: boolean }) {
    return this.request<ErrorCorrectionResponse>(
      `/api/scans/errors/${encodeURIComponent(errorType)}/${encodeURIComponent(jsonFilename)}/correct`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }

  deleteError(errorType: string, jsonFilename: string, payload: { user_id: number }) {
    return this.request<DeleteErrorEntryResponse>(
      `/api/scans/errors/${encodeURIComponent(errorType)}/${encodeURIComponent(jsonFilename)}`,
      {
        method: "DELETE",
        body: JSON.stringify(payload),
      },
    );
  }

  revalidateErrorCategory(errorType: string, payload: { user_id: number; persist_to_db: boolean; progress_every: number }) {
    return this.request<ErrorCategoryActionResponse>(`/api/scans/errors/${encodeURIComponent(errorType)}/revalidate`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  rescanErrorCategory(errorType: string, payload: { user_id: number; persist_to_db: boolean; progress_every: number; model?: string }) {
    return this.request<ErrorCategoryActionResponse>(`/api/scans/errors/${encodeURIComponent(errorType)}/rescan`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  getStats(userId: number, filters: AnalyticsFilterQuery = {}) {
    const query = new URLSearchParams();
    appendAnalyticsFilters(query, filters);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return this.request<StatsOverview>(`/api/users/${userId}/stats${suffix}`);
  }

  searchSongs(userId: number, q: string, server: User["server"]) {
    return this.request<SongSearchResponse>(
      `/api/users/${userId}/stats/songs/search?q=${encodeURIComponent(q)}&server=${server}`,
    );
  }

  getReferenceSongs(sinceId = 0, limit = 5000) {
    return this.request<{ max_id: number; items: ReferenceSongItem[] }>(`/api/reference/songs?since_id=${sinceId}&limit=${limit}`);
  }

  getSongStats(userId: number, songId: number, difficulty?: string) {
    const query = difficulty ? `?difficulty=${encodeURIComponent(difficulty)}` : "";
    return this.request<SongStatsResponse>(`/api/users/${userId}/stats/songs/${songId}${query}`);
  }

  getSongRankings(userId: number, params: { sort_by?: string; limit?: number } & AnalyticsFilterQuery = {}) {
    const query = new URLSearchParams();
    appendAnalyticsFilters(query, params);
    if (params.sort_by) query.set("sort_by", params.sort_by);
    if (params.limit) query.set("limit", String(params.limit));
    return this.request<SongRankingsResponse>(`/api/users/${userId}/stats/songs/rankings?${query.toString()}`);
  }

  getMilestones(userId: number, filters: AnalyticsFilterQuery = {}) {
    const query = new URLSearchParams();
    appendAnalyticsFilters(query, filters);
    return this.request<MilestonesResponse>(`/api/users/${userId}/stats/milestones?${query.toString()}`);
  }

  getActivity(userId: number, filters: AnalyticsFilterQuery = { preset: "30d" }) {
    const query = new URLSearchParams();
    appendAnalyticsFilters(query, filters);
    return this.request<ActivityResponse>(`/api/users/${userId}/stats/activity?${query.toString()}`);
  }

  getCalendar(userId: number, year: number, month: number, filters: AnalyticsFilterQuery = {}) {
    const query = new URLSearchParams({ year: String(year), month: String(month) });
    appendAnalyticsFilters(query, filters);
    return this.request<CalendarResponse>(`/api/users/${userId}/stats/calendar?${query.toString()}`);
  }

  getInsights(userId: number, filters: AnalyticsFilterQuery = { preset: "30d" }) {
    const query = new URLSearchParams();
    appendAnalyticsFilters(query, filters);
    return this.request<InsightsResponse>(`/api/users/${userId}/stats/insights?${query.toString()}`);
  }

  getProgression(userId: number, scope = "monthly", count = 6, anchorDate?: string, filters: AnalyticsFilterQuery = {}) {
    const query = new URLSearchParams({ scope, count: String(count) });
    if (anchorDate) query.set("anchor_date", anchorDate);
    appendAnalyticsFilters(query, filters);
    return this.request<ProgressionResponse>(`/api/users/${userId}/stats/progression?${query.toString()}`);
  }

  getEventStats(userId: number, eventId: number, filters: AnalyticsFilterQuery = {}) {
    const query = new URLSearchParams();
    appendAnalyticsFilters(query, filters);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return this.request<EventStatsResponse>(`/api/users/${userId}/stats/event-focus/${eventId}${suffix}`);
  }

  getSongJourney(userId: number, songId: number, difficulty?: string) {
    const query = difficulty ? `?difficulty=${encodeURIComponent(difficulty)}` : "";
    return this.request<SongJourneyResponse>(`/api/users/${userId}/stats/songs/${songId}/journey${query}`);
  }

  getRecap(userId: number, scope = "monthly", eventId?: number, anchorDate?: string, filters: AnalyticsFilterQuery = {}) {
    const query = new URLSearchParams({ scope });
    if (eventId) query.set("event_id", String(eventId));
    if (anchorDate) query.set("anchor_date", anchorDate);
    appendAnalyticsFilters(query, filters);
    return this.request<RecapResponse>(`/api/users/${userId}/stats/recap?${query.toString()}`);
  }

  getMetaSongConfig(userId: number) {
    return this.request<MetaSongConfigResponse>(`/api/users/${userId}/meta-song-config`);
  }

  exportUserData(userId: number) {
    return this.request<UserDataExportResponse>(`/api/users/${userId}/export`);
  }

  importUserData(userId: number, payload: Record<string, unknown>) {
    return this.request<UserDataImportResponse>(`/api/users/${userId}/import`, {
      method: "POST",
      body: JSON.stringify({ payload }),
    });
  }

  getReferenceEvents(limit = 5000) {
    return this.request<ReferenceChunkResponse>(`/api/reference/events?limit=${limit}`);
  }

  listScreenshots(
    userId: number,
    params: {
      songId?: number;
      song_query?: string;
      difficulty?: string;
      live_type?: string;
      include_meta?: boolean;
      from_date?: string;
      to_date?: string;
      sort_by?: "timestamp" | "song_name" | "score" | "accuracy";
      sort_order?: "asc" | "desc";
      limit?: number;
      offset?: number;
    } = {},
  ) {
    const query = new URLSearchParams();
    if (params.songId) query.set("song_id", String(params.songId));
    if (params.song_query) query.set("song_query", params.song_query);
    if (params.difficulty) query.set("difficulty", params.difficulty);
    if (params.live_type) query.set("live_type", params.live_type);
    if (typeof params.include_meta === "boolean") query.set("include_meta", String(params.include_meta));
    if (params.from_date) query.set("from_date", params.from_date);
    if (params.to_date) query.set("to_date", params.to_date);
    if (params.sort_by) query.set("sort_by", params.sort_by);
    if (params.sort_order) query.set("sort_order", params.sort_order);
    if (params.limit) query.set("limit", String(params.limit));
    if (params.offset) query.set("offset", String(params.offset));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return this.request<ScreenshotListResponse>(`/api/users/${userId}/screenshots${suffix}`);
  }

  listSyncJobs(limit = 20) {
    return this.request<{ jobs: SyncJob[] }>(`/api/sync/jobs?limit=${limit}`);
  }

  createSyncJob(server: User["server"], requestedByUserId: number) {
    return this.request<SyncJob>("/api/sync/jobs", {
      method: "POST",
      body: JSON.stringify({ server, requested_by_user_id: requestedByUserId }),
    });
  }

  health() {
    return this.request<{ status: string; mode: string; db_path: string; env: string; legacy_db_path: string; legacy_db_exists: boolean }>("/api/health");
  }

  flush(payload: { remote_cache: boolean; scan_cache: boolean; db: boolean }) {
    return this.request<{ backup_root: string; moved: string[]; skipped: string[] }>("/api/admin/flush", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
}

export const api = new ApiClient();
