import asyncio
import time
import os
from typing import Dict, List, Optional, Union
from enum import Enum
import openai
import anthropic
import google.generativeai as genai
from .cost_tracker import CostTracker
from .performance_monitor import PerformanceMonitor

class ProviderType(Enum):
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"

class MultiProvider:
    def __init__(self):
        self.cost_tracker = CostTracker()
        self.performance_monitor = PerformanceMonitor()

        # Provider configurations
        self.providers = {
            ProviderType.OPENAI: {
                "client": openai.AsyncOpenAI(),
                "models": {
                    "smart": "gpt-4-turbo",
                    "fast": "gpt-3.5-turbo",
                    "vision": "gpt-4-vision-preview"
                },
                "cost_per_1k": {"input": 0.01, "output": 0.03},
                "strengths": ["complex_reasoning", "function_calling", "structured_output"]
            },
            ProviderType.CLAUDE: {
                "client": anthropic.AsyncAnthropic(),
                "models": {
                    "smart": "claude-3-opus-20240229",
                    "fast": "claude-3-sonnet-20240229",
                    "analysis": "claude-3-sonnet-20240229"
                },
                "cost_per_1k": {"input": 0.015, "output": 0.075},
                "strengths": ["analysis", "creative_writing", "long_context"]
            },
            ProviderType.GEMINI: {
                "client": genai,
                "models": {
                    "smart": "gemini-pro",
                    "fast": "gemini-pro",
                    "multimodal": "gemini-pro-vision"
                },
                "cost_per_1k": {"input": 0.0005, "output": 0.0015},
                "strengths": ["cost_effective", "multimodal", "code_generation"]
            }
        }

        # Fallback chain
        self.fallback_chain = [
            ProviderType.OPENAI,
            ProviderType.GEMINI,
            ProviderType.CLAUDE
        ]

    async def complete(
        self,
        prompt: str,
        provider: str = "auto",
        model_type: str = "smart",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        functions: List[Dict] = None
    ) -> Dict:
        """Main completion method with automatic provider selection"""

        # Auto-select provider based on task characteristics
        if provider == "auto":
            provider = self._select_optimal_provider(prompt, functions)

        provider_enum = ProviderType(provider)

        # Try primary provider
        try:
            result = await self._call_provider(
                provider_enum, prompt, model_type, temperature, max_tokens, functions
            )

            # Track success
            await self.performance_monitor.track_success(provider, result)
            await self.cost_tracker.track_usage(provider, result)

            return result

        except Exception as e:
            # Try fallback providers
            for fallback_provider in self.fallback_chain:
                if fallback_provider == provider_enum:
                    continue

                try:
                    result = await self._call_provider(
                        fallback_provider, prompt, model_type, temperature, max_tokens, functions
                    )

                    # Track fallback usage
                    await self.performance_monitor.track_fallback(provider, fallback_provider.value, result)
                    await self.cost_tracker.track_usage(fallback_provider.value, result)

                    return result

                except Exception as fallback_error:
                    continue

            # All providers failed
            raise Exception(f"All providers failed. Last error: {str(e)}")

    def _select_optimal_provider(self, prompt: str, functions: List[Dict] = None) -> str:
        """Select optimal provider based on task characteristics"""

        # Function calling - prefer OpenAI
        if functions and len(functions) > 0:
            return "openai"

        # Long context analysis - prefer Claude
        if len(prompt) > 10000:
            return "claude"

        # Simple content generation - prefer Gemini (cost-effective)
        if any(keyword in prompt.lower() for keyword in ["generate", "create", "write", "compose"]):
            return "gemini"

        # Complex reasoning - prefer OpenAI
        if any(keyword in prompt.lower() for keyword in ["analyze", "reason", "solve", "calculate"]):
            return "openai"

        # Default to cost-effective option
        return "gemini"

    async def _call_provider(
        self,
        provider: ProviderType,
        prompt: str,
        model_type: str,
        temperature: float,
        max_tokens: int,
        functions: List[Dict] = None
    ) -> Dict:
        """Call specific provider"""

        start_time = time.time()

        if provider == ProviderType.OPENAI:
            result = await self._call_openai(prompt, model_type, temperature, max_tokens, functions)
        elif provider == ProviderType.CLAUDE:
            result = await self._call_claude(prompt, model_type, temperature, max_tokens)
        elif provider == ProviderType.GEMINI:
            result = await self._call_gemini(prompt, model_type, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {provider}")

        end_time = time.time()

        result.update({
            "provider": provider.value,
            "response_time": end_time - start_time,
            "timestamp": time.time()
        })

        return result

    async def _call_openai(
        self,
        prompt: str,
        model_type: str,
        temperature: float,
        max_tokens: int,
        functions: List[Dict] = None
    ) -> Dict:
        """Call OpenAI API"""

        model = self.providers[ProviderType.OPENAI]["models"][model_type]

        messages = [{"role": "user", "content": prompt}]

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        if functions:
            kwargs["functions"] = functions
            kwargs["function_call"] = "auto"

        response = await self.providers[ProviderType.OPENAI]["client"].chat.completions.create(**kwargs)

        return {
            "content": response.choices[0].message.content,
            "function_call": response.choices[0].message.function_call if functions else None,
            "usage": {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }

    async def _call_claude(
        self,
        prompt: str,
        model_type: str,
        temperature: float,
        max_tokens: int
    ) -> Dict:
        """Call Claude API"""

        model = self.providers[ProviderType.CLAUDE]["models"][model_type]

        response = await self.providers[ProviderType.CLAUDE]["client"].messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            "content": response.content[0].text,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        }

    async def _call_gemini(
        self,
        prompt: str,
        model_type: str,
        temperature: float,
        max_tokens: int
    ) -> Dict:
        """Call Gemini API"""

        model_name = self.providers[ProviderType.GEMINI]["models"][model_type]
        model = genai.GenerativeModel(model_name)

        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens
        )

        response = await model.generate_content_async(
            prompt,
            generation_config=generation_config
        )

        # Gemini doesn't provide detailed token usage, estimate it
        estimated_input_tokens = len(prompt) // 4  # Rough estimation
        estimated_output_tokens = len(response.text) // 4

        return {
            "content": response.text,
            "usage": {
                "input_tokens": estimated_input_tokens,
                "output_tokens": estimated_output_tokens,
                "total_tokens": estimated_input_tokens + estimated_output_tokens
            }
        }
