import React, { useEffect, useRef, useState, useCallback } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { api, setTokens, clearTokens, getToken } from "./api";

const bpeIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
});

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
        onBoundsChange([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(","));
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
    onBoundsChange([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(","));
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

  const [bbox, setBbox] = useState(null);
  const [bpeMap, setBpeMap] = useState({});
  const loadedIdsRef = useRef(new Set());
  const [loadingBpe, setLoadingBpe] = useState(false);
  const [totalInView, setTotalInView] = useState(0);

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

  // Réinitialiser le cache local lorsque les filtres changent
  useEffect(() => {
    loadedIdsRef.current = new Set();
    setBpeMap({});
  }, [selectedD1, selectedD2, selectedD3, selectedVilles]);

  // Chargement incrémental par emprise géographique + filtres actifs
  useEffect(() => {
    if (!bbox) return;
    let cancelled = false;
    setLoadingBpe(true);

    const alreadyLoaded = Array.from(loadedIdsRef.current);
    api
      .getBPE({
        bbox,
        domaine1: selectedD1,
        domaine2: selectedD2,
        domaine3: selectedD3,
        villes: selectedVilles,
        excludeIds: alreadyLoaded.slice(0, 500),
      })
      .then((res) => {
        if (cancelled) return;
        setTotalInView(res.total_in_view);
        if (res.results?.length) {
          setBpeMap((prev) => {
            const next = { ...prev };
            for (const item of res.results) {
              loadedIdsRef.current.add(item.id);
              next[item.id] = item;
            }
            return next;
          });
        }
      })
      .catch(console.error)
      .finally(() => {
        if (!cancelled) setLoadingBpe(false);
      });

    return () => {
      cancelled = true;
    };
  }, [bbox, selectedD1, selectedD2, selectedD3, selectedVilles]);

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
            Affichés : <strong>{bpeItems.length}</strong> / {totalInView} dans la zone
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
        <MapContainer center={[47.3220, 5.0415]} zoom={10} className="map">
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapWatcher
            onBoundsChange={setBbox}
            addMode={addMode}
            onMapClick={handleMapClick}
          />

          {bpeItems.map((eq) => (
            <Marker key={eq.id} position={[eq.lat, eq.lon]} icon={bpeIcon}>
              <Popup>
                <strong>{eq.nom}</strong>
                <br />
                <span>{eq.domaine3_code} — {eq.domaine3_libelle}</span>
                <br />
                <small>{eq.domaine1_libelle} &gt; {eq.domaine2_libelle}</small>
                <br />
                <span>{eq.adresse} {eq.codepostal} {eq.ville}</span>
                {eq.siret && (
                  <>
                    <br />
                    <small>SIRET : {eq.siret}</small>
                  </>
                )}
              </Popup>
            </Marker>
          ))}

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