"""
Couche de données de l'application Fatelikou (rappel des défunts – 11 Ikhlass).
SQLite pur (module standard), donc aucune dépendance externe : fonctionne
sur PC comme sur Android.
"""
import json
import sqlite3
from datetime import date, datetime, timedelta

NB_IKHLASS = 11

GROUPES_PAR_DEFAUT = [
    ("Famille", [
        "Côté paternel",
        "Côté maternel",
        "Parents & fratrie",
        "Belle-famille",
    ]),
    ("Amis", []),
    ("Voisins", []),
    ("Collègues", []),
    ("Communauté / Mosquée", []),
    ("Autres", []),
]

REGLAGES_PAR_DEFAUT = {
    "frequence_jours": "7",      # tous les combien de jours prier pour chaque défunt
    "notifications": "1",
    "dernier_rappel": "",
    "vibration": "1",
}


def _aujourdhui():
    return date.today()


def parse_date(texte):
    """Accepte JJ/MM/AAAA, JJ-MM-AAAA ou AAAA-MM-JJ. Renvoie 'AAAA-MM-JJ' ou ''."""
    texte = (texte or "").strip()
    if not texte:
        return ""
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(texte, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError("Date invalide (format attendu : JJ/MM/AAAA)")


def format_date(iso):
    if not iso:
        return ""
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso


def nom_complet(d):
    return " ".join(x for x in (d["prenom"], d["nom"]) if x).strip()


def age_au_deces(d):
    """Âge calculé à partir des dates (remplace la saisie manuelle de l'âge)."""
    if not d["date_naissance"] or not d["date_deces"]:
        return None
    n = date.fromisoformat(d["date_naissance"])
    m = date.fromisoformat(d["date_deces"])
    return m.year - n.year - ((m.month, m.day) < (n.month, n.day))


class Base:
    def __init__(self, chemin):
        self.conn = sqlite3.connect(chemin)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._creer()

    # ------------------------------------------------------------------ schéma
    def _creer(self):
        c = self.conn
        c.executescript("""
        CREATE TABLE IF NOT EXISTS groupes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            parent_id INTEGER REFERENCES groupes(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS defunts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prenom TEXT DEFAULT '',
            groupe_id INTEGER REFERENCES groupes(id) ON DELETE SET NULL,
            lien TEXT DEFAULT '',
            date_naissance TEXT DEFAULT '',
            lieu_naissance TEXT DEFAULT '',
            date_deces TEXT DEFAULT '',
            lieu_deces TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            cree_le TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prieres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            defunt_id INTEGER NOT NULL REFERENCES defunts(id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            nombre INTEGER NOT NULL DEFAULT 11
        );
        CREATE TABLE IF NOT EXISTS reglages (
            cle TEXT PRIMARY KEY,
            valeur TEXT
        );
        """)
        for k, v in REGLAGES_PAR_DEFAUT.items():
            c.execute("INSERT OR IGNORE INTO reglages(cle, valeur) VALUES (?, ?)", (k, v))
        if not c.execute("SELECT 1 FROM groupes LIMIT 1").fetchone():
            for nom, enfants in GROUPES_PAR_DEFAUT:
                gid = self.ajouter_groupe(nom)
                for e in enfants:
                    self.ajouter_groupe(e, gid)
        c.commit()

    # --------------------------------------------------------------- réglages
    def reglage(self, cle):
        r = self.conn.execute("SELECT valeur FROM reglages WHERE cle=?", (cle,)).fetchone()
        return r["valeur"] if r else REGLAGES_PAR_DEFAUT.get(cle, "")

    def set_reglage(self, cle, valeur):
        self.conn.execute("INSERT OR REPLACE INTO reglages(cle, valeur) VALUES (?, ?)",
                          (cle, str(valeur)))
        self.conn.commit()

    @property
    def frequence(self):
        try:
            return max(1, int(self.reglage("frequence_jours")))
        except ValueError:
            return 7

    # ---------------------------------------------------------------- groupes
    def ajouter_groupe(self, nom, parent_id=None):
        nom = (nom or "").strip()
        if not nom:
            raise ValueError("Le nom du groupe est obligatoire")
        cur = self.conn.execute("INSERT INTO groupes(nom, parent_id) VALUES (?, ?)",
                                (nom, parent_id))
        self.conn.commit()
        return cur.lastrowid

    def renommer_groupe(self, gid, nom):
        nom = (nom or "").strip()
        if not nom:
            raise ValueError("Le nom du groupe est obligatoire")
        self.conn.execute("UPDATE groupes SET nom=? WHERE id=?", (nom, gid))
        self.conn.commit()

    def supprimer_groupe(self, gid):
        """Supprime le groupe et ses sous-groupes ; les défunts sont déplacés
        dans le groupe parent (ou 'sans groupe')."""
        g = self.groupe(gid)
        if not g:
            return
        ids = self._ids_descendants(gid)
        place = ",".join("?" * len(ids))
        self.conn.execute(f"UPDATE defunts SET groupe_id=? WHERE groupe_id IN ({place})",
                          [g["parent_id"], *ids])
        self.conn.execute("DELETE FROM groupes WHERE id=?", (gid,))
        self.conn.commit()

    def _ids_descendants(self, gid):
        ids, pile = [], [gid]
        while pile:
            g = pile.pop()
            ids.append(g)
            pile.extend(r["id"] for r in self.conn.execute(
                "SELECT id FROM groupes WHERE parent_id=?", (g,)))
        return ids

    def defunts_du_groupe(self, gid):
        """Tous les défunts d'un groupe et de ses sous-groupes."""
        if gid is None:
            return self.conn.execute("SELECT * FROM defunts WHERE groupe_id IS NULL").fetchall()
        ids = self._ids_descendants(gid)
        return self.conn.execute(
            f"SELECT * FROM defunts WHERE groupe_id IN ({','.join('?' * len(ids))})"
            " ORDER BY prenom COLLATE NOCASE", ids).fetchall()

    def groupe(self, gid):
        return self.conn.execute("SELECT * FROM groupes WHERE id=?", (gid,)).fetchone()

    def groupes(self):
        return self.conn.execute("SELECT * FROM groupes ORDER BY id").fetchall()

    def chemin_groupe(self, gid):
        """'Famille › Côté paternel'"""
        noms = []
        while gid:
            g = self.groupe(gid)
            if not g:
                break
            noms.append(g["nom"])
            gid = g["parent_id"]
        return " › ".join(reversed(noms))

    def groupes_a_plat(self):
        """Liste [(id, 'Famille › Côté paternel'), ...] triée pour les menus."""
        res = [(g["id"], self.chemin_groupe(g["id"])) for g in self.groupes()]
        return sorted(res, key=lambda x: x[1].lower())

    def arbre(self):
        """Arborescence complète : liste de nœuds
        {'type':'groupe','id','nom','enfants':[...]} / {'type':'defunt', ...}"""
        groupes = self.groupes()
        defunts = self.defunts()
        par_parent = {}
        for g in groupes:
            par_parent.setdefault(g["parent_id"], []).append(g)
        def_par_groupe = {}
        for d in defunts:
            def_par_groupe.setdefault(d["groupe_id"], []).append(d)

        def construire(gid):
            noeuds = []
            for g in par_parent.get(gid, []):
                enfants = construire(g["id"])
                noeuds.append({
                    "type": "groupe", "id": g["id"], "nom": g["nom"],
                    "enfants": enfants,
                    "total": sum(n["total"] if n["type"] == "groupe" else 1 for n in enfants),
                })
            for d in def_par_groupe.get(gid, []) if gid is not None else []:
                noeuds.append({"type": "defunt", "id": d["id"], "nom": nom_complet(d),
                               "lien": d["lien"]})
            return noeuds

        racine = construire(None)
        sans = def_par_groupe.get(None, [])
        if sans:
            racine.append({"type": "groupe", "id": None, "nom": "Sans groupe",
                           "total": len(sans),
                           "enfants": [{"type": "defunt", "id": d["id"], "nom": nom_complet(d),
                                        "lien": d["lien"]} for d in sans]})
        return racine

    # ---------------------------------------------------------------- défunts
    CHAMPS = ("nom", "prenom", "groupe_id", "lien", "date_naissance", "lieu_naissance",
              "date_deces", "lieu_deces", "notes")

    def _valeurs(self, data):
        data = dict(data)
        if not (data.get("nom") or "").strip() and not (data.get("prenom") or "").strip():
            raise ValueError("Le nom ou le prénom est obligatoire")
        out = {}
        for k in self.CHAMPS:
            v = data.get(k)
            if k == "groupe_id":
                out[k] = v or None
            elif k.startswith("date_"):
                out[k] = parse_date(v)
            else:
                out[k] = (v or "").strip()
        if out["date_naissance"] and out["date_deces"] and out["date_deces"] < out["date_naissance"]:
            raise ValueError("La date de décès est avant la date de naissance")
        return out

    def ajouter_defunt(self, **data):
        v = self._valeurs(data)
        v["cree_le"] = datetime.now().isoformat(timespec="seconds")
        cols = ", ".join(v)
        cur = self.conn.execute(
            f"INSERT INTO defunts({cols}) VALUES ({', '.join('?' * len(v))})", list(v.values()))
        self.conn.commit()
        return cur.lastrowid

    def modifier_defunt(self, did, **data):
        v = self._valeurs(data)
        sets = ", ".join(f"{k}=?" for k in v)
        self.conn.execute(f"UPDATE defunts SET {sets} WHERE id=?", [*v.values(), did])
        self.conn.commit()

    def supprimer_defunt(self, did):
        self.conn.execute("DELETE FROM defunts WHERE id=?", (did,))
        self.conn.commit()

    def defunt(self, did):
        return self.conn.execute("SELECT * FROM defunts WHERE id=?", (did,)).fetchone()

    def defunts(self, recherche=""):
        if recherche:
            return self.conn.execute(
                "SELECT * FROM defunts WHERE (prenom || ' ' || nom) LIKE ? OR (nom || ' ' || prenom) LIKE ?"
                " ORDER BY prenom COLLATE NOCASE, nom COLLATE NOCASE",
                (f"%{recherche}%", f"%{recherche}%")).fetchall()
        return self.conn.execute(
            "SELECT * FROM defunts ORDER BY prenom COLLATE NOCASE, nom COLLATE NOCASE").fetchall()

    # ---------------------------------------------------------------- prières
    def enregistrer_priere(self, did, nombre=NB_IKHLASS, quand=None):
        quand = quand or datetime.now()
        self.conn.execute("INSERT INTO prieres(defunt_id, date, nombre) VALUES (?, ?, ?)",
                          (did, quand.isoformat(timespec="seconds"), nombre))
        self.conn.commit()

    def historique(self, did, limite=50):
        return self.conn.execute(
            "SELECT * FROM prieres WHERE defunt_id=? ORDER BY date DESC LIMIT ?",
            (did, limite)).fetchall()

    def derniere_priere(self, did):
        r = self.conn.execute("SELECT MAX(date) AS d FROM prieres WHERE defunt_id=?",
                              (did,)).fetchone()
        return r["d"] if r and r["d"] else None

    def nb_prieres(self, did=None):
        if did is None:
            r = self.conn.execute("SELECT COUNT(*) n, COALESCE(SUM(nombre),0) s FROM prieres")
        else:
            r = self.conn.execute(
                "SELECT COUNT(*) n, COALESCE(SUM(nombre),0) s FROM prieres WHERE defunt_id=?",
                (did,))
        r = r.fetchone()
        return r["n"], r["s"]

    def prie_aujourdhui(self, did, jour=None):
        jour = (jour or _aujourdhui()).isoformat()
        return self.conn.execute(
            "SELECT 1 FROM prieres WHERE defunt_id=? AND substr(date,1,10)=?",
            (did, jour)).fetchone() is not None

    # ---------------------------------------------------------------- rappels
    def a_prier(self, jour=None):
        """Défunts pour lesquels on n'a pas prié depuis `frequence` jours (ou jamais),
        plus ceux dont c'est l'anniversaire de décès. Triés : anniversaires,
        jamais priés, puis les plus anciens."""
        jour = jour or _aujourdhui()
        limite = jour - timedelta(days=self.frequence - 1)
        res = []
        for d in self.defunts():
            der = self.derniere_priere(d["id"])
            der_j = datetime.fromisoformat(der).date() if der else None
            anniv = bool(d["date_deces"]) and d["date_deces"][5:10] == jour.isoformat()[5:10]
            prie_ce_jour = der_j == jour
            if prie_ce_jour:
                continue
            if anniv or der_j is None or der_j < limite:
                res.append({"defunt": d, "derniere": der, "anniversaire": anniv,
                            "jours": (jour - der_j).days if der_j else None})
        res.sort(key=lambda x: (not x["anniversaire"], x["jours"] is not None,
                                -(x["jours"] or 0)))
        return res

    def stats(self):
        n, s = self.nb_prieres()
        nb_def = self.conn.execute("SELECT COUNT(*) FROM defunts").fetchone()[0]
        auj = self.conn.execute(
            "SELECT COUNT(*) FROM prieres WHERE substr(date,1,10)=?",
            (_aujourdhui().isoformat(),)).fetchone()[0]
        return {"defunts": nb_def, "prieres": n, "ikhlass": s, "aujourdhui": auj}

    # ------------------------------------------------------- export / import
    def exporter(self):
        def rows(t):
            return [dict(r) for r in self.conn.execute(f"SELECT * FROM {t}")]
        return json.dumps({
            "app": "fatelikou", "version": 1,
            "exporte_le": datetime.now().isoformat(timespec="seconds"),
            "groupes": rows("groupes"), "defunts": rows("defunts"),
            "prieres": rows("prieres"),
        }, ensure_ascii=False, indent=2)

    def importer(self, texte):
        """Remplace toutes les données par celles de la sauvegarde."""
        data = json.loads(texte)
        if data.get("app") != "fatelikou":
            raise ValueError("Ce fichier n'est pas une sauvegarde de l'application")
        c = self.conn
        try:
            c.execute("PRAGMA foreign_keys = OFF")
            c.execute("DELETE FROM prieres")
            c.execute("DELETE FROM defunts")
            c.execute("DELETE FROM groupes")
            for g in data["groupes"]:
                c.execute("INSERT INTO groupes(id, nom, parent_id) VALUES (?,?,?)",
                          (g["id"], g["nom"], g["parent_id"]))
            for d in data["defunts"]:
                cols = ["id", "cree_le", *self.CHAMPS]
                c.execute(f"INSERT INTO defunts({', '.join(cols)}) VALUES"
                          f" ({', '.join('?' * len(cols))})",
                          [d.get(k) if k in ("id", "groupe_id") else (d.get(k) or "")
                           for k in cols])
            for p in data["prieres"]:
                c.execute("INSERT INTO prieres(id, defunt_id, date, nombre) VALUES (?,?,?,?)",
                          (p["id"], p["defunt_id"], p["date"], p["nombre"]))
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.execute("PRAGMA foreign_keys = ON")
        return len(data["defunts"])
