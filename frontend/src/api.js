// Client de l'API Django (contrat validé en équipe, voir README / Swagger).
// Les réponses du backend (GeoJSON, champs du contrat) sont converties ici
// dans le format qu'utilise App.jsx, pour ne pas toucher aux composants.
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
  localStorage.removeItem("gp_username");
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
    if (response.status === 401) clearTokens();
    throw new Error(data.detail || JSON.stringify(data) || "Erreur serveur");
  }
  return data;
}

// --- Conversions backend -> format attendu par App.jsx ----------------------

// Arbre /domaines/ : "enfants" -> domaines2 / domaines3
function toDomaines(tree) {
  return tree.map((d1) => ({
    code: d1.code,
    libelle: d1.libelle,
    domaines2: (d1.enfants || []).map((d2) => ({
      code: d2.code,
      libelle: d2.libelle,
      domaines3: d2.enfants || [],
    })),
  }));
}

// /villes/ : {nom, codepostal, id_dept} -> {ville, codepostal, total}
// (le compteur affiché entre parenthèses devient le code postal)
function toVilles(list) {
  return list.map((v) => ({ ville: v.nom, codepostal: v.codepostal, total: v.codepostal }));
}

// Feature GeoJSON d'équipement -> objet plat {id, lat, lon, ...}
function toEquipement(f) {
  const [lon, lat] = f.geometry.coordinates;
  return { ...f.properties, lat, lon };
}

// Feature GeoJSON d'implantation -> objet plat utilisé par App.jsx
function toImplantation(f) {
  const p = f.properties;
  return {
    id: p.id,
    titre: p.titre,
    domaine3: p.domaine3_code,
    domaine3_libelle: p.domaine3_libelle,
    annotations: p.annotations,
    commentaires: p.commentaire,
    latitude: f.geometry.coordinates[1],
    longitude: f.geometry.coordinates[0],
  };
}

// Formulaire App.jsx -> corps attendu par /implantations/
function toImplantationPayload(form) {
  const body = {
    titre: form.titre,
    domaine3_code: form.domaine3 || null,
    annotations: form.annotations || "",
    commentaire: form.commentaires || "",
  };
  if (form.lat !== undefined && form.lat !== "") body.lat = parseFloat(form.lat);
  if (form.lon !== undefined && form.lon !== "") body.lon = parseFloat(form.lon);
  return body;
}

export const api = {
  register: ({ username, password }) =>
    request("/auth/register/", { method: "POST", body: JSON.stringify({ username, password }) }),

  login: async ({ username, password }) => {
    const tokens = await request("/auth/login/", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    localStorage.setItem("gp_username", username);
    return tokens;
  },

  // Pas de route /me/ dans l'API : le nom est mémorisé à la connexion
  me: async () => {
    const username = localStorage.getItem("gp_username");
    if (!getToken() || !username) throw new Error("Non connecté");
    return { username };
  },

  getReferentiels: async () => {
    const [domaines, villes] = await Promise.all([request("/domaines/"), request("/villes/")]);
    return { domaines: toDomaines(domaines), villes: toVilles(villes) };
  },

  // GET /equipements/?bbox=&domaines=&villes= (domaines des 3 niveaux mélangés)
  getEquipements: async ({ bbox, domaines = [], villes = [] }) => {
    const qs = new URLSearchParams();
    if (bbox) qs.set("bbox", bbox);
    if (domaines.length) qs.set("domaines", domaines.join(","));
    if (villes.length) qs.set("villes", villes.join(","));
    const fc = await request(`/equipements/?${qs.toString()}`);
    return fc.features.map(toEquipement);
  },

  getEquipement: (id) => request(`/equipements/${id}/`),

  getImplantations: async () => {
    const fc = await request("/implantations/");
    return fc.features.map(toImplantation);
  },
  createImplantation: async (form) =>
    toImplantation(
      await request("/implantations/", { method: "POST", body: JSON.stringify(toImplantationPayload(form)) })
    ),
  updateImplantation: async (id, form) =>
    toImplantation(
      await request(`/implantations/${id}/`, { method: "PATCH", body: JSON.stringify(toImplantationPayload(form)) })
    ),
  deleteImplantation: (id) => request(`/implantations/${id}/`, { method: "DELETE" }),
};
