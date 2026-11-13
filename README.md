# AiUniverse-Lipsync

Klon von [Aiuniverse](https://github.com/MyFunAppStudio/Aiuniverse) mit einem
Unterschied: Kling und MiniMax bewegen die Szene weiter wie bisher, und
danach werden die Muender der Avatare auf ihre Stimmen gesetzt.

Die Szene kommt vom Referenzclip (Hintergrund, beide Avatare, Regie).
Die Sprache lag bisher nur darueber, die Lippen blieben stumm, weil
reference-to-video die Tonspur nie sieht. `lippen.py` schneidet danach
jeden Kopf aus, schickt ihn mit der eigenen Stimme an
`fal-ai/sync-lipsync/v2` und legt nur den Mund zurueck. Gesten, Feuer
und Kamera bleiben vom Szenenclip.

Wer im Text zuerst spricht, steht links. Der zweite rechts.

Parallel zum laufenden AiUniverse, einmal. `/root/aiuniverse` und Dienst
`dashboard2` bleiben, wie sie sind. Nicht `git remote set-url` im alten
Ordner ausfuehren.

```sh
git clone https://github.com/MyFunAppStudio/Aiuniverse-Lipsync.git /root/aiuniverse-lipsync
cp -a /root/aiuniverse/regeln /root/aiuniverse-lipsync/regeln
cp -a /root/aiuniverse/.env /root/aiuniverse-lipsync/.env
cp -a /root/aiuniverse/eigene /root/aiuniverse-lipsync/eigene
pip3 install opencv-python-headless
cp /root/aiuniverse-lipsync/dashboard2-lipsync.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now dashboard2-lipsync
```

Dashboard der Kopie: Port **8092**. Das alte bleibt auf 8091.
Danach nur noch `sh /root/aiuniverse-lipsync/aktualisiere.sh`.
Das Skript bricht ab, wenn es versehentlich in `/root/aiuniverse` liegt.
Der Slot "Lippen auf den Clip" darf leer bleiben: genommen wird dann
sync-lipsync mit dem fal-Schluessel des Referenzclips. Wer lieber Kling
Lip-Sync will, traegt dort `fal-ai/kling-video/lipsync/audio-to-video` ein.

# AiUniverse

Automatische Videoproduktion auf eigenem Server. Erzeugt aus einem Thema
Text, Szenenbilder, Clips, Stimme und ein fertiges Video im Hochformat.

Die Kopie laeuft unter `/root/aiuniverse-lipsync` auf Port 8092.
Das alte Programm bleibt unter `/root/aiuniverse` auf Port 8091.

## Aktualisieren

Nur die Kopie:

```sh
sh /root/aiuniverse-lipsync/aktualisiere.sh
```

Holt die neueste Fassung, prueft sie und startet das Dashboard neu.
Zurueck auf den vorherigen Stand geht ueber `git reset --hard <stand>`;
das Skript nennt den passenden Befehl, falls etwas klemmt.

## Was NICHT in diesem Repo liegt

Bewusst ausgeschlossen, siehe `.gitignore`:

| Ordner | Inhalt |
|---|---|
| `regeln/` | API-Schluessel, Dashboard-Passwort, Kanal-Einstellungen, Szenen |
| `eigene/` | hochgeladene Bilder, Darstellerbilder, erzeugte Clips |
| `fertige_videos/`, `gs/`, `pr/` | erzeugte Medien und Zwischenstaende |
| `*.bak_*` | Sicherungskopien aelterer Patches |

Die Schluessel verlassen den Server nicht.

## Aufbau

| Datei | Aufgabe |
|---|---|
| `dashboard2.py` / `dashboard2.html` | Oberflaeche und Weboberflaeche |
| `einstellungen.py` | Kanaele, Modelle, Slots |
| `schluessel.py` | Zugriff auf die hinterlegten Schluessel |
| `text_generator.py` | Text zum Thema |
| `geschichte.py` | zerlegt den Text in Szenen, baut Bildprompts |
| `bilder.py` | erzeugt die Szenenbilder |
| `darsteller.py` | zwei wiederkehrende Figuren mit Kleidungssaetzen |
| `animation.py` | Clips aus Bildern, auch Referenzclips mit Darstellern |
| `szenen.py` | Szenenliste je Kanal |
| `szenen_video.py` | baut aus Szenen, Stimme und Musik das Video |
| `figuren.py` | aeltere, freigestellte Figuren zum Aufkleben |
| `themen.py`, `vorlagen.py` | Themenliste und Vorlagen |
| `telegram_sender.py` | Versand des fertigen Videos |
