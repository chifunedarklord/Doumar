"""Owner-funded model calls run only on the server, behind account quotas."""
import os


def generate(payload):
    from google import genai
    from google.genai import types
    import base64
    key = os.getenv('GEMINI_API_KEY', '')
    if not key:
        raise ValueError('Máy chủ chưa kết nối dịch vụ AI.')
    parts = [types.Part.from_text(text=payload['message'])]
    if payload.get('image'):
        parts.insert(0, types.Part.from_bytes(data=base64.b64decode(payload['image'], validate=True),
                                             mime_type=payload['mime']))
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=45000))
    model = os.getenv('TASKFLOW_AI_MODEL', 'gemini-3.1-flash-lite')
    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role='user', parts=parts)],
        config=types.GenerateContentConfig(system_instruction=payload.get('instruction', '')[:24000],
                                            max_output_tokens=4096,
                                            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW) if model.startswith('gemini-3') else None))
    if not response.text:
        raise ValueError('AI chưa trả lời. Hãy thử lại.')
    return response.text
