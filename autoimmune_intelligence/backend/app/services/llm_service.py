import logging
from app.models.schema import QueryResponse

logger = logging.getLogger(__name__)


class LLMService:
    """Handles LLM interactions for the Autoimmune Intelligence API.

    Stub implementation returns structured dummy output.
    Replace ``_call_llm`` with an OpenAI or other LLM provider call.
    """

    def query(self, question: str) -> QueryResponse:
        logger.info("LLMService.query called with question=%r", question)
        answer, sources = self._call_llm(question)
        return QueryResponse(answer=answer, sources=sources)

    def _call_llm(self, question: str) -> tuple[str, list[str]]:
        """Stub LLM call — replace with real provider integration."""
        logger.debug("_call_llm stub invoked for question=%r", question)
        answer = (
            f"Based on current immunological research, the query '{question}' "
            "relates to dysregulated cytokine signalling — particularly the "
            "JAK-STAT and NF-\u03baB pathways — which are implicated in a broad "
            "spectrum of autoimmune disorders. Targeted inhibition of upstream "
            "mediators such as IL-6 and TNF-\u03b1 has demonstrated clinical "
            "efficacy across rheumatoid arthritis, lupus, and inflammatory bowel "
            "disease cohorts."
        )
        sources = [
            "Firestein GS. Nature. 2003;423:356-361.",
            "Tanaka T, et al. J Clin Med. 2016;5(2):14.",
            "O'Shea JJ, et al. Nat Rev Drug Discov. 2004;3:555-564.",
        ]
        return answer, sources
