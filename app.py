from flask import Flask, render_template_string
from data_engine import MacroEngine
import json
import os

app = Flask(__name__)
engine = MacroEngine()

@app.route('/')
def home():
    print("🚀 Request Received. Compiling Fresh Market Pulses...")
    data = engine.calculate_regime()
    
    target_file = 'index.html'
    if not os.path.exists(target_file):
        return "❌ Error: index.html not found.", 500

    with open(target_file, 'r') as f:
        content = f.read()

    # Injection logic
    start_tag = '// --- DATA INJECTION POINT ---'
    end_tag = '// --- END DATA INJECTION ---'
    
    if start_tag in content and end_tag in content:
        data_string = f'\n        const DATA = {json.dumps(data)};\n        '
        parts = content.split(start_tag)
        rest = parts[1].split(end_tag)
        new_content = parts[0] + start_tag + data_string + end_tag + rest[1]
        return render_template_string(new_content)
    else:
        return "❌ Error: Could not find injection markers in index.html", 500

if __name__ == "__main__":
    port = 3000
    print(f"🔥 Global Macro Compass Server running at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
