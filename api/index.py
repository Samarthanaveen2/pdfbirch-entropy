from flask import Flask, send_file, make_response, request, jsonify
from fpdf import FPDF
import random, string, io, time

app = Flask(__name__)

# --- RATE LIMITER CONFIG (In-Memory for Hobby Tier) ---
# Format: { "email@gmail.com": [timestamp1, timestamp2, ...] }
USER_HISTORY = {}
MAX_PDFS = 20
WINDOW_SECONDS = 18000  # 5 Hours

# --- 1. THE FRONTEND ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pdfbirch | Privacy Engine</title>
    
    <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-auth-compat.js"></script>

    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #f8fafc; --primary: #0f172a; --accent: #22c55e; --muted: #94a3b8; --error: #ef4444; }
        body { margin: 0; font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg); display: flex; flex-direction: column; align-items: center; min-height: 100vh; color: var(--primary); background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 32px 32px; }
        
        .nav { width: 100%; max-width: 1100px; padding: 40px 20px; box-sizing: border-box; display: flex; justify-content: space-between; align-items: center; }
        .logo { display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 15px; text-decoration: none; color: inherit; }
        .dot { width: 8px; height: 8px; background: var(--accent); border-radius: 50%; }

        .container { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; max-width: 500px; padding: 0 20px; box-sizing: border-box; text-align: center; }
        h1 { font-size: 36px; font-weight: 800; letter-spacing: -2px; margin: 0 0 16px 0; line-height: 1; }
        p { color: #64748b; font-size: 16px; line-height: 1.6; margin-bottom: 40px; }
        
        .btn { background: var(--primary); color: white; border: none; padding: 22px; width: 100%; border-radius: 18px; font-weight: 700; font-size: 16px; cursor: pointer; transition: 0.2s; box-shadow: 0 10px 25px -5px rgba(15,23,42,0.2); }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 20px 35px -10px rgba(15,23,42,0.3); }
        .btn:disabled { background: #cbd5e1; cursor: not-allowed; transform: none; box-shadow: none; }

        .user-badge { display: none; background: #fff; padding: 8px 16px; border-radius: 30px; border: 1px solid #e2e8f0; font-size: 12px; font-weight: 700; margin-bottom: 20px; align-items: center; gap: 8px; }

        .loader { margin-top: 40px; display: none; width: 100%; }
        .bar-bg { background: #f1f5f9; height: 10px; border-radius: 10px; overflow: hidden; margin-top: 15px; }
        .bar-fill { background: var(--primary); height: 100%; width: 0%; transition: width 0.3s linear; }
        
        .results { margin-top: 40px; display: none; width: 100%; }
        .file-link { display: flex; justify-content: space-between; padding: 20px; background: rgba(255,255,255,0.8); border: 1px solid #e2e8f0; border-radius: 16px; text-decoration: none; color: var(--primary); font-weight: 700; font-size: 14px; margin-bottom: 12px; transition: 0.2s; }
        .file-link:hover { border-color: var(--primary); background: #fff; transform: scale(1.02); }
        
        .error-msg { display: none; margin-top: 20px; color: var(--error); font-size: 13px; font-weight: 700; font-family: 'JetBrains Mono'; }

        .support-box { margin-top: 80px; padding-top: 40px; border-top: 1px solid #f1f5f9; width: 100%; }
        .affiliate-card { background: rgba(255,255,255,0.8); border: 1px dashed #cbd5e1; border-radius: 20px; padding: 24px; text-align: left; display: flex; align-items: center; gap: 18px; text-decoration: none; color: inherit; transition: 0.2s; }
        .affiliate-card:hover { border-style: solid; border-color: var(--primary); background: #fff; transform: translateY(-3px); }
        
        footer { padding: 40px; color: #cbd5e1; font-size: 12px; font-family: 'JetBrains Mono'; opacity: 0.7; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/" class="logo"><div class="dot"></div>PDFBIRCH.APP</a>
        <a href="https://www.buymeacoffee.com/YOUR_USER" target="_blank" style="font-size: 14px; font-weight: 700; color: var(--muted); text-decoration: none;">☕ Support</a>
    </div>

    <div class="container">
        <div id="user-badge" class="user-badge"><span id="user-email"></span></div>
        <h1>Entropy Engine</h1>
        <p>A high-variance dataset generator for privacy testing. <b>20 files per 5 hours.</b></p>
        
        <button class="btn" id="login-btn" onclick="signIn()">Sign in with Google to Start</button>

        <div id="engine-ui" style="display:none; width: 100%;">
            <button class="btn" id="start-btn" onclick="startEngine()">Initialize Engine</button>
            <div id="limit-error" class="error-msg">⚠️ QUOTA EXCEEDED: Try again in 5 hours.</div>

            <div class="loader" id="loader">
                <div style="display:flex; justify-content:space-between; font-size:12px; font-family:'JetBrains Mono'; font-weight:700; color: #94a3b8;">
                    <span>Randomizing...</span><span id="pct">0%</span>
                </div>
                <div class="bar-bg"><div class="bar-fill" id="fill"></div></div>
            </div>

            <div class="results" id="results">
                <a href="/api/download" class="file-link"><span>Research_Analysis_K7M2.pdf</span> <span>↓</span></a>
                <a href="/api/download" class="file-link"><span>Draft_Final_X8N4.pdf</span> <span>↓</span></a>
                <button class="btn" onclick="location.reload()" style="background:none; color:var(--primary); box-shadow:none; border:1px solid #e2e8f0; margin-top:20px;">Reset Engine</button>
            </div>
        </div>

        <div class="support-box">
            <a href="YOUR_LINK" target="_blank" class="affiliate-card">
                <div style="font-size: 24px;">🛡️</div>
                <div style="flex:1">
                    <div style="font-weight:800; font-size:15px;">Secure Your Work</div>
                    <div style="font-size:13px; color:#94a3b8;">Protect your downloads with NordVPN.</div>
                </div>
                <div style="font-size:20px; color:#94a3b8;">→</div>
            </a>
        </div>
    </div>

    <footer>&copy; 2026 Pdfbirch &bull; Secure Academic Mode</footer>

    <script>
        // --- FIREBASE CONFIG (REPLACE WITH YOURS) ---
        const firebaseConfig = {
            apiKey: "AIzaSy...",
            authDomain: "your-app.firebaseapp.com",
            projectId: "your-app",
            storageBucket: "your-app.appspot.com",
            messagingSenderId: "12345",
            appId: "1:12345:web:6789"
        };
        firebase.initializeApp(firebaseConfig);
        const auth = firebase.auth();

        function signIn() {
            const provider = new firebase.auth.GoogleAuthProvider();
            auth.signInWithPopup(provider).catch(e => console.error(e));
        }

        auth.onAuthStateChanged(user => {
            if (user) {
                document.getElementById('login-btn').style.display = 'none';
                document.getElementById('engine-ui').style.display = 'block';
                document.getElementById('user-badge').style.display = 'inline-flex';
                document.getElementById('user-email').innerText = user.email;
            }
        });

        async function startEngine() {
            const user = auth.currentUser;
            if (!user) return;

            const res = await fetch(`/api/check_limit?email=${user.email}`);
            const data = await res.json();

            if (!data.allowed) {
                document.getElementById('limit-error').style.display = 'block';
                document.getElementById('start-btn').disabled = true;
                return;
            }

            document.getElementById('start-btn').style.display='none';
            document.getElementById('loader').style.display='block';
            let w=0; const f=document.getElementById('fill'), p=document.getElementById('pct');
            const t=setInterval(()=>{
                w++; f.style.width=w+'%'; p.innerText=w+'%';
                if(w>=100){ clearInterval(t); document.getElementById('loader').style.display='none'; document.getElementById('results').style.display='block'; }
            }, 30);
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home(): return HTML_PAGE

@app.route('/api/check_limit')
def check_limit():
    email = request.args.get('email')
    if not email: return jsonify({"allowed": False})
    
    now = time.time()
    if email not in USER_HISTORY:
        USER_HISTORY[email] = []
    
    # Clean out requests older than 5 hours
    USER_HISTORY[email] = [t for t in USER_HISTORY[email] if now - t < WINDOW_SECONDS]
    
    if len(USER_HISTORY[email]) >= MAX_PDFS:
        return jsonify({"allowed": False})
    
    USER_HISTORY[email].append(now)
    return jsonify({"allowed": True})

@app.route('/api/download')
def download():
    # Keep your existing gen_pdf logic here
    buf = gen_pdf_content(); buf.seek(0)
    name = f"{random.choice(PREFIXES)}_{random.choice(PREFIXES)}_{''.join(random.choices(string.ascii_uppercase+string.digits, k=4))}.pdf"
    return make_response(send_file(buf, as_attachment=True, download_name=name, mimetype='application/pdf'))

def gen_pdf_content():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)
    # ... (Your existing loop for lines and noise) ...
    return io.BytesIO(pdf.output(dest='S').encode('latin-1'))

app.debug = True















# from flask import Flask, send_file, make_response
# from fpdf import FPDF
# import random, string, io

# app = Flask(__name__)

# # --- 1. THE FRONTEND (Premium Minimalist UI) ---
# HTML_PAGE = """
# <!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <meta name="viewport" content="width=device-width, initial-scale=1.0">
#     <title>Pdfbirch | Privacy Engine</title>
#     <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
#     <style>
#         :root { --bg: #f8fafc; --primary: #0f172a; --accent: #22c55e; --muted: #94a3b8; }
#         body { margin: 0; font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg); display: flex; flex-direction: column; align-items: center; min-height: 100vh; color: var(--primary); background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 32px 32px; }
        
#         .nav { width: 100%; max-width: 1100px; padding: 40px 20px; box-sizing: border-box; display: flex; justify-content: space-between; align-items: center; }
#         .logo { display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 15px; text-decoration: none; color: inherit; margin-left: 20px; }
#         .dot { width: 8px; height: 8px; background: var(--accent); border-radius: 50%; }

#         .container { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; max-width: 500px; padding: 0 20px; box-sizing: border-box; text-align: center; }
#         h1 { font-size: 36px; font-weight: 800; letter-spacing: -2px; margin: 0 0 16px 0; line-height: 1; }
#         p { color: #64748b; font-size: 16px; line-height: 1.6; margin-bottom: 40px; }
        
#         .btn { background: var(--primary); color: white; border: none; padding: 22px; width: 100%; border-radius: 18px; font-weight: 700; font-size: 16px; cursor: pointer; transition: 0.2s; box-shadow: 0 10px 25px -5px rgba(15,23,42,0.2); }
#         .btn:hover { transform: translateY(-2px); box-shadow: 0 20px 35px -10px rgba(15,23,42,0.3); }

#         .loader { margin-top: 40px; display: none; width: 100%; }
#         .bar-bg { background: #f1f5f9; height: 10px; border-radius: 10px; overflow: hidden; margin-top: 15px; }
#         .bar-fill { background: var(--primary); height: 100%; width: 0%; transition: width 0.3s linear; }
        
#         .results { margin-top: 40px; display: none; width: 100%; }
#         .file-link { display: flex; justify-content: space-between; padding: 20px; background: rgba(255,255,255,0.8); border: 1px solid #e2e8f0; border-radius: 16px; text-decoration: none; color: var(--primary); font-weight: 700; font-size: 14px; margin-bottom: 12px; transition: 0.2s; }
#         .file-link:hover { border-color: var(--primary); background: #fff; transform: scale(1.02); }
        
#         .support-box { margin-top: 80px; padding-top: 40px; border-top: 1px solid #f1f5f9; width: 100%; }
#         .affiliate-card { background: rgba(255,255,255,0.8); border: 1px dashed #cbd5e1; border-radius: 20px; padding: 24px; text-align: left; display: flex; align-items: center; gap: 18px; text-decoration: none; color: inherit; transition: 0.2s; }
#         .affiliate-card:hover { border-style: solid; border-color: var(--primary); background: #fff; transform: translateY(-3px); }
#         .affiliate-icon { width: 44px; height: 44px; background: #fff; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        
#         .donation-btn { display: inline-flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 700; color: #94a3b8; text-decoration: none; transition: 0.2s; padding: 10px 15px; border-radius: 10px; }
#         .donation-btn:hover { background: rgba(255,255,255,0.8); color: var(--primary); }

#         footer { padding: 40px; color: #cbd5e1; font-size: 12px; font-family: 'JetBrains Mono'; opacity: 0.7; }
#     </style>
# </head>
# <body>
#     <div class="nav">
#         <a href="/" class="logo"><div class="dot"></div>PDFBIRCH.APP</a>
#         <a href="https://www.buymeacoffee.com/YOUR_USER" target="_blank" class="donation-btn">☕ Support Project</a>
#     </div>

#     <div class="container">
#         <h1>Entropy Engine</h1>
#         <p>A high-variance dataset generator for privacy testing and pipeline validation.</p>
        
#         <button class="btn" id="start-btn" onclick="start()">Initialize Engine</button>

#         <div class="loader" id="loader">
#             <div style="display:flex; justify-content:space-between; font-size:12px; font-family:'JetBrains Mono'; font-weight:700; color: #94a3b8;">
#                 <span>Randomizing Vectors...</span><span id="pct">0%</span>
#             </div>
#             <div class="bar-bg"><div class="bar-fill" id="fill"></div></div>
#         </div>

#         <div class="results" id="results">
#             <a href="/api/download" class="file-link"><span>Research_Analysis_K7M2.pdf</span> <span>↓</span></a>
#             <a href="/api/download" class="file-link"><span>Draft_Final_X8N4.pdf</span> <span>↓</span></a>
#             <a href="/api/download" class="file-link"><span>Project_Report_B3L9.pdf</span> <span>↓</span></a>
#             <a href="/api/download" class="file-link"><span>Case_Study_Thesis_A1C6.pdf</span> <span>↓</span></a>
#             <a href="/api/download" class="file-link"><span>Final_Project_T5R8.pdf</span> <span>↓</span></a>
#             <button class="btn" onclick="location.reload()" style="background:none; color:var(--primary); box-shadow:none; border:1px solid #e2e8f0; margin-top:20px;">Generate New Batch</button>
#         </div>

#         <div class="support-box">
#             <div style="font-family:'JetBrains Mono'; font-size:11px; color:#cbd5e1; text-transform:uppercase; letter-spacing:2px; margin-bottom:15px; text-align:left; opacity:0.8;">Verified Resources</div>
#             <a href="YOUR_LINK" target="_blank" class="affiliate-card">
#                 <div class="affiliate-icon">🛡️</div>
#                 <div style="flex:1">
#                     <div style="font-weight:800; font-size:15px;">Secure Your Work</div>
#                     <div style="font-size:13px; color:#94a3b8;">Protect your downloads with NordVPN.</div>
#                 </div>
#                 <div style="font-size:20px; color:#94a3b8;">→</div>
#             </a>
#         </div>
#     </div>

#     <footer>&copy; 2026 Pdfbirch &bull; Privacy Validation System</footer>

#     <script>
#         function start() {
#             document.getElementById('start-btn').style.display='none';
#             document.getElementById('loader').style.display='block';
#             let w=0; const f=document.getElementById('fill'), p=document.getElementById('pct');
#             const t=setInterval(()=>{
#                 w++; f.style.width=w+'%'; p.innerText=w+'%';
#                 if(w>=100){ clearInterval(t); document.getElementById('loader').style.display='none'; document.getElementById('results').style.display='block'; }
#             }, 30);
#         }
#     </script>
# </body>
# </html>
# """

# # --- 2. THE BACKEND (Naming & Formatting) ---
# PREFIXES = ["Research", "Analysis", "Draft", "Final", "Project", "Report", "Case_Study", "Thesis"]
# WORDS = ["strategy", "growth", "market", "value", "user", "product", "system", "data", "cloud", "AI", "project", "scale"]

# def gen_pdf():
#     pdf = FPDF()
#     pdf.set_auto_page_break(auto=True, margin=15)
#     for _ in range(10):
#         pdf.add_page()
#         pdf.set_font('Arial', '', 12)
#         for _ in range(25):
#             line = " ".join(random.choice(WORDS) for _ in range(random.randint(10,20))).capitalize() + "."
#             pdf.multi_cell(0, 10, line)
#             # Metadata Noise
#             pdf.set_text_color(255,255,255); pdf.set_font('Arial','',6)
#             pdf.cell(0,5,''.join(random.choices(string.ascii_letters, k=15)), ln=1)
#             pdf.set_text_color(0,0,0); pdf.set_font('Arial','',12)
#     return io.BytesIO(pdf.output(dest='S').encode('latin-1'))

# @app.route('/')
# def home(): return HTML_PAGE

# @app.route('/api/download')
# def download():
#     buf = gen_pdf(); buf.seek(0)
#     name = f"{random.choice(PREFIXES)}_{random.choice(PREFIXES)}_{''.join(random.choices(string.ascii_uppercase+string.digits, k=4))}.pdf"
#     return make_response(send_file(buf, as_attachment=True, download_name=name, mimetype='application/pdf'))

# # Critical for Vercel
# app.debug = True
