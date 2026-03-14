import asyncio
import os
import json
import base64
import aiohttp
import websockets

class SuperProjectEngine:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be provided or set in environment variables.")

    async def expand_prompt(self, seed: str, previous_context: str = "") -> dict:
        """
        Uses Gemini Flash to expand a short seed into a detailed video prompt and music prompt,
        while maintaining scene continuity.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        
        sys_instruct = (
            "You are a visionary film director generating prompts for an AI video generation model. "
            "You must output a JSON object containing exactly three fields: 'prompt' (string), 'music_prompt' (string), and 'is_new_scene' (boolean). "
            "1. 'prompt': A highly descriptive 40-60 word prompt. ALWAYS include Subject description, Environment details, Lighting, camera action, and high quality keywords (photorealistic, 8k). If it is a continuation of the previous scene, ensure the camera action flows naturally from the previous shot. "
            "2. 'music_prompt': A highly varied, dynamic 5-15 word description of the perfect background music for this exact scene (e.g., 'pulsing cyberpunk dark synthwave with heavy bass' or 'ethereal orchestral string arrangement, building tension'). Avoid generic terms; specify genres, instruments, and mood. "
            "3. 'is_new_scene': If the user's seed is a continuation of the previous context/characters, set to false. If it introduces a completely new scene, new location, or new characters, set to true. "
        )
        
        context_msg = f"Previous scene context: {previous_context}\n\nNew Seed idea: {seed}" if previous_context else f"New Seed idea: {seed}"
        
        payload = {
            "systemInstruction": {"parts": [{"text": sys_instruct}]},
            "contents": [{"parts": [{"text": context_msg}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                result_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                result_json = json.loads(result_text)
                
                return {
                    "expanded": result_json.get("prompt", seed),
                    "music_prompt": result_json.get("music_prompt", f"cinematic underscore: {seed}"),
                    "is_new_scene": result_json.get("is_new_scene", True)
                }

    async def generate_voiceover(self, instruction: str, audio_callback):
        """
        Connects to Gemini Live API to generate a dramatic voiceover stream based on the instruction.
        audio_callback should be an async function that takes (pcm_bytes: bytes) at 24000Hz.
        """
        ws_url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={self.api_key}"
        
        async with websockets.connect(ws_url) as ws:
            setup_msg = {
                "setup": {
                    "model": "models/gemini-2.5-flash-native-audio-latest",
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {
                            "voiceConfig": {
                                "prebuiltVoiceConfig": {
                                    "voiceName": "Aoede"
                                }
                            }
                        }
                    },
                    "systemInstruction": {
                        "parts": [{"text": "You are a dramatic narrator. Speak short, punchy, cinematic narration for a scene. Do not output text, only speak."}]
                    }
                }
            }
            await ws.send(json.dumps(setup_msg))

            client_content = {
                "clientContent": {
                    "turns": [{"role": "user", "parts": [{"text": instruction}]}],
                    "turnComplete": True
                }
            }
            await ws.send(json.dumps(client_content))

            async for message in ws:
                msg_data = json.loads(message)
                if "serverContent" in msg_data and "modelTurn" in msg_data["serverContent"]:
                    for part in msg_data["serverContent"]["modelTurn"].get("parts", []):
                        if "inlineData" in part and "data" in part["inlineData"]:
                            b64_data = part["inlineData"]["data"]
                            binary_data = base64.b64decode(b64_data)
                            
                            # Trim to valid Int16 boundary
                            valid_len = len(binary_data)
                            if valid_len % 2 != 0:
                                valid_len -= 1
                            
                            await audio_callback(binary_data[:valid_len])

    async def generate_music(self, prompt: str, audio_callback):
        """
        Connects to Lyria Music API to generate continuous background music based on the prompt.
        audio_callback should be an async function that takes (pcm_bytes: bytes) at 48000Hz.
        """
        ws_url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateMusic?key={self.api_key}"
        
        async with websockets.connect(ws_url) as ws:
            setup_msg = {"setup": {"model": "models/lyria-realtime-exp"}}
            await ws.send(json.dumps(setup_msg))

            await ws.send(json.dumps({"clientContent": {"weightedPrompts": [{"text": prompt, "weight": 1.0}]}}))
            await ws.send(json.dumps({"musicGenerationConfig": {"temperature": 1.0, "bpm": 90}}))
            await ws.send(json.dumps({"playbackControl": "PLAY"}))

            async for message in ws:
                msg_data = json.loads(message)
                if "serverContent" in msg_data and "audioChunks" in msg_data["serverContent"]:
                    for chunk in msg_data["serverContent"]["audioChunks"]:
                        if "data" in chunk:
                            b64_data = chunk["data"]
                            binary_data = base64.b64decode(b64_data)
                            
                            valid_len = len(binary_data)
                            if valid_len % 2 != 0:
                                valid_len -= 1
                            
                            await audio_callback(binary_data[:valid_len])

# Example usage:
# engine = SuperProjectEngine()
# expanded = await engine.expand_prompt("Cyberpunk detective finds a clue")
# await engine.generate_voiceover("Narrate this dramatically: " + expanded['expanded'], my_audio_callback)
