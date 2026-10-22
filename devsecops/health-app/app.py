from flask import Flask, jsonify
import hvac
import os
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)

# Initialize Prometheus metrics
metrics = PrometheusMetrics(app)
# Add custom info metric
metrics.info('app_info', 'Application info', version='v5.0')

# Vault configuration
VAULT_ADDR = os.getenv('VAULT_ADDR', 'http://host.docker.internal:8200')
VAULT_TOKEN = os.getenv('VAULT_TOKEN', 'myroot')

def get_secret_from_vault():
    """Fetch secrets from HashiCorp Vault"""
    try:
        client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
        
        # Read secret from Vault
        secret = client.secrets.kv.v2.read_secret_version(
            path='health-app/config',
            mount_point='secret'
        )
        
        return secret['data']['data']
    except Exception as e:
        return {"error": f"Failed to fetch secret: {str(e)}"}

@app.route("/health", methods=["GET"])
def health():
    return "ok", 200, {"Content-Type": "text/plain"}

@app.route("/version", methods=["GET"])
def version():
    return "v5.0 - Monitored by Prometheus!", 200, {"Content-Type": "text/plain"}

@app.route("/secret", methods=["GET"])
def secret():
    """New endpoint that fetches and displays secret from Vault"""
    secrets = get_secret_from_vault()
    
    if "error" in secrets:
        return jsonify(secrets), 500
    
    # In production, you'd never expose secrets like this!
    # This is just to prove Vault integration works
    return jsonify({
        "message": "Secret fetched from Vault successfully!",
        "api_key": secrets.get("api_key"),
        "db_password": "***hidden***"  # Good practice: don't expose passwords
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
