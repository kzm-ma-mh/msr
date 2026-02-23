"""
ارتباط با LLM (Ollama / OpenAI Compatible)
"""

import json
import requests
from config import Config


class LLMClient:
    def __init__(self):
        self.provider = Config.LLM_PROVIDER
        self.base_url = Config.OLLAMA_BASE_URL
        self.model = Config.OLLAMA_MODEL
        self.session = requests.Session()

        print(f"🤖 LLM Client: {self.provider}")
        print(f"   Model: {self.model}")
        print(f"   URL: {self.base_url}")

    def check_connection(self):
        """چک کردن اتصال به LLM"""
        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                print(f"   ✅ Connected. Available models: {model_names}")

                # چک وجود مدل
                has_model = any(self.model in name for name in model_names)
                if not has_model:
                    print(f"   ⚠️ Model '{self.model}' not found!")
                    print(f"   💡 Run: ollama create {self.model} -f Modelfile")
                return True
            return False
        except requests.ConnectionError:
            print(f"   ❌ Cannot connect to Ollama at {self.base_url}")
            print(f"   💡 Run: ollama serve")
            return False

    def generate(self, prompt, system_prompt=None, temperature=0.7, max_tokens=2048):
        """
        تولید پاسخ از LLM

        Args:
            prompt: متن سوال + context
            system_prompt: دستورالعمل سیستم
            temperature: خلاقیت (0-1)
            max_tokens: حداکثر توکن خروجی

        Returns:
            str: پاسخ مدل
        """
        if system_prompt is None:
            system_prompt = Config.SYSTEM_PROMPT.format(
                repo_name=f"{Config.GITEA_ORG}/{Config.REPO_NAME}"
            )

        url = f"{self.base_url}/api/chat"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": False,
        }

        try:
            resp = self.session.post(url, json=payload, timeout=120)

            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "")
            else:
                print(f"   ❌ LLM Error {resp.status_code}: {resp.text[:200]}")
                return f"Error: LLM returned status {resp.status_code}"

        except requests.Timeout:
            return "Error: LLM request timed out"
        except requests.ConnectionError:
            return "Error: Cannot connect to LLM server"
        except Exception as e:
            return f"Error: {str(e)}"

    def generate_stream(self, prompt, system_prompt=None, temperature=0.7, max_tokens=2048):
        """
        تولید پاسخ بصورت streaming

        Yields:
            str: هر قطعه از پاسخ
        """
        if system_prompt is None:
            system_prompt = Config.SYSTEM_PROMPT.format(
                repo_name=f"{Config.GITEA_ORG}/{Config.REPO_NAME}"
            )

        url = f"{self.base_url}/api/chat"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": True,
        }

        try:
            resp = self.session.post(url, json=payload, stream=True, timeout=120)

            if resp.status_code == 200:
                for line in resp.iter_lines():
                    if line:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("done", False):
                            break
            else:
                yield f"Error: LLM returned status {resp.status_code}"

        except Exception as e:
            yield f"Error: {str(e)}"