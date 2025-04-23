from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.http import HttpResponse
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import logout
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import pandas as pd
from django.db import transaction
import os
from . import models, nlp
from django.db.models import Q, Max
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import traceback

def index (request): 
    template = 'index.html'
    context = {}
    return render(request,template, context)
def search_results(request):
    """
    View hiển thị trang kết quả tìm kiếm đầy đủ
    """
    query = request.GET.get('q', '')
    results = {}
    
    if query:
        # Tìm kiếm trong Jobs - Sửa tìm kiếm trên ForeignKey
        job_results = models.Job.objects.filter(
            Q(job_name__icontains=query) | 
            Q(company__company_name__icontains=query) |  # Tìm kiếm tên công ty
            Q(jd__icontains=query)
        )[:20]  # Giới hạn 20 kết quả
        
        # Nếu user là admin, tìm kiếm cả trong Students
        if request.user.is_staff:
            student_results = models.Student.objects.filter(
                Q(name__icontains=query) |
                Q(email__icontains=query) |
                Q(student_code__icontains=query)  # Đổi student_id thành student_code theo model
            )[:20]
            results['students'] = student_results
        
        results['jobs'] = job_results
        
    return render(request, 'search_results.html', {
        'query': query,
        'results': results
    })

def api_search(request):
    """
    API endpoint trả về kết quả tìm kiếm dạng JSON cho Ajax
    """
    query = request.GET.get('q', '')
    results = {'jobs': [], 'students': []}
    
    if query and len(query) >= 2:
        # Tìm kiếm trong Jobs - Sửa tìm kiếm trên ForeignKey
        job_results = models.Job.objects.filter(
            Q(job_name__icontains=query) | 
            Q(company__company_name__icontains=query) |  # Tìm kiếm tên công ty
            Q(jd__icontains=query)
        )[:10]  # Giới hạn 10 kết quả cho dropdown
        
        # Chuyển đổi queryset thành dữ liệu JSON
        results['jobs'] = [
            {
                'id': job.id,
                'title': job.job_name,
                'company': job.company.company_name if job.company else ""  # Truy cập company_name trong Company
            } for job in job_results
        ]
        
        # Nếu user là admin, tìm kiếm cả trong Students
        if request.user.is_staff:
            student_results = models.Student.objects.filter(
                Q(name__icontains=query) |
                Q(email__icontains=query) |
                Q(student_code__icontains=query)  # Đổi student_id thành student_code theo model
            )[:10]
            
            results['students'] = [
                {
                    'id': student.id,
                    'name': student.name,
                    'email': student.email if student.email else ""
                } for student in student_results
            ]
    
    return JsonResponse(results)

@login_required(login_url='sign_in')
def student_form(request):
    template = 'student_form.html'

    if request.method == 'POST':
        student_name = request.POST.get('student_name')
        student_code = request.POST.get('student_code')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        study_year = request.POST.get('study_year')

        try:
            # Tạo User với mật khẩu mặc định là '12345'
            user = User.objects.create_user(username=student_code, email=email)
            user.set_password('12345')  # Đặt mật khẩu mặc định
            user.save()

            # Tạo Student và liên kết với User
            student = models.Student.objects.create(
                user=user,
                name=student_name,
                student_code=student_code,
                email=email,
                phone=phone,
                study_year=study_year,
            )

            response_data = {
                'message': 'Đã đăng ký thành công sinh viên mới với mật khẩu mặc định',
                'studentForm': {
                    'name': student.name,
                    'student_code': student.student_code
                }
            }
            return JsonResponse(response_data, status=201)

        except Exception as e:
            return JsonResponse({"message": f"Lỗi: {str(e)}"}, status=400)

    context = {}
    return render(request, template, context)

def sign_in(request):
    if request.method == 'POST':
        student_code = request.POST.get('username')
        password = request.POST.get('password')

        # Sử dụng authenticate của Django
        user = authenticate(request, username=student_code, password=password)
        if user is not None:
            if user.is_staff:  # Nếu là tài khoản admin
                login(request, user)  # Đăng nhập session
                return JsonResponse({"message": "Đăng nhập thành công (Admin)", "status": "success"}, status=200)
            else:  # Nếu là tài khoản thông thường
                try:
                    # Đảm bảo user liên kết với Student
                    student = models.Student.objects.get(user=user)
                    login(request, user)  # Đăng nhập session
                    return JsonResponse({"message": "Đăng nhập thành công", "status": "success"}, status=200)
                except models.Student.DoesNotExist:
                    return JsonResponse({"message": "Tài khoản không được liên kết với sinh viên", "status": "error"}, status=400)
        else:
            return JsonResponse({"message": "Tên đăng nhập hoặc mật khẩu không đúng", "status": "error"}, status=400)

    return render(request, 'sign_in.html')

def logout_view(request):
    logout(request)
    return redirect('index')

@login_required(login_url='sign_in')
def profile(request):
    student = models.Student.objects.filter(user=request.user).first()
    return render(request, 'profile.html', {'student': student})

@login_required(login_url='sign_in')
def update_profile(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            student = models.Student.objects.filter(user=request.user).first()
            student.name = data.get('name', student.name)
            student.email = data.get('email', student.email)
            student.phone = data.get('phone', student.phone)
            student.study_year = data.get('study_year', student.study_year)
            student.save()
            return JsonResponse({"success": True, "message": "Thông tin đã được cập nhật thành công!"})
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Có lỗi xảy ra: {str(e)}"})
    return JsonResponse({"success": False, "message": "Yêu cầu không hợp lệ"})

@login_required(login_url='sign_in')
def change_password(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            current_password = data.get('current_password')
            new_password = data.get('new_password')
            confirm_password = data.get('confirm_password')
            
            if not request.user.check_password(current_password):
                return JsonResponse({"success": False, "message": "Mật khẩu hiện tại không đúng."})
            
            if new_password != confirm_password:
                return JsonResponse({"success": False, "message": "Mật khẩu mới và xác nhận mật khẩu không khớp."})
            
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)  # Giữ người dùng đăng nhập sau khi đổi mật khẩu
            
            return JsonResponse({"success": True, "message": "Đổi mật khẩu thành công."})
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Có lỗi xảy ra: {str(e)}"})
    return JsonResponse({"success": False, "message": "Yêu cầu không hợp lệ"})


@login_required(login_url='sign_in')
def cv_list(request): 
    template = 'cv_list.html'
    # Lấy sinh viên từ user đã đăng nhập
    student = models.Student.objects.filter(user=request.user).first()
    if student:
        CVs = models.CV.objects.filter(student=student)
    else:
        CVs = models.CV.objects.none()
    context = {
        'CVs': CVs
    }
    return render(request, template, context)


def cv_detail(request, pk):
    template = 'cv_detail.html'
    cv = models.CV.objects.filter(pk=pk).last()

    experiences = models.ExperienceinCV.objects.filter(cv=cv).select_related('experience')
    educations = models.EducationinCV.objects.filter(cv=cv).select_related('education')
    skills = models.SkillinCV.objects.filter(cv=cv).select_related('skill')
    projects = models.Project.objects.filter(cv=cv)
    certifications = models.Certification.objects.filter(cv=cv)
    languages = models.LanguageinCV.objects.filter(cv=cv).select_related('language')

    # Use prefetch_related for display names to optimize queries
    social_links = models.SocialLink.objects.filter(cv=cv).prefetch_related('displayname_set') # chúa ngu

    context = {
        'cv': cv,
        'experiences': experiences,
        'educations': educations,
        'skills': skills,
        'projects': projects,
        'certifications': certifications,
        'languages': languages,
        'social_links': social_links,
    }

    return render(request, template, context)

from io import BytesIO
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.templatetags.static import static
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from PIL import Image as PILImage
from reportlab.platypus.flowables import HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.contrib.staticfiles import finders

# Use finders to get the actual file system path
FONT_PATH_REGULAR = finders.find('fonts/Nunito-Regular.ttf')
FONT_PATH_BOLD = finders.find('fonts/Nunito-Bold.ttf')

# Kiểm tra nếu file font tồn tại trước khi đăng ký
if FONT_PATH_REGULAR and FONT_PATH_BOLD:
    pdfmetrics.registerFont(TTFont('Nunito', FONT_PATH_REGULAR))
    pdfmetrics.registerFont(TTFont('Nunito-Bold', FONT_PATH_BOLD))
else:
    raise FileNotFoundError("Font Nunito không tìm thấy. Kiểm tra lại đường dẫn trong static/fonts/")


def generate_cv_pdf(request, cv_id):
    cv = get_object_or_404(models.CV, pk=cv_id)

    experiences = models.ExperienceinCV.objects.filter(cv=cv).select_related('experience')
    certifications = models.Certification.objects.filter(cv=cv)
    skills = models.SkillinCV.objects.filter(cv=cv).select_related('skill')
    languages = models.LanguageinCV.objects.filter(cv=cv).select_related('language')
    projects = models.Project.objects.filter(cv=cv)
    social_links = models.SocialLink.objects.filter(cv=cv).prefetch_related('displayname_set')

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)

    elements = []
    styles = getSampleStyleSheet()

    # Custom Styles
    # title_style = ParagraphStyle("Title", fontSize=24, fontName="Nunito-Bold", textColor=colors.HexColor("#1F3864"), alignment=1, spaceAfter=6)
    # subtitle_style = ParagraphStyle("Subtitle", fontSize=10, fontName="Nunito", textColor=colors.black, alignment=1, spaceAfter=10)
    # section_style = ParagraphStyle("Section", fontSize=16, fontName="Nunito-Bold", textColor=colors.HexColor("#1F3864"), spaceBefore=15, spaceAfter=8)
    # normal_style = ParagraphStyle("Normal", fontSize=11, fontName="Nunito", leading=14)
    # job_title_style = ParagraphStyle("JobTitle", fontSize=12, fontName="Nunito-Bold", textColor=colors.black, spaceBefore=8)
    # company_style = ParagraphStyle("Company", fontSize=12, fontName="Nunito", textColor=colors.HexColor("#0563C1"))
    # date_style = ParagraphStyle("Date", fontSize=11, fontName="Nunito", textColor=colors.gray, alignment=2)
    # bullet_style = ParagraphStyle("Bullet", fontSize=11, fontName="Nunito", leading=14, leftIndent=15, firstLineIndent=-10)

    BRAND_COLOR = colors.HexColor("#1b1d4d")
    ACCENT_COLOR = colors.HexColor("#6c757d")

    title_style = ParagraphStyle(
        "Title", 
        fontSize=28, 
        fontName="Nunito-Bold", 
        textColor=BRAND_COLOR, 
        alignment=1, 
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        "Subtitle", 
        fontSize=11, 
        fontName="Nunito", 
        textColor=colors.black, 
        alignment=1, 
        spaceAfter=10
    )
    
    section_style = ParagraphStyle(
        "Section", 
        fontSize=18, 
        fontName="Nunito-Bold", 
        textColor=BRAND_COLOR, 
        spaceBefore=15, 
        spaceAfter=10,
        borderWidth=0,
        borderColor=colors.black,
        borderPadding=(0, 0, 5, 0),
        endDots=None
    )
    
    normal_style = ParagraphStyle(
        "Normal", 
        fontSize=11, 
        fontName="Nunito", 
        leading=14
    )
    
    job_title_style = ParagraphStyle(
        "JobTitle", 
        fontSize=13, 
        fontName="Nunito-Bold", 
        textColor=BRAND_COLOR, 
        spaceBefore=8
    )
    
    company_style = ParagraphStyle(
        "Company", 
        fontSize=13, 
        fontName="Nunito", 
        textColor=colors.HexColor("#007bff")
    )
    
    date_style = ParagraphStyle(
        "Date", 
        fontSize=11, 
        fontName="Nunito-Bold", 
        textColor=ACCENT_COLOR, 
        alignment=2
    )
    
    bullet_style = ParagraphStyle(
        "Bullet", 
        fontSize=11, 
        fontName="Nunito", 
        leading=16, 
        leftIndent=20, 
        firstLineIndent=-10
    )

    # Profile Section
    if cv.avatar:
        try:
            avatar_path = cv.avatar.path
            with PILImage.open(avatar_path) as img:
                # Create circular crop of the avatar
                width, height = img.size
                new_size = min(width, height)
                left = (width - new_size) / 2
                top = (height - new_size) / 2
                right = (width + new_size) / 2
                bottom = (height + new_size) / 2
                cropped_img = img.crop((left, top, right, bottom))
                
                # Create a circular mask
                mask = PILImage.new('L', (new_size, new_size), 0)
                from PIL import ImageDraw
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, new_size, new_size), fill=255)
                
                # Apply the mask
                result = cropped_img.copy()
                result.putalpha(mask)
                
                # Save to buffer
                img_buffer = BytesIO()
                result.save(img_buffer, format="PNG")
                img_buffer.seek(0)
                
                # Create image for PDF
                profile_img = Image(img_buffer, width=120, height=120)
                
                # Create profile layout
                profile_data = [
                    [profile_img],
                    [Paragraph(cv.student.name, title_style)]
                ]
                
        except Exception as e:
            # Fallback if image processing fails
            profile_data = [[Paragraph(cv.student.name, title_style)]]
    else:
        # No avatar available
        profile_data = [[Paragraph(cv.student.name, title_style)]]
    
    # Create profile table centered
    profile_table = Table(profile_data, colWidths=[515])
    profile_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(profile_table)
    elements.append(Spacer(1, 10))

    # Contact information
    elements.append(Spacer(1, 7))
    contact_info = []
    contact_info.append([
        Paragraph(f'<font color="#6c757d">+84 - {cv.student.phone}</font>', subtitle_style)
    ])
    contact_info.append([
        Paragraph(f'<font color="#6c757d">{cv.student.email}</font>', subtitle_style)
    ])
    
    contact_table = Table(contact_info, colWidths=[515])
    contact_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(contact_table)
    elements.append(Spacer(1, 5))
    
    # Social Links (Hiển thị tối đa 3 links mỗi hàng, căn giữa)
    if social_links.exists():
        social_texts = []
        
        for link in social_links:
            display_name = link.displayname_set.first().display_name if link.displayname_set.exists() else link.link
            # For PDF links that work, we need to use proper annotations
            social_texts.append(f'<link href="{link.link}"><font color="#007bff"><u>{display_name}</u></font></link>')
        
        # Format as a single row with maximum 3 links per row
        row_size = 3
        social_rows = [social_texts[i:i + row_size] for i in range(0, len(social_texts), row_size)]
        
        for row in social_rows:
            # Fill empty cells for consistent layout
            while len(row) < row_size:
                row.append("")
                
            social_data = [[Paragraph(text, subtitle_style) for text in row]]
            social_table = Table(social_data, colWidths=[170] * row_size)
            
            social_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(social_table)

    
    # Add a separator line
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=10, spaceAfter=10))
    
    # About Me Section
    if cv.about_me:
        elements.append(Paragraph("About Me", section_style))
        elements.append(Paragraph(cv.about_me, normal_style))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=10, spaceAfter=0))
    
   # Professional Experience
    if experiences.exists():
        elements.append(Paragraph("Professional Experience", section_style))
        
        for exp in experiences:
            job = exp.experience
            
            # Create job entry styled like the website
            job_entry_data = [
                [
                    Paragraph(f'{job.role},', job_title_style),
                    Paragraph(f'({job.company_name})', company_style),
                    Paragraph(f'{job.start_date.strftime("%d/%m/%Y")} - {job.end_date.strftime("%d/%m/%Y") if job.end_date else "Present"}', date_style)
                ]
            ]
            
            job_table = Table(job_entry_data, colWidths=[200, 165, 150])
            job_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'LEFT'),
                ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            elements.append(job_table)
            
            # Job responsibilities with bullet points
            responsibilities = []
            for line in job.context.split('\n'):
                if line.strip():
                    # Format bullet points like website
                    clean_line = line.strip()
                    if clean_line:
                        elements.append(Paragraph(f'• {clean_line}', bullet_style))
            
            elements.append(Spacer(1, 15))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=10, spaceAfter=0))

    
    # Certifications
    if certifications.exists():
        elements.append(Paragraph("Certifications", section_style))
        for cert in certifications:
            elements.append(Paragraph(f"• {cert.certificate}", bullet_style))
        
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=10, spaceAfter=0))
    
    # Skills (as badges similar to HTML)
    if skills.exists():
        elements.append(Paragraph("Skills", section_style))
        
        skill_rows = []
        current_row = []
        
        # Create skill badges in rows of 4
        for idx, skill in enumerate(skills):
            skill_style = ParagraphStyle(
                f"Skill{idx}",
                parent=normal_style,
                textColor=colors.white,
                backColor=BRAND_COLOR,
                alignment=1,  # centered
                borderPadding=6
            )
            current_row.append(
                Paragraph(
                    f'{skill.skill.skill}',
                    skill_style
                )
            )
            
            if len(current_row) == 4 or idx == len(skills) - 1:
                # Fill empty cells for consistent layout
                while len(current_row) < 4:
                    current_row.append("")
                
                skill_rows.append(current_row)
                current_row = []
        
        if skill_rows:
            for row in skill_rows:
                skill_table = Table([row], colWidths=[120] * 4)
                skill_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ]))
                elements.append(skill_table)
                elements.append(Spacer(1, 5))
        
        elements.append(Spacer(1, 10))
        
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=10, spaceAfter=0))
    
    # Languages
    if languages.exists():
        elements.append(Paragraph("Languages", section_style))
        for lang in languages:
            elements.append(Paragraph(f"<b>{lang.language.language}</b>", normal_style))
            elements.append(Paragraph(f"{lang.language.text}", ParagraphStyle("LangDesc", parent=normal_style, textColor=colors.gray, leftIndent=10)))
        
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=10, spaceAfter=0))
    
    # Projects
    if projects.exists():
        elements.append(Paragraph("Projects", section_style))
        for project in projects:
            elements.append(Paragraph(f"<b>{project.project_name}</b>", job_title_style))
            elements.append(Spacer(1, 10))
            
            for line in project.project_content.split("\n"):
                if line.strip():
                    elements.append(Paragraph(f"• {line.strip()}", bullet_style))
            
            if project.project_link_set.exists():
                elements.append(Paragraph(f"(<a href='{project.project_link_set.first().link}' color='#0563C1'>link</a>)", normal_style))
            
            elements.append(Spacer(1, 10))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{cv.student.name}_CV.pdf"'
    return response




def get_student_info(request, pk):
    try:
        student = models.Student.objects.get(pk=pk)
        data = {
            'name': student.name,
            'student_code': student.student_code,
            'email': student.email,
            'phone': student.phone,
            'study_year': student.study_year
        }
        return JsonResponse(data)
    except models.Student.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)


@login_required(login_url='sign_in')
def cv_form(request, pk=None):
    template = 'cv_form.html'

    # Lấy thông tin sinh viên và các trường đại học
    student = models.Student.objects.filter(user=request.user).first()
    universitys = models.University.objects.all()
    cv = None

    # Kiểm tra nếu đang chỉnh sửa một CV
    if pk:
        cv = models.CV.objects.filter(pk=pk, student=student).first()

    if request.method == 'POST':
        print(request.POST)
        # Lấy dữ liệu từ form
        name = request.POST.get('cv_name')
        about_me = request.POST.get('about_me')
        avatar = request.FILES.get('avatar')  # Lấy file avatar từ form
        # Kiểm tra giá trị avatar
        print("Avatar Path:",avatar)

        # Nếu là chỉnh sửa CV
        if cv:
            cv.name = name
            cv.about_me = about_me
            if avatar:
                cv.avatar = avatar
            cv.save()
        else:  # Nếu là tạo mới CV
            cv = models.CV.objects.create(
                name=name,
                about_me=about_me,
                student=student,
                avatar=avatar
            )

        # Xử lý Social Links
        social_links = []
        social_link_count = int(request.POST.get('social_link_count', 0))
        for i in range(social_link_count):
            link = request.POST.get(f'social_link_{i}')
            display_name = request.POST.get(f'social_link_{i}_display_name')

            if link:
                social_link_obj = models.SocialLink.objects.create(cv=cv, link=link)
                if display_name:
                    models.Displayname.objects.create(social_link=social_link_obj, display_name=display_name)

        # Xử lý Ngôn ngữ
        language_index = 0
        while True:
            language_name = request.POST.get(f'language_{language_index}_name')
            description = request.POST.get(f'language_{language_index}_description')
            if not language_name:
                break
            language = models.Language.objects.create(language=language_name, text=description)
            models.LanguageinCV.objects.create(cv=cv, language=language)
            language_index += 1

        # Xử lý Chứng chỉ
        certifications = [key for key in request.POST if key.startswith('certification_') and not key.endswith('_count')]
        for cert_key in certifications:
            certificate = request.POST.get(cert_key)
            if certificate:
                models.Certification.objects.create(cv=cv, certificate=certificate)

        # Xử lý Dự án
        project_index = 0
        while True:
            project_name = request.POST.get(f'project_{project_index}_name')
            project_content = request.POST.get(f'project_{project_index}_description')
            project_link = request.POST.get(f'project_{project_index}_link')
            if not project_name:
                break
            project = models.Project.objects.create(
                project_name=project_name,
                project_content=project_content,
                cv=cv
            )
            if project_link:
                models.Project_link.objects.create(project=project, link=project_link)
            project_index += 1

        # Xử lý Học vấn
        education_index = 0
        while True:
            university_pk = request.POST.get(f'education_{education_index}_university')
            if not university_pk:
                break
            degree = request.POST.get(f'education_{education_index}_degree')
            start_year = request.POST.get(f'education_{education_index}_start_year')
            end_year = request.POST.get(f'education_{education_index}_end_year')
            if university_pk.isdigit():
                university = models.University.objects.get(pk=university_pk)
            else:
                university, _ = models.University.objects.get_or_create(university_name=university_pk)
            education = models.Education.objects.create(
                university=university,
                degree=degree,
                start_year=start_year,
                end_year=end_year
            )
            models.EducationinCV.objects.create(cv=cv, education=education)
            education_index += 1

        # Xử lý Kinh nghiệm
        experiences = [key for key in request.POST if key.startswith('experience_') and key.endswith('_company_name')]
        for experience_key in experiences:
            index = experience_key.split('_')[1]
            company_name = request.POST.get(f'experience_{index}_company_name')
            role = request.POST.get(f'experience_{index}_role')
            start_date = request.POST.get(f'experience_{index}_start_date')
            end_date = request.POST.get(f'experience_{index}_end_date')
            context = request.POST.get(f'experience_{index}_context')
            if company_name:
                experience = models.Experience.objects.create(
                    company_name=company_name,
                    role=role,
                    start_date=start_date,
                    end_date=end_date,
                    context=context
                )
                models.ExperienceinCV.objects.create(cv=cv, experience=experience)

        # Xử lý Kỹ năng
        skills = [key for key in request.POST if key.startswith('skill_') and not key.endswith('_count')]
        for skill_key in skills:
            skill_name = request.POST.get(skill_key)
            if skill_name:
                skill, _ = models.Skill.objects.get_or_create(skill=skill_name)
                models.SkillinCV.objects.create(cv=cv, skill=skill)

        messages.success(request, "CV đã được lưu thành công.")
        return redirect('cv_list')

    # Truyền dữ liệu vào context để hiển thị trên form
    context = {
        'cv': cv,
        'student': student,
        'universitys': universitys,
        'social_links': models.SocialLink.objects.filter(cv=cv) if cv else [],
        'projects': models.Project.objects.filter(cv=cv) if cv else [],
        'languages': models.LanguageinCV.objects.filter(cv=cv) if cv else [],
        'certifications': models.Certification.objects.filter(cv=cv) if cv else [],
        'experiences': models.ExperienceinCV.objects.filter(cv=cv) if cv else [],
        'skills': models.SkillinCV.objects.filter(cv=cv) if cv else [],
    }
    return render(request, template, context)


from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
import base64

@login_required(login_url='sign_in')
def upload_avatar(request):
    """
    Handle avatar upload with cropping functionality.
    Processes the cropped image data from POST request and saves it to the user's CV.
    """
    if request.method == 'POST':
        try:
            # Get student and CV information
            student = models.Student.objects.filter(user=request.user).first()
            
            # Find the most recent CV for the student or create a new one if none exists
            cv = models.CV.objects.filter(student=student).order_by('-id').first()
            if not cv:
                cv = models.CV.objects.create(
                    name=f"CV - {student.name}",
                    student=student
                )
            
            # Process the avatar image from the form data
            avatar_file = request.FILES.get('avatar')
            
            if avatar_file:
                # Save the image directly if it's a simple file upload
                cv.avatar = avatar_file
                cv.save()
                return JsonResponse({'success': True, 'message': 'Avatar uploaded successfully'})
            
            # Process base64 image data for cropped images
            image_data = request.POST.get('avatar')
            
            if image_data and ',' in image_data:
                # Extract base64 content
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                
                # Convert base64 to binary
                image_data = base64.b64decode(imgstr)
                
                # Process image with PIL
                image = Image.open(BytesIO(image_data))
                
                # Resize if needed (optional)
                # image = image.resize((170, 170), Image.ANTIALIAS)
                
                # Save to memory buffer
                output = BytesIO()
                if ext.lower() == 'png':
                    image.save(output, format='PNG')
                else:
                    image.save(output, format='JPEG', quality=90)
                output.seek(0)
                
                # Create Django file object
                avatar_file = InMemoryUploadedFile(
                    output,
                    'ImageField',
                    f"{student.student_code}_avatar.{ext}",
                    f'image/{ext}',
                    sys.getsizeof(output),
                    None
                )
                
                # Save to CV model
                cv.avatar = avatar_file
                cv.save()
                
                return JsonResponse({'success': True, 'message': 'Avatar cropped and saved successfully'})
            
            return JsonResponse({'success': False, 'message': 'No image data provided'}, status=400)
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)

@login_required(login_url='sign_in')
def update_cv(request, pk):
    template = 'cv_form.html'
    
    # Lấy thông tin CV và student
    student = models.Student.objects.filter(user=request.user).first()
    cv = models.CV.objects.filter(pk=pk, student=student).first()

    if not cv:
        return HttpResponse("CV không tồn tại hoặc bạn không có quyền chỉnh sửa.", status=404)

    if request.method == 'POST':
        # Cập nhật thông tin CV
        cv.name = request.POST.get('cv_name', cv.name)
        cv.about_me = request.POST.get('about_me', cv.about_me)
        cv.save()

        # Cập nhật liên kết cá nhân
        models.SocialLink.objects.filter(cv=cv).delete()
        social_link_count = int(request.POST.get('social_link_count', 0))
        for i in range(social_link_count):
            link = request.POST.get(f'social_link_{i}')
            display_name = request.POST.get(f'social_link_{i}_display_name')
            if link:
                social_link_obj = models.SocialLink.objects.create(cv=cv, link=link)
                if display_name:
                    models.Displayname.objects.create(social_link=social_link_obj, display_name=display_name)

        # Cập nhật ngôn ngữ
        models.LanguageinCV.objects.filter(cv=cv).delete()
        language_index = 0
        while True:
            language_name = request.POST.get(f'language_{language_index}_name')
            description = request.POST.get(f'language_{language_index}_description')
            if not language_name:
                break
            language = models.Language.objects.create(language=language_name, text=description)
            models.LanguageinCV.objects.create(cv=cv, language=language)
            language_index += 1

        # Cập nhật chứng chỉ
        models.Certification.objects.filter(cv=cv).delete()
        certifications = [key for key in request.POST if key.startswith('certification_') and not key.endswith('_count')]
        for cert_key in certifications:
            certificate = request.POST.get(cert_key)
            if certificate:
                models.Certification.objects.create(cv=cv, certificate=certificate)

        # Cập nhật dự án
        models.Project.objects.filter(cv=cv).delete()
        project_index = 0
        while True:
            project_name = request.POST.get(f'project_{project_index}_name')
            project_content = request.POST.get(f'project_{project_index}_description')
            project_link = request.POST.get(f'project_{project_index}_link')
            if not project_name:
                break
            project = models.Project.objects.create(
                project_name=project_name,
                project_content=project_content,
                cv=cv
            )
            if project_link:
                models.Project_link.objects.create(project=project, link=project_link)
            project_index += 1

        # Cập nhật học vấn
        models.EducationinCV.objects.filter(cv=cv).delete()
        education_index = 0
        while True:
            university_pk = request.POST.get(f'education_{education_index}_university')
            if not university_pk:
                break
            degree = request.POST.get(f'education_{education_index}_degree')
            start_year = request.POST.get(f'education_{education_index}_start_year')
            end_year = request.POST.get(f'education_{education_index}_end_year')
            if university_pk.isdigit():
                university = models.University.objects.get(pk=university_pk)
            else:
                university, _ = models.University.objects.get_or_create(university_name=university_pk)
            education = models.Education.objects.create(
                university=university,
                degree=degree,
                start_year=start_year,
                end_year=end_year
            )
            models.EducationinCV.objects.create(cv=cv, education=education)
            education_index += 1

        # Cập nhật kinh nghiệm
        models.ExperienceinCV.objects.filter(cv=cv).delete()
        experiences = [key for key in request.POST if key.startswith('experience_') and key.endswith('_company_name')]
        for experience_key in experiences:
            index = experience_key.split('_')[1]
            company_name = request.POST.get(f'experience_{index}_company_name')
            role = request.POST.get(f'experience_{index}_role')
            start_date = request.POST.get(f'experience_{index}_start_date')
            end_date = request.POST.get(f'experience_{index}_end_date')
            context = request.POST.get(f'experience_{index}_context')
            if company_name:
                experience = models.Experience.objects.create(
                    company_name=company_name,
                    role=role,
                    start_date=start_date,
                    end_date=end_date,
                    context=context
                )
                models.ExperienceinCV.objects.create(cv=cv, experience=experience)

        # Cập nhật kỹ năng
        models.SkillinCV.objects.filter(cv=cv).delete()
        skills = [key for key in request.POST if key.startswith('skill_') and not key.endswith('_count')]
        for skill_key in skills:
            skill_name = request.POST.get(skill_key)
            if skill_name:
                skill, _ = models.Skill.objects.get_or_create(skill=skill_name)
                models.SkillinCV.objects.create(cv=cv, skill=skill)

        messages.success(request, "CV đã được cập nhật thành công.")
        return redirect('cv_detail', pk=pk)

    # Dữ liệu để hiển thị form
    social_links = models.SocialLink.objects.filter(cv=cv).prefetch_related('displayname_set')
    languages = models.LanguageinCV.objects.filter(cv=cv).select_related('language')
    certifications = models.Certification.objects.filter(cv=cv)
    projects = models.Project.objects.filter(cv=cv)
    experiences = models.ExperienceinCV.objects.filter(cv=cv).select_related('experience')
    skills = models.SkillinCV.objects.filter(cv=cv).select_related('skill')
    educations = models.EducationinCV.objects.filter(cv=cv).select_related('education')

    context = {
        'cv': cv,
        'student': student,
        'social_links': social_links,
        'languages': languages,
        'certifications': certifications,
        'projects': projects,
        'experiences': experiences,
        'skills': skills,
        'educations': educations,
    }
    return render(request, template, context)


@login_required(login_url='sign_in')
def delete_cv(request, pk):
    # Lấy sinh viên hiện tại
    student = models.Student.objects.filter(user=request.user).first()

    # Tìm CV và kiểm tra quyền sở hữu
    cv_queryset = models.CV.objects.filter(pk=pk, student=student)
    if not cv_queryset.exists():
        messages.error(request, "CV không tồn tại hoặc bạn không có quyền xóa.")
        return redirect('cv_list')

    if request.method == 'POST':
        # Xóa CV
        cv_queryset.first().delete()
        messages.success(request, "CV đã được xóa thành công.")
        return redirect('cv_list')


import csv

@login_required
def import_csv(request):
    if request.method == 'POST':
        if 'csv_file' in request.FILES:
            csv_file = request.FILES['csv_file']

            # Kiểm tra định dạng file
            if not csv_file.name.endswith('.csv'):
                return JsonResponse({'status': 'error', 'message': "File không đúng định dạng CSV."})

            try:
                # Đọc file CSV
                decoded_file = csv_file.read().decode('utf-8-sig').splitlines()
                reader = csv.DictReader(decoded_file)

                results = []  # Danh sách lưu kết quả của từng dòng

                for row in reader:
                    try:
                        # Lấy thông tin từ từng dòng và chuyển đổi thành chuỗi
                        department_code = str(row['Mã ngành']).strip()
                        department_name = str(row['Tên ngành']).strip()
                        student_class = str(row['Lớp']).strip()
                        student_code = str(row['Mã sinh viên']).strip()
                        last_name = str(row['Họ và tên lót']).strip()
                        first_name = str(row['Tên']).strip()

                        # Tạo hoặc lấy Department
                        department, _ = models.Department.objects.get_or_create(
                            department_code=department_code,
                            defaults={'name': department_name}
                        )

                        # Tạo User
                        email = f"{student_code}@due.udn.vn"
                        user, created = User.objects.get_or_create(
                            username=student_code,
                            defaults={
                                'email': email,
                                'password': '12345',
                                'first_name': first_name,
                                'last_name': last_name,
                            }
                        )
                        if created:
                            user.set_password('12345')
                            user.save()

                        # Tạo Student
                        models.Student.objects.get_or_create(
                            user=user,
                            defaults={
                                'name': f"{last_name} {first_name}",
                                'student_code': student_code,
                                'email': email,
                                'phone': '',
                                'study_year': student_class,
                                'department': department,
                            }
                        )

                        # Ghi kết quả thành công
                        results.append({
                            'status': 'success',
                            'student_code': student_code,
                            'full_name': f"{last_name} {first_name}",
                            'student_class': student_class,
                            'created': created,
                        })

                    except Exception as e:
                        # Ghi kết quả lỗi
                        results.append({
                            'status': 'error',
                            'student_code': student_code,
                            'full_name': f"{last_name} {first_name}",
                            'student_class': student_class,
                            'error': str(e)
                        })

                # Trả về kết quả của tất cả các dòng
                return JsonResponse({
                    'status': 'complete',
                    'results': results
                })

            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f"Có lỗi xảy ra: {str(e)}"})

    return render(request, 'import_student_data.html')

@login_required
def update_from_gsheet(request):
    if request.method == 'POST':
        # Get spreadsheet details from the form
        spreadsheet_id = request.POST.get('spreadsheet_id', '')
        sheet_name = request.POST.get('sheet_name', '')
        api_key = request.POST.get('api_key', '')
        
        if not spreadsheet_id or not sheet_name or not api_key:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng điền đầy đủ thông tin.'})
        
        # Get Google Sheet data using the helper function
        sheet_data = get_google_sheet_data(spreadsheet_id, sheet_name, api_key)
        
        if not sheet_data:
            return JsonResponse({'status': 'error', 'message': 'Không thể kết nối đến Google Sheets API.'})
        
        if 'values' not in sheet_data:
            return JsonResponse({'status': 'error', 'message': 'Không tìm thấy dữ liệu trong Google Sheet.'})
        
        # Process the data
        headers = sheet_data['values'][0]
        rows = sheet_data['values'][1:]
        
        # Create a list of dictionaries with header keys
        data_rows = []
        for row in rows:
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ""
            data_rows.append(row_dict)
        
        results = []  # Danh sách lưu kết quả của từng dòng
        
        for row in data_rows:
            try:
                # Lấy thông tin từ từng dòng và chuyển đổi thành chuỗi
                department_code = str(row.get('Mã ngành', '')).strip()
                department_name = str(row.get('Tên ngành', '')).strip()
                student_class = str(row.get('Lớp', '')).strip()
                student_code = str(row.get('Mã sinh viên', '')).strip()
                last_name = str(row.get('Họ và tên lót', '')).strip()
                first_name = str(row.get('Tên', '')).strip()
                
                if not student_code:
                    continue  # Skip rows without student code
                
                # Tạo hoặc lấy Department
                department, _ = models.Department.objects.get_or_create(
                    department_code=department_code,
                    defaults={'name': department_name}
                )

                # Tạo User
                email = f"{student_code}@due.udn.vn"
                user, created = User.objects.get_or_create(
                    username=student_code,
                    defaults={
                        'email': email,
                        'password': '12345',
                        'first_name': first_name,
                        'last_name': last_name,
                    }
                )
                if created:
                    user.set_password('12345')
                    user.save()

                # Tạo Student
                models.Student.objects.get_or_create(
                    user=user,
                    defaults={
                        'name': f"{last_name} {first_name}",
                        'student_code': student_code,
                        'email': email,
                        'phone': '',
                        'study_year': student_class,
                        'department': department,
                    }
                )

                # Ghi kết quả thành công
                results.append({
                    'status': 'success',
                    'student_code': student_code,
                    'full_name': f"{last_name} {first_name}",
                    'student_class': student_class,
                    'created': created,
                })

            except Exception as e:
                # Ghi kết quả lỗi
                student_code_value = student_code if 'student_code' in locals() else 'Unknown'
                last_name_value = last_name if 'last_name' in locals() else ''
                first_name_value = first_name if 'first_name' in locals() else ''
                student_class_value = student_class if 'student_class' in locals() else 'Unknown'
                
                results.append({
                    'status': 'error',
                    'student_code': student_code_value,
                    'full_name': f"{last_name_value} {first_name_value}".strip(),
                    'student_class': student_class_value,
                    'error': str(e)
                })
        
        # Trả về kết quả của tất cả các dòng
        return JsonResponse({
            'status': 'complete',
            'results': results
        })
    
    return render(request, 'update_from_gsheet.html')

def get_google_sheet_data(spreadsheet_id, sheet_name, api_key):
    """Helper function to fetch data from Google Sheets API"""
    import requests
    
    # Construct the URL for the Google Sheets API
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{sheet_name}!A1:Z?alt=json&key={api_key}'

    try:
        # Make a GET request to retrieve data from the Google Sheets API
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the JSON response
        data = response.json()
        return data

    except Exception as e:
        # Handle any errors that occur during the request
        print(f"An error occurred: {e}")
        return None


@login_required
def student_management(request):
    students = models.Student.objects.all()
    departments = models.Department.objects.all()

    # Apply filters
    name = request.GET.get('name', '').strip()
    student_code = request.GET.get('student_code', '').strip()
    email = request.GET.get('email', '').strip()
    phone = request.GET.get('phone', '').strip()
    study_year = request.GET.get('study_year', '').strip()
    department_id = request.GET.get('department', '').strip()

    if name:
        students = students.filter(name__icontains=name)
    if student_code:
        students = students.filter(student_code__icontains=student_code)
    if email:
        students = students.filter(email__icontains=email)
    if phone:
        students = students.filter(phone__icontains=phone)
    if study_year:
        students = students.filter(study_year__icontains=study_year)
    if department_id:
        students = students.filter(department_id=department_id)

    context = {
        'students': students,
        'departments': departments,
    }
    return render(request, 'student_management.html', context)



##################################################
##################################################
# Module Job #####################################
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

@login_required(login_url='sign_in')
def import_jobs(request):
    if request.method == 'POST':
        if 'csv_file' in request.FILES:
            csv_file = request.FILES['csv_file']

            if not csv_file.name.endswith('.csv'):
                return JsonResponse({'status': 'error', 'message': "File không đúng định dạng CSV."})

            try:
                decoded_file = csv_file.read().decode('utf-8-sig').splitlines()
                reader = csv.DictReader(decoded_file)

                results = []
                for row in reader:
                    try:
                        job_link = str(row.get('job_link', '')).strip()
                        job_name = str(row.get('job_name', '')).strip()
                        company_name = str(row.get('company_name', '')).strip()
                        salary = row.get('salary', '').strip()
                        # region = str(row.get('region', '')).strip()
                        # job_status = str(row.get('job_status', '')).strip()
                        # post_date = str(row.get('post_date', '')).strip()
                        # scrape_date = str(row.get('scrape_date', '')).strip() 
                        jd = str(row.get('jd', '')).strip()
                        jd = str(row.get('description', '')).strip()
                        hr_id = str(row.get('hr_id', '')).strip()
                        company_href = str(row.get('company_href', '')).strip()
                        industry_name = str(row.get('industry_name', 'Chưa phân loại')).strip()

                        if not job_link or not job_name or not company_name:
                            continue  # Bỏ qua dòng thiếu dữ liệu quan trọng

                        hr, _ = models.HR.objects.get_or_create(
                            name=hr_id if hr_id else "N/A",
                            defaults={'link': job_link}
                        )

                        company, _ = models.Company.objects.get_or_create(
                            company_name=company_name,
                            defaults={'company_link': company_href}
                        )

                        industry, _ = models.Industry.objects.get_or_create(
                            industry_name=industry_name,
                            defaults={'description': 'Chưa phân loại'}
                        )

                        job, created = models.Job.objects.get_or_create(
                            link_job=job_link,
                            defaults={
                                'job_name': job_name,
                                'salary': salary if salary else None,
                                # 'region': region,
                                # 'job_status': job_status,
                                # 'post_date': post_date,
                                # 'scrape_date': scrape_date,
                                'jd': jd,
                                # 'description': description,
                                'company': company,
                                'hr': hr,
                                'industry': industry,
                            }
                        )
                        # print(job)


                        results.append({
                            'status': 'success',
                            'job_name': job_name,
                            'company_name': company_name,
                            'created': created,
                        })
                    except Exception as e:
                        error_trace = traceback.format_exc()
                        results.append({
                            'status': 'error',
                            'job_name': job_name,
                            'company_name': company_name,
                            'error': str(e),
                            'traceback': error_trace
                        })

                return JsonResponse({'status': 'complete', 'results': results})
            except Exception as e:
                # return JsonResponse({'status': 'error', 'message': f"Có lỗi xảy ra: {str(e)}"})
                return JsonResponse({'status': 'error', 'message': f"Có lỗi xảy ra: {str(e)}", 'traceback': traceback.format_exc()})

    return render(request, 'job/import_jobs.html')


from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseDownload
import io

@login_required(login_url='sign_in')
def update_jobs_from_drive(request):
    if request.method == 'POST':
        try:
            # Thiết lập xác thực Google Drive
            SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
            SERVICE_ACCOUNT_FILE = r'C:\working\job_rcm\job_rcm_code\django\due_job_rcm\job-rcm-luan-0e530aa9b6a0.json'  # Cập nhật đường dẫn thực tế
            
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            service = build('drive', 'v3', credentials=credentials)
            
            # Tìm file CSV trong thư mục Google Drive
            folder_id = '1hLlh5J_wRVWySJZb4dCeDwobpw5CaNNx'  # ID thư mục của bạn
            file_name_to_find = "final.csv"  # Tên file cần tìm
            
            query = f"name = '{file_name_to_find}' and '{folder_id}' in parents"
            results = service.files().list(
                q=query,
                pageSize=10,
                fields="files(id, name, mimeType)"
            ).execute()
            items = results.get('files', [])
            
            if not items:
                return JsonResponse({'status': 'error', 'message': f"Không tìm thấy file '{file_name_to_find}' trong thư mục Drive."})
            
            # Lấy file đầu tiên tìm thấy
            file_id = items[0]['id']
            
            # Tải xuống file
            request_download = service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request_download)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            # Xử lý file CSV đã tải xuống
            file_content.seek(0)  # Về đầu file
            decoded_file = file_content.read().decode('utf-8-sig').splitlines()
            reader = csv.DictReader(decoded_file)
            
            # Xử lý dữ liệu giống như trong hàm import_jobs của bạn
            results = []
            for row in reader:
                try:
                    job_link = str(row.get('job_link', '')).strip()
                    job_name = str(row.get('job_name', '')).strip()
                    company_name = str(row.get('company_name', '')).strip()
                    salary = row.get('salary', '').strip()
                    jd = str(row.get('jd', '')).strip() or str(row.get('description', '')).strip()
                    hr_id = str(row.get('hr_id', '')).strip()
                    company_href = str(row.get('company_href', '')).strip()
                    industry_name = str(row.get('industry_name', 'Chưa phân loại')).strip()

                    if not job_link or not job_name or not company_name:
                        continue  # Bỏ qua dòng thiếu dữ liệu quan trọng

                    hr, _ = models.HR.objects.get_or_create(
                        name=hr_id if hr_id else "N/A",
                        defaults={'link': job_link}
                    )

                    company, _ = models.Company.objects.get_or_create(
                        company_name=company_name,
                        defaults={'company_link': company_href}
                    )

                    industry, _ = models.Industry.objects.get_or_create(
                        industry_name=industry_name,
                        defaults={'description': 'Chưa phân loại'}
                    )

                    job, created = models.Job.objects.get_or_create(
                        link_job=job_link,
                        defaults={
                            'job_name': job_name,
                            'salary': salary if salary else None,
                            'jd': jd,
                            'company': company,
                            'hr': hr,
                            'industry': industry,
                        }
                    )

                    results.append({
                        'status': 'success',
                        'job_name': job_name,
                        'company_name': company_name,
                        'created': created,
                    })
                except Exception as e:
                    error_trace = traceback.format_exc()
                    results.append({
                        'status': 'error',
                        'job_name': row.get('job_name', 'Unknown'),
                        'company_name': row.get('company_name', 'Unknown'),
                        'error': str(e),
                        'traceback': error_trace
                    })

            return JsonResponse({'status': 'complete', 'results': results})
        
        except Exception as e:
            return JsonResponse({
                'status': 'error', 
                'message': f"Có lỗi xảy ra khi tải từ Google Drive: {str(e)}", 
                'traceback': traceback.format_exc()
            })

    return render(request, 'job/update_jobs.html')

@login_required(login_url='sign_in')
def job_list(request):
    jobs = models.Job.objects.all()
    companies = models.Company.objects.all()
    industries = models.Industry.objects.all()
    hrs = models.HR.objects.all()

    # Global search
    search_term = request.GET.get('search', '').strip()
    
    # Apply global search if provided
    if search_term:
        from django.db.models import Q
        jobs = jobs.filter(
            Q(job_name__icontains=search_term) |
            Q(jd__icontains=search_term) |  # Sử dụng jd thay vì job_description
            Q(company__company_name__icontains=search_term) |
            Q(industry__industry_name__icontains=search_term)
        )
    
    # Apply specific filters
    job_name = request.GET.get('job_name', '').strip()
    company_name = request.GET.get('company', '').strip()
    industry_id = request.GET.get('industry', '').strip()
    salary_min = request.GET.get('salary_min', '').strip()
    hr_id = request.GET.get('hr', '').strip()

    if job_name:
        jobs = jobs.filter(job_name__icontains=job_name)
    if company_name:
        jobs = jobs.filter(company__company_name__icontains=company_name)
    if industry_id:
        jobs = jobs.filter(industry_id=industry_id)
    if salary_min:
        jobs = jobs.filter(salary__gte=salary_min)
    if hr_id:
        jobs = jobs.filter(hr_id=hr_id)

    # Phân trang với 20 job mỗi trang
    paginator = Paginator(jobs, 20)
    page = request.GET.get('page')
    try:
        jobs = paginator.page(page)
    except PageNotAnInteger:
        jobs = paginator.page(1)
    except EmptyPage:
        jobs = paginator.page(paginator.num_pages)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':  # Check if the request is AJAX
        return render(request, 'job/job_table.html', {"jobs": jobs})

    context = {
        'jobs': jobs,
        'companies': companies,
        'industries': industries,
        'hrs': hrs,
    }
    return render(request, 'job/job_list.html', context)


@login_required(login_url='sign_in')
def recommended_jobs_by_department(request):
    # Lấy ngành học của sinh viên
    student = models.Student.objects.filter(user=request.user).first()
    department = student.department

    if not department:
        return render(request, 'job/job_table.html', {"jobs": [], "message": "Bạn chưa được liên kết với ngành học."})

    # Lọc các công việc theo ngành
    # jobs = models.Job.objects.filter(industry__description__icontains=department.name)
    jobs = models.Job.objects.all().order_by('-id')[:25]
    
    # Apply filters từ request.GET
    job_name = request.GET.get('job_name', '').strip()
    company_name = request.GET.get('company', '').strip()
    industry_id = request.GET.get('industry', '').strip()
    salary_min = request.GET.get('salary_min', '').strip()
    hr_id = request.GET.get('hr', '').strip()

    if job_name:
        jobs = jobs.filter(job_name__icontains=job_name)
    if company_name:
        jobs = jobs.filter(company__company_name__icontains=company_name)
    if industry_id:
        jobs = jobs.filter(industry_id=industry_id)
    if salary_min:
        jobs = jobs.filter(salary__gte=salary_min)
    if hr_id:
        jobs = jobs.filter(hr_id=hr_id)

    # Phân trang với 20 job mỗi trang
    paginator = Paginator(jobs, 20)
    page = request.GET.get('page')
    try:
        jobs = paginator.page(page)
    except PageNotAnInteger:
        jobs = paginator.page(1)
    except EmptyPage:
        jobs = paginator.page(paginator.num_pages)


    if request.headers.get('x-requested-with') == 'XMLHttpRequest': 
        return render(request, 'job/job_table.html', {"jobs": jobs})

    context = {
        "jobs": jobs,
        "department": department,
    }
    return render(request, 'job/job_list.html', context)


@login_required(login_url='sign_in')
def recommended_jobs_by_cv(request, pk):
    cv = models.CV.objects.filter(pk=pk).last()
    if not cv:
        return JsonResponse({"jobs": [], "message": "CV not found."})

    cv_data = {
        "skills": [skill.skill.skill for skill in models.SkillinCV.objects.filter(cv=cv)],
        "experiences": [exp.experience.role for exp in models.ExperienceinCV.objects.filter(cv=cv)],
        "projects": [proj.project_name for proj in models.Project.objects.filter(cv=cv)],
    }

    jobs = models.Job.objects.select_related("company", "industry", "hr").all()
    
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

    recommended_jobs = nlp.process_cv_to_jobs(cv_data, job_data)
    

    if request.headers.get('X-Requested-With') == 'fetch':
        return JsonResponse({"jobs": recommended_jobs.to_dict(orient='records')})

    context = {
        "cv": cv,
        "jobs": recommended_jobs.to_dict(orient='records'),
    }
    
    return render(request, 'job/job_table.html', context)


def compare_cv_with_job(request, pk):
    """
    So sánh CV với mô tả công việc (JD) và trả về kết quả độ tương đồng.
    """
    cv = models.CV.objects.filter(pk=pk).last()
    if not cv:
        return JsonResponse({"message": "CV not found."}, status=404)

    if request.method == "POST":
        data = json.loads(request.body)
        job_description = data.get("job_description", "")
        if not job_description:
            return JsonResponse({"message": "Job description is required."}, status=400)

        # Thu thập dữ liệu CV từ cơ sở dữ liệu
        cv_data = {
            "skills": [skill.skill.skill for skill in models.SkillinCV.objects.filter(cv=cv)],
            "experiences": [exp.experience.role for exp in models.ExperienceinCV.objects.filter(cv=cv)],
            "projects": [proj.project_name for proj in models.Project.objects.filter(cv=cv)],
        }

        # Tính điểm tương đồng giữa CV và JD
        job_data = [{"job_name": "Custom Job", "jd": job_description}]
        recommended_jobs = nlp.process_cv_to_jobs(cv_data, job_data)

        # Trả về kết quả độ tương đồng
        similarity = recommended_jobs.iloc[0]["similarity"]
        similarity_percentage = similarity * 100 
        return JsonResponse({"similarity": similarity_percentage})

    return JsonResponse({"message": "Invalid request method."}, status=405)


###################################
######## Module Chatbot gemini ####
###################################




import google.generativeai as genai
from django.views.decorators.csrf import csrf_exempt
import json
from django.conf import settings
import os
import re
from django.views.decorators.csrf import csrf_protect

# @csrf_exempt
# Cấu hình API Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)


generation_config = {
    "temperature": 1.55,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

# Tạo model chatbot
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config,
)

chat_session = model.start_chat(history=[])


@csrf_protect 
def chat_with_gemini(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "").strip()
            user = request.user

            if user_message:
                # Nếu người dùng đã đăng nhập
                if user.is_authenticated:
                    # 1. Lấy thông tin sinh viên và CV
                    student = models.Student.objects.filter(user=user).first()
                    
                    # 2. Truy xuất thông tin liên quan từ dữ liệu
                    context_info = retrieve_context_information(user_message, student)
                    
                    # 3. Tạo prompt tăng cường với thông tin bối cảnh
                    augmented_prompt = create_augmented_prompt(user_message, context_info)
                    
                    # Log prompt để debug
                    print("DEBUG - PROMPT TO GEMINI:", augmented_prompt)
                    
                    # 4. Gửi prompt tăng cường đến Gemini
                    response = chat_session.send_message(augmented_prompt)
                else:
                    # Nếu chưa đăng nhập, sử dụng prompt thông thường
                    response = chat_session.send_message(user_message)
                
                return JsonResponse({"response": response.text})
            else:
                return JsonResponse({"error": "Tin nhắn không hợp lệ."}, status=400)

        except Exception as e:
            return JsonResponse({"error": f"Lỗi: {str(e)}"}, status=500)

    return JsonResponse({"error": "Phương thức không hợp lệ."}, status=405)

# hàm này đang bị bà điên bà khùng, làm lại là ok
def retrieve_context_information(query, student):
    """
    Truy xuất toàn bộ thông tin người dùng từ cơ sở dữ liệu, bao gồm tất cả CV nhưng chưa cần xử lý job.
    """
    context_info = {
        "student_info": {},
        "all_cvs": [],
        "similar_questions": [],
        "chat_history": [],
    }

    if not student:
        return context_info

    # 1. Thông tin sinh viên
    context_info["student_info"] = {
        "name": student.name,
        "student_code": student.student_code,
        "email": student.email,
        "phone": student.phone,
        "study_year": student.study_year,
        "department": student.department.name if student.department else "Chưa có thông tin",
        "user_id": student.user.id,
        "join_date": student.user.date_joined.strftime("%d/%m/%Y") if hasattr(student.user, 'date_joined') else "N/A",
        "last_login": student.user.last_login.strftime("%d/%m/%Y %H:%M") if student.user.last_login else "Chưa đăng nhập"
    }

    # 2. Tất cả CV của sinh viên
    all_cvs = models.CV.objects.filter(student=student).order_by('-id')
    cv_list = []

    for cv in all_cvs:
        skills = models.SkillinCV.objects.filter(cv=cv)
        experiences = models.ExperienceinCV.objects.filter(cv=cv).select_related('experience')
        projects = models.Project.objects.filter(cv=cv)
        education = models.EducationinCV.objects.filter(cv=cv).select_related('education', 'education__university')
        languages = models.LanguageinCV.objects.filter(cv=cv).select_related('language')
        certifications = models.Certification.objects.filter(cv=cv)

        cv_data = {
            "id": cv.id,
            "name": cv.name,
            "about_me": cv.about_me,
            "skills": [skill.skill.skill for skill in skills],
            "experiences": [
                {
                    "role": exp.experience.role,
                    "company": exp.experience.company_name,
                    "start_date": exp.experience.start_date.strftime("%d/%m/%Y") if exp.experience.start_date else "N/A",
                    "end_date": exp.experience.end_date.strftime("%d/%m/%Y") if exp.experience.end_date else "Hiện tại",
                    "description": exp.experience.context
                } for exp in experiences
            ],
            "projects": [
                {
                    "name": proj.project_name,
                    "content": proj.project_content,
                    "links": [link.link for link in models.Project_link.objects.filter(project=proj)]
                } for proj in projects
            ],
            "education": [
                {
                    "university": edu.education.university.university_name,
                    "degree": edu.education.degree,
                    "start_year": edu.education.start_year,
                    "end_year": edu.education.end_year
                } for edu in education
            ],
            "languages": [
                {
                    "language": lang.language.language,
                    "description": lang.language.text
                } for lang in languages
            ],
            "certifications": [cert.certificate for cert in certifications]
        }

        cv_list.append(cv_data)

    context_info["all_cvs"] = cv_list
    # print(cv_data)
    print(cv_list)

    # 3. Tìm câu hỏi tương tự (vẫn giữ vì liên quan đến query)
    context_info["similar_questions"] = find_similar_questions(query)

    return context_info

def find_relevant_jobs(query, cv=None):
    """
    Tìm các công việc phù hợp dựa trên query và CV.
    Sử dụng keyword matching đơn giản.
    """
    # Xác định từ khóa từ query
    keywords = extract_keywords(query)
    
    # Tạo query cơ bản
    job_query = Q()
    
    # Thêm từ khóa từ query vào tìm kiếm
    for keyword in keywords:
        if len(keyword) > 2:  # Bỏ qua từ quá ngắn
            job_query |= Q(job_name__icontains=keyword)
            job_query |= Q(jd__icontains=keyword)
    
    # Nếu có CV, thêm kỹ năng từ CV vào tìm kiếm
    if cv:
        skills = models.SkillinCV.objects.filter(cv=cv)
        for skill in skills:
            job_query |= Q(jd__icontains=skill.skill.skill)
    
    # Lấy tối đa 3 công việc phù hợp nhất
    jobs = models.Job.objects.filter(job_query).select_related('company', 'industry').distinct()[:3]
    
    # Chuyển đổi sang định dạng dễ đọc
    relevant_jobs = []
    for job in jobs:
        relevant_jobs.append({
            "job_name": job.job_name,
            "company": job.company.company_name if job.company else "Không xác định",
            "industry": job.industry.industry_name if job.industry else "Không xác định",
            "link": job.link_job,
            "jd_summary": job.jd[:200] + "..." if job.jd and len(job.jd) > 200 else job.jd
        })
    
    return relevant_jobs

def extract_keywords(text):
    """
    Trích xuất từ khóa từ một đoạn văn bản.
    """
    # Loại bỏ các ký tự đặc biệt và chuyển về chữ thường
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    
    # Danh sách từ dừng (stopwords) tiếng Việt
    vietnamese_stopwords = [
        "và", "của", "cho", "là", "có", "không", "được", "các", "những", 
        "với", "tôi", "bạn", "anh", "chị", "em", "ông", "bà", "họ", "mình",
        "này", "đó", "kia", "thì", "mà", "để", "từ", "về", "như", "trong",
        "ngoài", "trên", "dưới", "vì", "bởi", "cũng", "nên", "khi", "lúc"
    ]
    
    # Tách từ và loại bỏ stopwords
    words = text.split()
    keywords = [word for word in words if word not in vietnamese_stopwords and len(word) > 2]
    
    return keywords

def find_similar_questions(query):
    """
    Tìm các câu hỏi tương tự từ bộ câu hỏi được định nghĩa trước.
    """
    # Bộ câu hỏi và câu trả lời mẫu (FAQ)
    faqs = [
        {
            "question": "Làm thế nào để viết CV tốt?",
            "answer": "Để viết CV tốt, bạn nên trình bày rõ ràng các kỹ năng, kinh nghiệm và thành tích của mình. Hãy sử dụng các động từ mạnh mẽ, định dạng nhất quán và tùy chỉnh CV cho từng công việc bạn ứng tuyển."
        },
        {
            "question": "Làm thế nào để cải thiện CV của tôi?",
            "answer": "Để cải thiện CV, hãy nhấn mạnh thành tích cụ thể, cập nhật kỹ năng mới, kiểm tra lỗi chính tả, và đảm bảo định dạng nhất quán dễ đọc."
        },
        {
            "question": "Tôi nên tìm kiếm việc làm ở đâu?",
            "answer": "Bạn có thể tìm kiếm việc làm trên các nền tảng tuyển dụng trực tuyến như TopCV, VietnamWorks, LinkedIn, cũng như trên trang web của công ty mà bạn muốn ứng tuyển."
        },
        {
            "question": "Làm thế nào để chuẩn bị cho phỏng vấn?",
            "answer": "Để chuẩn bị cho phỏng vấn, hãy nghiên cứu kỹ về công ty, luyện tập trả lời các câu hỏi phỏng vấn phổ biến, chuẩn bị các câu hỏi để hỏi người phỏng vấn và ăn mặc phù hợp với văn hóa công ty."
        },
        {
            "question": "Các kỹ năng quan trọng cho ngành IT là gì?",
            "answer": "Các kỹ năng quan trọng cho ngành IT bao gồm lập trình, giải quyết vấn đề, tư duy logic, kỹ năng học tập liên tục, làm việc nhóm, và giao tiếp hiệu quả."
        }
    ]
    
    # Trích xuất từ khóa từ query
    query_keywords = set(extract_keywords(query))
    
    # Tìm câu hỏi tương tự
    similar_faqs = []
    for faq in faqs:
        # Trích xuất từ khóa từ câu hỏi
        question_keywords = set(extract_keywords(faq["question"]))
        
        # Tính độ tương đồng dựa trên số từ khóa chung
        common_keywords = query_keywords.intersection(question_keywords)
        
        if len(common_keywords) > 0:
            similarity_score = len(common_keywords) / max(len(query_keywords), len(question_keywords))
            similar_faqs.append({
                "question": faq["question"],
                "answer": faq["answer"],
                "similarity": similarity_score
            })
    
    # Sắp xếp theo độ tương đồng và lấy 2 câu hỏi tương tự nhất
    similar_faqs.sort(key=lambda x: x["similarity"], reverse=True)
    return similar_faqs[:2]

def create_augmented_prompt(user_message, context_info):
    # Định dạng prompt đúng cách
    prompt = f"""
    # Nội dung từ người dùng
    "{user_message}"
    
    # Thông tin bối cảnh (chỉ để tham khảo, KHÔNG phải từ người dùng)
    {format_context_info(context_info)}
    
    # Hướng dẫn
    Bạn là trợ lý ảo ChatBot Gemini, chuyên hỗ trợ về CV và tìm kiếm việc làm. Hãy trả lời tin nhắn của người dùng một cách tự nhiên, thân thiện và hữu ích.
    
    1. Nếu người dùng chỉ chào hỏi đơn giản, hãy chào lại ngắn gọn và giới thiệu khả năng hỗ trợ của bạn.
    2. Chỉ đưa ra thông tin chi tiết và gợi ý khi người dùng thực sự yêu cầu.
    3. Trả lời phải ngắn gọn, súc tích và đi thẳng vào vấn đề.
    4. KHÔNG bao giờ liệt kê tất cả dữ liệu bối cảnh nếu không được yêu cầu cụ thể.
    5. KHÔNG giả vờ như bạn là người dùng hay nói thay người dùng.
    
    Trả lời tin nhắn của người dùng:
    """
    
    return prompt

def format_context_info(context_info):
    """Định dạng thông tin bối cảnh một cách cấu trúc và rõ ràng"""
    student_info = context_info.get("student_info", {})
    all_cvs = context_info.get("all_cvs", [])
    similar_questions = context_info.get("similar_questions", [])
    
    formatted_info = ""
    
    if student_info:
        formatted_info += "## Thông tin người dùng\n"
        formatted_info += f"- Tên: {student_info.get('name', 'Không có')}\n"
        formatted_info += f"- MSSV: {student_info.get('student_code', 'Không có')}\n"
        formatted_info += f"- Ngành học: {student_info.get('department', 'Không có')}\n"
        formatted_info += f"- Email: {student_info.get('email', 'Không có')}\n"
        formatted_info += f"- Năm học: {student_info.get('study_year', 'Không có')}\n"
    
    if all_cvs:
        formatted_info += "\n## Thông tin CV\n"
        for i, cv in enumerate(all_cvs):
            formatted_info += f"\n### CV {i+1}: {cv.get('name', 'Không có tên')}\n"
            
            if cv.get('about_me'):
                formatted_info += f"- Giới thiệu: {cv.get('about_me')}\n"
            
            if cv.get('skills'):
                formatted_info += f"- Kỹ năng: {', '.join(cv.get('skills', ['Không có']))}\n"
            
            if cv.get('experiences'):
                formatted_info += "- Kinh nghiệm:\n"
                for exp in cv.get('experiences', []):
                    formatted_info += f"  * {exp.get('role', '')} tại {exp.get('company', '')}"
                    if exp.get('start_date') and exp.get('end_date'):
                        formatted_info += f" ({exp.get('start_date')} - {exp.get('end_date')})\n"
                    else:
                        formatted_info += "\n"
                    # Thêm context/mô tả công việc
                    if exp.get('description'):
                        formatted_info += f"    Mô tả: {exp.get('description')}\n"
            
            if cv.get('education'):
                formatted_info += "- Học vấn:\n"
                for edu in cv.get('education', []):
                    formatted_info += f"  * {edu.get('degree', '')} tại {edu.get('university', '')}"
                    if edu.get('start_year') and edu.get('end_year'):
                        formatted_info += f" ({edu.get('start_year')} - {edu.get('end_year')})\n"
                    else:
                        formatted_info += "\n"
            
            if cv.get('projects'):
                formatted_info += "- Dự án:\n"
                for proj in cv.get('projects', []):
                    formatted_info += f"  * {proj.get('name', '')}\n"
                    # Thêm nội dung dự án
                    if proj.get('content'):
                        formatted_info += f"    Nội dung: {proj.get('content')}\n"
                    # Thêm các liên kết dự án nếu có
                    if proj.get('links') and len(proj.get('links')) > 0:
                        formatted_info += f"    Liên kết: {', '.join(proj.get('links'))}\n"
            
            if cv.get('languages'):
                formatted_info += "- Ngôn ngữ:\n"
                for lang in cv.get('languages', []):
                    formatted_info += f"  * {lang.get('language', '')}"
                    if lang.get('description'):
                        formatted_info += f": {lang.get('description')}\n"
                    else:
                        formatted_info += "\n"
            
            if cv.get('certifications'):
                formatted_info += f"- Chứng chỉ: {', '.join(cv.get('certifications', ['Không có']))}\n"
    
    if similar_questions:
        formatted_info += "\n## Câu hỏi tương tự\n"
        for i, q in enumerate(similar_questions):
            formatted_info += f"- Q{i+1}: {q.get('question')}\n"
            formatted_info += f"  A{i+1}: {q.get('answer')}\n"
    
    return formatted_info




#############################
# Module Chatting & chatbot
#############################

@login_required(login_url='sign_in')
def chat_with_admin(request):
    user1 = request.user
    user2 = User.objects.filter(is_superuser=True).first()
    
    # if not user2:
    #     return render(request, 'chat/room_list.html', {'error': 'Không tìm thấy admin.'})

    # Tạo hoặc lấy phòng chat với admin
    room, created = models.PrivateChatRoom.objects.get_or_create(
        user1=min(user1, user2, key=lambda u: u.id),
        user2=max(user1, user2, key=lambda u: u.id)
    )

    return redirect('chat_dashboard_with_room', room_id=room.id)


@login_required(login_url='sign_in')
def chat_dashboard(request, room_id=None):
    # Lấy danh sách các phòng chat
    rooms = models.PrivateChatRoom.objects.filter(
        Q(user1=request.user) | Q(user2=request.user)
    ).annotate(last_message_time=Max('messages__created_at')).order_by('-last_message_time')

    # Gán tin nhắn cuối cùng và tên hiển thị cho mỗi phòng
    for room in rooms:
        last_message = models.ChatMessage.objects.filter(room=room).order_by('-created_at').first()
        room.last_message = f"{last_message.sender.username}: {last_message.message[:30]}..." if last_message else "Chưa có tin nhắn nào."
        # room.display_username = room.user2.username if room.user1 == request.user else room.user1.username
        # room.display_username = "Phòng hỗ trợ sinh viên" if chat_partner.is_superuser else chat_partner.username
        chat_partner = room.user2 if room.user1 == request.user else room.user1
        room.display_username = "Phòng hỗ trợ sinh viên" if chat_partner.is_superuser else chat_partner.username

    # Nếu có `room_id`, lấy tin nhắn của phòng đó
    messages = []
    chat_partner_name = ""
    if room_id:
        room = models.PrivateChatRoom.objects.get(id=room_id)
        messages = models.ChatMessage.objects.filter(room=room).order_by('created_at')
        chat_partner = room.user1 if room.user2 == request.user else room.user2
        chat_partner_name = "Phòng hỗ trợ sinh viên" if chat_partner.is_superuser else chat_partner.username

    context = {
        'rooms': rooms,
        'room_id': room_id,
        'messages': messages,
        'chat_partner_name': chat_partner_name,
    }
    return render(request, 'chat/dashboard.html', context)


@login_required(login_url='sign_in')
def chat_with_bot(request):
    """Tạo hoặc lấy phòng chat với ChatBot Assistant."""
    bot_user, created = User.objects.get_or_create(
        username="ChatBot_Assistant",
        defaults={"is_active": True, "is_superuser": False}
    )

    # Tạo hoặc lấy phòng chat với chatbot
    room, created = models.PrivateChatRoom.objects.get_or_create(
        user1=min(request.user, bot_user, key=lambda u: u.id),
        user2=max(request.user, bot_user, key=lambda u: u.id)
    )

    return redirect('chat_dashboard_with_room', room_id=room.id)

