import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import PrivateChatRoom, ChatMessage, Student, CV, Job, SkillinCV, ExperienceinCV, Project
from django.contrib.auth.models import User
from channels.db import database_sync_to_async
from . import nlp


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f"chat_{self.room_id}"
        # Khởi tạo dictionary lưu trữ trạng thái hội thoại cho mỗi người dùng
        self.conversation_states = {}

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        sender_id = data['sender_id']

        sender = await self.get_user(sender_id)
        room = await self.get_room(self.room_id)

        chat_message = await self.save_message(room, sender, message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender': sender.username,
                'sender_id': sender.id,
                'created_at': str(chat_message.created_at),
                'is_superuser': sender.is_superuser,
            }
        )

        bot_username = "ChatBot_Assistant"
        if await self.is_chat_with_bot(room):
            bot_response = await self.generate_bot_response(message, sender.is_superuser, sender)
            bot_user = await self.get_user_by_username(bot_username)

            bot_message = await self.save_message(room, bot_user, bot_response)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': bot_response,
                    'sender': bot_user.username,
                    'sender_id': bot_user.id,
                    'created_at': str(bot_message.created_at),
                    'is_superuser': False,
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_user(self, user_id):
        return User.objects.get(id=user_id)

    @database_sync_to_async
    def get_user_by_username(self, username):
        return User.objects.get_or_create(username=username, defaults={"is_active": True})[0]

    @database_sync_to_async
    def get_room(self, room_id):
        return PrivateChatRoom.objects.get(id=room_id)

    @database_sync_to_async
    def save_message(self, room, sender, message):
        return ChatMessage.objects.create(room=room, sender=sender, message=message)

    @database_sync_to_async
    def is_chat_with_bot(self, room):
        bot_user = User.objects.filter(username="ChatBot_Assistant").first()
        return room.user1 == bot_user or room.user2 == bot_user

    @database_sync_to_async
    def lookup_student_info(self, student_code):
        student = Student.objects.filter(student_code=student_code).first()
        if not student:
            return f"❌ Không tìm thấy sinh viên với mã: {student_code}"
        return (
            f"🎓 **Thông tin sinh viên:**\n\n"
            f"Họ tên: **{student.name}**\n"
            f"Mã sinh viên: **{student.student_code}**\n"
            f"Email: {student.email}\n"
            f"Số điện thoại: {student.phone}\n"
            f"Năm học: {student.study_year}\n"
            f"Ngành: {student.department.name if student.department else 'Chưa có'}"
        )
    
    @database_sync_to_async
    def get_cv_list(self, user):
        """Liệt kê tất cả CV của người dùng."""
        student = Student.objects.filter(user=user).first()
        if not student:
            return (
                "❌ Bạn chưa có CV nào.\n\n"
                "💡 Bạn có thể tạo CV mới bằng cách:\n"
                "• Nhấn vào 'Tạo CV mới' trong mục Quản lý CV\n"
                "• Hoặc truy cập trực tiếp tại: http://127.0.0.1:8000/cv-form/"
            )

        cvs = CV.objects.filter(student=student)
        if not cvs:
            return (
                "❌ Bạn chưa có CV nào.\n\n"
                "💡 Bạn có thể tạo CV mới bằng cách:\n"
                "• Nhấn vào 'Tạo CV mới' trong mục Quản lý CV\n"
                "• Hoặc truy cập trực tiếp tại: http://127.0.0.1:8000/cv-form/"
            )

        response = "📄 **DANH SÁCH CV CỦA BẠN**\n\n"
        for cv in cvs:
            response += f"🔹 **{cv.name}** (ID: {cv.id})\n"
            response += f"   🔗 <a href='http://127.0.0.1:8000/cv/{cv.id}/'>Xem chi tiết</a>\n"
            response += f"   📅 Ngày tạo: {cv.create_date or 'Không có'}\n\n"

        response += (
            "💡 **Bạn muốn làm gì tiếp theo?**\n"
            "• Xem chi tiết: gõ 'Xem CV [id]'\n"
            "• Tìm việc phù hợp: gõ 'Tìm việc cho CV [id]'\n"
            "• Xóa CV: gõ 'Xóa CV [id]'\n"
            "• Tạo CV mới: truy cập http://127.0.0.1:8000/cv-form/"
        )

        return response.strip()

    @database_sync_to_async
    def delete_cv(self, user, cv_id):
        """Xóa CV theo ID."""
        student = Student.objects.filter(user=user).first()
        if not student:
            return "❌ Bạn không có quyền xóa CV này."

        try:
            cv_id = int(cv_id)
            cv = CV.objects.filter(id=cv_id, student=student).first()
            if not cv:
                return f"❌ Không tìm thấy CV với ID: {cv_id}"

            cv_name = cv.name
            cv.delete()
            
            return (
                f"✅ CV '{cv_name}' đã được xóa thành công.\n\n"
                f"💡 Bạn có thể:\n"
                f"• Xem danh sách CV còn lại (gõ 'CV của tôi')\n"
                f"• Tạo CV mới tại http://127.0.0.1:8000/cv-form/"
            )
        except ValueError:
            return "❌ ID CV không hợp lệ. Vui lòng nhập một số."

    @database_sync_to_async
    def get_cv_jobs(self, user, cv_id):
        """Trả về danh sách công việc phù hợp với CV bằng NLP."""
        try:
            cv_id = int(cv_id)
            cv = CV.objects.filter(id=cv_id, student__user=user).first()
            if not cv:
                return f"❌ Không tìm thấy CV với ID: {cv_id}"

            # Lấy dữ liệu từ CV
            cv_data = {
                "skills": [skill.skill.skill for skill in SkillinCV.objects.filter(cv=cv)],
                "experiences": [exp.experience.role for exp in ExperienceinCV.objects.filter(cv=cv)],
                "projects": [proj.project_name for proj in Project.objects.filter(cv=cv)],
            }

            # Lấy danh sách công việc từ database
            jobs = Job.objects.select_related("company", "industry", "hr").all()
            job_data = [
                {
                    "job_name": job.job_name,
                    "company": job.company.company_name if job.company else "N/A",
                    "industry": job.industry.industry_name if job.industry else "N/A",
                    "hr": job.hr.name if job.hr else "N/A",
                    "salary": job.salary,
                    "jd": job.jd,
                    "link_job": job.link_job
                }
                for job in jobs
            ]

            # Gọi NLP để xử lý gợi ý công việc
            recommended_jobs = nlp.process_cv_to_jobs(cv_data, job_data).head(5)  # Lấy top 5 công việc phù hợp

            if recommended_jobs.empty:
                return (
                    f"❌ Không có công việc nào phù hợp với CV '{cv.name}'.\n\n"
                    f"💡 Bạn có thể:\n"
                    f"• Cập nhật CV với nhiều kỹ năng hơn\n"
                    f"• Xem danh sách tất cả việc làm tại: http://127.0.0.1:8000/jobs/"
                )

            # Tạo danh sách công việc trả về chatbot
            response = f"💼 **Công việc phù hợp với CV '{cv.name}':**\n\n"
            for _, job in recommended_jobs.iterrows():
                response += f"🔹 **{job['job_name']}** tại **{job['company']}**\n"
                response += f"   💰 Lương: {job['salary'] if job['salary'] else 'Thỏa thuận'}\n"
                response += f"   🔗 <a href='{job['link_job']}'>Xem chi tiết và ứng tuyển</a>\n\n"

            response += (
                "💡 **Bạn muốn làm gì tiếp theo?**\n"
                "• Xem danh sách việc làm khác (truy cập http://127.0.0.1:8000/jobs/)\n"
                "• Tìm việc cho CV khác (gõ 'CV của tôi' và chọn CV khác)\n"
                "• Cập nhật CV hiện tại (truy cập link CV ở trên)"
            )
            
            return response.strip()
        except ValueError:
            return "❌ ID CV không hợp lệ. Vui lòng nhập một số."

    @database_sync_to_async
    def get_cv_view_link(self, user, cv_id):
        """Trả về đường dẫn đến trang chi tiết của CV."""
        try:
            cv_id = int(cv_id)
            cv = CV.objects.filter(id=cv_id, student__user=user).first()
            if not cv:
                return f"❌ Không tìm thấy CV với ID: {cv_id}"

            return (
                f"🔗 **CV: {cv.name}**\n\n"
                f"Xem chi tiết tại: <a href='http://127.0.0.1:8000/cv/{cv.id}/'>http://127.0.0.1:8000/cv/{cv.id}/</a>\n\n"
                f"💡 **Bạn muốn làm gì tiếp theo?**\n"
                f"• Tìm việc phù hợp cho CV này (gõ 'Tìm việc cho CV {cv.id}')\n"
                f"• Cập nhật CV (truy cập link CV bên trên)\n"
                f"• Xem các CV khác (gõ 'CV của tôi')"
            )
        except ValueError:
            return "❌ ID CV không hợp lệ. Vui lòng nhập một số."

    async def generate_bot_response(self, message, is_admin, user):
        """Tạo phản hồi cho tin nhắn người dùng với hỗ trợ trạng thái hội thoại."""
        user_id = user.id
        
        # Khởi tạo trạng thái hội thoại nếu chưa có
        if not hasattr(self, 'conversation_states'):
            self.conversation_states = {}
            
        if user_id not in self.conversation_states:
            self.conversation_states[user_id] = {'state': 'idle', 'context': {}}
            
        state = self.conversation_states[user_id]['state']
        context = self.conversation_states[user_id]['context']
        
        # Xử lý các lệnh để hủy trạng thái hiện tại
        if message.lower() in ['hủy', 'cancel', 'quay lại', 'thoát']:
            self.conversation_states[user_id] = {'state': 'idle', 'context': {}}
            return "✅ Đã hủy thao tác hiện tại. Bạn cần hỗ trợ gì thêm không? Gõ 'menu' để xem các lựa chọn."
            
        # Xử lý trạng thái hội thoại
        if state == 'awaiting_cv_id':
            action = context.get('action')
            try:
                cv_id = message.strip()
                
                if action == 'view':
                    self.conversation_states[user_id] = {'state': 'idle', 'context': {}}
                    return await self.get_cv_view_link(user, cv_id)
                elif action == 'delete':
                    self.conversation_states[user_id] = {'state': 'idle', 'context': {}}
                    return await self.delete_cv(user, cv_id)
                elif action == 'jobs':
                    self.conversation_states[user_id] = {'state': 'idle', 'context': {}}
                    return await self.get_cv_jobs(user, cv_id)
                    
            except Exception as e:
                return (
                    f"⚠️ Vui lòng nhập ID CV hợp lệ (một số).\n"
                    f"Hoặc gõ 'hủy' để quay lại menu chính."
                )
                
        # Xử lý lệnh admin
        if message.startswith("/admin") or message.lower().startswith("admin"):
            if not is_admin:
                return "⛔ Bạn không có quyền sử dụng lệnh này!"

            command_parts = message.split()
            if len(command_parts) == 1:
                return (
                    "⚠️ Vui lòng nhập lệnh sau /admin. Ví dụ:\n"
                    "• '/admin status' - Kiểm tra trạng thái bot\n"
                    "• '/admin lookup [mã sinh viên]' - Tra cứu thông tin sinh viên"
                )

            command = command_parts[1].lower()
            if command == "status":
                return "✅ Bot đang hoạt động bình thường."

            elif command == "lookup":
                if len(command_parts) != 3:
                    return "⚠️ Lệnh không đúng. Sử dụng: `/admin lookup [mã sinh viên]`."
                student_code = command_parts[2]
                return await self.lookup_student_info(student_code)

            else:
                return (
                    f"⚠️ Không nhận diện được lệnh: '{command}'\n"
                    f"Các lệnh admin có sẵn:\n"
                    f"• 'admin status' - Kiểm tra trạng thái\n"
                    f"• 'admin lookup [mã sinh viên]' - Tra cứu sinh viên"
                )
            
        # Xử lý các biến thể câu lệnh xem danh sách CV
        cv_list_patterns = ['/cv', 'cv của tôi', 'xem cv', 'danh sách cv', 'cv', 'hồ sơ', 'hồ sơ của tôi']
        if message.lower() in cv_list_patterns or any(message.lower().startswith(p) for p in cv_list_patterns):
            if message.lower().strip() == "/cv" or message.lower() in cv_list_patterns:
                return await self.get_cv_list(user)
                
        # Xử lý lệnh xem chi tiết CV
        view_cv_patterns = ['xem cv', 'xem hồ sơ', 'chi tiết cv', 'view cv', 'mở cv']
        if any(message.lower().startswith(pattern) for pattern in view_cv_patterns):
            parts = message.lower().split()
            if len(parts) >= 2 and parts[-1].isdigit():
                return await self.get_cv_view_link(user, parts[-1])
            else:
                self.conversation_states[user_id] = {'state': 'awaiting_cv_id', 'context': {'action': 'view'}}
                return (
                    "🔍 Vui lòng nhập ID của CV bạn muốn xem:\n"
                    "(ID là số hiển thị bên cạnh tên CV. Gõ 'hủy' để quay lại.)"
                )
                
        # Xử lý lệnh xóa CV
        delete_cv_patterns = ['xóa cv', 'delete cv', 'hủy cv', 'loại bỏ cv', 'xoa cv']
        if any(message.lower().startswith(pattern) for pattern in delete_cv_patterns):
            parts = message.lower().split()
            if len(parts) >= 2 and parts[-1].isdigit():
                return await self.delete_cv(user, parts[-1])
            else:
                self.conversation_states[user_id] = {'state': 'awaiting_cv_id', 'context': {'action': 'delete'}}
                return (
                    "⚠️ Vui lòng nhập ID của CV bạn muốn xóa:\n"
                    "(ID là số hiển thị bên cạnh tên CV. Gõ 'hủy' để quay lại.)"
                )
                
        # Xử lý lệnh tìm việc phù hợp với CV
        job_for_cv_patterns = ['tìm việc', 'việc làm phù hợp', 'gợi ý việc', 'cv jobs', 
                               'tìm việc cho cv', 'việc phù hợp', 'công việc phù hợp']
        if any(message.lower().startswith(pattern) for pattern in job_for_cv_patterns):
            parts = message.lower().split()
            # Tìm số cuối cùng trong tin nhắn (có thể là ID CV)
            cv_id = None
            for part in reversed(parts):
                if part.isdigit():
                    cv_id = part
                    break
                    
            if cv_id:
                return await self.get_cv_jobs(user, cv_id)
            else:
                self.conversation_states[user_id] = {'state': 'awaiting_cv_id', 'context': {'action': 'jobs'}}
                return (
                    "💼 Vui lòng nhập ID của CV bạn muốn tìm việc phù hợp:\n"
                    "(ID là số hiển thị bên cạnh tên CV. Gõ 'hủy' để quay lại.)"
                )
                
        # Xử lý lệnh help/menu
        if message.lower() in ['help', 'trợ giúp', 'hướng dẫn', 'menu']:
            return (
                "🤖 **HƯỚNG DẪN SỬ DỤNG INFOBOT**\n\n"
                "**📄 Quản lý CV**\n"
                "• Xem danh sách CV: gõ 'CV của tôi'\n"
                "• Xem chi tiết CV: gõ 'Xem CV [ID]'\n"
                "• Xóa CV: gõ 'Xóa CV [ID]'\n"
                "• Tìm việc phù hợp: gõ 'Tìm việc cho CV [ID]'\n\n"
                
                "**💬 Các lệnh khác**\n"
                "• Trợ giúp/Menu: gõ 'help' hoặc 'menu'\n"
                "• Hủy thao tác hiện tại: gõ 'hủy' hoặc 'cancel'\n"
                "• Chuyển sang CareerGemini: gõ 'dùng CareerGemini'\n\n"
                
                "**🛠️ Dành cho Admin**\n"
                "• Kiểm tra trạng thái: gõ 'admin status'\n"
                "• Tra cứu sinh viên: gõ 'admin lookup [mã sinh viên]'\n\n"
                
                "**📝 Lưu ý:**\n"
                "• InfoBot bảo mật thông tin cá nhân của bạn\n"
                "• Có thể dùng Tiếng Việt không dấu hoặc có dấu\n"
                "• Thông tin quan trọng sẽ không được chia sẻ với hệ thống bên ngoài"
            )
            
        # Xử lý chuyển sang CareerGemini
        if any(message.lower().startswith(p) for p in ['dùng careergemini', 'sử dụng careergemini', 
                                                       'chuyển sang careergemini', 'dung careergemini']):
            return (
                "🔄 Để chuyển sang sử dụng CareerGemini (trợ lý AI nâng cao):\n\n"
                "1. Nhấn vào nút 'CareerGemini' trên thanh công cụ\n"
                "2. Hoặc truy cập: http://127.0.0.1:8000/chatbotgemini/\n\n"
                "⚠️ **Lưu ý:** CareerGemini sử dụng AI của Google Gemini và sẽ tiếp cận các thông tin được chia sẻ. "
                "Không chia sẻ thông tin nhạy cảm với CareerGemini."
            )
            
        # Xử lý câu chào và các tin nhắn thông thường
        greetings = ['xin chào', 'hello', 'hi', 'chào', 'hey', 'alo', 'chao']
        if message.lower() in greetings or any(message.lower().startswith(g) for g in greetings):
            student_name = ""
            student = await database_sync_to_async(lambda: Student.objects.filter(user=user).first())()
            if student:
                student_name = student.name
                
            return (
                f"👋 Chào {student_name or user.username}!\n\n"
                f"Tôi là InfoBot, trợ lý thông tin bảo mật của E-commerce Portal. "
                f"Tôi có thể giúp bạn quản lý CV và thông tin cá nhân một cách an toàn.\n\n"
                f"Bạn cần hỗ trợ gì hôm nay? Gõ 'menu' để xem các tùy chọn."
            )
            
        # Xử lý câu cảm ơn
        thank_patterns = ['cảm ơn', 'thank', 'cám ơn', 'thanks', 'cam on']
        if message.lower() in thank_patterns or any(message.lower().startswith(t) for t in thank_patterns):
            return (
                "🙂 Không có gì! Rất vui khi được hỗ trợ bạn.\n"
                "Nếu cần thêm thông tin, đừng ngần ngại hỏi tôi nhé!"
            )
        
        # Câu trả lời mặc định cho những tin nhắn không nhận dạng được
        return (
            f"🤖 Tôi chưa hiểu yêu cầu của bạn. Bạn có thể:\n\n"
            f"• Gõ 'menu' để xem tất cả các lựa chọn\n"
            f"• Gõ 'CV của tôi' để xem danh sách CV\n"
            f"• Gõ 'help' để được trợ giúp\n"
        )