from google import genai
from google.genai import types
from core.services import TaskService, ChatService

def _get_context(user_id: str) -> str:
    tasks = TaskService.get_tasks(user_id)
    context = "THÔNG TIN CÔNG VIỆC CHƯA HOÀN THÀNH:\n"
    for t in tasks:
        if t.status != "done":
            context += f"- Tiêu đề: {t.title} | Phân loại: {t.category} | Ưu tiên: {t.priority} | Phức tạp: {getattr(t, 'complexity', 'medium')} | TG dự kiến: {getattr(t, 'estimated_minutes', 30)}p | Hạn chót: {t.due_date}\n"
    return context

def _get_system_prompt(context: str) -> str:
    return f"""Bạn là Doumar, một trợ lý năng suất xuất sắc.
Bạn có quyền truy cập vào danh sách công việc hiện tại của người dùng như sau:
{context}

NGUYÊN TẮC PHẢN HỒI:
1. Nếu người dùng hỏi chung chung, hãy tư vấn cách sắp xếp thời gian tự nhiên và thân thiện.
2. Lưu ý đặc biệt đến các thuộc tính "Độ phức tạp" (easy/medium/hard) và "Thời gian dự kiến". Gợi ý chia nhỏ các việc "Khó" ra nhiều pomodoro 25 phút.
3. Nếu người dùng úp ảnh (có image_path), hãy đọc nội dung trong ảnh và giúp họ bóc tách thành các Task cụ thể (Tiêu đề, Mô tả).
4. Phản hồi luôn dùng định dạng Markdown (có in đậm, danh sách) để dễ nhìn.
"""

def get_ai_reply(settings: dict, message: str, user_id: str, session_id: str, image_path: str = None) -> str:
    return get_gemini_reply(message, user_id, session_id, image_path)

def get_gemini_reply(message: str, user_id: str, session_id: str, image_path: str = None) -> str:
    try:
        client = genai.Client(api_key="")
        
        context = _get_context(user_id)
        sys_prompt = _get_system_prompt(context)
        
        session = ChatService.get_session(user_id, session_id)
        history = session["messages"] if session else []
        contents = []
        
        for i, msg in enumerate(history):
            role = "user" if msg["role"] == "user" else "model"
            
            if i == len(history) - 1 and role == "user" and image_path:
                parts = []
                with open(image_path, "rb") as f:
                    img_data = f.read()
                ext = image_path.split('.')[-1].lower()
                mime = f"image/{ext}" if ext in ["jpg", "jpeg", "png", "webp"] else "image/jpeg"
                parts.append(types.Part.from_bytes(data=img_data, mime_type=mime))
                parts.append(types.Part.from_text(text="Hãy phân tích hình ảnh này. " + msg["text"]))
                contents.append(types.Content(role=role, parts=parts))
            else:
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["text"])]))
        
        # Đề phòng trường hợp lỗi không có message nào (VD: tạo mới xong gọi AI luôn)
        if not contents:
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=sys_prompt)
        )
        return response.text
            
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            return "⚠️ Lỗi: API Key của bạn đã hết lượt sử dụng (Quota Exceeded) hoặc hệ thống đang quá tải. Vui lòng chờ một lát rồi thử lại, hoặc kiểm tra giới hạn sử dụng trên Google AI Studio."
        return f"⚠️ Lỗi gọi Gemini API: {error_msg}"
