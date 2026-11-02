from dataclasses import dataclass
import json
import threading
import time
from typing import Callable, Protocol

import httpx

from app.config import Settings


@dataclass(frozen=True)
class LLMGenerationResult:
    raw_text: str | None
    latency_ms: int
    model_id: str
    provider: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error: str | None = None


class LLMServiceInterface(Protocol):
    """Giao diện trừu tượng LLM_Service_Interface (Adapter Pattern - Mục 2.2.2 Chương 2)."""

    model_id: str
    provider_name: str

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        timeout_seconds: float = 15.0,
        max_tokens: int = 400,
    ) -> LLMGenerationResult: ...


def _parse_chat_completion_json(
    data: object,
    *,
    default_model_id: str,
    provider_name: str,
    latency_ms: int,
    empty_error_code: str,
) -> LLMGenerationResult:
    if not isinstance(data, dict):
        return LLMGenerationResult(
            raw_text=None,
            latency_ms=latency_ms,
            model_id=default_model_id,
            provider=provider_name,
            error="llm_invalid_payload",
        )
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return LLMGenerationResult(
            raw_text=None,
            latency_ms=latency_ms,
            model_id=default_model_id,
            provider=provider_name,
            error="llm_invalid_choices",
        )
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return LLMGenerationResult(
            raw_text=None,
            latency_ms=latency_ms,
            model_id=default_model_id,
            provider=provider_name,
            error="llm_invalid_choices",
        )
    message = first_choice.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    return LLMGenerationResult(
        raw_text=content if isinstance(content, str) else None,
        latency_ms=latency_ms,
        model_id=str(data.get("model") or default_model_id),
        provider=provider_name,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        error=None if isinstance(content, str) else empty_error_code,
    )


class _OpenAICompatibleAdapter:
    """Lớp cơ sở dùng chung cho các Adapter gọi REST API chuẩn OpenAI Chat Completions, an toàn đa luồng."""

    provider_name: str
    empty_error_code: str
    timeout_error_code: str
    transport_error_code: str

    def __init__(
        self,
        settings: Settings,
        *,
        model_id: str,
        client: httpx.Client | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self.model_id = model_id
        self._client = client
        self._owns_client = client is None
        self._client_lock = threading.Lock()
        self.monotonic = monotonic

    def _get_client(self, base_url: str, timeout_seconds: float) -> httpx.Client:
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    self._client = httpx.Client(
                        base_url=base_url.rstrip("/"),
                        timeout=timeout_seconds,
                    )
        return self._client

    def close(self) -> None:
        with self._client_lock:
            if self._owns_client and self._client is not None:
                self._client.close()
                self._client = None

    def _post_chat_completion(
        self,
        *,
        base_url: str,
        headers: dict[str, str],
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout_seconds: float,
        max_tokens: int,
        started: float,
    ) -> LLMGenerationResult:
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        http_client = self._get_client(base_url, timeout_seconds)
        try:
            response = http_client.post(
                "/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            return _parse_chat_completion_json(
                data,
                default_model_id=self.model_id,
                provider_name=self.provider_name,
                latency_ms=round((self.monotonic() - started) * 1000),
                empty_error_code=self.empty_error_code,
            )
        except httpx.TimeoutException:
            return LLMGenerationResult(
                raw_text=None,
                latency_ms=round((self.monotonic() - started) * 1000),
                model_id=self.model_id,
                provider=self.provider_name,
                error=self.timeout_error_code,
            )
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return LLMGenerationResult(
                raw_text=None,
                latency_ms=round((self.monotonic() - started) * 1000),
                model_id=self.model_id,
                provider=self.provider_name,
                error=self.transport_error_code,
            )


class APIDemoAdapter(_OpenAICompatibleAdapter):
    """Chế độ Vận hành/Demo: gọi REST API tương thích chuẩn OpenAI Chat Completions."""

    provider_name = "api_demo"
    empty_error_code = "llm_empty_content"
    timeout_error_code = "llm_timeout"
    transport_error_code = "llm_transport_or_protocol_error"

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(
            settings,
            model_id=settings.llm_model_id,
            client=client,
            monotonic=monotonic,
        )

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        timeout_seconds: float = 15.0,
        max_tokens: int = 400,
    ) -> LLMGenerationResult:
        started = self.monotonic()
        if not self.settings.llm_api_key:
            return LLMGenerationResult(
                raw_text=None,
                latency_ms=0,
                model_id=self.model_id,
                provider=self.provider_name,
                error="llm_api_key_not_configured",
            )
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.llm_api_key}",
        }
        return self._post_chat_completion(
            base_url=self.settings.llm_api_base_url,
            headers=headers,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            started=started,
        )


class ColabQwenAdapter(_OpenAICompatibleAdapter):
    """Chế độ Nghiên cứu & Đánh giá: Qwen2.5-Coder-7B-Instruct trên Google Colab T4."""

    provider_name = "colab_qwen"
    empty_error_code = "colab_qwen_empty_content"
    timeout_error_code = "colab_qwen_timeout"
    transport_error_code = "colab_qwen_transport_error"

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(
            settings,
            model_id=settings.colab_qwen_model_id,
            client=client,
            monotonic=monotonic,
        )

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        timeout_seconds: float = 15.0,
        max_tokens: int = 400,
    ) -> LLMGenerationResult:
        started = self.monotonic()
        endpoint = self.settings.colab_qwen_endpoint_url
        if not endpoint:
            return LLMGenerationResult(
                raw_text=None,
                latency_ms=0,
                model_id=self.model_id,
                provider=self.provider_name,
                error="colab_qwen_endpoint_not_configured",
            )
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true",
        }
        if self.settings.colab_qwen_api_key:
            headers["Authorization"] = f"Bearer {self.settings.colab_qwen_api_key}"
        return self._post_chat_completion(
            base_url=endpoint,
            headers=headers,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            started=started,
        )


class DisabledLLMAdapter:
    """Chế độ tắt AI tường minh: luôn báo dịch vụ chưa cấu hình và không trừ lượt."""

    model_id = "disabled"
    provider_name = "disabled"

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        timeout_seconds: float = 15.0,
        max_tokens: int = 400,
    ) -> LLMGenerationResult:
        return LLMGenerationResult(
            raw_text=None,
            latency_ms=0,
            model_id=self.model_id,
            provider=self.provider_name,
            error="llm_provider_disabled",
        )


class FakeLLMAdapter:
    """Fake provider có dán nhãn rõ ràng chỉ dành cho kiểm thử tự động & chạy thử offline."""

    def __init__(
        self,
        responses: list[str | LLMGenerationResult] | None = None,
        *,
        model_id: str = "fake-poc-provider",
    ) -> None:
        self.model_id = model_id
        self.provider_name = "fake"
        self._responses = list(responses) if responses is not None else []
        self.calls: list[dict[str, object]] = []
        self._lock = threading.Lock()

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        timeout_seconds: float = 15.0,
        max_tokens: int = 400,
    ) -> LLMGenerationResult:
        with self._lock:
            self.calls.append(
                {
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                    "temperature": temperature,
                    "timeout_seconds": timeout_seconds,
                }
            )
            popped = self._responses.pop(0) if self._responses else None

        if popped is not None:
            if isinstance(popped, LLMGenerationResult):
                return popped
            return LLMGenerationResult(
                raw_text=popped,
                latency_ms=12,
                model_id=self.model_id,
                provider=self.provider_name,
                prompt_tokens=120,
                completion_tokens=45,
            )

        is_km = "MỨC KM" in system_prompt
        if is_km:
            text = (
                "[FAKE-PROVIDER KM] Dựa trên bằng chứng kiểm thử công khai bị sai, "
                "hàm của bạn đang dừng hoặc trả về giá trị chưa khớp với đầu ra kỳ vọng "
                "ở trường hợp biên hoặc ngay trong vòng lặp đầu tiên."
            )
        else:
            text = (
                "[FAKE-PROVIDER KH] Bạn hãy kiểm tra lại thời điểm hàm kết thúc việc "
                "duyệt các phần tử và tự thử chạy tay với ví dụ công khai đầu tiên "
                "xem biến tích lũy thay đổi như thế nào qua từng bước."
            )
        return LLMGenerationResult(
            raw_text=text,
            latency_ms=15,
            model_id=self.model_id,
            provider=self.provider_name,
            prompt_tokens=130,
            completion_tokens=50,
        )


def build_llm_adapter(settings: Settings) -> LLMServiceInterface:
    if settings.llm_mode == "fake":
        return FakeLLMAdapter()
    if settings.llm_mode == "colab_qwen":
        return ColabQwenAdapter(settings)
    if settings.llm_mode == "disabled":
        return DisabledLLMAdapter()
    return APIDemoAdapter(settings)
