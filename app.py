from flask import Flask, request, redirect, url_for, session, render_template_string, jsonify, flash
import sqlite3, os, math, hmac, hashlib, json, base64, re, difflib, urllib.parse, urllib.request, io, struct, zlib
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash

APP_NAME = "BloodBridge"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bloodbridge.db")
SECRET_KEY = os.environ.get("BLOODBRIDGE_SECRET", "bloodbridge-demo-secret-change-me")
SIGNING_SECRET = os.environ.get("BLOODBRIDGE_SIGNING_SECRET", "bloodbridge-signing-secret-change-me")

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

BLOOD_GROUPS = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]
URGENCIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
ROLES = ["emergency", "bloodbank", "donor", "admin"]

# Phase-1 GIS: users enter a normal place name. The backend resolves it internally.
# No latitude/longitude is requested from the user.
PLACES = {
    "chennai": (13.0827, 80.2707),
    "chennai central": (13.0827, 80.2707),
    "park town": (13.0820, 80.2760),
    "egmore": (13.0732, 80.2609),
    "adyar": (13.0068, 80.2565),
    "t nagar": (13.0418, 80.2341),
    "velachery": (12.9815, 80.2180),
    "guindy": (13.0067, 80.2206),
    "manapakkam": (13.0226, 80.1750),
    "anna nagar": (13.0878, 80.2086),
    "tambaram": (12.9249, 80.1000),
    "porur": (13.0358, 80.1560),
    "mylapore": (13.0339, 80.2676),
    "nungambakkam": (13.0569, 80.2425),
    "royapettah": (13.0528, 80.2630),
    "airport": (12.9941, 80.1709), "chennai airport": (12.9941, 80.1709),
    "chromepet": (12.9516, 80.1462), "saidapet": (13.0213, 80.2231),
    "ashok nagar": (13.0350, 80.2120), "koyambedu": (13.0694, 80.1948),
    "madhuravoyal": (13.0524, 80.1620), "thiruvanmiyur": (12.9830, 80.2594),
}

COMPATIBILITY = {
    "O-": ["O-"],
    "O+": ["O+", "O-"],
    "A-": ["A-", "O-"],
    "A+": ["A+", "A-", "O+", "O-"],
    "B-": ["B-", "O-"],
    "B+": ["B+", "B-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": BLOOD_GROUPS,
}

BASE_CSS = r"""
:root{
 --bg:#f7f7f9;--panel:#ffffff;--ink:#15151a;--muted:#74747d;--line:#e8e8ee;
 --accent:#c51f45;--accent2:#8d1232;--accent-soft:#fff0f4;--green:#11845f;
 --green-soft:#e9f8f2;--amber:#a9690b;--amber-soft:#fff5df;--red:#c9344e;
 --nav:#17171c;--nav2:#222229;--shadow:0 18px 50px rgba(19,18,25,.08);
 --shadow2:0 28px 80px rgba(19,18,25,.14)
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Arial,sans-serif;background:
 radial-gradient(circle at 8% 0%,rgba(197,31,69,.08),transparent 26%),
 radial-gradient(circle at 92% 12%,rgba(90,76,180,.07),transparent 24%),var(--bg);color:var(--ink)}
a{text-decoration:none;color:inherit}
.shell{min-height:100vh}
.top{height:76px;background:rgba(255,255,255,.82);backdrop-filter:blur(20px);border-bottom:1px solid rgba(232,232,238,.9);
 display:flex;align-items:center;justify-content:space-between;padding:0 30px;position:sticky;top:0;z-index:50}
.brand{font-size:24px;font-weight:950;letter-spacing:-1.2px;color:var(--ink);display:flex;align-items:center;gap:10px}
.brand:before{content:"+";display:grid;place-items:center;width:38px;height:38px;border-radius:13px;
 background:linear-gradient(145deg,#d52a52,#9c1434);color:#fff;font-size:25px;font-weight:950;box-shadow:0 10px 25px rgba(197,31,69,.25)}
.brand span{color:var(--accent)}
.top-right{display:flex;align-items:center;gap:10px}
.role{font-size:10px;background:var(--accent-soft);color:var(--accent);padding:8px 11px;border-radius:999px;font-weight:900;letter-spacing:1px}
.logout{border:1px solid var(--line);padding:9px 14px;border-radius:12px;color:var(--ink);background:#fff;font-weight:800}
.logout:hover{border-color:#d3d3dc;background:#fafafd}
.layout{display:flex;min-height:calc(100vh - 76px)}
.side{width:255px;background:linear-gradient(180deg,var(--nav),#111116);color:#eee;padding:20px 14px;
 box-shadow:12px 0 35px rgba(15,14,20,.08);position:sticky;top:76px;height:calc(100vh - 76px);overflow:auto}
.side .section{font-size:10px;text-transform:uppercase;letter-spacing:1.8px;color:#8e8e98;padding:16px 12px 9px}
.nav{display:flex;align-items:center;gap:11px;padding:12px 13px;border-radius:13px;margin:5px 0;color:#cfcfd6;font-size:13px;font-weight:750;transition:.18s}
.nav:before{content:"";width:7px;height:7px;border-radius:50%;background:#575761}
.nav:hover,.nav.active{background:linear-gradient(90deg,#3a1d27,#292027);color:#fff;transform:translateX(2px)}
.nav:hover:before,.nav.active:before{background:#ff5c7e;box-shadow:0 0 0 4px rgba(255,92,126,.12)}
.main{flex:1;padding:34px;max-width:1600px;width:100%}
.title{font-size:32px;letter-spacing:-1.2px;margin:0 0 7px;font-weight:950}
.subtitle{color:var(--muted);margin:0 0 24px;line-height:1.6}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:17px}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.card{background:rgba(255,255,255,.94);border:1px solid rgba(232,232,238,.96);border-radius:22px;padding:22px;
 box-shadow:var(--shadow);transition:transform .18s,box-shadow .18s}
.card:hover{transform:translateY(-2px);box-shadow:var(--shadow2)}
.section-head{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:14px}
.best-row{background:#f1fbf7}
.metric{font-size:29px;font-weight:950;margin-top:9px;letter-spacing:-.8px}
.label{color:var(--muted);font-size:11px;font-weight:850;text-transform:uppercase;letter-spacing:.7px}
.small{font-size:12px;color:var(--muted)}
.btn{border:0;border-radius:13px;padding:12px 18px;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;
 font-weight:900;cursor:pointer;display:inline-block;transition:.18s;box-shadow:0 9px 20px rgba(197,31,69,.2)}
.btn:hover{transform:translateY(-1px);filter:brightness(.98)}
.btn.secondary{background:#f5f5f8;color:var(--accent);box-shadow:none;border:1px solid var(--line)}
.btn.success{background:linear-gradient(135deg,#15966d,#0d684d)}
.btn.danger{background:linear-gradient(135deg,#cf3b55,#a91f3b)}
.btn.dark{background:#1c1c22}
.btn + .btn{margin-left:7px}
.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.field{display:flex;flex-direction:column;gap:7px}
.field label{font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.65px}
.field input,.field select,.field textarea{width:100%;padding:13px 14px;border:1px solid var(--line);border-radius:13px;background:#fff;color:var(--ink);
 outline:none;font:inherit;transition:.16s}
.field input:focus,.field select:focus,.field textarea:focus{border-color:#d95b78;box-shadow:0 0 0 4px rgba(197,31,69,.09)}
.table-wrap{overflow:auto}.table{width:100%;border-collapse:separate;border-spacing:0}
.table th,.table td{padding:13px 11px;border-bottom:1px solid var(--line);text-align:left;font-size:13px}
.table th{font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);background:#fafafd}
.table tr:last-child td{border-bottom:0}
.badge{display:inline-block;padding:5px 9px;border-radius:999px;font-size:10px;font-weight:900;letter-spacing:.3px}
.badge.green{background:var(--green-soft);color:var(--green)}.badge.red{background:#ffedf0;color:var(--red)}.badge.amber{background:var(--amber-soft);color:var(--amber)}
.flash{background:#fff0f4;color:#8d2138;border:1px solid #f0cbd4;padding:13px 15px;border-radius:13px;margin-bottom:18px;font-weight:750;box-shadow:0 8px 20px rgba(197,31,69,.06)}
.hero{position:relative;overflow:hidden;background:radial-gradient(circle at 90% 10%,rgba(255,255,255,.18),transparent 25%),
 linear-gradient(135deg,#17171c,#3b1724 55%,#a31d43);color:#fff;border-radius:26px;padding:30px;box-shadow:0 22px 55px rgba(53,25,32,.19)}
.hero:after{content:"";position:absolute;width:190px;height:190px;border:1px solid rgba(255,255,255,.12);border-radius:50%;right:-55px;bottom:-90px}
.hero p{color:#eadde0}.hero .btn{background:#fff;color:#8e203a;box-shadow:none}.hero .btn.secondary{background:rgba(255,255,255,.1);color:#fff;border:1px solid rgba(255,255,255,.2)}
.actions{display:flex;gap:9px;flex-wrap:wrap;margin-top:18px}
.map{height:570px;border-radius:20px;overflow:hidden;border:1px solid var(--line);background:#e8e8ec;position:relative}
.map-status{position:absolute;z-index:1000;left:14px;top:14px;background:rgba(255,255,255,.96);padding:9px 12px;border-radius:11px;font-size:11px;font-weight:850;box-shadow:0 8px 22px rgba(0,0,0,.1)}
.timeline{display:grid;gap:10px}.timeline-item{padding:11px 13px;border-radius:12px;background:#fafafd;border:1px solid var(--line);font-size:13px;font-weight:700}
.timeline-item:before{content:"✓";color:var(--green);font-weight:900;margin-right:8px}
.gps-live{background:var(--green-soft)!important;color:var(--green)!important;border-color:#bfe9d9!important}
.notify-live{background:#fff8df!important;color:#8a5b08!important;border-color:#f1dfab!important}
.toast-wrap{position:fixed;right:18px;bottom:18px;z-index:9999;display:grid;gap:10px;max-width:min(380px,calc(100vw - 36px))}
.toast{background:#17171c;color:#fff;border-radius:15px;padding:13px 15px;box-shadow:0 16px 45px rgba(0,0,0,.2);font-size:13px;border-left:4px solid var(--accent)}
.map-fallback{position:absolute;inset:0;display:none;background:linear-gradient(rgba(255,255,255,.75) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.75) 1px,transparent 1px),radial-gradient(circle at 50% 45%,#eef5ee,#dce6df);background-size:46px 46px,46px 46px,100% 100%;overflow:hidden}
.map-fallback .road{position:absolute;height:3px;background:rgba(255,255,255,.9);transform-origin:left center}
.map-fallback .dot{position:absolute;transform:translate(-50%,-50%);width:18px;height:18px;border-radius:50%;background:#c51f45;border:3px solid #fff;box-shadow:0 4px 12px rgba(0,0,0,.22);z-index:3}
.map-fallback .dot.resource{background:#11845f}.map-fallback .dot.gps{background:#2267d8;width:20px;height:20px}
.map-fallback .label{position:absolute;transform:translate(10px,-8px);background:rgba(255,255,255,.94);padding:5px 8px;border-radius:8px;white-space:nowrap;box-shadow:0 4px 12px rgba(0,0,0,.1);font-size:10px;z-index:4;text-transform:none;letter-spacing:0;font-weight:800;color:#15151a}

/* New modern authentication UI */
.login-page{min-height:100vh;display:grid;place-items:center;padding:28px;
 background:
 radial-gradient(circle at 10% 10%,rgba(197,31,69,.14),transparent 28%),
 radial-gradient(circle at 92% 85%,rgba(93,75,180,.12),transparent 30%),
 linear-gradient(135deg,#f9f9fb,#f2f1f5)}
.auth-shell{width:min(1120px,96vw);min-height:680px;display:grid;grid-template-columns:1.02fr .98fr;background:rgba(255,255,255,.9);
 border:1px solid rgba(255,255,255,.8);border-radius:34px;overflow:hidden;box-shadow:0 35px 100px rgba(26,23,31,.16);backdrop-filter:blur(18px)}
.auth-visual{position:relative;padding:54px;color:#fff;overflow:hidden;background:
 radial-gradient(circle at 82% 12%,rgba(255,255,255,.22),transparent 24%),
 radial-gradient(circle at 18% 88%,rgba(255,255,255,.13),transparent 26%),
 linear-gradient(145deg,#17171d 0%,#351622 48%,#b31f46 100%)}
.auth-visual:before{content:"";position:absolute;width:420px;height:420px;border:1px solid rgba(255,255,255,.1);border-radius:50%;right:-190px;top:-170px}
.auth-visual:after{content:"";position:absolute;width:260px;height:260px;border:1px solid rgba(255,255,255,.09);border-radius:50%;left:-150px;bottom:-120px}
.auth-logo{display:flex;align-items:center;gap:12px;font-size:29px;font-weight:950;letter-spacing:-1.4px;position:relative;z-index:2}
.auth-logo .cross{width:43px;height:43px;border-radius:14px;background:#fff;color:var(--accent);display:grid;place-items:center;font-size:27px;font-weight:950}
.auth-visual h1{font-size:46px;line-height:1.03;letter-spacing:-2.2px;max-width:470px;margin:78px 0 18px;position:relative;z-index:2}
.auth-visual h1 span{color:#ffb7c7}
.auth-visual p{max-width:470px;color:#eadde2;line-height:1.7;font-size:15px;position:relative;z-index:2}
.auth-pills{display:flex;gap:9px;flex-wrap:wrap;margin-top:30px;position:relative;z-index:2}
.auth-pill{padding:9px 12px;border-radius:999px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.14);font-size:11px;font-weight:800}
.auth-steps{display:grid;gap:12px;margin-top:42px;position:relative;z-index:2}
.auth-step{display:flex;align-items:center;gap:12px;font-size:12px;color:#f5e9ed}
.auth-step i{width:29px;height:29px;border-radius:10px;background:rgba(255,255,255,.12);display:grid;place-items:center;font-style:normal;font-weight:900}
.auth-panel{padding:54px;display:flex;align-items:center}
.auth-card{width:100%;max-width:470px;margin:auto}
.auth-card .brand{display:none}
.auth-eyebrow{font-size:11px;font-weight:900;letter-spacing:1.5px;text-transform:uppercase;color:var(--accent);margin-bottom:12px}
.auth-card h2{font-size:36px;line-height:1.05;letter-spacing:-1.5px;margin:0 0 10px}
.auth-card .subtitle{font-size:14px;margin-bottom:28px}
.auth-card .field input,.auth-card .field select{height:51px;background:#fbfbfd}
.auth-submit{width:100%;height:52px;margin-top:4px;font-size:14px}
.auth-links{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-top:18px;font-size:13px}
.auth-links a{color:var(--accent);font-weight:900}
.demo-box{margin-top:24px;padding:14px 15px;border:1px dashed #d9d9e1;border-radius:14px;background:#fafafd;font-size:11px;color:var(--muted);line-height:1.6}
.role-note{font-size:11px;color:var(--muted);margin-top:5px}
/* FORCE PHONE/TABLET AUTH LAYOUT — also works when Android Chrome uses Desktop Site */
@media(max-width:1200px){
  .login-page{min-height:100svh;padding:0;place-items:stretch;background:linear-gradient(145deg,#fff7f8 0%,#f8f9fc 52%,#f1f3fa 100%)}
  .auth-shell{width:100%;min-height:100svh;display:block;border-radius:0;background:rgba(255,255,255,.97);box-shadow:none}
  .auth-visual{display:none}
  .auth-panel{min-height:100svh;padding:34px 24px 42px;display:flex;align-items:flex-start;justify-content:center}
  .auth-card{width:100%;max-width:680px;margin:0 auto}
  .auth-card h2{font-size:34px;line-height:1.05;margin-bottom:10px}
  .auth-card .subtitle{font-size:14px;line-height:1.55;margin-bottom:24px}
  .auth-card form{width:100%}
  .auth-card .form-grid{display:grid;grid-template-columns:1fr;gap:16px}
  .auth-card .field{margin:0}
  .auth-card .field label{font-size:11px;letter-spacing:.08em;margin-bottom:7px}
  .auth-card .field input,.auth-card .field select{width:100%;height:58px;font-size:16px;border-radius:15px;padding:0 16px;box-sizing:border-box}
  .auth-card .auth-submit,.auth-card .btn{width:100%;min-height:58px;font-size:15px;border-radius:15px;margin-top:8px}
  .auth-links{margin-top:18px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
  .demo-box{margin-top:20px;font-size:12px;line-height:1.55}
}

@media(max-width:1000px){.side{width:215px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.auth-shell{grid-template-columns:1fr}.auth-visual{display:none}.auth-panel{padding:38px}}
@media(max-width:900px){
  .login-page{min-height:100svh;padding:0;background:linear-gradient(145deg,#fff7f8 0%,#f8f9fc 52%,#f1f3fa 100%);place-items:stretch}
  .auth-shell{width:100%;min-height:100svh;display:block;border-radius:0;background:rgba(255,255,255,.96);box-shadow:none}
  .auth-panel{min-height:100svh;padding:32px 22px 36px;display:flex;align-items:flex-start;justify-content:center}
  .auth-card{width:100%;max-width:620px;margin:0 auto}
  .auth-card h2{font-size:34px;line-height:1.05;margin-bottom:10px}
  .auth-card .subtitle{font-size:14px;line-height:1.55;margin-bottom:24px}
  .auth-card form{width:100%}
  .auth-card .form-grid{display:grid;grid-template-columns:1fr;gap:16px}
  .auth-card .field{margin:0}
  .auth-card .field label{font-size:11px;letter-spacing:.08em;margin-bottom:7px}
  .auth-card .field input,.auth-card .field select{width:100%;height:56px;font-size:16px;border-radius:14px;padding:0 16px;box-sizing:border-box}
  .auth-card .auth-submit,.auth-card .btn{width:100%;min-height:56px;font-size:15px;border-radius:15px;margin-top:6px}
  .auth-links{margin-top:18px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
  .demo-box{margin-top:20px;font-size:12px;line-height:1.55}
}
@media(max-width:600px){
  .top{padding:0 16px}.top-right .small{display:none}.layout{display:block}.side{width:100%;height:auto;position:static;padding:8px;display:flex;overflow:auto}.side .section{display:none}.nav{white-space:nowrap}.main{padding:16px}.grid,.grid2,.form-grid{grid-template-columns:1fr}.map{height:430px}
  .login-page{padding:0}
  .auth-panel{padding:26px 18px 32px}
  .auth-card h2{font-size:31px}
  .auth-card .subtitle{margin-bottom:22px}
  .auth-card .field input,.auth-card .field select{height:54px}
  .auth-links{font-size:13px}
}

"""


BASE_HTML = """
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no'><title>{{ title }} · BloodBridge</title><link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css' crossorigin='anonymous'><link rel='manifest' href='{{ url_for("manifest") }}'><meta name='theme-color' content='#c51f45'><meta name='apple-mobile-web-app-capable' content='yes'><style>""" + BASE_CSS + """</style></head><body>
<div class='shell'><div class='top'><a class='brand' href='{{ url_for("dashboard") }}'>Blood<span>Bridge</span></a><div class='top-right'><button id='gpsBtn' class='logout' type='button'>📍 GPS</button><button id='notifyBtn' class='logout' type='button'>🔔 <span id='notifCount'>0</span></button><button id='installBtn' class='logout' type='button' style='display:none'>📱 Install</button><span class='role'>{{ session.get('role','')|upper }}</span><span class='small'>{{ session.get('name','') }}</span><a class='logout' href='{{ url_for("logout") }}'>Logout</a></div></div>
<div class='layout'><aside class='side'><div class='section'>Workspace</div><a class='nav' href='{{ url_for("dashboard") }}'>Dashboard</a>
{% if session.get('role')=='emergency' %}<a class='nav' href='{{ url_for("new_request") }}'>New Emergency</a><a class='nav' href='{{ url_for("gis") }}'>GIS Resource Map</a><a class='nav' href='{{ url_for("simulation") }}'>Digital Twin</a>{% endif %}
{% if session.get('role')=='bloodbank' %}<a class='nav' href='{{ url_for("inventory") }}'>Inventory</a><a class='nav' href='{{ url_for("bank_requests") }}'>Emergency Requests</a>{% endif %}
{% if session.get('role')=='donor' %}<a class='nav' href='{{ url_for("donor_profile") }}'>My Profile</a><a class='nav' href='{{ url_for("donor_requests") }}'>Emergency Requests</a>{% endif %}
{% if session.get('role')=='admin' %}<a class='nav' href='{{ url_for("admin_users") }}'>Users</a><a class='nav' href='{{ url_for("admin_audit") }}'>Audit Logs</a>{% endif %}<div class='section'>System</div><a class='nav' href='{{ url_for("health") }}'>System Status</a></aside><main class='main'>{% with messages=get_flashed_messages() %}{% for m in messages %}<div class='flash'>{{m}}</div>{% endfor %}{% endwith %}{{ content|safe }}</main></div></div><div id='toastWrap' class='toast-wrap'></div>
<script src='https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js' crossorigin='anonymous'></script>{{ scripts|safe }}<script>
(function(){
 var gpsWatch=null;
 function toast(t,m){var w=document.getElementById('toastWrap');if(!w)return;var x=document.createElement('div');x.className='toast';x.innerHTML='<b>'+String(t).replace(/</g,'&lt;')+'</b><div style="margin-top:4px;opacity:.86">'+String(m).replace(/</g,'&lt;')+'</div>';w.appendChild(x);setTimeout(function(){x.remove()},6500)}
 function gpsButton(on){var b=document.getElementById('gpsBtn');if(b){b.textContent=on?'📍 GPS LIVE':'📍 GPS';b.classList.toggle('gps-live',on)}}
 function sendGPS(p){var d=p.coords;fetch('{{ url_for("api_location") }}',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({latitude:d.latitude,longitude:d.longitude,accuracy:d.accuracy})}).then(function(r){if(!r.ok)throw 0;gpsButton(true);window.dispatchEvent(new CustomEvent('bloodbridge:gps',{detail:{lat:d.latitude,lng:d.longitude,accuracy:d.accuracy}}))}).catch(function(){})}
 function startGPS(){if(!navigator.geolocation){toast('GPS unavailable','This browser does not provide location services.');return}if(gpsWatch!==null){navigator.geolocation.clearWatch(gpsWatch);gpsWatch=null;gpsButton(false);return}if(!window.isSecureContext&&location.hostname!=='localhost'&&location.hostname!=='127.0.0.1'){toast('GPS needs HTTPS on phone','Open the HTTPS address printed by BloodBridge. Plain HTTP on a phone cannot grant browser GPS permission.');return}navigator.geolocation.getCurrentPosition(function(p){sendGPS(p);gpsWatch=navigator.geolocation.watchPosition(sendGPS,function(){toast('GPS permission','Allow Location for BloodBridge, then press GPS again.')},{enableHighAccuracy:true,timeout:15000,maximumAge:3000})},function(e){toast('GPS not started',e.code===1?'Allow Location permission for BloodBridge.':e.code===2?'Phone location is unavailable.':'GPS timed out.')},{enableHighAccuracy:true,timeout:15000,maximumAge:0})}
 var gb=document.getElementById('gpsBtn');if(gb)gb.onclick=startGPS;
 var nb=document.getElementById('notifyBtn');if(nb)nb.onclick=function(){if('Notification'in window&&Notification.permission==='granted'){fetch('{{ url_for("api_notifications_read") }}',{method:'POST'}).then(function(){var c=document.getElementById('notifCount');if(c)c.textContent='0';toast('Notifications','Unread alerts marked as read')});return}if(!('Notification'in window)){toast('Notifications','In-app notifications still work.');return}Notification.requestPermission().then(function(p){if(p==='granted'){nb.classList.add('notify-live');toast('Notifications enabled','BloodBridge alerts are on')}else toast('Notifications blocked','Allow notifications in browser settings');poll()})};
 var install=document.getElementById('installBtn'),deferred=null;window.addEventListener('beforeinstallprompt',function(e){e.preventDefault();deferred=e;if(install)install.style.display='inline-block'});if(install)install.onclick=function(){if(deferred){deferred.prompt();deferred.userChoice.finally(function(){deferred=null;install.style.display='none'})}};
 var last=Number(sessionStorage.getItem('bbLastNotification')||0);function poll(){fetch('{{ url_for("api_notifications") }}').then(function(r){return r.json()}).then(function(d){var c=document.getElementById('notifCount');if(c)c.textContent=d.unread||0;var a=d.items||[];if(!last&&a.length){last=Math.max.apply(null,a.map(function(n){return Number(n.id)||0}));sessionStorage.setItem('bbLastNotification',last);return}a.slice().reverse().forEach(function(n){if(Number(n.id)>last){last=Number(n.id);sessionStorage.setItem('bbLastNotification',last);toast(n.title,n.message);if('Notification'in window&&Notification.permission==='granted'){try{new Notification(n.title,{body:n.message,icon:'{{ url_for("icon192") }}'})}catch(e){}}}})}).catch(function(){})};poll();setInterval(poll,4000);
 if('serviceWorker'in navigator)navigator.serviceWorker.register('{{ url_for("service_worker") }}').catch(function(){});
})();
</script></body></html>
"""

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def migrate_schema(conn):
    """Upgrade older BloodBridge demo databases in-place without deleting user data."""
    required = {
        "users": {"password_hash": "TEXT", "name": "TEXT", "role": "TEXT", "location": "TEXT", "blood_group": "TEXT", "verified": "INTEGER DEFAULT 0", "available": "INTEGER DEFAULT 1", "created_at": "TEXT"},
        "blood_banks": {"location": "TEXT", "latitude": "REAL DEFAULT 13.0827", "longitude": "REAL DEFAULT 80.2707", "verified": "INTEGER DEFAULT 1"},
        "inventory": {"bank_id": "INTEGER", "blood_group": "TEXT", "units": "INTEGER DEFAULT 0", "updated_at": "TEXT"},
        "requests": {"user_id": "INTEGER", "hospital": "TEXT", "blood_group": "TEXT", "units_required": "INTEGER DEFAULT 1", "urgency": "TEXT DEFAULT 'HIGH'", "location": "TEXT", "latitude": "REAL DEFAULT 13.0827", "longitude": "REAL DEFAULT 80.2707", "status": "TEXT DEFAULT 'OPEN'", "signature": "TEXT", "created_at": "TEXT"},
        "allocations": {"request_id": "INTEGER", "bank_id": "INTEGER", "donor_id": "INTEGER", "blood_group": "TEXT", "units": "INTEGER DEFAULT 0", "distance_km": "REAL DEFAULT 0", "confidence": "REAL DEFAULT 0", "priority_score": "REAL DEFAULT 0", "status": "TEXT DEFAULT 'PROPOSED'", "created_at": "TEXT"},
        "audit_logs": {"actor": "TEXT", "action": "TEXT", "details": "TEXT", "created_at": "TEXT"},
        "users": {"latitude": "REAL", "longitude": "REAL", "gps_accuracy": "REAL", "gps_updated_at": "TEXT"},
    }
    for table, cols in required.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for col, spec in cols.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {spec}")
    # Older versions sometimes called the password column simply `password`.
    user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "password" in user_cols:
        conn.execute("UPDATE users SET password_hash=password WHERE (password_hash IS NULL OR password_hash='')")
    # Fill safe values for columns that older rows did not have.
    now = now_iso()
    conn.execute("UPDATE users SET created_at=? WHERE created_at IS NULL OR created_at=''", (now,))
    conn.execute("UPDATE users SET verified=0 WHERE verified IS NULL")
    conn.execute("UPDATE users SET available=1 WHERE available IS NULL")
    conn.execute("UPDATE users SET location='Chennai' WHERE location IS NULL OR location='' ")
    conn.execute("UPDATE users SET role='emergency' WHERE role IS NULL OR role='' ")
    conn.execute("UPDATE users SET name=username WHERE name IS NULL OR name='' ")
    conn.execute("UPDATE blood_banks SET verified=1 WHERE verified IS NULL")
    conn.execute("UPDATE inventory SET units=0 WHERE units IS NULL")
    conn.execute("UPDATE inventory SET updated_at=? WHERE updated_at IS NULL OR updated_at=''", (now,))
    conn.execute("UPDATE requests SET status='OPEN' WHERE status IS NULL OR status=''")
    conn.execute("UPDATE requests SET urgency='HIGH' WHERE urgency IS NULL OR urgency=''")
    conn.execute("UPDATE requests SET units_required=1 WHERE units_required IS NULL OR units_required<1")
    conn.execute("UPDATE allocations SET status='PROPOSED' WHERE status IS NULL OR status=''")
    conn.execute("UPDATE audit_logs SET created_at=? WHERE created_at IS NULL OR created_at=''", (now,))

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      name TEXT NOT NULL,
      role TEXT NOT NULL,
      location TEXT,
      blood_group TEXT,
      verified INTEGER NOT NULL DEFAULT 0,
      available INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS blood_banks(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      location TEXT NOT NULL,
      latitude REAL NOT NULL,
      longitude REAL NOT NULL,
      verified INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS inventory(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      bank_id INTEGER NOT NULL,
      blood_group TEXT NOT NULL,
      units INTEGER NOT NULL DEFAULT 0,
      updated_at TEXT NOT NULL,
      UNIQUE(bank_id,blood_group),
      FOREIGN KEY(bank_id) REFERENCES blood_banks(id)
    );
    CREATE TABLE IF NOT EXISTS requests(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      hospital TEXT NOT NULL,
      blood_group TEXT NOT NULL,
      units_required INTEGER NOT NULL,
      urgency TEXT NOT NULL,
      location TEXT NOT NULL,
      latitude REAL NOT NULL,
      longitude REAL NOT NULL,
      status TEXT NOT NULL DEFAULT 'OPEN',
      signature TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS allocations(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      request_id INTEGER NOT NULL,
      bank_id INTEGER,
      donor_id INTEGER,
      blood_group TEXT NOT NULL,
      units INTEGER NOT NULL,
      distance_km REAL NOT NULL,
      confidence REAL NOT NULL,
      priority_score REAL NOT NULL,
      status TEXT NOT NULL DEFAULT 'PROPOSED',
      created_at TEXT NOT NULL,
      FOREIGN KEY(request_id) REFERENCES requests(id),
      FOREIGN KEY(bank_id) REFERENCES blood_banks(id),
      FOREIGN KEY(donor_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS audit_logs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      actor TEXT NOT NULL,
      action TEXT NOT NULL,
      details TEXT,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS notifications(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      message TEXT NOT NULL,
      kind TEXT DEFAULT 'info',
      read INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL
    );
    """)
    migrate_schema(conn)
    # Seed banks and inventory only once.
    if conn.execute("SELECT COUNT(*) FROM blood_banks").fetchone()[0] == 0:
        banks=[
          ("Apollo Blood Centre","Chennai Central",13.0827,80.2707,1),
          ("Government General Blood Bank","Park Town",13.0820,80.2760,1),
          ("MIOT Blood Bank","Manapakkam",13.0226,80.1750,1),
          ("Fortis Blood Bank","Adyar",13.0068,80.2565,1),
        ]
        conn.executemany("INSERT INTO blood_banks(name,location,latitude,longitude,verified) VALUES(?,?,?,?,?)",banks)
    if conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0:
        ids=[r[0] for r in conn.execute("SELECT id FROM blood_banks ORDER BY id").fetchall()]
        stock=[[8,14,5,18,4,12,3,7],[5,10,6,15,8,9,2,5],[3,8,7,11,5,13,4,6],[4,12,3,9,6,10,2,8]]
        rows=[]
        for i,bid in enumerate(ids):
            for j,g in enumerate(BLOOD_GROUPS): rows.append((bid,g,stock[i][j],now_iso()))
        conn.executemany("INSERT INTO inventory(bank_id,blood_group,units,updated_at) VALUES(?,?,?,?)",rows)
    # Demo users exist so the first run is immediately demonstrable.
    demos=[
      ("emergency","1234","Emergency Centre","emergency","Adyar",None,1,1),
      ("bloodbank","1234","Apollo Blood Centre","bloodbank","Chennai Central",None,1,1),
      ("donor","1234","Verified Donor","donor","Egmore","O-",1,1),
      ("admin","1234","System Administrator","admin","Chennai",None,1,1),
    ]
    for u,p,n,r,l,g,v,a in demos:
        if conn.execute("SELECT 1 FROM users WHERE username=?",(u,)).fetchone() is None:
            conn.execute("INSERT INTO users(username,password_hash,name,role,location,blood_group,verified,available,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(u,generate_password_hash(p),n,r,l,g,v,a,now_iso()))
    conn.commit(); conn.close()

def verify_password(stored_hash, password):
    """Verify both current Werkzeug hashes and older Passlib pbkdf2_sha256 hashes.

    Older BloodBridge demo databases may contain hashes such as
    pbkdf2_sha256$29000$salt$digest. Werkzeug does not understand that
    Passlib format, which caused the "Invalid hash method 'pbkdf2_sha256'"
    error. We verify the legacy format here and migrate it to Werkzeug
    automatically after a successful login.
    """
    if not stored_hash:
        return False
    try:
        if stored_hash.startswith("pbkdf2_sha256$"):
            parts = stored_hash.split("$")
            if len(parts) != 4:
                return False
            _, rounds_text, salt, expected = parts
            rounds = int(rounds_text)
            derived = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                rounds,
            )
            actual = base64.b64encode(derived, altchars=b"./").decode("ascii").rstrip("=")
            return hmac.compare_digest(actual, expected)
        return check_password_hash(stored_hash, password)
    except Exception:
        return False


LOCATION_CACHE = {}

def _normalise_location(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9+\- ]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    for suffix in (" chennai", ", chennai", " tamil nadu", ", tamil nadu"):
        if value.endswith(suffix): value = value[:-len(suffix)].strip(" ,")
    return value

def resolve_location(location):
    raw=(location or "").strip(); clean=_normalise_location(raw)
    if not clean: return PLACES["chennai"]
    if clean in LOCATION_CACHE: return LOCATION_CACHE[clean]
    if clean in PLACES:
        LOCATION_CACHE[clean]=PLACES[clean]; return PLACES[clean]
    for key,value in PLACES.items():
        if key in clean or clean in key:
            LOCATION_CACHE[clean]=value; return value
    match=difflib.get_close_matches(clean,list(PLACES.keys()),n=1,cutoff=0.62)
    if match:
        value=PLACES[match[0]]; LOCATION_CACHE[clean]=value; return value
    try:
        query=urllib.parse.urlencode({"q":raw+", Chennai, India","format":"json","limit":1})
        req=urllib.request.Request("https://nominatim.openstreetmap.org/search?"+query,headers={"User-Agent":"BloodBridge-Demo/1.0"})
        with urllib.request.urlopen(req,timeout=5) as response: data=json.loads(response.read().decode("utf-8"))
        if data:
            value=(float(data[0]["lat"]),float(data[0]["lon"])); LOCATION_CACHE[clean]=value; return value
    except Exception: pass
    LOCATION_CACHE[clean]=PLACES["chennai"]; return PLACES["chennai"]

def distance_km(lat1,lon1,lat2,lon2):
    r=6371.0
    p1,p2=math.radians(lat1),math.radians(lat2)
    dp=math.radians(lat2-lat1); dl=math.radians(lon2-lon1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return round(2*r*math.asin(math.sqrt(a)),2)

def confidence(updated_at,verified=1):
    try:
        dt=datetime.fromisoformat(updated_at.replace("Z","+00:00"))
        age=max(0,(datetime.now(timezone.utc)-dt).total_seconds()/3600)
    except Exception: age=72
    freshness=max(0,1-age/48)
    return round((0.65*freshness+0.35*int(bool(verified)))*100,1)

def sign_request(data):
    raw="|".join(str(data[k]) for k in ["hospital","blood_group","units_required","urgency","location"])
    return hmac.new(SIGNING_SECRET.encode(),raw.encode(),hashlib.sha256).hexdigest()

def audit(actor,action,details=""):
    c=db(); c.execute("INSERT INTO audit_logs(actor,action,details,created_at) VALUES(?,?,?,?)",(actor,action,details,now_iso())); c.commit(); c.close()

def logged(): return bool(session.get("user_id"))

def role_required(*roles):
    return logged() and session.get("role") in roles

def render_page(content,title="BloodBridge",scripts=""):
    return render_template_string(BASE_HTML,title=title,content=content,scripts=scripts)


LOGIN_HTML="""
<div class='login-page'>
  <div class='auth-shell'>
    <section class='auth-visual'>
      <div class='auth-logo'><span class='cross'>+</span>BloodBridge</div>
      <h1>Connect the right blood <span>at the right time.</span></h1>
      <p>One coordination layer for emergency centres, blood banks, donors and administrators — with availability, location intelligence and auditable decisions.</p>
      <div class='auth-pills'>
        <span class='auth-pill'>LIVE AVAILABILITY</span><span class='auth-pill'>GIS RESOURCE MAP</span><span class='auth-pill'>ROLE-BASED ACCESS</span>
      </div>
      <div class='auth-steps'>
        <div class='auth-step'><i>1</i> Sign in to your BloodBridge workspace</div>
        <div class='auth-step'><i>2</i> Create or respond to an emergency request</div>
        <div class='auth-step'><i>3</i> Compare nearby compatible resources</div>
      </div>
    </section>
    <section class='auth-panel'>
      <div class='auth-card'>
        <div class='auth-eyebrow'>BloodBridge • Secure workspace</div>
        <h2>Welcome back.</h2>
        <p class='subtitle'>Sign in to continue coordinating blood resources.</p>
        <form method='post'>
          <div class='field'><label>Username</label><input name='username' placeholder='Enter your username' autocomplete='username' required autofocus></div>
          <br>
          <div class='field'><label>Password</label><input type='password' name='password' placeholder='Enter your password' autocomplete='current-password' required></div>
          <br>
          <button class='btn auth-submit' type='submit'>Sign in to BloodBridge</button>
        </form>
        <div class='auth-links'><span class='muted'>New to BloodBridge?</span><a href='{{url_for("register")}}'>Create account →</a></div>
        <div class='demo-box'><b>Demo access</b><br>emergency / bloodbank / donor / admin &nbsp;•&nbsp; password: <b>1234</b></div>
      </div>
    </section>
  </div>
</div>
"""
REGISTER_HTML="""
<div class='login-page'>
  <div class='auth-shell'>
    <section class='auth-visual'>
      <div class='auth-logo'><span class='cross'>+</span>BloodBridge</div>
      <h1>Build the network before the <span>emergency.</span></h1>
      <p>Create one account and BloodBridge will route you into the correct workspace based on your role.</p>
      <div class='auth-pills'>
        <span class='auth-pill'>EMERGENCY CENTRE</span><span class='auth-pill'>BLOOD BANK</span><span class='auth-pill'>DONOR</span>
      </div>
      <div class='auth-steps'>
        <div class='auth-step'><i>1</i> Create your account</div>
        <div class='auth-step'><i>2</i> Enter your locality and blood details</div>
        <div class='auth-step'><i>3</i> Sign in and open your workspace</div>
      </div>
    </section>
    <section class='auth-panel'>
      <div class='auth-card'>
        <div class='auth-eyebrow'>BloodBridge • New account</div>
        <h2>Create account.</h2>
        <p class='subtitle'>Choose your role and join the coordination network.</p>
        <form method='post'>
          <div class='form-grid'>
            <div class='field'><label>Full name</label><input name='name' placeholder='Your name' required></div>
            <div class='field'><label>Username</label><input name='username' placeholder='Choose a username' required></div>
            <div class='field'><label>Password</label><input type='password' name='password' minlength='4' placeholder='Minimum 4 characters' required></div>
            <div class='field'><label>Role</label><select name='role' id='role' required>
              <option value='emergency'>Emergency Centre</option><option value='bloodbank'>Blood Bank</option><option value='donor'>Donor</option>
            </select><div class='role-note'>Your dashboard changes automatically by role.</div></div>
            <div class='field'><label>Location / locality</label><input name='location' placeholder='e.g. Adyar, Chennai' required></div>
            <div class='field' id='bloodfield'><label>Blood group (donor)</label><select name='blood_group'><option value=''>Not applicable</option>{% for g in groups %}<option>{{g}}</option>{% endfor %}</select></div>
          </div>
          <br><button class='btn auth-submit' type='submit'>Create my BloodBridge account</button>
        </form>
        <div class='auth-links'><a href='{{url_for("login")}}'>← Back to login</a><span class='muted'>Already registered?</span></div>
      </div>
    </section>
  </div>
</div>
"""

@app.route('/')
def home():
    return redirect(url_for('dashboard') if logged() else url_for('login'))

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=request.form.get('username','').strip(); p=request.form.get('password','')
        c=db(); user=c.execute('SELECT * FROM users WHERE username=?',(u,)).fetchone(); c.close()
        if user and verify_password(user['password_hash'], p):
            # Automatically migrate old Passlib hashes to the current
            # Werkzeug format so the error never returns on later logins.
            if str(user['password_hash']).startswith('pbkdf2_sha256$'):
                c2 = db()
                c2.execute('UPDATE users SET password_hash=? WHERE id=?', (generate_password_hash(p), user['id']))
                c2.commit(); c2.close()
            session.clear(); session.update(user_id=user['id'],username=user['username'],name=user['name'],role=user['role'],location=user['location'],blood_group=user['blood_group'])
            audit(user['username'],'LOGIN','Successful login')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.')
    return render_template_string('<style>'+BASE_CSS+'</style>'+LOGIN_HTML)

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        name=request.form.get('name','').strip(); username=request.form.get('username','').strip().lower(); password=request.form.get('password',''); role=request.form.get('role',''); location=request.form.get('location','').strip(); bg=request.form.get('blood_group') or None
        if role not in ['emergency','bloodbank','donor']:
            flash('Choose a valid role.'); return render_template_string('<style>'+BASE_CSS+'</style>'+REGISTER_HTML,groups=BLOOD_GROUPS)
        if not all([name,username,password,location]): flash('Please complete all required fields.'); return render_template_string('<style>'+BASE_CSS+'</style>'+REGISTER_HTML,groups=BLOOD_GROUPS)
        if role=='donor' and bg not in BLOOD_GROUPS: flash('Donors must select a blood group.'); return render_template_string('<style>'+BASE_CSS+'</style>'+REGISTER_HTML,groups=BLOOD_GROUPS)
        c=db()
        try:
            c.execute('INSERT INTO users(username,password_hash,name,role,location,blood_group,verified,available,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(username,generate_password_hash(password),name,role,location,bg,0 if role!='emergency' else 1,1,now_iso()))
            if role == 'bloodbank':
                lat, lng = resolve_location(location)
                c.execute('INSERT INTO blood_banks(name,location,latitude,longitude,verified) VALUES(?,?,?,?,0)',(name,location,lat,lng))
                bank_id = c.execute('SELECT last_insert_rowid()').fetchone()[0]
                c.executemany('INSERT INTO inventory(bank_id,blood_group,units,updated_at) VALUES(?,?,?,?)',[(bank_id,g,0,now_iso()) for g in BLOOD_GROUPS])
            c.commit()
        except sqlite3.IntegrityError:
            c.close(); flash('Username already exists.'); return render_template_string('<style>'+BASE_CSS+'</style>'+REGISTER_HTML,groups=BLOOD_GROUPS)
        c.close(); flash('Account created. Please login.'); return redirect(url_for('login'))
    return render_template_string('<style>'+BASE_CSS+'</style>'+REGISTER_HTML,groups=BLOOD_GROUPS)

@app.route('/logout')
def logout():
    if logged(): audit(session.get('username','unknown'),'LOGOUT','User logged out')
    session.clear(); return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not logged(): return redirect(url_for('login'))
    role=session['role']; c=db()
    if role=='emergency':
        requests=c.execute('SELECT * FROM requests WHERE user_id=? ORDER BY id DESC',(session['user_id'],)).fetchall()
        open_count=sum(r['status'] in ('OPEN','ALLOCATED') for r in requests)
        content=render_template_string("""
        <h1 class='title'>Emergency Dashboard</h1><p class='subtitle'>Create an emergency request and let BloodBridge calculate the best resource allocation.</p>
        <div class='hero'><h2>Decision engine ready</h2><p>Location is entered as a normal place name. GIS coordinates are resolved internally.</p><div class='actions'><a class='btn' href='{{url_for("new_request")}}'>Create Emergency Request</a><a class='btn secondary' href='{{url_for("gis")}}'>Open GIS Map</a><a class='btn secondary' href='{{url_for("simulation")}}'>Run Digital Twin</a></div></div><br>
        <div class='grid'><div class='card'><div class='label'>My requests</div><div class='metric'>{{requests|length}}</div></div><div class='card'><div class='label'>Active</div><div class='metric'>{{open_count}}</div></div><div class='card'><div class='label'>GIS</div><div class='metric'>ON</div></div><div class='card'><div class='label'>Signed requests</div><div class='metric'>✓</div></div></div><br>
        <div class='card'><h3>Recent requests</h3><div class='table-wrap'><table class='table'><tr><th>ID</th><th>Hospital</th><th>Blood</th><th>Units</th><th>Urgency</th><th>Status</th><th></th></tr>{% for r in requests %}<tr><td>#{{r.id}}</td><td>{{r.hospital}}</td><td>{{r.blood_group}}</td><td>{{r.units_required}}</td><td><span class='badge {{"red" if r.urgency=="CRITICAL" else "amber"}}'>{{r.urgency}}</span></td><td>{{r.status}}</td><td><a class='btn secondary' href='{{url_for("request_detail",request_id=r.id)}}'>View</a></td></tr>{% else %}<tr><td colspan='7'>No requests yet.</td></tr>{% endfor %}</table></div></div>
        """,requests=requests,open_count=open_count)
    elif role=='bloodbank':
        bank=c.execute('SELECT * FROM blood_banks WHERE name=? OR location=? LIMIT 1',(session.get('name'),session.get('location'))).fetchone()
        if not bank: bank=c.execute('SELECT * FROM blood_banks ORDER BY id LIMIT 1').fetchone()
        inv=c.execute('SELECT * FROM inventory WHERE bank_id=? ORDER BY blood_group',(bank['id'],)).fetchall()
        total=sum(x['units'] for x in inv)
        content=render_template_string("""
        <h1 class='title'>Blood Bank Dashboard</h1><p class='subtitle'>Manage inventory and respond to emergency allocation recommendations.</p><div class='grid'><div class='card'><div class='label'>Facility</div><div class='metric' style='font-size:20px'>{{bank.name}}</div></div><div class='card'><div class='label'>Total units</div><div class='metric'>{{total}}</div></div><div class='card'><div class='label'>Verified</div><div class='metric'>✓</div></div><div class='card'><div class='label'>Location</div><div class='metric' style='font-size:18px'>{{bank.location}}</div></div></div><br><div class='card'><h3>Current inventory</h3><div class='table-wrap'><table class='table'><tr><th>Group</th><th>Units</th><th>Confidence</th><th>Updated</th></tr>{% for x in inv %}<tr><td>{{x.blood_group}}</td><td>{{x.units}}</td><td><span class='badge green'>{{confidence(x.updated_at,bank.verified)}}%</span></td><td>{{x.updated_at[:19]}}</td></tr>{% endfor %}</table></div></div>
        """,bank=bank,inv=inv,total=total,confidence=confidence)
    elif role=='donor':
        u=c.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone(); reqs=c.execute('SELECT * FROM requests WHERE status IN ("OPEN","ALLOCATED") ORDER BY id DESC LIMIT 10').fetchall()
        content=render_template_string("""
        <h1 class='title'>Donor Dashboard</h1><p class='subtitle'>Your availability can become a verified fallback resource during an emergency.</p><div class='hero'><h2>{{u.name}} · {{u.blood_group or 'Blood group not set'}}</h2><p>{{u.location}} · {% if u.verified %}Verified donor{% else %}Verification pending{% endif %}</p><a class='btn' href='{{url_for("donor_profile")}}'>Update availability</a></div><br><div class='grid'><div class='card'><div class='label'>Availability</div><div class='metric'>{{'ON' if u.available else 'OFF'}}</div></div><div class='card'><div class='label'>Verified</div><div class='metric'>{{'YES' if u.verified else 'PENDING'}}</div></div><div class='card'><div class='label'>Blood group</div><div class='metric'>{{u.blood_group or '-'}}</div></div><div class='card'><div class='label'>Open emergencies</div><div class='metric'>{{reqs|length}}</div></div></div>
        """,u=u,reqs=reqs)
    else:
        stats={
          'users':c.execute('SELECT COUNT(*) FROM users').fetchone()[0],
          'requests':c.execute('SELECT COUNT(*) FROM requests').fetchone()[0],
          'banks':c.execute('SELECT COUNT(*) FROM blood_banks').fetchone()[0],
          'donors':c.execute("SELECT COUNT(*) FROM users WHERE role='donor'").fetchone()[0],
        }
        content=render_template_string("""
        <h1 class='title'>Admin Control Centre</h1><p class='subtitle'>System-wide visibility across users, emergencies, resources and audit events.</p><div class='grid'><div class='card'><div class='label'>Users</div><div class='metric'>{{stats.users}}</div></div><div class='card'><div class='label'>Emergency requests</div><div class='metric'>{{stats.requests}}</div></div><div class='card'><div class='label'>Blood banks</div><div class='metric'>{{stats.banks}}</div></div><div class='card'><div class='label'>Donors</div><div class='metric'>{{stats.donors}}</div></div></div><br><div class='grid2'><div class='card'><h3>System capabilities</h3><div class='timeline'><div class='timeline-item'>GIS resource mapping</div><div class='timeline-item'>Availability confidence</div><div class='timeline-item'>Optimal allocation</div><div class='timeline-item'>Signed requests & audit trail</div><div class='timeline-item'>Digital Twin simulation</div><div class='timeline-item'>Offline-ready local database</div></div></div><div class='card'><h3>Quick actions</h3><div class='actions'><a class='btn' href='{{url_for("admin_users")}}'>Manage users</a><a class='btn secondary' href='{{url_for("admin_audit")}}'>Audit logs</a></div></div></div>
        """,stats=type('S',(),stats)())
    c.close(); return render_page(content,'Dashboard')

@app.route('/emergency/new',methods=['GET','POST'])
def new_request():
    if not role_required('emergency','admin'): return redirect(url_for('dashboard'))
    if request.method=='POST':
        hospital=request.form.get('hospital','').strip(); bg=request.form.get('blood_group',''); units=int(request.form.get('units_required','0') or 0); urgency=request.form.get('urgency','HIGH'); location=request.form.get('location','').strip()
        if not hospital or bg not in BLOOD_GROUPS or units<1 or urgency not in URGENCIES or not location:
            flash('Please enter valid emergency details.'); return redirect(url_for('new_request'))
        lat,lng=resolve_location(location); data={'hospital':hospital,'blood_group':bg,'units_required':units,'urgency':urgency,'location':location}; sig=sign_request(data)
        c=db(); c.execute('INSERT INTO requests(user_id,hospital,blood_group,units_required,urgency,location,latitude,longitude,signature,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(session['user_id'],hospital,bg,units,urgency,location,lat,lng,sig,now_iso())); rid=c.execute('SELECT last_insert_rowid()').fetchone()[0]; c.commit(); c.close()
        audit(session['username'],'CREATE_REQUEST',f'request={rid};signature={sig[:16]}...')
        optimize(rid)
        return redirect(url_for('request_detail',request_id=rid))
    content=render_template_string("""
    <h1 class='title'>Emergency Blood Request</h1><p class='subtitle'>Tell BloodBridge <b>where the emergency is</b>. The system finds the nearest compatible blood resources automatically.</p>
    <div class='hero'><h2 style='margin-top:0'>Fast emergency matching</h2><p>Enter a locality such as <b>Adyar, Chennai</b> or <b>Velachery</b>. You do <b>not</b> need latitude or longitude. BloodBridge converts the place into an internal map point and ranks nearby blood banks first.</p></div><br>
    <div class='card'><form method='post'><div class='form-grid'><div class='field'><label>Emergency Centre / Hospital</label><input name='hospital' placeholder='e.g. City Emergency Centre' required></div><div class='field'><label>Emergency location</label><input name='location' placeholder='e.g. Adyar, Chennai' required><span class='small'>Use a locality, landmark, hospital area, or Chennai neighbourhood.</span></div><div class='field'><label>Blood group required</label><select name='blood_group'>{% for g in groups %}<option>{{g}}</option>{% endfor %}</select></div><div class='field'><label>Units required</label><input type='number' name='units_required' min='1' value='4' required></div><div class='field'><label>Urgency</label><select name='urgency'>{% for u in urgencies %}<option>{{u}}</option>{% endfor %}</select></div><div class='field'><label>GIS location</label><input value='Automatic — no coordinates required' disabled></div></div><br><button class='btn'>Find Available Blood Now →</button></form></div>
    """,groups=BLOOD_GROUPS,urgencies=URGENCIES)
    return render_page(content,'New Emergency')

def optimize(request_id):
    c=db(); req=c.execute('SELECT * FROM requests WHERE id=?',(request_id,)).fetchone()
    if not req: c.close(); return []
    c.execute("DELETE FROM allocations WHERE request_id=? AND status='PROPOSED'",(request_id,))
    candidates=[]; allowed=COMPATIBILITY.get(req['blood_group'],[req['blood_group']]); urgency_weight={'CRITICAL':100,'HIGH':75,'MEDIUM':45,'LOW':20}.get(req['urgency'],45)
    banks=c.execute('SELECT i.*,b.name,b.location,b.latitude,b.longitude,b.verified FROM inventory i JOIN blood_banks b ON b.id=i.bank_id WHERE i.units>0').fetchall()
    for row in banks:
        if row['blood_group'] not in allowed: continue
        dist=distance_km(req['latitude'],req['longitude'],row['latitude'],row['longitude']); conf=confidence(row['updated_at'],row['verified']); exact=30 if row['blood_group']==req['blood_group'] else 15
        score=urgency_weight+exact+conf*.25-dist*5.0+min(row['units'],req['units_required'])*2.0
        candidates.append((score,row,dist,conf))
    candidates.sort(key=lambda x:(x[2],-x[0])); remaining=int(req['units_required']); results=[]
    for score,row,dist,conf in candidates:
        if remaining<=0: break
        take=min(remaining,int(row['units']))
        c.execute('INSERT INTO allocations(request_id,bank_id,blood_group,units,distance_km,confidence,priority_score,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(request_id,row['bank_id'],row['blood_group'],take,dist,conf,round(score,2),'PROPOSED',now_iso()))
        results.append({'bank_id':row['bank_id'],'name':row['name'],'location':row['location'],'group':row['blood_group'],'units':take,'distance':dist,'confidence':conf,'score':round(score,2),'lat':row['latitude'],'lng':row['longitude']}); remaining-=take
    if remaining>0:
        donors=c.execute("SELECT * FROM users WHERE role='donor' AND available=1 AND verified=1 AND blood_group=?",(req['blood_group'],)).fetchall(); dc=[]
        for d in donors:
            dlat,dlng=resolve_location(d['location']); dist=distance_km(req['latitude'],req['longitude'],dlat,dlng); conf=95.0; score=urgency_weight+30+conf*.25-dist*5.0; dc.append((dist,score,d,dlat,dlng,conf))
        dc.sort(key=lambda x:(x[0],-x[1]))
        for dist,score,d,dlat,dlng,conf in dc:
            if remaining<=0: break
            c.execute('INSERT INTO allocations(request_id,donor_id,blood_group,units,distance_km,confidence,priority_score,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(request_id,d['id'],d['blood_group'],1,dist,conf,round(score,2),'PROPOSED',now_iso()))
            results.append({'donor_id':d['id'],'name':d['name'],'location':d['location'],'group':d['blood_group'],'units':1,'distance':dist,'confidence':conf,'score':round(score,2),'lat':dlat,'lng':dlng,'donor':True}); remaining-=1
    c.execute("UPDATE requests SET status=? WHERE id=?",('ALLOCATED' if results else 'OPEN',request_id)); c.commit(); c.close(); return results

@app.route('/request/<int:request_id>')
def request_detail(request_id):
    if not logged(): return redirect(url_for('login'))
    c=db(); r=c.execute('SELECT r.*,u.name as requester FROM requests r JOIN users u ON u.id=r.user_id WHERE r.id=?',(request_id,)).fetchone(); a=c.execute('SELECT a.*,b.name as bank_name,d.name as donor_name FROM allocations a LEFT JOIN blood_banks b ON b.id=a.bank_id LEFT JOIN users d ON d.id=a.donor_id WHERE a.request_id=? ORDER BY a.priority_score DESC',(request_id,)).fetchall(); c.close()
    if not r: flash('Request not found.'); return redirect(url_for('dashboard'))
    content=render_template_string("""
    <h1 class='title'>Emergency #{{r.id}}</h1><p class='subtitle'>{{r.hospital}} · {{r.location}}</p><div class='grid'><div class='card'><div class='label'>Blood</div><div class='metric'>{{r.blood_group}}</div></div><div class='card'><div class='label'>Units</div><div class='metric'>{{r.units_required}}</div></div><div class='card'><div class='label'>Urgency</div><div class='metric' style='font-size:20px'>{{r.urgency}}</div></div><div class='card'><div class='label'>Status</div><div class='metric' style='font-size:20px'>{{r.status}}</div></div></div><br><div class='grid2'><div class='card'><h3>Verified request</h3><p><span class='badge green'>✓ SIGNED</span></p><p class='small'>Digital signature: {{r.signature[:32]}}…</p><p class='small'>Created: {{r.created_at}}</p></div><div class='card'><h3>Decision engine</h3><p>Recommendations are ranked using urgency, compatibility, availability confidence, distance and available units.</p><a class='btn secondary' href='{{url_for("gis",request_id=r.id)}}'>View GIS allocation</a>{% if session.get('role') in ['emergency','admin'] and r.status != 'RECEIVED' %}<form method='post' action='{{url_for("blood_received",request_id=r.id)}}' style='display:inline'><button class='btn success'>✓ Blood Received</button></form>{% endif %}</div></div><br><div class='card'><div class='section-head'><div><h3 style='margin:0'>Nearest available resources</h3><p class='small' style='margin:5px 0 0'>Ranked by proximity, compatible stock, confidence and urgency.</p></div>{% if a %}<span class='badge green'>{{a[0].distance_km}} km closest</span>{% endif %}</div><div class='table-wrap'><table class='table'><tr><th>Rank</th><th>Resource</th><th>Type</th><th>Blood</th><th>Units</th><th>Distance</th><th>Confidence</th><th>Status</th></tr>{% for x in a %}<tr class='{% if loop.first %}best-row{% endif %}'><td>{% if loop.first %}<span class='badge green'>BEST</span>{% else %}{{loop.index}}{% endif %}</td><td><b>{{x.bank_name or x.donor_name}}</b></td><td>{{'Donor' if x.donor_id else 'Blood Bank'}}</td><td><b>{{x.blood_group}}</b></td><td>{{x.units}}</td><td><b>{{x.distance_km}} km</b></td><td><span class='badge green'>{{x.confidence}}%</span></td><td>{{x.status}}</td></tr>{% else %}<tr><td colspan='8'>No compatible resources currently found.</td></tr>{% endfor %}</table></div></div>
    """,r=r,a=a)
    return render_page(content,'Emergency Details')

@app.route('/gis')
def gis():
    if not logged(): return redirect(url_for('login'))
    rid=request.args.get('request_id',type=int); c=db(); req=c.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone() if rid else c.execute('SELECT * FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 1',(session['user_id'],)).fetchone()
    alloc=c.execute('SELECT a.*,b.name as bank_name,b.latitude as blat,b.longitude as blng,d.name as donor_name,d.location as donor_location FROM allocations a LEFT JOIN blood_banks b ON b.id=a.bank_id LEFT JOIN users d ON d.id=a.donor_id WHERE a.request_id=? ORDER BY a.priority_score DESC',(req['id'],)).fetchall() if req else []; c.close()
    if not req: return render_page("<h1 class='title'>GIS Resource Map</h1><p class='subtitle'>Create an emergency request first.</p>",'GIS Map')
    points=[{'name':req['hospital'],'type':'Emergency','lat':float(req['latitude']),'lng':float(req['longitude']),'info':f"{req['blood_group']} · {req['units_required']} units · {req['urgency']}",'class':'emergency'}]
    for a in alloc:
        if a['bank_id']: points.append({'name':a['bank_name'],'type':'Blood Bank','lat':float(a['blat']),'lng':float(a['blng']),'info':f"{a['blood_group']} · {a['units']} units · {a['confidence']}% confidence",'class':'resource'})
        elif a['donor_id']:
            la,lo=resolve_location(a['donor_location']); points.append({'name':a['donor_name'],'type':'Verified Donor','lat':float(la),'lng':float(lo),'info':f"{a['blood_group']} · donor fallback · {a['confidence']}% confidence",'class':'resource'})
    js="""<script>(function(){const pts=__POINTS__,status=document.getElementById('map-status'),fb=document.getElementById('map-fallback');function draw(extra){fb.innerHTML='';fb.style.display='block';let a=pts.slice();if(extra)a.push({name:'Your GPS',type:'Live GPS',lat:extra.lat,lng:extra.lng,info:'accuracy ±'+Math.round(extra.accuracy||0)+' m',class:'gps'});let minLa=Math.min.apply(null,a.map(p=>p.lat)),maxLa=Math.max.apply(null,a.map(p=>p.lat)),minLo=Math.min.apply(null,a.map(p=>p.lng)),maxLo=Math.max.apply(null,a.map(p=>p.lng));let dLa=Math.max(maxLa-minLa,.015),dLo=Math.max(maxLo-minLo,.015);minLa-=dLa*.25;maxLa+=dLa*.25;minLo-=dLo*.25;maxLo+=dLo*.25;for(let i=0;i<6;i++){let r=document.createElement('div');r.className='road';r.style.left='5%';r.style.top=(15+i*16)+'%';r.style.width='90%';r.style.transform='rotate('+(i%2?2:-2)+'deg)';fb.appendChild(r)}a.forEach(function(p){let x=((p.lng-minLo)/(maxLo-minLo))*90+5,y=(1-(p.lat-minLa)/(maxLa-minLa))*80+10,d=document.createElement('div'),l=document.createElement('div');d.className='dot '+(p.class||'resource');d.style.left=x+'%';d.style.top=y+'%';d.title=p.name+' — '+p.info;l.className='label';l.style.left=x+'%';l.style.top=y+'%';l.textContent=p.name;fb.appendChild(d);fb.appendChild(l)});status.textContent='Map ready • '+a.length+' locations'}function start(){if(typeof L==='undefined'){draw();return}try{let map=L.map('map').setView([__LAT__,__LNG__],12),tiles=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'});tiles.on('tileerror',function(){draw()});tiles.addTo(map);let b=[];pts.forEach(function(p){let m=L.marker([p.lat,p.lng]).addTo(map);m.bindPopup('<b>'+p.name+'</b><br>'+p.type+'<br>'+p.info);b.push([p.lat,p.lng])});if(b.length>1)map.fitBounds(b,{padding:[40,40],maxZoom:14});status.textContent='GIS map ready • '+pts.length+' mapped resources';window.addEventListener('bloodbridge:gps',function(e){let p=e.detail;if(window.bbGpsMarker)bbGpsMarker.setLatLng([p.lat,p.lng]);else window.bbGpsMarker=L.circleMarker([p.lat,p.lng],{radius:9,color:'#2267d8',fillColor:'#2267d8',fillOpacity:.9}).addTo(map).bindPopup('Your live GPS')});setTimeout(function(){map.invalidateSize()},250)}catch(e){draw()}}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start()})();</script>""".replace('__POINTS__',json.dumps(points)).replace('__LAT__',str(req['latitude'])).replace('__LNG__',str(req['longitude']))
    content=render_template_string("""<h1 class='title'>GIS Resource Map</h1><p class='subtitle'>Emergency #{{req.id}} · {{req.location}} · {{req.blood_group}} · {{req.units_required}} units</p><div class='card'><div id='map' class='map'><div id='map-status' class='map-status'>Loading GIS map…</div><div id='map-fallback' class='map-fallback'></div></div></div><br><div class='card'><h3>Mapped allocation resources</h3><div class='table-wrap'><table class='table'><tr><th>Resource</th><th>Type</th><th>Units</th><th>Distance</th><th>Confidence</th></tr>{% for a in alloc %}<tr><td>{{a.bank_name or a.donor_name}}</td><td>{{'Donor' if a.donor_id else 'Blood Bank'}}</td><td>{{a.units}}</td><td>{{a.distance_km}} km</td><td><span class='badge green'>{{a.confidence}}%</span></td></tr>{% endfor %}</table></div></div>""",req=req,alloc=alloc)
    return render_page(content,'GIS Map',js)

@app.route('/simulation',methods=['GET','POST'])
def simulation():
    if not role_required('emergency','admin'): return redirect(url_for('dashboard'))
    severity=int(request.form.get('severity',1)) if request.method=='POST' else 1
    base_demand=10; demand=base_demand*severity
    c=db(); stock=c.execute('SELECT SUM(units) FROM inventory').fetchone()[0] or 0; groups=c.execute('SELECT blood_group,SUM(units) units FROM inventory GROUP BY blood_group ORDER BY blood_group').fetchall(); c.close()
    coverage=round(min(100,stock/demand*100),1) if demand else 100; status='STABLE' if coverage>=100 else ('STRESSED' if coverage>=60 else 'CRITICAL')
    content=render_template_string("""
    <h1 class='title'>Digital Twin Simulation</h1><p class='subtitle'>Test how BloodBridge responds when emergency demand increases.</p><div class='card'><form method='post'><div class='field'><label>Disaster severity: {{severity}}×</label><input type='range' name='severity' min='1' max='5' value='{{severity}}' oninput='this.form.querySelector("output").value=this.value'><output>{{severity}}</output></div><br><button class='btn'>Run Simulation</button></form></div><br><div class='grid'><div class='card'><div class='label'>Simulated demand</div><div class='metric'>{{demand}} units</div></div><div class='card'><div class='label'>Current inventory</div><div class='metric'>{{stock}}</div></div><div class='card'><div class='label'>Coverage</div><div class='metric'>{{coverage}}%</div></div><div class='card'><div class='label'>System state</div><div class='metric' style='font-size:20px'>{{status}}</div></div></div><br><div class='card'><h3>Blood resource model</h3><div class='table-wrap'><table class='table'><tr><th>Blood group</th><th>Units available</th></tr>{% for g in groups %}<tr><td>{{g.blood_group}}</td><td>{{g.units}}</td></tr>{% endfor %}</table></div></div>
    """,severity=severity,demand=demand,stock=stock,coverage=coverage,status=status,groups=groups)
    return render_page(content,'Digital Twin')

@app.route('/bloodbank/inventory',methods=['GET','POST'])
def inventory():
    if not role_required('bloodbank','admin'): return redirect(url_for('dashboard'))
    c=db(); bank=c.execute('SELECT * FROM blood_banks WHERE name=? OR location=? LIMIT 1',(session.get('name'),session.get('location'))).fetchone() or c.execute('SELECT * FROM blood_banks ORDER BY id LIMIT 1').fetchone()
    if request.method=='POST':
        bg=request.form.get('blood_group'); units=max(0,int(request.form.get('units','0') or 0)); c.execute('UPDATE inventory SET units=?,updated_at=? WHERE bank_id=? AND blood_group=?',(units,now_iso(),bank['id'],bg)); c.commit(); audit(session['username'],'UPDATE_INVENTORY',f'{bank["name"]}: {bg}={units}'); flash('Inventory updated.');
    inv=c.execute('SELECT * FROM inventory WHERE bank_id=? ORDER BY blood_group',(bank['id'],)).fetchall(); c.close()
    content=render_template_string("""<h1 class='title'>Inventory</h1><p class='subtitle'>Update stock without exposing latitude/longitude or technical GIS fields.</p><div class='card'><div class='table-wrap'><table class='table'><tr><th>Blood</th><th>Current units</th><th>Updated</th><th>Update</th></tr>{% for x in inv %}<tr><form method='post'><td>{{x.blood_group}}<input type='hidden' name='blood_group' value='{{x.blood_group}}'></td><td><input type='number' min='0' name='units' value='{{x.units}}' style='width:100px;padding:8px;border:1px solid #e3e9f2;border-radius:8px'></td><td>{{x.updated_at[:19]}}</td><td><button class='btn'>Save</button></td></form></tr>{% endfor %}</table></div></div>""",inv=inv)
    return render_page(content,'Inventory')

@app.route('/bloodbank/requests')
def bank_requests():
    if not role_required('bloodbank','admin'): return redirect(url_for('dashboard'))
    c=db(); rows=c.execute('SELECT r.*,a.id allocation_id,a.units allocation_units,a.status allocation_status,b.name bank_name FROM requests r JOIN allocations a ON a.request_id=r.id JOIN blood_banks b ON b.id=a.bank_id WHERE b.name=? ORDER BY r.id DESC',(session.get('name'),)).fetchall();
    if not rows: rows=c.execute('SELECT r.*,a.id allocation_id,a.units allocation_units,a.status allocation_status,b.name bank_name FROM requests r JOIN allocations a ON a.request_id=r.id JOIN blood_banks b ON b.id=a.bank_id ORDER BY r.id DESC').fetchall()
    c.close(); content=render_template_string("""<h1 class='title'>Emergency Requests</h1><p class='subtitle'>Recommended allocations for this blood bank.</p><div class='card'><div class='table-wrap'><table class='table'><tr><th>Request</th><th>Hospital</th><th>Blood</th><th>Units</th><th>Urgency</th><th>Allocation</th><th>Action</th></tr>{% for x in rows %}<tr><td>#{{x.id}}</td><td>{{x.hospital}}</td><td>{{x.blood_group}}</td><td>{{x.allocation_units}}</td><td>{{x.urgency}}</td><td>{{x.allocation_status}}</td><td><form method='post' action='{{url_for("allocation_action",allocation_id=x.allocation_id)}}' style='display:inline'><button class='btn success' name='action' value='ACCEPTED'>Accept</button>{% if x.allocation_status=='ACCEPTED' %}<button class='btn secondary' name='action' value='DISPATCHED'>Dispatch</button>{% endif %}</form></td></tr>{% else %}<tr><td colspan='7'>No allocation requests.</td></tr>{% endfor %}</table></div></div>""",rows=rows); return render_page(content,'Emergency Requests')

@app.route('/allocation/<int:allocation_id>',methods=['POST'])
def allocation_action(allocation_id):
    if not logged(): return redirect(url_for('dashboard'))
    action=request.form.get('action','ACCEPTED').upper(); allowed={'ACCEPTED','DISPATCHED','RECEIVED','CANCELLED'}
    if action not in allowed: action='ACCEPTED'
    c=db(); a=c.execute('SELECT * FROM allocations WHERE id=?',(allocation_id,)).fetchone()
    if not a: c.close(); flash('Allocation not found.'); return redirect(url_for('dashboard'))
    c.execute('UPDATE allocations SET status=? WHERE id=?',(action,allocation_id)); req=c.execute('SELECT * FROM requests WHERE id=?',(a['request_id'],)).fetchone()
    if req:
        if action=='RECEIVED': c.execute('UPDATE requests SET status=? WHERE id=?',('RECEIVED',a['request_id']))
        if action=='RECEIVED' and a['donor_id']: notify_user(a['donor_id'],'Blood Received',f'{req["hospital"]} confirmed receipt of {a["units"]} unit(s) of {a["blood_group"]}. Thank you.','received')
        if action=='RECEIVED' and a['bank_id']:
            b=c.execute('SELECT name FROM blood_banks WHERE id=?',(a['bank_id'],)).fetchone(); u=c.execute("SELECT id FROM users WHERE role='bloodbank' AND name=? LIMIT 1",(b['name'],)).fetchone() if b else None
            if u: notify_user(u['id'],'Blood Received',f'{req["hospital"]} confirmed receipt of {a["units"]} unit(s) of {a["blood_group"]}.','received')
        titles={'ACCEPTED':'Allocation Accepted','DISPATCHED':'Blood Dispatched','RECEIVED':'Blood Received','CANCELLED':'Allocation Cancelled'}; msgs={'ACCEPTED':f'Blood bank accepted allocation #{allocation_id} for {req["blood_group"]}.','DISPATCHED':f'Allocation #{allocation_id} has been dispatched to {req["hospital"]}.','RECEIVED':f'{req["hospital"]} confirmed receipt of {a["units"]} unit(s) of {a["blood_group"]}.','CANCELLED':f'Allocation #{allocation_id} was cancelled.'}; notify_user(req['user_id'],titles[action],msgs[action],'allocation')
    if action=='ACCEPTED' and a['bank_id']: c.execute('UPDATE inventory SET units=MAX(0,units-?),updated_at=? WHERE bank_id=? AND blood_group=?',(a['units'],now_iso(),a['bank_id'],a['blood_group']))
    c.commit(); c.close(); audit(session['username'],'ALLOCATION_'+action,f'allocation={allocation_id}'); flash('Allocation status updated.'); return redirect(request.referrer or url_for('dashboard'))

@app.route('/request/<int:request_id>/received',methods=['POST'])
def blood_received(request_id):
    if not role_required('emergency','admin'): return redirect(url_for('dashboard'))
    c=db(); req=c.execute('SELECT * FROM requests WHERE id=?',(request_id,)).fetchone()
    if not req: c.close(); flash('Emergency request not found.'); return redirect(url_for('dashboard'))
    allocs=c.execute('SELECT * FROM allocations WHERE request_id=?',(request_id,)).fetchall(); c.execute('UPDATE requests SET status=? WHERE id=?',('RECEIVED',request_id)); recipients=[]
    for a in allocs:
        if a['donor_id']: recipients.append(a['donor_id'])
        if a['bank_id']:
            b=c.execute('SELECT name FROM blood_banks WHERE id=?',(a['bank_id'],)).fetchone()
            if b:
                u=c.execute("SELECT id FROM users WHERE role='bloodbank' AND name=? LIMIT 1",(b['name'],)).fetchone()
                if u: recipients.append(u['id'])
        c.execute('UPDATE allocations SET status=? WHERE id=?',('RECEIVED',a['id']))
    c.commit(); c.close(); msg=f'{req["hospital"]} confirmed that {req["blood_group"]} blood has been received for Emergency #{request_id}.'
    for uid in set(recipients): notify_user(uid,'Blood Received',msg,'received')
    notify_user(req['user_id'],'Blood Received','Blood receipt was recorded successfully for this emergency.','received'); audit(session['username'],'BLOOD_RECEIVED',f'request={request_id}'); flash('✓ Blood Received recorded. The blood bank/donor has been notified.')
    return redirect(url_for('request_detail',request_id=request_id))

@app.route('/donor/profile',methods=['GET','POST'])
def donor_profile():
    if not role_required('donor'): return redirect(url_for('dashboard'))
    if request.method=='POST':
        available=1 if request.form.get('available')=='1' else 0; bg=request.form.get('blood_group'); loc=request.form.get('location','').strip(); c=db(); c.execute('UPDATE users SET available=?,blood_group=?,location=? WHERE id=?',(available,bg,loc,session['user_id'])); c.commit(); c.close(); session['blood_group']=bg; session['location']=loc; audit(session['username'],'UPDATE_DONOR_PROFILE',f'available={available}'); flash('Profile updated.')
    c=db(); u=c.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone(); c.close(); content=render_template_string("""<h1 class='title'>Donor Profile</h1><p class='subtitle'>Keep your availability current so the decision engine can use you as a fallback.</p><div class='card'><form method='post'><div class='form-grid'><div class='field'><label>Name</label><input value='{{u.name}}' disabled></div><div class='field'><label>Username</label><input value='{{u.username}}' disabled></div><div class='field'><label>Blood group</label><select name='blood_group'>{% for g in groups %}<option {% if g==u.blood_group %}selected{% endif %}>{{g}}</option>{% endfor %}</select></div><div class='field'><label>Location</label><input name='location' value='{{u.location}}' required></div><div class='field'><label>Available for emergency</label><select name='available'><option value='1' {% if u.available %}selected{% endif %}>ON</option><option value='0' {% if not u.available %}selected{% endif %}>OFF</option></select></div></div><br><button class='btn'>Save profile</button></form></div>""",u=u,groups=BLOOD_GROUPS); return render_page(content,'Donor Profile')

@app.route('/donor/requests')
def donor_requests():
    if not role_required('donor'): return redirect(url_for('dashboard'))
    c=db(); u=c.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone(); rows=c.execute('SELECT * FROM requests WHERE status IN ("OPEN","ALLOCATED") AND blood_group=? ORDER BY id DESC',(u['blood_group'],)).fetchall(); c.close(); content=render_template_string("""<h1 class='title'>Emergency Requests</h1><p class='subtitle'>Compatible open requests matching your blood group.</p><div class='card'><div class='table-wrap'><table class='table'><tr><th>Request</th><th>Hospital</th><th>Location</th><th>Blood</th><th>Units</th><th>Urgency</th></tr>{% for r in rows %}<tr><td>#{{r.id}}</td><td>{{r.hospital}}</td><td>{{r.location}}</td><td>{{r.blood_group}}</td><td>{{r.units_required}}</td><td>{{r.urgency}}</td></tr>{% else %}<tr><td colspan='6'>No matching open emergencies.</td></tr>{% endfor %}</table></div></div>""",rows=rows); return render_page(content,'Donor Requests')

@app.route('/admin/users')
def admin_users():
    if not role_required('admin'): return redirect(url_for('dashboard'))
    c=db(); users=c.execute('SELECT * FROM users ORDER BY id DESC').fetchall(); c.close(); content=render_template_string("""<h1 class='title'>Users</h1><p class='subtitle'>Admin view of all registered roles and verification state.</p><div class='card'><div class='table-wrap'><table class='table'><tr><th>ID</th><th>Name</th><th>Username</th><th>Role</th><th>Location</th><th>Blood</th><th>Verified</th><th>Available</th><th>Action</th></tr>{% for u in users %}<tr><td>{{u.id}}</td><td>{{u.name}}</td><td>{{u.username}}</td><td>{{u.role}}</td><td>{{u.location}}</td><td>{{u.blood_group or '-'}}</td><td>{{'YES' if u.verified else 'PENDING'}}</td><td>{{'ON' if u.available else 'OFF'}}</td><td>{% if u.id != session.get('user_id') %}<form method='post' action='{{url_for("admin_delete_user",user_id=u.id)}}' onsubmit="return confirm('Delete this account? Historical emergency requests will be preserved.')"><button class='btn danger' style='padding:7px 10px;font-size:11px'>Delete</button></form>{% else %}<span class='small'>Current admin</span>{% endif %}</td></tr>{% endfor %}</table></div></div>""",users=users); return render_page(content,'Users')

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if not role_required('admin'): return redirect(url_for('dashboard'))
    if user_id == session.get('user_id'):
        flash('You cannot delete your own administrator account while logged in.'); return redirect(url_for('admin_users'))
    c=db(); user=c.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
    if not user: c.close(); flash('User not found.'); return redirect(url_for('admin_users'))
    c.execute('UPDATE requests SET user_id=? WHERE user_id=?',(session.get('user_id'),user_id))
    c.execute('DELETE FROM users WHERE id=?',(user_id,)); c.commit(); c.close()
    audit(session['username'],'DELETE_USER',f'user={user["username"]};role={user["role"]}')
    flash(f'Account {user["username"]} deleted. Historical requests were preserved.')
    return redirect(url_for('admin_users'))

@app.route('/admin/audit')
def admin_audit():
    if not role_required('admin'): return redirect(url_for('dashboard'))
    c=db(); rows=c.execute('SELECT * FROM audit_logs ORDER BY id DESC LIMIT 200').fetchall(); c.close(); content=render_template_string("""<h1 class='title'>Audit Logs</h1><p class='subtitle'>Traceable actions for emergency coordination.</p><div class='card'><div class='table-wrap'><table class='table'><tr><th>Time</th><th>Actor</th><th>Action</th><th>Details</th></tr>{% for r in rows %}<tr><td>{{r.created_at[:19]}}</td><td>{{r.actor}}</td><td>{{r.action}}</td><td>{{r.details}}</td></tr>{% endfor %}</table></div></div>""",rows=rows); return render_page(content,'Audit Logs')

@app.route('/health')
def health():
    c=db(); users=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]; banks=c.execute('SELECT COUNT(*) FROM blood_banks').fetchone()[0]; reqs=c.execute('SELECT COUNT(*) FROM requests').fetchone()[0]; c.close(); content=render_template_string("""<h1 class='title'>System Status</h1><p class='subtitle'>Local demo health and persistence status.</p><div class='grid'><div class='card'><div class='label'>Flask backend</div><div class='metric'>ONLINE</div></div><div class='card'><div class='label'>SQLite database</div><div class='metric'>ONLINE</div></div><div class='card'><div class='label'>GIS</div><div class='metric'>READY</div></div><div class='card'><div class='label'>Users</div><div class='metric'>{{users}}</div></div></div><br><div class='card'><h3>Persistence</h3><p>Database file: <b>bloodbridge.db</b></p><p class='small'>The database is created automatically in the same folder as app.py and survives server restarts.</p></div>""",users=users,banks=banks,reqs=reqs); return render_page(content,'System Status')

@app.errorhandler(404)
def not_found(e): return redirect(url_for('dashboard')) if logged() else redirect(url_for('login'))

@app.errorhandler(500)
def server_error(e):
    return render_template_string('<style>'+BASE_CSS+'</style><div class="login-page"><div class="login-box"><div class="brand">Blood<span>Bridge</span></div><h2>Something went wrong</h2><p class="subtitle">BloodBridge could not complete that action. Your saved database has not been deleted.</p><a class="btn" href="/">Return to BloodBridge</a></div></div>'),500

@app.route('/api/status')
def api_status():
    c=db(); out={'users':c.execute('SELECT COUNT(*) FROM users').fetchone()[0],'blood_banks':c.execute('SELECT COUNT(*) FROM blood_banks').fetchone()[0],'requests':c.execute('SELECT COUNT(*) FROM requests').fetchone()[0]}; c.close(); return jsonify(out)

def notify_user(user_id,title,message,kind='info'):
    try:
        c=db(); c.execute('INSERT INTO notifications(user_id,title,message,kind,read,created_at) VALUES(?,?,?,?,0,?)',(user_id,title,message,kind,now_iso())); c.commit(); c.close()
    except Exception:
        pass

def notify_role(role,title,message,kind='info'):
    try:
        c=db(); ids=c.execute('SELECT id FROM users WHERE role=?',(role,)).fetchall();
        for x in ids: c.execute('INSERT INTO notifications(user_id,title,message,kind,read,created_at) VALUES(?,?,?,?,0,?)',(x['id'],title,message,kind,now_iso()))
        c.commit(); c.close()
    except Exception:
        pass

@app.route('/api/location',methods=['POST'])
def api_location():
    if not logged(): return jsonify({'ok':False}),401
    data=request.get_json(silent=True) or {}
    try: lat=float(data.get('latitude')); lng=float(data.get('longitude'))
    except (TypeError,ValueError): return jsonify({'ok':False,'error':'invalid coordinates'}),400
    if not (-90<=lat<=90 and -180<=lng<=180): return jsonify({'ok':False,'error':'invalid coordinates'}),400
    accuracy=data.get('accuracy');
    try: accuracy=float(accuracy) if accuracy is not None else None
    except (TypeError,ValueError): accuracy=None
    c=db(); c.execute('UPDATE users SET latitude=?,longitude=?,gps_accuracy=?,gps_updated_at=? WHERE id=?',(lat,lng,accuracy,now_iso(),session['user_id'])); c.commit(); c.close()
    return jsonify({'ok':True,'latitude':lat,'longitude':lng,'accuracy':accuracy})

@app.route('/api/notifications')
def api_notifications():
    if not logged(): return jsonify({'unread':0,'items':[]}),401
    c=db(); rows=c.execute('SELECT id,title,message,kind,created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 20',(session['user_id'],)).fetchall(); unread=c.execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0',(session['user_id'],)).fetchone()[0]; c.close()
    return jsonify({'unread':unread,'items':[dict(x) for x in rows]})

@app.route('/api/notifications/read',methods=['POST'])
def api_notifications_read():
    if not logged(): return jsonify({'ok':False}),401
    c=db(); c.execute('UPDATE notifications SET read=1 WHERE user_id=?',(session['user_id'],)); c.commit(); c.close(); return jsonify({'ok':True})

@app.route('/manifest.webmanifest')
def manifest():
    return jsonify({'name':'BloodBridge Emergency Coordination','short_name':'BloodBridge','start_url':'/dashboard','display':'standalone','background_color':'#f7f7f9','theme_color':'#c51f45','description':'Emergency blood coordination with live GPS and notifications.','icons':[{'src':'/icon-192.png','sizes':'192x192','type':'image/png'},{'src':'/icon-512.png','sizes':'512x512','type':'image/png'}]})

def png_icon(size):
    # simple generated PNG icon: white background with red cross
    raw=[]
    for y in range(size):
        row=bytearray([0]);
        for x in range(size):
            red=(size//3<=x<2*size//3) or (size//3<=y<2*size//3)
            row.extend((197,31,69,255) if red else (255,255,255,255))
        raw.append(bytes(row))
    raw=b''.join(raw)
    def chunk(t,d):
        return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw,9))+chunk(b'IEND',b'')

@app.route('/icon-192.png')
def icon192(): return app.response_class(png_icon(192),mimetype='image/png')
@app.route('/icon-512.png')
def icon512(): return app.response_class(png_icon(512),mimetype='image/png')

@app.route('/sw.js')
def service_worker():
    js="""const CACHE='bloodbridge-v2';self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/login','/manifest.webmanifest']))));self.addEventListener('fetch',e=>{if(e.request.method==='GET')e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));});"""
    return app.response_class(js,mimetype='application/javascript')

init_db()

if __name__=='__main__':
    print(f'BloodBridge database: {DB_PATH}')
    print('Demo accounts: emergency/1234, bloodbank/1234, donor/1234, admin/1234')
    https_mode=os.environ.get('BLOODBRIDGE_HTTPS','0')=='1'
    port=int(os.environ.get('PORT','5443' if https_mode else '5000'))
    if https_mode:
        print(f'Mobile GPS/PWA mode: https://YOUR-PC-IP:{port} (accept the local certificate once)')
        app.run(host='0.0.0.0',port=port,debug=True,ssl_context='adhoc')
    else:
        print('PC/browser mode: http://127.0.0.1:5000')
        print('For phone GPS + install, set BLOODBRIDGE_HTTPS=1 and run again.')
        app.run(host='0.0.0.0',port=port,debug=True)
