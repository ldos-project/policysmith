import re

from abc import ABC, abstractmethod
from types import SimpleNamespace

from google import genai
from openai import OpenAI

from api_key import GEMINI_API_KEY, OPENAI_API_KEY

class LLMWrapper(ABC):
    def __init__(self, model_name):
        self.model_name = model_name
        assert self.model_name in ALL_LLM_MODELS.keys()

    @abstractmethod
    def _send(self, message):
        pass
    
    @abstractmethod
    def _stats(self):
        # should return:
        #       - prompt_tokens: what was the prompt size (including all previous messages)
        #       - gen_tokens: how many tokens were generated in response
        pass
    
    def send_message(self, message):
        raw_response = self._send(message)
        return self.split_explanation_and_code(raw_response)

    def split_explanation_and_code(self, llm_output):
        """
        Splits LLM output into plaintext and code segments.
        """
        code_pattern = re.compile(r"```([a-zA-Z]*)\n(.*?)```", re.DOTALL)
        code_segments = []
        plaintext_segments = []
        code_languages = []

        last_idx = 0
        for match in code_pattern.finditer(llm_output):
            start, end = match.span()
            text = llm_output[last_idx:start].strip()
            plaintext_segments.append(text if text else "")
            code_languages.append(match.group(1).strip())
            code_segments.append(match.group(2).strip())
            last_idx = end

        trailing_text = llm_output[last_idx:].strip()
        if trailing_text:
            plaintext_segments.append(trailing_text)

        if len(code_segments) > len(plaintext_segments):
            plaintext_segments.insert(0, "")

        return {
            "full_response": llm_output,
            "text_segs": plaintext_segments,
            "code_segs": code_segments,
            "code_langs": code_languages,
            "stats": self._stats()
        }

class GeminiWrapper(LLMWrapper):
    def __init__(self, model_name):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.chat = self.client.chats.create(model=model_name)
        self.responses = []

    def _send(self, message):
        self.responses.append(self.chat.send_message(message))
        return self.responses[-1].text
    
    def _stats(self):
        return {
            "prompt_tokens": self.responses[-1].usage_metadata.prompt_token_count,
            "gen_tokens": self.responses[-1].usage_metadata.candidates_token_count
        }

class OpenAIWrapper(LLMWrapper):
    def __init__(self, model_name):
        self.model_name = model_name
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.responses = []
    
    def _send(self, message):
        self.responses.append(
            self.client.responses.create(
                model=self.model_name,
                previous_response_id=self.responses[-1].id if len(self.responses) > 0 else None,
                input=[{"role": "user", "content": message}]
            )
        )
        return self.responses[-1].output[0].content[0].text
    
    def _stats(self):
        return {
            "model": self.responses[-1].model,
            "prompt_tokens": self.responses[-1].usage.input_tokens,
            "gen_tokens": self.responses[-1].usage.output_tokens
        }
    
ALL_LLM_MODELS = {
    "gemini-2.0": ("gemini-2.0-flash", GeminiWrapper),
    "gemini-2.5": ("gemini-2.5-pro-exp-03-25", GeminiWrapper),
    "gpt-4o-mini": ("gpt-4o-mini", OpenAIWrapper)
}

def get_wrapper(model_name):
    if model_name not in ALL_LLM_MODELS:
        raise ValueError(f"Model {model_name} is not supported.")
    
    model_key, wrapper_class = ALL_LLM_MODELS[model_name]
    return wrapper_class(model_key)