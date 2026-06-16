from google import genai
from anthropic import Anthropic
from openai import OpenAI
import yaml
import os
import logging
import requests
from langfuse import observe as traceable, get_client as _get_langfuse_client

# Suppress the "Failed to detach context" noise from OpenTelemetry.
# This warning fires when Langfuse's internal @observe decorators run inside
# copy_context() worker threads — the token was created in the copied context
# but OTel tries to reset it in the parent. It is non-fatal and does not affect
# tracing correctness; suppressing it keeps logs clean.
logging.getLogger("opentelemetry.context").setLevel(logging.CRITICAL)

# Load .env file directly (without load_dotenv)
def load_env_file(env_path: str = ".env") -> dict:
    """Parse .env file and return a dictionary of key-value pairs."""
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                # Parse KEY=VALUE
                if "=" in line:
                    key, value = line.split("=", 1)
                    # Strip inline comments (e.g. value  # comment)
                    value = value.split("#")[0].strip().strip('"').strip("'")
                    env_vars[key.strip()] = value
    # Merge with os.environ (Cloud Run env vars take precedence)
    langfuse_keys = ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"]
    for key in ["GEMINI_API_KEY", "CLAUDE_API_KEY", "OPENAI_API_KEY", "YOU_API_KEY", "LLM_PROVIDER", "LLM_MODEL", "USE_SEARCH"] + langfuse_keys:
        if key in os.environ:
            env_vars[key] = os.environ[key]
    return env_vars

# Resolve .env path relative to this file, regardless of working directory
_env_path = os.path.join(os.path.dirname(__file__), ".env")
_env = load_env_file(_env_path)

# Push Langfuse config into os.environ so the SDK picks it up automatically
for _lf_key in ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"]:
    if _lf_key in _env and _env[_lf_key]:
        os.environ.setdefault(_lf_key, _env[_lf_key])

# Load configuration
_prompts_path = os.path.join(os.path.dirname(__file__), "prompts.yaml")
_config = yaml.safe_load(open(_prompts_path, encoding='utf-8'))
# Inject today's date so the LLM never outputs placeholder dates like "[Current Date]"
_today = __import__("datetime").date.today().strftime("%B %d, %Y")
_system_prompt = _config["system_prompt"] + f"\n\nToday's date is {_today}."

# Export all prompts for use by other modules
PROMPTS = _config


def format_prompt(template: str, **kwargs) -> str:
    """
    Safely substitute {key} placeholders in a prompt template without using
    Python's str.format(), which breaks when the user's input contains literal
    curly braces (e.g. JSON snippets, error messages, code).

    Only replaces exact {key} tokens listed in kwargs — all other braces
    (including {{ }} escape sequences used for JSON examples in the template)
    are left untouched.
    """
    result = template
    for key, value in kwargs.items():
        result = result.replace("{" + key + "}", str(value))
    return result

# LLM Configuration from .env file
_llm_provider = _env.get("LLM_PROVIDER", "gemini").lower()
_llm_model = _env.get("LLM_MODEL", "")

# Default models for each provider
_default_models = {
    "gemini": "gemini-2.5-flash",
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "you": "you",
}

# Initialize clients
_gemini_client = None
_claude_client = None
_openai_client = None
_you_api_key = _env.get("YOU_API_KEY", "").strip()

if _env.get("GEMINI_API_KEY"):
    _gemini_client = genai.Client(api_key=_env.get("GEMINI_API_KEY", "").strip())

if _env.get("CLAUDE_API_KEY"):
    _claude_client = Anthropic(api_key=_env.get("CLAUDE_API_KEY", "").strip())

if _env.get("OPENAI_API_KEY"):
    _openai_client = OpenAI(api_key=_env.get("OPENAI_API_KEY", "").strip())


def _get_model_for_provider(provider: str) -> str:
    """Get the model name for the specified provider."""
    if _llm_model:
        return _llm_model
    return _default_models.get(provider, _default_models["gemini"])


@traceable(name="gemini-generate", as_type="generation")
def _generate_with_gemini(prompt: str, model: str, use_search: bool = False) -> str:
    """Generate response using Gemini."""
    if not _gemini_client:
        raise ValueError("Gemini client not initialized. Check GEMINI_API_KEY.")

    config = {
        "temperature": 0,
        "top_p": 0.95,
        "top_k": 20,
        "system_instruction": _system_prompt,
    }
    if use_search:
        config["tools"] = [{"google_search": {}}]

    response = _gemini_client.models.generate_content(
        model=model,
        contents={"text": prompt},
        config=config,
    )

    # Report token usage to Langfuse so it can calculate cost
    usage = getattr(response, "usage_metadata", None)
    if usage:
        try:
            _lf = _get_langfuse_client()
            _lf.update_current_generation(
                model=model,
                usage_details={
                    "input": getattr(usage, "prompt_token_count", 0),
                    "output": getattr(usage, "candidates_token_count", 0),
                    "total": getattr(usage, "total_token_count", 0),
                },
            )
        except Exception as _lf_err:
            print(f"[langfuse] Failed to update usage metadata: {_lf_err}")

    # Safely extract text — response.text raises ValueError if response was blocked
    try:
        return response.text
    except ValueError:
        # Try extracting from candidates directly
        if response.candidates:
            parts = response.candidates[0].content.parts
            if parts:
                return "".join(p.text for p in parts if hasattr(p, "text"))
        raise ValueError(f"Gemini returned no text. Finish reason: {response.candidates[0].finish_reason if response.candidates else 'unknown'}")


@traceable(name="claude-generate", as_type="generation")
def _generate_with_claude(prompt: str, model: str, use_search: bool = False) -> str:
    """Generate response using Claude."""
    if not _claude_client:
        raise ValueError("Claude client not initialized. Check CLAUDE_API_KEY.")

    if use_search:
        print("Warning: google_search is not supported for Claude. Proceeding without search.")

    response = _claude_client.messages.create(
        model=model,
        max_tokens=8192,
        temperature=0,
        system=_system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


@traceable(name="openai-generate", as_type="generation")
def _generate_with_openai(prompt: str, model: str, use_search: bool = False) -> str:
    """Generate response using OpenAI."""
    if not _openai_client:
        raise ValueError("OpenAI client not initialized. Check OPENAI_API_KEY.")

    if use_search:
        # web_search_preview is only supported in the Responses API with gpt-4o family
        search_model = model if model.startswith("gpt-4o") else "gpt-4o"
        if search_model != model:
            print(f"Note: '{model}' does not support web search. Switching to '{search_model}' for search.")
        print(f"Note: Using OpenAI Responses API with web_search_preview (model: {search_model}).")
        response = _openai_client.responses.create(
            model=search_model,
            instructions=_system_prompt,
            input=prompt,
            tools=[{"type": "web_search_preview"}],
        )
        return response.output_text
    else:
        response = _openai_client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": _system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content


@traceable(name="you-generate", as_type="generation")
def _generate_with_you(prompt: str, model: str, use_search: bool = True) -> str:
    """Generate response using You.com Search API."""
    if not _you_api_key:
        raise ValueError("You.com API key not initialized. Check YOU_API_KEY.")

    # You.com Search API endpoint
    url = "https://api.you.com/search"
    headers = {
        "x-api-key": _you_api_key,
        "Accept": "application/json",
    }
    params = {
        "query": prompt,
        "web_search_options": {
            "search_type": "search",  # or "news", "images", "videos"
        },
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    # Extract top results and format as context
    results = data.get("results", [])
    if not results:
        return "No results found from You.com search."

    # Format results for LLM consumption
    formatted_results = "\n\n".join([
        f"Title: {r.get('title', 'N/A')}\n"
        f"URL: {r.get('url', 'N/A')}\n"
        f"Description: {r.get('description', 'N/A')}"
        for r in results[:5]  # Top 5 results
    ])

    # Now use the LLM to synthesize an answer from the search results
    synthesis_prompt = f"""Based on the following search results from You.com, provide a concise answer to the query:

Query: {prompt}

Search Results:
{formatted_results}

Answer:"""

    # Use the configured LLM to synthesize from search results
    selected_model = model or _get_model_for_provider("you")
    return _generate_with_openai(synthesis_prompt, selected_model, use_search=False)


@traceable(name="generate-response", as_type="chain")
def generate_response(prompt: str, provider: str = None, model: str = None, use_search: bool = False) -> str:
    """
    Generate a response using the configured LLM provider and model.

    Args:
        prompt: The user prompt to send to the LLM
        provider: Optional override for LLM provider ('gemini', 'claude', or 'openai')
        model: Optional override for specific model name
        use_search: Enable web search tool (google_search for Gemini,
                    web_search_preview for OpenAI, ignored for Claude)

    Returns:
        Generated text response from the LLM

    Raises:
        ValueError: If provider is not supported or client not initialized
    """
    selected_provider = (provider or _llm_provider).lower()
    selected_model = model or _get_model_for_provider(selected_provider)

    print(f"Using provider: {selected_provider}, model: {selected_model}, search: {use_search}")

    try:
        if selected_provider == "gemini":
            return _generate_with_gemini(prompt, selected_model, use_search)
        elif selected_provider == "claude":
            return _generate_with_claude(prompt, selected_model, use_search)
        elif selected_provider == "openai":
            return _generate_with_openai(prompt, selected_model, use_search)
        elif selected_provider == "you":
            return _generate_with_you(prompt, selected_model, use_search)
        else:
            raise ValueError(f"Unsupported LLM provider: {selected_provider}")

    except Exception as e:
        # Fallback logic for Gemini 503 errors
        if selected_provider == "gemini" and ("503" in str(e) or "unavailable" in str(e).lower()):
            print(f"Gemini unavailable (503), falling back to OpenAI: {e}")
            if _openai_client:
                fallback_model = _default_models["openai"]
                # google_search is Gemini-only; use OpenAI's search equivalent on fallback
                return _generate_with_openai(prompt, fallback_model, use_search)
            else:
                raise ValueError("Fallback to OpenAI failed: OpenAI client not initialized. Check OPENAI_API_KEY.")
        raise
