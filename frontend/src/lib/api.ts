// FinSight AI — API client (axios) with JWT auth and automatic token refresh
import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 120000, // training / reports / first live-data fetches can take a while
});

// ── Token storage ────────────────────────────────────────────────────────────
export const tokens = {
  get access() {
    return typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  },
  get refresh() {
    return typeof window !== "undefined" ? localStorage.getItem("refresh_token") : null;
  },
  set(access: string, refresh: string) {
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
  },
  clear() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  },
};

api.interceptors.request.use((config) => {
  const token = tokens.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// One refresh request shared by all requests that failed with 401 at the same time
let refreshPromise: Promise<string> | null = null;

function redirectToLogin() {
  tokens.clear();
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `/login?next=${next}`;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const isAuthCall = original?.url?.startsWith("/auth/");
    if (error.response?.status !== 401 || !original || original._retry || isAuthCall) {
      return Promise.reject(error);
    }
    const refresh = tokens.refresh;
    if (!refresh) {
      redirectToLogin();
      return Promise.reject(error);
    }
    original._retry = true;
    try {
      refreshPromise ??= axios
        .post(`${API_URL}/api/v1/auth/refresh`, { refresh_token: refresh })
        .then(({ data }) => {
          tokens.set(data.access_token, data.refresh_token);
          return data.access_token as string;
        })
        .finally(() => {
          refreshPromise = null;
        });
      const newToken = await refreshPromise;
      original.headers.Authorization = `Bearer ${newToken}`;
      return api.request(original);
    } catch (e) {
      redirectToLogin();
      return Promise.reject(e);
    }
  }
);

/** Human-readable message from an API error (FastAPI `detail` strings or validation arrays). */
export function apiError(error: unknown, fallback = "Something went wrong"): string {
  const err = error as AxiosError<any>;
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d: any) => d.msg?.replace(/^Value error, /, "") ?? String(d)).join("; ");
  }
  if (err?.code === "ERR_NETWORK") return "Cannot reach the backend — is it running on " + API_URL + "?";
  if (err?.code === "ECONNABORTED") return "The request timed out. Please try again.";
  return fallback;
}

// ── Endpoint helpers ─────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) => api.post("/auth/login", { email, password }),
  register: (data: { email: string; password: string; full_name?: string }) => api.post("/auth/register", data),
  me: () => api.get("/auth/me"),
  updateMe: (data: any) => api.patch("/auth/me", data),
  getPreferences: () => api.get("/auth/me/preferences"),
  updatePreferences: (data: any) => api.put("/auth/me/preferences", data),
  changePassword: (current_password: string, new_password: string) =>
    api.post("/auth/change-password", { current_password, new_password }),
  forgotPassword: (email: string) => api.post("/auth/forgot-password", { email }),
  resetPassword: (token: string, new_password: string) => api.post("/auth/reset-password", { token, new_password }),
  logout: () => api.post("/auth/logout"),
};

export const systemApi = {
  status: () => api.get("/system/status"),
};

export const stocksApi = {
  search: (q: string) => api.get("/stocks/search", { params: { q } }),
  getDetail: (symbol: string) => api.get(`/stocks/${encodeURIComponent(symbol)}`),
  getHistory: (symbol: string, period: string, interval = "1d", indicators = false) =>
    api.get(`/stocks/${encodeURIComponent(symbol)}/history`, { params: { period, interval, indicators } }),
  getFundamentals: (symbol: string) => api.get(`/stocks/${encodeURIComponent(symbol)}/fundamentals`),
  getTechnical: (symbol: string) => api.get(`/stocks/${encodeURIComponent(symbol)}/technical`),
  getMarketOverview: () => api.get("/stocks/market/overview"),
  quotes: (symbols: string[]) => api.get("/stocks/quotes", { params: { symbols: symbols.join(",") } }),
  compare: (symbols: string[], period = "1y") => api.get("/stocks/compare", { params: { symbols: symbols.join(","), period } }),
};

export const portfolioApi = {
  list: () => api.get("/portfolios"),
  create: (data: { name: string; description?: string; currency?: string }) => api.post("/portfolios", data),
  update: (id: string, data: any) => api.patch(`/portfolios/${id}`, data),
  delete: (id: string) => api.delete(`/portfolios/${id}`),
  addTransaction: (id: string, data: any) => api.post(`/portfolios/${id}/transactions`, data),
  listTransactions: (id: string) => api.get(`/portfolios/${id}/transactions`),
  deleteTransaction: (id: string, txId: string) => api.delete(`/portfolios/${id}/transactions/${txId}`),
  getHoldings: (id: string) => api.get(`/portfolios/${id}/holdings`),
  getAnalytics: (id: string) => api.get(`/portfolios/${id}/analytics`),
};

export const watchlistApi = {
  list: () => api.get("/watchlists"),
  create: (name: string) => api.post("/watchlists", { name }),
  rename: (id: string, name: string) => api.patch(`/watchlists/${id}`, { name }),
  delete: (id: string) => api.delete(`/watchlists/${id}`),
  addSymbol: (id: string, symbol: string) => api.post(`/watchlists/${id}/symbols`, { symbol }),
  removeSymbol: (id: string, symbol: string) => api.delete(`/watchlists/${id}/symbols/${encodeURIComponent(symbol)}`),
  quotes: (id: string) => api.get(`/watchlists/${id}/quotes`),
};

export const predictionsApi = {
  train: (data: { symbol: string; model_types?: string[]; lookback_years?: number }) => api.post("/predictions/train", data),
  status: (symbol: string) => api.get(`/predictions/${encodeURIComponent(symbol)}/status`),
  getPredictions: (symbol: string) => api.get(`/predictions/${encodeURIComponent(symbol)}`),
  getEvaluation: (symbol: string) => api.get(`/predictions/${encodeURIComponent(symbol)}/evaluation`),
  trained: () => api.get("/predictions/trained"),
};

export const newsApi = {
  getMarket: (limit = 20, category?: string) => api.get("/news", { params: { limit, category } }),
  getStock: (symbol: string, days = 14, limit = 20) => api.get(`/news/${encodeURIComponent(symbol)}`, { params: { days, limit } }),
  getSentiment: (symbol: string, days = 30) => api.get(`/news/${encodeURIComponent(symbol)}/sentiment`, { params: { days } }),
  analyze: (text: string) => api.post("/news/sentiment/analyze", { text }),
  model: () => api.get("/news/sentiment/model"),
};

export const aiApi = {
  status: () => api.get("/ai/status"),
  models: () => api.get("/ai/models"),
  selectModel: (data: { provider?: string; ollama_model?: string }) => api.put("/ai/models", data),
  chat: (message: string, sessionId?: string | null) => api.post("/ai/chat", { message, session_id: sessionId || undefined }),
  getSessions: () => api.get("/ai/sessions"),
  getSession: (id: string) => api.get(`/ai/sessions/${id}`),
  deleteSession: (id: string) => api.delete(`/ai/sessions/${id}`),
  generateReport: (data: { symbol: string; include_predictions?: boolean; include_sentiment?: boolean }) =>
    api.post("/ai/generate-report", data),
};

export const optimizationApi = {
  efficientFrontier: (data: any) => api.post("/optimization/efficient-frontier", data),
  maxSharpe: (data: any) => api.post("/optimization/max-sharpe", data),
  minVolatility: (data: any) => api.post("/optimization/min-volatility", data),
};

export const alertsApi = {
  list: () => api.get("/alerts"),
  create: (data: { symbol: string; alert_type: string; target_value: number }) => api.post("/alerts", data),
  delete: (id: string) => api.delete(`/alerts/${id}`),
  checkNow: () => api.post("/alerts/check"),
};

export const notificationsApi = {
  list: () => api.get("/notifications"),
  markRead: (id: string) => api.post(`/notifications/${id}/read`),
  markAllRead: () => api.post("/notifications/read-all"),
  delete: (id: string) => api.delete(`/notifications/${id}`),
};

export const reportsApi = {
  list: () => api.get("/reports"),
  get: (id: string) => api.get(`/reports/${id}`),
  delete: (id: string) => api.delete(`/reports/${id}`),
  /** Download the PDF with the auth header (a plain link would not be authenticated). */
  async downloadPdf(id: string, filename: string) {
    const res = await api.get(`/reports/${id}/export`, { responseType: "blob" });
    const url = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
