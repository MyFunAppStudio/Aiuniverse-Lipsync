# -*- coding: utf-8 -*-
"""Muender auf einen fertigen Szenenclip setzen.

Kling und MiniMax (reference-to-video) bewegen die Szene, bekommen die
Stimmen aber nie zu sehen. Darum gestikulieren die Avatare, waehrend die
Sprache nur darueber liegt. Dieses Modul laeuft DANACH:

  1. Dieselben Stimmen wie im fertigen Video, je Zeile.
  2. Je Avatar eine Tonspur ueber den ganzen Clip: er redet, sonst Stille.
  3. Gesichter verfolgen. Gross im Vordergrund, nicht die Statisten.
  4. Jeden Kopf einzeln an fal-ai/sync-lipsync/v2 schicken.
  5. Nur den Mund zurueck ins Szenenbild legen, und nur waehrend
     dieser Avatar redet. Koerper, Hintergrund und Gesten bleiben.

Wer im Text zuerst drankommt, steht links. Der zweite rechts.
Das ist dieselbe Ordnung wie bisher bei zwei Tonspuren.

Ist unter KI & Technik ein Modell im Slot "lippen" eingetragen, wird
das genommen. Sonst sync-lipsync mit dem fal-Schluessel des Referenzclips.
"""
import glob
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
             "face_detection_yunet/face_detection_yunet_2023mar.onnx")
YUNET_NAME = "face_detection_yunet_2023mar.onnx"
STANDARD_URL = "fal-ai/sync-lipsync/v2"
GROESSE = 768          # Kopfclip, gross genug fuer Kling- und Sync-Modelle
FAKTOR = 2.6           # Ausschnitt gegenueber dem Gesichtsrahmen
WARTE_MAX = 900.0
TAKT = 5.0
MIN_GESICHT = 0.055    # Hoehe im Bild, darunter sind Statisten


def _lauf(befehl, zeit=300):
    return subprocess.run(befehl, capture_output=True, text=True, timeout=zeit)


def _welche(name):
    return shutil.which(name) is not None


def masse(pfad):
    """(breite, hoehe, fps, dauer) oder None."""
    if _welche("ffprobe"):
        r = _lauf(["ffprobe", "-v", "error", "-select_streams", "v:0",
                   "-show_entries", "stream=width,height,r_frame_rate,duration",
                   "-of", "csv=p=0", str(pfad)])
        zeile = (r.stdout or "").strip().splitlines()
        if r.returncode == 0 and zeile:
            teile = zeile[-1].split(",")
            if len(teile) >= 4:
                try:
                    b, h = int(teile[0]), int(teile[1])
                    z, n = teile[2].split("/")
                    fps = float(z) / float(n) if float(n) else 24.0
                    return b, h, fps if fps > 1 else 24.0, float(teile[3])
                except Exception:
                    pass
    r = _lauf(["ffmpeg", "-i", str(pfad)])
    text = (r.stderr or "") + (r.stdout or "")
    import re
    m = re.search(r"(\d{2,5})x(\d{2,5})", text)
    d = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    f = re.search(r"(\d+(?:\.\d+)?)\s*fps", text)
    if not m or not d:
        return None
    dauer = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
    return int(m.group(1)), int(m.group(2)), float(f.group(1)) if f else 24.0, dauer


def ton_laenge(pfad):
    if not pfad or not os.path.exists(pfad):
        return 0.0
    if _welche("ffprobe"):
        r = _lauf(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "csv=p=0", str(pfad)])
        try:
            return max(0.0, float((r.stdout or "0").strip().split(",")[0] or 0))
        except Exception:
            return 0.0
    info = masse(pfad)
    return info[3] if info else 0.0


def auf_laenge(ton, sekunden, ziel):
    """Ton auf eine feste Laenge bringen: kuerzer wird mit Stille aufgefuellt."""
    sek = max(0.2, float(sekunden))
    r = _lauf(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ton),
               "-af", "apad,atrim=0:%.3f" % sek, "-t", "%.3f" % sek,
               "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-q:a", "4",
               str(ziel)])
    if r.returncode != 0 or not os.path.exists(ziel):
        return None
    return str(ziel)


def video_auf_laenge(quelle, sekunden, ziel):
    """Letztes Bild stehen lassen, bis der Clip so lang ist wie die Sprache."""
    info = masse(quelle)
    if not info:
        return None
    sek = max(0.2, float(sekunden))
    extra = sek - info[3]
    if extra < 0.08:
        return str(quelle)
    r = _lauf(["ffmpeg", "-y", "-loglevel", "error", "-i", str(quelle),
               "-vf", "tpad=stop_mode=clone:stop_duration=%.3f" % (extra + 0.05),
               "-an", "-t", "%.3f" % sek, "-pix_fmt", "yuv420p",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", str(ziel)],
              zeit=600)
    if r.returncode != 0 or not os.path.exists(ziel):
        print("[Lippen] Clip liess sich nicht verlaengern: %s" % (r.stderr or "")[-160:])
        return None
    return str(ziel)


def rahmen_holen(video, ordner):
    os.makedirs(ordner, exist_ok=True)
    r = _lauf(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
               "-q:v", "2", os.path.join(ordner, "%05d.jpg")], zeit=600)
    dateien = sorted(glob.glob(os.path.join(ordner, "*.jpg")))
    if r.returncode != 0 or not dateien:
        print("[Lippen] Keine Bilder aus dem Clip: %s" % (r.stderr or "")[-160:])
        return []
    return dateien


def rahmen_packen(dateien, fps, ziel, ton=None):
    """Bilder mit fester Bildrate zum Clip. Mit Ton, wenn einer mitkommt."""
    if not dateien:
        return None
    ordner = tempfile.mkdtemp(prefix="pack_")
    try:
        for i, pfad in enumerate(dateien):
            wohin = os.path.join(ordner, "%05d.jpg" % (i + 1))
            try:
                os.link(pfad, wohin)
            except Exception:
                shutil.copyfile(pfad, wohin)
        rate = "%.5f" % max(1.0, float(fps))
        befehl = ["ffmpeg", "-y", "-loglevel", "error",
                  "-framerate", rate, "-start_number", "1",
                  "-i", os.path.join(ordner, "%05d.jpg")]
        if ton and os.path.exists(ton):
            befehl += ["-i", str(ton)]
        befehl += ["-pix_fmt", "yuv420p", "-c:v", "libx264",
                   "-preset", "veryfast", "-crf", "16"]
        if ton and os.path.exists(ton):
            befehl += ["-c:a", "aac", "-b:a", "160k", "-shortest"]
        befehl.append(str(ziel))
        r = _lauf(befehl, zeit=600)
    finally:
        shutil.rmtree(ordner, ignore_errors=True)
    if r.returncode != 0 or not os.path.exists(ziel):
        print("[Lippen] Clip liess sich nicht bauen: %s" % (r.stderr or "")[-200:])
        return None
    return str(ziel)


def yunet_pfad():
    basis = os.path.dirname(os.path.abspath(__file__))
    ziel = os.path.join(basis, "modelle", YUNET_NAME)
    if os.path.exists(ziel) and os.path.getsize(ziel) > 100000:
        return ziel
    os.makedirs(os.path.dirname(ziel), exist_ok=True)
    try:
        urllib.request.urlretrieve(YUNET_URL, ziel)
    except Exception as e:
        print("[Lippen] Gesichtsmodell nicht geladen: %s" % str(e)[:140])
        return None
    if not os.path.exists(ziel) or os.path.getsize(ziel) < 100000:
        return None
    return ziel


def _detektor(modell, breite, hoehe):
    import cv2
    if hasattr(cv2, "FaceDetectorYN"):
        return cv2.FaceDetectorYN.create(modell, "", (int(breite), int(hoehe)),
                                          0.6, 0.3, 5000)
    return cv2.FaceDetectorYN_create(modell, "", (int(breite), int(hoehe)),
                                      0.6, 0.3, 5000)


def erkenne(bild, det, min_anteil=MIN_GESICHT):
    """Gesichter als (x, y, w, h, score). Kleine Statisten fallen weg."""
    import cv2
    h, w = bild.shape[:2]
    det.setInputSize((w, h))
    try:
        _, faces = det.detect(bild)
    except Exception:
        return []
    if faces is None:
        return []
    raus = []
    for f in faces:
        x, y, fw, fh = [float(v) for v in f[:4]]
        score = float(f[-1])
        if fh < h * min_anteil or score < 0.5 or fw < 8 or fh < 8:
            continue
        raus.append((x, y, fw, fh, score))
    return raus


def _mitte(box):
    return box[0] + box[2] / 2.0, box[1] + box[3] / 2.0


def verfolge(je_rahmen):
    """Haltet jedes Gesicht ueber die Bilder fest.

    Luecken bis zu zehn Bilder werden fuer den Ausschnitt geschaetzt,
    zaehlen aber nicht als gesehen: da wird kein Mund eingesetzt.
    """
    n = len(je_rahmen)
    spuren = []
    for i, funde in enumerate(je_rahmen):
        benutzt = set()
        for spur in spuren:
            letzte = spur["last"]
            if letzte is None:
                continue
            lx, ly = _mitte(letzte)
            beste, bestj, bestd = None, -1, 1e9
            for j, box in enumerate(funde):
                if j in benutzt:
                    continue
                cx, cy = _mitte(box)
                d = ((cx - lx) ** 2 + (cy - ly) ** 2) ** 0.5
                grenze = max(box[2], box[3], letzte[2], letzte[3]) * 1.3
                if d < grenze and d < bestd:
                    beste, bestj, bestd = box, j, d
            if bestj >= 0:
                spur["gesehen"][i] = beste
                spur["last"] = beste
                benutzt.add(bestj)
        for j, box in enumerate(funde):
            if j in benutzt:
                continue
            gesehen = [None] * n
            gesehen[i] = box
            spuren.append({"gesehen": gesehen, "last": box})

    min_treffer = max(3, int(n * 0.08))
    bleibend = []
    for spur in spuren:
        treffer = [b for b in spur["gesehen"] if b]
        if len(treffer) < min_treffer:
            continue
        flaechen = sorted(b[2] * b[3] for b in treffer)
        xs = sorted(_mitte(b)[0] for b in treffer)
        spur["flaeche"] = flaechen[len(flaechen) // 2]
        spur["x"] = xs[len(xs) // 2]
        spur["boxen"] = _luecken(spur["gesehen"], 10)
        bleibend.append(spur)
    bleibend.sort(key=lambda s: s["flaeche"], reverse=True)
    bleibend = bleibend[:2]
    bleibend.sort(key=lambda s: s["x"])
    for i, spur in enumerate(bleibend):
        spur["seite"] = "links" if i == 0 else "rechts"
    return bleibend


def _luecken(gesehen, hoechstens):
    """Schaetzt kurze Luecken, laesst lange (abgewandter Kopf) offen."""
    n = len(gesehen)
    bekannt = [i for i, b in enumerate(gesehen) if b]
    if not bekannt:
        return [None] * n
    raus = list(gesehen)
    for a, b in zip(bekannt, bekannt[1:]):
        if b - a - 1 <= 0 or b - a - 1 > hoechstens:
            continue
        ba, bb = gesehen[a], gesehen[b]
        for i in range(a + 1, b):
            t = (i - a) / float(b - a)
            raus[i] = tuple(ba[k] + (bb[k] - ba[k]) * t for k in range(5))
    letzte = gesehen[bekannt[0]]
    for i in range(bekannt[0]):
        if bekannt[0] - i <= hoechstens:
            raus[i] = letzte
    letzte = gesehen[bekannt[-1]]
    for i in range(bekannt[-1] + 1, n):
        if i - bekannt[-1] <= hoechstens:
            raus[i] = letzte
    return raus


def ausschnitt_box(box, breite, hoehe, faktor=FAKTOR):
    """Quadratisches Fenster um das Gesicht, moeglichst im Bild."""
    x, y, w, h = box[:4]
    cx, cy = x + w / 2.0, y + h / 2.0
    seite = int(max(w, h) * faktor)
    seite = max(32, seite)
    x0 = int(round(cx - seite / 2.0))
    y0 = int(round(cy - seite / 2.0))
    if seite <= breite:
        x0 = min(max(0, x0), breite - seite)
    if seite <= hoehe:
        y0 = min(max(0, y0), hoehe - seite)
    return x0, y0, seite


def schneide(bild, rect, groesse=GROESSE):
    """Fenster aus dem Bild, Rand wird wiederholt wenn es uebersteht."""
    import cv2
    import numpy as np
    x0, y0, seite = rect
    h, w = bild.shape[:2]
    x1, y1 = x0 + seite, y0 + seite
    ix0, iy0 = max(0, x0), max(0, y0)
    ix1, iy1 = min(w, x1), min(h, y1)
    if ix1 <= ix0 or iy1 <= iy0:
        return np.zeros((groesse, groesse, 3), dtype=bild.dtype)
    stueck = bild[iy0:iy1, ix0:ix1]
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        leinwand = cv2.copyMakeBorder(
            stueck,
            max(0, -y0), max(0, y1 - h), max(0, -x0), max(0, x1 - w),
            cv2.BORDER_REPLICATE)
    else:
        leinwand = stueck
    if leinwand.shape[0] != seite or leinwand.shape[1] != seite:
        leinwand = cv2.resize(leinwand, (seite, seite), interpolation=cv2.INTER_LINEAR)
    if seite != groesse:
        leinwand = cv2.resize(leinwand, (groesse, groesse), interpolation=cv2.INTER_LINEAR)
    return leinwand


def lege(ziel, quelle, rect):
    """Setzt den quadratischen Kopfclip zurueck an seine Stelle."""
    import cv2
    x0, y0, seite = rect
    h, w = ziel.shape[:2]
    gross = cv2.resize(quelle, (seite, seite), interpolation=cv2.INTER_LINEAR)
    x1, y1 = x0 + seite, y0 + seite
    dx0, dy0 = max(0, x0), max(0, y0)
    dx1, dy1 = min(w, x1), min(h, y1)
    if dx1 <= dx0 or dy1 <= dy0:
        return ziel
    sx0, sy0 = dx0 - x0, dy0 - y0
    ziel[dy0:dy1, dx0:dx1] = gross[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]
    return ziel


def mund_maske(form, box, weich=31):
    """Weiche Maske nur ueber Mund und Kinn, die Augen bleiben vom Szenenclip."""
    import cv2
    import numpy as np
    h, w = form[:2]
    maske = np.zeros((h, w), dtype=np.uint8)
    x, y, fw, fh = box[:4]
    cx, cy = int(round(x + fw / 2.0)), int(round(y + fh * 0.68))
    rx, ry = max(4, int(fw * 0.26)), max(3, int(fh * 0.11))
    cv2.ellipse(maske, (cx, cy), (rx, ry), 0, 0, 360, 255, -1)
    k = int(max(fw, fh) * 0.16)
    k = max(7, k)
    if k % 2 == 0:
        k += 1
    maske = cv2.GaussianBlur(maske, (k, k), 0)
    return maske


def mischen(orig, sync_bild, rect, box):
    """Legt nur den Mund des synchronisierten Kopfes auf das Szenenbild."""
    import numpy as np
    voll = orig.copy()
    lege(voll, sync_bild, rect)
    maske = mund_maske(orig.shape, box)
    alpha = (maske.astype("float32") / 255.0)[:, :, None]
    return (orig.astype("float32") * (1.0 - alpha) + voll.astype("float32") * alpha).astype(orig.dtype)


def aktive_rahmen(zeiten, fps, anzahl, vor=0.04, nach=0.14):
    """Bilder, in denen dieser Avatar gerade redet, plus ein kleiner Rand."""
    treffer = set()
    for start, ende in zeiten or []:
        i0 = int((float(start) - vor) * fps)
        i1 = int((float(ende) + nach) * fps) + 1
        for i in range(max(0, i0), min(anzahl, max(i0 + 1, i1))):
            treffer.add(i)
    return treffer


def paare(redner, spuren, besetzung):
    """[(Name, Spur), ...]. Erster Name links, zweiter rechts."""
    if not redner or not spuren:
        return []
    if len(spuren) >= 2 and len(redner) >= 2:
        return [(redner[0], spuren[0]), (redner[1], spuren[1])]
    if len(spuren) == 1 and len(redner) == 1:
        return [(redner[0], spuren[0])]
    if len(redner) == 1:
        name = redner[0]
        stelle = 0
        for i, n in enumerate(besetzung or []):
            if str(n).strip().lower() == name.strip().lower():
                stelle = i
                break
        if len(besetzung or []) <= 1:
            return [(name, max(spuren, key=lambda s: s.get("flaeche") or 0))]
        return [(name, spuren[0 if stelle <= 0 else min(1, len(spuren) - 1)])]
    return [(redner[0], spuren[0])]


def zeiten_von(stuecke):
    """{Name: [(start, ende), ...]} entlang der Stuecke in Textreihenfolge."""
    t, raus = 0.0, {}
    for name, _pfad, dauer in stuecke:
        dauer = max(0.0, float(dauer or 0))
        if name and dauer > 0:
            raus.setdefault(name, []).append((t, t + dauer))
        t += dauer
    return raus, t


def _spur(stuecke, wer, ziel):
    """Eine Spur: dieser Sprecher redet, alle anderen Stellen sind Stille."""
    eingaben, teile, nr = [], [], 0
    for name, pfad, dauer in stuecke:
        if dauer <= 0.01:
            continue
        if (name or "").strip().lower() == (wer or "").strip().lower() and pfad:
            eingaben += ["-i", str(pfad)]
        else:
            eingaben += ["-f", "lavfi", "-t", "%.3f" % dauer, "-i", "anullsrc=r=44100:cl=mono"]
        teile.append("[%d:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=mono[a%d]"
                     % (nr, nr))
        nr += 1
    if not nr:
        return None
    filt = ";".join(teile) + ";" + "".join("[a%d]" % i for i in range(nr))
    filt += "concat=n=%d:v=0:a=1[out]" % nr
    r = _lauf(["ffmpeg", "-y", "-loglevel", "error"] + eingaben
              + ["-filter_complex", filt, "-map", "[out]",
                 "-c:a", "libmp3lame", "-q:a", "4", str(ziel)])
    if r.returncode != 0 or not os.path.exists(ziel):
        print("[Lippen] Spur fuer %s ging nicht: %s" % (wer, (r.stderr or "")[-160:]))
        return None
    return str(ziel)


def _zusammen(stuecke, ziel):
    """Alle Zeilen hintereinander, auch der Erzaehler. Das hoert man im Clip."""
    if len(stuecke) == 1 and stuecke[0][1] and os.path.exists(stuecke[0][1]):
        shutil.copyfile(stuecke[0][1], ziel)
        return ziel
    eingaben, teile, nr = [], [], 0
    for _name, pfad, dauer in stuecke:
        if dauer <= 0.01:
            continue
        if pfad and os.path.exists(pfad):
            eingaben += ["-i", str(pfad)]
        else:
            eingaben += ["-f", "lavfi", "-t", "%.3f" % max(0.05, dauer),
                         "-i", "anullsrc=r=44100:cl=mono"]
        teile.append("[%d:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=mono[a%d]"
                     % (nr, nr))
        nr += 1
    if not nr:
        return None
    filt = ";".join(teile) + ";" + "".join("[a%d]" % i for i in range(nr))
    filt += "concat=n=%d:v=0:a=1[out]" % nr
    r = _lauf(["ffmpeg", "-y", "-loglevel", "error"] + eingaben
              + ["-filter_complex", filt, "-map", "[out]",
                 "-c:a", "libmp3lame", "-q:a", "4", str(ziel)])
    if r.returncode != 0 or not os.path.exists(ziel):
        return None
    return str(ziel)


def _eintrag(kanal):
    import animation
    import schluessel
    e = animation._slot(kanal, "lippen")
    if e and (e.get("url") or "").strip():
        return e
    ref = animation.ref_slot(kanal) or animation._slot(kanal, "video") or {}
    key = schluessel.fuer(kanal, ref) if ref else ""
    if not key:
        key = schluessel.aus_umgebung("fal")
    return {"url": STANDARD_URL, "key": key}


def _fal_clip(kanal, video, audio, ziel, sag):
    """Kopfclip plus Tonspur an das Lippenmodell. Pfad oder None."""
    import animation
    import schluessel
    e = _eintrag(kanal)
    key = (e.get("key") or "").strip() or schluessel.fuer(kanal, e)
    if not key:
        sag("kein fal-Schluessel fuer die Lippen")
        return None
    basis = animation._basis_url(e.get("url") or STANDARD_URL)
    sag("lade Kopf und Stimme hoch")
    vurl = animation.m18_hochladen(video, key)
    aurl = animation.m18_hochladen(audio, key)
    if not vurl or not aurl or str(vurl).startswith("data:"):
        sag("Hochladen zu fal ging nicht")
        return None
    adresse = (e.get("url") or "").lower()
    if "kling" in adresse and "lipsync" in adresse:
        koerper = {"video_url": vurl, "audio_url": aurl}
    else:
        koerper = {"video_url": vurl, "audio_url": aurl,
                   "model": "lipsync-2", "sync_mode": "cut_off"}
    try:
        start = animation._hole(basis, key, koerper, zeit=120)
    except urllib.error.HTTPError as f:
        roh = ""
        try:
            roh = f.read().decode("utf-8", "replace")[:240]
        except Exception:
            pass
        sag("Lippenmodell lehnt ab (%s). %s" % (f.code, roh))
        return None
    except Exception as f:
        sag("keine Verbindung zum Lippenmodell: %s" % str(f)[:140])
        return None
    return _warten(basis, key, start, ziel, sag)


def _warten(basis, key, start, ziel, sag):
    import animation
    status_url = start.get("status_url")
    antwort_url = start.get("response_url")
    if not status_url and not antwort_url:
        url = animation._video_url(start)
        return animation._laden(url, ziel) if url else None
    t0, st, gemeldet, gesagt = time.time(), {}, "", 0
    while time.time() - t0 < WARTE_MAX:
        time.sleep(TAKT)
        try:
            st = animation._hole(status_url, key, zeit=40)
        except Exception:
            continue
        lage = (st.get("status") or "").upper()
        lief = int(time.time() - t0)
        if lage != gemeldet or lief - gesagt >= 30:
            gemeldet, gesagt = lage, lief
            sag("%s, %d:%02d" % (lage or "laeuft", lief // 60, lief % 60))
        if lage == "COMPLETED":
            break
        if st.get("error"):
            sag("Lippenmodell: %s" % str(st.get("error"))[:200])
            return None
    else:
        sag("Lippenmodell nach %d Minuten nicht fertig" % int(WARTE_MAX / 60))
        return None
    fertig = animation._ergebnis_holen(basis, key, start, st, status_url, antwort_url)
    url = animation._video_url(fertig) if fertig else None
    if not url:
        sag("Lippenmodell lieferte kein Video")
        return None
    return animation._laden(url, ziel)


def _kanal(k):
    if isinstance(k, dict):
        k.setdefault("_key", k.get("id") or "")
        return k
    import einstellungen
    d = dict(einstellungen.laden().get(k) or {})
    d.setdefault("_key", k)
    return d


def _sichtbare(k, s):
    import darsteller
    wer = s.get("wer") if isinstance(s, dict) else None
    nur = [str(x) for x in wer if str(x or "").strip()] if isinstance(wer, list) and wer else None
    return [x["name"] for x in darsteller.besetzung(k, nur)]


def _stuecke(k, kanal, s, ordner):
    """Gesprochene Zeilen als Dateien, Regieanweisungen ausgelassen."""
    import medien
    import szenen_video as sv
    text, _regie = sv._regie_trennen(s.get("text") or "")
    namen = sv._r15_namen(kanal)
    zeilen = sv._r15_zerlegen(text, namen)
    roh = []
    for i, (wer, wort) in enumerate(zeilen):
        if not (wort or "").strip():
            continue
        ziel = os.path.join(ordner, "zeile_%02d.mp3" % i)
        stimme = None
        if wer:
            try:
                stimme = sv._stimme_fuer(kanal, wer)
            except Exception:
                stimme = None
        try:
            medien.erzeuge_stimme(kanal, wort, ziel, stimme_id=stimme)
        except TypeError:
            medien.erzeuge_stimme(kanal, wort, ziel)
        dauer = ton_laenge(ziel)
        if dauer <= 0.05:
            return []
        roh.append((wer or "", ziel, dauer))
    return roh


def kopf_clip(dateien, spur, fps, ordner, breite, hoehe):
    """Schreibt den Kopf als eigenen Clip und die Fenster je Bild."""
    import cv2
    kopf = os.path.join(ordner, "kopf")
    os.makedirs(kopf, exist_ok=True)
    rechtecke, letzte = [], None
    for i, pfad in enumerate(dateien):
        box = spur["boxen"][i] if i < len(spur["boxen"]) else None
        if box is None and letzte is not None:
            box = letzte
        if box is None:
            rechtecke.append(None)
            bild = cv2.imread(pfad)
            leer = schneide(bild, (0, 0, min(breite, hoehe)), GROESSE) if bild is not None else None
            if leer is not None:
                cv2.imwrite(os.path.join(kopf, "%05d.jpg" % i), leer, [cv2.IMWRITE_JPEG_QUALITY, 92])
            continue
        rect = ausschnitt_box(box, breite, hoehe)
        letzte = box
        rechtecke.append(rect)
        bild = cv2.imread(pfad)
        if bild is None:
            continue
        cv2.imwrite(os.path.join(kopf, "%05d.jpg" % i), schneide(bild, rect),
                    [cv2.IMWRITE_JPEG_QUALITY, 92])
    teile = sorted(glob.glob(os.path.join(kopf, "*.jpg")))
    clip = rahmen_packen(teile, fps, os.path.join(ordner, "kopf.mp4"))
    return clip, rechtecke


def zurueck(dateien, sync_video, spur, rechtecke, aktiv, ordner):
    """Setzt die Muender auf die Szenenbilder. Gibt die neuen Dateien zurueck."""
    import cv2
    sync_ordner = os.path.join(ordner, "sync")
    os.makedirs(sync_ordner, exist_ok=True)
    rahmen_holen(sync_video, sync_ordner)
    syncs = sorted(glob.glob(os.path.join(sync_ordner, "*.jpg")))
    if not syncs:
        return None
    raus_ordner = os.path.join(ordner, "fertig")
    os.makedirs(raus_ordner, exist_ok=True)
    n, ns = len(dateien), len(syncs)
    geschrieben = []
    for i, pfad in enumerate(dateien):
        orig = cv2.imread(pfad)
        if orig is None:
            continue
        ziel = os.path.join(raus_ordner, "%05d.jpg" % i)
        gesehen = spur["gesehen"][i] if i < len(spur["gesehen"]) else None
        rect = rechtecke[i] if i < len(rechtecke) else None
        if i not in aktiv or gesehen is None or rect is None:
            cv2.imwrite(ziel, orig, [cv2.IMWRITE_JPEG_QUALITY, 92])
            geschrieben.append(ziel)
            continue
        j = i if ns == n else int(round(i * (ns - 1) / float(max(1, n - 1))))
        j = max(0, min(ns - 1, j))
        kopf = cv2.imread(syncs[j])
        if kopf is None:
            cv2.imwrite(ziel, orig, [cv2.IMWRITE_JPEG_QUALITY, 92])
        else:
            cv2.imwrite(ziel, mischen(orig, kopf, rect, gesehen),
                        [cv2.IMWRITE_JPEG_QUALITY, 92])
        geschrieben.append(ziel)
    return geschrieben


def nachziehen(k, sid, melden=None):
    """Haengt die Muender an den schon erzeugten Szenenclip.

    Gibt (True, Text) bei Erfolg, (None, "") wenn in der Szene niemand
    im Bild redet, (False, Grund) wenn es nicht geklappt hat.
    """
    def sag(t):
        print("[Lippen] %s" % t)
        if melden and t:
            try:
                melden(t)
            except Exception:
                pass

    if not _welche("ffmpeg"):
        return False, "ffmpeg fehlt auf dem Server"
    try:
        import cv2  # noqa: F401
    except Exception:
        return False, "opencv fehlt. Auf dem Server: pip install opencv-python-headless"

    import szenen
    kanal = _kanal(k)
    s = szenen.r3_szene(k, sid) if not isinstance(k, dict) else None
    if s is None and isinstance(k, dict):
        s = szenen.r3_szene(k, sid)
    if not s:
        return False, "Szene unbekannt"
    name = s.get("clip") or ""
    clip = szenen.datei_pfad(k, name) if name else ""
    if not clip or not os.path.exists(clip):
        return False, "kein Szenenclip"

    import szenen as _sz
    redner = []
    try:
        redner = _sz.r19_redner(k, s.get("text") or "")
    except Exception as e:
        return False, "Sprecher nicht lesbar: %s" % str(e)[:120]
    sichtbar = _sichtbare(k, s)
    def _dabei(n):
        return any(n.strip().lower() == x.strip().lower() for x in sichtbar)
    redner = [n for n in redner if _dabei(n)]
    if not redner:
        return None, ""

    arbeit = tempfile.mkdtemp(prefix="lippen_")
    try:
        sag("Stimmen fuer %s" % ", ".join(redner))
        stuecke = _stuecke(k, kanal, s, arbeit)
        if not stuecke:
            return False, "Stimmen liessen sich nicht erzeugen"
        wann, sprach_dauer = zeiten_von(stuecke)
        if sprach_dauer <= 0.2:
            return False, "Stimme ist leer"

        info = masse(clip)
        if not info:
            return False, "Clip laesst sich nicht lesen"
        breite, hoehe, fps, _dauer = info
        arbeitsclip = clip
        if sprach_dauer > _dauer + 0.15:
            sag("Sprache ist laenger als der Clip, letztes Bild bleibt stehen")
            verlaengert = video_auf_laenge(clip, sprach_dauer, os.path.join(arbeit, "lang.mp4"))
            if not verlaengert:
                return False, "Clip liess sich nicht auf die Sprachlaenge bringen"
            arbeitsclip = verlaengert
            info = masse(arbeitsclip) or info
            breite, hoehe, fps = info[0], info[1], info[2]

        ziellaenge = masse(arbeitsclip)[3]
        spuren_ton = {}
        for n in redner:
            roh = _spur(stuecke, n, os.path.join(arbeit, "spur_%s.mp3" % _dateiname(n)))
            if not roh:
                return False, "Tonspur fuer %s ging nicht" % n
            fertig = auf_laenge(roh, ziellaenge, os.path.join(arbeit, "fest_%s.mp3" % _dateiname(n)))
            if not fertig:
                return False, "Tonspur fuer %s liess sich nicht anpassen" % n
            spuren_ton[n] = fertig
        gesamt = _zusammen(stuecke, os.path.join(arbeit, "gesamt.mp3"))
        if gesamt:
            gesamt = auf_laenge(gesamt, ziellaenge, os.path.join(arbeit, "gesamt_fest.mp3")) or gesamt

        sag("Gesichter suchen")
        bilder = rahmen_holen(arbeitsclip, os.path.join(arbeit, "rahmen"))
        if not bilder:
            return False, "keine Bilder im Clip"
        modell = yunet_pfad()
        if not modell:
            return False, "Gesichtsmodell nicht geladen"
        det = _detektor(modell, breite, hoehe)
        import cv2
        funde = []
        for pfad in bilder:
            bild = cv2.imread(pfad)
            funde.append(erkenne(bild, det) if bild is not None else [])
        gesichter = verfolge(funde)
        if not gesichter:
            return False, "keine Gesichter im Vordergrund gefunden"
        zuordnung = paare(redner, gesichter, sichtbar)
        if not zuordnung:
            return False, "Sprecher und Gesichter passen nicht zusammen"
        sag(", ".join("%s %s" % (n, sp["seite"]) for n, sp in zuordnung))

        aktuell = bilder
        geschafft = []
        gruende = []
        for n, spur in zuordnung:
            kopf, rechtecke = kopf_clip(aktuell, spur, fps, os.path.join(arbeit, _dateiname(n)),
                                        breite, hoehe)
            if not kopf:
                gruende.append("%s: Kopfclip ging nicht" % n)
                sag(gruende[-1])
                continue
            ziel = os.path.join(arbeit, "sync_%s.mp4" % _dateiname(n))
            sag("%s: Mund wird gesetzt" % n)
            sync = _fal_clip(kanal, kopf, spuren_ton[n], ziel, sag)
            if not sync:
                sag("%s: noch einmal" % n)
                time.sleep(8)
                sync = _fal_clip(kanal, kopf, spuren_ton[n], ziel, sag)
            if not sync:
                gruende.append("%s: Lippenmodell hat nichts geliefert" % n)
                sag(gruende[-1])
                continue
            aktiv = aktive_rahmen(_zeiten_fuer(wann, n), fps, len(aktuell))
            neu = zurueck(aktuell, sync, spur, rechtecke, aktiv, os.path.join(arbeit, "zurueck_" + _dateiname(n)))
            if not neu:
                gruende.append("%s: Mund liess sich nicht zuruecklegen" % n)
                sag(gruende[-1])
                continue
            aktuell = neu
            geschafft.append(n)

        if not geschafft:
            return False, "kein Mund gesetzt"
        endname = "clip_%s_%s_lippen.mp4" % (
            __import__("re").sub(r"[^A-Za-z0-9]+", "", str(sid))[:12],
            time.strftime("%H%M%S"))
        endpfad = os.path.join(szenen.ordner(k), endname)
        if not rahmen_packen(aktuell, fps, endpfad, gesamt):
            return False, "fertiger Clip liess sich nicht schreiben"
        gesetzt = szenen.r3_clip_setzen(k, sid, endname)
        if not gesetzt.get("ok"):
            return False, gesetzt.get("fehler") or "Clip nicht angenommen"
        if len(geschafft) < len(zuordnung):
            return True, "lippensynchron (%s). %s" % (
                ", ".join(geschafft), " ".join(gruende))
        return True, "lippensynchron, " + " und ".join(
            "%s %s" % (n, sp["seite"]) for n, sp in zuordnung)
    finally:
        shutil.rmtree(arbeit, ignore_errors=True)


def _zeiten_fuer(wann, name):
    """Zeiten unabhaengig von Grossschreibung des Namens."""
    ziel = (name or "").strip().lower()
    for schluessel, spanne in (wann or {}).items():
        if (schluessel or "").strip().lower() == ziel:
            return spanne
    return []


def _dateiname(name):
    import re
    return re.sub(r"[^A-Za-z0-9]+", "", name or "x")[:24] or "x"


# ---------- Pruefung ohne API und ohne Gesichtermodell ----------

def pruefen():
    """Reine Bildrechnung: Mund landet nur im Mund, der Rest bleibt."""
    import cv2
    import numpy as np
    orig = np.zeros((200, 320, 3), dtype=np.uint8)
    orig[:, :] = (40, 80, 40)
    cv2.rectangle(orig, (0, 0), (30, 30), (10, 10, 200), -1)
    box = (100, 40, 80, 100, 0.9)
    sync = np.zeros((GROESSE, GROESSE, 3), dtype=np.uint8)
    sync[:, :] = (0, 0, 255)
    rect = ausschnitt_box(box, 320, 200)
    bild = mischen(orig, sync, rect, box)
    ecke = bild[5, 5].tolist()
    if ecke != [10, 10, 200]:
        raise SystemExit("Ecke wurde veraendert: %s" % ecke)
    cx, cy = int(box[0] + box[2] / 2), int(box[1] + box[3] * 0.72)
    mund = bild[cy, cx].tolist()
    if mund[2] < 180:
        raise SystemExit("Mund wurde nicht gesetzt: %s" % mund)
    auge_y = int(box[1] + box[3] * 0.35)
    auge = bild[auge_y, cx].tolist()
    if auge[1] < 50:
        raise SystemExit("Auge wurde mitveraendert: %s" % auge)
    spuren = [
        {"x": 400, "flaeche": 10, "seite": "rechts"},
        {"x": 100, "flaeche": 50, "seite": "links"},
    ]
    spuren_sortiert = sorted(spuren, key=lambda s: s["x"])
    z = paare(["Mara", "Jonas"], spuren_sortiert, ["Mara", "Jonas"])
    if [a[0] for a in z] != ["Mara", "Jonas"]:
        raise SystemExit("Zuordnung falsch: %s" % z)
    if z[0][1]["seite"] != "links" or z[1][1]["seite"] != "rechts":
        raise SystemExit("Seiten falsch")
    aktiv = aktive_rahmen([(1.0, 1.2)], 10, 30)
    if 9 not in aktiv or 13 not in aktiv or 0 in aktiv:
        raise SystemExit("Zeiten falsch: %s" % sorted(aktiv))
    print("OK  Mund nur im Mund, links bleibt links")
    return True


if __name__ == "__main__":
    pruefen()
