const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export function getToken() {
  return localStorage.getItem("gp_access_token");
}

export function setTokens(access, refresh) {
  localStorage.setItem("gp_access_token", access);
  if (refresh) localStorage.setItem("gp_refresh_token", refresh);
}

export function clearTokens() {
  localStorage.removeItem("gp_access_token");
  localStorage.removeItem("gp_refresh_token");
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 204) return null;

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || JSON.stringify(data) || "Erreur serveur");
  }
  return data;
}

export const api = {
  register: (payload) =>
    request("/auth/register/", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload) =>
    request("/auth/login/", { method: "POST", body: JSON.stringify(payload) }),
  me: () => request("/auth/me/"),
  getReferentiels: () => request("/referentiels/"),
  getBPE: (params) => {
    const qs = new URLSearchParams();
    if (params.bbox) qs.set("bbox", params.bbox);
    if (params.domaine1?.length) qs.set("domaine1", params.domaine1.join(","));
    if (params.domaine2?.length) qs.set("domaine2", params.domaine2.join(","));
    if (params.domaine3?.length) qs.set("domaine3", params.domaine3.join(","));
    if (params.villes?.length) qs.set("villes", params.villes.join(","));
    if (params.excludeIds?.length) qs.set("exclude_ids", params.excludeIds.join(","));
    return request(`/bpe/?${qs.toString()}`);
  },
  getImplantations: () => request("/implantations/"),
  createImplantation: (payload) =>
    request("/implantations/", { method: "POST", body: JSON.stringify(payload) }),
  updateImplantation: (id, payload) =>
    request(`/implantations/${id}/`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteImplantation: (id) =>
    request(`/implantations/${id}/`, { method: "DELETE" }),
};