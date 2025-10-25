# app.py — Share location via Email (Consent + Geolocation) — Render-ready
# Uses SendGrid Web API (HTTPS) instead of SMTP (blocked on Render free)
# -----------------------------------------------------------------------
# pip install Flask requests
# python app.py  → http://127.0.0.1:5000   (HTTPS required in production)

import os
import ssl
from datetime import datetime
from email.message import EmailMessage  # kept for parity, not used
from urllib.parse import urlparse

import requests
from flask import Flask, render_template_string, request, jsonify, make_response

app = Flask(__name__)
app.secret_key = "education-location-secret"

# ================= BASIC APP CONFIG =================
APP_NAME = os.getenv("APP_NAME", "Campus Connect")
FROM_EMAIL = os.getenv("FROM_EMAIL", "info@arinnovativetechnologies.com")  # must be a verified sender in SendGrid
TO_EMAIL   = os.getenv("TO_EMAIL",   "arinnovativetechnologies@zohomail.in")

# Frontend → API base. If you host the HTML from this SAME Flask app, leave empty.
API_BASE = os.getenv("API_BASE", "")  # "" → same origin; else absolute base like "https://your-app.onrender.com"

# ================= SENDGRID (HTTPS) =================
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "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")  # REQUIRED
SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"

def send_via_sendgrid(to_email: str, subject: str, text: str):
    """
    Send a simple plain-text email using SendGrid Web API over HTTPS (port 443).
    Requires SENDGRID_API_KEY and a verified sender identity (FROM_EMAIL).
    """
    if not SENDGRID_API_KEY:
        raise RuntimeError("SENDGRID_API_KEY is not set")

    payload = {
        "personalizations": [{
            "to": [{"email": to_email}],
            "subject": subject
        }],
        "from": {"email": FROM_EMAIL},
        "content": [{
            "type": "text/plain",
            "value": text
        }]
    }
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    r = requests.post(SENDGRID_API_URL, json=payload, headers=headers, timeout=20)
    if r.status_code >= 400:
        # Bubble up SendGrid's error details for debugging
        raise RuntimeError(f"SendGrid error {r.status_code}: {r.text or r.reason}")

# ================= ORIGIN / CORS HELPERS =================
def _norm_origin(o: str) -> str:
    if not o:
        return ""
    o = o.strip().lower()
    if o.endswith("/"):
        o = o[:-1]
    return o

def _to_origin(o: str) -> str:
    o = _norm_origin(o)
    if not o:
        return ""
    parsed = urlparse(o)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    if "://" not in o:
        return f"https://{o}"
    return o

# Allowed origins for CORS
DEFAULT_ALLOWED = {
    _to_origin("http://127.0.0.1:5000"),
    _to_origin("http://localhost:5000"),
    _to_origin("https://getfreeoffers.onrender.com"),  # ← NOTE: no trailing slash
    # _to_origin("https://<your-username>.github.io"),  # add if hosting HTML on GitHub Pages
}
env_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
if env_origins:
    ALLOWED_ORIGINS = {_to_origin(o) for o in env_origins.split(",") if o.strip()}
else:
    ALLOWED_ORIGINS = DEFAULT_ALLOWED

ALLOW_NULL_ORIGIN = os.getenv("ALLOW_NULL_ORIGIN", "false").lower() == "true"

def is_origin_allowed(origin: str) -> bool:
    if not origin:
        return True
    o = _to_origin(origin)
    if ALLOW_NULL_ORIGIN and o == "null":
        return True
    return o in ALLOWED_ORIGINS

@app.after_request
def add_security_and_cors_headers(resp):
    # Security headers
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(self)"

    # CORS for allowed origins
    origin = request.headers.get("Origin", "")
    if is_origin_allowed(origin):
        resp.headers["Access-Control-Allow-Origin"] = origin or "*"
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return resp

# ================= UI (unchanged) =================
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
    body{margin:0;font-family:Inter,system-ui,Arial,sans-serif;background:linear-gradient(180deg,#eef5ff 0%,var(--bg) 100%);color:var(--ink);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;}
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
        <p class="hint" style="margin:6px 0 0">Your browser will ask for location permission. (Requires HTTPS)</p>
      </div>

      <figure class="poster" id="poster" tabindex="0" role="button" aria-label="Click to share your location">
        <img src="https://images.unsplash.com/photo-1524995997946-a1c2e315a42f?q=80&w=1800&auto=format&fit=crop" alt="Education Poster" draggable="false">
        <figcaption class="tag">Education • Tap to Share</figcaption>
      </figure>

      <div class="panel">
        <div id="status" class="status" aria-live="polite"></div>
      </div>
    </section>
  </main>

  <script>
    const statusEl = document.getElementById("status");
    const poster   = document.getElementById("poster");
    let isSending  = false;

    // API base comes from server; if empty we use same-origin
    const API_BASE = {{ api_base | tojson }};
    const SEND_URL = (API_BASE ? API_BASE : window.location.origin) + "/send-email";

    function setStatus(msg, cls){
      statusEl.textContent = msg || "";
      statusEl.className = "status " + (cls || "");
      console.log("[status]", msg);
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

    function mapLink(lat,lng){ return "https://www.google.com/maps/search/?api=1&query="+encodeURIComponent(lat+","+lng); }

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
          throw new Error("Location unavailable (no coordinates). Try again with GPS enabled and HTTPS.");
        }

        const lat = +latNum.toFixed(7);
        const lng = +lngNum.toFixed(7);
        const acc = (typeof accNum === "number" && isFinite(accNum)) ? (Math.round(accNum) + " m") : "unknown";
        const map = mapLink(lat,lng);

        setStatus("Sending email…");

        const res = await fetch(SEND_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ consent:true, lat, lng, acc, map })
        });

        let data = {};
        try { data = await res.json(); } catch (e) { /* ignore */ }

        if(res.ok && data.ok){
          setStatus("✅ Email sent successfully.", "ok");
        }else{
          setStatus("❌ Failed to send email: " + (data.error || res.statusText), "err");
          console.error("Server reply:", res.status, data);
        }
      }catch(e){
        if(e && e.code === e.PERMISSION_DENIED){ setStatus("Location permission denied by the user.", "err"); }
        else{ setStatus("Error: " + (e.message || e), "err"); }
        console.error(e);
      }finally{
        setTimeout(()=>{ isSending = false; }, 600);
      }
    }

    poster.addEventListener("click", handleClick);
    poster.addEventListener("keydown", (e)=>{ if(e.key==="Enter"||e.key===" "){ e.preventDefault(); handleClick(); }});
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML, to_email=TO_EMAIL, app_name=APP_NAME, api_base=API_BASE)

# Preflight (CORS)
@app.route("/send-email", methods=["OPTIONS"])
def preflight():
    return make_response(("", 204))

@app.post("/send-email")
def send_email():
    origin = request.headers.get("Origin", "")
    print(f"[send-email] Origin: {origin!r}  | Allowed: {sorted(ALLOWED_ORIGINS)}  | NullAllowed={ALLOW_NULL_ORIGIN}")
    if not is_origin_allowed(origin):
        return jsonify({"ok": False, "error": f"Origin not allowed: {origin or '(none)'}"}), 403

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

    # ---- Send via SendGrid HTTPS API ----
    try:
        send_via_sendgrid(TO_EMAIL, subject, body)
        print("[send-email] Email sent to", TO_EMAIL)
        return jsonify({"ok": True})
    except Exception as e:
        print("[send-email] SendGrid error:", e)
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/health")
def health():
    def mask(s, keep=3):
        return (s[:keep] + "…" + "*"*5) if s else "NOT SET"
    return jsonify({
        "from_email": FROM_EMAIL,
        "to_email": TO_EMAIL,
        "api_base": API_BASE or "(same-origin)",
        "allowed_origins": sorted(list(ALLOWED_ORIGINS)),
        "allow_null_origin": ALLOW_NULL_ORIGIN,
        "sendgrid_key": "SET" if bool(SENDGRID_API_KEY) else "NOT SET",
    })

if __name__ == "__main__":
    print("🚀 Serving on http://0.0.0.0:5000  (use HTTPS in production)")
    print("Allowed origins:", sorted(ALLOWED_ORIGINS))
    print("ALLOW_NULL_ORIGIN:", ALLOW_NULL_ORIGIN)
    app.run(host="0.0.0.0", port=5000, debug=True)
