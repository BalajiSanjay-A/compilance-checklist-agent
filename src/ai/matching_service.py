"""AI evidence matching service using LangChain with provider abstraction."""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.ai.prompts import HUMAN_PROMPT_TEMPLATE, SYSTEM_PROMPT
from src.ai.schemas import EvidenceMatchResult
from src.config import Settings, get_settings
from src.core.exceptions import AIProviderException, EntityNotFoundException
from src.core.logging import get_logger
from src.database.models import (
    ComplianceStatus,
    EvidenceDocument,
    EvidenceMatch,
    Requirement,
)

logger = get_logger("ai.matching")

PROMPT_VERSION = "v1.0"


class BaseLLMService(ABC):
    """Abstract LLM service interface."""

    @abstractmethod
    def evaluate_evidence(
        self,
        requirement_code: str,
        requirement_title: str,
        requirement_description: str,
        evidence_text: str,
    ) -> EvidenceMatchResult:
        """Evaluate evidence against a requirement and return structured result."""
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier."""
        ...


class GrokLLMService(BaseLLMService):
    """Production LLM service using Grok via xAI API (OpenAI-compatible)."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        if not self.settings.xai_api_key:
            raise AIProviderException("XAI_API_KEY is not configured")

        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        self._model = ChatOpenAI(
            model=self.settings.xai_model,
            openai_api_key=self.settings.xai_api_key,
            openai_api_base=self.settings.xai_base_url,
            temperature=0.0,
            max_tokens=2000,
        )
        self._SystemMessage = SystemMessage
        self._HumanMessage = HumanMessage

    def evaluate_evidence(
        self,
        requirement_code: str,
        requirement_title: str,
        requirement_description: str,
        evidence_text: str,
    ) -> EvidenceMatchResult:
        human_content = HUMAN_PROMPT_TEMPLATE.format(
            requirement_code=requirement_code,
            requirement_title=requirement_title,
            requirement_description=requirement_description,
            evidence_text=evidence_text,
        )

        messages = [
            self._SystemMessage(content=SYSTEM_PROMPT),
            self._HumanMessage(content=human_content),
        ]

        try:
            response = self._model.invoke(messages)
            raw_text = response.content.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result = EvidenceMatchResult.model_validate_json(raw_text)
            return result
        except ValidationError as exc:
            raise AIProviderException(
                f"LLM returned invalid structured output: {exc}",
                details={"raw_response": raw_text if 'raw_text' in dir() else "unavailable"},
            )
        except Exception as exc:
            raise AIProviderException(
                f"LLM evaluation failed: {exc}",
            )

    def get_model_name(self) -> str:
        return self.settings.xai_model


class MockLLMService(BaseLLMService):
    """Deterministic mock LLM for testing. Analyzes keywords in evidence text."""

    def evaluate_evidence(
        self,
        requirement_code: str,
        requirement_title: str,
        requirement_description: str,
        evidence_text: str,
    ) -> EvidenceMatchResult:
        text_lower = evidence_text.lower()
        title_lower = requirement_title.lower()

        title_keywords = [w for w in title_lower.split() if len(w) > 3]
        matched_keywords = [k for k in title_keywords if k in text_lower]
        match_ratio = len(matched_keywords) / max(len(title_keywords), 1)

        supporting = []
        sentences = [s.strip() for s in evidence_text.replace("\n", ". ").split(".") if s.strip()]
        for sentence in sentences:
            if any(k in sentence.lower() for k in title_keywords):
                supporting.append(sentence.strip())

        if match_ratio >= 0.5 and supporting:
            return EvidenceMatchResult(
                status="satisfied",
                confidence=min(0.6 + match_ratio * 0.3, 0.95),
                reasoning=f"Evidence contains relevant content matching requirement '{requirement_code}'. "
                          f"Found {len(supporting)} supporting statement(s).",
                supporting_evidence=supporting[:3],
                missing_evidence=[],
                requested_evidence=[],
                expiration_risk="none",
            )
        elif match_ratio > 0 or supporting:
            return EvidenceMatchResult(
                status="partial",
                confidence=max(0.2, match_ratio * 0.5),
                reasoning=f"Evidence partially addresses requirement '{requirement_code}' but lacks complete coverage.",
                supporting_evidence=supporting[:2],
                missing_evidence=[f"Complete documentation for: {requirement_title}"],
                requested_evidence=[f"Detailed evidence demonstrating: {requirement_description[:100]}"],
                expiration_risk="none",
            )
        else:
            return EvidenceMatchResult(
                status="gap",
                confidence=0.1,
                reasoning=f"No relevant evidence found for requirement '{requirement_code}' ({requirement_title}).",
                supporting_evidence=[],
                missing_evidence=[requirement_title],
                requested_evidence=[f"Evidence addressing: {requirement_description[:100]}"],
                expiration_risk="none",
            )

    def get_model_name(self) -> str:
        return "mock-deterministic-v1"


def get_llm_service(settings: Optional[Settings] = None) -> BaseLLMService:
    """Factory: return MockLLMService in test/mock mode, GrokLLMService in production."""
    settings = settings or get_settings()
    if settings.ai_mock_mode:
        return MockLLMService()
    return GrokLLMService(settings)


class EvidenceMatchingAgent:
    """Agent that evaluates evidence against requirements using the LLM service."""

    def __init__(self, llm_service: Optional[BaseLLMService] = None, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.llm = llm_service or get_llm_service(self.settings)

    def match_evidence_to_requirement(
        self,
        session: Session,
        evidence_id: uuid.UUID,
        requirement_id: uuid.UUID,
    ) -> EvidenceMatch:
        """Evaluate evidence against a requirement and persist the match result."""
        evidence = session.get(EvidenceDocument, evidence_id)
        if not evidence:
            raise EntityNotFoundException(
                f"Evidence document '{evidence_id}' not found",
                details={"evidence_id": str(evidence_id)},
            )

        requirement = session.get(Requirement, requirement_id)
        if not requirement:
            raise EntityNotFoundException(
                f"Requirement '{requirement_id}' not found",
                details={"requirement_id": str(requirement_id)},
            )

        if not evidence.content_text:
            raise AIProviderException(
                "Evidence has no extracted text content. Text extraction must complete first.",
                details={"evidence_id": str(evidence_id), "processing_status": evidence.processing_status.value},
            )

        result = self.llm.evaluate_evidence(
            requirement_code=requirement.requirement_code,
            requirement_title=requirement.title,
            requirement_description=requirement.description,
            evidence_text=evidence.content_text,
        )

        status_map = {
            "satisfied": ComplianceStatus.SATISFIED,
            "partial": ComplianceStatus.PARTIAL,
            "gap": ComplianceStatus.GAP,
        }

        match = EvidenceMatch(
            evidence_id=evidence_id,
            requirement_id=requirement_id,
            status=status_map[result.status],
            confidence=result.confidence,
            reasoning=result.reasoning,
            supporting_evidence=result.supporting_evidence,
            missing_evidence=result.missing_evidence,
            requested_evidence=result.requested_evidence,
            citation_verified=False,
            model_name=self.llm.get_model_name(),
            prompt_version=PROMPT_VERSION,
            evaluated_at=datetime.now(timezone.utc),
        )
        session.add(match)
        session.flush()

        logger.info(
            "Evidence match [%s]: evidence=%s requirement=%s status=%s confidence=%.2f",
            match.id, evidence_id, requirement_id, result.status, result.confidence,
        )
        return match
