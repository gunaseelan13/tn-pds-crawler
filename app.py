from flask import Flask, jsonify, send_file, render_template_string, abort
import os
import json
from datetime import datetime

app = Flask(__name__)

# HTML template for the index page
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>TN PDS Crawler</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        .card {
            background: #f9f9f9;
            border-radius: 5px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .status-online {
            color: green;
            font-weight: bold;
        }
        .status-offline {
            color: #e74c3c;
            font-weight: bold;
        }
        .links {
            margin-top: 30px;
        }
        .links a {
            display: inline-block;
            margin-right: 15px;
            text-decoration: none;
            color: #3498db;
            padding: 8px 15px;
            border: 1px solid #3498db;
            border-radius: 4px;
        }
        .links a:hover {
            background: #3498db;
            color: white;
        }
        .timestamp {
            color: #7f8c8d;
            font-size: 0.9em;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f2f2f2;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
    </style>
</head>
<body>
    <h1>Tamil Nadu PDS Crawler</h1>
    
    <div class="card">
        <h2>Crawler Status</h2>
        <p><strong>Status:</strong> {{ status }}</p>
        <p><strong>Last Run:</strong> <span class="timestamp">{{ last_run }}</span></p>
        <p><strong>Shops Checked:</strong> {{ shops_checked }}</p>
        <p><strong>Shops Found:</strong> {{ shops_found }}</p>
        <p><strong>Online Shops:</strong> <span class="status-online">{{ online_shops }}</span></p>
        <p><strong>Offline Shops:</strong> <span class="status-offline">{{ offline_shops }}</span></p>
    </div>

    {% if shops_data %}
    <div class="card">
        <h2>Shop Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Shop ID</th>
                    <th>Name</th>
                    <th>District</th>
                    <th>Taluk</th>
                    <th>Status</th>
                    <th>Last Transaction</th>
                </tr>
            </thead>
            <tbody>
                {% for shop_id, shop in shops_data.items() %}
                <tr>
                    <td>{{ shop_id }}</td>
                    <td>{{ shop.name }}</td>
                    <td>{{ shop.district }}</td>
                    <td>{{ shop.taluk }}</td>
                    <td class="status-{% if shop.status == 'Online' %}online{% else %}offline{% endif %}">{{ shop.status }}</td>
                    <td>{{ shop.last_transaction.date_time if shop.last_transaction else 'N/A' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    <div class="links">
        <a href="/">Home</a>
        <a href="/status">Status API</a>
        <a href="/results">Raw JSON</a>
        <a href="/health">Health Check</a>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    # Check if results file exists
    results_file = '/app/data/shop_status_results.json'
    context = {
        "status": "running",
        "last_run": "Not yet run",
        "shops_checked": 0,
        "shops_found": 0,
        "online_shops": 0,
        "offline_shops": 0,
        "shops_data": None
    }
    
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r') as f:
                data = json.load(f)
            
            context.update({
                "status": "success",
                "last_run": data.get("timestamp", "unknown"),
                "shops_checked": data.get("total_shops_checked", 0),
                "shops_found": data.get("shops_found", 0),
                "online_shops": data.get("online_shops", 0),
                "offline_shops": data.get("offline_shops", 0),
                "shops_data": data.get("results", {})
            })
        except Exception as e:
            context["status"] = f"Error reading results: {str(e)}"
    
    return render_template_string(INDEX_TEMPLATE, **context)

@app.route('/status')
def status():
    # Check if results file exists
    results_file = '/app/data/shop_status_results.json'
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r') as f:
                data = json.load(f)
            return jsonify({
                "status": "success",
                "last_run": data.get("timestamp", "unknown"),
                "shops_checked": data.get("total_shops_checked", 0),
                "shops_found": data.get("shops_found", 0),
                "online_shops": data.get("online_shops", 0),
                "offline_shops": data.get("offline_shops", 0)
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Error reading results file: {str(e)}"
            }), 500
    else:
        return jsonify({
            "status": "pending",
            "message": "No crawler results found yet. The crawler may not have run."
        })

@app.route('/results')
def results():
    # Serve the raw JSON file
    results_file = '/app/data/shop_status_results.json'
    if os.path.exists(results_file):
        try:
            return send_file(results_file, mimetype='application/json')
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Error serving results file: {str(e)}"
            }), 500
    else:
        return jsonify({
            "status": "pending",
            "message": "No crawler results found yet. The crawler may not have run."
        }), 404

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/logs')
def logs():
    # Serve the crawler logs if they exist
    log_file = '/app/data/crawler.log'
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                log_content = f.read()
            return log_content, 200, {'Content-Type': 'text/plain'}
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Error reading log file: {str(e)}"
            }), 500
    else:
        return jsonify({
            "status": "pending",
            "message": "No crawler logs found yet."
        }), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
