# Job Recommendation System
![image](https://github.com/user-attachments/assets/f39c3612-8942-462d-84b2-caa0a56a0ac3)


## 🌟 Overview

The **DUE Job Recommendation System** is a comprehensive career platform designed specifically for Danang University of Economics students. The system empowers students to create professional CVs, discover suitable job opportunities, and receive personalized job recommendations based on their skills and educational background.

Leveraging advanced machine learning algorithms and natural language processing, our platform creates a seamless bridge between students and employment opportunities.

## ✨ Key Features

### 👤 User Management
- **Secure Authentication**: Custom implementation with role-based access control
- **Student Registration**: Simple onboarding with university credentials
- **Profile Management**: Comprehensive user profile with academic integration

### 📄 CV Builder & Management
- **Interactive CV Creation**: User-friendly interface for building professional resumes
- **Multiple Template Support**: Choose from various professional designs
- **Section Management**: Skills, experience, education, projects, languages, and certifications
- **PDF Export**: Generate high-quality, print-ready PDF documents

### 💼 Job Management
- **Advanced Job Search**: Filter by industry, company, salary, and more
- **Intelligent Recommendations**: ML-powered job matching based on student profiles
- **Bulk Import**: Administrative tools for efficient job data management

### 🤖 AI Assistants
- **Gemini-powered ChatBot**: Context-aware career advice and guidance
- **Real-time CV Analysis**: Get instant feedback on resume quality 
- **Job-CV Comparison**: Analyze how well your CV matches specific job descriptions

### 💬 Communication Tools
- **Private Chat System**: Direct messaging with administrators
- **Admin Support Room**: Dedicated channel for assistance
- **Bot Interactions**: 24/7 automated support

## 🛠️ Technologies

- **Backend**: Django 4.2, Python 3.8+
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap
- **Database**: PostgreSQL
- **AI/ML**: Google Gemini 2.0, Custom NLP models, RAG
- **Authentication**: Django Authentication System
- **Visualization**: ReportLab, SVG
- **API Integration**: Google Drive API, Google Sheets API

## 📊 Architecture

The system follows a structured MVT (Model-View-Template) architecture with dedicated modules for:

- User management and authentication
- CV creation and management
- Job discovery and recommendation
- AI-powered chatbot assistance
- Administrative operations

## 📋 Installation & Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/due_job_rcm.git
cd due_job_rcm

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your configuration

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

## 🚀 Deployment

Detailed deployment instructions for:
- Docker containers
- Heroku
- AWS EB/EC2
- DigitalOcean

Can be found in the [Deployment Guide](docs/deployment.md).

## 🔒 Security Features

- CSRF protection
- Password hashing
- Session management
- XSS prevention
- Input validation

## 🔧 Administrative Tools

- Student data import from CSV/Google Sheets
- Job data management with bulk operations
- User activity monitoring
- Template management

## 👥 Contributors

- [Lead Developer Name](https://github.com/leaddev)
- [Backend Developer Name](https://github.com/backenddev)
- [Frontend Developer Name](https://github.com/frontenddev)
- [ML Engineer Name](https://github.com/mlengineer)

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For support, questions, or feedback, please:
- Open an [issue](https://github.com/yourusername/due_job_rcm/issues)
- Contact us at support@example.com
- Visit our [documentation](https://due-job-rcm.readthedocs.io/)

---

Made with ❤️ for Danang University of Economics students
