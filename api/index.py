from flask import Flask, send_file, make_response, request, jsonify
from fpdf import FPDF
import random, string, io, time
import os
import json
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

app = Flask(__name__)

# Initialize Firebase Admin
service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT')
if service_account_json:
    cred_dict = json.loads(service_account_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')

def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    """Initialize database table if it doesn't exist"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS user_downloads (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                download_time TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_email ON user_downloads(email)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_download_time ON user_downloads(download_time)')
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Database init error: {e}")

# Initialize database on startup
init_db()

# Config
MAX_PDFS = 20
WINDOW_HOURS = 24

def verify_firebase_token(token):
    """Verify Firebase ID token and return email if valid"""
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        return decoded_token.get('email')
    except:
        return None

def get_user_download_count(email):
    """Get number of downloads in the last 24 hours"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cutoff_time = datetime.now() - timedelta(hours=WINDOW_HOURS)
        cur.execute(
            'SELECT COUNT(*) FROM user_downloads WHERE email = %s AND download_time > %s',
            (email, cutoff_time)
        )
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count
    except Exception as e:
        print(f"Database error: {e}")
        return 0

def record_download(email):
    """Record a download for the user"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO user_downloads (email, download_time) VALUES (%s, %s)',
            (email, datetime.now())
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Database error: {e}")
        return False

def get_time_until_reset(email):
    """Get minutes until oldest download expires"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cutoff_time = datetime.now() - timedelta(hours=WINDOW_HOURS)
        cur.execute(
            'SELECT download_time FROM user_downloads WHERE email = %s AND download_time > %s ORDER BY download_time ASC LIMIT 1',
            (email, cutoff_time)
        )
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result:
            oldest = result[0]
            reset_time = oldest + timedelta(hours=WINDOW_HOURS)
            minutes = int((reset_time - datetime.now()).total_seconds() / 60) + 1
            return max(1, minutes)
        return 0
    except Exception as e:
        print(f"Database error: {e}")
        return 0

# --- THE FRONTEND ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Free PDF Generator - Random Test Documents | Pdfbirch</title>
    <meta name="description" content="Generate random PDFs instantly. Free online PDF maker with realistic content & varied fonts. Perfect for testing, development, placeholder documents. No signup for preview, 20 free daily with Google login.">
    <meta name="keywords" content="pdf generator, random pdf, test documents, fake pdf, pdf maker, document generator, placeholder pdf, development tools">
    <meta name="author" content="Pdfbirch">
    <meta name="robots" content="index, follow">
    <meta name="language" content="English">
    <link rel="canonical" href="https://pdfbirch.app">
    
    <meta property="og:title" content="Free Random PDF Generator - Pdfbirch">
    <meta property="og:description" content="Generate realistic test PDFs with varied fonts and content. Free online document generator for developers.">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://pdfbirch.app">
    <meta property="og:site_name" content="Pdfbirch">
    
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Free Random PDF Generator - Pdfbirch">
    <meta name="twitter:description" content="Generate realistic test PDFs instantly. Perfect for testing and development.">

    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebApplication",
      "name": "Pdfbirch - Random PDF Generator",
      "description": "Generate random test PDFs for development and QA testing",
      "url": "https://pdfbirch.app",
      "applicationCategory": "DeveloperApplication",
      "operatingSystem": "Any",
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "USD"
      },
      "featureList": "Random PDF generation, Varied fonts, Test document creation, Batch generation"
    }
    </script>

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
        h1 { font-size: 42px; font-weight: 800; letter-spacing: -1px; margin: 0 0 16px 0; line-height: 1.2; word-spacing: 0.15em; }
        h2 { font-size: 18px; font-weight: 600; color: #64748b; margin: 0 0 12px 0; }
        p { color: #64748b; font-size: 16px; line-height: 1.6; margin-bottom: 40px; }
        
        .btn { background: var(--primary); color: white; border: none; padding: 22px; width: 100%; border-radius: 18px; font-weight: 700; font-size: 16px; cursor: pointer; transition: 0.2s; box-shadow: 0 10px 25px -5px rgba(15,23,42,0.2); }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 20px 35px -10px rgba(15,23,42,0.3); }

        .user-badge { display: none; background: #fff; padding: 8px 16px; border-radius: 30px; border: 1px solid #e2e8f0; font-size: 12px; font-weight: 700; margin-bottom: 20px; }

        .loader { margin-top: 40px; display: none; width: 100%; }
        .bar-bg { background: #f1f5f9; height: 10px; border-radius: 10px; overflow: hidden; margin-top: 15px; }
        .bar-fill { background: var(--primary); height: 100%; width: 0%; transition: width 0.3s linear; }
        
        .results { margin-top: 40px; display: none; width: 100%; }
        .file-link { display: flex; justify-content: space-between; padding: 20px; background: rgba(255,255,255,0.8); border: 1px solid #e2e8f0; border-radius: 16px; color: var(--primary); font-weight: 700; font-size: 14px; margin-bottom: 12px; cursor: pointer; transition: 0.2s; }
        .file-link:hover { border-color: var(--primary); background: #fff; transform: scale(1.02); }

        #limit-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15,23,42,0.9); z-index: 1000; backdrop-filter: blur(8px); align-items: center; justify-content: center; }
        .modal-card { background: white; padding: 40px; border-radius: 24px; max-width: 320px; text-align: center; }
        
        #crypto-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15,23,42,0.9); z-index: 1000; backdrop-filter: blur(8px); align-items: center; justify-content: center; }
        .wallet-text { background: #f1f5f9; padding: 12px; border-radius: 8px; font-family: 'JetBrains Mono', monospace; font-size: 11px; word-break: break-all; margin: 20px 0; }

        .support-box { margin-top: 80px; padding-top: 40px; border-top: 1px solid #f1f5f9; width: 100%; }
        .affiliate-card { background: rgba(255,255,255,0.8); border: 1px dashed #cbd5e1; border-radius: 20px; padding: 24px; text-align: left; display: flex; align-items: center; gap: 18px; text-decoration: none; color: inherit; transition: 0.2s; }
        
        .features { margin-top: 60px; width: 100%; }
        .feature-grid { display: grid; grid-template-columns: 1fr; gap: 16px; margin-top: 24px; }
        .feature-item { background: rgba(255,255,255,0.6); padding: 20px; border-radius: 12px; text-align: left; border: 1px solid #e2e8f0; }
        .feature-item h3 { margin: 0 0 8px 0; font-size: 15px; font-weight: 700; }
        .feature-item p { margin: 0; font-size: 13px; color: #64748b; }
        
        footer { padding: 40px 20px; color: #cbd5e1; font-size: 12px; font-family: 'JetBrains Mono'; text-align: center; max-width: 600px; }
        
        @media (max-width: 768px) {
            h1 { font-size: 32px; }
        }
    </style>
</head>
<body>
    <div id="limit-modal">
        <div class="modal-card">
            <div style="font-size:40px; margin-bottom:20px;">🛡️</div>
            <h2 style="margin:0; font-weight:800; font-size:20px;">Daily Quota Exhausted</h2>
            <p style="font-size:14px; color:#64748b; margin:15px 0 25px;">
                You've reached the 20-file daily limit. Access resets in approximately <span id="time-left" style="font-weight:800; color:var(--primary);">--</span> minutes.
            </p>
            <button class="btn" onclick="location.reload()">Understood</button>
        </div>
    </div>

    <div id="crypto-modal">
        <div class="modal-card">
            <div style="font-size:40px; margin-bottom:20px;">◎</div>
            <h2 style="margin:0; font-weight:800; font-size:20px;">Support via Solana</h2>
            <p style="font-size:14px; color:#64748b; margin:15px 0 10px;">
                Send SOL or SPL tokens to:
            </p>
            <div class="wallet-text" id="wallet-address">7fD3Yz3QRJ98nSPjaWYqayhmF3zxa4zoWK8rLk1Mzz7J</div>
            <button class="btn" onclick="copyWalletAddress()" style="margin-bottom:10px;">Copy Address</button>
            <button class="btn" onclick="closeCryptoModal()" style="background:none; color:var(--primary); box-shadow:none; border:1px solid #e2e8f0;">Close</button>
        </div>
    </div>

    <div class="nav">
        <a href="/" class="logo"><div class="dot" role="img" aria-label="Pdfbirch logo"></div>PDFBIRCH.APP</a>
        <a href="javascript:void(0)" onclick="openCryptoModal()" style="font-size: 13px; font-weight: 700; color: var(--muted); text-decoration: none; cursor: pointer;">◎ Support</a>
    </div>

    <div class="container">
        <div id="user-badge" class="user-badge"><span id="user-email"></span></div>
        
        <h1>Free Random PDF Generator</h1>
        <h2>Generate Test Documents Instantly</h2>
        <p>Create realistic test PDFs with randomized fonts, styles, and content. Perfect for development, QA testing, and placeholder documents.</p>
        
        <button class="btn" id="login-btn" onclick="signIn()">Enter Engine</button>

        <div id="engine-ui" style="display:none; width: 100%;">
            <button class="btn" id="start-btn" onclick="startEngine()">Initialize Batch</button>

            <div class="loader" id="loader">
                <div style="display:flex; justify-content:space-between; font-size:12px; font-family:'JetBrains Mono'; font-weight:700; color: #94a3b8;">
                    <span>Hashing...</span><span id="pct">0%</span>
                </div>
                <div class="bar-bg"><div class="bar-fill" id="fill"></div></div>
            </div>

            <div class="results" id="results"></div>
        </div>

        <div class="features">
            <h2 style="text-align: center;">Why Use Pdfbirch?</h2>
            <div class="feature-grid">
                <div class="feature-item">
                    <h3>🎨 Varied Fonts & Styles</h3>
                    <p>Each PDF uses randomized fonts, sizes, and formatting for realistic test scenarios</p>
                </div>
                <div class="feature-item">
                    <h3>⚡ Instant Generation</h3>
                    <p>Generate multiple PDFs in seconds with a single click</p>
                </div>
                <div class="feature-item">
                    <h3>🔒 Privacy-First</h3>
                    <p>No data collection, no tracking. Your testing stays private</p>
                </div>
            </div>
        </div>

        <div class="support-box">
            <a href="https://www.grammarly.com/affiliates" target="_blank" class="affiliate-card">
                <div style="font-size: 24px;">✍️</div>
                <div style="flex:1">
                    <div style="font-weight:800; font-size:15px;">Polish Your Real Documents</div>
                    <div style="font-size:13px; color:#94a3b8;">Use Grammarly to check grammar and spelling in your actual work.</div>
                </div>
                <div>→</div>
            </a>
        </div>
    </div>

    <footer>
        <div style="margin-bottom:20px; line-height:1.8; opacity:0.8;">
            Free tool for developers and QA engineers. Generate random PDFs for testing pipelines, document parsers, and workflow automation.
        </div>
        <div style="opacity:0.6;">
            &copy; 2026 Pdfbirch &bull; For Testing & Development
        </div>
    </footer>

    <script>
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

        function openCryptoModal() {
            document.getElementById('crypto-modal').style.display = 'flex';
        }

        function closeCryptoModal() {
            document.getElementById('crypto-modal').style.display = 'none';
        }

        function copyWalletAddress() {
            const wallet = '7fD3Yz3QRJ98nSPjaWYqayhmF3zxa4zoWK8rLk1Mzz7J';
            navigator.clipboard.writeText(wallet).then(() => {
                alert('Wallet address copied to clipboard!');
            }).catch(() => {
                alert('Failed to copy. Please copy manually from the modal.');
            });
        }

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

            const token = await user.getIdToken();

            const res = await fetch('/api/check_limit', {
                headers: { 'Authorization': 'Bearer ' + token }
            });
            const data = await res.json();

            if (!data.allowed) {
                document.getElementById('time-left').innerText = data.wait_time || 'N/A';
                document.getElementById('limit-modal').style.display = 'flex';
                return;
            }

            document.getElementById('start-btn').style.display='none';
            document.getElementById('loader').style.display='block';
            let w=0; 
            const f=document.getElementById('fill'), p=document.getElementById('pct');
            const t=setInterval(()=>{
                w++; 
                f.style.width=w+'%'; 
                p.innerText=w+'%';
                if(w>=100){ 
                    clearInterval(t); 
                    document.getElementById('loader').style.display='none'; 
                    showResults(token);
                }
            }, 600);
        }

      async function downloadPDF(_, filename) {
    try {
        const user = auth.currentUser;
        if (!user) return;

        // ✅ FIX: always get a fresh Firebase token
        const token = await user.getIdToken(true);

        const res = await fetch('/api/download', {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/json'
            }
        });

        if (res.status === 429) {
            alert('Daily quota reached!');
            location.reload();
            return;
        }

        if (!res.ok) {
            alert('Download failed.');
            return;
        }

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    } catch (e) {
        console.error(e);
        alert('Download error');
    }
}


                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            } catch(e) {
                console.error(e);
                alert('Download error');
            }
        }

        function showResults(token) {
            const files = [
                'Research_Analysis_K7M2.pdf',
                'Draft_Final_X8N4.pdf',
                'Project_Report_B3L9.pdf',
                'Case_Study_Thesis_A1C6.pdf',
                'Final_Project_T5R8.pdf'
            ];

            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = files.map(f => 
                `<div class="file-link" onclick="downloadPDF('${token}', '${f}')"><span>${f}</span><span>↓</span></div>`
            ).join('') + 
            '<button class="btn" onclick="location.reload()" style="background:none; color:var(--primary); box-shadow:none; border:1px solid #e2e8f0; margin-top:20px;">Refresh Batch</button>';
            resultsDiv.style.display = 'block';
        }
    </script>
</body>
</html>
"""

# --- THE BACKEND ---
PREFIXES = ["Research", "Analysis", "Draft", "Final", "Project", "Report", "Case_Study", "Thesis"]
WORDS = ["strategy", "growth", "market", "value", "user", "product", "system", "data", "cloud", "AI", "project", "scale"]

@app.route('/')
def home(): 
    return HTML_PAGE

@app.route('/robots.txt')
def robots():
    return """User-agent: *
Allow: /
Sitemap: https://pdfbirch.app/sitemap.xml

User-agent: GPTBot
Disallow: /

User-agent: CCBot
Disallow: /""", 200, {'Content-Type': 'text/plain'}

@app.route('/sitemap.xml')
def sitemap():
    return """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://pdfbirch.app</loc>
    <lastmod>2026-02-07</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>""", 200, {'Content-Type': 'application/xml'}

@app.route('/api/check_limit')
def check_limit():
    """Check if user has quota left - DOES NOT increment counter"""
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"allowed": False, "error": "No token"}), 401
    
    email = verify_firebase_token(token.replace('Bearer ', ''))
    if not email:
        return jsonify({"allowed": False, "error": "Invalid token"}), 401
    
    count = get_user_download_count(email)
    
    if count >= MAX_PDFS:
        wait_time = get_time_until_reset(email)
        return jsonify({"allowed": False, "wait_time": wait_time})
    
    return jsonify({"allowed": True})

@app.route('/api/download', methods=['POST'])
def download():
    """Download PDF - INCREMENTS counter on actual download"""
    token = request.headers.get('Authorization')
    if not token:
        return "Unauthorized", 401
    
    email = verify_firebase_token(token.replace('Bearer ', ''))
    if not email:
        return "Unauthorized", 401
    
    count = get_user_download_count(email)
    
    if count >= MAX_PDFS:
        return "Quota exceeded", 429
    
    # Record download in database
    if not record_download(email):
        return "Database error", 500
    
    # Generate and return PDF
    buf = gen_pdf_content()
    buf.seek(0)
    name = f"{random.choice(PREFIXES)}_{random.choice(PREFIXES)}_{''.join(random.choices(string.ascii_uppercase+string.digits, k=4))}.pdf"
    return make_response(send_file(buf, as_attachment=True, download_name=name, mimetype='application/pdf'))

def gen_pdf_content():
    """Generate PDF with randomized fonts, sizes, and styles"""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    for page_num in range(10):
        pdf.add_page()
        
        for line_num in range(25):
            # Randomize font, style, and size for EACH line
            family = random.choice(['Arial', 'Times', 'Courier'])
            style = random.choice(['', 'B', 'I', 'BI'])
            size = random.randint(10, 14)
            
            pdf.set_font(family, style, size)
            
            # Generate random sentence
            line = " ".join(random.choice(WORDS) for _ in range(random.randint(10, 20))).capitalize() + "."
            pdf.multi_cell(0, 10, line, align='L')
            
            # Anti-Detector Noise
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', '', 6)
            noise = ''.join(random.choices(string.ascii_letters + string.digits, k=15))
            pdf.cell(0, 5, noise, ln=1)
            pdf.set_text_color(0, 0, 0)
    
    return io.BytesIO(pdf.output(dest='S').encode('latin-1'))

if __name__ == '__main__':
    app.run(debug=True)












# from flask import Flask, send_file, make_response, request, jsonify
# from fpdf import FPDF
# import random, string, io, time
# import os
# import json
# import firebase_admin
# from firebase_admin import credentials, auth as firebase_auth
# import psycopg2
# from psycopg2.extras import RealDictCursor
# from datetime import datetime, timedelta

# app = Flask(__name__)

# # Initialize Firebase Admin
# service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT')
# if service_account_json:
#     cred_dict = json.loads(service_account_json)
#     cred = credentials.Certificate(cred_dict)
#     firebase_admin.initialize_app(cred)

# # Database connection
# DATABASE_URL = os.getenv('DATABASE_URL')

# def get_db_connection():
#     """Create database connection"""
#     return psycopg2.connect(DATABASE_URL, sslmode='require')

# def init_db():
#     """Initialize database table if it doesn't exist"""
#     try:
#         conn = get_db_connection()
#         cur = conn.cursor()
#         cur.execute('''
#             CREATE TABLE IF NOT EXISTS user_downloads (
#                 id SERIAL PRIMARY KEY,
#                 email VARCHAR(255) NOT NULL,
#                 download_time TIMESTAMP NOT NULL,
#                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#             )
#         ''')
#         cur.execute('CREATE INDEX IF NOT EXISTS idx_email ON user_downloads(email)')
#         cur.execute('CREATE INDEX IF NOT EXISTS idx_download_time ON user_downloads(download_time)')
#         conn.commit()
#         cur.close()
#         conn.close()
#     except Exception as e:
#         print(f"Database init error: {e}")

# # Initialize database on startup
# init_db()

# # Config
# MAX_PDFS = 20
# WINDOW_HOURS = 24

# def verify_firebase_token(token):
#     """Verify Firebase ID token and return email if valid"""
#     try:
#         decoded_token = firebase_auth.verify_id_token(token)
#         return decoded_token.get('email')
#     except:
#         return None

# def get_user_download_count(email):
#     """Get number of downloads in the last 24 hours"""
#     try:
#         conn = get_db_connection()
#         cur = conn.cursor()
#         cutoff_time = datetime.now() - timedelta(hours=WINDOW_HOURS)
#         cur.execute(
#             'SELECT COUNT(*) FROM user_downloads WHERE email = %s AND download_time > %s',
#             (email, cutoff_time)
#         )
#         count = cur.fetchone()[0]
#         cur.close()
#         conn.close()
#         return count
#     except Exception as e:
#         print(f"Database error: {e}")
#         return 0

# def record_download(email):
#     """Record a download for the user"""
#     try:
#         conn = get_db_connection()
#         cur = conn.cursor()
#         cur.execute(
#             'INSERT INTO user_downloads (email, download_time) VALUES (%s, %s)',
#             (email, datetime.now())
#         )
#         conn.commit()
#         cur.close()
#         conn.close()
#         return True
#     except Exception as e:
#         print(f"Database error: {e}")
#         return False

# def get_time_until_reset(email):
#     """Get minutes until oldest download expires"""
#     try:
#         conn = get_db_connection()
#         cur = conn.cursor()
#         cutoff_time = datetime.now() - timedelta(hours=WINDOW_HOURS)
#         cur.execute(
#             'SELECT download_time FROM user_downloads WHERE email = %s AND download_time > %s ORDER BY download_time ASC LIMIT 1',
#             (email, cutoff_time)
#         )
#         result = cur.fetchone()
#         cur.close()
#         conn.close()
        
#         if result:
#             oldest = result[0]
#             reset_time = oldest + timedelta(hours=WINDOW_HOURS)
#             minutes = int((reset_time - datetime.now()).total_seconds() / 60) + 1
#             return max(1, minutes)
#         return 0
#     except Exception as e:
#         print(f"Database error: {e}")
#         return 0

# # --- THE FRONTEND ---
# HTML_PAGE = """
# <!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <meta name="viewport" content="width=device-width, initial-scale=1.0">
#     <title>Free PDF Generator - Random Test Documents | Pdfbirch</title>
#     <meta name="description" content="Generate random PDFs instantly. Free online PDF maker with realistic content & varied fonts. Perfect for testing, development, placeholder documents. No signup for preview, 20 free daily with Google login.">
#     <meta name="keywords" content="pdf generator, random pdf, test documents, fake pdf, pdf maker, document generator, placeholder pdf, development tools">
#     <meta name="author" content="Pdfbirch">
#     <meta name="robots" content="index, follow">
#     <meta name="language" content="English">
#     <link rel="canonical" href="https://pdfbirch.app">
    
#     <meta property="og:title" content="Free Random PDF Generator - Pdfbirch">
#     <meta property="og:description" content="Generate realistic test PDFs with varied fonts and content. Free online document generator for developers.">
#     <meta property="og:type" content="website">
#     <meta property="og:url" content="https://pdfbirch.app">
#     <meta property="og:site_name" content="Pdfbirch">
    
#     <meta name="twitter:card" content="summary_large_image">
#     <meta name="twitter:title" content="Free Random PDF Generator - Pdfbirch">
#     <meta name="twitter:description" content="Generate realistic test PDFs instantly. Perfect for testing and development.">

#     <script type="application/ld+json">
#     {
#       "@context": "https://schema.org",
#       "@type": "WebApplication",
#       "name": "Pdfbirch - Random PDF Generator",
#       "description": "Generate random test PDFs for development and QA testing",
#       "url": "https://pdfbirch.app",
#       "applicationCategory": "DeveloperApplication",
#       "operatingSystem": "Any",
#       "offers": {
#         "@type": "Offer",
#         "price": "0",
#         "priceCurrency": "USD"
#       },
#       "featureList": "Random PDF generation, Varied fonts, Test document creation, Batch generation"
#     }
#     </script>

#     <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-app-compat.js"></script>
#     <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-auth-compat.js"></script>

#     <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
#     <style>
#         :root { --bg: #f8fafc; --primary: #0f172a; --accent: #22c55e; --muted: #94a3b8; }
#         body { margin: 0; font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg); display: flex; flex-direction: column; align-items: center; min-height: 100vh; color: var(--primary); background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 32px 32px; }
        
#         .nav { width: 100%; max-width: 1100px; padding: 40px 20px; box-sizing: border-box; display: flex; justify-content: space-between; align-items: center; }
#         .logo { display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 15px; text-decoration: none; color: inherit; }
#         .dot { width: 8px; height: 8px; background: var(--accent); border-radius: 50%; }

#         .container { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; max-width: 500px; padding: 0 20px; box-sizing: border-box; text-align: center; }
#         h1 { font-size: 42px; font-weight: 800; letter-spacing: -1px; margin: 0 0 16px 0; line-height: 1.2; word-spacing: 0.15em; }
#         h2 { font-size: 18px; font-weight: 600; color: #64748b; margin: 0 0 12px 0; }
#         p { color: #64748b; font-size: 16px; line-height: 1.6; margin-bottom: 40px; }
        
#         .btn { background: var(--primary); color: white; border: none; padding: 22px; width: 100%; border-radius: 18px; font-weight: 700; font-size: 16px; cursor: pointer; transition: 0.2s; box-shadow: 0 10px 25px -5px rgba(15,23,42,0.2); }
#         .btn:hover { transform: translateY(-2px); box-shadow: 0 20px 35px -10px rgba(15,23,42,0.3); }

#         .user-badge { display: none; background: #fff; padding: 8px 16px; border-radius: 30px; border: 1px solid #e2e8f0; font-size: 12px; font-weight: 700; margin-bottom: 20px; }

#         .loader { margin-top: 40px; display: none; width: 100%; }
#         .bar-bg { background: #f1f5f9; height: 10px; border-radius: 10px; overflow: hidden; margin-top: 15px; }
#         .bar-fill { background: var(--primary); height: 100%; width: 0%; transition: width 0.3s linear; }
        
#         .results { margin-top: 40px; display: none; width: 100%; }
#         .file-link { display: flex; justify-content: space-between; padding: 20px; background: rgba(255,255,255,0.8); border: 1px solid #e2e8f0; border-radius: 16px; color: var(--primary); font-weight: 700; font-size: 14px; margin-bottom: 12px; cursor: pointer; transition: 0.2s; }
#         .file-link:hover { border-color: var(--primary); background: #fff; transform: scale(1.02); }

#         #limit-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15,23,42,0.9); z-index: 1000; backdrop-filter: blur(8px); align-items: center; justify-content: center; }
#         .modal-card { background: white; padding: 40px; border-radius: 24px; max-width: 320px; text-align: center; }

#         .support-box { margin-top: 80px; padding-top: 40px; border-top: 1px solid #f1f5f9; width: 100%; }
#         .affiliate-card { background: rgba(255,255,255,0.8); border: 1px dashed #cbd5e1; border-radius: 20px; padding: 24px; text-align: left; display: flex; align-items: center; gap: 18px; text-decoration: none; color: inherit; transition: 0.2s; }
        
#         .features { margin-top: 60px; width: 100%; }
#         .feature-grid { display: grid; grid-template-columns: 1fr; gap: 16px; margin-top: 24px; }
#         .feature-item { background: rgba(255,255,255,0.6); padding: 20px; border-radius: 12px; text-align: left; border: 1px solid #e2e8f0; }
#         .feature-item h3 { margin: 0 0 8px 0; font-size: 15px; font-weight: 700; }
#         .feature-item p { margin: 0; font-size: 13px; color: #64748b; }
        
#         footer { padding: 40px 20px; color: #cbd5e1; font-size: 12px; font-family: 'JetBrains Mono'; text-align: center; max-width: 600px; }
        
#         @media (max-width: 768px) {
#             h1 { font-size: 32px; }
#         }
#     </style>
# </head>
# <body>
#     <div id="limit-modal">
#         <div class="modal-card">
#             <div style="font-size:40px; margin-bottom:20px;">🛡️</div>
#             <h2 style="margin:0; font-weight:800; font-size:20px;">Daily Quota Exhausted</h2>
#             <p style="font-size:14px; color:#64748b; margin:15px 0 25px;">
#                 You've reached the 20-file daily limit. Access resets in approximately <span id="time-left" style="font-weight:800; color:var(--primary);">--</span> minutes.
#             </p>
#             <button class="btn" onclick="location.reload()">Understood</button>
#         </div>
#     </div>

#     <div class="nav">
#         <a href="/" class="logo"><div class="dot" role="img" aria-label="Pdfbirch logo"></div>PDFBIRCH.APP</a>
#         <a href="#" onclick="copyWallet(); return false;" style="font-size: 13px; font-weight: 700; color: var(--muted); text-decoration: none; cursor: pointer;">◎ Support</a>
#     </div>

#     <div class="container">
#         <div id="user-badge" class="user-badge"><span id="user-email"></span></div>
        
#         <h1>Free Random PDF Generator</h1>
#         <h2>Generate Test Documents Instantly</h2>
#         <p>Create realistic test PDFs with randomized fonts, styles, and content. Perfect for development, QA testing, and placeholder documents.</p>
        
#         <button class="btn" id="login-btn" onclick="signIn()">Enter Engine</button>

#         <div id="engine-ui" style="display:none; width: 100%;">
#             <button class="btn" id="start-btn" onclick="startEngine()">Initialize Batch</button>

#             <div class="loader" id="loader">
#                 <div style="display:flex; justify-content:space-between; font-size:12px; font-family:'JetBrains Mono'; font-weight:700; color: #94a3b8;">
#                     <span>Hashing...</span><span id="pct">0%</span>
#                 </div>
#                 <div class="bar-bg"><div class="bar-fill" id="fill"></div></div>
#             </div>

#             <div class="results" id="results"></div>
#         </div>

#         <div class="features">
#             <h2 style="text-align: center;">Why Use Pdfbirch?</h2>
#             <div class="feature-grid">
#                 <div class="feature-item">
#                     <h3>🎨 Varied Fonts & Styles</h3>
#                     <p>Each PDF uses randomized fonts, sizes, and formatting for realistic test scenarios</p>
#                 </div>
#                 <div class="feature-item">
#                     <h3>⚡ Instant Generation</h3>
#                     <p>Generate multiple PDFs in seconds with a single click</p>
#                 </div>
#                 <div class="feature-item">
#                     <h3>🔒 Privacy-First</h3>
#                     <p>No data collection, no tracking. Your testing stays private</p>
#                 </div>
#             </div>
#         </div>

#         <div class="support-box">
#             <a href="https://www.grammarly.com/affiliates" target="_blank" class="affiliate-card">
#                 <div style="font-size: 24px;">✍️</div>
#                 <div style="flex:1">
#                     <div style="font-weight:800; font-size:15px;">Polish Your Real Documents</div>
#                     <div style="font-size:13px; color:#94a3b8;">Use Grammarly to check grammar and spelling in your actual work.</div>
#                 </div>
#                 <div>→</div>
#             </a>
#         </div>
#     </div>

#     <footer>
#         <div style="margin-bottom:20px; line-height:1.8; opacity:0.8;">
#             Free tool for developers and QA engineers. Generate random PDFs for testing pipelines, document parsers, and workflow automation.
#         </div>
#         <div style="opacity:0.6;">
#             &copy; 2026 Pdfbirch &bull; For Testing & Development
#         </div>
#     </footer>

#     <script>
#         const firebaseConfig = {
#             apiKey: "AIzaSyBZ_LmqF-RHh3RxCl39XhRfCm_mu7k-diQ",
#             authDomain: "pdfbirch.firebaseapp.com",
#             projectId: "pdfbirch",
#             storageBucket: "pdfbirch.firebasestorage.app",
#             messagingSenderId: "701712083387",
#             appId: "1:701712083387:web:f438920e98b9831ea63c9e",
#             measurementId: "G-RTZELQLMMZ"
#         };
#         firebase.initializeApp(firebaseConfig);
#         const auth = firebase.auth();

#         function copyWallet() {
#             const wallet = '7fD3Yz3QRJ98nSPjaWYqayhmF3zxa4zoWK8rLk1Mzz7J';
#             navigator.clipboard.writeText(wallet).then(() => {
#                 alert('Solana wallet address copied!\n\n' + wallet + '\n\nSend SOL or SPL tokens to support this project. Thank you!');
#             }).catch(() => {
#                 prompt('Copy this Solana address:', wallet);
#             });
#         }

#         function signIn() {
#             const provider = new firebase.auth.GoogleAuthProvider();
#             auth.signInWithPopup(provider).catch(e => console.error(e));
#         }

#         auth.onAuthStateChanged(user => {
#             if (user) {
#                 document.getElementById('login-btn').style.display = 'none';
#                 document.getElementById('engine-ui').style.display = 'block';
#                 document.getElementById('user-badge').style.display = 'inline-flex';
#                 document.getElementById('user-email').innerText = user.email;
#             }
#         });

#         async function startEngine() {
#             const user = auth.currentUser;
#             if (!user) return;

#             const token = await user.getIdToken();

#             const res = await fetch('/api/check_limit', {
#                 headers: { 'Authorization': 'Bearer ' + token }
#             });
#             const data = await res.json();

#             if (!data.allowed) {
#                 document.getElementById('time-left').innerText = data.wait_time || 'N/A';
#                 document.getElementById('limit-modal').style.display = 'flex';
#                 return;
#             }

#             document.getElementById('start-btn').style.display='none';
#             document.getElementById('loader').style.display='block';
#             let w=0; 
#             const f=document.getElementById('fill'), p=document.getElementById('pct');
#             const t=setInterval(()=>{
#                 w++; 
#                 f.style.width=w+'%'; 
#                 p.innerText=w+'%';
#                 if(w>=100){ 
#                     clearInterval(t); 
#                     document.getElementById('loader').style.display='none'; 
#                     showResults(token);
#                 }
#             }, 600);
#         }

#         async function downloadPDF(token, filename) {
#             try {
#                 const res = await fetch('/api/download', {
#                     method: 'POST',
#                     headers: {
#                         'Authorization': 'Bearer ' + token,
#                         'Content-Type': 'application/json'
#                     }
#                 });

#                 if (res.status === 429) {
#                     alert('Daily quota reached!');
#                     location.reload();
#                     return;
#                 }

#                 if (!res.ok) {
#                     alert('Download failed. Please try again.');
#                     return;
#                 }

#                 const blob = await res.blob();
#                 const url = window.URL.createObjectURL(blob);
#                 const a = document.createElement('a');
#                 a.href = url;
#                 a.download = filename;
#                 document.body.appendChild(a);
#                 a.click();
#                 a.remove();
#                 window.URL.revokeObjectURL(url);
#             } catch(e) {
#                 console.error(e);
#                 alert('Download error');
#             }
#         }

#         function showResults(token) {
#             const files = [
#                 'Research_Analysis_K7M2.pdf',
#                 'Draft_Final_X8N4.pdf',
#                 'Project_Report_B3L9.pdf',
#                 'Case_Study_Thesis_A1C6.pdf',
#                 'Final_Project_T5R8.pdf'
#             ];

#             const resultsDiv = document.getElementById('results');
#             resultsDiv.innerHTML = files.map(f => 
#                 `<div class="file-link" onclick="downloadPDF('${token}', '${f}')"><span>${f}</span><span>↓</span></div>`
#             ).join('') + 
#             '<button class="btn" onclick="location.reload()" style="background:none; color:var(--primary); box-shadow:none; border:1px solid #e2e8f0; margin-top:20px;">Refresh Batch</button>';
#             resultsDiv.style.display = 'block';
#         }
#     </script>
# </body>
# </html>
# """

# # --- THE BACKEND ---
# PREFIXES = ["Research", "Analysis", "Draft", "Final", "Project", "Report", "Case_Study", "Thesis"]
# WORDS = ["strategy", "growth", "market", "value", "user", "product", "system", "data", "cloud", "AI", "project", "scale"]

# @app.route('/')
# def home(): 
#     return HTML_PAGE

# @app.route('/robots.txt')
# def robots():
#     return """User-agent: *
# Allow: /
# Sitemap: https://pdfbirch.app/sitemap.xml

# User-agent: GPTBot
# Disallow: /

# User-agent: CCBot
# Disallow: /""", 200, {'Content-Type': 'text/plain'}

# @app.route('/sitemap.xml')
# def sitemap():
#     return """<?xml version="1.0" encoding="UTF-8"?>
# <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
#   <url>
#     <loc>https://pdfbirch.app</loc>
#     <lastmod>2026-02-07</lastmod>
#     <changefreq>weekly</changefreq>
#     <priority>1.0</priority>
#   </url>
# </urlset>""", 200, {'Content-Type': 'application/xml'}

# @app.route('/api/check_limit')
# def check_limit():
#     """Check if user has quota left - DOES NOT increment counter"""
#     token = request.headers.get('Authorization')
#     if not token:
#         return jsonify({"allowed": False, "error": "No token"}), 401
    
#     email = verify_firebase_token(token.replace('Bearer ', ''))
#     if not email:
#         return jsonify({"allowed": False, "error": "Invalid token"}), 401
    
#     count = get_user_download_count(email)
    
#     if count >= MAX_PDFS:
#         wait_time = get_time_until_reset(email)
#         return jsonify({"allowed": False, "wait_time": wait_time})
    
#     return jsonify({"allowed": True})

# @app.route('/api/download', methods=['POST'])
# def download():
#     """Download PDF - INCREMENTS counter on actual download"""
#     token = request.headers.get('Authorization')
#     if not token:
#         return "Unauthorized", 401
    
#     email = verify_firebase_token(token.replace('Bearer ', ''))
#     if not email:
#         return "Unauthorized", 401
    
#     count = get_user_download_count(email)
    
#     if count >= MAX_PDFS:
#         return "Quota exceeded", 429
    
#     # Record download in database
#     if not record_download(email):
#         return "Database error", 500
    
#     # Generate and return PDF
#     buf = gen_pdf_content()
#     buf.seek(0)
#     name = f"{random.choice(PREFIXES)}_{random.choice(PREFIXES)}_{''.join(random.choices(string.ascii_uppercase+string.digits, k=4))}.pdf"
#     return make_response(send_file(buf, as_attachment=True, download_name=name, mimetype='application/pdf'))

# def gen_pdf_content():
#     """Generate PDF with randomized fonts, sizes, and styles"""
#     pdf = FPDF()
#     pdf.set_auto_page_break(auto=True, margin=15)
    
#     for page_num in range(10):
#         pdf.add_page()
        
#         for line_num in range(25):
#             # Randomize font, style, and size for EACH line
#             family = random.choice(['Arial', 'Times', 'Courier'])
#             style = random.choice(['', 'B', 'I', 'BI'])
#             size = random.randint(10, 14)
            
#             pdf.set_font(family, style, size)
            
#             # Generate random sentence
#             line = " ".join(random.choice(WORDS) for _ in range(random.randint(10, 20))).capitalize() + "."
#             pdf.multi_cell(0, 10, line, align='L')
            
#             # Anti-Detector Noise
#             pdf.set_text_color(255, 255, 255)
#             pdf.set_font('Arial', '', 6)
#             noise = ''.join(random.choices(string.ascii_letters + string.digits, k=15))
#             pdf.cell(0, 5, noise, ln=1)
#             pdf.set_text_color(0, 0, 0)
    
#     return io.BytesIO(pdf.output(dest='S').encode('latin-1'))

# if __name__ == '__main__':
#     app.run(debug=True)









# # from flask import Flask, send_file, make_response, request, jsonify
# # from fpdf import FPDF
# # import random, string, io, time
# # import os
# # import json
# # import firebase_admin
# # from firebase_admin import credentials, auth as firebase_auth
# # import psycopg2
# # from psycopg2.extras import RealDictCursor
# # from datetime import datetime, timedelta

# # app = Flask(__name__)

# # # Initialize Firebase Admin
# # service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT')
# # if service_account_json:
# #     cred_dict = json.loads(service_account_json)
# #     cred = credentials.Certificate(cred_dict)
# #     firebase_admin.initialize_app(cred)

# # # Database connection
# # DATABASE_URL = os.getenv('DATABASE_URL')

# # def get_db_connection():
# #     """Create database connection"""
# #     return psycopg2.connect(DATABASE_URL, sslmode='require')

# # def init_db():
# #     """Initialize database table if it doesn't exist"""
# #     try:
# #         conn = get_db_connection()
# #         cur = conn.cursor()
# #         cur.execute('''
# #             CREATE TABLE IF NOT EXISTS user_downloads (
# #                 id SERIAL PRIMARY KEY,
# #                 email VARCHAR(255) NOT NULL,
# #                 download_time TIMESTAMP NOT NULL,
# #                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# #             )
# #         ''')
# #         cur.execute('CREATE INDEX IF NOT EXISTS idx_email ON user_downloads(email)')
# #         cur.execute('CREATE INDEX IF NOT EXISTS idx_download_time ON user_downloads(download_time)')
# #         conn.commit()
# #         cur.close()
# #         conn.close()
# #     except Exception as e:
# #         print(f"Database init error: {e}")

# # # Initialize database on startup
# # init_db()

# # # Config
# # MAX_PDFS = 20
# # WINDOW_HOURS = 24

# # def verify_firebase_token(token):
# #     """Verify Firebase ID token and return email if valid"""
# #     try:
# #         decoded_token = firebase_auth.verify_id_token(token)
# #         return decoded_token.get('email')
# #     except:
# #         return None

# # def get_user_download_count(email):
# #     """Get number of downloads in the last 24 hours"""
# #     try:
# #         conn = get_db_connection()
# #         cur = conn.cursor()
# #         cutoff_time = datetime.now() - timedelta(hours=WINDOW_HOURS)
# #         cur.execute(
# #             'SELECT COUNT(*) FROM user_downloads WHERE email = %s AND download_time > %s',
# #             (email, cutoff_time)
# #         )
# #         count = cur.fetchone()[0]
# #         cur.close()
# #         conn.close()
# #         return count
# #     except Exception as e:
# #         print(f"Database error: {e}")
# #         return 0

# # def record_download(email):
# #     """Record a download for the user"""
# #     try:
# #         conn = get_db_connection()
# #         cur = conn.cursor()
# #         cur.execute(
# #             'INSERT INTO user_downloads (email, download_time) VALUES (%s, %s)',
# #             (email, datetime.now())
# #         )
# #         conn.commit()
# #         cur.close()
# #         conn.close()
# #         return True
# #     except Exception as e:
# #         print(f"Database error: {e}")
# #         return False

# # def get_time_until_reset(email):
# #     """Get minutes until oldest download expires"""
# #     try:
# #         conn = get_db_connection()
# #         cur = conn.cursor()
# #         cutoff_time = datetime.now() - timedelta(hours=WINDOW_HOURS)
# #         cur.execute(
# #             'SELECT download_time FROM user_downloads WHERE email = %s AND download_time > %s ORDER BY download_time ASC LIMIT 1',
# #             (email, cutoff_time)
# #         )
# #         result = cur.fetchone()
# #         cur.close()
# #         conn.close()
        
# #         if result:
# #             oldest = result[0]
# #             reset_time = oldest + timedelta(hours=WINDOW_HOURS)
# #             minutes = int((reset_time - datetime.now()).total_seconds() / 60) + 1
# #             return max(1, minutes)
# #         return 0
# #     except Exception as e:
# #         print(f"Database error: {e}")
# #         return 0

# # # --- THE FRONTEND ---
# # HTML_PAGE = """
# # <!DOCTYPE html>
# # <html lang="en">
# # <head>
# #     <meta charset="UTF-8">
# #     <meta name="viewport" content="width=device-width, initial-scale=1.0">
# #     <title>Free PDF Generator - Random Test Documents | Pdfbirch</title>
# #     <meta name="description" content="Generate random PDFs instantly. Free online PDF maker with realistic content & varied fonts. Perfect for testing, development, placeholder documents. No signup for preview, 20 free daily with Google login.">
# #     <meta name="keywords" content="pdf generator, random pdf, test documents, fake pdf, pdf maker, document generator, placeholder pdf, development tools">
# #     <meta name="author" content="Pdfbirch">
# #     <meta name="robots" content="index, follow">
# #     <meta name="language" content="English">
# #     <link rel="canonical" href="https://pdfbirch.app">
    
# #     <meta property="og:title" content="Free Random PDF Generator - Pdfbirch">
# #     <meta property="og:description" content="Generate realistic test PDFs with varied fonts and content. Free online document generator for developers.">
# #     <meta property="og:type" content="website">
# #     <meta property="og:url" content="https://pdfbirch.app">
# #     <meta property="og:site_name" content="Pdfbirch">
    
# #     <meta name="twitter:card" content="summary_large_image">
# #     <meta name="twitter:title" content="Free Random PDF Generator - Pdfbirch">
# #     <meta name="twitter:description" content="Generate realistic test PDFs instantly. Perfect for testing and development.">

# #     <script type="application/ld+json">
# #     {
# #       "@context": "https://schema.org",
# #       "@type": "WebApplication",
# #       "name": "Pdfbirch - Random PDF Generator",
# #       "description": "Generate random test PDFs for development and QA testing",
# #       "url": "https://pdfbirch.app",
# #       "applicationCategory": "DeveloperApplication",
# #       "operatingSystem": "Any",
# #       "offers": {
# #         "@type": "Offer",
# #         "price": "0",
# #         "priceCurrency": "USD"
# #       },
# #       "featureList": "Random PDF generation, Varied fonts, Test document creation, Batch generation"
# #     }
# #     </script>

# #     <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-app-compat.js"></script>
# #     <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-auth-compat.js"></script>

# #     <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
# #     <style>
# #         :root { --bg: #f8fafc; --primary: #0f172a; --accent: #22c55e; --muted: #94a3b8; }
# #         body { margin: 0; font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg); display: flex; flex-direction: column; align-items: center; min-height: 100vh; color: var(--primary); background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 32px 32px; }
        
# #         .nav { width: 100%; max-width: 1100px; padding: 40px 20px; box-sizing: border-box; display: flex; justify-content: space-between; align-items: center; }
# #         .logo { display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 15px; text-decoration: none; color: inherit; }
# #         .dot { width: 8px; height: 8px; background: var(--accent); border-radius: 50%; }

# #         .container { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; max-width: 500px; padding: 0 20px; box-sizing: border-box; text-align: center; }
# #         h1 { font-size: 42px; font-weight: 800; letter-spacing: -1px; margin: 0 0 16px 0; line-height: 1.2; word-spacing: 0.15em; }
# #         h2 { font-size: 18px; font-weight: 600; color: #64748b; margin: 0 0 12px 0; }
# #         p { color: #64748b; font-size: 16px; line-height: 1.6; margin-bottom: 40px; }
        
# #         .btn { background: var(--primary); color: white; border: none; padding: 22px; width: 100%; border-radius: 18px; font-weight: 700; font-size: 16px; cursor: pointer; transition: 0.2s; box-shadow: 0 10px 25px -5px rgba(15,23,42,0.2); }
# #         .btn:hover { transform: translateY(-2px); box-shadow: 0 20px 35px -10px rgba(15,23,42,0.3); }

# #         .user-badge { display: none; background: #fff; padding: 8px 16px; border-radius: 30px; border: 1px solid #e2e8f0; font-size: 12px; font-weight: 700; margin-bottom: 20px; }

# #         .loader { margin-top: 40px; display: none; width: 100%; }
# #         .bar-bg { background: #f1f5f9; height: 10px; border-radius: 10px; overflow: hidden; margin-top: 15px; }
# #         .bar-fill { background: var(--primary); height: 100%; width: 0%; transition: width 0.3s linear; }
        
# #         .results { margin-top: 40px; display: none; width: 100%; }
# #         .file-link { display: flex; justify-content: space-between; padding: 20px; background: rgba(255,255,255,0.8); border: 1px solid #e2e8f0; border-radius: 16px; color: var(--primary); font-weight: 700; font-size: 14px; margin-bottom: 12px; cursor: pointer; transition: 0.2s; }
# #         .file-link:hover { border-color: var(--primary); background: #fff; transform: scale(1.02); }

# #         #limit-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15,23,42,0.9); z-index: 1000; backdrop-filter: blur(8px); align-items: center; justify-content: center; }
# #         .modal-card { background: white; padding: 40px; border-radius: 24px; max-width: 320px; text-align: center; }

# #         .support-box { margin-top: 80px; padding-top: 40px; border-top: 1px solid #f1f5f9; width: 100%; }
# #         .affiliate-card { background: rgba(255,255,255,0.8); border: 1px dashed #cbd5e1; border-radius: 20px; padding: 24px; text-align: left; display: flex; align-items: center; gap: 18px; text-decoration: none; color: inherit; transition: 0.2s; }
        
# #         .features { margin-top: 60px; width: 100%; }
# #         .feature-grid { display: grid; grid-template-columns: 1fr; gap: 16px; margin-top: 24px; }
# #         .feature-item { background: rgba(255,255,255,0.6); padding: 20px; border-radius: 12px; text-align: left; border: 1px solid #e2e8f0; }
# #         .feature-item h3 { margin: 0 0 8px 0; font-size: 15px; font-weight: 700; }
# #         .feature-item p { margin: 0; font-size: 13px; color: #64748b; }
        
# #         footer { padding: 40px 20px; color: #cbd5e1; font-size: 12px; font-family: 'JetBrains Mono'; text-align: center; max-width: 600px; }
        
# #         @media (max-width: 768px) {
# #             h1 { font-size: 32px; }
# #         }
# #     </style>
# # </head>
# # <body>
# #     <div id="limit-modal">
# #         <div class="modal-card">
# #             <div style="font-size:40px; margin-bottom:20px;">🛡️</div>
# #             <h2 style="margin:0; font-weight:800; font-size:20px;">Daily Quota Exhausted</h2>
# #             <p style="font-size:14px; color:#64748b; margin:15px 0 25px;">
# #                 You've reached the 20-file daily limit. Access resets in approximately <span id="time-left" style="font-weight:800; color:var(--primary);">--</span> minutes.
# #             </p>
# #             <button class="btn" onclick="location.reload()">Understood</button>
# #         </div>
# #     </div>

# #     <div class="nav">
# #         <a href="/" class="logo"><div class="dot" role="img" aria-label="Pdfbirch logo"></div>PDFBIRCH.APP</a>
# #         <a href="https://www.buymeacoffee.com/sherlock2803" target="_blank" style="font-size: 13px; font-weight: 700; color: var(--muted); text-decoration: none;">☕ Support</a>
# #     </div>

# #     <div class="container">
# #         <div id="user-badge" class="user-badge"><span id="user-email"></span></div>
        
# #         <h1>Free Random PDF Generator</h1>
# #         <h2>Generate Test Documents Instantly</h2>
# #         <p>Create realistic test PDFs with randomized fonts, styles, and content. Perfect for development, QA testing, and placeholder documents.</p>
        
# #         <button class="btn" id="login-btn" onclick="signIn()">Enter Engine</button>

# #         <div id="engine-ui" style="display:none; width: 100%;">
# #             <button class="btn" id="start-btn" onclick="startEngine()">Initialize Batch</button>

# #             <div class="loader" id="loader">
# #                 <div style="display:flex; justify-content:space-between; font-size:12px; font-family:'JetBrains Mono'; font-weight:700; color: #94a3b8;">
# #                     <span>Hashing...</span><span id="pct">0%</span>
# #                 </div>
# #                 <div class="bar-bg"><div class="bar-fill" id="fill"></div></div>
# #             </div>

# #             <div class="results" id="results"></div>
# #         </div>

# #         <div class="features">
# #             <h2 style="text-align: center;">Why Use Pdfbirch?</h2>
# #             <div class="feature-grid">
# #                 <div class="feature-item">
# #                     <h3>🎨 Varied Fonts & Styles</h3>
# #                     <p>Each PDF uses randomized fonts, sizes, and formatting for realistic test scenarios</p>
# #                 </div>
# #                 <div class="feature-item">
# #                     <h3>⚡ Instant Generation</h3>
# #                     <p>Generate multiple PDFs in seconds with a single click</p>
# #                 </div>
# #                 <div class="feature-item">
# #                     <h3>🔒 Privacy-First</h3>
# #                     <p>No data collection, no tracking. Your testing stays private</p>
# #                 </div>
# #             </div>
# #         </div>

# #         <div class="support-box">
# #             <a href="https://www.grammarly.com/affiliates" target="_blank" class="affiliate-card">
# #                 <div style="font-size: 24px;">✍️</div>
# #                 <div style="flex:1">
# #                     <div style="font-weight:800; font-size:15px;">Polish Your Real Documents</div>
# #                     <div style="font-size:13px; color:#94a3b8;">Use Grammarly to check grammar and spelling in your actual work.</div>
# #                 </div>
# #                 <div>→</div>
# #             </a>
# #         </div>
# #     </div>

# #     <footer>
# #         <div style="margin-bottom:20px; line-height:1.8; opacity:0.8;">
# #             Free tool for developers and QA engineers. Generate random PDFs for testing pipelines, document parsers, and workflow automation.
# #         </div>
# #         <div style="opacity:0.6;">
# #             &copy; 2026 Pdfbirch &bull; For Testing & Development
# #         </div>
# #     </footer>

# #     <script>
# #         const firebaseConfig = {
# #             apiKey: "AIzaSyBZ_LmqF-RHh3RxCl39XhRfCm_mu7k-diQ",
# #             authDomain: "pdfbirch.firebaseapp.com",
# #             projectId: "pdfbirch",
# #             storageBucket: "pdfbirch.firebasestorage.app",
# #             messagingSenderId: "701712083387",
# #             appId: "1:701712083387:web:f438920e98b9831ea63c9e",
# #             measurementId: "G-RTZELQLMMZ"
# #         };
# #         firebase.initializeApp(firebaseConfig);
# #         const auth = firebase.auth();

# #         function signIn() {
# #             const provider = new firebase.auth.GoogleAuthProvider();
# #             auth.signInWithPopup(provider).catch(e => console.error(e));
# #         }

# #         auth.onAuthStateChanged(user => {
# #             if (user) {
# #                 document.getElementById('login-btn').style.display = 'none';
# #                 document.getElementById('engine-ui').style.display = 'block';
# #                 document.getElementById('user-badge').style.display = 'inline-flex';
# #                 document.getElementById('user-email').innerText = user.email;
# #             }
# #         });

# #         async function startEngine() {
# #             const user = auth.currentUser;
# #             if (!user) return;

# #             const token = await user.getIdToken();

# #             const res = await fetch('/api/check_limit', {
# #                 headers: { 'Authorization': 'Bearer ' + token }
# #             });
# #             const data = await res.json();

# #             if (!data.allowed) {
# #                 document.getElementById('time-left').innerText = data.wait_time || 'N/A';
# #                 document.getElementById('limit-modal').style.display = 'flex';
# #                 return;
# #             }

# #             document.getElementById('start-btn').style.display='none';
# #             document.getElementById('loader').style.display='block';
# #             let w=0; 
# #             const f=document.getElementById('fill'), p=document.getElementById('pct');
# #             const t=setInterval(()=>{
# #                 w++; 
# #                 f.style.width=w+'%'; 
# #                 p.innerText=w+'%';
# #                 if(w>=100){ 
# #                     clearInterval(t); 
# #                     document.getElementById('loader').style.display='none'; 
# #                     showResults(token);
# #                 }
# #             }, 600);
# #         }

# #         async function downloadPDF(token, filename) {
# #             try {
# #                 const res = await fetch('/api/download', {
# #                     method: 'POST',
# #                     headers: {
# #                         'Authorization': 'Bearer ' + token,
# #                         'Content-Type': 'application/json'
# #                     }
# #                 });

# #                 if (res.status === 429) {
# #                     alert('Daily quota reached!');
# #                     location.reload();
# #                     return;
# #                 }

# #                 if (!res.ok) {
# #                     alert('Download failed. Please try again.');
# #                     return;
# #                 }

# #                 const blob = await res.blob();
# #                 const url = window.URL.createObjectURL(blob);
# #                 const a = document.createElement('a');
# #                 a.href = url;
# #                 a.download = filename;
# #                 document.body.appendChild(a);
# #                 a.click();
# #                 a.remove();
# #                 window.URL.revokeObjectURL(url);
# #             } catch(e) {
# #                 console.error(e);
# #                 alert('Download error');
# #             }
# #         }

# #         function showResults(token) {
# #             const files = [
# #                 'Research_Analysis_K7M2.pdf',
# #                 'Draft_Final_X8N4.pdf',
# #                 'Project_Report_B3L9.pdf',
# #                 'Case_Study_Thesis_A1C6.pdf',
# #                 'Final_Project_T5R8.pdf'
# #             ];

# #             const resultsDiv = document.getElementById('results');
# #             resultsDiv.innerHTML = files.map(f => 
# #                 `<div class="file-link" onclick="downloadPDF('${token}', '${f}')"><span>${f}</span><span>↓</span></div>`
# #             ).join('') + 
# #             '<button class="btn" onclick="location.reload()" style="background:none; color:var(--primary); box-shadow:none; border:1px solid #e2e8f0; margin-top:20px;">Refresh Batch</button>';
# #             resultsDiv.style.display = 'block';
# #         }
# #     </script>
# # </body>
# # </html>
# # """

# # # --- THE BACKEND ---
# # PREFIXES = ["Research", "Analysis", "Draft", "Final", "Project", "Report", "Case_Study", "Thesis"]
# # WORDS = ["strategy", "growth", "market", "value", "user", "product", "system", "data", "cloud", "AI", "project", "scale"]

# # @app.route('/')
# # def home(): 
# #     return HTML_PAGE

# # @app.route('/robots.txt')
# # def robots():
# #     return """User-agent: *
# # Allow: /
# # Sitemap: https://pdfbirch.app/sitemap.xml

# # User-agent: GPTBot
# # Disallow: /

# # User-agent: CCBot
# # Disallow: /""", 200, {'Content-Type': 'text/plain'}

# # @app.route('/sitemap.xml')
# # def sitemap():
# #     return """<?xml version="1.0" encoding="UTF-8"?>
# # <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
# #   <url>
# #     <loc>https://pdfbirch.app</loc>
# #     <lastmod>2026-02-07</lastmod>
# #     <changefreq>weekly</changefreq>
# #     <priority>1.0</priority>
# #   </url>
# # </urlset>""", 200, {'Content-Type': 'application/xml'}

# # @app.route('/api/check_limit')
# # def check_limit():
# #     """Check if user has quota left - DOES NOT increment counter"""
# #     token = request.headers.get('Authorization')
# #     if not token:
# #         return jsonify({"allowed": False, "error": "No token"}), 401
    
# #     email = verify_firebase_token(token.replace('Bearer ', ''))
# #     if not email:
# #         return jsonify({"allowed": False, "error": "Invalid token"}), 401
    
# #     count = get_user_download_count(email)
    
# #     if count >= MAX_PDFS:
# #         wait_time = get_time_until_reset(email)
# #         return jsonify({"allowed": False, "wait_time": wait_time})
    
# #     return jsonify({"allowed": True})

# # @app.route('/api/download', methods=['POST'])
# # def download():
# #     """Download PDF - INCREMENTS counter on actual download"""
# #     token = request.headers.get('Authorization')
# #     if not token:
# #         return "Unauthorized", 401
    
# #     email = verify_firebase_token(token.replace('Bearer ', ''))
# #     if not email:
# #         return "Unauthorized", 401
    
# #     count = get_user_download_count(email)
    
# #     if count >= MAX_PDFS:
# #         return "Quota exceeded", 429
    
# #     # Record download in database
# #     if not record_download(email):
# #         return "Database error", 500
    
# #     # Generate and return PDF
# #     buf = gen_pdf_content()
# #     buf.seek(0)
# #     name = f"{random.choice(PREFIXES)}_{random.choice(PREFIXES)}_{''.join(random.choices(string.ascii_uppercase+string.digits, k=4))}.pdf"
# #     return make_response(send_file(buf, as_attachment=True, download_name=name, mimetype='application/pdf'))

# # def gen_pdf_content():
# #     """Generate PDF with randomized fonts, sizes, and styles"""
# #     pdf = FPDF()
# #     pdf.set_auto_page_break(auto=True, margin=15)
    
# #     for page_num in range(10):
# #         pdf.add_page()
        
# #         for line_num in range(25):
# #             # Randomize font, style, and size for EACH line
# #             family = random.choice(['Arial', 'Times', 'Courier'])
# #             style = random.choice(['', 'B', 'I', 'BI'])
# #             size = random.randint(10, 14)
            
# #             pdf.set_font(family, style, size)
            
# #             # Generate random sentence
# #             line = " ".join(random.choice(WORDS) for _ in range(random.randint(10, 20))).capitalize() + "."
# #             pdf.multi_cell(0, 10, line, align='L')
            
# #             # Anti-Detector Noise
# #             pdf.set_text_color(255, 255, 255)
# #             pdf.set_font('Arial', '', 6)
# #             noise = ''.join(random.choices(string.ascii_letters + string.digits, k=15))
# #             pdf.cell(0, 5, noise, ln=1)
# #             pdf.set_text_color(0, 0, 0)
    
# #     return io.BytesIO(pdf.output(dest='S').encode('latin-1'))

# # if __name__ == '__main__':
# #     app.run(debug=True)












# # # from flask import Flask, send_file, make_response, request, jsonify
# # # from fpdf import FPDF
# # # import random, string, io, time
# # # import os
# # # import json
# # # import firebase_admin
# # # from firebase_admin import credentials, auth as firebase_auth
# # # import psycopg2
# # # from psycopg2.extras import RealDictCursor
# # # from datetime import datetime, timedelta

# # # app = Flask(__name__)

# # # # Initialize Firebase Admin
# # # service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT')
# # # if service_account_json:
# # #     cred_dict = json.loads(service_account_json)
# # #     cred = credentials.Certificate(cred_dict)
# # #     firebase_admin.initialize_app(cred)

# # # # Database connection
# # # DATABASE_URL = os.getenv('DATABASE_URL')

# # # def get_db_connection():
# # #     """Create database connection"""
# # #     return psycopg2.connect(DATABASE_URL, sslmode='require')

# # # def init_db():
# # #     """Initialize database table if it doesn't exist"""
# # #     try:
# # #         conn = get_db_connection()
# # #         cur = conn.cursor()
# # #         cur.execute('''
# # #             CREATE TABLE IF NOT EXISTS user_downloads (
# # #                 id SERIAL PRIMARY KEY,
# # #                 email VARCHAR(255) NOT NULL,
# # #                 download_time TIMESTAMP NOT NULL,
# # #                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# # #             )
# # #         ''')
# # #         cur.execute('CREATE INDEX IF NOT EXISTS idx_email ON user_downloads(email)')
# # #         cur.execute('CREATE INDEX IF NOT EXISTS idx_download_time ON user_downloads(download_time)')
# # #         conn.commit()
# # #         cur.close()
# # #         conn.close()
# # #     except Exception as e:
# # #         print(f"Database init error: {e}")

# # # # Initialize database on startup
# # # init_db()

# # # # Config
# # # MAX_PDFS = 20
# # # WINDOW_HOURS = 24

# # # def verify_firebase_token(token):
# # #     """Verify Firebase ID token and return email if valid"""
# # #     try:
# # #         decoded_token = firebase_auth.verify_id_token(token)
# # #         return decoded_token.get('email')
# # #     except:
# # #         return None

# # # def get_user_download_count(email):
# # #     """Get number of downloads in the last 24 hours"""
# # #     try:
# # #         conn = get_db_connection()
# # #         cur = conn.cursor()
# # #         cutoff_time = datetime.now() - timedelta(hours=WINDOW_HOURS)
# # #         cur.execute(
# # #             'SELECT COUNT(*) FROM user_downloads WHERE email = %s AND download_time > %s',
# # #             (email, cutoff_time)
# # #         )
# # #         count = cur.fetchone()[0]
# # #         cur.close()
# # #         conn.close()
# # #         return count
# # #     except Exception as e:
# # #         print(f"Database error: {e}")
# # #         return 0

# # # def record_download(email):
# # #     """Record a download for the user"""
# # #     try:
# # #         conn = get_db_connection()
# # #         cur = conn.cursor()
# # #         cur.execute(
# # #             'INSERT INTO user_downloads (email, download_time) VALUES (%s, %s)',
# # #             (email, datetime.now())
# # #         )
# # #         conn.commit()
# # #         cur.close()
# # #         conn.close()
# # #         return True
# # #     except Exception as e:
# # #         print(f"Database error: {e}")
# # #         return False

# # # def get_time_until_reset(email):
# # #     """Get minutes until oldest download expires"""
# # #     try:
# # #         conn = get_db_connection()
# # #         cur = conn.cursor()
# # #         cutoff_time = datetime.now() - timedelta(hours=WINDOW_HOURS)
# # #         cur.execute(
# # #             'SELECT download_time FROM user_downloads WHERE email = %s AND download_time > %s ORDER BY download_time ASC LIMIT 1',
# # #             (email, cutoff_time)
# # #         )
# # #         result = cur.fetchone()
# # #         cur.close()
# # #         conn.close()
        
# # #         if result:
# # #             oldest = result[0]
# # #             reset_time = oldest + timedelta(hours=WINDOW_HOURS)
# # #             minutes = int((reset_time - datetime.now()).total_seconds() / 60) + 1
# # #             return max(1, minutes)
# # #         return 0
# # #     except Exception as e:
# # #         print(f"Database error: {e}")
# # #         return 0

# # # # --- THE FRONTEND ---
# # # HTML_PAGE = """
# # # <!DOCTYPE html>
# # # <html lang="en">
# # # <head>
# # #     <meta charset="UTF-8">
# # #     <meta name="viewport" content="width=device-width, initial-scale=1.0">
# # #     <title>Free PDF Generator - Random Test Documents | Pdfbirch</title>
# # #     <meta name="description" content="Generate random PDFs instantly. Free online PDF maker with realistic content & varied fonts. Perfect for testing, development, placeholder documents. No signup for preview, 20 free daily with Google login.">
# # #     <meta name="keywords" content="pdf generator, random pdf, test documents, fake pdf, pdf maker, document generator, placeholder pdf, development tools">
# # #     <meta name="author" content="Pdfbirch">
# # #     <meta name="robots" content="index, follow">
# # #     <meta name="language" content="English">
# # #     <link rel="canonical" href="https://pdfbirch.app">
    
# # #     <meta property="og:title" content="Free Random PDF Generator - Pdfbirch">
# # #     <meta property="og:description" content="Generate realistic test PDFs with varied fonts and content. Free online document generator for developers.">
# # #     <meta property="og:type" content="website">
# # #     <meta property="og:url" content="https://pdfbirch.app">
# # #     <meta property="og:site_name" content="Pdfbirch">
    
# # #     <meta name="twitter:card" content="summary_large_image">
# # #     <meta name="twitter:title" content="Free Random PDF Generator - Pdfbirch">
# # #     <meta name="twitter:description" content="Generate realistic test PDFs instantly. Perfect for testing and development.">

# # #     <script type="application/ld+json">
# # #     {
# # #       "@context": "https://schema.org",
# # #       "@type": "WebApplication",
# # #       "name": "Pdfbirch - Random PDF Generator",
# # #       "description": "Generate random test PDFs for development and QA testing",
# # #       "url": "https://pdfbirch.app",
# # #       "applicationCategory": "DeveloperApplication",
# # #       "operatingSystem": "Any",
# # #       "offers": {
# # #         "@type": "Offer",
# # #         "price": "0",
# # #         "priceCurrency": "USD"
# # #       },
# # #       "featureList": "Random PDF generation, Varied fonts, Test document creation, Batch generation"
# # #     }
# # #     </script>

# # #     <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
# # #     <style>
# # #         :root { --bg: #f8fafc; --primary: #0f172a; --accent: #22c55e; --muted: #94a3b8; }
# # #         body { margin: 0; font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg); display: flex; flex-direction: column; align-items: center; min-height: 100vh; color: var(--primary); background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 32px 32px; }
        
# # #         .nav { width: 100%; max-width: 1100px; padding: 40px 20px; box-sizing: border-box; display: flex; justify-content: space-between; align-items: center; }
# # #         .logo { display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 15px; text-decoration: none; color: inherit; }
# # #         .dot { width: 8px; height: 8px; background: var(--accent); border-radius: 50%; }

# # #         .container { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; max-width: 500px; padding: 0 20px; box-sizing: border-box; text-align: center; }
# # #         h1 { font-size: 42px; font-weight: 800; letter-spacing: -2px; margin: 0 0 16px 0; line-height: 1; }
# # #         h2 { font-size: 18px; font-weight: 600; color: #64748b; margin: 0 0 12px 0; }
# # #         p { color: #64748b; font-size: 16px; line-height: 1.6; margin-bottom: 40px; }
        
# # #         .btn { background: var(--primary); color: white; border: none; padding: 22px; width: 100%; border-radius: 18px; font-weight: 700; font-size: 16px; cursor: pointer; transition: 0.2s; box-shadow: 0 10px 25px -5px rgba(15,23,42,0.2); }
# # #         .btn:hover { transform: translateY(-2px); box-shadow: 0 20px 35px -10px rgba(15,23,42,0.3); }

# # #         .user-badge { display: none; background: #fff; padding: 8px 16px; border-radius: 30px; border: 1px solid #e2e8f0; font-size: 12px; font-weight: 700; margin-bottom: 20px; }

# # #         .loader { margin-top: 40px; display: none; width: 100%; }
# # #         .bar-bg { background: #f1f5f9; height: 10px; border-radius: 10px; overflow: hidden; margin-top: 15px; }
# # #         .bar-fill { background: var(--primary); height: 100%; width: 0%; transition: width 0.3s linear; }
        
# # #         .results { margin-top: 40px; display: none; width: 100%; }
# # #         .file-link { display: flex; justify-content: space-between; padding: 20px; background: rgba(255,255,255,0.8); border: 1px solid #e2e8f0; border-radius: 16px; color: var(--primary); font-weight: 700; font-size: 14px; margin-bottom: 12px; cursor: pointer; transition: 0.2s; }
# # #         .file-link:hover { border-color: var(--primary); background: #fff; transform: scale(1.02); }

# # #         #limit-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15,23,42,0.9); z-index: 1000; backdrop-filter: blur(8px); align-items: center; justify-content: center; }
# # #         .modal-card { background: white; padding: 40px; border-radius: 24px; max-width: 320px; text-align: center; }

# # #         .support-box { margin-top: 80px; padding-top: 40px; border-top: 1px solid #f1f5f9; width: 100%; }
# # #         .affiliate-card { background: rgba(255,255,255,0.8); border: 1px dashed #cbd5e1; border-radius: 20px; padding: 24px; text-align: left; display: flex; align-items: center; gap: 18px; text-decoration: none; color: inherit; transition: 0.2s; }
        
# # #         .features { margin-top: 60px; width: 100%; }
# # #         .feature-grid { display: grid; grid-template-columns: 1fr; gap: 16px; margin-top: 24px; }
# # #         .feature-item { background: rgba(255,255,255,0.6); padding: 20px; border-radius: 12px; text-align: left; border: 1px solid #e2e8f0; }
# # #         .feature-item h3 { margin: 0 0 8px 0; font-size: 15px; font-weight: 700; }
# # #         .feature-item p { margin: 0; font-size: 13px; color: #64748b; }
        
# # #         footer { padding: 40px 20px; color: #cbd5e1; font-size: 12px; font-family: 'JetBrains Mono'; text-align: center; max-width: 600px; }
        
# # #         @media (max-width: 768px) {
# # #             h1 { font-size: 32px; }
# # #         }
# # #     </style>
    
# # #     <script>
# # #         // Lazy load Firebase only when needed
# # #         let firebaseLoaded = false;
# # #         function loadFirebase() {
# # #             if (firebaseLoaded) return Promise.resolve();
# # #             firebaseLoaded = true;
            
# # #             return Promise.all([
# # #                 new Promise((resolve) => {
# # #                     const script1 = document.createElement('script');
# # #                     script1.src = 'https://www.gstatic.com/firebasejs/9.6.1/firebase-app-compat.js';
# # #                     script1.onload = resolve;
# # #                     document.head.appendChild(script1);
# # #                 }),
# # #                 new Promise((resolve) => {
# # #                     const script2 = document.createElement('script');
# # #                     script2.src = 'https://www.gstatic.com/firebasejs/9.6.1/firebase-auth-compat.js';
# # #                     script2.onload = resolve;
# # #                     document.head.appendChild(script2);
# # #                 })
# # #             ]).then(() => {
# # #                 const firebaseConfig = {
# # #                     apiKey: "AIzaSyBZ_LmqF-RHh3RxCl39XhRfCm_mu7k-diQ",
# # #                     authDomain: "pdfbirch.firebaseapp.com",
# # #                     projectId: "pdfbirch",
# # #                     storageBucket: "pdfbirch.firebasestorage.app",
# # #                     messagingSenderId: "701712083387",
# # #                     appId: "1:701712083387:web:f438920e98b9831ea63c9e",
# # #                     measurementId: "G-RTZELQLMMZ"
# # #                 };
# # #                 firebase.initializeApp(firebaseConfig);
# # #                 return firebase.auth();
# # #             });
# # #         }
# # #     </script>
# # # </head>
# # # <body>
# # #     <div id="limit-modal">
# # #         <div class="modal-card">
# # #             <div style="font-size:40px; margin-bottom:20px;">🛡️</div>
# # #             <h2 style="margin:0; font-weight:800; font-size:20px;">Daily Quota Exhausted</h2>
# # #             <p style="font-size:14px; color:#64748b; margin:15px 0 25px;">
# # #                 You've reached the 20-file daily limit. Access resets in approximately <span id="time-left" style="font-weight:800; color:var(--primary);">--</span> minutes.
# # #             </p>
# # #             <button class="btn" onclick="location.reload()">Understood</button>
# # #         </div>
# # #     </div>

# # #     <div class="nav">
# # #         <a href="/" class="logo"><div class="dot" role="img" aria-label="Pdfbirch logo"></div>PDFBIRCH.APP</a>
# # #         <a href="https://www.buymeacoffee.com/YOUR_BMAC_USER" target="_blank" style="font-size: 13px; font-weight: 700; color: var(--muted); text-decoration: none;">☕ Support</a>
# # #     </div>

# # #     <div class="container">
# # #         <div id="user-badge" class="user-badge"><span id="user-email"></span></div>
        
# # #         <h1>Free Random PDF Generator</h1>
# # #         <h2>Generate Test Documents Instantly</h2>
# # #         <p>Create realistic test PDFs with randomized fonts, styles, and content. Perfect for development, QA testing, and placeholder documents.</p>
        
# # #         <button class="btn" id="login-btn" onclick="signIn()">Enter Engine</button>

# # #         <div id="engine-ui" style="display:none; width: 100%;">
# # #             <button class="btn" id="start-btn" onclick="startEngine()">Initialize Batch</button>

# # #             <div class="loader" id="loader">
# # #                 <div style="display:flex; justify-content:space-between; font-size:12px; font-family:'JetBrains Mono'; font-weight:700; color: #94a3b8;">
# # #                     <span>Hashing...</span><span id="pct">0%</span>
# # #                 </div>
# # #                 <div class="bar-bg"><div class="bar-fill" id="fill"></div></div>
# # #             </div>

# # #             <div class="results" id="results"></div>
# # #         </div>

# # #         <div class="features">
# # #             <h2 style="text-align: center;">Why Use Pdfbirch?</h2>
# # #             <div class="feature-grid">
# # #                 <div class="feature-item">
# # #                     <h3>🎨 Varied Fonts & Styles</h3>
# # #                     <p>Each PDF uses randomized fonts, sizes, and formatting for realistic test scenarios</p>
# # #                 </div>
# # #                 <div class="feature-item">
# # #                     <h3>⚡ Instant Generation</h3>
# # #                     <p>Generate multiple PDFs in seconds with a single click</p>
# # #                 </div>
# # #                 <div class="feature-item">
# # #                     <h3>🔒 Privacy-First</h3>
# # #                     <p>No data collection, no tracking. Your testing stays private</p>
# # #                 </div>
# # #             </div>
# # #         </div>

# # #         <div class="support-box">
# # #             <a href="https://www.grammarly.com/affiliates" target="_blank" class="affiliate-card">
# # #                 <div style="font-size: 24px;">✍️</div>
# # #                 <div style="flex:1">
# # #                     <div style="font-weight:800; font-size:15px;">Polish Your Real Documents</div>
# # #                     <div style="font-size:13px; color:#94a3b8;">Use Grammarly to check grammar and spelling in your actual work.</div>
# # #                 </div>
# # #                 <div>→</div>
# # #             </a>
# # #         </div>
# # #     </div>

# # #     <footer>
# # #         <div style="margin-bottom:20px; line-height:1.8; opacity:0.8;">
# # #             Free tool for developers and QA engineers. Generate random PDFs for testing pipelines, document parsers, and workflow automation.
# # #         </div>
# # #         <div style="opacity:0.6;">
# # #             &copy; 2026 Pdfbirch &bull; For Testing & Development
# # #         </div>
# # #     </footer>

# # #     <script>
# # #         let auth = null;

# # #         async function signIn() {
# # #             await loadFirebase();
# # #             auth = firebase.auth();
# # #             const provider = new firebase.auth.GoogleAuthProvider();
# # #             auth.signInWithPopup(provider).catch(e => console.error(e));
            
# # #             auth.onAuthStateChanged(user => {
# # #                 if (user) {
# # #                     document.getElementById('login-btn').style.display = 'none';
# # #                     document.getElementById('engine-ui').style.display = 'block';
# # #                     document.getElementById('user-badge').style.display = 'inline-flex';
# # #                     document.getElementById('user-email').innerText = user.email;
# # #                 }
# # #             });
# # #         }

# # #         async function startEngine() {
# # #             const user = auth.currentUser;
# # #             if (!user) return;

# # #             const token = await user.getIdToken();

# # #             const res = await fetch('/api/check_limit', {
# # #                 headers: { 'Authorization': 'Bearer ' + token }
# # #             });
# # #             const data = await res.json();

# # #             if (!data.allowed) {
# # #                 document.getElementById('time-left').innerText = data.wait_time || 'N/A';
# # #                 document.getElementById('limit-modal').style.display = 'flex';
# # #                 return;
# # #             }

# # #             document.getElementById('start-btn').style.display='none';
# # #             document.getElementById('loader').style.display='block';
# # #             let w=0; 
# # #             const f=document.getElementById('fill'), p=document.getElementById('pct');
# # #             const t=setInterval(()=>{
# # #                 w++; 
# # #                 f.style.width=w+'%'; 
# # #                 p.innerText=w+'%';
# # #                 if(w>=100){ 
# # #                     clearInterval(t); 
# # #                     document.getElementById('loader').style.display='none'; 
# # #                     showResults(token);
# # #                 }
# # #             }, 600);
# # #         }

# # #         async function downloadPDF(token, filename) {
# # #             try {
# # #                 const res = await fetch('/api/download', {
# # #                     method: 'POST',
# # #                     headers: {
# # #                         'Authorization': 'Bearer ' + token,
# # #                         'Content-Type': 'application/json'
# # #                     }
# # #                 });

# # #                 if (res.status === 429) {
# # #                     alert('Daily quota reached!');
# # #                     location.reload();
# # #                     return;
# # #                 }

# # #                 if (!res.ok) {
# # #                     alert('Download failed. Please try again.');
# # #                     return;
# # #                 }

# # #                 const blob = await res.blob();
# # #                 const url = window.URL.createObjectURL(blob);
# # #                 const a = document.createElement('a');
# # #                 a.href = url;
# # #                 a.download = filename;
# # #                 document.body.appendChild(a);
# # #                 a.click();
# # #                 a.remove();
# # #                 window.URL.revokeObjectURL(url);
# # #             } catch(e) {
# # #                 console.error(e);
# # #                 alert('Download error');
# # #             }
# # #         }

# # #         function showResults(token) {
# # #             const files = [
# # #                 'Research_Analysis_K7M2.pdf',
# # #                 'Draft_Final_X8N4.pdf',
# # #                 'Project_Report_B3L9.pdf',
# # #                 'Case_Study_Thesis_A1C6.pdf',
# # #                 'Final_Project_T5R8.pdf'
# # #             ];

# # #             const resultsDiv = document.getElementById('results');
# # #             resultsDiv.innerHTML = files.map(f => 
# # #                 `<div class="file-link" onclick="downloadPDF('${token}', '${f}')"><span>${f}</span><span>↓</span></div>`
# # #             ).join('') + 
# # #             '<button class="btn" onclick="location.reload()" style="background:none; color:var(--primary); box-shadow:none; border:1px solid #e2e8f0; margin-top:20px;">Refresh Batch</button>';
# # #             resultsDiv.style.display = 'block';
# # #         }
# # #     </script>
# # # </body>
# # # </html>
# # # """

# # # # --- THE BACKEND ---
# # # PREFIXES = ["Research", "Analysis", "Draft", "Final", "Project", "Report", "Case_Study", "Thesis"]
# # # WORDS = ["strategy", "growth", "market", "value", "user", "product", "system", "data", "cloud", "AI", "project", "scale"]

# # # @app.route('/')
# # # def home(): 
# # #     return HTML_PAGE

# # # @app.route('/robots.txt')
# # # def robots():
# # #     return """User-agent: *
# # # Allow: /
# # # Sitemap: https://pdfbirch.app/sitemap.xml

# # # User-agent: GPTBot
# # # Disallow: /

# # # User-agent: CCBot
# # # Disallow: /""", 200, {'Content-Type': 'text/plain'}

# # # @app.route('/sitemap.xml')
# # # def sitemap():
# # #     return """<?xml version="1.0" encoding="UTF-8"?>
# # # <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
# # #   <url>
# # #     <loc>https://pdfbirch.app</loc>
# # #     <lastmod>2026-02-07</lastmod>
# # #     <changefreq>weekly</changefreq>
# # #     <priority>1.0</priority>
# # #   </url>
# # # </urlset>""", 200, {'Content-Type': 'application/xml'}

# # # @app.route('/api/check_limit')
# # # def check_limit():
# # #     """Check if user has quota left - DOES NOT increment counter"""
# # #     token = request.headers.get('Authorization')
# # #     if not token:
# # #         return jsonify({"allowed": False, "error": "No token"}), 401
    
# # #     email = verify_firebase_token(token.replace('Bearer ', ''))
# # #     if not email:
# # #         return jsonify({"allowed": False, "error": "Invalid token"}), 401
    
# # #     count = get_user_download_count(email)
    
# # #     if count >= MAX_PDFS:
# # #         wait_time = get_time_until_reset(email)
# # #         return jsonify({"allowed": False, "wait_time": wait_time})
    
# # #     return jsonify({"allowed": True})

# # # @app.route('/api/download', methods=['POST'])
# # # def download():
# # #     """Download PDF - INCREMENTS counter on actual download"""
# # #     token = request.headers.get('Authorization')
# # #     if not token:
# # #         return "Unauthorized", 401
    
# # #     email = verify_firebase_token(token.replace('Bearer ', ''))
# # #     if not email:
# # #         return "Unauthorized", 401
    
# # #     count = get_user_download_count(email)
    
# # #     if count >= MAX_PDFS:
# # #         return "Quota exceeded", 429
    
# # #     # Record download in database
# # #     if not record_download(email):
# # #         return "Database error", 500
    
# # #     # Generate and return PDF
# # #     buf = gen_pdf_content()
# # #     buf.seek(0)
# # #     name = f"{random.choice(PREFIXES)}_{random.choice(PREFIXES)}_{''.join(random.choices(string.ascii_uppercase+string.digits, k=4))}.pdf"
# # #     return make_response(send_file(buf, as_attachment=True, download_name=name, mimetype='application/pdf'))

# # # def gen_pdf_content():
# # #     """Generate PDF with randomized fonts, sizes, and styles"""
# # #     pdf = FPDF()
# # #     pdf.set_auto_page_break(auto=True, margin=15)
    
# # #     for page_num in range(10):
# # #         pdf.add_page()
        
# # #         for line_num in range(25):
# # #             # Randomize font, style, and size for EACH line
# # #             family = random.choice(['Arial', 'Times', 'Courier'])
# # #             style = random.choice(['', 'B', 'I', 'BI'])
# # #             size = random.randint(10, 14)
            
# # #             pdf.set_font(family, style, size)
            
# # #             # Generate random sentence
# # #             line = " ".join(random.choice(WORDS) for _ in range(random.randint(10, 20))).capitalize() + "."
# # #             pdf.multi_cell(0, 10, line, align='L')
            
# # #             # Anti-Detector Noise
# # #             pdf.set_text_color(255, 255, 255)
# # #             pdf.set_font('Arial', '', 6)
# # #             noise = ''.join(random.choices(string.ascii_letters + string.digits, k=15))
# # #             pdf.cell(0, 5, noise, ln=1)
# # #             pdf.set_text_color(0, 0, 0)
    
# # #     return io.BytesIO(pdf.output(dest='S').encode('latin-1'))

# # # if __name__ == '__main__':
# # #     app.run(debug=True)












# # # # from flask import Flask, send_file, make_response, request, jsonify
# # # # from fpdf import FPDF
# # # # import random, string, io, time
# # # # import os
# # # # import json
# # # # import firebase_admin
# # # # from firebase_admin import credentials, auth as firebase_auth
# # # # import psycopg2
# # # # from psycopg2.extras import RealDictCursor
# # # # from datetime import datetime, timedelta

# # # # app = Flask(__name__)

# # # # # Initialize Firebase Admin
# # # # service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT')
# # # # if service_account_json:
# # # #     cred_dict = json.loads(service_account_json)
# # # #     cred = credentials.Certificate(cred_dict)
# # # #     firebase_admin.initialize_app(cred)

# # # # # Database connection
# # # # DATABASE_URL = os.getenv('DATABASE_URL')

# # # # def get_db_connection():
# # # #     """Create database connection"""
# # # #     return psycopg2.connect(DATABASE_URL, sslmode='require')

# # # # def init_db():
# # # #     """Initialize database table if it doesn't exist"""
# # # #     try:
# # # #         conn = get_db_connection()
# # # #         cur = conn.cursor()
# # # #         cur.execute('''
# # # #             CREATE TABLE IF NOT EXISTS user_downloads (
# # # #                 id SERIAL PRIMARY KEY,
# # # #                 email VARCHAR(255) NOT NULL,
# # # #                 download_time TIMESTAMP NOT NULL,
# # # #                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# # # #             )
# # # #         ''')
# # # #         cur.execute('CREATE INDEX IF NOT EXISTS idx_email ON user_downloads(email)')
# # # #         cur.execute('CREATE INDEX IF NOT EXISTS idx_download_time ON user_downloads(download_time)')
# # # #         conn.commit()
# # # #         cur.close()
# # # #         conn.close()
# # # #     except Exception as e:
# # # #         print(f"Database init error: {e}")

# # # # # Initialize database on startup
# # # # init_db()

# # # # # Config
# # # # MAX_PDFS = 20
# # # # WINDOW_HOURS = 24

# # # # def verify_firebase_token(token):
# # # #     """Verify Firebase ID token and return email if valid"""
# # # #     try:
# # # #         decoded_token = firebase_auth.verify_id_token(token)
# # # #         return decoded_token.get('email')
# # # #     except:
# # # #         return None

# # # # def get_user_download_count(email):
# # # #     """Get number of downloads in the last 24 hours"""
# # # #     try:
# # # #         conn = get_db_connection()
# # # #         cur = conn.cursor()
# # # #         cutoff_time = datetime.now() - timedelta(hours=WINDOW_HOURS)
# # # #         cur.execute(
# # # #             'SELECT COUNT(*) FROM user_downloads WHERE email = %s AND download_time > %s',
# # # #             (email, cutoff_time)
# # # #         )
# # # #         count = cur.fetchone()[0]
# # # #         cur.close()
# # # #         conn.close()
# # # #         return count
# # # #     except Exception as e:
# # # #         print(f"Database error: {e}")
# # # #         return 0

# # # # def record_download(email):
# # # #     """Record a download for the user"""
# # # #     try:
# # # #         conn = get_db_connection()
# # # #         cur = conn.cursor()
# # # #         cur.execute(
# # # #             'INSERT INTO user_downloads (email, download_time) VALUES (%s, %s)',
# # # #             (email, datetime.now())
# # # #         )
# # # #         conn.commit()
# # # #         cur.close()
# # # #         conn.close()
# # # #         return True
# # # #     except Exception as e:
# # # #         print(f"Database error: {e}")
# # # #         return False

# # # # def get_time_until_reset(email):
# # # #     """Get minutes until oldest download expires"""
# # # #     try:
# # # #         conn = get_db_connection()
# # # #         cur = conn.cursor()
# # # #         cutoff_time = datetime.now() - timedelta(hours=WINDOW_HOURS)
# # # #         cur.execute(
# # # #             'SELECT download_time FROM user_downloads WHERE email = %s AND download_time > %s ORDER BY download_time ASC LIMIT 1',
# # # #             (email, cutoff_time)
# # # #         )
# # # #         result = cur.fetchone()
# # # #         cur.close()
# # # #         conn.close()
        
# # # #         if result:
# # # #             oldest = result[0]
# # # #             reset_time = oldest + timedelta(hours=WINDOW_HOURS)
# # # #             minutes = int((reset_time - datetime.now()).total_seconds() / 60) + 1
# # # #             return max(1, minutes)
# # # #         return 0
# # # #     except Exception as e:
# # # #         print(f"Database error: {e}")
# # # #         return 0

# # # # # --- THE FRONTEND ---
# # # # HTML_PAGE = """
# # # # <!DOCTYPE html>
# # # # <html lang="en">
# # # # <head>
# # # #     <meta charset="UTF-8">
# # # #     <meta name="viewport" content="width=device-width, initial-scale=1.0">
# # # #    <title>Free PDF Generator - Random Test Documents | Pdfbirch</title>
# # # # <meta name="description" content="Generate random PDFs instantly. Free online PDF maker with realistic content & varied fonts. Perfect for testing, development, placeholder documents. No signup for preview, 20 free daily with Google login.">
# # # # <meta name="keywords" content="pdf generator, random pdf, test documents, fake pdf, pdf maker, document generator, placeholder pdf, development tools">
# # # # <meta name="author" content="Pdfbirch">
# # # # <meta name="robots" content="index, follow">
# # # # <meta property="og:title" content="Free Random PDF Generator - Pdfbirch">
# # # # <meta property="og:description" content="Generate realistic test PDFs with varied fonts and content. Free online document generator for developers.">
# # # # <meta property="og:type" content="website">
# # # # <meta property="og:url" content="https://pdfbirch.app">
# # # # <meta property="og:site_name" content="Pdfbirch">
# # # # <meta name="twitter:card" content="summary_large_image">
# # # # <meta name="twitter:title" content="Free Random PDF Generator - Pdfbirch">
# # # # <meta name="twitter:description" content="Generate realistic test PDFs instantly. Perfect for testing and development.">

# # # # <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-app-compat.js"></script>
# # # # <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-auth-compat.js"></script>

# # # # <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
# # # #     <style>
# # # #         :root { --bg: #f8fafc; --primary: #0f172a; --accent: #22c55e; --muted: #94a3b8; }
# # # #         body { margin: 0; font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg); display: flex; flex-direction: column; align-items: center; min-height: 100vh; color: var(--primary); background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 32px 32px; }
        
# # # #         .nav { width: 100%; max-width: 1100px; padding: 40px 20px; box-sizing: border-box; display: flex; justify-content: space-between; align-items: center; }
# # # #         .logo { display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 15px; text-decoration: none; color: inherit; }
# # # #         .dot { width: 8px; height: 8px; background: var(--accent); border-radius: 50%; }

# # # #         .container { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; max-width: 500px; padding: 0 20px; box-sizing: border-box; text-align: center; }
# # # #         h1 { font-size: 42px; font-weight: 800; letter-spacing: -2px; margin: 0 0 16px 0; line-height: 1; }
# # # #         p { color: #64748b; font-size: 16px; line-height: 1.6; margin-bottom: 40px; }
        
# # # #         .btn { background: var(--primary); color: white; border: none; padding: 22px; width: 100%; border-radius: 18px; font-weight: 700; font-size: 16px; cursor: pointer; transition: 0.2s; box-shadow: 0 10px 25px -5px rgba(15,23,42,0.2); }
# # # #         .btn:hover { transform: translateY(-2px); box-shadow: 0 20px 35px -10px rgba(15,23,42,0.3); }

# # # #         .user-badge { display: none; background: #fff; padding: 8px 16px; border-radius: 30px; border: 1px solid #e2e8f0; font-size: 12px; font-weight: 700; margin-bottom: 20px; }

# # # #         .loader { margin-top: 40px; display: none; width: 100%; }
# # # #         .bar-bg { background: #f1f5f9; height: 10px; border-radius: 10px; overflow: hidden; margin-top: 15px; }
# # # #         .bar-fill { background: var(--primary); height: 100%; width: 0%; transition: width 0.3s linear; }
        
# # # #         .results { margin-top: 40px; display: none; width: 100%; }
# # # #         .file-link { display: flex; justify-content: space-between; padding: 20px; background: rgba(255,255,255,0.8); border: 1px solid #e2e8f0; border-radius: 16px; color: var(--primary); font-weight: 700; font-size: 14px; margin-bottom: 12px; cursor: pointer; transition: 0.2s; }
# # # #         .file-link:hover { border-color: var(--primary); background: #fff; transform: scale(1.02); }

# # # #         #limit-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15,23,42,0.9); z-index: 1000; backdrop-filter: blur(8px); align-items: center; justify-content: center; }
# # # #         .modal-card { background: white; padding: 40px; border-radius: 24px; max-width: 320px; text-align: center; }

# # # #         .support-box { margin-top: 80px; padding-top: 40px; border-top: 1px solid #f1f5f9; width: 100%; }
# # # #         .affiliate-card { background: rgba(255,255,255,0.8); border: 1px dashed #cbd5e1; border-radius: 20px; padding: 24px; text-align: left; display: flex; align-items: center; gap: 18px; text-decoration: none; color: inherit; transition: 0.2s; }
        
# # # #         footer { padding: 40px; color: #cbd5e1; font-size: 12px; font-family: 'JetBrains Mono'; opacity: 0.7; }
# # # #     </style>
# # # # </head>
# # # # <body>
# # # #     <div id="limit-modal">
# # # #         <div class="modal-card">
# # # #             <div style="font-size:40px; margin-bottom:20px;">🛡️</div>
# # # #             <h2 style="margin:0; font-weight:800; font-size:20px;">Daily Quota Exhausted</h2>
# # # #             <p style="font-size:14px; color:#64748b; margin:15px 0 25px;">
# # # #                 You've reached the 20-file daily limit. Access resets in approximately <span id="time-left" style="font-weight:800; color:var(--primary);">--</span> minutes.
# # # #             </p>
# # # #             <button class="btn" onclick="location.reload()">Understood</button>
# # # #         </div>
# # # #     </div>

# # # #     <div class="nav">
# # # #         <a href="/" class="logo"><div class="dot"></div>PDFBIRCH.APP</a>
# # # #         <a href="https://www.buymeacoffee.com/YOUR_BMAC_USER" target="_blank" style="font-size: 13px; font-weight: 700; color: var(--muted); text-decoration: none;">☕ Support</a>
# # # #     </div>

# # # #     <div class="container">
# # # #         <div id="user-badge" class="user-badge"><span id="user-email"></span></div>
# # # #         <h1>Free Random PDF Generator</h1>
# # # #         <p>Generate realistic test PDFs with randomized fonts, styles, and content. Perfect for development, QA testing, and placeholder documents.</p>
        
# # # #         <button class="btn" id="login-btn" onclick="signIn()">Enter Engine</button>

# # # #         <div id="engine-ui" style="display:none; width: 100%;">
# # # #             <button class="btn" id="start-btn" onclick="startEngine()">Initialize Batch</button>

# # # #             <div class="loader" id="loader">
# # # #                 <div style="display:flex; justify-content:space-between; font-size:12px; font-family:'JetBrains Mono'; font-weight:700; color: #94a3b8;">
# # # #                     <span>Hashing...</span><span id="pct">0%</span>
# # # #                 </div>
# # # #                 <div class="bar-bg"><div class="bar-fill" id="fill"></div></div>
# # # #             </div>

# # # #             <div class="results" id="results"></div>
# # # #         </div>

# # # #         <div class="support-box">
# # # #             <a href="https://www.grammarly.com/affiliates" target="_blank" class="affiliate-card">
# # # #                 <div style="font-size: 24px;">🛡️</div>
# # # #                 <div style="flex:1">
# # # #                     <div style="font-weight:800; font-size:15px;">Verify Your Content</div>
# # # #                     <div style="font-size:13px; color:#94a3b8;">Use Grammarly to check your academic documents.</div>
# # # #                 </div>
# # # #                 <div>→</div>
# # # #             </a>
# # # #         </div>
# # # #     </div>

# # # #     <footer>
# # # #     <div style="max-width:700px; margin:0 auto 20px auto; text-align:center; color:#94a3b8; font-size:12px; line-height:1.8;">
# # # #         <strong style="color:#64748b;">Free PDF Generator Tools:</strong><br>
# # # #         Random PDF Generator • Test Document Creator • Fake PDF Maker • Online Document Generator • 
# # # #         Placeholder PDF Creator • Development Test Files • QA Testing Documents • Privacy-First PDF Tools
# # # #     </div>
# # # #     <div style="color:#cbd5e1; font-size:11px; opacity:0.7;">
# # # #         &copy; 2026 Pdfbirch &bull; For Testing & Development Purposes
# # # #     </div>
# # # # </footer>

# # # #     <script>
# # # #         const firebaseConfig = {
# # # #             apiKey: "AIzaSyBZ_LmqF-RHh3RxCl39XhRfCm_mu7k-diQ",
# # # #             authDomain: "pdfbirch.firebaseapp.com",
# # # #             projectId: "pdfbirch",
# # # #             storageBucket: "pdfbirch.firebasestorage.app",
# # # #             messagingSenderId: "701712083387",
# # # #             appId: "1:701712083387:web:f438920e98b9831ea63c9e",
# # # #             measurementId: "G-RTZELQLMMZ"
# # # #         };
# # # #         firebase.initializeApp(firebaseConfig);
# # # #         const auth = firebase.auth();

# # # #         function signIn() {
# # # #             const provider = new firebase.auth.GoogleAuthProvider();
# # # #             auth.signInWithPopup(provider).catch(e => console.error(e));
# # # #         }

# # # #         auth.onAuthStateChanged(user => {
# # # #             if (user) {
# # # #                 document.getElementById('login-btn').style.display = 'none';
# # # #                 document.getElementById('engine-ui').style.display = 'block';
# # # #                 document.getElementById('user-badge').style.display = 'inline-flex';
# # # #                 document.getElementById('user-email').innerText = user.email;
# # # #             }
# # # #         });

# # # #         async function startEngine() {
# # # #             const user = auth.currentUser;
# # # #             if (!user) return;

# # # #             const token = await user.getIdToken();

# # # #             const res = await fetch('/api/check_limit', {
# # # #                 headers: { 'Authorization': 'Bearer ' + token }
# # # #             });
# # # #             const data = await res.json();

# # # #             if (!data.allowed) {
# # # #                 document.getElementById('time-left').innerText = data.wait_time || 'N/A';
# # # #                 document.getElementById('limit-modal').style.display = 'flex';
# # # #                 return;
# # # #             }

# # # #             document.getElementById('start-btn').style.display='none';
# # # #             document.getElementById('loader').style.display='block';
# # # #             let w=0; 
# # # #             const f=document.getElementById('fill'), p=document.getElementById('pct');
# # # #             const t=setInterval(()=>{
# # # #                 w++; 
# # # #                 f.style.width=w+'%'; 
# # # #                 p.innerText=w+'%';
# # # #                 if(w>=100){ 
# # # #                     clearInterval(t); 
# # # #                     document.getElementById('loader').style.display='none'; 
# # # #                     showResults(token);
# # # #                 }
# # # #             }, 600);
# # # #         }

# # # #         async function downloadPDF(token, filename) {
# # # #             try {
# # # #                 const res = await fetch('/api/download', {
# # # #                     method: 'POST',
# # # #                     headers: {
# # # #                         'Authorization': 'Bearer ' + token,
# # # #                         'Content-Type': 'application/json'
# # # #                     }
# # # #                 });

# # # #                 if (res.status === 429) {
# # # #                     alert('Daily quota reached!');
# # # #                     location.reload();
# # # #                     return;
# # # #                 }

# # # #                 if (!res.ok) {
# # # #                     alert('Download failed. Please try again.');
# # # #                     return;
# # # #                 }

# # # #                 const blob = await res.blob();
# # # #                 const url = window.URL.createObjectURL(blob);
# # # #                 const a = document.createElement('a');
# # # #                 a.href = url;
# # # #                 a.download = filename;
# # # #                 document.body.appendChild(a);
# # # #                 a.click();
# # # #                 a.remove();
# # # #                 window.URL.revokeObjectURL(url);
# # # #             } catch(e) {
# # # #                 console.error(e);
# # # #                 alert('Download error');
# # # #             }
# # # #         }

# # # #         function showResults(token) {
# # # #             const files = [
# # # #                 'Research_Analysis_K7M2.pdf',
# # # #                 'Draft_Final_X8N4.pdf',
# # # #                 'Project_Report_B3L9.pdf',
# # # #                 'Case_Study_Thesis_A1C6.pdf',
# # # #                 'Final_Project_T5R8.pdf'
# # # #             ];

# # # #             const resultsDiv = document.getElementById('results');
# # # #             resultsDiv.innerHTML = files.map(f => 
# # # #                 `<div class="file-link" onclick="downloadPDF('${token}', '${f}')"><span>${f}</span><span>↓</span></div>`
# # # #             ).join('') + 
# # # #             '<button class="btn" onclick="location.reload()" style="background:none; color:var(--primary); box-shadow:none; border:1px solid #e2e8f0; margin-top:20px;">Refresh Batch</button>';
# # # #             resultsDiv.style.display = 'block';
# # # #         }
# # # #     </script>
# # # # </body>
# # # # </html>
# # # # """

# # # # # --- THE BACKEND ---
# # # # PREFIXES = ["Research", "Analysis", "Draft", "Final", "Project", "Report", "Case_Study", "Thesis"]
# # # # WORDS = ["strategy", "growth", "market", "value", "user", "product", "system", "data", "cloud", "AI", "project", "scale"]

# # # # @app.route('/')
# # # # def home(): 
# # # #     return HTML_PAGE

# # # # @app.route('/api/check_limit')
# # # # def check_limit():
# # # #     """Check if user has quota left - DOES NOT increment counter"""
# # # #     token = request.headers.get('Authorization')
# # # #     if not token:
# # # #         return jsonify({"allowed": False, "error": "No token"}), 401
    
# # # #     email = verify_firebase_token(token.replace('Bearer ', ''))
# # # #     if not email:
# # # #         return jsonify({"allowed": False, "error": "Invalid token"}), 401
    
# # # #     count = get_user_download_count(email)
    
# # # #     if count >= MAX_PDFS:
# # # #         wait_time = get_time_until_reset(email)
# # # #         return jsonify({"allowed": False, "wait_time": wait_time})
    
# # # #     return jsonify({"allowed": True})

# # # # @app.route('/api/download', methods=['POST'])
# # # # def download():
# # # #     """Download PDF - INCREMENTS counter on actual download"""
# # # #     token = request.headers.get('Authorization')
# # # #     if not token:
# # # #         return "Unauthorized", 401
    
# # # #     email = verify_firebase_token(token.replace('Bearer ', ''))
# # # #     if not email:
# # # #         return "Unauthorized", 401
    
# # # #     count = get_user_download_count(email)
    
# # # #     if count >= MAX_PDFS:
# # # #         return "Quota exceeded", 429
    
# # # #     # Record download in database
# # # #     if not record_download(email):
# # # #         return "Database error", 500
    
# # # #     # Generate and return PDF
# # # #     buf = gen_pdf_content()
# # # #     buf.seek(0)
# # # #     name = f"{random.choice(PREFIXES)}_{random.choice(PREFIXES)}_{''.join(random.choices(string.ascii_uppercase+string.digits, k=4))}.pdf"
# # # #     return make_response(send_file(buf, as_attachment=True, download_name=name, mimetype='application/pdf'))

# # # # def gen_pdf_content():
# # # #     """Generate PDF with randomized fonts, sizes, and styles"""
# # # #     pdf = FPDF()
# # # #     pdf.set_auto_page_break(auto=True, margin=15)
    
# # # #     for page_num in range(10):
# # # #         pdf.add_page()
        
# # # #         for line_num in range(25):
# # # #             # Randomize font, style, and size for EACH line
# # # #             family = random.choice(['Arial', 'Times', 'Courier'])
# # # #             style = random.choice(['', 'B', 'I', 'BI'])
# # # #             size = random.randint(10, 14)
            
# # # #             pdf.set_font(family, style, size)
            
# # # #             # Generate random sentence
# # # #             line = " ".join(random.choice(WORDS) for _ in range(random.randint(10, 20))).capitalize() + "."
# # # #             pdf.multi_cell(0, 10, line, align='L')
            
# # # #             # Anti-Detector Noise
# # # #             pdf.set_text_color(255, 255, 255)
# # # #             pdf.set_font('Arial', '', 6)
# # # #             noise = ''.join(random.choices(string.ascii_letters + string.digits, k=15))
# # # #             pdf.cell(0, 5, noise, ln=1)
# # # #             pdf.set_text_color(0, 0, 0)
    
# # # #     return io.BytesIO(pdf.output(dest='S').encode('latin-1'))

# # # # app.debug = True












# # # # # from flask import Flask, send_file, make_response, request, jsonify
# # # # # from fpdf import FPDF
# # # # # import random, string, io, time
# # # # # import os
# # # # # import json
# # # # # import firebase_admin
# # # # # from firebase_admin import credentials, auth as firebase_auth

# # # # # app = Flask(__name__)

# # # # # # Initialize Firebase Admin
# # # # # service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT')
# # # # # if service_account_json:
# # # # #     cred_dict = json.loads(service_account_json)
# # # # #     cred = credentials.Certificate(cred_dict)
# # # # #     firebase_admin.initialize_app(cred)

# # # # # # --- THE HARD CAP CONFIG ---
# # # # # USER_HISTORY = {}
# # # # # MAX_PDFS = 20
# # # # # WINDOW_SECONDS = 86400  # Exactly 24 Hours

# # # # # # Helper function to verify Firebase tokens
# # # # # def verify_firebase_token(token):
# # # # #     """Verify Firebase ID token and return email if valid"""
# # # # #     try:
# # # # #         decoded_token = firebase_auth.verify_id_token(token)
# # # # #         return decoded_token.get('email')
# # # # #     except:
# # # # #         return None

# # # # # # --- 1. THE FRONTEND ---
# # # # # HTML_PAGE = """
# # # # # <!DOCTYPE html>
# # # # # <html lang="en">
# # # # # <head>
# # # # #     <meta charset="UTF-8">
# # # # #     <meta name="viewport" content="width=device-width, initial-scale=1.0">
# # # # #     <title>Pdfbirch | Privacy Engine</title>
    
# # # # #     <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-app-compat.js"></script>
# # # # #     <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-auth-compat.js"></script>

# # # # #     <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
# # # # #     <style>
# # # # #         :root { --bg: #f8fafc; --primary: #0f172a; --accent: #22c55e; --muted: #94a3b8; }
# # # # #         body { margin: 0; font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg); display: flex; flex-direction: column; align-items: center; min-height: 100vh; color: var(--primary); background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 32px 32px; }
        
# # # # #         .nav { width: 100%; max-width: 1100px; padding: 40px 20px; box-sizing: border-box; display: flex; justify-content: space-between; align-items: center; }
# # # # #         .logo { display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 15px; text-decoration: none; color: inherit; }
# # # # #         .dot { width: 8px; height: 8px; background: var(--accent); border-radius: 50%; }

# # # # #         .container { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; max-width: 500px; padding: 0 20px; box-sizing: border-box; text-align: center; }
# # # # #         h1 { font-size: 42px; font-weight: 800; letter-spacing: -2px; margin: 0 0 16px 0; line-height: 1; }
# # # # #         p { color: #64748b; font-size: 16px; line-height: 1.6; margin-bottom: 40px; }
        
# # # # #         .btn { background: var(--primary); color: white; border: none; padding: 22px; width: 100%; border-radius: 18px; font-weight: 700; font-size: 16px; cursor: pointer; transition: 0.2s; box-shadow: 0 10px 25px -5px rgba(15,23,42,0.2); }
# # # # #         .btn:hover { transform: translateY(-2px); box-shadow: 0 20px 35px -10px rgba(15,23,42,0.3); }

# # # # #         .user-badge { display: none; background: #fff; padding: 8px 16px; border-radius: 30px; border: 1px solid #e2e8f0; font-size: 12px; font-weight: 700; margin-bottom: 20px; }

# # # # #         .loader { margin-top: 40px; display: none; width: 100%; }
# # # # #         .bar-bg { background: #f1f5f9; height: 10px; border-radius: 10px; overflow: hidden; margin-top: 15px; }
# # # # #         .bar-fill { background: var(--primary); height: 100%; width: 0%; transition: width 0.3s linear; }
        
# # # # #         .results { margin-top: 40px; display: none; width: 100%; }
# # # # #         .file-link { display: flex; justify-content: space-between; padding: 20px; background: rgba(255,255,255,0.8); border: 1px solid #e2e8f0; border-radius: 16px; color: var(--primary); font-weight: 700; font-size: 14px; margin-bottom: 12px; cursor: pointer; transition: 0.2s; }
# # # # #         .file-link:hover { border-color: var(--primary); background: #fff; transform: scale(1.02); }

# # # # #         #limit-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15,23,42,0.9); z-index: 1000; backdrop-filter: blur(8px); align-items: center; justify-content: center; }
# # # # #         .modal-card { background: white; padding: 40px; border-radius: 24px; max-width: 320px; text-align: center; }

# # # # #         .support-box { margin-top: 80px; padding-top: 40px; border-top: 1px solid #f1f5f9; width: 100%; }
# # # # #         .affiliate-card { background: rgba(255,255,255,0.8); border: 1px dashed #cbd5e1; border-radius: 20px; padding: 24px; text-align: left; display: flex; align-items: center; gap: 18px; text-decoration: none; color: inherit; transition: 0.2s; }
        
# # # # #         footer { padding: 40px; color: #cbd5e1; font-size: 12px; font-family: 'JetBrains Mono'; opacity: 0.7; }
# # # # #     </style>
# # # # # </head>
# # # # # <body>
# # # # #     <div id="limit-modal">
# # # # #         <div class="modal-card">
# # # # #             <div style="font-size:40px; margin-bottom:20px;">🛡️</div>
# # # # #             <h2 style="margin:0; font-weight:800; font-size:20px;">Daily Quota Exhausted</h2>
# # # # #             <p style="font-size:14px; color:#64748b; margin:15px 0 25px;">
# # # # #                 You've reached the 20-file daily limit. Access resets in approximately <span id="time-left" style="font-weight:800; color:var(--primary);">--</span> minutes.
# # # # #             </p>
# # # # #             <button class="btn" onclick="location.reload()">Understood</button>
# # # # #         </div>
# # # # #     </div>

# # # # #     <div class="nav">
# # # # #         <a href="/" class="logo"><div class="dot"></div>PDFBIRCH.APP</a>
# # # # #         <a href="https://www.buymeacoffee.com/YOUR_BMAC_USER" target="_blank" style="font-size: 13px; font-weight: 700; color: var(--muted); text-decoration: none;">☕ Support</a>
# # # # #     </div>

# # # # #     <div class="container">
# # # # #         <div id="user-badge" class="user-badge"><span id="user-email"></span></div>
# # # # #         <h1>Entropy Engine</h1>
# # # # #         <p>Advanced dataset generation for privacy research. Secure, limited-access mode active.</p>
        
# # # # #         <button class="btn" id="login-btn" onclick="signIn()">Enter Engine</button>

# # # # #         <div id="engine-ui" style="display:none; width: 100%;">
# # # # #             <button class="btn" id="start-btn" onclick="startEngine()">Initialize Batch</button>

# # # # #             <div class="loader" id="loader">
# # # # #                 <div style="display:flex; justify-content:space-between; font-size:12px; font-family:'JetBrains Mono'; font-weight:700; color: #94a3b8;">
# # # # #                     <span>Hashing...</span><span id="pct">0%</span>
# # # # #                 </div>
# # # # #                 <div class="bar-bg"><div class="bar-fill" id="fill"></div></div>
# # # # #             </div>

# # # # #             <div class="results" id="results"></div>
# # # # #         </div>

# # # # #         <div class="support-box">
# # # # #             <a href="https://www.grammarly.com/affiliates" target="_blank" class="affiliate-card">
# # # # #                 <div style="font-size: 24px;">🛡️</div>
# # # # #                 <div style="flex:1">
# # # # #                     <div style="font-weight:800; font-size:15px;">Verify Your Content</div>
# # # # #                     <div style="font-size:13px; color:#94a3b8;">Use Grammarly to check your academic documents.</div>
# # # # #                 </div>
# # # # #                 <div>→</div>
# # # # #             </a>
# # # # #         </div>
# # # # #     </div>

# # # # #     <footer>&copy; 2026 Pdfbirch &bull; 24h Security Window Active</footer>

# # # # #     <script>
# # # # #         const firebaseConfig = {
# # # # #             apiKey: "AIzaSyBZ_LmqF-RHh3RxCl39XhRfCm_mu7k-diQ",
# # # # #             authDomain: "pdfbirch.firebaseapp.com",
# # # # #             projectId: "pdfbirch",
# # # # #             storageBucket: "pdfbirch.firebasestorage.app",
# # # # #             messagingSenderId: "701712083387",
# # # # #             appId: "1:701712083387:web:f438920e98b9831ea63c9e",
# # # # #             measurementId: "G-RTZELQLMMZ"
# # # # #         };
# # # # #         firebase.initializeApp(firebaseConfig);
# # # # #         const auth = firebase.auth();

# # # # #         function signIn() {
# # # # #             const provider = new firebase.auth.GoogleAuthProvider();
# # # # #             auth.signInWithPopup(provider).catch(e => console.error(e));
# # # # #         }

# # # # #         auth.onAuthStateChanged(user => {
# # # # #             if (user) {
# # # # #                 document.getElementById('login-btn').style.display = 'none';
# # # # #                 document.getElementById('engine-ui').style.display = 'block';
# # # # #                 document.getElementById('user-badge').style.display = 'inline-flex';
# # # # #                 document.getElementById('user-email').innerText = user.email;
# # # # #             }
# # # # #         });

# # # # #         async function startEngine() {
# # # # #             const user = auth.currentUser;
# # # # #             if (!user) return;

# # # # #             const token = await user.getIdToken();

# # # # #             const res = await fetch('/api/check_limit', {
# # # # #                 headers: { 'Authorization': 'Bearer ' + token }
# # # # #             });
# # # # #             const data = await res.json();

# # # # #             if (!data.allowed) {
# # # # #                 document.getElementById('time-left').innerText = data.wait_time || 'N/A';
# # # # #                 document.getElementById('limit-modal').style.display = 'flex';
# # # # #                 return;
# # # # #             }

# # # # #             document.getElementById('start-btn').style.display='none';
# # # # #             document.getElementById('loader').style.display='block';
# # # # #             let w=0; 
# # # # #             const f=document.getElementById('fill'), p=document.getElementById('pct');
# # # # #             const t=setInterval(()=>{
# # # # #                 w++; 
# # # # #                 f.style.width=w+'%'; 
# # # # #                 p.innerText=w+'%';
# # # # #                 if(w>=100){ 
# # # # #                     clearInterval(t); 
# # # # #                     document.getElementById('loader').style.display='none'; 
# # # # #                     showResults(token);
# # # # #                 }
# # # # #             }, 600);
# # # # #         }

# # # # #         async function downloadPDF(token, filename) {
# # # # #             try {
# # # # #                 const res = await fetch('/api/download', {
# # # # #                     method: 'POST',
# # # # #                     headers: {
# # # # #                         'Authorization': 'Bearer ' + token,
# # # # #                         'Content-Type': 'application/json'
# # # # #                     }
# # # # #                 });

# # # # #                 if (res.status === 429) {
# # # # #                     alert('Daily quota reached!');
# # # # #                     location.reload();
# # # # #                     return;
# # # # #                 }

# # # # #                 if (!res.ok) {
# # # # #                     alert('Download failed. Please try again.');
# # # # #                     return;
# # # # #                 }

# # # # #                 const blob = await res.blob();
# # # # #                 const url = window.URL.createObjectURL(blob);
# # # # #                 const a = document.createElement('a');
# # # # #                 a.href = url;
# # # # #                 a.download = filename;
# # # # #                 document.body.appendChild(a);
# # # # #                 a.click();
# # # # #                 a.remove();
# # # # #                 window.URL.revokeObjectURL(url);
# # # # #             } catch(e) {
# # # # #                 console.error(e);
# # # # #                 alert('Download error');
# # # # #             }
# # # # #         }

# # # # #         function showResults(token) {
# # # # #             const files = [
# # # # #                 'Research_Analysis_K7M2.pdf',
# # # # #                 'Draft_Final_X8N4.pdf',
# # # # #                 'Project_Report_B3L9.pdf',
# # # # #                 'Case_Study_Thesis_A1C6.pdf',
# # # # #                 'Final_Project_T5R8.pdf'
# # # # #             ];

# # # # #             const resultsDiv = document.getElementById('results');
# # # # #             resultsDiv.innerHTML = files.map(f => 
# # # # #                 `<div class="file-link" onclick="downloadPDF('${token}', '${f}')"><span>${f}</span><span>↓</span></div>`
# # # # #             ).join('') + 
# # # # #             '<button class="btn" onclick="location.reload()" style="background:none; color:var(--primary); box-shadow:none; border:1px solid #e2e8f0; margin-top:20px;">Refresh Batch</button>';
# # # # #             resultsDiv.style.display = 'block';
# # # # #         }
# # # # #     </script>
# # # # # </body>
# # # # # </html>
# # # # # """

# # # # # # --- 2. THE BACKEND ---
# # # # # PREFIXES = ["Research", "Analysis", "Draft", "Final", "Project", "Report", "Case_Study", "Thesis"]
# # # # # WORDS = ["strategy", "growth", "market", "value", "user", "product", "system", "data", "cloud", "AI", "project", "scale"]

# # # # # @app.route('/')
# # # # # def home(): 
# # # # #     return HTML_PAGE

# # # # # @app.route('/api/check_limit')
# # # # # def check_limit():
# # # # #     """Check if user has quota left - DOES NOT increment counter"""
# # # # #     token = request.headers.get('Authorization')
# # # # #     if not token:
# # # # #         return jsonify({"allowed": False, "error": "No token"}), 401
    
# # # # #     email = verify_firebase_token(token.replace('Bearer ', ''))
# # # # #     if not email:
# # # # #         return jsonify({"allowed": False, "error": "Invalid token"}), 401
    
# # # # #     now = time.time()
# # # # #     if email not in USER_HISTORY: 
# # # # #         USER_HISTORY[email] = []
    
# # # # #     # Clean up old entries
# # # # #     USER_HISTORY[email] = [t for t in USER_HISTORY[email] if now - t < WINDOW_SECONDS]
    
# # # # #     if len(USER_HISTORY[email]) >= MAX_PDFS:
# # # # #         oldest = USER_HISTORY[email][0]
# # # # #         wait_m = int(((oldest + WINDOW_SECONDS) - now) // 60) + 1
# # # # #         return jsonify({"allowed": False, "wait_time": wait_m})
    
# # # # #     return jsonify({"allowed": True})

# # # # # @app.route('/api/download', methods=['POST'])
# # # # # def download():
# # # # #     """Download PDF - INCREMENTS counter on actual download"""
# # # # #     token = request.headers.get('Authorization')
# # # # #     if not token:
# # # # #         return "Unauthorized", 401
    
# # # # #     email = verify_firebase_token(token.replace('Bearer ', ''))
# # # # #     if not email:
# # # # #         return "Unauthorized", 401
    
# # # # #     now = time.time()
    
# # # # #     # Initialize if new user
# # # # #     if email not in USER_HISTORY:
# # # # #         USER_HISTORY[email] = []
    
# # # # #     # Clean up old entries
# # # # #     USER_HISTORY[email] = [t for t in USER_HISTORY[email] if now - t < WINDOW_SECONDS]
    
# # # # #     # Check quota
# # # # #     if len(USER_HISTORY[email]) >= MAX_PDFS:
# # # # #         return "Quota exceeded", 429
    
# # # # #     # INCREMENT COUNTER ON ACTUAL DOWNLOAD
# # # # #     USER_HISTORY[email].append(now)
    
# # # # #     # Generate and return PDF
# # # # #     buf = gen_pdf_content()
# # # # #     buf.seek(0)
# # # # #     name = f"{random.choice(PREFIXES)}_{random.choice(PREFIXES)}_{''.join(random.choices(string.ascii_uppercase+string.digits, k=4))}.pdf"
# # # # #     return make_response(send_file(buf, as_attachment=True, download_name=name, mimetype='application/pdf'))

# # # # # def gen_pdf_content():
# # # # #     """Generate PDF with randomized fonts, sizes, and styles"""
# # # # #     pdf = FPDF()
# # # # #     pdf.set_auto_page_break(auto=True, margin=15)
    
# # # # #     for page_num in range(10):
# # # # #         pdf.add_page()
        
# # # # #         for line_num in range(25):
# # # # #             # Randomize font, style, and size for EACH line
# # # # #             family = random.choice(['Arial', 'Times', 'Courier'])
# # # # #             style = random.choice(['', 'B', 'I', 'BI'])  # Normal, Bold, Italic, Bold+Italic
# # # # #             size = random.randint(10, 14)
            
# # # # #             pdf.set_font(family, style, size)
            
# # # # #             # Generate random sentence
# # # # #             line = " ".join(random.choice(WORDS) for _ in range(random.randint(10, 20))).capitalize() + "."
# # # # #             pdf.multi_cell(0, 10, line, align='L')
            
# # # # #             # Anti-Detector Noise (invisible white text)
# # # # #             pdf.set_text_color(255, 255, 255)
# # # # #             pdf.set_font('Arial', '', 6)
# # # # #             noise = ''.join(random.choices(string.ascii_letters + string.digits, k=15))
# # # # #             pdf.cell(0, 5, noise, ln=1)
# # # # #             pdf.set_text_color(0, 0, 0)  # Reset to black
    
# # # # #     return io.BytesIO(pdf.output(dest='S').encode('latin-1'))

# # # # # app.debug = True















# # # # # # from flask import Flask, send_file, make_response, request, jsonify
# # # # # # from fpdf import FPDF
# # # # # # import random, string, io, time
# # # # # # import os
# # # # # # import json
# # # # # # import firebase_admin
# # # # # # from firebase_admin import credentials, auth as firebase_auth

# # # # # # app = Flask(__name__)

# # # # # # # Initialize Firebase Admin
# # # # # # service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT')
# # # # # # if service_account_json:
# # # # # #     cred_dict = json.loads(service_account_json)
# # # # # #     cred = credentials.Certificate(cred_dict)
# # # # # #     firebase_admin.initialize_app(cred)

# # # # # # # --- THE HARD CAP CONFIG ---
# # # # # # USER_HISTORY = {}
# # # # # # MAX_PDFS = 20
# # # # # # WINDOW_SECONDS = 86400  # Exactly 24 Hours

# # # # # # # Helper function to verify Firebase tokens
# # # # # # def verify_firebase_token(token):
# # # # # #     """Verify Firebase ID token and return email if valid"""
# # # # # #     try:
# # # # # #         decoded_token = firebase_auth.verify_id_token(token)
# # # # # #         return decoded_token.get('email')
# # # # # #     except:
# # # # # #         return None

# # # # # # # --- 1. THE FRONTEND ---
# # # # # # HTML_PAGE = """
# # # # # # <!DOCTYPE html>
# # # # # # <html lang="en">
# # # # # # <head>
# # # # # #     <meta charset="UTF-8">
# # # # # #     <meta name="viewport" content="width=device-width, initial-scale=1.0">
# # # # # #     <title>Pdfbirch | Privacy Engine</title>
    
# # # # # #     <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-app-compat.js"></script>
# # # # # #     <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-auth-compat.js"></script>

# # # # # #     <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
# # # # # #     <style>
# # # # # #         :root { --bg: #f8fafc; --primary: #0f172a; --accent: #22c55e; --muted: #94a3b8; }
# # # # # #         body { margin: 0; font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg); display: flex; flex-direction: column; align-items: center; min-height: 100vh; color: var(--primary); background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 32px 32px; }
        
# # # # # #         .nav { width: 100%; max-width: 1100px; padding: 40px 20px; box-sizing: border-box; display: flex; justify-content: space-between; align-items: center; }
# # # # # #         .logo { display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 15px; text-decoration: none; color: inherit; }
# # # # # #         .dot { width: 8px; height: 8px; background: var(--accent); border-radius: 50%; }

# # # # # #         .container { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; max-width: 500px; padding: 0 20px; box-sizing: border-box; text-align: center; }
# # # # # #         h1 { font-size: 42px; font-weight: 800; letter-spacing: -2px; margin: 0 0 16px 0; line-height: 1; }
# # # # # #         p { color: #64748b; font-size: 16px; line-height: 1.6; margin-bottom: 40px; }
        
# # # # # #         .btn { background: var(--primary); color: white; border: none; padding: 22px; width: 100%; border-radius: 18px; font-weight: 700; font-size: 16px; cursor: pointer; transition: 0.2s; box-shadow: 0 10px 25px -5px rgba(15,23,42,0.2); }
# # # # # #         .btn:hover { transform: translateY(-2px); box-shadow: 0 20px 35px -10px rgba(15,23,42,0.3); }

# # # # # #         .user-badge { display: none; background: #fff; padding: 8px 16px; border-radius: 30px; border: 1px solid #e2e8f0; font-size: 12px; font-weight: 700; margin-bottom: 20px; }

# # # # # #         .loader { margin-top: 40px; display: none; width: 100%; }
# # # # # #         .bar-bg { background: #f1f5f9; height: 10px; border-radius: 10px; overflow: hidden; margin-top: 15px; }
# # # # # #         .bar-fill { background: var(--primary); height: 100%; width: 0%; transition: width 0.3s linear; }
        
# # # # # #         .results { margin-top: 40px; display: none; width: 100%; }
# # # # # #         .file-link { display: flex; justify-content: space-between; padding: 20px; background: rgba(255,255,255,0.8); border: 1px solid #e2e8f0; border-radius: 16px; text-decoration: none; color: var(--primary); font-weight: 700; font-size: 14px; margin-bottom: 12px; }

# # # # # #         #limit-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15,23,42,0.9); z-index: 1000; backdrop-filter: blur(8px); align-items: center; justify-content: center; }
# # # # # #         .modal-card { background: white; padding: 40px; border-radius: 24px; max-width: 320px; text-align: center; }

# # # # # #         .support-box { margin-top: 80px; padding-top: 40px; border-top: 1px solid #f1f5f9; width: 100%; }
# # # # # #         .affiliate-card { background: rgba(255,255,255,0.8); border: 1px dashed #cbd5e1; border-radius: 20px; padding: 24px; text-align: left; display: flex; align-items: center; gap: 18px; text-decoration: none; color: inherit; transition: 0.2s; }
        
# # # # # #         footer { padding: 40px; color: #cbd5e1; font-size: 12px; font-family: 'JetBrains Mono'; opacity: 0.7; }
# # # # # #     </style>
# # # # # # </head>
# # # # # # <body>
# # # # # #     <div id="limit-modal">
# # # # # #         <div class="modal-card">
# # # # # #             <div style="font-size:40px; margin-bottom:20px;">🛡️</div>
# # # # # #             <h2 style="margin:0; font-weight:800; font-size:20px;">Daily Quota Exhausted</h2>
# # # # # #             <p style="font-size:14px; color:#64748b; margin:15px 0 25px;">
# # # # # #                 You've reached the 20-file daily hard cap. Access resets in approximately <span id="time-left" style="font-weight:800; color:var(--primary);">--</span> minutes.
# # # # # #             </p>
# # # # # #             <button class="btn" onclick="location.reload()">Understood</button>
# # # # # #         </div>
# # # # # #     </div>

# # # # # #     <div class="nav">
# # # # # #         <a href="/" class="logo"><div class="dot"></div>PDFBIRCH.APP</a>
# # # # # #         <a href="https://www.buymeacoffee.com/YOUR_BMAC_USER" target="_blank" style="font-size: 13px; font-weight: 700; color: var(--muted); text-decoration: none;">☕ Support</a>
# # # # # #     </div>

# # # # # #     <div class="container">
# # # # # #         <div id="user-badge" class="user-badge"><span id="user-email"></span></div>
# # # # # #         <h1>Entropy Engine</h1>
# # # # # #         <p>Advanced dataset generation for privacy research. Secure, limited-access mode active.</p>
        
# # # # # #         <button class="btn" id="login-btn" onclick="signIn()">Enter Engine</button>

# # # # # #         <div id="engine-ui" style="display:none; width: 100%;">
# # # # # #             <button class="btn" id="start-btn" onclick="startEngine()">Initialize Batch</button>

# # # # # #             <div class="loader" id="loader">
# # # # # #                 <div style="display:flex; justify-content:space-between; font-size:12px; font-family:'JetBrains Mono'; font-weight:700; color: #94a3b8;">
# # # # # #                     <span>Hashing...</span><span id="pct">0%</span>
# # # # # #                 </div>
# # # # # #                 <div class="bar-bg"><div class="bar-fill" id="fill"></div></div>
# # # # # #             </div>

# # # # # #             <div class="results" id="results">
# # # # # #                 <!-- Links will be added dynamically -->
# # # # # #             </div>
# # # # # #         </div>

# # # # # #         <div class="support-box">
# # # # # #             <a href="https://www.grammarly.com/affiliates" target="_blank" class="affiliate-card">
# # # # # #                 <div style="font-size: 24px;">🛡️</div>
# # # # # #                 <div style="flex:1">
# # # # # #                     <div style="font-weight:800; font-size:15px;">Verify Your Content</div>
# # # # # #                     <div style="font-size:13px; color:#94a3b8;">Use Grammarly to check your academic documents.</div>
# # # # # #                 </div>
# # # # # #                 <div>→</div>
# # # # # #             </a>
# # # # # #         </div>
# # # # # #     </div>

# # # # # #     <footer>&copy; 2026 Pdfbirch &bull; 24h Security Window Active</footer>

# # # # # #     <script>
# # # # # #         const firebaseConfig = {
# # # # # #             apiKey: "AIzaSyBZ_LmqF-RHh3RxCl39XhRfCm_mu7k-diQ",
# # # # # #             authDomain: "pdfbirch.firebaseapp.com",
# # # # # #             projectId: "pdfbirch",
# # # # # #             storageBucket: "pdfbirch.firebasestorage.app",
# # # # # #             messagingSenderId: "701712083387",
# # # # # #             appId: "1:701712083387:web:f438920e98b9831ea63c9e",
# # # # # #             measurementId: "G-RTZELQLMMZ"
# # # # # #         };
# # # # # #         firebase.initializeApp(firebaseConfig);
# # # # # #         const auth = firebase.auth();

# # # # # #         function signIn() {
# # # # # #             const provider = new firebase.auth.GoogleAuthProvider();
# # # # # #             auth.signInWithPopup(provider).catch(e => console.error(e));
# # # # # #         }

# # # # # #         auth.onAuthStateChanged(user => {
# # # # # #             if (user) {
# # # # # #                 document.getElementById('login-btn').style.display = 'none';
# # # # # #                 document.getElementById('engine-ui').style.display = 'block';
# # # # # #                 document.getElementById('user-badge').style.display = 'inline-flex';
# # # # # #                 document.getElementById('user-email').innerText = user.email;
# # # # # #             }
# # # # # #         });

# # # # # #         async function startEngine() {
# # # # # #             const user = auth.currentUser;
# # # # # #             if (!user) return;

# # # # # #             // Get Firebase token
# # # # # #             const token = await user.getIdToken();

# # # # # #             const res = await fetch('/api/check_limit', {
# # # # # #                 headers: {
# # # # # #                     'Authorization': 'Bearer ' + token
# # # # # #                 }
# # # # # #             });
# # # # # #             const data = await res.json();

# # # # # #             if (!data.allowed) {
# # # # # #                 document.getElementById('time-left').innerText = data.wait_time;
# # # # # #                 document.getElementById('limit-modal').style.display = 'flex';
# # # # # #                 return;
# # # # # #             }

# # # # # #             document.getElementById('start-btn').style.display='none';
# # # # # #             document.getElementById('loader').style.display='block';
# # # # # #             let w=0; const f=document.getElementById('fill'), p=document.getElementById('pct');
# # # # # #             const t=setInterval(()=>{
# # # # # #                 w++; f.style.width=w+'%'; p.innerText=w+'%';
# # # # # #                 if(w>=100){ 
# # # # # #                     clearInterval(t); 
# # # # # #                     document.getElementById('loader').style.display='none'; 
# # # # # #                     showResults(token);
# # # # # #                 }
# # # # # #             }, 600);
# # # # # #         }

# # # # # #         function showResults(token) {
# # # # # #             const resultsDiv = document.getElementById('results');
# # # # # #             resultsDiv.innerHTML = `
# # # # # #                 <a href="/api/download?token=${token}" class="file-link"><span>Research_Analysis_K7M2.pdf</span> <span>↓</span></a>
# # # # # #                 <a href="/api/download?token=${token}" class="file-link"><span>Draft_Final_X8N4.pdf</span> <span>↓</span></a>
# # # # # #                 <a href="/api/download?token=${token}" class="file-link"><span>Project_Report_B3L9.pdf</span> <span>↓</span></a>
# # # # # #                 <a href="/api/download?token=${token}" class="file-link"><span>Case_Study_Thesis_A1C6.pdf</span> <span>↓</span></a>
# # # # # #                 <a href="/api/download?token=${token}" class="file-link"><span>Final_Project_T5R8.pdf</span> <span>↓</span></a>
# # # # # #                 <button class="btn" onclick="location.reload()" style="background:none; color:var(--primary); box-shadow:none; border:1px solid #e2e8f0; margin-top:20px;">Refresh Batch</button>
# # # # # #             `;
# # # # # #             resultsDiv.style.display = 'block';
# # # # # #         }
# # # # # #     </script>
# # # # # # </body>
# # # # # # </html>
# # # # # # """

# # # # # # # --- 2. THE BACKEND ---
# # # # # # PREFIXES = ["Research", "Analysis", "Draft", "Final", "Project", "Report", "Case_Study", "Thesis"]
# # # # # # WORDS = ["strategy", "growth", "market", "value", "user", "product", "system", "data", "cloud", "AI", "project", "scale"]

# # # # # # @app.route('/')
# # # # # # def home(): 
# # # # # #     return HTML_PAGE

# # # # # # @app.route('/api/check_limit')
# # # # # # def check_limit():
# # # # # #     token = request.headers.get('Authorization')
# # # # # #     if not token:
# # # # # #         return jsonify({"allowed": False, "error": "No token"}), 401
    
# # # # # #     email = verify_firebase_token(token.replace('Bearer ', ''))
# # # # # #     if not email:
# # # # # #         return jsonify({"allowed": False, "error": "Invalid token"}), 401
    
# # # # # #     now = time.time()
# # # # # #     if email not in USER_HISTORY: 
# # # # # #         USER_HISTORY[email] = []
    
# # # # # #     USER_HISTORY[email] = [t for t in USER_HISTORY[email] if now - t < WINDOW_SECONDS]
    
# # # # # #     if len(USER_HISTORY[email]) >= MAX_PDFS:
# # # # # #         oldest = USER_HISTORY[email][0]
# # # # # #         wait_m = int(((oldest + WINDOW_SECONDS) - now) // 60) + 1
# # # # # #         return jsonify({"allowed": False, "wait_time": wait_m})
    
# # # # # #     USER_HISTORY[email].append(now)
# # # # # #     return jsonify({"allowed": True})

# # # # # # @app.route('/api/download')
# # # # # # def download():
# # # # # #     token = request.args.get('token')
# # # # # #     if not token:
# # # # # #         return "Unauthorized", 401
    
# # # # # #     email = verify_firebase_token(token)
# # # # # #     if not email:
# # # # # #         return "Unauthorized", 401
    
# # # # # #     # Check if user has quota left
# # # # # #     now = time.time()
# # # # # #     if email not in USER_HISTORY:
# # # # # #         return "Unauthorized", 403
    
# # # # # #     USER_HISTORY[email] = [t for t in USER_HISTORY[email] if now - t < WINDOW_SECONDS]
# # # # # #     if len(USER_HISTORY[email]) >= MAX_PDFS:
# # # # # #         return "Quota exceeded", 429
    
# # # # # #     buf = gen_pdf_content()
# # # # # #     buf.seek(0)
# # # # # #     name = f"{random.choice(PREFIXES)}_{''.join(random.choices(string.ascii_uppercase, k=4))}.pdf"
# # # # # #     return make_response(send_file(buf, as_attachment=True, download_name=name, mimetype='application/pdf'))

# # # # # # def gen_pdf_content():
# # # # # #     pdf = FPDF()
# # # # # #     pdf.set_auto_page_break(auto=True, margin=15)
# # # # # #     for _ in range(10):
# # # # # #         pdf.add_page()
# # # # # #         pdf.set_font('Arial', '', 12)
# # # # # #         for _ in range(25):
# # # # # #             line = " ".join(random.choice(WORDS) for _ in range(random.randint(10,20))).capitalize() + "."
# # # # # #             pdf.multi_cell(0, 10, line)
# # # # # #             pdf.set_text_color(255,255,255); pdf.set_font('Arial','',6)
# # # # # #             pdf.cell(0,5,''.join(random.choices(string.ascii_letters, k=15)), ln=1)
# # # # # #             pdf.set_text_color(0,0,0); pdf.set_font('Arial','',12)
# # # # # #     return io.BytesIO(pdf.output(dest='S').encode('latin-1'))

# # # # # # app.debug = True

















# # # # # # # from flask import Flask, send_file, make_response, request, jsonify
# # # # # # # from fpdf import FPDF
# # # # # # # import random, string, io, time

# # # # # # # app = Flask(__name__)

# # # # # # # # --- THE HARD CAP CONFIG ---
# # # # # # # USER_HISTORY = {}
# # # # # # # MAX_PDFS = 20
# # # # # # # WINDOW_SECONDS = 86400  # Exactly 24 Hours

# # # # # # # # --- 1. THE FRONTEND ---
# # # # # # # HTML_PAGE = """
# # # # # # # <!DOCTYPE html>
# # # # # # # <html lang="en">
# # # # # # # <head>
# # # # # # #     <meta charset="UTF-8">
# # # # # # #     <meta name="viewport" content="width=device-width, initial-scale=1.0">
# # # # # # #     <title>Pdfbirch | Privacy Engine</title>
    
# # # # # # #     <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-app-compat.js"></script>
# # # # # # #     <script src="https://www.gstatic.com/firebasejs/9.6.1/firebase-auth-compat.js"></script>

# # # # # # #     <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
# # # # # # #     <style>
# # # # # # #         :root { --bg: #f8fafc; --primary: #0f172a; --accent: #22c55e; --muted: #94a3b8; }
# # # # # # #         body { margin: 0; font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg); display: flex; flex-direction: column; align-items: center; min-height: 100vh; color: var(--primary); background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 32px 32px; }
        
# # # # # # #         .nav { width: 100%; max-width: 1100px; padding: 40px 20px; box-sizing: border-box; display: flex; justify-content: space-between; align-items: center; }
# # # # # # #         .logo { display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 15px; text-decoration: none; color: inherit; }
# # # # # # #         .dot { width: 8px; height: 8px; background: var(--accent); border-radius: 50%; }

# # # # # # #         .container { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; max-width: 500px; padding: 0 20px; box-sizing: border-box; text-align: center; }
# # # # # # #         h1 { font-size: 42px; font-weight: 800; letter-spacing: -2px; margin: 0 0 16px 0; line-height: 1; }
# # # # # # #         p { color: #64748b; font-size: 16px; line-height: 1.6; margin-bottom: 40px; }
        
# # # # # # #         .btn { background: var(--primary); color: white; border: none; padding: 22px; width: 100%; border-radius: 18px; font-weight: 700; font-size: 16px; cursor: pointer; transition: 0.2s; box-shadow: 0 10px 25px -5px rgba(15,23,42,0.2); }
# # # # # # #         .btn:hover { transform: translateY(-2px); box-shadow: 0 20px 35px -10px rgba(15,23,42,0.3); }

# # # # # # #         .user-badge { display: none; background: #fff; padding: 8px 16px; border-radius: 30px; border: 1px solid #e2e8f0; font-size: 12px; font-weight: 700; margin-bottom: 20px; }

# # # # # # #         .loader { margin-top: 40px; display: none; width: 100%; }
# # # # # # #         .bar-bg { background: #f1f5f9; height: 10px; border-radius: 10px; overflow: hidden; margin-top: 15px; }
# # # # # # #         .bar-fill { background: var(--primary); height: 100%; width: 0%; transition: width 0.3s linear; }
        
# # # # # # #         .results { margin-top: 40px; display: none; width: 100%; }
# # # # # # #         .file-link { display: flex; justify-content: space-between; padding: 20px; background: rgba(255,255,255,0.8); border: 1px solid #e2e8f0; border-radius: 16px; text-decoration: none; color: var(--primary); font-weight: 700; font-size: 14px; margin-bottom: 12px; }

# # # # # # #         #limit-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15,23,42,0.9); z-index: 1000; backdrop-filter: blur(8px); align-items: center; justify-content: center; }
# # # # # # #         .modal-card { background: white; padding: 40px; border-radius: 24px; max-width: 320px; text-align: center; }

# # # # # # #         .support-box { margin-top: 80px; padding-top: 40px; border-top: 1px solid #f1f5f9; width: 100%; }
# # # # # # #         .affiliate-card { background: rgba(255,255,255,0.8); border: 1px dashed #cbd5e1; border-radius: 20px; padding: 24px; text-align: left; display: flex; align-items: center; gap: 18px; text-decoration: none; color: inherit; transition: 0.2s; }
        
# # # # # # #         footer { padding: 40px; color: #cbd5e1; font-size: 12px; font-family: 'JetBrains Mono'; opacity: 0.7; }
# # # # # # #     </style>
# # # # # # # </head>
# # # # # # # <body>
# # # # # # #     <div id="limit-modal">
# # # # # # #         <div class="modal-card">
# # # # # # #             <div style="font-size:40px; margin-bottom:20px;">🛡️</div>
# # # # # # #             <h2 style="margin:0; font-weight:800; font-size:20px;">Daily Quota Exhausted</h2>
# # # # # # #             <p style="font-size:14px; color:#64748b; margin:15px 0 25px;">
# # # # # # #                 You've reached the 20-file daily hard cap. Access resets in approximately <span id="time-left" style="font-weight:800; color:var(--primary);">--</span> minutes.
# # # # # # #             </p>
# # # # # # #             <button class="btn" onclick="location.reload()">Understood</button>
# # # # # # #         </div>
# # # # # # #     </div>

# # # # # # #     <div class="nav">
# # # # # # #         <a href="/" class="logo"><div class="dot"></div>PDFBIRCH.APP</a>
# # # # # # #         <a href="https://www.buymeacoffee.com/YOUR_BMAC_USER" target="_blank" style="font-size: 13px; font-weight: 700; color: var(--muted); text-decoration: none;">☕ Support</a>
# # # # # # #     </div>

# # # # # # #     <div class="container">
# # # # # # #         <div id="user-badge" class="user-badge"><span id="user-email"></span></div>
# # # # # # #         <h1>Entropy Engine</h1>
# # # # # # #         <p>Advanced dataset generation for privacy research. Secure, limited-access mode active.</p>
        
# # # # # # #         <button class="btn" id="login-btn" onclick="signIn()">Enter Engine</button>

# # # # # # #         <div id="engine-ui" style="display:none; width: 100%;">
# # # # # # #             <button class="btn" id="start-btn" onclick="startEngine()">Initialize Batch</button>

# # # # # # #             <div class="loader" id="loader">
# # # # # # #                 <div style="display:flex; justify-content:space-between; font-size:12px; font-family:'JetBrains Mono'; font-weight:700; color: #94a3b8;">
# # # # # # #                     <span>Hashing...</span><span id="pct">0%</span>
# # # # # # #                 </div>
# # # # # # #                 <div class="bar-bg"><div class="bar-fill" id="fill"></div></div>
# # # # # # #             </div>

# # # # # # #             <div class="results" id="results">
# # # # # # #                 <a href="/api/download" class="file-link"><span>Research_Analysis_K7M2.pdf</span> <span>↓</span></a>
# # # # # # #                 <a href="/api/download" class="file-link"><span>Draft_Final_X8N4.pdf</span> <span>↓</span></a>
# # # # # # #                 <a href="/api/download" class="file-link"><span>Project_Report_B3L9.pdf</span> <span>↓</span></a>
# # # # # # #                 <a href="/api/download" class="file-link"><span>Case_Study_Thesis_A1C6.pdf</span> <span>↓</span></a>
# # # # # # #                 <a href="/api/download" class="file-link"><span>Final_Project_T5R8.pdf</span> <span>↓</span></a>
# # # # # # #                 <button class="btn" onclick="location.reload()" style="background:none; color:var(--primary); box-shadow:none; border:1px solid #e2e8f0; margin-top:20px;">Refresh Batch</button>
# # # # # # #             </div>
# # # # # # #         </div>

# # # # # # #         <div class="support-box">
# # # # # # #             <a href="https://www.grammarly.com/affiliates" target="_blank" class="affiliate-card">
# # # # # # #                 <div style="font-size: 24px;">🛡️</div>
# # # # # # #                 <div style="flex:1">
# # # # # # #                     <div style="font-weight:800; font-size:15px;">Verify Your Content</div>
# # # # # # #                     <div style="font-size:13px; color:#94a3b8;">Use Grammarly to check your academic documents.</div>
# # # # # # #                 </div>
# # # # # # #                 <div>→</div>
# # # # # # #             </a>
# # # # # # #         </div>
# # # # # # #     </div>

# # # # # # #     <footer>&copy; 2026 Pdfbirch &bull; 24h Security Window Active</footer>

# # # # # # #     <script>
# # # # # # #         // --- YOUR ACTUAL FIREBASE CONFIG ---
# # # # # # #         const firebaseConfig = {
# # # # # # #             apiKey: "AIzaSyBZ_LmqF-RHh3RxCl39XhRfCm_mu7k-diQ",
# # # # # # #             authDomain: "pdfbirch.firebaseapp.com",
# # # # # # #             projectId: "pdfbirch",
# # # # # # #             storageBucket: "pdfbirch.firebasestorage.app",
# # # # # # #             messagingSenderId: "701712083387",
# # # # # # #             appId: "1:701712083387:web:f438920e98b9831ea63c9e",
# # # # # # #             measurementId: "G-RTZELQLMMZ"
# # # # # # #         };
# # # # # # #         firebase.initializeApp(firebaseConfig);
# # # # # # #         const auth = firebase.auth();

# # # # # # #         function signIn() {
# # # # # # #             const provider = new firebase.auth.GoogleAuthProvider();
# # # # # # #             auth.signInWithPopup(provider).catch(e => console.error(e));
# # # # # # #         }

# # # # # # #         auth.onAuthStateChanged(user => {
# # # # # # #             if (user) {
# # # # # # #                 document.getElementById('login-btn').style.display = 'none';
# # # # # # #                 document.getElementById('engine-ui').style.display = 'block';
# # # # # # #                 document.getElementById('user-badge').style.display = 'inline-flex';
# # # # # # #                 document.getElementById('user-email').innerText = user.email;
# # # # # # #             }
# # # # # # #         });

# # # # # # #         async function startEngine() {
# # # # # # #             const user = auth.currentUser;
# # # # # # #             if (!user) return;

# # # # # # #             const res = await fetch(`/api/check_limit?email=${user.email}`);
# # # # # # #             const data = await res.json();

# # # # # # #             if (!data.allowed) {
# # # # # # #                 document.getElementById('time-left').innerText = data.wait_time;
# # # # # # #                 document.getElementById('limit-modal').style.display = 'flex';
# # # # # # #                 return;
# # # # # # #             }

# # # # # # #             document.getElementById('start-btn').style.display='none';
# # # # # # #             document.getElementById('loader').style.display='block';
# # # # # # #             let w=0; const f=document.getElementById('fill'), p=document.getElementById('pct');
# # # # # # #             const t=setInterval(()=>{
# # # # # # #                 w++; f.style.width=w+'%'; p.innerText=w+'%';
# # # # # # #                 if(w>=100){ clearInterval(t); document.getElementById('loader').style.display='none'; document.getElementById('results').style.display='block'; }
# # # # # # #             }, 600);
# # # # # # #         }
# # # # # # #     </script>
# # # # # # # </body>
# # # # # # # </html>
# # # # # # # """

# # # # # # # # --- 2. THE BACKEND ---
# # # # # # # PREFIXES = ["Research", "Analysis", "Draft", "Final", "Project", "Report", "Case_Study", "Thesis"]
# # # # # # # WORDS = ["strategy", "growth", "market", "value", "user", "product", "system", "data", "cloud", "AI", "project", "scale"]

# # # # # # # @app.route('/')
# # # # # # # def home(): return HTML_PAGE

# # # # # # # @app.route('/api/check_limit')
# # # # # # # def check_limit():
# # # # # # #     email = request.args.get('email')
# # # # # # #     if not email: return jsonify({"allowed": False})
# # # # # # #     now = time.time()
# # # # # # #     if email not in USER_HISTORY: USER_HISTORY[email] = []
# # # # # # #     USER_HISTORY[email] = [t for t in USER_HISTORY[email] if now - t < WINDOW_SECONDS]
# # # # # # #     if len(USER_HISTORY[email]) >= MAX_PDFS:
# # # # # # #         oldest = USER_HISTORY[email][0]
# # # # # # #         wait_m = int(((oldest + WINDOW_SECONDS) - now) // 60) + 1
# # # # # # #         return jsonify({"allowed": False, "wait_time": wait_m})
# # # # # # #     USER_HISTORY[email].append(now)
# # # # # # #     return jsonify({"allowed": True})

# # # # # # # @app.route('/api/download')
# # # # # # # def download():
# # # # # # #     buf = gen_pdf_content(); buf.seek(0)
# # # # # # #     name = f"{random.choice(PREFIXES)}_{''.join(random.choices(string.ascii_uppercase, k=4))}.pdf"
# # # # # # #     return make_response(send_file(buf, as_attachment=True, download_name=name, mimetype='application/pdf'))

# # # # # # # def gen_pdf_content():
# # # # # # #     pdf = FPDF()
# # # # # # #     pdf.set_auto_page_break(auto=True, margin=15)
# # # # # # #     for _ in range(10):
# # # # # # #         pdf.add_page()
# # # # # # #         pdf.set_font('Arial', '', 12)
# # # # # # #         for _ in range(25):
# # # # # # #             line = " ".join(random.choice(WORDS) for _ in range(random.randint(10,20))).capitalize() + "."
# # # # # # #             pdf.multi_cell(0, 10, line)
# # # # # # #             pdf.set_text_color(255,255,255); pdf.set_font('Arial','',6)
# # # # # # #             pdf.cell(0,5,''.join(random.choices(string.ascii_letters, k=15)), ln=1)
# # # # # # #             pdf.set_text_color(0,0,0); pdf.set_font('Arial','',12)
# # # # # # #     return io.BytesIO(pdf.output(dest='S').encode('latin-1'))

# # # # # # # app.debug = True
