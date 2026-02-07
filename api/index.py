from flask import Flask, send_file, make_response, request, jsonify
from fpdf import FPDF
import random, string, io, time

app = Flask(__name__)

# --- THE HARD CAP CONFIG ---
USER_HISTORY = {}
MAX_PDFS = 20
WINDOW_SECONDS = 86400  # Exactly 24 Hours

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
        :root { --bg: #f8fafc; --primary: #0f172a; --accent: #22c55e; --muted: #94a3b8; }
        body { margin: 0; font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg); display: flex; flex-direction: column; align-items: center; min-height: 100vh; color: var(--primary); background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 32px 32px; }
        
        .nav { width: 100%; max-width: 1100px; padding: 40px 20px; box-sizing: border-box; display: flex; justify-content: space-between; align-items: center; }
        .logo { display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 15px; text-decoration: none; color: inherit; }
        .dot { width: 8px; height: 8px; background: var(--accent); border-radius: 50%; }

        .container { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; max-width: 500px; padding: 0 20px; box-sizing: border-box; text-align: center; }
        h1 { font-size: 42px; font-weight: 800; letter-spacing: -2px; margin: 0 0 16px 0; line-height: 1; }
        p { color: #64748b; font-size: 16px; line-height: 1.6; margin-bottom: 40px; }
        
        .btn { background: var(--primary); color: white; border: none; padding: 22px; width: 100%; border-radius: 18px; font-weight: 700; font-size: 16px; cursor: pointer; transition: 0.2s; box-shadow: 0 10px 25px -5px rgba(15,23,42,0.2); }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 20px 35px -10px rgba(15,23,42,0.3); }

        .user-badge { display: none; background: #fff; padding: 8px 16px; border-radius: 30px; border: 1px solid #e2e8f0; font-size: 12px; font-weight: 700; margin-bottom: 20px; }

        .loader { margin-top: 40px; display: none; width: 100%; }
        .bar-bg { background: #f1f5f9; height: 10px; border-radius: 10px; overflow: hidden; margin-top: 15px; }
        .bar-fill { background: var(--primary); height: 100%; width: 0%; transition: width 0.3s linear; }
        
        .results { margin-top: 40px; display: none; width: 100%; }
        .file-link { display: flex; justify-content: space-between; padding: 20px; background: rgba(255,255,255,0.8); border: 1px solid #e2e8f0; border-radius: 16px; text-decoration: none; color: var(--primary); font-weight: 700; font-size: 14px; margin-bottom: 12px; }

        #limit-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15,23,42,0.9); z-index: 1000; backdrop-filter: blur(8px); align-items: center; justify-content: center; }
        .modal-card { background: white; padding: 40px; border-radius: 24px; max-width: 320px; text-align: center; }

        .support-box { margin-top: 80px; padding-top: 40px; border-top: 1px solid #f1f5f9; width: 100%; }
        .affiliate-card { background: rgba(255,255,255,0.8); border: 1px dashed #cbd5e1; border-radius: 20px; padding: 24px; text-align: left; display: flex; align-items: center; gap: 18px; text-decoration: none; color: inherit; transition: 0.2s; }
        
        footer { padding: 40px; color: #cbd5e1; font-size: 12px; font-family: 'JetBrains Mono'; opacity: 0.7; }
    </style>
</head>
<body>
    <div id="limit-modal">
        <div class="modal-card">
            <div style="font-size:40px; margin-bottom:20px;">🛡️</div>
            <h2 style="margin:0; font-weight:800; font-size:20px;">Daily Quota Exhausted</h2>
            <p style="font-size:14px; color:#64748b; margin:15px 0 25px;">
                You've reached the 20-file daily hard cap. Access resets in approximately <span id="time-left" style="font-weight:800; color:var(--primary);">--</span> minutes.
            </p>
            <button class="btn" onclick="location.reload()">Understood</button>
        </div>
    </div>

    <div class="nav">
        <a href="/" class="logo"><div class="dot"></div>PDFBIRCH.APP</a>
        <a href="https://www.buymeacoffee.com/YOUR_BMAC_USER" target="_blank" style="font-size: 13px; font-weight: 700; color: var(--muted); text-decoration: none;">☕ Support</a>
    </div>

    <div class="container">
        <div id="user-badge" class="user-badge"><span id="user-email"></span></div>
        <h1>Entropy Engine</h1>
        <p>Advanced dataset generation for privacy research. Secure, limited-access mode active.</p>
        
        <button class="btn" id="login-btn" onclick="signIn()">Enter Engine</button>

        <div id="engine-ui" style="display:none; width: 100%;">
            <button class="btn" id="start-btn" onclick="startEngine()">Initialize Batch</button>

            <div class="loader" id="loader">
                <div style="display:flex; justify-content:space-between; font-size:12px; font-family:'JetBrains Mono'; font-weight:700; color: #94a3b8;">
                    <span>Hashing...</span><span id="pct">0%</span>
                </div>
                <div class="bar-bg"><div class="bar-fill" id="fill"></div></div>
            </div>

            <div class="results" id="results">
                <a href="/api/download" class="file-link"><span>Research_Analysis_K7M2.pdf</span> <span>↓</span></a>
                <a href="/api/download" class="file-link"><span>Draft_Final_X8N4.pdf</span> <span>↓</span></a>
                <a href="/api/download" class="file-link"><span>Project_Report_B3L9.pdf</span> <span>↓</span></a>
                <a href="/api/download" class="file-link"><span>Case_Study_Thesis_A1C6.pdf</span> <span>↓</span></a>
                <a href="/api/download" class="file-link"><span>Final_Project_T5R8.pdf</span> <span>↓</span></a>
                <button class="btn" onclick="location.reload()" style="background:none; color:var(--primary); box-shadow:none; border:1px solid #e2e8f0; margin-top:20px;">Refresh Batch</button>
            </div>
        </div>

        <div class="support-box">
            <a href="https://www.grammarly.com/affiliates" target="_blank" class="affiliate-card">
                <div style="font-size: 24px;">🛡️</div>
                <div style="flex:1">
                    <div style="font-weight:800; font-size:15px;">Verify Your Content</div>
                    <div style="font-size:13px; color:#94a3b8;">Use Grammarly to check your academic documents.</div>
                </div>
                <div>→</div>
            </a>
        </div>
    </div>

    <footer>&copy; 2026 Pdfbirch &bull; 24h Security Window Active</footer>

    <script>
        // --- YOUR ACTUAL FIREBASE CONFIG ---
        const firebaseConfig = {
            apiKey: "AIzaSyBZ_LmqF-RHh3RxCl39XhRfCm_mu7k-diQ",
            authDomain: "pdfbirch.firebaseapp.com",
            projectId: "pdfbirch",
            storageBucket: "pdfbirch.firebasestorage.app",
            messagingSenderId: "701712083387",
            appId: "1:701712083387:web:f438920e98b9831ea63c9e",
            measurementId: "G-RTZELQLMMZ"
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
                document.getElementById('time-left').innerText = data.wait_time;
                document.getElementById('limit-modal').style.display = 'flex';
                return;
            }

            document.getElementById('start-btn').style.display='none';
            document.getElementById('loader').style.display='block';
            let w=0; const f=document.getElementById('fill'), p=document.getElementById('pct');
            const t=setInterval(()=>{
                w++; f.style.width=w+'%'; p.innerText=w+'%';
                if(w>=100){ clearInterval(t); document.getElementById('loader').style.display='none'; document.getElementById('results').style.display='block'; }
            }, 600);
        }
    </script>
</body>
</html>
"""

# --- 2. THE BACKEND ---
PREFIXES = ["Research", "Analysis", "Draft", "Final", "Project", "Report", "Case_Study", "Thesis"]
WORDS = ["strategy", "growth", "market", "value", "user", "product", "system", "data", "cloud", "AI", "project", "scale"]

@app.route('/')
def home(): return HTML_PAGE

@app.route('/api/check_limit')
def check_limit():
    email = request.args.get('email')
    if not email: return jsonify({"allowed": False})
    now = time.time()
    if email not in USER_HISTORY: USER_HISTORY[email] = []
    USER_HISTORY[email] = [t for t in USER_HISTORY[email] if now - t < WINDOW_SECONDS]
    if len(USER_HISTORY[email]) >= MAX_PDFS:
        oldest = USER_HISTORY[email][0]
        wait_m = int(((oldest + WINDOW_SECONDS) - now) // 60) + 1
        return jsonify({"allowed": False, "wait_time": wait_m})
    USER_HISTORY[email].append(now)
    return jsonify({"allowed": True})

@app.route('/api/download')
def download():
    buf = gen_pdf_content(); buf.seek(0)
    name = f"{random.choice(PREFIXES)}_{''.join(random.choices(string.ascii_uppercase, k=4))}.pdf"
    return make_response(send_file(buf, as_attachment=True, download_name=name, mimetype='application/pdf'))

def gen_pdf_content():
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    for _ in range(10):
        pdf.add_page()
        pdf.set_font('Arial', '', 12)
        for _ in range(25):
            line = " ".join(random.choice(WORDS) for _ in range(random.randint(10,20))).capitalize() + "."
            pdf.multi_cell(0, 10, line)
            pdf.set_text_color(255,255,255); pdf.set_font('Arial','',6)
            pdf.cell(0,5,''.join(random.choices(string.ascii_letters, k=15)), ln=1)
            pdf.set_text_color(0,0,0); pdf.set_font('Arial','',12)
    return io.BytesIO(pdf.output(dest='S').encode('latin-1'))

app.debug = True
