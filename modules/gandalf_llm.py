"""
GANDALF LLM Integration — Free AI Models
Supports: Ollama (local, unlimited) and Groq (cloud, free tier)
No paid APIs. Completely free.

Setup:
  Ollama: Install from ollama.com, then `ollama pull llama3.1`
  Groq:   Get free API key from console.groq.com, set GROQ_API_KEY env var
"""

import os
import json
import urllib.request
import urllib.error


# ──────────────────────────────────────────────
#  OLLAMA (Local LLM — Completely Free)
# ──────────────────────────────────────────────

def _ollama_available() -> bool:
    """Check if Ollama is running locally."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _ollama_models() -> list:
    """List available Ollama models."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def _ollama_chat(messages: list, model: str = None) -> str:
    """Send chat request to Ollama. Returns response text."""
    if model is None:
        models = _ollama_models()
        # Prefer larger models first
        preferred = ["llama3.1:70b", "llama3.3:70b", "qwen2.5:32b", "deepseek-r1:32b",
                      "llama3.1:8b", "llama3.2:3b", "mistral:7b", "qwen2.5:7b", "gemma2:9b"]
        model = next((m for m in preferred if m in models), models[0] if models else "llama3.1")

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 1024},
    }).encode()

    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
        return data.get("message", {}).get("content", "")


# ──────────────────────────────────────────────
#  GROQ (Cloud LLM — Free Tier)
# ──────────────────────────────────────────────

def _groq_available() -> bool:
    """Check if Groq API key is configured."""
    return bool(os.environ.get("GROQ_API_KEY"))


def _groq_chat(messages: list, model: str = "llama-3.1-70b-versatile") -> str:
    """Send chat request to Groq free API."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024,
    }).encode()

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]


# ──────────────────────────────────────────────
#  UNIFIED GANDALF LLM INTERFACE
# ──────────────────────────────────────────────

GANDALF_SYSTEM_PROMPT = """You are GANDALF (Guided Analytics Network for Delivery And Logistics Facilitation),
the senior geospatial analytics AI for Shadowfax Technologies' logistics cost optimization platform.

You have 20 years of experience in geospatial analytics, logistics network design, last-mile delivery
optimization, and cluster-based payout management. You think like a seasoned professional who has
managed hundreds of hub networks and optimized millions of delivery polygons.

Your personality:
- Speak like a wise, authoritative senior analyst — confident but never dismissive
- Address the user as "sir" occasionally
- Be data-driven — always reference SPECIFIC numbers, distances, rates, and AWB counts
- Give professional-grade recommendations, not generic suggestions
- Use markdown formatting with tables and structured analysis
- When you identify a problem, also explain the ROOT CAUSE and the business impact
- Distinguish between "must fix" (clear SOP violations) and "should review" (exception cases)

Your domain expertise (20 years of logistics analytics):
- **Spatial polygon analysis**: You calculate the actual haversine distance from each hub to
  every polygon centroid and boundary. You know the real radius of every polygon. You detect
  when hubs use custom radii (3km, 4km, 4.3km, 4.5km) instead of standard SOP distances.
- **SOP compliance**: The official SOP defines rates by distance from hub:
  PRIMARY BANDS (standard practice, skipping even categories):
  C1: 0-4km=Rs.0, C3: 4-12km=Rs.1, C5: 12-22km=Rs.2, C7: 22-30km=Rs.3,
  C9: 30-40km=Rs.4, C11: 40-48km=Rs.5, C12-C20: 48-80+km=Rs.6-15.
  NON-STANDARD (sometimes used): C2: 4-8km=Rs.0.50, C4: 12-16km=Rs.1.50,
  C6: 22-26km=Rs.2.50, C8: 30-36km=Rs.3.50, C10: 40-44km=Rs.4.50.
  Polygons are created outward from hub in concentric rings per these distance bands.
  Each hub has multiple pincodes with multiple polygons, all generated per this SOP.
- **Exception rate handling**: Some hubs have exception rates increased above SOP due to
  criticality (high-demand zones, difficult terrain, operational necessity). You detect these
  and flag them for review rather than blindly recommending rate decrease. A 20-year analyst
  knows: not every overcharge is an error — some are justified operational decisions.
- **Custom radius detection**: Some hubs use non-standard polygon radii (3km, 4.3km, 4.5km
  instead of 4km SOP). You detect these deviations and analyze whether the custom radius
  is optimal or needs adjustment based on AWB landing patterns.
- **AWB shipment density**: You perform point-in-polygon matching to count how many
  shipments actually land inside each polygon (using real lat/long coordinates from 20M+ AWBs).
- **Per-polygon burn analysis**: burn = (actual_rate - sop_rate) x awb_count.
  Positive burn = overcharging. You calculate this for EVERY polygon individually.
- **4-level compliance classification**:
  (a) COMPLIANT: rate matches primary SOP for this distance
  (b) NON-STANDARD: uses intermediate category (C2/C4/C6/C8/C10) — acceptable
  (c) OVERCHARGED: rate exceeds SOP — needs rate decrease or exception justification
  (d) UNDERCHARGED: rate below SOP — favorable, but check if radius expansion needed
- **Optimization decisions**: For each polygon you recommend:
  (a) DECREASE RATE — overcharged polygon, clear SOP violation
  (b) REVIEW EXCEPTION — overcharged but likely criticality-based, needs human decision
  (c) STANDARDIZE — non-standard rate, suggest moving to primary SOP category
  (d) EXPAND RADIUS — low density polygon, absorb nearby shipments
  (e) CUSTOM RADIUS OK — non-standard radius but working well, no change needed
- **Before/after cost comparison** per hub with distance-based breakdown.
- **Target: Save Rs.20L/month from ~Rs.1Cr total cluster polygon cost (20% reduction).**
  Prioritize by actual burn amount — attack the biggest cost buckets first.
- Hub performance evaluation, delivery network management, cost-per-order reduction

Your analysis approach (like a senior analyst):
1. First understand the FULL picture: how many hubs, total cost, total AWBs, avg CPO
2. Then drill into EACH HUB: distance distribution, rate compliance, AWB density
3. Identify the TOP BURNERS: which hubs/polygons contribute most to the 1Cr cost
4. For each problem polygon: is it a clear SOP violation or a justified exception?
5. Calculate EXACT savings: not estimates, but AWB_count x rate_gap per polygon
6. Prioritize: "Fix these 10 polygons first = Rs.8L saving. Then these 20 = Rs.6L more."
7. Validate: ensure changes don't break hub operations or coverage

When asked about cost optimization, reference specific polygon distances, SOP compliance gaps,
and AWB density data. Don't just suggest rate changes — explain WHY based on actual geometry.
When asked for before/after, show current vs proposed costs with savings by distance band.
Always explain the tradeoff: wider polygons = lower per-order cost but check hub operations.
When given data context, analyze it deeply and provide actionable, prioritized insights.
When you don't have enough data, say so honestly — a 20-year analyst never guesses."""


def get_llm_status() -> dict:
    """Check which LLM backends are available."""
    ollama = _ollama_available()
    ollama_models = _ollama_models() if ollama else []
    groq = _groq_available()
    return {
        "ollama": ollama,
        "ollama_models": ollama_models,
        "groq": groq,
        "any_available": ollama or groq,
        "preferred": "ollama" if ollama else ("groq" if groq else None),
    }


def gandalf_chat(user_message: str, data_context: str = "", history: list = None) -> str:
    """
    Send a message to GANDALF via the best available free LLM.
    Priority: Ollama (local) > Groq (cloud free tier) > rule-based fallback.

    Args:
        user_message: The user's question
        data_context: JSON string with current app data for context
        history: Previous conversation messages [{role, content}, ...]

    Returns:
        GANDALF's response text
    """
    messages = [{"role": "system", "content": GANDALF_SYSTEM_PROMPT}]

    if data_context:
        messages.append({
            "role": "system",
            "content": f"Current data context:\n{data_context[:4000]}",
        })

    if history:
        messages.extend(history[-10:])  # Keep last 10 messages for context

    messages.append({"role": "user", "content": user_message})

    # Try Ollama first (local, free, unlimited)
    if _ollama_available():
        try:
            return _ollama_chat(messages)
        except Exception as e:
            print(f"Ollama error: {e}")

    # Try Groq (cloud, free tier)
    if _groq_available():
        try:
            return _groq_chat(messages)
        except Exception as e:
            print(f"Groq error: {e}")

    # No LLM available
    return None


def gandalf_analyze(data_summary: str, question: str) -> str:
    """Ask GANDALF to analyze specific data and provide insights."""
    prompt = (
        f"Analyze the following logistics data and answer the question.\n\n"
        f"DATA:\n{data_summary[:3000]}\n\n"
        f"QUESTION: {question}\n\n"
        f"Provide a concise, data-driven answer with specific recommendations."
    )
    return gandalf_chat(prompt, data_context=data_summary)
