from flask import Flask, render_template_string, jsonify, send_file
from data_engine import MacroEngine
import json
import os

app = Flask(__name__)
engine = MacroEngine()

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/api/macro')
def get_macro_data():
    try:
        data = engine.calculate_regime()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = 3000
    print(f"🔥 Global Macro Compass Server running at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
