import json
import google.generativeai as genai
from src.config import Config
from pathlib import Path

def get_user_name_from_resume() -> str:
    try:
        resume_path = Config.RESUME_FILE
        if resume_path.exists():
            content = resume_path.read_text(encoding="utf-8")
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            if lines:
                first_line = lines[0]
                parts = first_line.split()
                if 1 <= len(parts) <= 4 and not any(char in first_line for char in [":", "@", "/", ".", "http"]):
                    return first_line
    except Exception:
        pass
    return ""

_GEMINI_CONFIGURED = False

class GeminiService:
    def __init__(self):
        global _GEMINI_CONFIGURED
        self.api_key = Config.GEMINI_API_KEY
        self.model_name = Config.GEMINI_MODEL
        self.initialized = False

        if not self.api_key or "YOUR_GEMINI" in self.api_key:
            print("[⚠️ Предупреждение] API-ключ Gemini не настроен в файле .env. ИИ-функции будут отключены.")
            return

        try:
            if not _GEMINI_CONFIGURED:
                # Force REST transport to avoid gRPC credentials mismatch
                genai.configure(api_key=self.api_key, transport="rest")
                _GEMINI_CONFIGURED = True
            self.initialized = True
        except Exception as e:
            print(f"[❌ Ошибка] Не удалось инициализировать Gemini API: {e}")

    def evaluate_vacancy(self, resume: str, vacancy_text: str) -> dict:
        """
        Оценивает вакансию на соответствие резюме от 1 до 10.
        Возвращает словарь: {"score": int, "reason": str}
        """
        if not self.initialized:
            # Если ИИ не настроен, возвращаем дефолтные значения (пропускаем или одобряем всё)
            return {"score": 10, "reason": "ИИ не инициализирован, авто-одобрение"}

        prompt = f"""
        Ты — опытный ИТ-рекрутер. Твоя задача — сопоставить резюме соискателя с вакансией и оценить, насколько кандидат подходит на эту роль по шкале от 1 до 10.

        ОБРАТИ ВНИМАНИЕ НА ГРЕЙД КАНДИДАТА:
        - Целевой уровень (грейд) кандидата: {Config.TARGET_GRADE}.
        - Категорически НЕ подходят вакансии для следующих грейдов: {', '.join(Config.EXCLUDE_GRADES)}.
        Если в тексте вакансии явно указано, что ищется уровень из неподходящих (например, Lead или Junior), сразу ставь оценку 1.

        Данные резюме кандидата:
        \"\"\"
        {resume}
        \"\"\"

        Данные вакансии:
        \"\"\"
        {vacancy_text}
        \"\"\"

        Ответь строго в формате JSON со следующими полями:
        - "score": целое число от 1 до 10 (где 10 — идеальное совпадение стека, грейда и опыта, а 1 — неподходящая вакансия или неподходящий грейд).
        - "reason": краткое пояснение (1-2 предложения), почему выставлена такая оценка.
        """

        try:
            model = genai.GenerativeModel(self.model_name)
            
            # Для моделей Gemma отключаем принудительный JSON-режим в API, так как они его не поддерживают
            is_gemma = "gemma" in self.model_name.lower()
            gen_config = {}
            if not is_gemma:
                gen_config["response_mime_type"] = "application/json"

            response = model.generate_content(
                prompt,
                generation_config=gen_config
            )
            
            raw_text = response.text.strip()
            
            # Очищаем текст от разметки markdown (```json ... ```), которую любят возвращать открытые модели
            clean_text = raw_text
            if "```json" in clean_text:
                clean_text = clean_text.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_text:
                clean_text = clean_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(clean_text)
            return {
                "score": int(data.get("score", 5)),
                "reason": data.get("reason", "Успешно проанализировано")
            }
        except Exception as e:
            print(f"[⚠️ Ошибка при оценке вакансии через Gemini/Gemma]: {e}")
            # Фолбек на случай, если JSON не распарсился стандартным способом
            if 'response' in locals() and response and response.text:
                import re
                # Пробуем найти число в поле "score": X
                score_match = re.search(r'"score"\s*:\s*(\d+)', response.text)
                reason_match = re.search(r'"reason"\s*:\s*"([^"]+)"', response.text)
                if score_match:
                    score_val = int(score_match.group(1))
                    reason_val = reason_match.group(1) if reason_match else "Успешно извлечено регулярным выражением"
                    return {"score": score_val, "reason": reason_val}
            return {"score": 5, "reason": "Произошла ошибка при анализе ИИ (не удалось распарсить ответ)"}

    def generate_cover_letter(self, resume: str, vacancy_text: str) -> str:
        """
        Генерирует сопроводительное письмо на основе вакансии и резюме.
        """
        if not self.initialized:
            return "Здравствуйте! Меня заинтересовала ваша вакансия. Буду рад обсудить подробности на собеседовании."

        # Персональные контакты и пожелания
        user_contacts = Config.USER_CONTACTS
        special_wishes_rule = f"- Соблюдай дополнительные пожелания к тону/стилю и акцентам письма:\n          {Config.USER_SPECIAL_WISHES}" if Config.USER_SPECIAL_WISHES else ""
        contacts_rule = f"- В самом конце письма ОБЯЗАТЕЛЬНО добавь следующую подпись (слово в слово):\n{user_contacts}" if user_contacts else "- Заверши письмо вежливой деловой подписью."

        prompt = f"""
        Напиши емкое, профессиональное и цепляющее сопроводительное письмо от лица соискателя на русском языке для этой вакансии.
        Используй информацию из резюме для подтверждения навыков, требуемых в вакансии. 

        Правила написания письма:
        - Будь лаконичен (не более 3-4 небольших абзацев).
        - Письмо должно быть структурированным, дружелюбным и деловым.
        - Избегай общих фраз вроде "Я ответственный и легко обучаемый". Вместо этого кратко подсвети стек, релевантный вакансии.
        - СТРОГО ЗАПРЕЩЕНО использовать плейсхолдеры или скобки для подстановки текста (например, [ссылка на ваш репозиторий], [вставьте имя], [название компании]). Письмо должно быть полностью готовым к отправке.
        - СТРОГО ЗАПРЕЩЕНО упоминать GitHub, GitLab, портфолио или примеры кода, даже если этого требует вакансия. Кандидат их не ведет. Ничего не придумывай на этот счет.
        - Не выдумывай опыт работы, которого нет в резюме.
        - Заверши вежливым призывом к действию (например, приглашением к диалогу или интервью).
        {special_wishes_rule}
        {contacts_rule}

        Резюме кандидата:
        \"\"\"
        {resume}
        \"\"\"

        Текст вакансии:
        \"\"\"
        {vacancy_text}
        \"\"\"
        САМОЕ ВАЖНОЕ ПРАВИЛО:
        Ответь СТРОГО в формате JSON. Твой ответ должен содержать два поля:
        1. "reasoning" — здесь ты можешь писать любые свои мысли, планы, анализ на английском или русском.
        2. "letter" — здесь должен быть ТОЛЬКО финальный, чистовой текст сопроводительного письма на русском языке, готовый к отправке.
        
        Пример формата ответа:
        {{
            "reasoning": "Здесь я думаю о том, как лучше написать...",
            "letter": "Здравствуйте! Меня заинтересовала..."
        }}
        """

        try:
            model = genai.GenerativeModel(self.model_name)
            
            # Для моделей Gemma отключаем принудительный JSON-режим в API
            is_gemma = "gemma" in self.model_name.lower()
            gen_config = {}
            if not is_gemma:
                gen_config["response_mime_type"] = "application/json"

            response = model.generate_content(
                prompt,
                generation_config=gen_config
            )
            raw_text = response.text.strip()
            
            # Очищаем текст от разметки markdown (```json ... ```)
            clean_text = raw_text
            if "```json" in clean_text:
                clean_text = clean_text.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_text:
                clean_text = clean_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(clean_text)
            letter = data.get("letter", "")
            
            if not letter:
                raise ValueError("Поле 'letter' пустое в JSON-ответе.")
            
            # Убеждаемся, что в конце письма всегда будет красивая профессиональная подпись
            user_name = get_user_name_from_resume()
            
            if user_contacts:
                # Проверяем, добавил ли ИИ уже контакты в конец письма
                contacts_lines = [l.strip() for l in user_contacts.split('\n') if l.strip()]
                last_contact_line = contacts_lines[-1] if contacts_lines else ""
                
                last_chars = letter[-150:] if len(letter) > 150 else letter
                if not last_contact_line or last_contact_line not in last_chars:
                    if "С уважением" in user_contacts:
                        signature = f"\n\n{user_contacts}"
                    else:
                        if user_name and user_name not in user_contacts:
                            signature = f"\n\nС уважением,\n{user_name}\n{user_contacts}"
                        else:
                            signature = f"\n\nС уважением,\n{user_contacts}"
                    letter = f"{letter}{signature}"
            else:
                # Если контакты пустые, подписываемся именем из резюме
                last_chars = letter[-150:] if len(letter) > 150 else letter
                first_word_of_name = user_name.split()[0] if user_name else ""
                if not user_name or (first_word_of_name not in last_chars):
                    if user_name:
                        signature = f"\n\nС уважением,\n{user_name}"
                    else:
                        signature = "\n\nС уважением"
                    letter = f"{letter}{signature}"
            
            return letter
        except Exception as e:
            print(f"[⚠️ Ошибка при генерации письма через Gemini]: {e}")
            user_name = get_user_name_from_resume()
            if user_contacts:
                if "С уважением" in user_contacts:
                    default_sig = f"\n\n{user_contacts}"
                else:
                    if user_name and user_name not in user_contacts:
                        default_sig = f"\n\nС уважением,\n{user_name}\n{user_contacts}"
                    else:
                        default_sig = f"\n\nС уважением,\n{user_contacts}"
            else:
                if user_name:
                    default_sig = f"\n\nС уважением,\n{user_name}"
                else:
                    default_sig = "\n\nС уважением"

            default_letter = (
                "Здравствуйте!\n\n"
                "Ознакомился с вашей вакансией, мой стек отлично подходит под ваши требования. "
                "Буду рад обсудить сотрудничество!"
                f"{default_sig}"
            )
            return default_letter
