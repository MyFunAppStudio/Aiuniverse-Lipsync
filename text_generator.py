# ============================================
# Text-Generator: Skript, Titel, Beschreibung
# ============================================
import json
import urllib.request
from pathlib import Path
import config
import einstellungen

ZEICHEN_PRO_SEKUNDE = 9.0  # ZPS_KORRIGIERT (vorher 15.0)  # gesprochene Zeichen pro Sekunde


def _claude_anfrage(prompt, max_tokens=20000, kanal=None):
    """Fragt Claude ueber die API. Key kommt aus dem Dashboard."""
    api = einstellungen.aktive_api(kanal, "text") if kanal else None
    schluessel = ((api or {}).get("key") or config.ANTHROPIC_KEY or "").strip()
    basis = ((api or {}).get("url") or "https://api.anthropic.com").strip()
    if not schluessel:
        raise RuntimeError("Kein Anthropic-Key im Dashboard eingetragen (Kanal -> APIs -> TEXT)")
    modelle = ["claude-sonnet-4-5", "claude-opus-4-5", "claude-haiku-4-5",
               "claude-3-5-sonnet-latest"]
    letzter = None
    for modell in modelle:
        daten = json.dumps({
            "model": modell,
            "max_tokens": max_tokens,
            "temperature": 1,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        anfrage = urllib.request.Request(
            basis.rstrip("/") + "/v1/messages",
            data=daten,
            headers={
                "x-api-key": schluessel,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        )
        try:
            with urllib.request.urlopen(anfrage, timeout=600) as antwort:
                ergebnis = json.loads(antwort.read().decode())
            print(f"[Text] Modell: {modell}")
            return ergebnis["content"][0]["text"]
        except urllib.error.HTTPError as f:
            leib = f.read().decode()[:200]
            letzter = f"{f.code}: {leib}"
            if f.code in (404, 400, 503):
                continue
            raise RuntimeError(f"Anthropic Fehler {letzter}")
    raise RuntimeError(f"Kein Modell nutzbar. Letzter Fehler: {letzter}")


def lade_prompt(kanal):
    """Laedt den Master-Prompt aus dem regeln-Ordner."""
    datei = config.ORDNER_REGELN / f"prompt_{kanal['id']}.txt"
    if datei.exists():
        return datei.read_text(encoding="utf-8")
    return f"Du bist Erzaehler fuer den Kanal {kanal['name']}."


def lade_regeln(kanal):
    """Laedt die Regeln aus dem regeln-Ordner."""
    datei = config.ORDNER_REGELN / f"regeln_{kanal['id']}.txt"
    if datei.exists():
        return datei.read_text(encoding="utf-8")
    return ""


def _test_paket(kanal):
    """Platzhalter-Text fuer den Testmodus."""
    return {
        "titel": f"[TEST] Beispiel-Titel fuer {kanal['name']}",
        "skript": (
            "Das ist ein Testskript. Es simuliert was Claude spaeter schreibt. "
            "Hook in den ersten Sekunden. Dann der Aufbau. "
            "Dann die Wendung. Am Ende der Aufruf zu folgen."
        ),
        "bild_prompts": [
            "Test-Bild 1: dunkle Strasse bei Nacht",
            "Test-Bild 2: verlassenes Haus",
            "Test-Bild 3: Nahaufnahme eines Briefes",
        ],
        "beschreibung_youtube": "[TEST] YouTube Beschreibung mit Hook und CTA.",
        "beschreibung_tiktok": "[TEST] TikTok Text #test #fyp",
        "beschreibung_instagram": "[TEST] Instagram Caption #test",
        "hashtags": ["#test", "#beispiel", "#fyp"],
        "pinned_comment": "[TEST] Welches Thema als naechstes?",
    }


def erzeuge_paket(kanal, eigenes_thema=None):
    """Erzeugt das komplette Text-Paket fuer EIN Video."""
    if config.TESTMODUS:
        print(f"[Text] {kanal['name']}: TESTMODUS -> Platzhalter")
        return _test_paket(kanal)

    laenge = einstellungen.laenge_in_minuten(kanal)
    anzahl_bilder = max(1, int(round(laenge * kanal["bilder_pro_minute"])))
    _je = min(9.0, (laenge * 60.0) / max(1, anzahl_bilder))
    _wps = _p37_wps(kanal)
    _unten = max(4, int(_je * _wps * 0.85))
    _oben = max(_unten + 1, int(_je * _wps))

    prompt = f"""{lade_prompt(kanal)}

REGELN:
{lade_regeln(kanal)}

AUFGABE:
Erstelle EIN komplettes Video-Paket.
Sprache: {', '.join(kanal.get('sprachen', ['Deutsch']))}
Laenge: ca. {laenge*60:.0f} Sekunden gesprochen\n{_tl_hinweis(kanal)}Das SKRIPT hat genau {anzahl_bilder} Szenen. Jede Szene hat {_unten} bis {_oben} Woerter, in ein bis drei Saetzen. Das sind hoechstens 9 Sekunden. Der Clip ist 10 Sekunden und kann nicht laenger. Was darueber liegt, bleibt als Standbild stehen. Lieber kuerzer als laenger. SUBSTANZ: In JEDER Szene steht mindestens eine harte Angabe - ein Name, ein Ort, ein Datum, eine Zahl, ein Ergebnis. Keine Szene, die nur Stimmung macht, etwas ankuendigt oder wiederholt, was schon gesagt wurde. Am Ende muss jemand, der das Video gesehen hat, das Ereignis erklaeren koennen: wer, wo, wann, warum, wie es ausging und was danach anders war.
{P49_THEMA % eigenes_thema if eigenes_thema else "Waehle selbst ein passendes Thema."}

Bildbeschreibungen je maximal 120 Zeichen. Beschreibungen je maximal 400 Zeichen.\n\nBILDER - SEHR WICHTIG: Jedes Bild zeigt den MOMENT, von dem die Szene erzaehlt - Menschen, Ort und Handlung, nicht ein Ding davon und nicht einen leeren Weg. Geht es um Krieg, sind Soldaten im Bild und man sieht den Kampf, den Aufmarsch oder die Attacke. JEDES Bild ein anderer Moment. Bildbeschreibungen auf Englisch. Das Bild ist der HINTERGRUND, in den spaeter ein Avatar gestellt wird: nur unten links ein Streifen Boden frei, der Rest ist das Ereignis. Nicht "wide shot" und nicht "aerial view". Gut: "medium shot at eye level, infantry in blue coats firing through smoke, cavalry crossing behind them, muddy grass only in the lower left".\n\nBEWEGUNG: Zu jeder Szene gehoert ein kurzer Satz, was sich bewegt. Deutsch, hoechstens 15 Woerter. Die Handlung im Hintergrund, nicht die Kamera. Keine Schnitte.

Antworte NUR mit JSON, ohne Erklaerung, ohne Markdown.
Teile die Geschichte in {anzahl_bilder} SZENEN. Jede Szene hat ihren eigenen
Text UND das Bild das GENAU dazu passt. Das Bild zeigt was in diesem Moment
erzaehlt wird - nicht irgendein allgemeines Motiv.

{{
  "titel": "...",
  "szenen": [
    {{"text": "gesprochener Text dieser Szene",
      "bild": "englische Bildbeschreibung die genau zu diesem Text passt",
      "bewegung": "was sich im Bild bewegt, auf Deutsch, ein kurzer Satz",
      "wer": ["Namen der Figuren, die in diesem Bild zu sehen sind, sonst leere Liste"]}}
  ],
  "beschreibung_youtube": "...",
  "beschreibung_tiktok": "...",
  "beschreibung_instagram": "...",
  "hashtags": ["#...", "#..."],
  "pinned_comment": "..."
}}"""

    print(f"[Text] {kanal['name']}: frage Claude...")
    antwort = _claude_anfrage(prompt, kanal=kanal)
    antwort = antwort.strip()
    if "```" in antwort:
        teile = antwort.split("```")
        if len(teile) > 1:
            antwort = teile[1]
        if antwort.startswith("json"):
            antwort = antwort[4:]
    antwort = antwort.strip()
    a, b = antwort.find("{"), antwort.rfind("}")
    if a >= 0 and b > a:
        antwort = antwort[a:b+1]
    def _aus_szenen(d):
        """Baut skript und bild_prompts aus den Szenen."""
        sz = d.get("szenen") or []
        if sz:
            d["skript"] = " ".join((x.get("text") or "").strip() for x in sz).strip()
            d["bild_prompts"] = [(x.get("bild") or "").strip() for x in sz if x.get("bild")]
        d.setdefault("skript", "")
        d.setdefault("bild_prompts", [])
        return d

    try:
        return _aus_szenen(_p40_json(antwort))
    except json.JSONDecodeError as f:
        print("[Text] JSON unvollstaendig - versuche Rettung...")
        import re
        d = {}
        for feld in ["titel","skript","beschreibung_youtube","beschreibung_tiktok",
                     "beschreibung_instagram","pinned_comment"]:
            t = re.search(r'"' + feld + r'"\s*:\s*"((?:[^"\\]|\\.)*)"', antwort)
            if t:
                d[feld] = t.group(1).replace('\\n','\n').replace('\\"','"')
        b = re.search(r'"bild_prompts"\s*:\s*\[(.*?)\]', antwort, re.S)
        d["bild_prompts"] = re.findall(r'"((?:[^"\\]|\\.)*)"', b.group(1)) if b else []
        h = re.search(r'"hashtags"\s*:\s*\[(.*?)\]', antwort, re.S)
        d["hashtags"] = re.findall(r'"((?:[^"\\]|\\.)*)"', h.group(1)) if h else ["#fyp"]
        for feld in ["titel","skript","beschreibung_youtube","beschreibung_tiktok",
                     "beschreibung_instagram","pinned_comment"]:
            d.setdefault(feld, "")
        if not d["titel"] or not d["skript"] or not d["bild_prompts"]:
            print("[Text] Rettung fehlgeschlagen. Ende der Antwort:", antwort[-150:])
            raise
        print(f"[Text] Gerettet: {len(d['bild_prompts'])} Bilder")
        return d


if __name__ == "__main__":
    print("=" * 45)
    print("TEXT-GENERATOR TEST")
    print("=" * 45)
    for k in config.KANAELE:
        paket = erzeuge_paket(k)
        print(f"\n{k['emoji']} {k['name']}")
        print(f"  Titel:  {paket['titel']}")
        print(f"  Bilder: {len(paket['bild_prompts'])} Prompts")
        print(f"  Skript: {paket['skript'][:60]}...")
    print("\n" + "=" * 45)


# ===== Themenliste (Patch T1) =====
import themen as _tl

_erzeuge_paket_tl = erzeuge_paket


def _tl_hinweis(kanal):
    try:
        return _tl.hinweis(kanal)
    except Exception:
        return ""


def erzeuge_paket(kanal, eigenes_thema=None):
    gewaehlt = (eigenes_thema or "").strip() or None
    if not gewaehlt:
        gewaehlt = _tl.naechstes(kanal)
        if gewaehlt:
            print("  Thema aus der Liste: %s" % gewaehlt)
        else:
            print("  Themenliste leer - Claude waehlt frei")
    d = _erzeuge_paket_tl(kanal, gewaehlt)
    try:
        if d and gewaehlt:
            _tl.erledigt(kanal, gewaehlt)
            rest = len(_tl.laden(kanal)["offen"])
            print("  Thema abgehakt, noch %d offen" % rest)
    except Exception as ex:
        print("  Themenliste: %s" % ex)
    return d


# ---------- Nachtrag p33: Serien ----------
# Ein Fall wird am Stueck geschrieben und danach getrennt. Die KI kennt beim
# Schreiben das Ende und kann die Nahtstellen dahin legen, wo es wehtut.

_p33_prompt_alt = lade_prompt

SERIE_SATZ = """SERIE: Dieser Fall wird in %d Teile geteilt.
Schreibe alle Teile am Stueck, als eine durchgehende Geschichte.
Setze zwischen zwei Teile eine eigene Szene, deren Text nur ### ist
und die keine Bildbeschreibung hat.
Jeder Teil beginnt mit einem eigenen Haken, nicht mit einer Zusammenfassung
des vorigen. Jeder Teil endet mitten im Geschehen, an einer Stelle, wo gerade
etwas Neues aufgetaucht ist.
Teil 1 muss fuer sich allein verstaendlich sein - er bringt die Reichweite.
Jeder Teil ist mindestens 70 Sekunden gesprochen, also kein Teil darf kurz sein."""


def lade_prompt(kanal):
    """Wie bisher, plus Serienanweisung wenn der Kanal eine Serie baut."""
    text = _p33_prompt_alt(kanal)
    try:
        n = int((kanal or {}).get("serie_teile") or 1)
    except Exception:
        n = 1
    if n > 1 and "SERIE:" not in text:
        text = text + "\n\n" + (SERIE_SATZ % n)
    return text


# ---------- Nachtrag p36: Masterprompt aus dem Dashboard + Serie ----------
# Steht absichtlich als letztes in der Datei. Was hier definiert wird, gilt.

_p36_alt_prompt = lade_prompt
try:
    _p36_alt_regeln = lade_regeln
except NameError:
    _p36_alt_regeln = None

P36_FIGUR = ("Wenn %s etwas sagt, schreibe es in Anfuehrungszeichen mitten in "
             "den Satz. Alles ohne Anfuehrungszeichen spricht der Erzaehler.")

P36_SERIE = """=== SERIE: DIESER FALL WIRD IN %(n)d TEILE GETEILT ===
Das ist die wichtigste Regel dieses Auftrags.

Schreibe alle %(n)d Teile am Stueck als EINE durchgehende Geschichte.

Zwischen zwei Teilen steht eine eigene, zusaetzliche Szene als Trenner:
- ihr gesprochener Text ist genau ### und sonst gar nichts
- ihre Bildbeschreibung ist genau: black screen
Anzahl dieser Trennerszenen: %(t)d. Ohne sie ist der Auftrag nicht
erfuellt. Schreibe sonst nirgends ### hin.

Jeder Teil faengt mit einem eigenen Haken an, nicht mit einer
Zusammenfassung des vorigen, und endet mitten im Geschehen an einer
Stelle, wo gerade etwas Neues aufgetaucht ist.
Teil 1 muss fuer sich allein verstaendlich sein - er bringt die Reichweite.
Jeder Teil ist mindestens 70 Sekunden gesprochen. Kein Teil darf kurz sein."""


def _p36_teile(kanal):
    try:
        n = int((kanal or {}).get("serie_teile") or 1)
    except Exception:
        n = 1
    return n if n > 1 else 1


def lade_prompt(kanal):
    """Dashboard-Feld schlaegt Datei schlaegt Notnagel, dann Figur, dann Serie."""
    k = kanal or {}
    text = (k.get("prompt") or "").strip()
    if not text:
        try:
            text = (_p36_alt_prompt(k) or "").strip()
        except Exception:
            text = ""
    if not text:
        text = "Du bist Erzaehler fuer den Kanal %s." % (k.get("name") or "")

    figur = (k.get("geschichte_figur") or "").strip()
    if figur and "nfuehrungszeichen" not in text and "nf\u00fchrungszeichen" not in text:
        text = text + "\n\n" + (P36_FIGUR % figur)

    n = _p36_teile(k)
    if n > 1 and "SERIE" not in text:
        text = text + "\n\n" + (P36_SERIE % {"n": n, "t": n - 1})
    return text


def lade_regeln(kanal):
    """Regeln: Dashboard-Feld schlaegt Datei."""
    k = kanal or {}
    text = (k.get("regeln") or "").strip()
    if text:
        return text
    if _p36_alt_regeln is None:
        return ""
    try:
        return _p36_alt_regeln(k) or ""
    except Exception:
        return ""


# ---------- Nachtrag p37: Woerter je Sekunde ----------
# 1,8 war geraten. An einem fertigen Video gemessen: 2,65 Woerter je Sekunde
# Video. 2,5 als Vorgabe laesst etwas Luft nach oben, damit ein Teil eher
# zu lang als zu kurz wird. Im Kanal unter woerter_pro_sekunde aenderbar.

P37_STANDARD = 2.5


def _p37_wps(kanal):
    try:
        wert = float((kanal or {}).get("woerter_pro_sekunde") or P37_STANDARD)
    except Exception:
        wert = P37_STANDARD
    if wert < 1.2 or wert > 4.0:
        wert = P37_STANDARD
    return wert


# ---------- Nachtrag p40: JSON mit Anfuehrungszeichen retten ----------
# Ein gerades " mitten in einem Text beendet dort den JSON-Wert. Wir gehen
# Zeichen fuer Zeichen durch und ersetzen nur die Anfuehrungszeichen, auf
# die KEIN Komma, Doppelpunkt oder Klammerende folgt - das sind die, die
# im Text stehen und nicht zum JSON gehoeren.

import json as _p40_json_modul

_P40_STRUKTUR = ":,}]"


def _p40_flicken(text):
    raus = []
    im_string = False
    auf = True
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if not im_string:
            raus.append(c)
            if c == chr(34):
                im_string = True
            i += 1
            continue
        if c == chr(92):
            raus.append(text[i:i + 2])
            i += 2
            continue
        if c == chr(34):
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j >= n or text[j] in _P40_STRUKTUR:
                raus.append(c)
                im_string = False
            else:
                raus.append("\u00bb" if auf else "\u00ab")
                auf = not auf
            i += 1
            continue
        raus.append(c)
        i += 1
    return "".join(raus)


def _p40_json(antwort):
    """Erst normal einlesen, bei Bruch einmal flicken und nochmal."""
    try:
        return _p40_json_modul.loads(antwort)
    except Exception:
        pass
    geflickt = _p40_flicken(antwort)
    try:
        d = _p40_json_modul.loads(geflickt)
        print("[Text] Anfuehrungszeichen im JSON geflickt")
        return d
    except Exception:
        raise _p40_json_modul.JSONDecodeError(
            "JSON auch nach dem Flicken unlesbar", antwort, 0)


# ---------- Nachtrag p49: das Thema durchsetzen ----------
# Eine Zeile reicht nicht, wenn drumherum 6000 Zeichen stehen. Der Absatz
# steht an derselben Stelle wie vorher, nimmt sich aber mehr Platz und sagt
# klar, dass das Thema die Geschichte bestimmt - nicht nur anregt.

P49_THEMA = """=== DAS THEMA DIESES VIDEOS ===
%s

Die Geschichte handelt von genau diesem Thema. Ort, Titel und Geschehen
muessen dazu passen. Steht im Thema ein Ort - ein Moor, ein See, ein
Bahnhof -, dann spielt die Geschichte dort und nicht woanders.
Weiche nicht auf ein anderes Thema aus, auch nicht auf ein aehnliches.
Faellt dir zu dem Thema wenig ein, erfinde mehr Einzelheiten dazu -
aber bleib dabei."""


# ---------- Nachtrag p80: zwei Regeln in den Masterprompt ----------

P80_WOERTER = """WOERTER:
Benutze keine Woerter mit mehr als 14 Buchstaben. Lange zusammengesetzte
Woerter schreibst du auseinander: statt "Haftpflichtversicherungsbeitrag"
schreibst du "Beitrag fuer die Haftpflicht", statt "Lebenshaltungskosten"
schreibst du "was das Leben kostet". Das gilt fuer jeden gesprochenen Satz.
Kurze Woerter versteht man beim Hoeren besser und sie passen in den
Untertitel, ohne dass er getrennt werden muss."""

P80_EINTEILIG = """ENDE:
Diese Geschichte ist mit diesem einen Video zu Ende. Erzaehle sie fertig.
Kuendige keinen naechsten Teil an, schreibe kein "Fortsetzung folgt", kein
"mehr dazu im naechsten Video" und kein offenes Ende. Die letzte Szene
loest auf, worum es ging."""

_p80_prompt_alt = lade_prompt


def lade_prompt(kanal):
    """Wie bisher, dazu die Wortregel - und bei einem Teil die Endregel."""
    text = _p80_prompt_alt(kanal)
    # Auf den genauen Satz pruefen, nicht auf ein Allerweltswort -
    # "Buchstaben" kann in jedem Prompt stehen.
    if "mehr als 14 Buchstaben" not in text:
        text = text + "\n\n" + P80_WOERTER
    try:
        teile = _p36_teile(kanal)
    except Exception:
        teile = 1
    # Bei einem Teil kommt die Endregel immer. Steht im Prompt noch ein
    # Serienrest von frueher, soll sie ihn gerade ueberstimmen - sie steht
    # hinten und gilt damit zuletzt.
    if teile <= 1 and "Kuendige keinen naechsten Teil" not in text:
        text = text + "\n\n" + P80_EINTEILIG
    return text


# ---------- Nachtrag p82: Regieanweisung in den Masterprompt ----------

P82_REGIE = """REGIEANWEISUNG
Hinter jeden gesprochenen Satz setzt du eine Anweisung in eckige Klammern.
Sie wird nicht gesprochen und steht in keinem Untertitel. Sie sagt dem
Modell, das die Szene bewegt, was sich im Bild ruehren soll.

In die Klammern kommt nur, was ein Bild-zu-Video-Modell sauber kann:
Kamera - langsam heranfahren, langsam zurueck, sanft zur Seite ziehen.
Umgebung - Nebel, Rauch, Staub im Licht, Regen, Schnee, Blaetter, Funken.
Licht - flackern, langsam heller werden, Schatten wandert, ein Blitz.
Stoff und Haare - ein Vorhang bewegt sich, ein Mantel weht, Haare im Wind.
Wasser - Wellen, Tropfen, eine Spiegelung zittert.

In die Klammern kommt nie: Personen, die gehen, greifen, sich umdrehen,
die Haende bewegen, den Kopf drehen oder reden. Keine Gesichtsausdruecke.
Menschen im Bild bleiben ruhig - bewegt wird alles um sie herum. Steht
eine Figur im Bild, wird sie in der Klammer nicht erwaehnt.

Eine Klammer je Szene, hoechstens zwoelf Woerter.
Beispiel: Er hatte den Brief nie geoeffnet. [Kamera faehrt langsam heran,
Staub schwebt im Lichtstrahl]"""

_p82_prompt_alt = lade_prompt


def lade_prompt(kanal):
    """Wie bisher, dazu der Regieblock."""
    text = _p82_prompt_alt(kanal)
    if "REGIEANWEISUNG" not in text:
        text = text + "\n\n" + P82_REGIE
    return text


# ---------- Nachtrag p85: Beweisbilder statt Stimmungsbilder ----------

P85_BILD = """BILD UND BEWEGUNG
Hinter jeden gesprochenen Satz setzt du eine Bildbeschreibung in eckige
Klammern, mit BILD davor. Sie wird nicht gesprochen und steht in keinem
Untertitel. Sie ist das, was gemalt wird - also muss sie ein Bild sein und
nicht der Satz noch einmal.

Beispiel: Drei Euro am Tag sind tausend im Jahr.
[BILD: tausend Ein-Euro-Muenzen flach ausgebreitet auf schwarzem Tisch,
von oben, randlos bis zum Bildrand]

SO BAUST DU EIN BILD
Ein Gegenstand, nah dran. Keine Szene mit mehreren Dingen darin.
Die Menge macht die Aussage: nicht eine Muenze, sondern tausend. Nicht
ein Becher, sondern dreihundertfuenfundsechzig. Nicht ein Blatt, sondern
ein kniehoher Stapel.
Nenne Material und Licht: Blech, Papier, nasser Asphalt, Sonne von der
Seite, Neonlicht von oben, eine Lampe im Dunkeln.
Nenne den Blickwinkel: von oben, dicht ueber dem Tisch, aus der Hocke,
von unten.
Acht bis zwanzig Woerter. Jede Szene ein anderer Gegenstand.

WAS NIE INS BILD KOMMT
Keine Schrift, keine Buchstaben, keine Zahlen, keine Logos, keine
Preisschilder, keine Zeitungen, keine Bildschirme mit Text. Daraus werden
unleserliche Zeichen.
Keine Sinnbilder: kein Muenzstapel, kein Sparschwein, keine Kurve, die
nach oben zeigt, kein Eurozeichen, keine Gluehbirne, keine Waage, keine
Hand, die Geldscheine faechert. Das sieht nach Baukasten aus und wird
weggescrollt.
Nichts Abstraktes: Freiheit, Druck, Sicherheit, Zukunft kann man nicht
malen. Nenne den Gegenstand, an dem man es sieht.
Menschen nur, wenn der Satz von einem Menschen handelt - dann ein
Koerperteil nah dran, kein Gesicht, keine ganze Person.

ZWOELF GEGENSTAENDE ALS RICHTUNG
eine offene leere Geldboerse auf einem Beifahrersitz
ein kniehoher Stapel Kontoauszuege, danebengekippt
Pappbecher in Reihen auf dem Boden einer leeren Wohnung
ein Einkaufswagen mit einem einzigen Artikel darin
eine Stechuhr-Karte, durchgestempelt bis nach unten
ein Kassenzettel, zerknuellt auf nassem Asphalt
ein Schluesselbund an einem Nagel in einer kahlen Wand
ein Umzugskarton, halb gepackt, im Flur
zwei Paar Schuhe nebeneinander, eines neu, eines durchgelaufen
Finger auf einer einzigen Zeile im Kleingedruckten
ein Kuehlschrank von innen, fast leer, Licht an
ein Briefkasten, ueberquellend, von unten gesehen

BEWEGUNG
Nur wenn sich im Video etwas ruehren soll, setzt du eine zweite Klammer
mit BEWEGUNG davor. Laesst du sie weg, bleibt das Bild stehen - bei
solchen Bildern ist das meist das Bessere.
In die Bewegungsklammer kommt nur, was ein Bild-zu-Video-Modell sauber
kann: Kamera langsam heran oder zurueck, Staub im Licht, Rauch, Regen,
Licht das flackert, ein Vorhang der sich bewegt, Wasser das zittert.
Nie Personen, die gehen, greifen, sich umdrehen oder reden - daraus wird
Matsch. Hoechstens zwoelf Woerter.

Beispiel mit beidem: Er hatte den Brief nie geoeffnet.
[BILD: ein ungeoeffneter Brief auf einem Holzboden, Staub, Licht von
schraeg oben] [BEWEGUNG: Kamera faehrt langsam heran, Staub schwebt]"""

_p85_prompt_alt = lade_prompt


def lade_prompt(kanal):
    """Wie bisher - der Regieblock aus p82 weicht dem neuen Bildblock.

    Der alte Block verlangte einen Kamerabefehl in denselben Klammern, in
    denen jetzt die Bildbeschreibung steht. Zwei Anweisungen fuer eine
    Klammer waeren ein Widerspruch, darum wird der alte herausgenommen.
    """
    text = _p85_prompt_alt(kanal)
    alt = globals().get("P82_REGIE") or ""
    if alt and alt in text:
        text = text.replace("\n\n" + alt, "")
        text = text.replace(alt, "")
    if "BILD UND BEWEGUNG" not in text:
        text = text.rstrip() + "\n\n" + P85_BILD
    return text


# ---------- Nachtrag p87: vollstaendiger Prompt steht fuer sich ----------

P87_MARKE = "=== AIU PROFI-FORMAT"

_p87_alt = lade_prompt


def lade_prompt(kanal):
    """Traegt der Prompt die Marke, wird nichts mehr angehaengt."""
    k = kanal or {}
    eigen = k.get("prompt") or ""
    if P87_MARKE not in eigen:
        return _p87_alt(k)

    text = eigen.rstrip()

    # Figur und Serie haengen am Kanal, nicht am Format - die bleiben.
    figur = (k.get("geschichte_figur") or "").strip()
    if figur and "nfuehrungszeichen" not in text and "nführungszeichen" not in text:
        try:
            text = text + "\n\n" + (P36_FIGUR % figur)
        except Exception:
            pass
    try:
        n = _p36_teile(k)
    except Exception:
        n = 1
    if n > 1 and "SERIE" not in text:
        try:
            text = text + "\n\n" + (P36_SERIE % {"n": n, "t": n - 1})
        except Exception:
            pass
    return text


# ---------- Nachtrag t2: keine Serienteile mehr ----------
#
# Die Einstellung "Serie: Teile" ist aus dem Dashboard raus. In den
# Kanaldateien steht serie_teile aber noch drin, und solange der
# Generator das liest, schreibt Claude weiter zwei Folgen und der
# Text landet geteilt im Feld. Ein Video ist ein Video.

def _p36_teile(kanal):
    return 1


# ---------- Nachtrag t3: JSON aus der Antwort herausschaelen ----------
#
# "JSON auch nach dem Flicken unlesbar: line 1 column 1 (char 0)"
# heisst: schon das erste Zeichen passt nicht. Das passiert, wenn das
# Modell seine Antwort in einen Markdown-Block packt (```json ... ```)
# oder einen Satz davorstellt - trotz der Bitte, nur JSON zu
# schicken. Vorher ist der ganze Lauf daran gescheitert.
#
# Also: Zaun wegnehmen, und notfalls von der ersten geschweiften
# Klammer bis zur letzten schneiden.

_t3_json_alt = _p40_json


def _t3_schaelen(text):
    s = (text or "").strip()
    if s.startswith("```"):
        z = s.split("\n")
        if z and z[0].startswith("```"):
            z = z[1:]
        while z and not z[-1].strip().startswith("```"):
            if z[-1].strip():
                break
            z = z[:-1]
        if z and z[-1].strip().startswith("```"):
            z = z[:-1]
        s = "\n".join(z).strip()
    a, b = s.find("{"), s.rfind("}")
    if a > 0 or (a == 0 and b < len(s) - 1):
        if a >= 0 and b > a:
            s = s[a:b + 1]
    return s


def _p40_json(antwort):
    try:
        return _t3_json_alt(antwort)
    except Exception:
        pass
    geschaelt = _t3_schaelen(antwort)
    if geschaelt and geschaelt != (antwort or "").strip():
        print("[Text] Antwort war verpackt - JSON herausgeschaelt")
        return _t3_json_alt(geschaelt)
    raise _p40_json_modul.JSONDecodeError(
        "Die Text-KI hat kein JSON geschickt. Anfang der Antwort: %r"
        % ((antwort or "")[:120],), antwort or "", 0)


# ---------- Nachtrag t4: die Besetzung vor dem Schreiben ----------
#
# Claude wusste beim Schreiben nichts von Mara und Jonas. Also konnte
# es keinen Dialog fuer sie schreiben und nicht entscheiden, wer in
# welcher Szene zu sehen ist. Beides wird jetzt mitgeschickt.
#
# Gibt es keine angehakten Avatare, bleibt alles wie bisher: ein
# Erzaehler, keine Namen, keine Besetzungszeile.

def _t4_besetzung(kanal):
    try:
        import darsteller
        d = darsteller.laden(kanal)
        dabei = [x for x in (d.get("darsteller") or [])
                 if x.get("id") in (d.get("besetzung") or [])]
        return [(x.get("name") or "").strip() for x in dabei
                if (x.get("name") or "").strip()]
    except Exception as e:
        print("[Text] Besetzung nicht lesbar:", e)
        return []


def _t4_anweisung(namen):
    if not namen:
        return ""
    liste = " und ".join(namen) if len(namen) < 3 else ", ".join(namen)
    mehrere = len(namen) > 1
    return (
        "\n\nBESETZUNG - SEHR WICHTIG:\n"
        "In diesem Kanal treten auf: %s. Es gibt KEINEN Erzaehler. "
        "Jeder gesprochene Satz gehoert einer dieser Figuren.\n"
        "Schreib den Text jeder Szene als Zeilen mit dem Namen davor:\n"
        "  %s: Erster Satz.\n"
        "%s"
        "%s"
        "Die Figuren fuehren durch das Thema, sie sind keine Zeitzeugen und "
        "keine historischen Personen. Sie duerfen staunen, zweifeln und "
        "nachfragen.\n"
        "Dazu gehoert je Szene das Feld \"wer\": eine Liste der Namen, die in "
        "DIESEM Bild zu sehen sind. Das ist unabhaengig davon, wer spricht - "
        "die Figuren koennen auch aus dem Off reden, waehrend man nur die "
        "Landschaft sieht. Zeig sie nicht in jeder Szene; bei Szenen, in "
        "denen der Ort oder das Ereignis wichtiger ist, gehoert \"wer\": []."
        % (liste,
           namen[0],
           ("  %s: Antwort darauf.\n" % namen[1]) if mehrere else "",
           ("Sie reden MITEINANDER: einer fragt, der andere antwortet, einer "
            "widerspricht. Keine zwei Leute, die abwechselnd Fakten aufsagen.\n")
           if mehrere else "")
    )


_t4_erzeuge_alt = erzeuge_paket


def erzeuge_paket(kanal, eigenes_thema=None):
    namen = _t4_besetzung(kanal)
    if not namen:
        return _t4_erzeuge_alt(kanal, eigenes_thema)
    k2 = dict(kanal or {})
    k2["prompt"] = (k2.get("prompt") or "") + _t4_anweisung(namen)
    return _t4_erzeuge_alt(k2, eigenes_thema)


# ---------- Nachtrag p88: Orte und Ereignisse statt Gegenstaende ----------
#
# Der Bildblock aus p85 stammt vom True-Crime- und Finanzkanal. Er
# verlangt woertlich "Ein Gegenstand, nah dran. Keine Szene mit mehreren
# Dingen darin" und verbietet ganze Personen. Fuer einen Geschichtskanal
# ist das genau verkehrt: Zu "Die Schlacht bei Waterloo" kam ein
# Nahaufnahme-Foto von verkohltem Papier auf nassem Stein.
#
# Hat der Kanal eine Besetzung, ist es ein Erzaehlkanal - dann gilt der
# Block hier: der Ort, das Ereignis, die Menschen, weit statt nah. Ohne
# Besetzung bleibt es beim alten Block, damit der Finanzkanal weiter
# seine Gegenstaende bekommt.

P88_BILD = """DIE SZENEN EINES EREIGNISSES
Bevor du schreibst, denk wie ein Regisseur: Welche fuenf bis acht
Momente braucht man, um dieses Ereignis zu verstehen? Nimm die, die
eine Dokumentation zeigen wuerde, in zeitlicher Reihenfolge - die Lage
davor, der Ausloeser, der Aufmarsch, der entscheidende Moment, die
Wendung, der Ausgang, die Folgen.
Jede Szene ist genau einer dieser Momente, und ihr Bild zeigt diesen
Moment - nicht die Stimmung drumherum und nicht einen Gegenstand, der
dazu passen koennte.

Beispiel Waterloo: der Regen in der Nacht davor, die Heere im
Morgengrauen gegenueber, der Kampf um das Gehoeft, die
Kavallerieattacke in den Schlamm, das Eintreffen der Preussen, das
Feld am Abend.

Steht im Thema nur ein Stichwort, nimm den bekannten Ablauf des
Ereignisses. Bist du dir bei einer Einzelheit nicht sicher, lass sie
weg und nimm einen Moment, der belegt ist. Erfinde keine Zahlen,
keine Namen und keine Zitate.

BILD UND BEWEGUNG
Hinter jeden gesprochenen Satz setzt du eine Bildbeschreibung in eckige
Klammern, mit BILD davor. Sie wird nicht gesprochen und steht in keinem
Untertitel. Sie ist die Anweisung an das Bildmodell - schreib sie auf
Englisch und schreib sie AUSFUEHRLICH. Kurze Beschreibungen geben
beliebige Bilder.

DIE SZENE, NICHT EIN DING DANEBEN
Zeig, was im Satz passiert. Geht es um eine Schlacht, sieht man den Krieg:
Soldaten, Reihen, Reiterei, Rauch, Fahnen. Nicht einen leeren Weg, nicht
nur Matsch, nicht nur Himmel. Jede Szene ein anderer Moment: Aufmarsch,
Feuer, Attacke, das Eintreffen der Verstaerkung, der Rueckzug. Dieselbe
Matschstrasse zweimal ist verboten.
Halbtotale aus Augenhoehe. Die Handelnden sind gross genug, dass man
Uniform und was sie tun erkennt. Keine Luftaufnahme, kein Panorama,
keine Grossaufnahme von einem Gegenstand.

SECHS DINGE GEHOEREN IN JEDE BESCHREIBUNG
1. Einstellung und Ort: medium shot at eye level, und wo. Niemals
   "wide shot", "wide view", "aerial", "bird's eye" oder "panorama".
2. Was passiert, konkret: nicht "soldiers" und nicht "a muddy path",
   sondern "infantry in blue coats kneeling and firing, horses charging
   past them through smoke". Die Handlung fuellt die Mitte und die
   rechte Seite. Nur unten links bleibt Boden frei.
3. Tageszeit, Licht, Wetter.
4. Epoche an Kleidung und Bauten, nie als Jahreszahl. Keine Autos,
   Jeeps, Lastwagen, Asphalt.
5. Blickwinkel: from eye level. Open ground only in the lower left,
   the action everywhere else.
6. Ein oder zwei Einzelheiten: broken fence, drums, a farmhouse, flags.

Der Avatar kommt spaeter unten links dazu. Darum dort kein Gedraenge.
Ueberall sonst sind die Leute, um die es geht. Bei Krieg immer Soldaten
im Bild, nie nur Landschaft.

WAS NIE INS BILD KOMMT
Keine Schrift, keine Buchstaben, keine Zahlen, keine Wappen mit Text,
keine beschrifteten Karten, keine Urkunden, keine Siegel, keine
Buecher, keine Zeitungen. Daraus werden unleserliche Zeichen.
Keine Sinnbilder statt der Szene: kein einzelnes Schwert auf einem
Tisch, kein Helm im Gras, kein Brief, kein verkohltes Papier, keine
Sanduhr, keine Kerze, keine Landkarte. Das ist Deko statt Geschichte.
Keine Gesichter in Grossaufnahme, keine benannten echten Personen.
Keine modernen Dinge: Autos, Strassenlaternen, Stromleitungen, Asphalt,
Kleidung von heute.
Kein Blut, keine Leichen, keine Verstuemmelung.

DREI BEISPIELE IN DER RICHTIGEN LAENGE
[BILD: medium shot at eye level, infantry in dark blue coats kneeling and firing across a field at dawn, a troop of cavalry charging through white powder smoke on the right, a farmhouse burning behind them, open muddy grass only in the lower left, heavy grey clouds]

[BILD: medium shot at eye level, a column of infantry in red coats marching onto the field with flags and drums, ranks already formed and waiting ahead of them, low sun, dust, open ground only in the lower left]

[BILD: medium shot at eye level from a stone quay at sunrise, sailors hauling ropes as three wooden ships come alongside the pier, barrels and crates on the dock, orange light, open flagstones only in the lower left]

BEWEGUNG
Zu JEDER Szene schreibst du eine zweite Klammer mit BEWEGUNG davor.
Sie sagt, was sich ruehrt. Auf Deutsch, hoechstens zwanzig Woerter.
Drei Teile, immer in dieser Reihenfolge:

1. DIE FIGUREN. Stehen in dieser Szene Figuren im Bild (siehe "wer"),
   schreib hinein, was sie tun, waehrend sie reden: zeigt hinunter ins
   Tal, deutet auf die Reihen, dreht sich zum anderen, breitet die Arme
   aus, schuettelt den Kopf. Sie sollen nicht herumstehen wie
   hingestellt. Aber: nicht gehen, nicht greifen, nicht hinsetzen,
   nichts aufheben - sie bleiben auf der Stelle, sonst wird der Koerper
   Matsch. Ist "wer" leer, laesst du diesen Teil weg.
2. DER HINTERGRUND. Was dort passiert, passend zum Satz. Bei Krieg:
   die Reihen feuern, die Reiterei reitet an, Rauch zieht, Fahnen gehen
   vor. Nicht nur Gras im Wind und nicht nur ein leerer Weg.
   Eine Menschenmenge als Ganzes geht; einzelne Leute, die etwas
   anfassen, werden Matsch.
3. Die Kamera bleibt stehen. Keine Fahrt, kein Zoom, kein Schwenk.
   Der Erklaerende bleibt von vorne im Bild.

Mit Figuren: [BEWEGUNG: Mara bleibt stehen und schaut in die Kamera, Rauch zieht ueber das Feld, die Reihen schieben sich vor]

Ohne Figuren: [BEWEGUNG: Kamera faehrt langsam zurueck, Rauch zieht ueber das Feld]"""


_p88_prompt_alt = lade_prompt


def lade_prompt(kanal):
    text = _p88_prompt_alt(kanal)
    try:
        if not _t4_besetzung(kanal):
            return text
    except Exception:
        return text
    alt = globals().get("P85_BILD") or ""
    if alt and alt in text:
        return text.replace(alt, P88_BILD)
    if "BILD UND BEWEGUNG" not in text:
        return text.rstrip() + "\n\n" + P88_BILD
    return text


# ---------- Nachtrag t5: Dialog mit Inhalt ----------
#
# Der Besetzungsauftrag zeigte als Beispiel "Mara: Erster Satz. / Jonas:
# Antwort darauf." - zwei leere Halbsaetze - und verbot im selben Atemzug
# "zwei Leute, die abwechselnd Fakten aufsagen". Gemeint war: kein
# Ablesen. Gelesen hat es die KI als: keine Fakten. Herausgekommen ist
# Geplauder ohne Inhalt.
#
# Das Gespraech ist die Form, nicht der Inhalt. In jedem Beitrag steckt
# eine Angabe, und das Beispiel zeigt jetzt, wie das aussieht.


def _t4_anweisung(namen):
    if not namen:
        return ""
    liste = " und ".join(namen) if len(namen) < 3 else ", ".join(namen)
    mehrere = len(namen) > 1
    if mehrere:
        beispiel = (
            "  %s: Um sieben Uhr abends warf Napoleon die Garde nach vorn.\n"
            "  %s: Eine Stunde spaeter war er auf der Flucht.\n"
            % (namen[0], namen[1]))
        form = ("Sie wechseln sich ab wie zwei Sprecher einer Dokumentation: "
                "einer erzaehlt ein Stueck, der naechste fuehrt genau dort "
                "weiter, wo der erste aufgehoert hat. KEINE Fragen "
                "aneinander, keine Rueckmeldungen, kein Staunen, kein "
                "\"Unglaublich\", kein \"Erzaehl weiter\", keine Anrede mit "
                "Namen. Solche Zeilen halten nur auf. Jede Zeile bringt die "
                "Geschichte voran und enthaelt eine Angabe.\n")
    else:
        beispiel = ("  %s: Am Morgen des 18. Juni standen sich bei Waterloo "
                    "zweihunderttausend Mann gegenueber.\n" % namen[0])
        form = ("%s erklaert das ganze Video allein. In JEDER Szene spricht "
                "nur %s, genau ein Satz, hoechstens 16 Woerter. "
                "Das Feld \"wer\" ist in jeder Szene nur dieser eine Name.\n"
                % (namen[0], namen[0]))
    satz = ("JEDE Szene ist EINE Einstellung mit EINER Person. Genau ein "
            "kurzer Satz, hoechstens 16 Woerter. Die Personen wechseln sich "
            "ab: erst der eine, in der naechsten Szene der andere. "
            "Das Feld \"wer\" enthaelt nur den Namen, der in dieser Szene redet.\n"
            if mehrere else "")
    return (
        "\n\nBESETZUNG - SEHR WICHTIG:\n"
        "In diesem Kanal treten auf: %s. Es gibt KEINEN Erzaehler. "
        "Jeder gesprochene Satz gehoert einer dieser Figuren.\n"
        "Schreib den Text jeder Szene mit dem Namen vor jedem Stueck, alles in EINER Zeile hintereinander - im JSON darf kein echter Zeilenumbruch stehen:\n"
        "%s"
        "%s"
        "Die Figuren erklaeren das Thema, sie sind keine Zeitzeugen und "
        "keine historischen Personen. Sie kommentieren nicht, sie "
        "berichten.\n"
        "%s"
        % (liste, beispiel, form, satz)
    )


# ---------- Nachtrag t6: kaputtes JSON flicken und richtig melden ----------
#
# Seit die Szenen mehrere Saetze haben duerfen, schreibt die Text-KI die
# Sprecherzeilen untereinander:
#     "text": "Mara: Erster Satz.
#              Jonas: Zweiter Satz."
# In JSON darf in einem String kein echter Zeilenumbruch stehen - die
# Antwort war damit unlesbar, obwohl inhaltlich alles stimmte.
#
# Zwei Dinge: der Umbruch wird vor dem Lesen escaped, und wenn es dann
# immer noch nicht geht, steht der echte Grund in der Meldung. Vorher
# stand dort immer "line 1 column 1 (char 0)", weil die Stelle beim
# Weiterreichen auf 0 gesetzt wurde - damit war nicht zu erkennen, wo es
# klemmt.


def _t6_flicken(s):
    """Rohe Steuerzeichen innerhalb von JSON-Strings escapen."""
    ersatz = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
    raus, drin, esc = [], False, False
    for ch in (s or ""):
        if esc:
            raus.append(ch)
            esc = False
            continue
        if ch == "\\":
            raus.append(ch)
            esc = True
            continue
        if ch == '"':
            drin = not drin
            raus.append(ch)
            continue
        if drin and ch in ersatz:
            raus.append(ersatz[ch])
            continue
        raus.append(ch)
    return "".join(raus)


_t6_json_alt = _p40_json


def _p40_json(antwort):
    try:
        return _t6_json_alt(antwort)
    except Exception:
        pass
    roh = _t3_schaelen(antwort) or (antwort or "")
    for versuch in (_t6_flicken(roh), _t6_flicken(antwort or "")):
        if not versuch:
            continue
        try:
            d = _t3_json_alt(versuch)
            print("[Text] Zeilenumbrueche im JSON geflickt")
            return d
        except Exception as e:
            letzter = e
    raise _p40_json_modul.JSONDecodeError(
        "Die Text-KI hat kaputtes JSON geschickt - %s. Anfang der Antwort: %r"
        % (str(letzter)[:90], (antwort or "")[:120]), antwort or "", 0)


# ---------- Nachtrag t7: Szenen auf die Stufen des Modells legen ----------
#
# Bisher lief es andersherum: der Sprechtext bestimmte die Szenenlaenge,
# und der Clip wurde auf die naechste Stufe aufgerundet. Eine Szene von
# 8 Sekunden hat damit 10 bestellt und 2 verschenkt - und war sie laenger
# als die groesste Stufe, endete sie mit einem stehenden Bild.
#
# Jetzt wird die Szenenzahl so gewaehlt, dass jede Szene genau auf einer
# Stufe des Modells landet. Genommen wird die Stufe, die der bisherigen
# Szenenlaenge am naechsten kommt - die Einstellung des Kanals aendert
# sich also im Gefuehl nicht, es passt nur genau.
#
# Kennt das Modell keine Stufen (Kling nimmt jede ganze Sekunde), bleibt
# alles wie bisher.


def _t7_stufen(kanal):
    try:
        import animation
        e = animation.ref_slot(kanal) or {}
        url = (e.get("url") or "").strip().lower()
        if not url:
            return []
        stufen = animation.m9_zahlen(animation.m9_laden().get(url) or {})
        if not stufen and animation.m7_ist_h3(url):
            stufen = list(getattr(animation, "M7_STUFEN", []) or [])
        return stufen
    except Exception as e:
        print("[Text] Modellstufen nicht lesbar:", e)
        return []


_t7_erzeuge_alt = erzeuge_paket

import re as _clip_re
_CLIP_NAME = _clip_re.compile(r"^([^:]{1,24}):\s*")
_CLIP_KLAMMER = _clip_re.compile(r"\[[^\[\]]*\]")
_CLIP_SPRECHER = _clip_re.compile(
    r"(?:^|\s)([A-Za-zÄÖÜäöüß]+(?:\s+[A-Za-zÄÖÜäöüß]+){0,2}):\s+")


def _clip_sprecher(text):
    """[(Name, Satz), ...] wenn mindestens zwei Leute reden."""
    ms = [m for m in _CLIP_SPRECHER.finditer(text or "")
          if len(m.group(1).split()) <= 3]
    if len(ms) < 2:
        return []
    raus = []
    for i, m in enumerate(ms):
        ende = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        wort = (text[m.end():ende] or "").strip(" .")
        if wort:
            raus.append((m.group(1).strip(), wort))
    return raus if len(raus) >= 2 else []


def _clip_beide_kurz(beide, grenze=20):
    """Beide bleiben in derselben Szene. Zu langer Text wird gekuerzt."""
    teile = [(n, w.split()) for n, w in beide]
    if sum(len(w) for _n, w in teile) <= grenze:
        return [(n, " ".join(w)) for n, w in teile]
    topf, raus = grenze, []
    rest = len(teile)
    for name, ww in teile:
        rest -= 1
        nimm = topf if rest == 0 else max(4, topf // (rest + 1))
        nimm = min(len(ww), topf, nimm)
        raus.append((name, " ".join(ww[:max(1, nimm)])))
        topf -= max(1, nimm)
    return raus


def _clip10(paket):
    """Keine Szene darf laenger gesprochen sein, als der Clip dauert.

    22 Woerter sind bei der Schaetzung knapp unter 10 Sekunden. Was
    darueber liegt, wird zur naechsten Szene - dasselbe Bild, neuer Satz.
    Die Text-KI haelt sich nicht an die Vorgabe.
    """
    if not isinstance(paket, dict):
        return paket
    szenen = paket.get("szenen")
    if not isinstance(szenen, list):
        return paket
    neu = []
    for s in szenen:
        if not isinstance(s, dict):
            neu.append(s)
            continue
        roh = _CLIP_KLAMMER.sub(" ", s.get("text") or "")
        auf = roh.find("[")
        if auf >= 0:
            roh = roh[:auf]
        roh = " ".join(roh.split())
        beide = _clip_sprecher(roh)
        if len(beide) >= 2:
            for n, w in _clip_beide_kurz(beide):
                s2 = dict(s)
                s2["text"] = "%s: %s." % (n, w)
                s2["wer"] = [n]
                neu.append(s2)
            continue
        name = ""
        m = _CLIP_NAME.match(roh)
        if m and len(m.group(1).split()) <= 3:
            name = m.group(1).strip()
            roh = roh[m.end():].strip()
        woerter = roh.split()
        if len(woerter) <= 22:
            s2 = dict(s)
            s2["text"] = (name + ": " + roh).strip(": ").strip() if name else roh
            if name:
                s2["wer"] = [name]
            neu.append(s2)
            continue
        rest = woerter
        while rest:
            if len(rest) <= 26:
                stueck, rest = rest, []
            else:
                schnitt = 18
                for i in range(18, 10, -1):
                    if rest[i - 1][-1:] in ",;:":
                        schnitt = i
                        break
                stueck, rest = rest[:schnitt], rest[schnitt:]
            s2 = dict(s)
            kern = " ".join(stueck)
            s2["text"] = (name + ": " + kern) if name else kern
            if name:
                s2["wer"] = [name]
            neu.append(s2)
    if len(neu) != len(szenen):
        print("[Text] Zu lang fuer 10 Sekunden: %d Szenen werden %d"
              % (len(szenen), len(neu)))
    raus = dict(paket)
    raus["szenen"] = neu
    return raus


def erzeuge_paket(kanal, eigenes_thema=None):
    try:
        k = dict(kanal or {})
        minuten = einstellungen.laenge_in_minuten(k)
        gesamt = minuten * 60.0
        if gesamt > 0:
            stufen = _t7_stufen(k)
            nahe = [x for x in stufen if 6 <= x <= 10]
            stufe = min(nahe, key=lambda x: abs(x - 10)) if nahe else 10
            stufe = min(10, stufe)
            szenen = max(1, int(round(gesamt / float(stufe))))
            if gesamt / szenen > 10:
                szenen = max(1, int((gesamt + 9) // 10))
            bisher = max(1, int(round(minuten * k.get("bilder_pro_minute", 6))))
            k["bilder_pro_minute"] = (szenen + 0.4) / max(0.01, minuten)
            k["woerter_pro_sekunde"] = round(_p37_wps(k) * 0.85, 3)
            print("[Text] %d Szenen zu je hoechstens %d Sekunden "
                  "(vorher %d Szenen, im Schnitt %.1f)"
                  % (szenen, stufe, bisher, gesamt / max(1, bisher)))
            return _clip10(_t7_erzeuge_alt(k, eigenes_thema))
    except Exception as e:
        print("[Text] Szenenlaenge nicht anpassbar:", e)
    return _clip10(_t7_erzeuge_alt(kanal, eigenes_thema))
