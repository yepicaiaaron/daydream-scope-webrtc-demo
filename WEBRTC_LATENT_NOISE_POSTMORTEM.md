# WebRTC & Daydream Scope Backend Troubleshooting: The "Latent Noise" Bug

## The Problem
When connecting to the Daydream Scope PyTorch backend (`34.44.193.2:8000`) via a custom WebRTC proxy/demo UI, the video stream would successfully connect and broadcast at 25 FPS, but the visual output was pure, colorful "blocky" static (unprocessed latent noise) instead of the requested video generation. 

This occurred despite the fact that the Native UI (`http://34.44.193.2:8000/`) was able to successfully stream clear, coherent video (e.g., a 3D animated panda) using the exact same backend.

## The Troubleshooting Journey (What We Tried & Why It Failed)

### Phase 1: Diagnosing Backend Crashes (Tensor Mismatches)
* **Initial Observation:** The `memflow` and `longlive` pipelines were completely crashing upon initialization when called from our proxy.
* **The Error:** `RuntimeError: The expanded size of the tensor (0) must match the existing size (2160) at non-singleton dimension 1.`
* **What We Tried:**
  1. We initially thought the payload was completely malformed.
  2. We discovered the proxy was sending a barebones WebRTC offer payload.
* **The Fix:** We had to mirror the exact `INITIAL_PARAMS` structure the native UI uses. The backend requires specific configuration keys (`height`, `width`, `vace_enabled`, `vace_context_scale`, `manage_cache`, `noise_controller`, `denoising_step_list`, `pipeline_ids`) to properly initialize the tensor shapes. Once we populated these in the `/api/v1/webrtc/offer` payload, the PyTorch tensor crashes stopped, and the pipeline worker thread began running successfully.

### Phase 2: The "Latent Noise" Anomaly
* **The Symptom:** Even after fixing the tensor crashes, the WebRTC stream delivered perfect, high-definition, 25 FPS colorful static.
* **Hypothesis 1: WebRTC Channeling/Signaling Issue (Failed)**
  * *Theory:* Packet loss, MTU limits, or UDP transport degradation was corrupting the video frames over the wire.
  * *Test:* Ran WebRTC `getStats()` via Playwright during a live stream.
  * *Result:* Packet loss was 0%. NACKs and PLIs were near zero. The stream was flawless. 
  * *Conclusion:* The colorful static was *intentional*. The WebRTC encoder was perfectly encoding and transmitting pure noise.
* **Hypothesis 2: PyTorch Math Corruption / NaN Outputs (Failed)**
  * *Theory:* The underlying `causal_model.py` attention mechanism was generating `NaN` (Not a Number) or `Infinity` values due to precision errors, causing the image to blow out into static.
  * *Test:* SSH'd into the GPU instance, created a git branch (`debug-longlive-noise-1`), and injected a `print(tensor.shape, tensor.mean())` statement directly into `src/scope/core/pipelines/longlive/pipeline.py` right before the frame processor.
  * *Result:* The logs output `DEBUG LONGLIVE - Output Video Shape: torch.Size([1, 12, 3, 320, 576]), Mean: -0.2624`.
  * *Conclusion:* The tensor shape was perfectly correct for an RGB image batch, and the mean was healthy (no NaNs). The VAE decoder was successfully translating the latent space to pixel space.

### Phase 3: The Smoking Gun (Text Conditioning Weight)
* **The Epiphany:** If the PyTorch math is healthy and the stream is healthy, the U-Net model must be intentionally skipping the denoising steps. In diffusion models, if the text conditioning (the prompt) is ignored, the model outputs unconditional noise.
* **The Deep Dive:** We wrote a Playwright script to physically automate the Native UI (`http://34.44.193.2:8000/`), click the "ON" button, and intercept the exact WebSocket/HTTP payload it sends to the backend when starting a stream.
* **The Critical Discovery:** We compared the intercepted Native UI payload to our WebRTC proxy payload.
  * *Our Proxy Payload:* `"prompts": [{"text": "A cinematic landscape", "weight": 1.0}]`
  * *Native UI Payload:* `"prompts": [{"text": "A 3D animated scene. A **panda** walks...", "weight": 100.0}]`
* **The Root Cause:** The text encoder configuration on the backend is highly sensitive to the prompt `weight`. By sending a weight of `1.0`, our proxy was effectively muting the text prompt to 1% strength. The model had no conditioning data, so it correctly output 99% random noise. The Native UI defaults to a weight of `100.0`.

## The Final Solution
We updated the `INITIAL_PARAMS` in our WebRTC proxy `index.html` to perfectly match the Native UI's initialization state:

```javascript
const INITIAL_PARAMS = {
    pipeline_ids: ["longlive"],
    input_mode: "text",
    prompts: [{ text: "A 3D animated scene. A **panda** walks along a path towards the camera in a park on a spring day.", weight: 100.0 }],
    prompt_interpolation_method: "linear",
    denoising_step_list: [1000, 750, 500, 250],
    manage_cache: true,
    vace_enabled: true,
    vace_context_scale: 1.0,
    recording: false
};
```

Once the `weight: 100.0` and the correct `denoising_step_list` were applied, the backend U-Net successfully conditioned on the prompt, denoised the latent tensor, and streamed the animated panda perfectly over the WebRTC channel.

## Key Takeaways for Future Developers
1. **Latent Noise != Network Noise:** In generative AI streaming, if you see crisp, colorful, blocky static, do not blame the network transport (WebRTC/UDP). That is the visual signature of a Diffusion Model outputting raw latent space due to missing conditioning, zeroed weights, or skipped denoising steps.
2. **Payload Parity is Mandatory:** The Daydream Scope backend is extremely strict about initialization parameters. Missing keys (like `vace_enabled`) will cause hard PyTorch tensor crashes (`RuntimeError: The expanded size of the tensor (0) must match...`).
3. **Weight Scaling:** The prompt `weight` parameter operates on a 0-100 scale (or higher), not a 0.0-1.0 normalized scale. Sending `1.0` will result in unconditional noise.
4. **Debugging Methodology:** When debugging cloud PyTorch pipelines, injecting raw `print(tensor.shape)` statements via SSH is infinitely faster than guessing. Always verify the math before blaming the transport layer.