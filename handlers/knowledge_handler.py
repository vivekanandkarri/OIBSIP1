"""Knowledge handler module for PyVoice Assistant.

Queries the Wikipedia API for general search terms, falling back to OpenAI GPT or
Anthropic Claude for complex questions. Truncates answers to 3 sentences.
"""

import os
import re
import logging
from typing import Any, Dict
from handlers.base_handler import BaseHandler, HandlerError

logger = logging.getLogger("PyVoice.Handlers.Knowledge")

# Optional imports for LLMs
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class KnowledgeHandler(BaseHandler):
    """Answers factual questions using Wikipedia or LLM engines."""

    def execute(self, entities: Dict[str, Any]) -> str:
        """Looks up a query on Wikipedia or forwards to a generative LLM.

        Args:
            entities: Extracted entities, should contain "query".

        Returns:
            A concise response string (max 3 sentences).
        """
        query = entities.get("query")
        if not query:
            raise HandlerError("What would you like me to look up?")

        logger.info(f"Knowledge lookup query: '{query}'")

        # 1. Attempt Wikipedia Lookup
        wiki_response = self._search_wikipedia(query)
        if wiki_response:
            return self._truncate_sentences(wiki_response)

        # 2. Wikipedia didn't match. Fall back to LLM (OpenAI or Anthropic)
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if openai_key and not openai_key.startswith("your_") and OPENAI_AVAILABLE:
            try:
                logger.info("Wikipedia returned nothing. Using OpenAI fallback...")
                client = OpenAI(api_key=openai_key)
                completion = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are Nova, a helpful voice assistant. Answer the user's question concisely in under three sentences."},
                        {"role": "user", "content": query}
                    ],
                    max_tokens=150,
                    temperature=0.7
                )
                answer = completion.choices[0].message.content.strip()
                return self._truncate_sentences(answer)
            except Exception as e:
                logger.error(f"OpenAI fallback query failed: {e}")

        elif anthropic_key and not anthropic_key.startswith("your_") and ANTHROPIC_AVAILABLE:
            try:
                logger.info("Wikipedia returned nothing. Using Anthropic fallback...")
                client = anthropic.Anthropic(api_key=anthropic_key)
                message = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=150,
                    system="You are Nova, a helpful voice assistant. Answer the user's question concisely in under three sentences.",
                    messages=[
                        {"role": "user", "content": query}
                    ]
                )
                answer = message.content[0].text.strip()
                return self._truncate_sentences(answer)
            except Exception as e:
                logger.error(f"Anthropic fallback query failed: {e}")

        # 3. Complete Fallback Mock if no keys or APIs succeeded
        logger.info("No LLM keys or API responses succeeded. Returning mock/default facts.")
        return self._get_mock_fact(query)

    def _search_wikipedia(self, query: str) -> Optional[str]:
        """Queries the Wikipedia API (using secure HTTPS requests) for the query."""
        try:
            # We search Wikipedia for titles matching query
            search_url = "https://en.wikipedia.org/w/api.php"
            search_params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json"
            }
            
            search_res = self.secure_request(search_url, params=search_params).json()
            search_results = search_res.get("query", {}).get("search", [])
            
            if not search_results:
                return None
            
            # Take the best matching title
            best_title = search_results[0]["title"]
            logger.info(f"Wikipedia matched page title: '{best_title}'")

            # Fetch the introduction paragraph of that page
            intro_params = {
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "redirects": 1,
                "titles": best_title,
                "format": "json"
            }
            intro_res = self.secure_request(search_url, params=intro_params).json()
            pages = intro_res.get("query", {}).get("pages", {})
            
            for page_id, page_data in pages.items():
                if page_id != "-1" and "extract" in page_data:
                    extract = page_data["extract"].strip()
                    if extract:
                        return extract
            
            return None
        except Exception as e:
            logger.warning(f"Wikipedia search failed: {e}")
            return None

    def _truncate_sentences(self, text: str, max_sentences: int = 3) -> str:
        """Helper to truncate text to a maximum number of sentences."""
        # Regex to split text by typical sentence terminators (. ! ?) followed by whitespace or end of string
        sentences = re.split(r'(?<=[.!?])\s+', text)
        clean_sentences = [s.strip() for s in sentences if s.strip()]
        
        truncated = " ".join(clean_sentences[:max_sentences])
        
        # Ensure it ends with punctuation if truncated
        if truncated and truncated[-1] not in ('.', '!', '?'):
            truncated += "."
            
        return truncated

    def _get_mock_fact(self, query: str) -> str:
        """Generates realistic fallback response if no internet/LLM keys exist."""
        query_lower = query.lower()
        if "sky" in query_lower and "blue" in query_lower:
            return "The sky is blue because the Earth's atmosphere scatters sunlight in all directions, and blue light is scattered more than other colors because it travels as shorter, smaller waves. This is called Rayleigh scattering."
        elif "meaning" in query_lower and "life" in query_lower:
            return "The meaning of life is a subjective question, but many philosophers and scientists suggest it is to seek happiness, connection, and learning. In fiction, Douglas Adams famously wrote that the answer is 42."
        elif "gravity" in query_lower:
            return "Gravity is a fundamental force by which a planet or other body draws objects toward its center. It is what keeps planets in orbit and objects on the ground."
            
        # General generic fallback
        return f"I looked up {query}, but since I don't have access to active LLM keys or Wikipedia at the moment, I can only tell you that it's a fascinating topic worth exploring!"
