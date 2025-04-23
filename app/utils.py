# utils.py
def get_or_create_templates():
    """Tạo hoặc lấy các template mặc định"""
    from app.models import CVTemplate
    
    templates = []
    
    default, created = CVTemplate.objects.get_or_create(
        name="Original",
        defaults={"template_file": "cv_templates/original.html"}
    )
    templates.append(default)
    
    modern, created = CVTemplate.objects.get_or_create(
        name="Modern",
        defaults={"template_file": "cv_templates/modern.html"}
    )
    templates.append(modern)
    
    minimal, created = CVTemplate.objects.get_or_create(
        name="Minimal",
        defaults={"template_file": "cv_templates/minimal.html"}
    )
    templates.append(minimal)
    
    return templates