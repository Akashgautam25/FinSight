// API client configuration
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

// Attach JWT token from localStorage
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Auto-refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      const refreshToken = localStorage.getItem("refresh_token");
      if (refreshToken) {
        try {
          const { data } = await axios.post(`${API_URL}/api/v1/auth/refresh`, {
            refresh_token: refreshToken,
          });
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem("refresh_token", data.refresh_token);
          error.config.headers.Authorization = `Bearer ${data.access_token}`;
          return api.request(error.config);
        } catch {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/login";
        }
      } else {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// API helpers
export const stocksApi = {
  search: (q: string) => api.get(`/stocks/search?q=${encodeURIComponent(q)}`),
  getDetail: (symbol: string) => api.get(`/stocks/${symbol}`),
  getHistory: (symbol: string, period: string, interval: string = "1d") =>
    api.get(`/stocks/${symbol}/history?period=${period}&interval=${interval}`),
  getFundamentals: (symbol: string) => api.get(`/stocks/${symbol}/fundamentals`),
  getTechnical: (symbol: string) => api.get(`/stocks/${symbol}/technical`),
  getMarketOverview: () => api.get("/stocks/market/overview"),
  compare: (symbols: string[], period: string = "1y") =>
    api.get(`/stocks/compare?symbols=${symbols.join(",")}&period=${period}`),
};

export const portfolioApi = {
  list: () => api.get("/portfolios"),
  create: (data: any) => api.post("/portfolios", data),
  get: (id: string) => api.get(`/portfolios/${id}`),
  delete: (id: string) => api.delete(`/portfolios/${id}`),
  addTransaction: (id: string, data: any) => api.post(`/portfolios/${id}/transactions`, data),
  getHoldings: (id: string) => api.get(`/portfolios/${id}/holdings`),
  getAnalytics: (id: string) => api.get(`/portfolios/${id}/analytics`),
};

export const predictionsApi = {
  train: (data: any) => api.post("/predictions/train", data),
  getPredictions: (symbol: string) => api.get(`/predictions/${symbol}`),
  getEvaluation: (symbol: string) => api.get(`/predictions/${symbol}/evaluation`),
};

export const newsApi = {
  getMarket: (limit?: number) => api.get(`/news?limit=${limit || 20}`),
  getStock: (symbol: string, days?: number) => api.get(`/news/${symbol}?days=${days || 7}`),
  getSentiment: (symbol: string) => api.get(`/news/${symbol}/sentiment`),
};

export const aiApi = {
  chat: (message: string, sessionId?: string) =>
    api.post("/ai/chat", { message, session_id: sessionId }),
  getSessions: () => api.get("/ai/sessions"),
  getSession: (id: string) => api.get(`/ai/sessions/${id}`),
  generateReport: (data: any) => api.post("/ai/generate-report", data),
};

export const optimizationApi = {
  efficientFrontier: (data: any) => api.post("/optimization/efficient-frontier", data),
  maxSharpe: (data: any) => api.post("/optimization/max-sharpe", data),
  minVolatility: (data: any) => api.post("/optimization/min-volatility", data),
};

export const alertsApi = {
  list: () => api.get("/alerts"),
  create: (data: any) => api.post("/alerts", data),
  delete: (id: string) => api.delete(`/alerts/${id}`),
};

export const reportsApi = {
  list: () => api.get("/reports"),
  get: (id: string) => api.get(`/reports/${id}`),
  export: (id: string) => api.get(`/reports/${id}/export`, { responseType: "blob" }),
};
