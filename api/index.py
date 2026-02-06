from flask import Flask, send_file, make_response
from fpdf import FPDF
import random
import string
import io

app = Flask(__name__)

# --- 1. THE FRONTEND (Grid Aesthetic: Box within a Box) ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pdfbirch | Entropy Engine</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;700;800&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #f8fafc; --text-main: #020617; --text-muted: #64748b; --card-bg: rgba(255, 255, 255, 0.85); --primary: #0f172a; }
        
        body { margin: 0; font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg); color: var(--text-main); min-height: 100vh; display: flex; flex-direction: column; align-items: center; background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 32px 32px; overflow-y: auto; padding: 20px 0; } 
        
        /* Fixed Centering Grid */
        .layout-grid { display: flex; align-items: flex-start; justify-content: center; gap: 20px; width: 100%; max-width: 1400px; padding: 0 10px; box-sizing: border-box; }
        
        /* Side Ad Container (Ghost Border) */
        .side-ad { width: 160px; height: 600px; background: rgba(255,255,255,0.5); border: 1px dashed #cbd5e1; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; overflow: hidden; }
        
        /* Main Card */
        .main-card { background: var(--card-bg); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px); border: 1px solid #fff; border-radius: 20px; padding: 32px 24px; width: 100%; max-width: 440px; text-align: center; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05); margin: 0 auto 20px auto; }
        
        @media (max-width: 1150px) { 
            .side-ad { display: none !important; } 
            .layout-grid { gap: 0; }
        }
        
        h1 { font-size: 26px; font-weight: 800; margin: 0 0 8px 0; letter-spacing: -1.0px; color: #0f172a; line-height: 1.1; }
        p { color: var(--text-muted); font-size: 14px; line-height: 1.5; margin-bottom: 24px; font-weight: 500; }
        
        .btn-primary { background: #0f172a; color: white; border: none; padding: 18px; width: 100%; border-radius: 12px; font-family: 'Plus Jakarta Sans', sans-serif; font-size: 15px; font-weight: 600; cursor: pointer; transition: all 0.2s ease; box-shadow: 0 10px 15px -3px rgba(15, 23, 42, 0.2); letter-spacing: -0.3px; margin-bottom: 0; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 20px 25px -5px rgba(15, 23, 42, 0.3); }

        /* --- THE AD ZONE BOX --- */
        .ad-stack-wrapper {
            margin-top: 32px;
            border: 3px solid #0f172a; /* Thick dark border */
            background: #f1f5f9;
            border-radius: 16px;
            padding: 20px 16px;
        }
        .ad-stack-label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            font-weight: 700;
            color: #0f172a;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 16px;
            display: block;
        }

        /* --- INDIVIDUAL AD SLOTS (Dashed Borders Restored) --- */
        .ad-slot-inner { 
            background: #fff; 
            border: 1px dashed #94a3b8; /* Visible dashed border */
            border-radius: 8px;
            margin: 0 auto 16px auto; 
            display: flex; align-items: center; justify-content: center; overflow: hidden; width: 100%; max-width: 320px; 
        }
        .ad-slot-inner:last-child { margin-bottom: 0; }
        
        /* Specific Heights */
        .ad-small { min-height: 50px; }
        .ad-big { min-height: 250px; background: #e2e8f0; } 
        
        /* Loader & Results */
        .loader-container { margin-top: 24px; display: none; text-align: left; }
        .status-header { display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-muted); margin-bottom: 8px; font-weight: 500; text-transform: uppercase; }
        .progress-track { background: #e2e8f0; height: 4px; border-radius: 10px; overflow: hidden; }
        .progress-fill { background: #0f172a; height: 100%; width: 0%; transition: width 0.6s linear; }
        
        .results-area { margin-top: 24px; display: none; border-top: 1px solid #e2e8f0; padding-top: 24px; }
        .download-item { display: flex; justify-content: space-between; align-items: center; padding: 14px; margin: 8px 0; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; color: var(--text-main); text-decoration: none; font-size: 13px; font-weight: 600; transition: 0.2s; box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); }
        .hidden { display: none; }
        
        .footer-legal { width: 100%; text-align: center; color: #94a3b8; font-size: 11px; font-family: 'Plus Jakarta Sans', sans-serif; opacity: 0.6; padding-bottom: 40px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="layout-grid">
        
        <div class="side-ad left">
            <script type="text/javascript">
                atOptions = { 'key' : '59bcd34a7d0fbed85bbe98e1b3aa6e8b', 'format' : 'iframe', 'height' : 600, 'width' : 160, 'params' : {} };
            </script>
            <script type="text/javascript" src="//www.highperformanceformat.com/59bcd34a7d0fbed85bbe98e1b3aa6e8b/invoke.js"></script>
        </div>

        <div class="main-card">
            <h1>Pdfbirch - Entropy Engine</h1>
            <p>Generate high-variance, cryptographically unique English datasets for pipeline validation.</p>
            
            <button class="btn-primary" id="start-btn" onclick="startSequence()">Initialize Sequence</button>

            <div class="ad-stack-wrapper">
                <span class="ad-stack-label">Sponsored Placements</span>
                
                <div class="ad-slot-inner ad-small">
                    <script type="text/javascript">
                        atOptions = { 'key' : '3bab905f2f3178c02c3534a0ea5773f6', 'format' : 'iframe', 'height' : 50, 'width' : 320, 'params' : {} };
                    </script>
                    <script type="text/javascript" src="//www.highperformanceformat.com/3bab905f2f3178c02c3534a0ea5773f6/invoke.js"></script>
                </div>
                
                <div class="ad-slot-inner ad-big">
                     <div style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%;">
                        <script type="text/javascript">
                            atOptions = { 'key' : '3bab905f2f3178c02c3534a0ea5773f6', 'format' : 'iframe', 'height' : 50, 'width' : 320, 'params' : {} };
                        </script>
                        <script type="text/javascript" src="//www.highperformanceformat.com/3bab905f2f3178c02c3534a0ea5773f6/invoke.js"></script>
                        <span style="font-size:10px; color:#94a3b8; margin-top:10px;">[ Big Box Slot ]</span>
                     </div>
                </div>
                
                <div class="ad-slot-inner ad-small">
                    <script type="text/javascript">
                        atOptions = { 'key' : '3bab905f2f3178c02c3534a0ea5773f6', 'format' : 'iframe', 'height' : 50, 'width' : 320, 'params' : {} };
                    </script>
                    <script type="text/javascript" src="//www.highperformanceformat.com/3bab905f2f3178c02c3534a0ea5773f6/invoke.js"></script>
                </div>
            </div>
            <div class="loader-container" id="loader">
                <div class="status-header"><span id="console-text">System Handshake...</span><span id="percent-text">0%</span></div>
                <div class="progress-track"><div class="progress-fill" id="fill"></div></div>
            </div>
            
            <div class="results-area" id="results">
                <div style="text-align: left; margin-bottom: 12px; font-family:'JetBrains Mono'; font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing:1px;">Manifest Ready</div>
                <a href="/api/download" class="download-item"><span>Dataset_Batch_A83.pdf</span> <span>↓</span></a>
                <a href="/api/download" class="download-item"><span>Dataset_Batch_X92.pdf</span> <span>↓</span></a>
                <a href="/api/download" class="download-item"><span>Dataset_Batch_B11.pdf</span> <span>↓</span></a>
                <a href="/api/download" class="download-item"><span>Dataset_Batch_G44.pdf</span> <span>↓</span></a>
                <a href="/api/download" class="download-item"><span>Dataset_Batch_L09.pdf</span> <span>↓</span></a>
                <button class="btn-primary" onclick="location.reload()" style="margin-top:20px; background: white; color: #0f172a; border: 1px solid #e2e8f0; box-shadow:none;">Generate New Batch</button>
            </div>
        </div>

        <div class="side-ad right">
            <script type="text/javascript">
                atOptions = { 'key' : '59bcd34a7d0fbed85bbe98e1b3aa6e8b', 'format' : 'iframe', 'height' : 600, 'width' : 160, 'params' : {} };
            </script>
            <script type="text/javascript" src="//www.highperformanceformat.com/59bcd34a7d0fbed85bbe98e1b3aa6e8b/invoke.js"></script>
        </div>

    </div>

    <div class="footer-legal">
        <p style="margin: 0;">&copy; 2026 Pdfbirch.app &bull; <span style="color: #64748b;">Privacy & Testing Tool</span></p>
        <p style="margin: 6px 0 0 0; font-size: 10px;">
            Generated documents are intended for pipeline validation, system load testing, and privacy protection.<br>
            Not affiliated with any third-party file hosting platforms.
        </p>
    </div>

    <script>
        function startSequence() {
            // Hide the ad box when sequence starts
            document.querySelector('.ad-stack-wrapper').style.display = 'none';
            
            document.getElementById('start-btn').style.display = 'none';
            document.getElementById('loader').style.display = 'block';
            let w = 0;
            const fill = document.getElementById('fill');
            const txt = document.getElementById('console-text');
            const pct = document.getElementById('percent-text');
            const timer = setInterval(() => {
                w++; fill.style.width = w + '%'; pct.innerText = w + '%';
                if(w < 20) txt.innerText = "Encrypting Handshake..."; else if(w < 40) txt.innerText = "Allocating Dictionary..."; else if(w < 60) txt.innerText = "Randomizing Vectors..."; else if(w < 85) txt.innerText = "Injecting Entropy..."; else txt.innerText = "Finalizing Output...";
                if(w >= 100) { clearInterval(timer); showResults(); }
            }, 600); 
        }
        function showResults() {
            document.getElementById('loader').style.display = 'none';
            document.getElementById('results').style.display = 'block';
            // Show ad box again
            document.querySelector('.ad-stack-wrapper').style.display = 'block';
        }
    </script>
</body>
</html>
"""

# --- 2. THE BACKEND (The Brains) ---
WORDS = ["strategy", "growth", "market", "value", "user", "product", "system", "data", "cloud", "AI", "project", "scale"]

def get_random_sentence():
    length = random.randint(10, 20)
    sentence = " ".join(random.choice(WORDS) for _ in range(length))
    return sentence.capitalize() + "."

def generate_messy_pdf():
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    for page in range(10):
        pdf.add_page()
        for _ in range(20):
            family = random.choice(['Arial', 'Times', 'Courier'])
            style = random.choice(['', 'B', 'I'])
            size = random.randint(10, 14)
            pdf.set_font(family, style, size)
            pdf.multi_cell(0, 10, get_random_sentence(), align='L')
            
            # Anti-Detector Noise
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', '', 6)
            noise = ''.join(random.choices(string.ascii_letters, k=10))
            pdf.cell(0, 5, noise, ln=1)
            pdf.set_text_color(0, 0, 0)

    pdf_string = pdf.output(dest='S')
    buffer = io.BytesIO(pdf_string.encode('latin-1'))
    buffer.seek(0)
    return buffer

# --- ROUTES ---
@app.route('/')
def home():
    return HTML_PAGE

@app.route('/api/download')
def download():
    try:
        pdf_buffer = generate_messy_pdf()
        filename = f"Dataset_{random.randint(1000,9999)}.pdf"
        response = make_response(send_file(pdf_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf'))
        return response
    except Exception as e:
        return f"Error: {str(e)}"

# Critical for Vercel
app.debug = True
