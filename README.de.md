# LibreCrawl 🇩🇪

Ein webbasierter SEO-Crawler für Website-Analysen und technische SEO-Audits — kostenlos, quelloffen und ohne Abonnement.

🌐 **Website**: [librecrawl.com](https://librecrawl.com)  
📖 **API-Dokumentation**: [librecrawl.com/api/docs](https://librecrawl.com/api/docs/)

> LibreCrawl wird ***immer*** kostenlos und quelloffen bleiben.  
> Wenn es deine Screaming-Frog-Lizenz für 259 $/Jahr ersetzt, freut sich der Entwickler über einen [Kaffee ☕](https://www.paypal.com/donate/?business=7H9HFA3385JS8&no_recurring=0&item_name=Continue+the+development+of+LibreCrawl&currency_code=AUD).

---

## Was LibreCrawl macht

LibreCrawl crawlt Websites und liefert detaillierte Informationen zu Seiten, Links, SEO-Elementen und Performance. Es ist als Webanwendung auf Basis von Python Flask gebaut und unterstützt mehrere gleichzeitige Benutzer mit isolierten Sitzungen.

## Features

- 🚀 **Multi-Tenancy** – Mehrere Benutzer können gleichzeitig crawlen, vollständig isoliert
- 🌍 **Deutsche & englische Oberfläche** – Sprachumschalter (DE/EN) in der Kopfzeile
- 🎨 **Eigenes CSS** – Oberfläche mit eigenem CSS-Theme personalisieren
- 🔄 **JavaScript-Rendering** für dynamische Inhalte (React, Vue, Angular usw.)
- 📊 **SEO-Analyse** – Titel, Meta-Beschreibungen, Überschriften, Author, Canonical u.v.m.
- 🔗 **Link-Analyse** – Interne und externe Links mit detaillierter Beziehungskarte
- 📈 **PageSpeed-Insights-Integration** – Core Web Vitals analysieren
- 💾 **Mehrere Exportformate** – CSV, JSON oder XML
- 🔍 **Problemerkennung** – Automatische SEO-Fehler- und Warnungserkennung
- ⚡ **Echtzeit-Fortschritt** mit Live-Statistiken

---

## Installation

### Schnellstart (automatisch)

**Windows:**
```batch
start-librecrawl.bat
```

**Linux/Mac:**
```bash
chmod +x start-librecrawl.sh
./start-librecrawl.sh
```

Das Skript prüft automatisch, ob Docker vorhanden ist, installiert Abhängigkeiten und öffnet LibreCrawl unter `http://localhost:5000`.

---

### Manuelle Installation

#### Option 1: Docker (empfohlen)

**Voraussetzungen:** Docker und Docker Compose

```bash
# Repository klonen
git clone https://github.com/PhialsBasement/LibreCrawl.git
cd LibreCrawl

# Umgebungsdatei kopieren
cp .env.example .env

# Starten
docker compose up -d

# Browser öffnen: http://localhost:5000
```

**Lokaler Betrieb** (Standard — kein Login erforderlich):
```bash
# .env
LOCAL_MODE=true
HOST_BINDING=127.0.0.1
```

**Produktionsbetrieb** (mit Benutzeranmeldung):
```bash
# .env
LOCAL_MODE=false
HOST_BINDING=0.0.0.0
```

Nach Änderungen den Container neu bauen:
```bash
docker compose up -d --build
```

---

#### Option 2: Python

**Voraussetzungen:** Python 3.8+

```bash
# Abhängigkeiten installieren
pip install -r requirements.txt

# Optional: JavaScript-Rendering
playwright install chromium

# Starten (lokaler Modus, kein Login)
python main.py --local

# Starten (Standard mit Authentifizierung)
python main.py
```

Browser öffnen: `http://localhost:5000`

---

## Betriebsmodi

| Modus | Beschreibung |
|---|---|
| **Lokalmodus** (`--local`) | Kein Login, alle Benutzer erhalten Admin-Rechte — ideal für Einzelnutzer |
| **Standardmodus** | Vollständiges Authentifizierungssystem mit Benutzerrollen und Ratelimits |

---

## Einstellungen

Über den Button **„Einstellungen"** konfigurierbar:

| Bereich | Optionen |
|---|---|
| **Crawler** | Crawl-Tiefe (bis 5 Mio. URLs), Verzögerung, externe Links |
| **Anfragen** | User Agent, Timeouts, Proxy, robots.txt |
| **JavaScript** | Browser-Engine, Wartezeit, Viewport-Größe |
| **Filter** | Dateitypen und URL-Muster ein-/ausschließen |
| **Export** | Format und Felder auswählen |
| **Eigenes CSS** | Oberfläche mit eigenem Stylesheet anpassen |
| **Problem-Ausschluss** | Muster für die SEO-Problemerkennung ausschließen |

Für PageSpeed-Analysen einen Google-API-Schlüssel unter **Einstellungen → Anfragen** eintragen (25.000 Anfragen/Tag statt limitiertem Kontingent).

---

## Exportformate

- **CSV** – Für Tabellenkalkulationen (Excel, Google Sheets)
- **JSON** – Strukturierte Daten mit allen Details
- **XML** – Für externe Tools und Weiterverarbeitung

---

## Plugins

Eigene Plugins als `.js`-Datei in `/web/static/plugins/` ablegen — sie erscheinen automatisch als neuer Tab in der Oberfläche.

```javascript
LibreCrawlPlugin.register({
  id: 'mein-plugin',
  name: 'Mein Plugin',
  tab: { label: 'Mein Tab', icon: '🔥' },

  onTabActivate(container, data) {
    // data enthält: { urls, links, issues, stats }
    container.innerHTML = `
      <div class="plugin-content" style="padding: 20px; overflow-y: auto; max-height: calc(100vh - 280px);">
        <h2>Meine Analyse</h2>
        <p>${data.urls.length} URLs gefunden</p>
      </div>
    `;
  }
});
```

Beispiel-Plugins: `_example-plugin.js` (Vorlage) und `e-e-a-t.js` (E-E-A-T-Analyse).

---

## Bekannte Einschränkungen

- PageSpeed API hat Ratelimits (mit API-Schlüssel deutlich besser)
- Große Websites benötigen mehr Zeit
- JavaScript-Rendering ist langsamer als reines HTTP-Crawling
- Einstellungen werden im Browser-LocalStorage gespeichert (gehen verloren, wenn Browser-Daten gelöscht werden)

---

## Projektstruktur

```
main.py                  – Flask-Server und Haupt-Einstiegspunkt
src/crawler.py           – Kern-Crawling-Engine
src/core/seo_extractor.py – SEO-Datenextraktion
src/crawl_db.py          – Datenbankoperationen
web/templates/           – HTML-Templates
web/static/js/           – Frontend-JavaScript
web/static/locales/      – Übersetzungsdateien (de.json, en.json)
web/static/plugins/      – Eigene Plugins
```

---

## Lizenz

MIT License — siehe [LICENSE](LICENSE).

---

## Danksagung

Herzlichen Dank an **[PhialsBasement](https://github.com/PhialsBasement)** für die Entwicklung von LibreCrawl und dafür, dass er es der Community als freies, quelloffenes Werkzeug zur Verfügung stellt.
Dieses Projekt wäre ohne seine Arbeit nicht möglich.
