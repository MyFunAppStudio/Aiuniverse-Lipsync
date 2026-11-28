# -*- coding: utf-8 -*-
"""Geschichte rein, Szenen raus.

Stefan fuegt seinen Text ein. Dieses Modul zerlegt ihn in Szenen und
erzeugt zu jeder Szene ein Bild - mit fester Figur, wenn eine gewaehlt ist.
Danach liegt alles im ganz normalen Szenen-Editor und wird vom selben
Renderer gebaut wie alles andere.
"""
import os
import re
import time

BASIS = os.path.dirname(os.path.abspath(__file__))

ENDE = re.compile(r"(?<=[.!?…])\s+")
KURZ = 5        # weniger Woerter -> mit dem Nachbarn zusammen, wenn es passt
LANG = 16       # mehr Woerter -> am Komma teilen
VOLL = 14       # so lang darf eine Szene nach dem Zusammenlegen hoechstens sein

STILE = [["", "ohne Vorgabe"],
         ["maerchen", "Maerchen, warm gemalt"],
         ["comic", "Comic, klare Linien"],
         ["foto", "fotorealistisch"],
         ["3d", "3D, weich beleuchtet"],
         ["aquarell", "Aquarell"],
         ["dunkel", "dunkel und stimmungsvoll"]]
STIL_TEXT = {
    "maerchen": "Kinderbuch-Illustration, warme Farben, weiches Licht, gemalt",
    "comic": "Comic-Illustration, klare schwarze Linien, kraeftige Flaechen",
    "foto": "fotorealistisch, natuerliches Licht, scharfe Tiefenschaerfe",
    "3d": "3D-Render, weiche Beleuchtung, freundliche Formen",
    "aquarell": "Aquarell, weiche Raender, helles Papier",
    "dunkel": "dunkle Stimmung, harter Schatten, kuehles Licht",
}


def _woerter(s):
    return [w for w in re.split(r"\s+", (s or "").strip()) if w]


KLAMMER = re.compile(r"\(([^()]{2,}?)\)", re.S)


def _sauber(s):
    return " ".join((s or "").split())


def zerlege(text, hoechstens=40):
    """Macht aus einem Text eine Liste von Szenen.

    Drei Stufen, von ausdruecklich zu bequem:
    1. Klammern bestimmen die Szenen, wenn welche gesetzt sind
    2. sonst trennen Leerzeilen die Szenen
    3. sonst wird Satz fuer Satz zerlegt, wie frueher
    """
    ganz = (text or "").replace("\r", "")

    gruppen = [_sauber(g) for g in KLAMMER.findall(ganz)]
    gruppen = [g for g in gruppen if g]
    # Eine einzelne Klammer ist eine Szene. Frueher wurden erst zwei
    # anerkannt, und die eine wurde an Kommas und Punkten zerrissen -
    # der Bildtext wurde dabei zu eigenen Szenen.
    if gruppen:
        return _in_den_clip(gruppen, hoechstens)

    bloecke = [_sauber(b) for b in re.split(r"\n[ \t]*\n", ganz)]
    bloecke = [b for b in bloecke if b]
    if len(bloecke) >= 2:
        return _in_den_clip(bloecke, hoechstens)

    roh = [s.strip() for s in ENDE.split(ganz) if s.strip()]
    # Absatzumbrueche trennen ebenfalls
    teile = []
    for s in roh:
        for t in re.split(r"\n{2,}", s):
            t = " ".join(t.split())
            if t:
                teile.append(t)

    # zu lange Saetze am Komma teilen
    mittel = []
    for s in teile:
        if len(_woerter(s)) <= LANG:
            mittel.append(s)
            continue
        stuecke = [x.strip() for x in re.split(r",\s+", s) if x.strip()]
        if len(stuecke) < 2:
            mittel.append(s)
            continue
        puffer = ""
        for st in stuecke:
            kandidat = (puffer + ", " + st).strip(", ") if puffer else st
            if len(_woerter(kandidat)) > LANG and puffer:
                mittel.append(puffer)
                puffer = st
            else:
                puffer = kandidat
        if puffer:
            mittel.append(puffer)

    # zu kurze Saetze anhaengen, aber nur solange die Szene nicht zu voll wird
    raus = []
    for s in mittel:
        kurz = len(_woerter(s)) < KURZ
        if raus and kurz and len(_woerter(raus[-1])) + len(_woerter(s)) <= VOLL:
            raus[-1] = raus[-1] + " " + s
        else:
            raus.append(s)
    # und falls der erste zu kurz blieb
    if len(raus) > 1 and len(_woerter(raus[0])) < KURZ \
            and len(_woerter(raus[0])) + len(_woerter(raus[1])) <= VOLL:
        raus[1] = raus[0] + " " + raus[1]
        raus.pop(0)
    return _in_den_clip(raus, hoechstens)


_CLIP_ECKIG = re.compile(r"\[([^\[\]]*)\]")
_CLIP_NAME = re.compile(r"^([^:]{1,24}):\s*")


def _in_den_clip(szenen, hoechstens):
    """Jede Szene muss in 15 Sekunden gesprochen sein.

    Was darüber liegt, wird die nächste Szene, mit demselben Bild.
    """
    raus = []
    for s in szenen:
        raus.extend(_clip_stueck(s))
        if len(raus) >= hoechstens:
            break
    return raus[:hoechstens]


def _clip_stueck(satz, grenze=36):
    """Eine Klammer bleibt eine Szene, solange sie in 15 Sekunden passt.

    36 Woerter sind knapp unter 15 Sekunden. Frueher wurden bei 22 Woertern
    und bei zwei Sprechern aus 3 Szenen 6. Mehrere Namen in einer Klammer
    bleiben zusammen.
    """
    ganz = str(satz or "")
    klammern = [k.strip() for k in _CLIP_ECKIG.findall(ganz) if k.strip()]
    rest = _CLIP_ECKIG.sub(" ", ganz)
    auf = rest.find("[")
    if auf >= 0:
        rest = rest[:auf]
    rest = " ".join(rest.split())
    anhang = "".join(" [%s]" % k for k in klammern)
    if len(rest.split()) <= grenze:
        return [(rest + anhang).strip() or ganz]
    # Nicht in eine weitere Szene schneiden. Sonst werden aus 2 Szenen 3,
    # und das Bild des Ereignisses geht dabei verloren.
    return [(rest + anhang).strip() or ganz]


def bildprompt(satz, stil="", figur_name="", zusatz=""):
    """Baut aus einem Erzaehlsatz eine Bildbeschreibung."""
    teile = []
    # eckige Klammern fallen weg, ihr Inhalt bleibt als Beschreibung stehen
    s = " ".join(str(satz or "").replace("[", " ").replace("]", " ").split())
    if figur_name:
        teile.append("%s in dieser Szene: %s" % (figur_name, s))
    else:
        teile.append(s)
    st = STIL_TEXT.get((stil or "").strip().lower())
    if st:
        teile.append(st)
    if (zusatz or "").strip():
        teile.append(zusatz.strip())
    teile.append("keine Schrift im Bild, kein Text, kein Wasserzeichen")
    return ", ".join(teile)


TRENNER = re.compile(r"^[ \t]*#{3,}[ \t]*$", re.M)


def teile_trennen(text):
    """Zerlegt eine Serie an den ###-Zeilen in einzelne Teile."""
    roh = TRENNER.split(text or "")
    return [x.strip() for x in roh if x and x.strip()]


def ist_trenner(satz):
    """Eine Szene, die nur aus ### besteht, ist keine Szene sondern eine Naht."""
    s = (satz or "").strip()
    return bool(s) and set(s) == {"#"} and len(s) >= 3


def aus_paket(paket):
    """Macht aus dem Paket der Text-KI einen Text in Klammerschreibweise.

    Die Text-KI liefert je Szene einen gesprochenen Satz und eine
    Bildbeschreibung. Der Satz kommt in runde Klammern, die Bildbeschreibung
    als Regieanweisung in eckige. Damit ist der Text sofort brauchbar.
    """
    p = paket or {}
    paare = []
    szenen = p.get("szenen") or []
    if szenen:
        for s in szenen:
            if isinstance(s, dict):
                paare.append((_sauber(s.get("text") or ""), _sauber(s.get("bild") or "")))
    else:
        # Rettungsweg: nur skript und bild_prompts gekommen
        saetze = [x for x in ENDE.split(_sauber(p.get("skript") or "")) if x.strip()]
        bildliste = [str(x) for x in (p.get("bild_prompts") or [])]
        for i, satz in enumerate(saetze):
            paare.append((_sauber(satz),
                          _sauber(bildliste[i]) if i < len(bildliste) else ""))
    zeilen = []
    for satz, bild in paare:
        if not satz:
            continue
        if ist_trenner(satz):
            zeilen.append("###")
            continue
        zeilen.append("(%s%s)" % (satz, (" [%s]" % bild) if bild else ""))
    return "\n\n".join(zeilen)


def vorschlag(kanal, thema=""):
    """Laesst die Text-KI schreiben. Gibt den fertigen Text zurueck, nichts wird gespeichert."""
    try:
        import text_generator
    except Exception as e:
        return {"ok": False, "fehler": "Text-Generator nicht nutzbar: %s" % e}
    try:
        paket = text_generator.erzeuge_paket(kanal, (thema or "").strip() or None)
    except Exception as e:
        return {"ok": False, "fehler": str(e)[:300]}
    text = aus_paket(paket)
    if not text:
        return {"ok": False, "fehler": "Die Text-KI hat nichts Brauchbares geliefert"}
    teile = teile_trennen(text)
    return {"ok": True, "text": text,
            "titel": (paket or {}).get("titel") or "",
            "teile": len(teile),
            "szenen": len(zerlege(text))}


def aufbauen(kanal, text, melde=None):
    """Zerlegt den Text, erzeugt die Bilder, legt die Szenen an.

    melde(nr, gesamt, zustand) wird bei jedem Schritt gerufen, falls gegeben.
    Gibt eine Zusammenfassung zurueck.
    """
    import bilder
    import szenen

    saetze = zerlege(text)
    if not saetze:
        return {"ok": False, "fehler": "Kein Text erkannt"}

    ok, grund = bilder.bereit(kanal)
    if not ok:
        return {"ok": False, "fehler": grund}

    figur = (kanal.get("geschichte_figur") or "").strip()
    referenz = bilder.figur_referenz(kanal, figur) if figur else None
    if figur and not referenz:
        print("[Geschichte] Figur '%s' hat kein Bild - wird ohne Vorlage erzeugt" % figur)
    kann, _feld = bilder.kann_figur(kanal)
    if referenz and not kann:
        print("[Geschichte] Das Bildmodell nimmt keine Vorlage. "
              "Fuer gleiche Figur in jeder Szene ein Modell wie "
              "fal-ai/instant-character eintragen.")

    stil = kanal.get("geschichte_stil") or ""
    zusatz = kanal.get("stil_zusatz") or ""
    seite = kanal.get("format") or "9:16"
    ordner = szenen.ordner(kanal)
    os.makedirs(ordner, exist_ok=True)

    # alte Szenen weg, damit nichts durcheinander geht
    d = szenen.laden(kanal)
    d["szenen"] = []
    szenen.speichern(kanal, d)

    gemacht, fehlend = 0, 0
    stempel = time.strftime("%H%M%S")
    for i, satz in enumerate(saetze):
        if melde:
            melde(i + 1, len(saetze), "Bild %d von %d" % (i + 1, len(saetze)))
        name = "gs_%s_%02d.png" % (stempel, i + 1)
        ziel = os.path.join(ordner, name)
        prompt = flux_anweisung(kanal, satz, stil=stil, zusatz=zusatz)
        print("[Bild] Szene %d malt: %s" % (i + 1, " ".join(prompt.split())[:140]))
        p = bilder.erzeuge(kanal, prompt, ziel,
                           referenz=referenz, seite=seite)
        if not p:
            print("[Bild] Szene %d noch einmal, gleiche Beschreibung" % (i + 1))
            p = bilder.erzeuge(kanal, prompt, ziel, referenz=None, seite=seite)
        if not p:
            fehlend += 1
            print("[Geschichte] Szene %d ohne Bild uebersprungen" % (i + 1))
            continue
        szenen.hinzufuegen(kanal, name, satz)
        if figur:
            d = szenen.laden(kanal)
            if d["szenen"]:
                d["szenen"][-1]["figur"] = ""      # Figur steckt im Bild, nicht als Aufkleber
                szenen.speichern(kanal, d)
        gemacht += 1

    return {"ok": gemacht > 0, "szenen": gemacht, "ohne_bild": fehlend,
            "saetze": len(saetze),
            "kosten": round(gemacht * bilder.preis_je_bild(kanal), 3)}


# ---------- Nachtrag p35: leeres Themenfeld ----------
# Wer nichts eintippt, will nicht nachdenken muessen. Dann nimmt der
# Schreibknopf das naechste Thema aus der Themenliste des Kanals. Erst wenn
# auch die leer ist, denkt sich die Text-KI selbst etwas aus.

_p35_vorschlag_alt = vorschlag


def vorschlag(kanal, thema=""):
    """Wie bisher, aber mit Thema aus der Liste wenn keins mitkommt."""
    gewaehlt = (thema or "").strip()
    aus_liste = False
    if not gewaehlt:
        try:
            import themen
            gewaehlt = (themen.naechstes(kanal) or "").strip()
            aus_liste = bool(gewaehlt)
        except Exception:
            gewaehlt = ""
    antwort = _p35_vorschlag_alt(kanal, gewaehlt)
    if isinstance(antwort, dict) and antwort.get("ok") and gewaehlt:
        antwort["thema"] = gewaehlt
        antwort["thema_aus_liste"] = aus_liste
    return antwort


# ---------- Nachtrag p84: Bildprompt aus der BILD-Klammer ----------

import re as _p84_re

P84_GANZ = _p84_re.compile(r"\[([^\[\]]{1,2000})\]", _p84_re.S)
P84_OFFEN = _p84_re.compile(r"\[([^\[\]]{1,2000})$", _p84_re.S)
P84_BILD = _p84_re.compile(r"^BILD\s*[:\-]\s*", _p84_re.I)
P84_BEWEG = _p84_re.compile(r"^BEWEGUNG\s*[:\-]\s*", _p84_re.I)

P84_SAUBER = ("keine Schrift im Bild, kein Text, keine Buchstaben, "
              "keine Zahlen, kein Logo, kein Wasserzeichen")


def _p84_klammern(satz):
    """Zerlegt eine Szene in Satz, Bildteile, Bewegungsteile, Namenlose.

    Die fehlende schliessende Klammer wird mitgenommen - die Text-KI
    vergisst sie regelmaessig, und dann stand der halbe Kamerabefehl im
    Bildprompt.
    """
    ganz = str(satz or "")
    roh = [x for x in P84_GANZ.findall(ganz) if x and x.strip()]
    rest = P84_GANZ.sub(" ", ganz)

    offen = P84_OFFEN.search(rest)
    if offen:
        if offen.group(1).strip():
            roh.append(offen.group(1))
        rest = rest[:offen.start()]
    rest = " ".join(rest.replace("[", " ").replace("]", " ").split())

    bild, beweg, ohne = [], [], []
    for x in roh:
        x = " ".join(x.split())
        if P84_BILD.match(x):
            w = P84_BILD.sub("", x).strip()
            if w:
                bild.append(w)
        elif P84_BEWEG.match(x):
            w = P84_BEWEG.sub("", x).strip()
            if w:
                beweg.append(w)
        else:
            ohne.append(x)
    return rest, bild, beweg, ohne


def _platte(kanal):
    """Nur wenn ein Avatar im Video steht, bleibt unten links die Platte frei."""
    try:
        import darsteller
        return bool(darsteller.besetzung(kanal))
    except Exception:
        return False


def _zusatz_tauglich(zusatz):
    """Der alte Stil-Anker hat jeder Szene denselben Angriff vorgeschrieben."""
    z = (zusatz or "").strip()
    niedrig = z.lower()
    if "people charging" in niedrig or "firing or riding" in niedrig:
        return ""
    return z


_STEIN = _p84_re.compile(
    r"(?i)\b(stein\s*platte|steinplatte|podest|felsblock|fels|boulder|"
    r"kn[oö]chel\s*hoch|unten links eine flache)[^.,]{0,40}")


def _ohne_stein(text):
    return " ".join(_STEIN.sub(" ", text or "").split()).strip(" ,.")


def _flux_vorspann(text):
    """Flux malt deutsche Nebensätze schlecht. Das Ereignis steht deshalb Englisch vorne."""
    t = (text or "").lower()
    if any(w in t for w in ("ramm", "bug", "zusammen", "stoss", "stoß", "kollid")):
        return ("TWO ships colliding in a narrow harbor, the bow of one steamship "
                "smashing into the hull of the other freighter, both hulls large "
                "and close, sparks at the impact, brick warehouses and wooden "
                "cranes on the quay behind, not one ship, not a distant liner")
    if any(w in t for w in ("explod", "feuerball", "druckwelle", "blast")):
        return ("a munitions ship exploding in a narrow harbor, a huge white "
                "fireball rising from the ship, a shockwave snapping wooden roofs "
                "and blowing out windows, the ship still visible as the source, "
                "no blood, no bodies")
    return ("the event in this description, large enough to recognize, "
            "not a distant view and not an empty shore")


def bildprompt(satz, stil="", figur_name="", zusatz="", mit_platte=False):
    """Nur der Moment dieser Szene. Keine Steinplatte, die wird zum Felsblock."""
    rest, bild, _beweg, ohne = _p84_klammern(satz)
    kern = _ohne_stein(", ".join(bild) or ", ".join(ohne) or rest)
    gesprochen = _ohne_stein(rest)
    if not kern.strip():
        kern = gesprochen
    teile = [_flux_vorspann(kern + " " + gesprochen)]
    st = STIL_TEXT.get((stil or "").strip().lower())
    if st:
        teile.append(st)
    extra = _zusatz_tauglich(zusatz)
    if extra:
        teile.append(extra)
    teile.append(P84_SAUBER)
    teile.append(
        "Only the one action named below. No second event in the same frame. "
        "No person standing in the foreground looking at the camera. "
        "No pedestal, no stone slab, no boulder. "
        "No text, no letters, no numbers, no logo, no watermark.")
    if gesprochen and gesprochen != kern:
        teile.append(gesprochen)
    if kern:
        teile.append(kern)
    return ", ".join(x for x in teile if x)


_MEDIUM = _p84_re.compile(
    r"^(medium shot at eye level|medium shot|halbtotale|wide shot|establishing shot)\s*,?\s*",
    _p84_re.I)


def grok_bild_anweisung(kanal, satz, gesprochen="", stil="", zusatz=""):
    """Die volle Szenenbeschreibung. Nichts wird auf 80 Woerter gekuerzt."""
    rest, bild, _beweg, ohne = _p84_klammern(satz or "")
    kern = _ohne_stein(", ".join(bild) or ", ".join(ohne) or "")
    kern = _MEDIUM.sub("", kern).strip(" ,.")
    if not kern:
        # Die Bildbeschreibung steht oft ohne [BILD:]-Klammer im Feld.
        # Dann ist sie der ganze Text, nicht der gesprochene Satz.
        kern = _MEDIUM.sub("", _ohne_stein(rest)).strip(" ,.")
    if not kern:
        kern = _MEDIUM.sub("", _ohne_stein(gesprochen or "")).strip(" ,.")
    look = STIL_TEXT.get((stil or "").strip().lower()) or "photorealistic cinematic still"
    extra = _zusatz_tauglich(zusatz)
    teile = [
        "Photorealistic cinematic still. Paint only the description below, exactly that place and that action. "
        "If it names people, those people are in the frame doing that action, large enough to recognize. "
        "Do not replace it with a different event from any other sentence. "
        "No empty room when the description names people. "
        "No person standing idle in the foreground. "
        "No pedestal, no stone slab, no boulder. "
        "Not a distant view and not a mood without the event. "
        "No text, no letters, no numbers, no logo, no watermark.",
        look,
    ]
    if extra:
        teile.append(extra)
    teile.append(kern)
    return " ".join(x for x in teile if x)


def flux_anweisung(kanal, satz, gesprochen="", stil="", zusatz=""):
    """Bildauftrag. Frueher hat ein zweiter Claude-Aufruf auf 40 bis 80 Woerter gekuerzt."""
    return grok_bild_anweisung(kanal, satz, gesprochen, stil, zusatz)


# ---------- Nachtrag g2: Thema abhaken ----------
#
# naechstes() liefert immer das oberste offene Thema, aber erledigt()
# wurde nirgends gerufen. Also stand nach dem Schreiben dasselbe Thema
# wieder oben und der Schreibknopf nahm beim naechsten Mal dasselbe.
# Jetzt wird ein Thema aus der Liste nach erfolgreichem Schreiben
# abgehakt und wandert zu "erledigt".

_g2_vorschlag_alt = vorschlag


def vorschlag(kanal, thema=""):
    antwort = _g2_vorschlag_alt(kanal, thema)
    if (isinstance(antwort, dict) and antwort.get("ok")
            and antwort.get("thema_aus_liste") and antwort.get("thema")):
        try:
            import themen
            themen.erledigt(kanal, antwort["thema"])
        except Exception as e:
            print("[Geschichte] Thema nicht abgehakt:", e)
    return antwort


# ---------- Nachtrag g8: Bewegung je Szene mitschreiben ----------
#
# Die Text-KI lieferte je Szene nur Satz und Bild. Die
# Animationsanweisung blieb leer, und Stefan haette sie bei jeder
# einzelnen Szene selbst eintippen muessen. Jetzt wird auch sie
# abgefragt und als eigene, benannte Klammer in den Text geschrieben -
# szenen.r13_trennen() sortiert sie danach ins richtige Feld.

_g8_aus_paket_alt = aus_paket


def aus_paket(paket):
    p = paket or {}
    szenen_ = p.get("szenen") or []
    hat_bewegung = any(isinstance(s, dict) and (s.get("bewegung") or "").strip()
                       for s in szenen_)
    if not hat_bewegung:
        return _g8_aus_paket_alt(paket)

    zeilen = []
    for s in szenen_:
        if not isinstance(s, dict):
            continue
        satz = _sauber(s.get("text") or "")
        if not satz:
            continue
        if ist_trenner(satz):
            zeilen.append("###")
            continue
        bild = _sauber(s.get("bild") or "")
        beweg = _sauber(s.get("bewegung") or "")
        teile = [satz]
        if bild:
            teile.append("[BILD: %s]" % bild)
        if beweg:
            teile.append("[BEWEGUNG: %s]" % beweg)
        zeilen.append("(%s)" % " ".join(teile))
    return "\n\n".join(zeilen)


# ---------- Nachtrag g9: wer im Bild steht mitschreiben ----------
#
# Claude liefert je Szene jetzt auch, welche Figuren zu sehen sind.
# Das wandert als benannte Klammer in den Text, damit es den Weg bis
# in die Szene uebersteht - genauso wie BILD und BEWEGUNG.

_g9_aus_paket_alt = aus_paket


def _g9_wer_text(s):
    w = s.get("wer")
    if isinstance(w, str):
        w = [x.strip() for x in w.split(",")]
    if not isinstance(w, list):
        return None
    namen = [str(x).strip() for x in w if str(x).strip()]
    return ", ".join(namen) if namen else ""


def aus_paket(paket):
    p = paket or {}
    szenen_ = p.get("szenen") or []
    hat_wer = any(isinstance(s, dict) and _g9_wer_text(s) is not None
                  for s in szenen_)
    if not hat_wer:
        return _g9_aus_paket_alt(paket)

    zeilen = []
    for s in szenen_:
        if not isinstance(s, dict):
            continue
        satz = _sauber(s.get("text") or "")
        if not satz:
            continue
        if ist_trenner(satz):
            zeilen.append("###")
            continue
        teile = [satz]
        bild = _sauber(s.get("bild") or "")
        beweg = _sauber(s.get("bewegung") or "")
        wer = _g9_wer_text(s)
        if bild:
            teile.append("[BILD: %s]" % bild)
        if beweg:
            teile.append("[BEWEGUNG: %s]" % beweg)
        if wer is not None:
            teile.append("[IM BILD: %s]" % (wer or "niemand"))
        zeilen.append("(%s)" % " ".join(teile))
    return "\n\n".join(zeilen)


# ---------- Nachtrag: gleicher Knopf, anderer Text ----------
# Bleibt das Thema im Feld stehen, soll der naechste Druck nicht
# dieselbe Fassung noch einmal liefern.

_neu_vorschlag_alt = vorschlag


def vorschlag(kanal, thema="", bisher="", quelle=""):
    alt = " ".join(str(bisher or "").split())
    q = " ".join(str(quelle or "").split())[:8000]
    if isinstance(kanal, dict) and (alt or q):
        kanal = dict(kanal)
        extra = ""
        if q:
            extra += (
                "\n\nQUELLE:\n"
                "Der Nutzer hat einen Text zu diesem Thema hineinkopiert. "
                "Das ist die Faktengrundlage, nicht das Drehbuch und nicht zum Abschreiben.\n"
                "Uebernimm daraus Namen, Orte, Jahreszahlen und Zahlen. "
                "Erfinde keine Zahl und kein Zitat, das weder in der Quelle steht "
                "noch allgemein bekannt ist. Bekannte Fakten, die zur Sache gehoeren "
                "und in der Quelle fehlen, darfst du ergaenzen.\n"
                "Schreibe daraus kurze Szenen. Jede Szene ein eigener Moment.\n"
                "-----\n%s\n-----" % q)
        if alt:
            extra += (
                "\n\nNEUER VERSUCH:\n"
                "Zu diesem Thema liegt schon eine Fassung vor. Schreibe eine andere. "
                "Anderer erster Satz, andere Szenen, andere Formulierungen. "
                "Dieselbe Fassung noch einmal ist falsch. Die Fakten aus der Quelle bleiben.\n"
                "Die alte Fassung, nicht wiederholen:\n" + alt[:1200])
        kanal["prompt"] = (kanal.get("prompt") or "") + extra
    return _neu_vorschlag_alt(kanal, thema)
