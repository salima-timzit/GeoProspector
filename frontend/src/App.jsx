import React, { useEffect, useRef, useState, useCallback } from "react";
import { MapContainer, TileLayer, Marker, CircleMarker, Popup, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { api, setTokens, clearTokens, getToken } from "./api";

// Chargement par tuiles : la carte est découpée en carrés de TILE degrés.
// Seuls les carrés visibles et pas encore chargés sont demandés à l'API.
const TILE = 0.1;
const MIN_ZOOM = 12; // en dessous, trop d'équipements : on ne charge rien

function tilesFor(view) {
  const tiles = [];
  for (let x = Math.floor(view.west / TILE); x <= Math.floor(view.east / TILE); x++) {
    for (let y = Math.floor(view.south / TILE); y <= Math.floor(view.north / TILE); y++) {
      tiles.push({ key: `${x}:${y}`, bbox: [x * TILE, y * TILE, (x + 1) * TILE, (y + 1) * TILE].map((v) => v.toFixed(4)).join(",") });
    }
  }
  return tiles;
}

const DOMAINE_COLORS = { A: "#2563eb", B: "#dc2626", C: "#7c3aed", D: "#059669", E: "#0891b2", F: "#d97706", G: "#db2777" };

const prospectIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-orange.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
});

function MapWatcher({ onBoundsChange, addMode, onMapClick }) {
  const timerRef = useRef(null);

  const map = useMapEvents({
    moveend: () => {
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        const b = map.getBounds();
        onBoundsChange({ west: b.getWest(), south: b.getSouth(), east: b.getEast(), north: b.getNorth(), zoom: map.getZoom() });
      }, 300);
    },
    click: (e) => {
      if (addMode) {
        onMapClick({ lat: e.latlng.lat, lon: e.latlng.lng });
      }
    },
  });

  useEffect(() => {
    const b = map.getBounds();
    onBoundsChange({ west: b.getWest(), south: b.getSouth(), east: b.getEast(), north: b.getNorth(), zoom: map.getZoom() });
  }, [map, onBoundsChange]);

  return null;
}

export default function App() {
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({ username: "", email: "", password: "" });
  const [authError, setAuthError] = useState("");

  const [referentiels, setReferentiels] = useState({ domaines: [], villes: [] });
  const [selectedD1, setSelectedD1] = useState([]);
  const [selectedD2, setSelectedD2] = useState([]);
  const [selectedD3, setSelectedD3] = useState([]);
  const [selectedVilles, setSelectedVilles] = useState([]);
  const [villeSearch, setVilleSearch] = useState("");

  const [view, setView] = useState(null);
  const [bpeMap, setBpeMap] = useState({});
  const loadedTilesRef = useRef(new Set());
  const generationRef = useRef(0);
  const [pending, setPending] = useState(0);
  const loadingBpe = pending > 0;
  const [details, setDetails] = useState({});

  const [implantations, setImplantations] = useState([]);
  const [addMode, setAddMode] = useState(false);
  const [editingImplantation, setEditingImplantation] = useState(null);
  const [impForm, setImpForm] = useState({
    titre: "",
    domaine3: "",
    annotations: "",
    commentaires: "",
    lat: "",
    lon: "",
  });

  useEffect(() => {
    api.getReferentiels().then(setReferentiels).catch(console.error);
    if (getToken()) {
      api.me()
        .then((u) => {
          setUser(u);
          return api.getImplantations();
        })
        .then(setImplantations)
        .catch(() => clearTokens());
    }
  }, []);

  const filtersKey = JSON.stringify([selectedD1, selectedD2, selectedD3, selectedVilles]);

  // Réinitialiser le cache local lorsque les filtres changent
  useEffect(() => {
    generationRef.current += 1;
    loadedTilesRef.current = new Set();
    setBpeMap({});
  }, [filtersKey]);

  // Chargement incrémental : uniquement les tuiles visibles pas encore chargées
  useEffect(() => {
    if (!view || view.zoom < MIN_ZOOM) return;
    const generation = generationRef.current;
    const domaines = [...selectedD1, ...selectedD2, ...selectedD3];
    const nouvelles = tilesFor(view).filter((t) => !loadedTilesRef.current.has(t.key));
    for (const tile of nouvelles) {
      loadedTilesRef.current.add(tile.key);
      setPending((n) => n + 1);
      api
        .getEquipements({ bbox: tile.bbox, domaines, villes: selectedVilles })
        .then((items) => {
          if (generation !== generationRef.current || !items.length) return;
          setBpeMap((prev) => {
            const next = { ...prev };
            for (const item of items) next[item.id] = item;
            return next;
          });
        })
        .catch((err) => {
          console.error(err);
          loadedTilesRef.current.delete(tile.key); // sera retentée au prochain déplacement
        })
        .finally(() => setPending((n) => n - 1));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, filtersKey]);

  const loadDetail = (id) => {
    if (details[id]) return;
    api
      .getEquipement(id)
      .then((d) => setDetails((prev) => ({ ...prev, [id]: d })))
      .catch(console.error);
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError("");
    try {
      if (authMode === "register") {
        await api.register(authForm);
      }
      const tokens = await api.login({
        username: authForm.username,
        password: authForm.password,
      });
      setTokens(tokens.access, tokens.refresh);
      const me = await api.me();
      setUser(me);
      const imps = await api.getImplantations();
      setImplantations(imps);
    } catch (err) {
      setAuthError(err.message);
    }
  };

  const handleLogout = () => {
    clearTokens();
    setUser(null);
    setImplantations([]);
    setAddMode(false);
  };

  const toggleItem = (list, setList, value) => {
    setList((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    );
  };

  const handleMapClick = useCallback(({ lat, lon }) => {
    setEditingImplantation(null);
    setImpForm({
      titre: "",
      domaine3: "",
      annotations: "",
      commentaires: "",
      lat: lat.toFixed(6),
      lon: lon.toFixed(6),
    });
    setAddMode(false);
  }, []);

  const handleSaveImplantation = async (e) => {
    e.preventDefault();
    if (!impForm.lat || !impForm.lon || !impForm.titre) return;
    const payload = {
      ...impForm,
      domaine3: impForm.domaine3 || null,
      lat: parseFloat(impForm.lat),
      lon: parseFloat(impForm.lon),
    };
    if (editingImplantation) {
      const updated = await api.updateImplantation(editingImplantation.id, payload);
      setImplantations((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
      setEditingImplantation(null);
    } else {
      const created = await api.createImplantation(payload);
      setImplantations((prev) => [created, ...prev]);
    }
    setImpForm({ titre: "", domaine3: "", annotations: "", commentaires: "", lat: "", lon: "" });
  };

  const handleDeleteImplantation = async (id) => {
    await api.deleteImplantation(id);
    setImplantations((prev) => prev.filter((i) => i.id !== id));
  };

  const startEdit = (imp) => {
    setEditingImplantation(imp);
    setImpForm({
      titre: imp.titre,
      domaine3: imp.domaine3 || "",
      annotations: imp.annotations || "",
      commentaires: imp.commentaires || "",
      lat: imp.latitude,
      lon: imp.longitude,
    });
  };

  const allDomaine3 = referentiels.domaines.flatMap((d1) =>
    d1.domaines2.flatMap((d2) => d2.domaines3)
  );

  const filteredVilles = referentiels.villes.filter((v) =>
    v.ville.toLowerCase().includes(villeSearch.toLowerCase())
  );

  const bpeItems = Object.values(bpeMap);

  return (
    <div className="layout">
      <aside className="sidebar">
        <header className="brand">
          <h1>Geo Prospector</h1>
          <p>Exploration BPE 2025 & Prospection</p>
        </header>

        <section className="card">
          <h2>Espace Prospection</h2>
          {user ? (
            <div>
              <div className="row-between">
                <span>Connecté : <strong>{user.username}</strong></span>
                <button className="btn-secondary" onClick={handleLogout}>Déconnexion</button>
              </div>
              <button
                className={addMode ? "btn-warning full" : "btn-primary full"}
                onClick={() => setAddMode((v) => !v)}
              >
                {addMode ? "Cliquez sur la carte..." : "+ Placer une implantation sur la carte"}
              </button>
            </div>
          ) : (
            <form onSubmit={handleAuthSubmit} className="stack">
              <div className="tabs">
                <button
                  type="button"
                  className={authMode === "login" ? "active" : ""}
                  onClick={() => setAuthMode("login")}
                >
                  Connexion
                </button>
                <button
                  type="button"
                  className={authMode === "register" ? "active" : ""}
                  onClick={() => setAuthMode("register")}
                >
                  Inscription
                </button>
              </div>
              <input
                placeholder="Nom d'utilisateur"
                value={authForm.username}
                onChange={(e) => setAuthForm({ ...authForm, username: e.target.value })}
                required
              />
              {authMode === "register" && (
                <input
                  type="email"
                  placeholder="Email"
                  value={authForm.email}
                  onChange={(e) => setAuthForm({ ...authForm, email: e.target.value })}
                />
              )}
              <input
                type="password"
                placeholder="Mot de passe"
                value={authForm.password}
                onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
                required
              />
              {authError && <p className="error">{authError}</p>}
              <button type="submit" className="btn-primary full">
                {authMode === "login" ? "Se connecter" : "Créer un compte"}
              </button>
            </form>
          )}
        </section>

        {user && (impForm.lat || editingImplantation) && (
          <section className="card highlight">
            <h3>{editingImplantation ? "Modifier l'implantation" : "Nouvelle implantation"}</h3>
            <form onSubmit={handleSaveImplantation} className="stack">
              <input
                placeholder="Titre du projet / local *"
                value={impForm.titre}
                onChange={(e) => setImpForm({ ...impForm, titre: e.target.value })}
                required
              />
              <select
                value={impForm.domaine3}
                onChange={(e) => setImpForm({ ...impForm, domaine3: e.target.value })}
              >
                <option value="">-- Type de commerce BPE envisagé --</option>
                {allDomaine3.map((d3) => (
                  <option key={d3.code} value={d3.code}>
                    {d3.code} — {d3.libelle}
                  </option>
                ))}
              </select>
              <input
                placeholder="Annotations courtes (ex: Angle de rue, forte affluence)"
                value={impForm.annotations}
                onChange={(e) => setImpForm({ ...impForm, annotations: e.target.value })}
              />
              <textarea
                rows="3"
                placeholder="Commentaires détaillés..."
                value={impForm.commentaires}
                onChange={(e) => setImpForm({ ...impForm, commentaires: e.target.value })}
              />
              <div className="grid-2">
                <input
                  placeholder="Latitude"
                  value={impForm.lat}
                  onChange={(e) => setImpForm({ ...impForm, lat: e.target.value })}
                  required
                />
                <input
                  placeholder="Longitude"
                  value={impForm.lon}
                  onChange={(e) => setImpForm({ ...impForm, lon: e.target.value })}
                  required
                />
              </div>
              <div className="row-between">
                <button type="submit" className="btn-primary">Enregistrer</button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    setEditingImplantation(null);
                    setImpForm({ titre: "", domaine3: "", annotations: "", commentaires: "", lat: "", lon: "" });
                  }}
                >
                  Annuler
                </button>
              </div>
            </form>
          </section>
        )}

        {user && (
          <section className="card">
            <h3>Mes implantations ({implantations.length})</h3>
            {implantations.length === 0 ? (
              <p className="muted">Aucun point enregistré.</p>
            ) : (
              <ul className="list">
                {implantations.map((imp) => (
                  <li key={imp.id} className="list-item">
                    <div>
                      <strong>{imp.titre}</strong>
                      {imp.domaine3_libelle && <div className="badge">{imp.domaine3_libelle}</div>}
                      {imp.annotations && <p className="small">{imp.annotations}</p>}
                    </div>
                    <div className="actions">
                      <button className="btn-secondary" onClick={() => startEdit(imp)}>Éditer</button>
                      <button className="btn-danger" onClick={() => handleDeleteImplantation(imp.id)}>Suppr.</button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        <section className="card">
          <div className="row-between">
            <h2>Filtres BPE</h2>
            <button
              className="btn-secondary"
              onClick={() => {
                setSelectedD1([]);
                setSelectedD2([]);
                setSelectedD3([]);
                setSelectedVilles([]);
              }}
            >
              Réinitialiser
            </button>
          </div>
          <p className="muted">
            {view && view.zoom < MIN_ZOOM
              ? "Zoomez pour afficher les équipements."
              : <>Équipements chargés : <strong>{bpeItems.length}</strong></>}
            {loadingBpe ? " (chargement...)" : ""}
          </p>

          <h3>Villes ({selectedVilles.length})</h3>
          <input
            placeholder="Rechercher une ville..."
            value={villeSearch}
            onChange={(e) => setVilleSearch(e.target.value)}
          />
          <div className="scroll-box">
            {filteredVilles.slice(0, 60).map((v) => (
              <label key={`${v.ville}-${v.codepostal}`} className="check">
                <input
                  type="checkbox"
                  checked={selectedVilles.includes(v.ville)}
                  onChange={() => toggleItem(selectedVilles, setSelectedVilles, v.ville)}
                />
                <span>{v.ville} ({v.total})</span>
              </label>
            ))}
          </div>

          <h3>Domaines (3 niveaux)</h3>
          <div className="scroll-box tall">
            {referentiels.domaines.map((d1) => (
              <div key={d1.code} className="tree-d1">
                <label className="check bold">
                  <input
                    type="checkbox"
                    checked={selectedD1.includes(d1.code)}
                    onChange={() => toggleItem(selectedD1, setSelectedD1, d1.code)}
                  />
                  <span>{d1.code} — {d1.libelle}</span>
                </label>
                {d1.domaines2.map((d2) => (
                  <div key={d2.code} className="tree-d2">
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={selectedD2.includes(d2.code)}
                        onChange={() => toggleItem(selectedD2, setSelectedD2, d2.code)}
                      />
                      <span>{d2.code} — {d2.libelle}</span>
                    </label>
                    {d2.domaines3.map((d3) => (
                      <label key={d3.code} className="check tree-d3">
                        <input
                          type="checkbox"
                          checked={selectedD3.includes(d3.code)}
                          onChange={() => toggleItem(selectedD3, setSelectedD3, d3.code)}
                        />
                        <span>{d3.code} — {d3.libelle}</span>
                      </label>
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </section>
      </aside>

      <main className="map-wrapper">
        <MapContainer center={[47.3220, 5.0415]} zoom={14} className="map" preferCanvas={true}>
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapWatcher
            onBoundsChange={setView}
            addMode={addMode}
            onMapClick={handleMapClick}
          />

          {bpeItems.map((eq) => {
            const d = details[eq.id];
            return (
              <CircleMarker
                key={eq.id}
                center={[eq.lat, eq.lon]}
                radius={5}
                pathOptions={{ color: DOMAINE_COLORS[eq.domaine1_code] || "#2563eb", weight: 1, fillOpacity: 0.7 }}
                eventHandlers={{ popupopen: () => loadDetail(eq.id) }}
              >
                <Popup>
                  <strong>{eq.nom || "(sans nom)"}</strong>
                  <br />
                  <span>{eq.domaine3_code} — {eq.domaine3_libelle}</span>
                  {d ? (
                    <>
                      <br />
                      <small>{d.domaine1.libelle} &gt; {d.domaine2.libelle}</small>
                      <br />
                      <span>{d.adresse} {d.codepostal} {d.ville}</span>
                      {d.siret && (
                        <>
                          <br />
                          <small>SIRET : {d.siret}</small>
                        </>
                      )}
                    </>
                  ) : (
                    <>
                      <br />
                      <small>{eq.ville} · chargement de la fiche…</small>
                    </>
                  )}
                </Popup>
              </CircleMarker>
            );
          })}

          {implantations.map((imp) => (
            <Marker
              key={imp.id}
              position={[imp.latitude, imp.longitude]}
              icon={prospectIcon}
            >
              <Popup>
                <strong>[Prospection] {imp.titre}</strong>
                <br />
                {imp.domaine3_libelle && (
                  <>
                    <span>Type envisagé : {imp.domaine3_libelle}</span>
                    <br />
                  </>
                )}
                {imp.annotations && <p>{imp.annotations}</p>}
                {imp.commentaires && <small>{imp.commentaires}</small>}
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </main>
    </div>
  );
}