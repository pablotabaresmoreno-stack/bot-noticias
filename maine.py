import os
import re
import smtplib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime

# ─── Configuracion ────────────────────────────────────────────────────────────
GEMINI_API_KEY  = os.environ["GEMINI_API_KEY"]
GMAIL_USER      = os.environ["GMAIL_USER"]
GMAIL_PASSWORD  = os.environ["GMAIL_PASSWORD"]
RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]

# ─── Fuentes RSS — los mejores medios economicos del mundo ────────────────────
RSS_SOURCES = [
    # Globales
    {"name": "Reuters Business",        "cat": "Economia Global",  "url": "https://feeds.reuters.com/reuters/businessNews"},
    {"name": "Bloomberg Markets",       "cat": "Mercados y Bolsa", "url": "https://feeds.bloomberg.com/markets/news.rss"},
    {"name": "Financial Times",         "cat": "Mercados y Bolsa", "url": "https://www.ft.com/rss/home"},
    {"name": "The Economist",           "cat": "Economia Global",  "url": "https://www.economist.com/finance-and-economics/rss.xml"},
    {"name": "Wall Street Journal",     "cat": "Mercados y Bolsa", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"},
    {"name": "CNBC Economy",            "cat": "Economia Global",  "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"},
    {"name": "MarketWatch",             "cat": "Mercados y Bolsa", "url": "https://feeds.marketwatch.com/marketwatch/topstories/"},
    {"name": "Forbes Business",         "cat": "Economia Global",  "url": "https://www.forbes.com/business/feed/"},
    {"name": "Business Insider",        "cat": "Economia Global",  "url": "https://feeds.businessinsider.com/custom/all"},
    {"name": "Yahoo Finance",           "cat": "Mercados y Bolsa", "url": "https://finance.yahoo.com/rss/topfinstories"},
    {"name": "Investing.com",           "cat": "Mercados y Bolsa", "url": "https://www.investing.com/rss/news.rss"},
    # Cripto
    {"name": "CoinDesk",                "cat": "Criptomonedas",    "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "CoinTelegraph",           "cat": "Criptomonedas",    "url": "https://cointelegraph.com/rss"},
    {"name": "Decrypt",                 "cat": "Criptomonedas",    "url": "https://decrypt.co/feed"},
    {"name": "The Block",               "cat": "Criptomonedas",    "url": "https://www.theblock.co/rss.xml"},
    # Colombia y LATAM
    {"name": "Portafolio",              "cat": "Colombia y LATAM", "url": "https://www.portafolio.co/rss/portafolio.xml"},
    {"name": "El Colombiano",           "cat": "Colombia y LATAM", "url": "https://www.elcolombiano.com/rss/economia.xml"},
    {"name": "Semana Economia",         "cat": "Colombia y LATAM", "url": "https://www.semana.com/rss/economia.xml"},
    {"name": "El Tiempo Economia",      "cat": "Colombia y LATAM", "url": "https://www.eltiempo.com/rss/economia.xml"},
    {"name": "Dinero Colombia",         "cat": "Colombia y LATAM", "url": "https://www.dinero.com/rss/economia.xml"},
    {"name": "La Republica",            "cat": "Colombia y LATAM", "url": "https://www.larepublica.co/rss/economia"},
    {"name": "Infobae Economia",        "cat": "Colombia y LATAM", "url": "https://www.infobae.com/feeds/rss/economia/"},
    {"name": "El Pais Economia",        "cat": "Economia Global",  "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada"},
    {"name": "America Economia",        "cat": "Colombia y LATAM", "url": "https://www.americaeconomia.com/rss.xml"},
    # Instituciones
    {"name": "Banco Mundial",           "cat": "Instituciones",    "url": "https://feeds.worldbank.org/worldbank/finances/rss.xml"},
    {"name": "FMI",                     "cat": "Instituciones",    "url": "https://www.imf.org/en/News/rss?language=eng"},
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EconBot/2.0)"}

# ─── 1. Leer RSS ──────────────────────────────────────────────────────────────
def fetch_rss(source: dict, cutoff: datetime) -> list:
    try:
        resp = requests.get(source["url"], headers=HEADERS, timeout=12)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        print(f"  [x] {source['name']}: {e}")
        return []

    items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    articles = []

    for item in items[:8]:
        t = item.find("title") or item.find("{http://www.w3.org/2005/Atom}title")
        d = (item.find("description") or
             item.find("{http://www.w3.org/2005/Atom}summary") or
             item.find("{http://www.w3.org/2005/Atom}content"))

        title = (t.text or "").strip() if t is not None else ""
        desc  = re.sub(r"<[^>]+>", "", (d.text or "")).strip()[:280] if d is not None else ""

        pub_el = item.find("pubDate") or item.find("{http://www.w3.org/2005/Atom}published")
        pub_date = None
        if pub_el is not None and pub_el.text:
            try:
                pub_date = parsedate_to_datetime(pub_el.text)
                if pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
            except Exception:
                pass

        if title and (pub_date is None or pub_date >= cutoff):
            articles.append({"source": source["name"], "title": title, "description": desc})

    return articles


def fetch_all_news() -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    categories = {"Mercados y Bolsa": [], "Criptomonedas": [], "Colombia y LATAM": [], "Economia Global": [], "Instituciones": []}

    for source in RSS_SOURCES:
        print(f"  {source['name']}...")
        arts = fetch_rss(source, cutoff)
        categories[source["cat"]].extend(arts[:3])

    return categories


# ─── 2. Resumir con Gemini ────────────────────────────────────────────────────
def summarize_with_gemini(categories: dict) -> str:
    news_text = ""
    for cat, articles in categories.items():
        if not articles:
            continue
        news_text += f"\n\n=== {cat} ===\n"
        for a in articles:
            news_text += f"[{a['source']}] {a['title']}"
            if a["description"]:
                news_text += f": {a['description']}"
            news_text += "\n"

    prompt = f"""Eres un analista financiero senior de nivel mundial. Tienes los titulares economicos mas importantes del mundo de hoy, de Reuters, Bloomberg, Financial Times, Wall Street Journal, medios colombianos, latinoamericanos e instituciones como el FMI y el Banco Mundial.

Redacta un RESUMEN EJECUTIVO DIARIO en español con estas reglas:
- Para cada categoria escribe 3-5 oraciones conectando las noticias mas relevantes.
- Conecta los eventos entre si cuando tengan relacion (ej: si sube el dolar, como afecta a Colombia).
- Incluye datos concretos si aparecen en los titulares (porcentajes, precios, nombres de empresas).
- Tono profesional, claro y directo. Como si lo escribiera el Financial Times en español.
- En Colombia y LATAM menciona siempre la TRM, el peso colombiano o indices locales si hay info.

Noticias de hoy:
{news_text}

Formato EXACTO (usa estos titulos):
## Mercados y Bolsa
[resumen]

## Criptomonedas
[resumen]

## Colombia y LATAM
[resumen]

## Economia Global
[resumen]

## Instituciones
[resumen — solo si hay noticias del FMI o Banco Mundial, si no, omite]

## Conclusion del Dia
- [punto clave 1]
- [punto clave 2]
- [punto clave 3]"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.3}}
    resp = requests.post(url, json=payload, timeout=40)
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


# ─── 3. HTML del correo ───────────────────────────────────────────────────────
SECTION_STYLE = {
    "Mercados y Bolsa":    ("📈", "#0d3b6e", "#e8f0fb"),
    "Criptomonedas":       ("🪙", "#5a3200", "#fdf3e3"),
    "Colombia y LATAM":    ("🇨🇴", "#0a4d2a", "#e6f7ee"),
    "Economia Global":     ("🌎", "#1a2c6b", "#edf0fc"),
    "Instituciones":       ("🏛",  "#3d1060", "#f5eafd"),
    "Conclusion del Dia":  ("💡", "#7a4500", "#fff8e6"),
}

def build_email_html(summary: str) -> str:
    today     = datetime.now().strftime("%A, %d de %B de %Y")
    n_sources = len(RSS_SOURCES)
    lines     = summary.split("\n")
    html_body = ""
    cur_color = "#1a3c5e"

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            title = line[3:].strip()
            icon, color, bg = SECTION_STYLE.get(title, ("📌", "#333", "#f5f5f5"))
            cur_color = color
            html_body += f"""
<div style="margin-top:30px;margin-bottom:10px;padding:11px 18px;
            background:{bg};border-left:4px solid {color};border-radius:0 8px 8px 0">
  <h2 style="color:{color};font-size:15px;margin:0;font-weight:700">{icon}&nbsp; {title}</h2>
</div>"""
        elif line.startswith("- "):
            html_body += f"""
<div style="display:flex;gap:10px;margin:7px 0;padding:8px 14px;
            background:#f8fafc;border-radius:6px;border:1px solid #eaecef">
  <span style="color:{cur_color};font-weight:700;margin-top:1px">▸</span>
  <p style="margin:0;color:#2d3748;line-height:1.7;font-size:14px">{line[2:]}</p>
</div>"""
        else:
            html_body += f'<p style="margin:7px 0;color:#374151;line-height:1.8;font-size:14px">{line}</p>'

    source_names = " · ".join([s["name"] for s in RSS_SOURCES[:10]]) + " · y más"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:Georgia,serif;background:#dde4ee;margin:0;padding:28px 16px">
<div style="max-width:650px;margin:0 auto">

  <div style="background:#0a1f3d;border-radius:14px 14px 0 0;padding:34px 40px">
    <p style="color:#5b9bd5;font-size:11px;margin:0 0 8px;letter-spacing:2.5px;text-transform:uppercase">Resumen Economico Diario</p>
    <h1 style="color:#fff;font-size:26px;margin:0 0 10px;font-weight:400">{today}</h1>
    <div style="display:flex;gap:20px;flex-wrap:wrap">
      <span style="color:#7fb3d3;font-size:12px">📡 {n_sources} fuentes monitoreadas</span>
      <span style="color:#7fb3d3;font-size:12px">🌐 Reuters · Bloomberg · FT · WSJ · Portafolio · y más</span>
    </div>
  </div>

  <div style="background:#fff;padding:34px 40px;border-left:1px solid #c8d4e6;border-right:1px solid #c8d4e6">
    {html_body}
  </div>

  <div style="background:#f0f4fa;border-radius:0 0 14px 14px;padding:18px 40px;
              border:1px solid #c8d4e6;border-top:none">
    <p style="color:#7a8fa6;font-size:11px;margin:0 0 4px;text-align:center">{source_names}</p>
    <p style="color:#a0b0c0;font-size:10px;margin:0;text-align:center">
      Generado automaticamente · No constituye asesoria financiera
    </p>
  </div>

</div>
</body>
</html>"""


# ─── 4. Enviar correo ─────────────────────────────────────────────────────────
def send_email(html_content: str):
    today = datetime.now().strftime("%d/%m/%Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Resumen Economico Mundial — {today}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_content, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
    print(f"Correo enviado a {RECIPIENT_EMAIL}")


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Bot Economico — iniciando ===")
    print("Leyendo RSS de medios mundiales...")
    categories = fetch_all_news()
    total = sum(len(v) for v in categories.values())
    print(f"Total: {total} articulos recopilados")

    print("Resumiendo con Gemini...")
    summary = summarize_with_gemini(categories)

    print("Enviando correo...")
    html = build_email_html(summary)
    send_email(html)
    print("=== Listo ===")
