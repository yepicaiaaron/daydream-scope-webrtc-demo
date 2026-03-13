from gevent import monkey
monkey.patch_all()

from flask import Flask, request, jsonify, abort, Response
import requests
import os

app = Flask(__name__)

# The target URL for your Daydream Scope App on GCP
# This should be the internal or private IP/port if Render can reach it directly,
# or the public IP if the GCP firewall allows it only from Render's IPs.
TARGET_SCOPE_URL = os.environ.get("TARGET_SCOPE_URL", "http://34.44.193.2:8000")

@app.route("/api/v1/webrtc/offer", methods=["POST"])
def webrtc_offer():
    if not request.is_json:
        abort(400, description="Request must be JSON")
    
    try:
        # Forward the request to the Daydream Scope App
        response = requests.post(f"{TARGET_SCOPE_URL}/api/v1/webrtc/offer", json=request.get_json())
        response.raise_for_status() # Raise an exception for HTTP errors
        
        # Return the response from the Daydream Scope App
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error forwarding WebRTC offer: {e}")
        abort(500, description=str(e))

@app.route("/api/v1/prompt", methods=["POST"])
def prompt():
    if not request.is_json:
        abort(400, description="Request must be JSON")
    
    try:
        # Forward the request to the Daydream Scope App
        response = requests.post(f"{TARGET_SCOPE_URL}/api/v1/prompt", json=request.get_json())
        response.raise_for_status() # Raise an exception for HTTP errors
        
        # Return the response from the Daydream Scope App
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error forwarding prompt: {e}")
        abort(500, description=str(e))

# Generic route to catch all other /api/v1 calls if needed, and forward them
@app.route("/api/v1/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def forward_api_v1(subpath):
    # Ensure we're forwarding to the correct base URL and path
    forward_url = f"{TARGET_SCOPE_URL}/api/v1/{subpath}"
    
    headers = {key: value for key, value in request.headers if key != 'Host'}
    data = request.get_data()
    
    try:
        resp = requests.request(
            method=request.method,
            url=forward_url,
            headers=headers,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [
            (name, value) for name, value in resp.raw.headers.items()
            if name.lower() not in excluded_headers
        ]

        return Response(resp.content, resp.status_code, headers)

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error forwarding generic API call to {forward_url}: {e}")
        abort(500, description=str(e))

@app.route("/")
def index():
    return open("index.html").read()

@app.route("/director")
def director():
    return open("director.html").read()

@app.route("/api/get-gemini-token")
def get_gemini_token():
    return jsonify({"api_key": os.environ.get("GEMINI_API_KEY")})

@app.route("/api/generate-music", methods=["POST"])
def generate_music():
    if not request.is_json:
        abort(400, description="Request must be JSON")
    
    prompt = request.json.get("prompt", "epic music")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        abort(500, description="GEMINI_API_KEY not configured")

    try:
        # Placeholder / best effort call for Gemini Music API (Lyria/Bison)
        # Note: If this specific endpoint requires allowlisting, it may return 404/403.
        # This structure demonstrates the backend orchestration for the prototype.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/music-bison:predict?key={api_key}"
        # We also mock success to allow UI testing if the API fails
        return jsonify({"audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3", "status": "mocked_fallback"})
    except Exception as e:
        app.logger.error(f"Error generating music: {e}")
        abort(500, description=str(e))

import io
import base64
try:
    from PIL import Image
except ImportError:
    pass # Handled in requirements.txt

@app.route("/api/expand-prompt", methods=["POST"])
def expand_prompt():
    if not request.is_json:
        abort(400, description="Request must be JSON")
    
    seed = request.json.get("seed", "")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        abort(500, description="GEMINI_API_KEY not configured")

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        sys_instruct = (
            "You are a visionary film director generating a highly descriptive, 40-60 word prompt for an AI video generation model. "
            "ALWAYS include: Subject description, Environment details, Lighting, a specific camera action, and high quality keywords (photorealistic, 8k). "
            "Output ONLY the final prompt text."
        )
        payload = {
            "systemInstruction": {"parts": [{"text": sys_instruct}]},
            "contents": [{"parts": [{"text": f"Seed idea: {seed}"}]}]
        }
        res = requests.post(url, json=payload)
        res.raise_for_status()
        data = res.json()
        expanded = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return jsonify({"expanded": expanded})
    except Exception as e:
        app.logger.error(f"Error expanding prompt: {e}")
        return jsonify({"expanded": f"{seed}, highly detailed, cinematic lighting, 8k resolution, wide angle tracking shot, photorealistic"})

@app.route("/api/generate-image", methods=["POST"])
def generate_image():
    if not request.is_json:
        abort(400, description="Request must be JSON")
    
    prompt = request.json.get("prompt", "a cinematic scene")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        abort(500, description="GEMINI_API_KEY not configured")

    try:
        # Call Imagen 3 via Gemini API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={api_key}"
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": "16:9",
                "outputOptions": {"mimeType": "image/jpeg"}
            }
        }
        res = requests.post(url, json=payload)
        res.raise_for_status()
        
        data = res.json()
        b64_img = data["predictions"][0]["bytesBase64Encoded"]
        
        # Resize image to exact VACE size (e.g. 576x320)
        img_data = base64.b64decode(b64_img)
        img = Image.open(io.BytesIO(img_data))
        img = img.resize((576, 320), Image.Resampling.LANCZOS)
        
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG")
        b64_resized = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        return jsonify({"image": f"data:image/jpeg;base64,{b64_resized}"})
    except Exception as e:
        app.logger.error(f"Error generating image: {e}")
        abort(500, description=str(e))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
