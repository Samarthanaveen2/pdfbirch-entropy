from flask import Flask, send_file, make_response
from fpdf import FPDF
import random
import string
import io

app = Flask(__name__)

# --- THE FRONTEND (Embedded here so it can never be lost) ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pdfbirch | Entropy Engine</title>

<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@400;500;700;800&display=swap" rel="stylesheet">

<style>
:root {
    --bg: #f8fafc;
    --text-main: #020617;
    --text-muted: #64748b;
    --card-bg: rgba(255,255,255,0.85);
    --primary: #0f172a;
}

body {
    margin: 0;
    font-family: 'Plus Jakarta Sans', sans-serif;
    background: var(--bg);
    color: var(--text-main);
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    background-image: radial-gradient(#cbd5e1 1px, transparent 1px);
    background-size: 32px 32px;
}

.layout-grid {
    display: flex;
    align-items: flex-start;
    justify-content: center;
    gap: 24px;
    width: 100%;
    max-width: 1400px;
    padding: 32px;
}

.side-ad {
    width: 300px;
    height: 600px;
    background: #fff;
    border: 1px dashed #cbd5e1;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #94a3b8;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
    flex-shrink: 0;
}

.main-card {
    background: var(--card-bg);
    backdrop-filter: blur(24px);
    border-radius: 24px;
    padding: 48px;
    width: 100%;
    max-width: 480px;
    text-align: center;
    box-shadow: 0 20px 25px -5px rgba(0,0,0,0.05);
}

h1 {
    font-size: 32px;
    font-weight: 800;
    margin-bottom: 12px;
}

p {
    color: var(--text-muted);
    font-size: 15px;
    line-height: 1.6;
    margin-bottom: 28px;
}

.btn-primary {
    background: #0f172a;
    color: #fff;
    border: none;
    padding: 18px;
    width: 100%;
    border-radius: 12px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
}

.loader-container,
.results-area {
    display: none;
    margin-top: 28px;
}

/* ---------------- MOBILE FIXES ---------------- */

@media (max-width: 1150px) {

    body {
        align-items: flex-start;
    }

    .layout-grid {
        flex-direction: column;
        padding: 16px;
    }

    /* Ensure card renders first */
    .main-card { order: 1; }
    .side-ad.left { order: 2; }
    .side-ad.right { order: 3; }

    /* Prevent ads from pushing content below fold */
    .side-ad {
        width: 100%;
        max-width: 480px;
        height: min(18vh, 140px);
    }

    /* Guarantee button visibility */
    .main-card {
        margin-top: 8px;
    }
}
</style>
</head>

<body>
<div class="layout-grid">
    <div class="side-ad left">[ Ad Tower Left ]</div>

    <div class="main-card">
        <h1>Pdfbirch – Entropy Engine</h1>
        <p>Generate high-variance, cryptographically unique English datasets for pipeline validation.</p>
        <button class="btn-primary" onclick="startSequence()">Initialize Sequence</button>
        <div class="loader-container" id="loader">Processing…</div>
        <div class="results-area" id="results">Done</div>
    </div>

    <div class="side-ad right">[ Ad Tower Right ]</div>
</div>

<script>
function startSequence() {
    document.querySelector('.btn-primary').style.display = 'none';
    document.getElementById('loader').style.display = 'block';
}
</script>
</body>
</html>
"""

# --- BACKEND LOGIC ---
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
