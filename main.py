"""
Fatelikou – se rappeler des défunts et réciter pour eux 11 fois la sourate Al-Ikhlass.

Application mobile Kivy (Android / PC).
  * Arborescence des défunts : Famille (côté paternel, maternel...), Amis, Voisins...
  * Fiche de chaque défunt : naissance, décès (date + lieu), âge calculé, notes
  * Compteur de 11 Ikhlass, enregistré dans l'historique du défunt
  * Rappels : la page d'accueil liste les défunts pour qui on n'a pas prié depuis
    un certain nombre de jours, et ceux dont c'est l'anniversaire du décès
  * Sauvegarde / restauration (fichier JSON ou presse-papiers)
"""
import os
from datetime import date, datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.treeview import TreeView, TreeViewLabel
from kivy.utils import escape_markup, platform

from db import Base, NB_IKHLASS, format_date, nom_complet, age_au_deces

# --------------------------------------------------------------------- thème
FOND = (0.96, 0.95, 0.91, 1)       # sable clair
CARTE = (1, 1, 1, 1)
VERT = (0.11, 0.37, 0.29, 1)       # vert profond
VERT_CLAIR = (0.85, 0.92, 0.88, 1)
OR = (0.75, 0.58, 0.25, 1)
ROUGE = (0.70, 0.22, 0.20, 1)
GRIS = (0.55, 0.55, 0.52, 1)
TEXTE = (0.13, 0.14, 0.13, 1)
BLANC = (1, 1, 1, 1)

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

FREQUENCES = [("Chaque jour", 1), ("Tous les 3 jours", 3), ("Chaque semaine", 7),
              ("Toutes les 2 semaines", 14), ("Chaque mois", 30)]

SOURATE = (
    "[b]Bismillahi r-rahmani r-rahim[/b]\n"
    "[b]Qul huwa Allahu ahad[/b]\n"
    "[b]Allahu s-samad[/b]\n"
    "[b]Lam yalid wa lam yulad[/b]\n"
    "[b]Wa lam yakun lahu kufuwan ahad[/b]"
)
TRADUCTION = (
    "Au nom d'Allah, le Tout Miséricordieux, le Très Miséricordieux.\n"
    "Dis : Lui, Allah, est Unique.\n"
    "Allah, l'Absolu, vers qui tout se tourne.\n"
    "Il n'engendre pas et n'a pas été engendré.\n"
    "Et nul n'est égal à Lui."
)
DOUA = ("Ô Allah, fais parvenir la récompense de cette lecture à {nom}. "
        "Pardonne-lui, fais-lui miséricorde et accorde-lui le Paradis. Amine.")


def esc(t):
    return escape_markup(t or "")


def date_longue(j=None):
    j = j or date.today()
    return f"{JOURS[j.weekday()].capitalize()} {j.day} {MOIS[j.month - 1]} {j.year}"


# ------------------------------------------------------------ petits widgets
def lbl(texte, taille=16, gras=False, couleur=TEXTE, align="left"):
    l = Label(text=texte, font_size=sp(taille), bold=gras, color=couleur, halign=align,
              valign="middle", markup=True, size_hint_y=None)
    l.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
    l.bind(texture_size=lambda w, v: setattr(w, "height", v[1] + dp(4)))
    return l


def bouton(texte, action, couleur=VERT, couleur_texte=BLANC, h=48, **kw):
    b = Button(text=texte, size_hint_y=None, height=dp(h), background_normal="",
               background_color=couleur, color=couleur_texte, font_size=sp(16),
               bold=True, markup=True, **kw)
    b.bind(on_release=lambda *_: action())
    return b


def champ(indice="", texte="", multiligne=False, type_saisie="text"):
    return TextInput(text=texte, hint_text=indice, multiline=multiligne,
                     size_hint_y=None, height=dp(100 if multiligne else 46),
                     font_size=sp(16), write_tab=False, input_type=type_saisie,
                     padding=[dp(10), dp(12), dp(10), dp(10)])


def ligne(*widgets, h=48, espace=8):
    b = BoxLayout(size_hint_y=None, height=dp(h), spacing=dp(espace))
    for w in widgets:
        b.add_widget(w)
    return b


def fond(widget, couleur, rayon=0):
    with widget.canvas.before:
        Color(*couleur)
        r = RoundedRectangle(radius=[dp(rayon)]) if rayon else Rectangle()
    widget.bind(pos=lambda w, v: setattr(r, "pos", v), size=lambda w, v: setattr(r, "size", v))


class Carte(BoxLayout):
    def __init__(self, couleur=CARTE, **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("padding", dp(14))
        kw.setdefault("spacing", dp(6))
        super().__init__(size_hint_y=None, **kw)
        self.bind(minimum_height=self.setter("height"))
        fond(self, couleur, 14)


def zone_defilante():
    sv = ScrollView(do_scroll_x=False, bar_width=dp(4))
    boite = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10),
                      padding=[0, 0, 0, dp(16)])
    boite.bind(minimum_height=boite.setter("height"))
    sv.add_widget(boite)
    return sv, boite


# -------------------------------------------------------------- fenêtres pop
def popup_info(titre, message):
    contenu = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(12))
    contenu.add_widget(lbl(message, couleur=BLANC))
    p = Popup(title=titre, content=contenu, size_hint=(0.9, None), height=dp(260))
    contenu.add_widget(bouton("OK", p.dismiss))
    p.open()


def popup_confirmer(titre, message, action, texte_ok="Confirmer", couleur=ROUGE):
    contenu = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(12))
    contenu.add_widget(lbl(message, couleur=BLANC))
    p = Popup(title=titre, content=contenu, size_hint=(0.9, None), height=dp(280))

    def ok():
        p.dismiss()
        action()
    contenu.add_widget(ligne(bouton("Annuler", p.dismiss, couleur=GRIS),
                             bouton(texte_ok, ok, couleur=couleur)))
    p.open()


def popup_texte(titre, action, valeur="", indice=""):
    contenu = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(12))
    ti = champ(indice, valeur)
    contenu.add_widget(ti)
    p = Popup(title=titre, content=contenu, size_hint=(0.9, None), height=dp(220),
              pos_hint={"top": 0.95})

    def ok():
        try:
            action(ti.text)
            p.dismiss()
        except ValueError as e:
            popup_info("Attention", str(e))
    contenu.add_widget(ligne(bouton("Annuler", p.dismiss, couleur=GRIS), bouton("Valider", ok)))
    p.open()
    Clock.schedule_once(lambda dt: setattr(ti, "focus", True), 0.3)


def popup_choix(titre, options):
    """options = [(texte, action, couleur), ...]"""
    contenu = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
    p = Popup(title=titre, content=contenu, size_hint=(0.9, None),
              height=dp(80 + 56 * (len(options) + 1)))
    for texte, action, couleur in options:
        def faire(a=action):
            p.dismiss()
            a()
        contenu.add_widget(bouton(texte, faire, couleur=couleur))
    contenu.add_widget(bouton("Fermer", p.dismiss, couleur=GRIS))
    p.open()


# ------------------------------------------------------------- écran de base
class Ecran(Screen):
    titre = ""
    avec_retour = True

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        racine = BoxLayout(orientation="vertical")
        fond(racine, FOND)
        barre = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(6), 0], spacing=dp(6))
        fond(barre, VERT)
        if self.avec_retour:
            r = Button(text="< Retour", size_hint_x=None, width=dp(96), background_normal="",
                       background_color=VERT, color=BLANC, font_size=sp(15))
            r.bind(on_release=lambda *_: self.app.retour())
            barre.add_widget(r)
        self.lbl_titre = Label(text=self.titre, font_size=sp(20), bold=True, color=BLANC,
                               halign="left", valign="middle", shorten=True,
                               shorten_from="right", markup=True)
        self.lbl_titre.bind(size=lambda w, v: setattr(w, "text_size", v))
        barre.add_widget(self.lbl_titre)
        racine.add_widget(barre)
        self.contenu = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        racine.add_widget(self.contenu)
        self.add_widget(racine)
        self.construire()

    @property
    def db(self):
        return self.app.db

    def construire(self):
        pass

    def rafraichir(self):
        pass

    def on_pre_enter(self, *a):
        self.rafraichir()


# ------------------------------------------------------------------ accueil
class Accueil(Ecran):
    titre = "Fatelikou"
    avec_retour = False

    def construire(self):
        self.sv, self.boite = zone_defilante()
        self.contenu.add_widget(self.sv)

    def rafraichir(self):
        b = self.boite
        b.clear_widgets()
        st = self.db.stats()
        a_prier = self.db.a_prier()

        c = Carte(couleur=VERT_CLAIR)
        c.add_widget(lbl(date_longue(), 15, couleur=VERT))
        c.add_widget(lbl("[b]Qu'Allah fasse miséricorde à nos défunts[/b]", 18, couleur=VERT))
        c.add_widget(lbl(f"{st['defunts']} défunt(s)  ·  {st['prieres']} lecture(s)  ·  "
                         f"{st['ikhlass']} Ikhlass récitées", 14, couleur=TEXTE))
        c.add_widget(lbl(f"Aujourd'hui : {st['aujourdhui']} lecture(s)", 14, couleur=TEXTE))
        b.add_widget(c)

        if st["defunts"] == 0:
            vide = Carte()
            vide.add_widget(lbl("Bienvenue", 18, True))
            vide.add_widget(lbl("Commencez par ajouter les défunts de votre famille, vos amis, "
                                "vos voisins... Ils seront rangés dans un arbre et l'application "
                                "vous rappellera de lire pour eux 11 fois la sourate Al-Ikhlass.",
                                15))
            vide.add_widget(bouton("+ Ajouter un défunt", lambda: self.app.ouvrir_formulaire()))
            b.add_widget(vide)
            return

        b.add_widget(lbl(f"[b]À prier aujourd'hui ({len(a_prier)})[/b]", 18, couleur=VERT))
        if not a_prier:
            ok = Carte()
            ok.add_widget(lbl("Toutes vos lectures sont à jour. Alhamdulillah.", 16))
            ok.add_widget(lbl(f"Rappel réglé sur : {self.app.libelle_frequence()}.", 14,
                              couleur=GRIS))
            b.add_widget(ok)
        else:
            ids = [x["defunt"]["id"] for x in a_prier]
            b.add_widget(bouton(f"Prier pour les {len(ids)} défunts à la suite",
                                lambda: self.app.ouvrir_priere(ids), couleur=OR, h=54))
            for x in a_prier:
                b.add_widget(self._carte_defunt(x))

    def _carte_defunt(self, x):
        d = x["defunt"]
        c = Carte(spacing=dp(4))
        c.add_widget(lbl(f"[b]{esc(nom_complet(d))}[/b]", 17))
        infos = [esc(d["lien"])] if d["lien"] else []
        if d["groupe_id"]:
            infos.append(esc(self.db.chemin_groupe(d["groupe_id"])))
        if infos:
            c.add_widget(lbl("  ·  ".join(infos), 14, couleur=GRIS))
        if x["anniversaire"]:
            raison = "[color=b08a3c][b]Anniversaire de son décès aujourd'hui[/b][/color]"
        elif x["jours"] is None:
            raison = "Pas encore de lecture enregistrée"
        else:
            raison = f"Dernière lecture il y a {x['jours']} jour(s)"
        c.add_widget(lbl(raison, 14))
        c.add_widget(ligne(
            bouton("Fiche", lambda: self.app.ouvrir_fiche(d["id"]), couleur=VERT_CLAIR,
                   couleur_texte=VERT, h=42),
            bouton("Lire 11 Ikhlass", lambda: self.app.ouvrir_priere([d["id"]]), h=42),
            h=42))
        return c


# ------------------------------------------------------------------- arbre
class Noeud(TreeViewLabel):
    pass


class Arbre(Ecran):
    titre = "Mes défunts"
    avec_retour = False

    def construire(self):
        self.ouverts = set()
        self.groupe_courant = None    # (id, nom) du dernier groupe touché
        self.recherche = champ("Rechercher un nom...")
        self.recherche.bind(text=lambda *_: self.rafraichir())
        self.contenu.add_widget(self.recherche)
        self.contenu.add_widget(ligne(
            bouton("+ Défunt", lambda: self.app.ouvrir_formulaire(
                groupe_id=self.groupe_courant[0] if self.groupe_courant else None)),
            bouton("+ Groupe", self.nouveau_groupe, couleur=OR)))
        self.barre_groupe = BoxLayout(size_hint_y=None, height=0, opacity=0)
        self.contenu.add_widget(self.barre_groupe)
        self.sv, self.boite = zone_defilante()
        self.contenu.add_widget(self.sv)

    def rafraichir(self):
        self.boite.clear_widgets()
        q = self.recherche.text.strip()
        if q:
            self._cacher_barre()
            res = self.db.defunts(q)
            if not res:
                self.boite.add_widget(lbl("Aucun défunt trouvé.", 15, couleur=GRIS))
            for d in res:
                titre = esc(nom_complet(d))
                if d["groupe_id"]:
                    titre += f"\n[size={int(sp(13))}][color=888884]" \
                             f"{esc(self.db.chemin_groupe(d['groupe_id']))}[/color][/size]"
                b = bouton(titre, lambda did=d["id"]: self.app.ouvrir_fiche(did),
                           couleur=CARTE, couleur_texte=TEXTE, h=60)
                b.halign = "left"
                b.bind(size=lambda w, v: setattr(w, "text_size", (v[0] - dp(24), None)))
                self.boite.add_widget(b)
            return

        tv = TreeView(hide_root=True, indent_level=dp(22), size_hint_y=None)
        tv.bind(minimum_height=tv.setter("height"))
        tv.bind(selected_node=self._selection)
        tv.bind(on_node_expand=lambda t, n: self.ouverts.add(n.gid))
        tv.bind(on_node_collapse=lambda t, n: self.ouverts.discard(n.gid))

        def ajouter(noeuds, parent=None):
            for n in noeuds:
                if n["type"] == "groupe":
                    w = Noeud(text=f"[b]{esc(n['nom'])}[/b]  [color=888884]({n['total']})[/color]",
                              markup=True, font_size=sp(17), color=VERT,
                              is_open=n["id"] in self.ouverts, padding=(dp(4), dp(10)),
                              even_color=(0, 0, 0, 0.03), odd_color=(0, 0, 0, 0),
                              color_selected=VERT_CLAIR)
                    w.gid, w.did, w.nom = n["id"], None, n["nom"]
                    tv.add_node(w, parent)
                    ajouter(n["enfants"], w)
                else:
                    t = esc(n["nom"])
                    if n["lien"]:
                        t += f"  [color=888884]– {esc(n['lien'])}[/color]"
                    w = Noeud(text=t, markup=True, font_size=sp(16), color=TEXTE,
                              padding=(dp(4), dp(10)), even_color=(0, 0, 0, 0.03),
                              odd_color=(0, 0, 0, 0), color_selected=VERT_CLAIR)
                    w.gid, w.did = None, n["id"]
                    tv.add_node(w, parent)

        ajouter(self.db.arbre())
        self.boite.add_widget(tv)
        self.boite.add_widget(lbl("Touchez un groupe pour l'ouvrir et le gérer, "
                                  "un nom pour voir sa fiche.", 13, couleur=GRIS))
        if self.groupe_courant:
            self._montrer_barre()

    def _selection(self, tv, noeud):
        if noeud is None:
            return
        if noeud.did is not None:
            self.app.ouvrir_fiche(noeud.did)
        else:
            tv.toggle_node(noeud)
            self.groupe_courant = (noeud.gid, noeud.nom)
            self._montrer_barre()
        Clock.schedule_once(lambda dt: tv.deselect_node(), 0)

    def _cacher_barre(self):
        self.barre_groupe.clear_widgets()
        self.barre_groupe.height, self.barre_groupe.opacity = 0, 0

    def _montrer_barre(self):
        gid, nom = self.groupe_courant
        self.barre_groupe.clear_widgets()
        self.barre_groupe.height, self.barre_groupe.opacity = dp(44), 1
        self.barre_groupe.add_widget(bouton(f"Gérer « {esc(nom)} »", self.gerer_groupe,
                                            couleur=VERT_CLAIR, couleur_texte=VERT, h=44))

    def nouveau_groupe(self, parent_id=None):
        def creer(nom):
            gid = self.db.ajouter_groupe(nom, parent_id)
            if parent_id:
                self.ouverts.add(parent_id)
            self.groupe_courant = (gid, nom.strip())
            self.rafraichir()
        popup_texte("Nouveau sous-groupe" if parent_id else "Nouveau groupe", creer,
                    indice="ex : Côté paternel, Amis d'enfance...")

    def gerer_groupe(self):
        gid, nom = self.groupe_courant
        defunts = self.db.defunts_du_groupe(gid)
        options = []
        if defunts:
            ids = [d["id"] for d in defunts]
            options.append((f"Prier pour tout le groupe ({len(ids)})",
                            lambda: self.app.ouvrir_priere(ids), OR))
        if gid is None:      # « Sans groupe » n'est pas un vrai groupe
            popup_choix(nom, options) if options else None
            return
        options += [
            ("+ Défunt dans ce groupe", lambda: self.app.ouvrir_formulaire(groupe_id=gid), VERT),
            ("+ Sous-groupe", lambda: self.nouveau_groupe(gid), VERT),
            ("Renommer", self._renommer, VERT),
            ("Supprimer le groupe", self._supprimer, ROUGE),
        ]
        popup_choix(nom, options)

    def _renommer(self):
        gid, nom = self.groupe_courant

        def faire(n):
            self.db.renommer_groupe(gid, n)
            self.groupe_courant = (gid, n.strip())
            self.rafraichir()
        popup_texte("Renommer le groupe", faire, valeur=nom)

    def _supprimer(self):
        gid, nom = self.groupe_courant

        def faire():
            self.db.supprimer_groupe(gid)
            self.groupe_courant = None
            self._cacher_barre()
            self.rafraichir()
        popup_confirmer("Supprimer", f"Supprimer le groupe « {nom} » et ses sous-groupes ?\n"
                        "Les défunts ne sont pas supprimés : ils remontent dans le groupe parent.",
                        faire, "Supprimer")


# -------------------------------------------------------------------- fiche
class Fiche(Ecran):
    titre = "Fiche"

    def construire(self):
        self.did = None
        self.sv, self.boite = zone_defilante()
        self.contenu.add_widget(self.sv)

    def rafraichir(self):
        b = self.boite
        b.clear_widgets()
        d = self.db.defunt(self.did) if self.did else None
        if not d:
            b.add_widget(lbl("Ce défunt n'existe plus.", 16))
            return
        nom = nom_complet(d)
        self.lbl_titre.text = esc(nom)

        c = Carte()
        c.add_widget(lbl(f"[b]{esc(nom)}[/b]", 22, couleur=VERT))
        sous = []
        if d["lien"]:
            sous.append(esc(d["lien"]))
        if d["groupe_id"]:
            sous.append(esc(self.db.chemin_groupe(d["groupe_id"])))
        if sous:
            c.add_widget(lbl("  ·  ".join(sous), 14, couleur=GRIS))
        if d["date_naissance"] or d["lieu_naissance"]:
            t = "Né(e)"
            if d["date_naissance"]:
                t += f" le {format_date(d['date_naissance'])}"
            if d["lieu_naissance"]:
                t += f" à {esc(d['lieu_naissance'])}"
            c.add_widget(lbl(t, 15))
        if d["date_deces"] or d["lieu_deces"]:
            t = "Décédé(e)"
            if d["date_deces"]:
                t += f" le {format_date(d['date_deces'])}"
            if d["lieu_deces"]:
                t += f" à {esc(d['lieu_deces'])}"
            c.add_widget(lbl(t, 15))
        age = age_au_deces(d)
        if age is not None:
            c.add_widget(lbl(f"À l'âge de {age} ans", 15))
        if d["notes"]:
            c.add_widget(lbl(f"[i]{esc(d['notes'])}[/i]", 15, couleur=GRIS))
        b.add_widget(c)

        b.add_widget(bouton("Lire 11 Ikhlass pour lui / elle",
                            lambda: self.app.ouvrir_priere([d["id"]]), couleur=OR, h=56))

        n, s = self.db.nb_prieres(d["id"])
        h = Carte()
        h.add_widget(lbl("[b]Historique[/b]", 17, couleur=VERT))
        h.add_widget(lbl(f"{n} lecture(s), soit {s} Ikhlass récitées", 15))
        if self.db.prie_aujourdhui(d["id"]):
            h.add_widget(lbl("[color=1c5e4a]Lecture faite aujourd'hui[/color]", 15))
        hist = self.db.historique(d["id"], 15)
        for p in hist:
            dt = datetime.fromisoformat(p["date"])
            h.add_widget(lbl(f"{dt.strftime('%d/%m/%Y à %H:%M')}  –  {p['nombre']} Ikhlass", 14,
                             couleur=GRIS))
        if not hist:
            h.add_widget(lbl("Aucune lecture pour l'instant.", 14, couleur=GRIS))
        b.add_widget(h)

        b.add_widget(ligne(
            bouton("Modifier", lambda: self.app.ouvrir_formulaire(did=d["id"]),
                   couleur=VERT_CLAIR, couleur_texte=VERT),
            bouton("Supprimer", lambda: self._supprimer(d), couleur=ROUGE)))

    def _supprimer(self, d):
        def faire():
            self.db.supprimer_defunt(d["id"])
            self.app.retour()
        popup_confirmer("Supprimer", f"Supprimer {nom_complet(d)} et tout son historique ?",
                        faire, "Supprimer")


# --------------------------------------------------------------- formulaire
class Formulaire(Ecran):
    titre = "Défunt"
    SANS = "Sans groupe"

    def construire(self):
        self.did = None
        sv, b = zone_defilante()
        b.spacing = dp(6)
        self.contenu.add_widget(sv)

        def section(t):
            b.add_widget(lbl(f"[b]{t}[/b]", 16, couleur=VERT))

        def etiquette(t):
            b.add_widget(lbl(t, 14, couleur=GRIS))

        section("Identité")
        etiquette("Prénom")
        self.prenom = champ("Prénom")
        b.add_widget(self.prenom)
        etiquette("Nom")
        self.nom = champ("Nom de famille")
        b.add_widget(self.nom)
        etiquette("Groupe dans l'arbre")
        self.groupe = Spinner(text=self.SANS, values=[], size_hint_y=None, height=dp(46),
                              font_size=sp(15), background_normal="", background_color=VERT_CLAIR,
                              color=VERT)
        b.add_widget(self.groupe)
        etiquette("Lien avec vous")
        self.lien = champ("ex : grand-père, tante, ami d'enfance...")
        b.add_widget(self.lien)

        section("Naissance")
        etiquette("Date (JJ/MM/AAAA)")
        self.date_naissance = champ("JJ/MM/AAAA", type_saisie="datetime")
        b.add_widget(self.date_naissance)
        etiquette("Lieu")
        self.lieu_naissance = champ("Ville, pays")
        b.add_widget(self.lieu_naissance)

        section("Décès")
        etiquette("Date (JJ/MM/AAAA)")
        self.date_deces = champ("JJ/MM/AAAA", type_saisie="datetime")
        b.add_widget(self.date_deces)
        etiquette("Lieu")
        self.lieu_deces = champ("Ville, pays")
        b.add_widget(self.lieu_deces)

        section("Notes")
        self.notes = champ("Souvenirs, invocations particulières...", multiligne=True)
        b.add_widget(self.notes)

        b.add_widget(BoxLayout(size_hint_y=None, height=dp(6)))
        b.add_widget(bouton("Enregistrer", self.enregistrer, h=54))

    def preparer(self, did=None, groupe_id=None):
        self.did = did
        self.choix_groupes = [(None, self.SANS)] + self.db.groupes_a_plat()
        self.groupe.values = [c for _, c in self.choix_groupes]
        d = self.db.defunt(did) if did else None
        self.lbl_titre.text = "Modifier" if d else "Nouveau défunt"
        val = lambda k: (d[k] or "") if d else ""
        for k in ("prenom", "nom", "lien", "lieu_naissance", "lieu_deces", "notes"):
            getattr(self, k).text = val(k)
        self.date_naissance.text = format_date(val("date_naissance"))
        self.date_deces.text = format_date(val("date_deces"))
        gid = d["groupe_id"] if d else groupe_id
        self.groupe.text = next((c for i, c in self.choix_groupes if i == gid), self.SANS)

    def enregistrer(self):
        gid = next((i for i, c in self.choix_groupes if c == self.groupe.text), None)
        data = {k: getattr(self, k).text for k in
                ("prenom", "nom", "lien", "date_naissance", "lieu_naissance", "date_deces",
                 "lieu_deces", "notes")}
        data["groupe_id"] = gid
        try:
            if self.did:
                self.db.modifier_defunt(self.did, **data)
                did = self.did
            else:
                did = self.db.ajouter_defunt(**data)
        except ValueError as e:
            popup_info("Attention", str(e))
            return
        g = gid
        while g:      # déplier le groupe et ses parents dans l'arbre
            self.app.ecran("arbre").ouverts.add(g)
            g = self.db.groupe(g)["parent_id"]
        if self.did:
            self.app.retour()                     # revient sur la fiche, mise à jour
        else:
            self.app.ouvrir_fiche(did, remplacer=True)


# ------------------------------------------------------------------ prière
class Priere(Ecran):
    titre = "11 Ikhlass"

    def construire(self):
        self.file, self.index, self.compte, self.fini = [], 0, 0, False
        self.lbl_pour = lbl("", 14, couleur=GRIS, align="center")
        self.lbl_nom = lbl("", 21, True, couleur=VERT, align="center")
        self.contenu.add_widget(self.lbl_pour)
        self.contenu.add_widget(self.lbl_nom)

        sv, b = zone_defilante()
        self.carte_texte = Carte(couleur=CARTE)
        self.lbl_sourate = lbl(SOURATE, 16, align="center")
        self.lbl_trad = lbl(f"[i]{TRADUCTION}[/i]", 13, couleur=GRIS, align="center")
        self.carte_texte.add_widget(lbl("[b]Sourate Al-Ikhlass (112)[/b]", 14, couleur=OR,
                                        align="center"))
        self.carte_texte.add_widget(self.lbl_sourate)
        self.carte_texte.add_widget(self.lbl_trad)
        b.add_widget(self.carte_texte)
        self.contenu.add_widget(sv)

        self.progres = ProgressBar(max=NB_IKHLASS, value=0, size_hint_y=None, height=dp(14))
        self.contenu.add_widget(self.progres)

        self.compteur = Button(text="", size_hint_y=None, height=dp(170), background_normal="",
                               background_color=VERT, color=BLANC, markup=True,
                               halign="center")
        self.compteur.bind(on_release=lambda *_: self.compter())
        self.contenu.add_widget(self.compteur)
        self.actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.contenu.add_widget(self.actions)

    def demarrer(self, ids):
        self.file, self.index = list(ids), 0
        self._defunt_suivant()

    def _defunt_suivant(self):
        self.compte, self.fini = 0, False
        self._maj()

    def _defunt(self):
        return self.db.defunt(self.file[self.index]) if self.index < len(self.file) else None

    def _maj(self):
        d = self._defunt()
        if not d:
            self.app.retour()
            return
        total = len(self.file)
        self.lbl_pour.text = (f"Lecture pour  ({self.index + 1} / {total})" if total > 1
                              else "Lecture pour")
        self.lbl_nom.text = esc(nom_complet(d))
        self.progres.value = self.compte
        self.actions.clear_widgets()
        if self.fini:
            self.compteur.background_color = OR
            self.compteur.text = (f"[size={int(sp(20))}][b]Lecture terminée[/b][/size]\n\n"
                                  f"[size={int(sp(14))}]{esc(DOUA.format(nom=nom_complet(d)))}"
                                  "[/size]")
            self.compteur.text_size = (self.compteur.width - dp(30), None)
            if self.index + 1 < total:
                self.actions.add_widget(bouton("Défunt suivant", self._suivant))
            self.actions.add_widget(bouton("Terminer", self.app.retour, couleur=GRIS))
        else:
            self.compteur.background_color = VERT
            self.compteur.text_size = (None, None)
            self.compteur.text = (f"[size={int(sp(64))}][b]{self.compte}[/b][/size]"
                                  f"[size={int(sp(24))}] / {NB_IKHLASS}[/size]\n"
                                  f"[size={int(sp(14))}]Touchez après chaque Ikhlass[/size]")
            self.actions.add_widget(bouton("- 1", self._moins, couleur=VERT_CLAIR,
                                           couleur_texte=VERT))
            if total > 1:
                self.actions.add_widget(bouton("Passer", self._suivant, couleur=GRIS))

    def compter(self):
        if self.fini:
            return
        self.compte += 1
        self.app.vibrer(0.04)
        if self.compte >= NB_IKHLASS:
            self.db.enregistrer_priere(self.file[self.index], NB_IKHLASS)
            self.fini = True
            self.app.vibrer(0.4)
        self._maj()

    def _moins(self):
        self.compte = max(0, self.compte - 1)
        self._maj()

    def _suivant(self):
        self.index += 1
        if self.index >= len(self.file):
            self.app.retour()
        else:
            self._defunt_suivant()


# ---------------------------------------------------------------- réglages
class Reglages(Ecran):
    titre = "Réglages"
    avec_retour = False

    def construire(self):
        sv, b = zone_defilante()
        self.contenu.add_widget(sv)

        c = Carte()
        c.add_widget(lbl("[b]Rappels[/b]", 17, couleur=VERT))
        c.add_widget(lbl("Un défunt apparaît dans « À prier aujourd'hui » quand sa dernière "
                         "lecture date de plus longtemps que :", 14))
        self.freq = Spinner(text="", values=[f for f, _ in FREQUENCES], size_hint_y=None,
                            height=dp(46), background_normal="", background_color=VERT_CLAIR,
                            color=VERT, font_size=sp(15))
        self.freq.bind(text=self._freq)
        c.add_widget(self.freq)
        c.add_widget(lbl("Le jour anniversaire du décès, le défunt apparaît aussi.", 13,
                         couleur=GRIS))
        self.vib = ToggleButton(text="Vibration du compteur : oui", size_hint_y=None,
                                height=dp(44), background_normal="", background_down="",
                                background_color=VERT_CLAIR, color=VERT)
        self.vib.bind(state=self._vib)
        c.add_widget(self.vib)
        b.add_widget(c)

        s = Carte()
        s.add_widget(lbl("[b]Sauvegarde[/b]", 17, couleur=VERT))
        s.add_widget(lbl("Faites une sauvegarde régulièrement pour ne rien perdre "
                         "(changement de téléphone...).", 14))
        s.add_widget(bouton("Exporter dans un fichier", self.exporter_fichier))
        s.add_widget(bouton("Copier la sauvegarde (presse-papiers)", self.exporter_presse,
                            couleur=VERT_CLAIR, couleur_texte=VERT))
        s.add_widget(lbl("Restaurer remplace toutes les données actuelles.", 13, couleur=GRIS))
        s.add_widget(bouton("Restaurer depuis le fichier", self.importer_fichier, couleur=OR))
        s.add_widget(bouton("Restaurer depuis le presse-papiers", self.importer_presse,
                            couleur=OR))
        b.add_widget(s)

        a = Carte()
        a.add_widget(lbl("[b]À propos[/b]", 17, couleur=VERT))
        a.add_widget(lbl("Fatelikou – pour ne jamais oublier nos défunts dans nos invocations. "
                         "Toutes les données restent sur votre téléphone.", 14))
        b.add_widget(a)

    def rafraichir(self):
        self.freq.text = self.app.libelle_frequence()
        self.vib.state = "normal" if self.db.reglage("vibration") == "1" else "down"

    def _freq(self, sp_, texte):
        for f, j in FREQUENCES:
            if f == texte:
                self.db.set_reglage("frequence_jours", j)

    def _vib(self, w, etat):
        actif = etat == "normal"
        self.db.set_reglage("vibration", "1" if actif else "0")
        w.text = f"Vibration du compteur : {'oui' if actif else 'non'}"

    # -- sauvegarde
    def _chemin(self):
        dossier = None
        if platform == "android":
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([Permission.WRITE_EXTERNAL_STORAGE,
                                     Permission.READ_EXTERNAL_STORAGE])
            except Exception:
                pass
            try:
                from android.storage import primary_external_storage_path
                dossier = os.path.join(primary_external_storage_path(), "Download")
            except Exception:
                dossier = None
        if not dossier or not os.path.isdir(dossier):
            dossier = os.path.expanduser("~") if platform != "android" else self.app.user_data_dir
        return os.path.join(dossier, "fatelikou_sauvegarde.json")

    def exporter_fichier(self):
        chemin = self._chemin()
        try:
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(self.db.exporter())
        except OSError:
            chemin = os.path.join(self.app.user_data_dir, "fatelikou_sauvegarde.json")
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(self.db.exporter())
        popup_info("Sauvegarde faite", f"Fichier enregistré :\n{chemin}")

    def exporter_presse(self):
        Clipboard.copy(self.db.exporter())
        popup_info("Copié", "La sauvegarde est copiée. Collez-la dans une note, un e-mail "
                            "ou un message pour la garder en lieu sûr.")

    def _importer(self, texte):
        def faire():
            try:
                n = self.db.importer(texte)
                popup_info("Restauration faite", f"{n} défunt(s) restauré(s).")
            except Exception as e:
                popup_info("Erreur", f"Restauration impossible : {e}")
        popup_confirmer("Restaurer", "Remplacer toutes les données actuelles par la sauvegarde ?",
                        faire, "Restaurer", couleur=OR)

    def importer_fichier(self):
        chemin = self._chemin()
        if not os.path.exists(chemin):
            alt = os.path.join(self.app.user_data_dir, "fatelikou_sauvegarde.json")
            chemin = alt if os.path.exists(alt) else chemin
        try:
            with open(chemin, encoding="utf-8") as f:
                self._importer(f.read())
        except OSError:
            popup_info("Introuvable", f"Aucun fichier de sauvegarde trouvé ici :\n{chemin}")

    def importer_presse(self):
        texte = Clipboard.paste() or ""
        if not texte.strip():
            popup_info("Vide", "Le presse-papiers est vide. Copiez d'abord votre sauvegarde.")
            return
        self._importer(texte)


# ---------------------------------------------------------- application
class Navigation(BoxLayout):
    def __init__(self, app, **kw):
        super().__init__(size_hint_y=None, height=dp(60), **kw)
        fond(self, CARTE)
        self.app = app
        self.boutons = {}
        for nom, texte in (("accueil", "Accueil"), ("arbre", "Mes défunts"),
                           ("reglages", "Réglages")):
            b = Button(text=texte, background_normal="", background_color=CARTE, color=GRIS,
                       font_size=sp(15), bold=True)
            b.bind(on_release=lambda w, n=nom: app.onglet(n))
            self.boutons[nom] = b
            self.add_widget(b)

    def activer(self, nom):
        for n, b in self.boutons.items():
            b.color = VERT if n == nom else GRIS
            b.background_color = VERT_CLAIR if n == nom else CARTE


class FatelikouApp(App):
    title = "Fatelikou"

    def build(self):
        if platform not in ("android", "ios"):
            Window.size = (430, 860)        # format téléphone pour tester sur PC
        Window.clearcolor = FOND
        Window.softinput_mode = "below_target"
        Window.bind(on_keyboard=self._touche)
        self.db = Base(os.path.join(self.user_data_dir, "fatelikou.db"))
        self.historique = []
        self.sm = ScreenManager(transition=SlideTransition(duration=0.18))
        for cls, nom in ((Accueil, "accueil"), (Arbre, "arbre"), (Fiche, "fiche"),
                         (Formulaire, "formulaire"), (Priere, "priere"),
                         (Reglages, "reglages")):
            self.sm.add_widget(cls(self, name=nom))
        racine = BoxLayout(orientation="vertical")
        racine.add_widget(self.sm)
        self.nav = Navigation(self)
        racine.add_widget(self.nav)
        self.nav.activer("accueil")
        return racine

    def on_start(self):
        self.sm.current_screen.rafraichir()

    def on_pause(self):
        return True

    def on_resume(self):
        # au retour dans l'appli (le lendemain par ex.), on remet les rappels à jour
        self.sm.current_screen.rafraichir()

    # -- navigation
    def ecran(self, nom):
        return self.sm.get_screen(nom)

    def aller(self, nom, remplacer=False):
        if not remplacer and self.sm.current != nom:
            self.historique.append(self.sm.current)
        self.sm.transition.direction = "left"
        if self.sm.current == nom:
            self.sm.current_screen.rafraichir()
        self.sm.current = nom
        if nom in self.nav.boutons:
            self.nav.activer(nom)

    def onglet(self, nom):
        self.historique.clear()
        self.sm.transition.direction = "left"
        self.sm.current = nom
        self.sm.current_screen.rafraichir()
        self.nav.activer(nom)

    def retour(self):
        if not self.historique:
            if self.sm.current != "accueil":
                self.onglet("accueil")
                return True
            return False
        nom = self.historique.pop()
        self.sm.transition.direction = "right"
        self.sm.current = nom
        if nom in self.nav.boutons:
            self.nav.activer(nom)
        return True

    def _touche(self, window, touche, *a):
        if touche == 27:            # bouton « retour » d'Android / Échap
            return self.retour()
        return False

    def ouvrir_fiche(self, did, remplacer=False):
        self.ecran("fiche").did = did
        self.aller("fiche", remplacer)

    def ouvrir_formulaire(self, did=None, groupe_id=None):
        self.ecran("formulaire").preparer(did, groupe_id)
        self.aller("formulaire")

    def ouvrir_priere(self, ids):
        if not ids:
            return
        self.ecran("priere").demarrer(ids)
        self.aller("priere")

    # -- divers
    def libelle_frequence(self):
        j = self.db.frequence
        return next((f for f, n in FREQUENCES if n == j), f"Tous les {j} jours")

    def vibrer(self, duree):
        if self.db.reglage("vibration") != "1" or platform != "android":
            return
        try:
            from plyer import vibrator
            vibrator.vibrate(duree)
        except Exception:
            pass


if __name__ == "__main__":
    FatelikouApp().run()
