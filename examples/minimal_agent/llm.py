"""
Provider-Agnostic LLM Interface
examples/minimal_agent/llm.py

Provides a unified interface for model decisions with zero mandatory dependencies.
Defaults to MockLLM for 100% offline, deterministic learning and testing.
Includes optional adapters for OpenAI, Anthropic, Gemini, and Ollama.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
from typing import Any
import urllib.request
import urllib.error


@dataclass
class LLMResponse:
    action_type: str # "tool_call" or "finish"
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    content: str | None = None


class BaseLLM(ABC):
    """Abstract Base Class for LLM decision engines."""

    @abstractmethod
    def generate_decision(
        self,
        messages: list[dict[str, Any]],
        tools_schema: list[dict[str, Any]]
    ) -> LLMResponse:
        """Inspect state messages and tool schemas, then emit an action decision."""
        pass


# ============================================================================
# 1. Default Zero-Dependency Mock LLM
# ============================================================================

class MockLLM(BaseLLM):
    """
    Deterministic offline model simulator.
    Simulates multi-step reasoning for customer order & weather calculations.
    """
    def generate_decision(
        self,
        messages: list[dict[str, Any]],
        tools_schema: list[dict[str, Any]]
    ) -> LLMResponse:
        tool_observations = [m for m in messages if m.get("role") == "tool"]

        # Step 0: Initial prompt -> check weather in customer's city
        if len(tool_observations) == 0:
            return LLMResponse(
                action_type="tool_call",
                tool_name="get_weather",
                tool_args={"city": "Seattle"},
                content="I need to check the current weather in Seattle first."
            )

        # Step 1: Got weather -> check discount
        if len(tool_observations) == 1:
            raw_content = tool_observations[0].get("content", {})
            if isinstance(raw_content, dict):
                weather_data = raw_content.get("result", {})
            else:
                weather_data = {}
            temp = weather_data.get("temp_c", 14) if isinstance(weather_data, dict) else 14

            return LLMResponse(
                action_type="tool_call",
                tool_name="calculate_discount",
                tool_args={"base_amount": 100.0, "vip_status": True},
                content=f"Seattle temperature is {temp}°C. Now computing VIP discount on $100 order."
            )

        # Step 2: Got discount -> final synthesis
        if len(tool_observations) == 2:
            raw_content = tool_observations[1].get("content", {})
            if isinstance(raw_content, dict):
                discount = float(raw_content.get("result", 25.0))
            else:
                discount = 25.0
            final_bill = 100.0 - discount
            return LLMResponse(
                action_type="finish",
                content=(
                    f"In Seattle, it is currently rainy with a temperature of 14°C. "
                    f"With your VIP discount of ${discount:.2f}, your total bill is ${final_bill:.2f}."
                )
            )

        return LLMResponse(action_type="finish", content="Task completed.")


# ============================================================================
# 2. Optional Provider Adapters (Standard Library HTTP / Zero Required SDKs)
# ============================================================================

class OllamaAdapter(BaseLLM):
    """Local Ollama provider (e.g. llama3, mistral, qwen). Zero external dependencies."""
    def __init__(self, model_name: str = "llama3", base_url: str = "http://localhost:11434") -> None:
        self.model_name = model_name
        self.base_url = base_url

    def generate_decision(
        self,
        messages: list[dict[str, Any]],
        tools_schema: list[dict[str, Any]]
    ) -> LLMResponse:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "tools": tools_schema,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                msg = data.get("message", {})
                tool_calls = msg.get("tool_calls", [])
                if tool_calls:
                    tc = tool_calls[0]["function"]
                    return LLMResponse(
                        action_type="tool_call",
                        tool_name=tc["name"],
                        tool_args=tc.get("arguments", {}),
                        content=msg.get("content")
                    )
                return LLMResponse(action_type="finish", content=msg.get("content", ""))
        except Exception as e:
            return LLMResponse(action_type="finish", content=f"Ollama connection error: {e}")


class OpenAIAdapter(BaseLLM):
    """OpenAI API adapter using standard library HTTP."""
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.model_name = model_name

    def generate_decision(
        self,
        messages: list[dict[str, Any]],
        tools_schema: list[dict[str, Any]]
    ) -> LLMResponse:
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "tools": tools_schema if tools_schema else None,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data["choices"][0]["message"]
                if "tool_calls" in choice and choice["tool_calls"]:
                    tc = choice["tool_calls"][0]["function"]
                    return LLMResponse(
                        action_type="tool_call",
                        tool_name=tc["name"],
                        tool_args=json.loads(tc.get("arguments", "{}")),
                        content=choice.get("content")
                    )
                return LLMResponse(action_type="finish", content=choice.get("content", ""))
        except Exception as e:
            return LLMResponse(action_type="finish", content=f"OpenAI error: {e}")


class AnthropicAdapter(BaseLLM):
    """Anthropic Claude API adapter using standard library HTTP."""
    def __init__(self, api_key: str, model_name: str = "claude-3-5-sonnet-20241022") -> None:
        self.api_key = api_key
        self.model_name = model_name

    def generate_decision(
        self,
        messages: list[dict[str, Any]],
        tools_schema: list[dict[str, Any]]
    ) -> LLMResponse:
        url = "https://api.anthropic.com/v1/messages"
        anthropic_tools = []
        for t in tools_schema:
            fn = t.get("function", {})
            anthropic_tools.append({
                "name": fn.get("name"),
                "description": fn.get("description"),
                "input_schema": fn.get("parameters", {})
            })
        
        system_prompt = "You are a helpful AI Agent."
        user_msgs = [m for m in messages if m.get("role") != "system"]

        payload = {
            "model": self.model_name,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": user_msgs,
            "tools": anthropic_tools if anthropic_tools else None,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for block in data.get("content", []):
                    if block.get("type") == "tool_use":
                        return LLMResponse(
                            action_type="tool_call",
                            tool_name=block.get("name"),
                            tool_args=block.get("input", {}),
                            content=None
                        )
                    elif block.get("type") == "text":
                        return LLMResponse(action_type="finish", content=block.get("text"))
                return LLMResponse(action_type="finish", content="No text response received.")
        except Exception as e:
            return LLMResponse(action_type="finish", content=f"Anthropic error: {e}")


class GeminiAdapter(BaseLLM):
    """Google Gemini API adapter using standard library HTTP."""
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash") -> None:
        self.api_key = api_key
        self.model_name = model_name

    def generate_decision(
        self,
        messages: list[dict[str, Any]],
        tools_schema: list[dict[str, Any]]
    ) -> LLMResponse:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        contents = []
        for m in messages:
            contents.append({
                "role": "user" if m.get("role") in ("user", "tool") else "model",
                "parts": [{"text": str(m.get("content", ""))}]
            })
        payload = {"contents": contents}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidate = data["candidates"][0]["content"]["parts"][0]
                return LLMResponse(action_type="finish", content=candidate.get("text", ""))
        except Exception as e:
            return LLMResponse(action_type="finish", content=f"Gemini error: {e}")
