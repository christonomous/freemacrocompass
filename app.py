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

    # Injection logic - Replace the placeholder DATA object
    placeholder = 'const DATA = { "composite": 0.2297, "components": { "Liquidity": 0.5, "Credit": 0.8, "Monetary Conditions": 0.7, "Growth (Cu/Au)": 0.3, "Risk Appetite": -0.1, "Sentiment": 0.5 }, "raw": { "fred": { "yield_10y3m": 0.39, "real_yield": 1.89, "hy_spread": 3.2, "nfci": -0.5, "inflation": 3.1, "fed_funds": 5.33, "net_liquidity": 6.5e12 }, "market": { "momentum": { "SPY": 0.02, "GLD": 0.01, "HG=F": 0.01, "DX-Y.NYB": 0.01, "XLK": 0.03, "XLP": 0.01 }, "cg_ratio": 0.002, "rotation": -0.1122, "correlation": {} } } };'
    
    if placeholder in content:
        data_string = f'const DATA = {json.dumps(data)};'
        new_content = content.replace(placeholder, data_string)
        return render_template_string(new_content)
    else:
        # Fallback to a more generic regex if the exact placeholder is changed
        import re
        new_content = re.sub(r'const DATA = \{.*?\};', f'const DATA = {json.dumps(data)};', content, flags=re.DOTALL)
        return render_template_string(new_content)

if __name__ == "__main__":
    port = 3000
    print(f"🔥 Global Macro Compass Server running at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
