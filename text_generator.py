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
    if kanal.get("szenen_soll"):
        anzahl_bilder = max(1, int(kanal["szenen_soll"]))
    else:
        anzahl_bilder = max(1, int(round(laenge * kanal["bilder_pro_minute"])))
    _sek, _worte, _grok = _clip_deckel(kanal)
    _je = min(float(_sek) - 1.0, (laenge * 60.0) / max(1, anzahl_bilder))
    _je = max(8.0 if _grok else 4.0, _je)
    _wps = _p37_wps(kanal)
    _unten = max(8 if _grok else 4, int(_je * _wps * 0.85))
    _oben = max(_unten + 1, min(_worte, int(_je * _wps)))
    _zeit = ("Der Clip wird so lang bestellt, wie der Satz braucht, plus knapp eine Sekunde. "
             "Mindestens 4, hoechstens 15 Sekunden. Nicht auf 10 oder 15 auffuellen. "
             "Der Satz fuellt diese Zeit, das letzte Wort kommt kurz vor dem Schluss. "
             if _grok else
             "Der Clip ist 10 Sekunden und kann nicht laenger. ")

    prompt = f"""{lade_prompt(kanal)}

REGELN:
{lade_regeln(kanal)}

AUFGABE:
Erstelle EIN komplettes Video-Paket.
Sprache: {', '.join(kanal.get('sprachen', ['Deutsch']))}
Laenge: ca. {laenge*60:.0f} Sekunden gesprochen\n{_tl_hinweis(kanal)}Das SKRIPT hat genau {anzahl_bilder} Szenen. Jede Szene hat {_unten} bis {_oben} Woerter, in ein oder zwei Saetzen, und beide Saetze beschreiben denselben Augenblick. Das sind etwa {_je:.0f} Sekunden gesprochen, nicht deutlich weniger. {_zeit}Was nicht in 15 Sekunden passt, wird nicht bestellt und nicht abgeschnitten. EINE SZENE IST EIN AUGENBLICK: Der gesprochene Text sagt nur, was auf diesem einen Bild zu sehen ist. Kein Danach, kein Dann, keine zweite Handlung. Die naechste Handlung ist die naechste Szene. Passen mehr Handlungen nicht in die Szenenzahl, lass die unwichtigeren weg. Stapel sie nicht in einen Satz. SUBSTANZ: In JEDER Szene steht mindestens eine harte Angabe - ein Name, ein Ort, ein Datum, eine Zahl, ein Ergebnis. Keine Szene, die nur Stimmung macht, etwas ankuendigt oder wiederholt, was schon gesagt wurde. Am Ende muss jemand, der das Video gesehen hat, das Ereignis erklaeren koennen: wer, wo, wann, warum, wie es ausging und was danach anders war. Normales Deutsch, ganze Woerter: Attrappenkoepfe, Regenmaentel, Ruderrest. Nie ein Wort zerhacken und nie ein erfundenes Wort wie Ertrappen.
{P49_THEMA % eigenes_thema if eigenes_thema else "Waehle selbst ein passendes Thema."}

Bildbeschreibungen konkret, nicht ein Stichwort.\n\nBILDER: Jedes Bild zeigt genau den einen Augenblick, den der Satz sagt, so gross, dass man die Handlung erkennt. Nicht drei Handlungen in einem Bild. Keine Person, die nur im Vordergrund steht und in die Kamera schaut. Kein Podest, keine Steinplatte, kein Felsblock. Kein Blut, keine Leichen. Jede Szene ein anderer Moment.\n\nBEWEGUNG: Was in diesem einen Augenblick passiert. Nicht die Kamera. Der Hintergrund lebt genau diese Handlung, nichts daneben.

Antworte NUR mit JSON, ohne Erklaerung, ohne Markdown.
Teile die Geschichte in {anzahl_bilder} SZENEN. Jede Szene hat ihren eigenen
Text UND das Bild das GENAU dazu passt. Das Bild zeigt was in diesem Moment
erzaehlt wird - nicht irgendein allgemeines Motiv.

{{
  "titel": "...",
  "szenen": [
    {{"text": "gesprochener Text dieser Szene",
      "bild": "genaue Bildbeschreibung, 400 bis 700 Zeichen, Ort, Leute, Handlung, Kleidung, Licht",
      "bewegung": "Gesten: ein Avatar zwei Handbewegungen, mehrere je Zeile Name: Geste",
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


def _clip_deckel(kanal):
    """Wie lang ein Clip sein darf, und wie viele Woerter reinpassen.

    Grok nimmt jede ganze Sekunde von 4 bis 15. Kling und MiniMax bleiben
    bei 10. Der Puffer muss noch in den Clip passen, sonst wird gesperrt.
    """
    try:
        import animation
        grok = animation.grok_ist((animation.ref_slot(kanal) or {}).get("url"))
    except Exception:
        grok = False
    sek = 15 if grok else 10
    try:
        puff = float((kanal or {}).get("nachlauf"))
    except Exception:
        puff = 0.9
    if puff != puff or puff < 0 or puff > 5:
        puff = 0.9
    worte = max(12, int((sek - puff) * _p37_wps(kanal)))
    return sek, worte, grok


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


def _t4_sprecher(kanal):
    ids = [str(x) for x in ((kanal or {}).get("sprecher_an") or [])]
    if not ids:
        return []
    try:
        import darsteller
        d = darsteller.laden(kanal)
        return [(x.get("name") or "").strip()
                for x in (d.get("darsteller") or [])
                if str(x.get("id") or "") in ids and (x.get("art") == "sprecher")
                and (x.get("name") or "").strip()]
    except Exception as e:
        print("[Text] Sprecher nicht lesbar:", e)
        return []


def _t4_anweisung(namen, kanal=None, sprecher=None):
    if not namen and not sprecher:
        return ""
    sprecher = sprecher or []
    mehrere = len(namen) > 1
    if namen and sprecher:
        lage = (
            "Es gibt ZWEI Arten von Szenen, nie beide in derselben Szene.\n"
            "Avatar-Szene: nur %s redet und steht im Bild. \"wer\" enthaelt %s. "
            "Grok spricht.\n"
            "Sprecher-Szene: nur %s redet, niemand im Bild, \"wer\": [].\n"
            % (", ".join(namen),
               "alle diese Namen" if mehrere else "diesen Namen",
               ", ".join(sprecher)))
        if mehrere:
            lage += ("In einer Avatar-Szene stehen alle zusammen, ohne Podest, "
                     "und reden nacheinander.\n")
    elif mehrere:
        lage = (
            "ALLE stehen in jeder Avatar-Szene zusammen, ohne Podest, "
            "und reden nacheinander. \"wer\" enthaelt immer: %s.\n"
            % ", ".join(namen))
    elif namen:
        links = bool((kanal or {}).get("podest_an")) and str(
            (kanal or {}).get("figur_stand") or "") != "szene"
        lage = (
            ("%s steht in jeder Avatar-Szene links auf einem flachen Podest. "
             "\"wer\" ist [\"%s\"]. Nimmt man die Person aus dem Bild, "
             "redet sie weiter aus dem Off, dieselbe Stimme.\n")
            if links else
            ("%s steht in jeder Avatar-Szene im Bild, ohne Podest. "
             "\"wer\" ist [\"%s\"]. Nimmt man die Person aus dem Bild, "
             "redet sie weiter aus dem Off, dieselbe Stimme.\n")
        ) % (namen[0], namen[0])
    else:
        lage = (
            "Niemand ist im Bild. Es spricht nur der Sprecher aus dem Off. "
            "Das Feld \"wer\" ist immer [].\n")
    wer = namen + [n for n in sprecher if n not in namen]
    liste = ", ".join(wer)
    return (
        "\n\nBESETZUNG - SEHR WICHTIG:\n"
        "Zu sehen oder zu hoeren: %s.\n"
        "Schreib den Text jeder Szene als Zeilen mit dem Namen davor:\n"
        "  %s: Erster Satz.\n"
        "%s"
        "%s"
        "Die Figuren fuehren durch das Thema. Sie sind keine Zeitzeugen.\n"
        "%s"
        % (liste,
           wer[0],
           ("  %s: Antwort darauf.\n" % wer[1]) if len(wer) > 1 else "",
           ("Sie reden nacheinander. Keiner redet gleichzeitig.\n")
           if len(namen) > 1 else "",
           lage)
    )


_t4_erzeuge_alt = erzeuge_paket


def erzeuge_paket(kanal, eigenes_thema=None):
    namen = _t4_besetzung(kanal)
    stimmen = _t4_sprecher(kanal)
    if not namen and not stimmen:
        return _t4_erzeuge_alt(kanal, eigenes_thema)
    k2 = dict(kanal or {})
    k2["prompt"] = (k2.get("prompt") or "") + _t4_anweisung(namen, kanal, stimmen)
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
Bevor du schreibst, denk wie ein Regisseur. Nimm genau so viele Momente,
wie der Auftrag Szenen verlangt, nicht eine mehr. Eine Dokumentation
wuerde sie in dieser Reihenfolge zeigen: die Lage davor, der Ausloeser,
der entscheidende Moment, der Ausgang.
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
Untertitel. Sie steht nur in der eckigen Klammer, niemals im gesprochenen Text.
Der gesprochene Text enthaelt kein Wort BILD. Schreib sie in der
Sprache des Videos, nicht auf Englisch, ausser das Video ist englisch.
Schreib sie AUSFUEHRLICH, 400 bis 700 Zeichen. Kurze Beschreibungen geben
beliebige Bilder.

DAS BILD ZEIGT NUR DIESEN AUGENBLICK
Der gesprochene Satz und das Bild sind dasselbe. Sagt der Satz, sie kratzen mit Loeffeln Beton, sieht man genau das: zwei Maenner, Loeffel, Wand, Loch. Sagt der Satz, ein Foto liegt auf dem Tisch, sieht man das Foto, nicht gleichzeitig eine Blume, ein Begräbnis und ein anderes Jahr.
Keine zweite Handlung im selben Bild und kein Satz, der etwas erzaehlt, das auf dem Bild nicht vorkommt.
Keine Person im Vordergrund, die nur steht und in die Kamera schaut. Kein Podest, keine Steinplatte, kein Fels.
Kein Blut, keine Leichen. Luftaufnahme bleibt verboten. Das Bild darf weit sein, wenn man die Handlung sonst nicht sieht.

WAS IN DIE BESCHREIBUNG GEHOERT
Ort, was genau passiert, Kleidung und Bauten der Zeit, Licht und Wetter.
Unten links keine Steinplatte, kein Fels und kein Block. Eine Steinplatte
im Text wird zum Felsblock und verdeckt die Schiffe. Der Avatar kommt spaeter
dazu, er wird nicht ins Standbild gemalt.
Deutsche Zusammensetzungen in einem Wort: Dampfschiff, Frachtschiff,
Einschlagstelle, nicht Dampf Schiff.
Keine Schrift, keine Zahlen, keine Karten, keine Grossaufnahme eines Gesichts.
Kein Blut, keine Leichen.

BEISPIELE
[BILD: Weit genug, im Hafenbecken stossen zwei Frachtdampfer zusammen, der Bug des einen steckt im Rumpf des anderen, Holz splittert, Wasser spritzt, Speicherhaeuser dahinter, tiefes Sonnenlicht.]

[BILD: Weit genug, aus dem getroffenen Schiff steigt ein weisser Feuerball, die Druckwelle knickt Holzhausdacher und wirft Fenster nach aussen, keine Menschen im Vordergrund, keine Leichen.]

BEWEGUNG
Zu JEDER Szene eine Klammer [BEWEGUNG: ...]. Sie wird nicht gesprochen.
Zwei Teile, in dieser Reihenfolge, hoechstens dreissig Woerter:

1. DER AVATAR. Er steht auf der flachen Platte, Fuesse bleiben.
   Beide Haende zeigen auf das Ereignis dieser Szene: auf die Schiffe,
   auf den Feuerball, auf die Druckwelle. Nicht ins Leere.
   Der Kopf bleibt zur Kamera. Er laeuft nicht weg.
   Den Mund nicht erwaehnen. Grok bewegt ihn zum Sprechen.
2. DIE SZENE DAHINTER. Genau das Ereignis bewegt sich.
   Schiffe stossen zusammen: der Bug faehrt in den anderen Rumpf, Wasser spritzt.
   Explosion: der Feuerball waechst, die Druckwelle knickt die Daecher.
   Nicht "Rauch zieht" als Ersatz. Nicht "nicht zweimal". Die Kamera bleibt stehen.

[BEWEGUNG: Mara steht auf der Platte, beide Haende zeigen zum Feuerball. Der Feuerball waechst, die Druckwelle knickt die Daecher.]"""


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


def _t4_anweisung(namen, kanal=None, sprecher=None):
    if not namen and not sprecher:
        return ""
    sprecher = sprecher or []
    mehrere = len(namen) > 1
    if mehrere:
        sek, worte, grok = _clip_deckel(kanal) if kanal else (15, 35, True)
        boden = 12 if len(namen) >= 3 else 10
        try:
            puff = float((kanal or {}).get("nachlauf"))
        except Exception:
            puff = 0.9
        if puff != puff or puff < 0 or puff > 5:
            puff = 0.9
        mindest_worte = max(12, int((boden - puff) * _p37_wps(kanal)))
        zeilen = "\n".join(
            "  %s: Ein ganzer Satz mit einer harten Angabe." % n for n in namen[:3])
        lage = (
            "ALLE Avatare stehen in JEDER Avatar-Szene zusammen und reden "
            "NACHEINANDER IN DERSELBEN Szene. Nicht jeder in einer eigenen "
            "Szene und nicht gleichzeitig.\n"
            "Schreib alle Zeilen in den Text dieser einen Szene:\n%s\n"
            "Jeder sagt mindestens einen ganzen Satz, nicht drei Woerter. "
            "Mindestens %d Woerter, hoechstens %d. Der Clip ist %d bis %d Sekunden%s. Nie 4 Sekunden.\n"
            "Das Feld \"wer\" enthaelt immer alle Avatar-Namen: %s.\n"
            "Die Animationsanweisung ist je Avatar eine Zeile mit einer deutlichen Geste, "
            "Haende hoch, zeigen, nicken, nicht stillstehen: %s: zeigt mit beiden Haenden auf den Kampf. %s: nickt und ballt die Faust.\n"
            % (zeilen, mindest_worte, worte, boden, sek,
               ", bei Grok jede ganze Sekunde von 8 bis 15" if grok else "",
               ", ".join(namen), namen[0], namen[1]))
    elif namen:
        lage = (
            "%s steht in JEDER Szene im Bild und spricht sie selbst, "
            "zwei oder drei Saetze, nicht nur einen. Keine Szene ohne %s. "
            "Keine Szene nur mit Sprecher. Eine Stimme, kein Wechsel.\n"
            "Jede Zeile beginnt mit %s:. Das Feld \"wer\" ist [\"%s\"].\n"
            "Die Animationsanweisung nennt zwei Gesten: zeigen, zaehlen, nicken, "
            "Oberkoerper leicht drehen. Die Arme haengen nicht herunter.\n"
            % (namen[0], namen[0], namen[0], namen[0]))
    else:
        lage = (
            "Niemand ist im Bild. Es spricht nur der Sprecher. "
            "Das Feld \"wer\" ist immer [].\n")
    if namen and sprecher:
        lage += (
            "Der Sprecher aus dem Off wird in diesem Video nicht benutzt. "
            "Sonst gibt es zwei Stimmen. Jede Szene gehoert %s.\n"
            % ", ".join(namen))
    wer = namen + [n for n in sprecher if n not in namen]
    return (
        "\n\nBESETZUNG - SEHR WICHTIG:\n"
        "Zu sehen oder zu hoeren: %s.\n"
        "Jede Zeile beginnt mit dem Namen. Avatare duerfen in einer Szene "
        "nacheinander reden.\n"
        "%s"
        % (", ".join(wer), lage))


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


def _clip_gruppen(beide, grenze=20):
    """Mehrere Sprecher bleiben zusammen, solange der Clip das fasst."""
    gruppen, paket, zahl = [], [], 0
    for name, wort in beide:
        ww = (wort or "").split()
        if not ww:
            continue
        if zahl and zahl + len(ww) > grenze:
            gruppen.append(paket)
            paket, zahl = [], 0
        while ww:
            platz = grenze - zahl
            if platz <= 0:
                gruppen.append(paket)
                paket, zahl = [], 0
                platz = grenze
            stueck, ww = ww[:platz], ww[platz:]
            paket.append((name, " ".join(stueck)))
            zahl += len(stueck)
            if ww:
                gruppen.append(paket)
                paket, zahl = [], 0
    if paket:
        gruppen.append(paket)
    return gruppen


def _clip10(paket, grenze=35):
    """Keine Szene darf laenger gesprochen sein, als der Clip dauert.

    grenze ist die Wortzahl, die inklusive Puffer in den Clip passt.
    Bei Grok sind das bis zu 15 Sekunden, sonst 10. Was darueber liegt,
    wird zur naechsten Szene.
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
            # Dieselbe Person steht vor jedem Satz ("Frau: ... Frau: ...").
            # Das ist ein Erzaehler, kein Dialog. Nichts davon wird gekuerzt.
            # Auch bei zwei echten Sprechern bleibt jeder Satz ganz.
            # Abschneiden hat "vor der." und "weil die." erzeugt.
            namen = []
            for n, _w in beide:
                if n not in namen:
                    namen.append(n)
            woerter = roh.split()
            if len(woerter) > grenze:
                print("[Text] Szene hat %d Woerter, Grenze %d. "
                      "Der Satz bleibt ganz, nichts wird abgeschnitten."
                      % (len(woerter), grenze))
            s2 = dict(s)
            s2["text"] = roh
            s2["wer"] = namen
            neu.append(s2)
            continue
        name = ""
        m = _CLIP_NAME.match(roh)
        if m and len(m.group(1).split()) <= 3:
            name = m.group(1).strip()
            roh = roh[m.end():].strip()
        woerter = roh.split()
        if len(woerter) > grenze:
            print("[Text] Szene hat %d Woerter, Grenze %d. Sie bleibt eine Szene, "
                  "damit aus zwei Szenen nicht drei werden."
                  % (len(woerter), grenze))
        s2 = dict(s)
        s2["text"] = (name + ": " + roh).strip(": ").strip() if name else roh
        if name:
            s2["wer"] = [name]
        neu.append(s2)
    if len(neu) != len(szenen):
        print("[Text] Zu lang fuer %d Woerter: %d Szenen werden %d"
              % (grenze, len(szenen), len(neu)))
    raus = dict(paket)
    raus["szenen"] = neu
    return raus


def _paket_worte(paket):
    n = 0
    for s in (paket or {}).get("szenen") or []:
        if isinstance(s, dict):
            n += len(str(s.get("text") or "").split())
    return n


def _plan_laenge(kanal):
    """Wie viele Szenen in die eingegebene Videolaenge passen.

    20 Sekunden sind zwei Szenen zu etwa 10 Sekunden, nicht drei zu 12.
    Die Summe ist die Videolaenge. Jede einzelne Szene darf nicht
    auf den Deckel von 15 Sekunden aufgeblasen werden.
    """
    minuten = einstellungen.laenge_in_minuten(kanal or {})
    gesamt = max(4.0, minuten * 60.0)
    sek, _worte, grok = _clip_deckel(kanal)
    mind = 8.0 if grok else 6.0
    if mind > sek:
        mind = sek
    n_min = max(1, int((gesamt + sek - 1) // sek))
    n_max = max(1, int(gesamt // mind))
    if n_max < n_min:
        n, je = 1, min(sek, gesamt)
    else:
        n = n_min
        while n < n_max and gesamt / n > sek - 2:
            n += 1
        je = gesamt / n
    wps = _p37_wps(kanal)
    worte = max(8, int(gesamt * wps * 0.95))
    return gesamt, n, je, sek, worte


def _ganze_saetze(text, worte_je):
    """Nur ganze Saetze. Nie 'vor der.' oder 'weil die.'."""
    ww = (text or "").split()
    if len(ww) <= worte_je:
        return " ".join(ww)
    genommen, gut = [], None
    for w in ww:
        genommen.append(w)
        if w[-1:] in ".!?":
            if len(genommen) <= worte_je:
                gut = list(genommen)
            else:
                break
    if gut:
        return " ".join(gut)
    return " ".join(ww)


def _auf_soll(paket, n, worte_je):
    """Mehr Szenen als die Videolaenge hergibt, werden zusammengezogen."""
    if not isinstance(paket, dict) or n < 1:
        return paket
    sz = [s for s in (paket.get("szenen") or []) if isinstance(s, dict)]
    if len(sz) <= n:
        return paket
    gruppen = [[] for _ in range(n)]
    for i, s in enumerate(sz):
        gruppen[min(n - 1, i * n // len(sz))].append(s)
    neu = []
    for g in gruppen:
        s0 = dict(g[0])
        texte, bilder = [], []
        for x in g:
            t = str(x.get("text") or "").strip()
            if t:
                texte.append(t)
            b = str(x.get("bild") or "").strip()
            if b and b not in bilder:
                bilder.append(b)
        kern = _CLIP_KLAMMER.sub(" ", " ".join(texte))
        klammern = _CLIP_KLAMMER.findall(" ".join(texte))
        ww = kern.split()
        if len(ww) > worte_je:
            kern = _ganze_saetze(kern, worte_je)
        else:
            kern = " ".join(ww)
        if klammern:
            kern = (kern + " " + " ".join("[%s]" % k for k in klammern[:2])).strip()
        s0["text"] = kern
        if bilder:
            s0["bild"] = bilder[0]
        neu.append(s0)
    raus = dict(paket)
    raus["szenen"] = neu
    print("[Text] %d Szenen waren zu viel, es bleiben %d" % (len(sz), n))
    return raus


def _eine_stimme(kanal, paket):
    """Steht ein Avatar in der Besetzung, spricht er jede Szene. Sonst zwei Stimmen."""
    if not isinstance(paket, dict):
        return paket
    namen = _t4_besetzung(kanal)
    if not namen:
        return paket
    fremd = [n for n in _t4_sprecher(kanal) if n not in namen]
    for s in paket.get("szenen") or []:
        if not isinstance(s, dict):
            continue
        text = " ".join(str(s.get("text") or "").split())
        for n in fremd:
            text = _clip_re.sub(
                r"(?<![\wÄÖÜäöüß])" + _clip_re.escape(n) + r"\s*:",
                namen[0] + ":", text)
        if not any(_clip_re.search(
                r"(?<![\wÄÖÜäöüß])" + _clip_re.escape(n) + r"\s*:", text)
                for n in namen):
            text = ("%s: %s" % (namen[0], text)).strip()
        if "[IM BILD:" not in text.upper():
            text = text.rstrip() + " [IM BILD: %s]" % ", ".join(namen)
        s["text"] = text
        s["wer"] = list(namen)
    return paket


_HAENGER = frozenset(
    "der die das den dem des ein eine einer einem eines "
    "und oder aber denn weil dass "
    "für fuer vor mit von zu zur zum an auf aus in im am bei nach "
    "über ueber ohne als vom beim ins ans durch fürs fuers".split())


_ZIFFERWORT = {
    "null": 0, "eins": 1, "ein": 1, "zwei": 2, "drei": 3, "vier": 4,
    "fünf": 5, "funf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9,
}
_KLEIN = ["", "ein", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun"]
_ZEHN = ["zehn", "elf", "zwölf", "dreizehn", "vierzehn", "fünfzehn",
         "sechzehn", "siebzehn", "achtzehn", "neunzehn"]
_ZEHNER = ["", "", "zwanzig", "dreißig", "vierzig", "fünfzig",
           "sechzig", "siebzig", "achtzig", "neunzig"]


def _bis100(n):
    if n < 10:
        return _KLEIN[n]
    if n < 20:
        return _ZEHN[n - 10]
    z, e = divmod(n, 10)
    if not e:
        return _ZEHNER[z]
    return _KLEIN[e] + "und" + _ZEHNER[z]


def _bis1000(n):
    if n < 100:
        return _bis100(n)
    h, r = divmod(n, 100)
    return _KLEIN[h] + "hundert" + (_bis100(r) if r else "")


def _jahrwort(n):
    if n < 1000:
        return _bis1000(n)
    t, r = divmod(n, 1000)
    kopf = "eintausend" if t == 1 else _KLEIN[t] + "tausend"
    return kopf + (_bis1000(r) if r else "")


def _jahre_im_text(text):
    """'drei eins zwei' wird dreihundertzwölf. Drei Ziffernwörter hintereinander."""
    teile = (text or "").split()
    raus, i = [], 0
    while i < len(teile):
        lauf, j = [], i
        while j < len(teile):
            nackt = teile[j].strip(".,;:!?\"'“”").lower()
            if nackt not in _ZIFFERWORT:
                break
            lauf.append(_ZIFFERWORT[nackt])
            j += 1
        if len(lauf) >= 3:
            zahl = 0
            for z in lauf:
                zahl = zahl * 10 + z
            ende = ""
            if teile[j - 1][-1:] in ".!?,;:":
                ende = teile[j - 1][-1]
            raus.append(_jahrwort(zahl) + ende)
            i = j
        else:
            raus.append(teile[i])
            i += 1
    return " ".join(raus)


def _satz_kaputt(text):
    """True, wenn ein Satz auf einem Artikel endet oder eine Zahl ziffernweise steht."""
    roh = _clip_re.sub(r"\[[^\]]*\]", " ", text or "")
    roh = _clip_re.sub(r"\b[A-ZÄÖÜ][\wÄÖÜäöüß'’-]{0,24}\s*:", " ", roh)
    if _clip_re.search(
            r"\b(null|eins|zwei|drei|vier|fünf|funf|sechs|sieben|acht|neun)\s+"
            r"(null|eins|zwei|drei|vier|fünf|funf|sechs|sieben|acht|neun)\b",
            roh.lower()):
        return True
    for satz in _clip_re.split(r"(?<=[.!?])\s+", roh.strip()):
        worte = _clip_re.findall(r"[A-Za-zÄÖÜäöüß0-9]+", satz)
        if worte and worte[-1].lower() in _HAENGER:
            return True
    return False


def _sprechtext_heilen(kanal, paket):
    """Abgeschnittene Sätze werden zu Ende geschrieben. Fertige Sätze bleiben."""
    if not isinstance(paket, dict):
        return paket
    szenen = [s for s in (paket.get("szenen") or []) if isinstance(s, dict)]
    for s in szenen:
        alt = " ".join(str(s.get("text") or "").split())
        neu = _jahre_im_text(alt)
        if neu != alt:
            s["text"] = neu
            print("[Text] Jahreszahl ausgeschrieben")
    idx = [i for i, s in enumerate(szenen) if _satz_kaputt(s.get("text") or "")]
    if not idx:
        return paket
    bloecke = []
    for n, i in enumerate(idx, 1):
        s = szenen[i]
        bloecke.append("SZENE %d\nTEXT: %s\nBILD: %s" % (
            n, " ".join(str(s.get("text") or "").split()),
            " ".join(str(s.get("bild") or "").split())[:700]))
    auftrag = (
        "Diese Sprechtexte sind abgeschnitten oder eine Jahreszahl steht als einzelne Ziffern. "
        "Ergaenze nur das fehlende Satzende, anhand der Bildzeile. "
        "Streiche kein Wort. Schreibe keinen Satz um. Erfinde keine neue Handlung. "
        "Jahreszahlen als ein Wort: dreihundertzwoelf, nicht drei eins zwei. "
        "Der Name vor dem Doppelpunkt bleibt stehen.\n"
        "Antworte NUR mit JSON {\"texte\": [\"...\", ...]} mit genau %d Eintraegen, "
        "in derselben Reihenfolge.\n\n%s"
        % (len(idx), "\n\n".join(bloecke)))
    try:
        roh = _claude_anfrage(auftrag, max_tokens=2500, kanal=kanal)
    except Exception as e:
        print("[Text] Sprechtext nicht heilbar:", e)
        return paket
    m = _clip_re.search(r"\{.*\}", roh or "", _clip_re.S)
    texte = []
    if m:
        try:
            texte = json.loads(m.group(0)).get("texte") or []
        except Exception:
            texte = []
    if len(texte) != len(idx):
        print("[Text] Heilung unbrauchbar, Texte bleiben")
        return paket
    for n, i in enumerate(idx):
        neu = " ".join(str(texte[n] or "").split())
        alt = " ".join(str(szenen[i].get("text") or "").split())
        if len(neu.split()) * 2 < len(alt.split()):
            print("[Text] Szene %d wurde kuerzer, bleibt" % (i + 1))
            continue
        if _satz_kaputt(neu):
            print("[Text] Szene %d immer noch abgeschnitten, bleibt" % (i + 1))
            continue
        szenen[i]["text"] = neu
        print("[Text] Szene %d Sprechtext ergaenzt" % (i + 1))
    return paket


def erzeuge_paket(kanal, eigenes_thema=None):
    try:
        k = dict(kanal or {})
        gesamt, szenen, je, sek, worte = _plan_laenge(k)
        k["szenen_soll"] = szenen
        k["bilder_pro_minute"] = (szenen + 0.49) / max(0.01, gesamt / 60.0)
        k["prompt"] = (k.get("prompt") or "") + (
            "\n\nLAENGE, DIE GILT:\n"
            "Das ganze Video ist %.0f Sekunden gesprochen, nicht mehr. "
            "Genau %d Szenen, nicht eine mehr und nicht eine weniger. "
            "Alle Szenen zusammen hoechstens %d Woerter. "
            "Jede Szene etwa %.0f Sekunden, nie laenger als %d. "
            "Der Satz fuellt die Szene. Nicht auf 10 oder 15 Sekunden auffuellen "
            "und nicht kuerzer schreiben, sonst steht der Avatar stumm, "
            "und die leere Zeit ist trotzdem bezahlt. "
            "Jeder Satz ist fertig und endet mit einem Punkt. "
            "Hoere nie mitten im Satz auf, auch nicht um die Wortzahl zu treffen. "
            "Lieber einen ganzen Satz weniger als 'vor der.' oder 'weil die.'. "
            "Jahreszahlen als ein Wort: dreihundertzwoelf, nicht drei eins zwei "
            "und nicht 312. Daten ebenso: achtundzwanzigsten Oktober.\n"
            % (gesamt, szenen, worte, je, sek))
        print("[Text] %d Szenen, zusammen %.0f Sekunden, hoechstens %d Woerter"
              % (szenen, gesamt, worte))
        paket = _clip10(_t7_erzeuge_alt(k, eigenes_thema), max(12, int(je * _p37_wps(k))))
        ist = _paket_worte(paket)
        if (isinstance(paket, dict) and paket.get("szenen")
                and (len(paket["szenen"]) != szenen or ist > int(worte * 1.15))):
            print("[Text] %d Szenen, %d Woerter, erlaubt %d Szenen und %d Woerter. Nochmal."
                  % (len(paket["szenen"]), ist, szenen, worte))
            k["prompt"] += (
                "\n\nVORIGER VERSUCH WAR ZU LANG: %d Szenen und %d Woerter. "
                "Diesmal genau %d Szenen. Streiche ganze Saetze, bis zusammen "
                "hoechstens %d Woerter bleiben. Schneide nie mitten im Satz ab.\n"
                % (len(paket["szenen"]), ist, szenen, worte))
            paket = _clip10(_t7_erzeuge_alt(k, eigenes_thema), max(12, int(je * _p37_wps(k))))
        return _sprechtext_heilen(
            k, _eine_stimme(k, _auf_soll(paket, szenen, max(12, int(je * _p37_wps(k))))))
    except Exception as e:
        print("[Text] Szenenlaenge nicht anpassbar:", e)
        try:
            _sek, worte, _grok = _clip_deckel(kanal)
        except Exception:
            worte = 35
        return _sprechtext_heilen(
            kanal, _eine_stimme(kanal, _clip10(_t7_erzeuge_alt(kanal, eigenes_thema), worte)))


_lage_prompt_alt = lade_prompt


def _lage_satz(kanal):
    """Die Lage aus Video machen. Steht am Ende und gilt vor der alten Platte."""
    k = kanal or {}
    sicht = {"knie": "head to knees", "ober": "chest up, face large"}.get(
        str(k.get("figur_sicht") or ""), "full body, head to shoes")
    mehrere = False
    try:
        import darsteller
        mehrere = len(darsteller.besetzung(k)) > 1
    except Exception:
        mehrere = False
    stand = str(k.get("figur_stand") or "links")
    if stand == "rechts" or (k.get("podest_an") and not mehrere):
        stand = "links"
    if mehrere or stand == "szene":
        return ("LAGE, DIE GILT: The avatars stand together in the scene, %s. "
                "No pedestal and no empty corner on the left." % sicht)
    seite = "right" if stand == "rechts" else "left"
    andere = "left" if seite == "right" else "right"
    if not k.get("podest_an"):
        boden = "on the scene floor, no pedestal"
    else:
        art = str(k.get("podest_art") or "stein")
        eigen = " ".join(str(k.get("podest_text") or "").split())[:40]
        if art == "wolke":
            boden = "on a flat ankle-high cloud, not a tall rock"
        elif art == "eigen" and eigen:
            boden = "on a flat low %s, not a tall rock" % eigen
        else:
            boden = "on a flat ankle-high stone slab, not a boulder"
    return ("LAGE, DIE GILT: lower %s stays empty, %s, %s. "
            "The action fills the center and the %s. "
            "Ignore any older pedestal instruction."
            % (seite, boden, sicht, andere))


def lade_prompt(kanal):
    text = _lage_prompt_alt(kanal)
    extra = _lage_satz(kanal)
    if extra and extra not in (text or ""):
        return (text or "").rstrip() + "\n\n" + extra
    return text

