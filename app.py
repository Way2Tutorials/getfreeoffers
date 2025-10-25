# app.py — Share location via Email (Consent + Geolocation)
# ---------------------------------------------------------
# 1) pip install Flask
# 2) Edit CONFIG (SMTP + ALLOWED_ORIGINS)
# 3) python app.py → http://127.0.0.1:5000

from flask import Flask, render_template_string, request, jsonify, make_response
from urllib.parse import quote
import smtplib, ssl
from email.message import EmailMessage
from datetime import datetime

app = Flask(__name__)
app.secret_key = "education-location-secret"

# ================= CONFIG =================
# SMTP Server (choose one set)
SMTP_HOST = "smtp.gmail.com"     # e.g., Gmail: smtp.gmail.com, Outlook: smtp.office365.com
SMTP_PORT = 587                  # 587 for STARTTLS, 465 for SSL
SMTP_USERNAME = "cloudkeys1@gmail.com"
SMTP_PASSWORD = "xwtkukcruopujueo"  # Gmail App Password (with 2FA)
USE_SSL = False                  # True → SSL (465); False → STARTTLS (587)

FROM_EMAIL = "arinnovativetechnologies@gmail.com"     # sender (Gmail may require matching/alias)
TO_EMAIL   = "arinnovativetechnologies@zohomail.in"   # recipient

# ✅ Allow local + your Render domain (ADD YOUR REAL RENDER URL BELOW)
ALLOWED_ORIGINS = {
    "http://127.0.0.1:5000",
    "http://localhost:5000",
    "https://getfreeoffers.onrender.com/",      # <-- change to your real Render URL
}
APP_NAME = "Campus Connect"
# ==========================================

def is_origin_allowed(origin: str) -> bool:
    # Allow when no Origin (same-origin, some proxies) or when whitelisted
    return (not origin) or (origin in ALLOWED_ORIGINS)

@app.after_request
def add_security_and_cors_headers(resp):
    # Security headers
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(self)"

    # CORS (for allowed origins only)
    origin = request.headers.get("Origin", "")
    if is_origin_allowed(origin):
        resp.headers["Access-Control-Allow-Origin"] = origin or "*"
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return resp

INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ app_name }} — Share Location via Email</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root{--bg:#f4f7fb;--card:#fff;--ink:#14233b;--muted:#6c7a91;--accent:#2b6cb0;--ok:#1d8649;--err:#b42318;--radius:18px}
    *{box-sizing:border-box}
    body{
      margin:0;font-family:Inter,system-ui,Arial,sans-serif;
      background:linear-gradient(180deg,#eef5ff 0%,var(--bg) 100%);
      color:var(--ink);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;
    }
    .container{max-width:950px;width:100%;padding:0 12px}
    .card{background:var(--card);border-radius:var(--radius);box-shadow:0 14px 40px rgba(20,30,80,.08);overflow:hidden}
    .header{padding:18px 18px 8px}
    .muted{color:var(--muted)}
    .poster{position:relative;margin:0;cursor:pointer;outline:none}
    .poster img{display:block;width:100%;height:auto;transition:transform .35s ease}
    .poster:hover img,.poster:focus img{transform:scale(1.015)}
    .tag{position:absolute;left:16px;bottom:16px;background:rgba(255,255,255,.92);border-radius:12px;padding:8px 12px;font-weight:600;color:var(--accent);box-shadow:0 10px 24px rgba(0,0,0,.05)}
    .panel{padding:14px 18px 18px;border-top:1px solid #edf3ff}
    .status{min-height:24px;font-size:14px}.ok{color:var(--ok)} .err{color:var(--err)}
    .prepared{display:none}
    .hint{font-size:12px;color:var(--muted)}
  </style>
</head>
<body>
  <main class="container">
    <section class="card">
      <div class="header">
        <h1 style="margin:0 0 6px">{{ app_name }}</h1>
        <p class="muted" style="margin:0">
          Click the image to share your current location via <b>Email</b>.
          Email will be sent to: <code>{{ to_email }}</code>
        </p>
        <p class="hint" style="margin:6px 0 0">Your browser will ask for location permission.</p>
      </div>

      <figure class="poster" id="poster" tabindex="0" role="button" aria-label="Click to share your location">
        <img src="https://images.unsplash.com/photo-1524995997946-a1c2e315a42f?q=80&w=1800&auto=format&fit=crop" alt="Education Poster" draggable="false">
        <figcaption class="tag">Education • Tap to Share</figcaption>
      </figure>

      <div class="panel">
        <div id="status" class="status" aria-live="polite"></div>
        <pre id="prepared" class="prepared">No data yet.</pre>
      </div>
    </section>
  </main>

  <script>
    const poster   = document.getElementById("poster");
    const statusEl = document.getElementById("status");
    let isSending  = false;

    function setStatus(msg, cls){
      statusEl.textContent = msg || "";
      statusEl.className = "status " + (cls || "");
    }

    function getGeo(){
      return new Promise((resolve,reject)=>{
        if(!("geolocation" in navigator)) return reject(new Error("Geolocation not available in this browser."));
        navigator.geolocation.getCurrentPosition(
          pos => resolve(pos),
          err => reject(err),
          { enableHighAccuracy:true, timeout:15000, maximumAge:0 }
        );
      });
    }

    function mapLink(lat,lng){
      return "https://www.google.com/maps/search/?api=1&query="+encodeURIComponent(lat+","+lng);
    }

    async function handleClick(){
      if(isSending) return;
      isSending = true;
      setStatus("Requesting geolocation permission…");
      try{
        const pos = await getGeo();
        const latNum = pos?.coords?.latitude;
        const lngNum = pos?.coords?.longitude;
        const accNum = pos?.coords?.accuracy;

        if (typeof latNum !== "number" || typeof lngNum !== "number" || !isFinite(latNum) || !isFinite(lngNum)) {
          throw new Error("Location unavailable (no coordinates). Try again with GPS enabled.");
        }

        const lat = +latNum.toFixed(7);
        const lng = +lngNum.toFixed(7);
        const acc = (typeof accNum === "number" && isFinite(accNum)) ? (Math.round(accNum) + " m") : "unknown";
        const map = mapLink(lat,lng);

        setStatus("Sending email…");

        const res = await fetch("/send-email", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ consent:true, lat, lng, acc, map })
        });
        const data = await res.json();
        if(data.ok){
          setStatus("✅ Email sent successfully.", "ok");
        }else{
          setStatus("❌ Failed to send email: " + (data.error || "Unknown error"), "err");
        }
      }catch(e){
        if(e && e.code === e.PERMISSION_DENIED){
          setStatus("Location permission denied by the user.", "err");
        }else{
          setStatus("Error: " + (e.message || e), "err");
        }
      }finally{
        setTimeout(()=>{ isSending = false; }, 600);
      }
    }

    poster.addEventListener("click", handleClick);
    poster.addEventListener("keydown", (e)=>{
      if(e.key === "Enter" || e.key === " "){
        e.preventDefault();
        handleClick();
      }
    });
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML, to_email=TO_EMAIL, app_name=APP_NAME)

# CORS preflight (some hosts/browsers may send it)
@app.route("/send-email", methods=["OPTIONS"])
def preflight():
    resp = make_response(("", 204))
    return resp

@app.post("/send-email")
def send_email():
    origin = request.headers.get("Origin", "")
    if not is_origin_allowed(origin):
        return jsonify({"ok": False, "error": "Origin not allowed"}), 403

    data = request.get_json(silent=True) or {}
    if data.get("consent") is not True:
        return jsonify({"ok": False, "error": "Consent is required"}), 400

    try:
        lat = float(data.get("lat"))
        lng = float(data.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Missing or invalid coordinates"}), 400

    acc = data.get("acc") or "unknown"
    map_url = data.get("map") or f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"

    # Compose Email
    subject = f"{APP_NAME} — Location Share (with consent)"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = (
        f"{APP_NAME} — User Shared Location (with consent)\n"
        f"Time: {timestamp}\n"
        f"Latitude: {lat}\n"
        f"Longitude: {lng}\n"
        f"Accuracy: {acc}\n"
        f"Map: {map_url}\n"
    )

    msg = EmailMessage()
    msg["From"] = FROM_EMAIL or SMTP_USERNAME
    msg["To"] = TO_EMAIL
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        if USE_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=20) as server:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/health")
def health():
    def mask(s, keep=3): 
        return (s[:keep] + "…" + "*"*5) if s else "NOT SET"
    return jsonify({
        "smtp_host": SMTP_HOST,
        "smtp_port": SMTP_PORT,
        "use_ssl": USE_SSL,
        "username": mask(SMTP_USERNAME),
        "from_email": FROM_EMAIL or SMTP_USERNAME,
        "to_email": TO_EMAIL,
        "allowed_origins": list(ALLOWED_ORIGINS),
    })

if __name__ == "__main__":
    print("🚀 Server on http://127.0.0.1:5000 — Email mode")
    print("Allowed origins:", ALLOWED_ORIGINS)
    app.run(host="0.0.0.0", port=5000, debug=True)
