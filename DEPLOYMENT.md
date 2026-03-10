# Render.com Deployment for Daydream Scope Live Stream Web Page

This document provides instructions for deploying the `index.html` (Daydream Scope Live Stream Web Page) to Render.com using a GitHub repository and the provided API key.

**Render.com API Key:** `rnd_0synGOzPOIRhsuhIA0KdaGayB331` (Updated from previous value)
**GitHub Repository:** `yepicaiaaron/bigscreenhack-website` (or specific sub-directory if only deploying this component)

## Prerequisites

1.  **Render.com Account:** Ensure you have an active Render.com account.
2.  **GitHub Repository:** The `index.html` and any related static assets (CSS, JS, images) should be pushed to your GitHub repository. For this deployment, we assume they are in the root or a specified sub-directory of `yepicaiaaron/bigscreenhack-website`.
3.  **Render CLI (Optional but Recommended for Automation):** While not strictly required for a manual setup, the Render CLI can automate parts of this process if installed locally.

## Deployment Steps (Manual via Render.com Dashboard)

1.  **Create a New Static Site on Render.com:**
    *   Log in to your Render.com dashboard.
    *   Click on "New" -> "Static Site".
2.  **Connect to GitHub:**
    *   Render.com will prompt you to connect your GitHub account. Authorize Render to access your repositories.
    *   Select the repository: `yepicaiaaron/bigscreenhack-website`.
3.  **Configure Your Static Site:**
    *   **Name:** Choose a unique name for your service (e.g., `daydream-scope-stream`).
    *   **Root Directory (if applicable):** If your `index.html` is not in the root of your repository, specify the sub-directory here (e.g., `public`, `dist`, or `webrtc-demo`).
    *   **Build Command:** Leave empty for a simple static site, or use `npm install && npm run build` if you have a build process (e.g., for a React/Vue app). For this `index.html`, it's likely empty.
    *   **Publish Directory:** Specify the directory containing your `index.html` and other static files after any build process. Often `.` (root), `public`, or `dist`.
    *   **Branches:** Select the branch you want to deploy from (e.g., `main`, `master`).
    *   **Auto Deploy:** Set to "Yes" for automatic deployments on new pushes to the selected branch.
4.  **Advanced Settings (Optional):**
    *   You can add environment variables if your `index.html` needs to consume any (though for this static client-side page, it's unlikely).
5.  **Create Static Site:**
    *   Click "Create Static Site". Render will then fetch your repository, build (if a build command is specified), and deploy your site.
6.  **Update Scope API Base (if necessary):**
    *   **CRITICAL:** The `index.html` currently points to `http://34.44.193.2:8000` as the `SCOPE_API_BASE`. If your Render deployment needs to communicate with a *different* publicly accessible IP/domain for your Scope App, you will need to update this URL in your `index.html` file *before* pushing to GitHub for deployment. This IP (`34.44.193.2`) is likely internal to your GCP deployment and won't be accessible from Render.com unless it's configured as a public endpoint.

## `render.yaml` Blueprint for Infrastructure as Code (Optional)

You can define your service directly in a `render.yaml` file in your repository. This allows for automated provisioning and updates.

```yaml
# render.yaml
# For deploying the Daydream Scope Live Stream Web Page
# This file should be placed in the root of your GitHub repository.

services:
  - type: static_site
    name: daydream-scope-stream
    env: static
    buildCommand: "" # No build command for a simple HTML file, leave empty
    staticPublishPath: "." # Assumes index.html is in the root of the repo
    repo: https://github.com/yepicaiaaron/bigscreenhack-website.git # Replace if different
    branch: main # Or your deployment branch
    pullRequestPreviewsEnabled: true # Optional
    # headers:
    #   - path: /*
    #     name: X-Frame-Options
    #     value: DENY
    # rewrites:
    #   - source: /foo
    #     destination: /bar
    # redirects:
    #   - source: /old
    #     destination: /new
    # environmentVariables:
    #   - key: SCOPE_API_BASE
    #     value: "https://your-public-scope-api.render.com" # Replace with your public Scope API URL if needed
```

**Note on `SCOPE_API_BASE` in `index.html`:** The current `index.html` hardcodes `http://34.44.193.2:8000`. For a public Render.com deployment, the Scope App's API also needs to be publicly accessible, and this IP will likely need to be replaced with a public domain or IP address that Render.com can reach. This might require additional configuration on your GCP deployment for the Scope App to expose its API publicly.
