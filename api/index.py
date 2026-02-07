from flask import Flask, send_file, make_response, request, jsonify
from fpdf import FPDF
import random, string, io
import os
import json
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
import traceback
app = Flask(__name__)
# Initialize Firebase Admin
service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT')
if service_account_json:
    try:
        cred_dict = json.loads(service_account_json)
        cred = credentials.Certificate(cred_dict)
        if not firebase_admin._apps: # Check if already initialized
            firebase_admin.initialize_app(cred)
        print("Firebase initialized successfully")
    except Exception as e:
        print(f"Firebase initialization error: {e}")
else:
    print("WARNING: FIREBASE_SERVICE_ACCOUNT not set")
def verify_firebase_token(token):
    """Verify Firebase ID token and return email if valid"""
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        return decoded_token.get('email')
    except Exception as e:
        print(f"Token verification error: {e}")
        return None
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
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .user-badge { display: none; background: #fff; padding: 8px 16px; border-radius: 30px; border: 1px solid #e2e8f0; font-size: 12px; font-weight: 700; margin-bottom: 20px; }
        .loader { margin-top: 40px; display: none; width: 100%; }
        .bar-bg { background: #f1f5f9; height: 10px; border-radius: 10px; overflow: hidden; margin-top: 15px; }
        .bar-fill { background: var(--primary); height: 100%; width: 0%; transition: width 0.3s linear; }
       
        .results { margin-top: 40px; display: none; width: 100%; }
        .file-link { display: flex; justify-content: space-between; padding: 20px; background: rgba(255,255,255,0.8); border: 1px solid #e2e8f0; border-radius: 16px; color: var(--primary); font-weight: 700; font-size: 14px; margin-bottom: 12px; cursor: pointer; transition: 0.2s; }
        .file-link:hover { border-color: var(--primary); background: #fff; transform: scale(1.02); }
        .file-link.downloading { opacity: 0.6; cursor: wait; }
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
            auth.signInWithPopup(provider).catch(e => {
                console.error('Sign in error:', e);
                alert('Sign in failed: ' + e.message);
            });
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
            if (!user) {
                alert('Please sign in first');
                return;
            }
            try {
                const token = await user.getIdToken();
                const res = await fetch('/api/check_limit', {
                    headers: { 'Authorization': 'Bearer ' + token }
                });
               
                if (!res.ok) {
                    throw new Error('Failed to check limit: ' + res.status);
                }
               
                const data = await res.json();
                if (!data.allowed) {
                    alert('Authentication failed. Please sign in again.');
                    location.reload();
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
            } catch(e) {
                console.error('Start engine error:', e);
                alert('Error: ' + e.message);
                document.getElementById('start-btn').style.display='block';
            }
        }
        async function downloadPDF(element, token, filename) {
            // Prevent multiple clicks
            if (element.classList.contains('downloading')) {
                return;
            }
           
            element.classList.add('downloading');
            const originalText = element.innerHTML;
            element.innerHTML = '<span>' + filename + '</span><span>⏳</span>';
           
            try {
                console.log('Starting download for:', filename);
               
                const res = await fetch('/api/download', {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer ' + token,
                        'Content-Type': 'application/json'
                    }
                });
                console.log('Response status:', res.status);
                if (res.status === 401) {
                    alert('Authentication failed. Please sign in again.');
                    location.reload();
                    return;
                }
                if (res.status === 500) {
                    const errorText = await res.text();
                    console.error('Server error:', errorText);
                    alert('Server error: ' + errorText);
                    element.classList.remove('downloading');
                    element.innerHTML = originalText;
                    return;
                }
                if (!res.ok) {
                    const errorText = await res.text();
                    console.error('Download failed:', errorText);
                    alert('Download failed: ' + errorText);
                    element.classList.remove('downloading');
                    element.innerHTML = originalText;
                    return;
                }
                const blob = await res.blob();
                console.log('Blob received, size:', blob.size);
               
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
               
                // Reset button state
                element.classList.remove('downloading');
                element.innerHTML = originalText;
               
                console.log('Download completed successfully');
            } catch(e) {
                console.error('Download exception:', e);
                alert('Download error: ' + e.message);
                element.classList.remove('downloading');
                element.innerHTML = originalText;
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
                `<div class="file-link" onclick="downloadPDF(this, '${token}', '${f}')"><span>${f}</span><span>↓</span></div>`
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
    """Always allow if authenticated"""
    try:
        token = request.headers.get('Authorization')
        if not token:
            print("No token provided")
            return jsonify({"allowed": False, "error": "No token"}), 401
       
        email = verify_firebase_token(token.replace('Bearer ', ''))
        if not email:
            print("Invalid token")
            return jsonify({"allowed": False, "error": "Invalid token"}), 401
       
        return jsonify({"allowed": True})
    except Exception as e:
        print(f"Error in check_limit: {e}")
        traceback.print_exc()
        return jsonify({"allowed": False, "error": str(e)}), 500
@app.route('/api/download', methods=['POST'])
def download():
    """Generate and download PDF if authenticated - no quota"""
    try:
        token = request.headers.get('Authorization')
        if not token:
            print("No token provided in download")
            return "Unauthorized - No token", 401
       
        email = verify_firebase_token(token.replace('Bearer ', ''))
        if not email:
            print("Invalid token in download")
            return "Unauthorized - Invalid token", 401
       
        print(f"Download request from: {email}")
       
        # Generate and return PDF
        print("Generating PDF content...")
        buf = gen_pdf_content()
        buf.seek(0)
        name = f"{random.choice(PREFIXES)}_{random.choice(PREFIXES)}_{''.join(random.choices(string.ascii_uppercase+string.digits, k=4))}.pdf"
        print(f"Sending PDF: {name}, Size: {buf.getbuffer().nbytes} bytes")
       
        return make_response(send_file(buf, as_attachment=True, download_name=name, mimetype='application/pdf'))
   
    except Exception as e:
        print(f"Error in download endpoint: {str(e)}")
        traceback.print_exc()
        return str(e), 500
def gen_pdf_content():
    """Generate PDF with randomized fonts, sizes, and styles"""
    try:
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
    except Exception as e:
        print(f"Error generating PDF: {e}")
        traceback.print_exc()
        raise
# For Vercel, we need to export the app
app = app
