# Dooper AI Symptom Checker & Doctor Recommendation Portal

An AI-powered symptom assessment and doctor specialty recommendation system. Designed to closely match the official **Dooper** healthcare branding system, utilizing the Outfit typography, vibrant brand colors, clean card layers, responsive layouts, and featuring advanced utilities like Light/Dark themes, Speech Recognition, PDF exportation, and an interactive Doctor AI Assistant.

---

## 🛠 Tech Stack & Core Libraries

- **Backend**: Python Flask (`3.0.2`)
- **Database**: MySQL (`mysql-connector-python`)
- **Authentication**: JWT token-based authentication (stored securely in HTTP-only cookies)
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla HSL-derived palette, outfit fonts, FontAwesome 6 icons)
- **Key Client libraries**:
  - Web Speech API (speech recognition for symptoms description)
  - [jsPDF CDN](https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js) (client-side PDF generation)

---

## 🚀 Setup & Execution Instructions

Follow these simple steps to configure and run the application locally on your Windows system:

### 1. Database Setup
Ensure your MySQL server is running locally on port `3306`. Make sure a database administrator account exists with password matching the configuration in `database.py` and `setup.py` (Default: `root` / `123Shorya@`).

### 2. Dependency Installation
Create a Python virtual environment and install the required libraries listed in `requirements.txt`:
```bash
# Navigate to the workspace folder
cd C:\Users\Shourya Sinha\.gemini\antigravity-ide\scratch\ai_symptom_checker

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Initialize Database & Directory Assets
Run the bootstrap setup script to construct database tables, folders, and copy the official branding logo:
```bash
python setup.py
```

### 4. Boot the Server
Start the Flask dev server:
```bash
python app.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🌟 Highlights of Implemented Features

1. **Authentication**: Form-validated signup and login routes generating JWT auth tokens, verifying security standards.
2. **AI Checker engine**: Multi-input assessment evaluating symptoms, age, gender, duration, and conditions.
3. **Assessment History**: Revisit previous findings with date, severity, and specialty columns. Supports searching and filter queries.
4. **Interactive Chat Assistant**: Allows patient to converse with an AI doctor about follow-up instructions.
5. **Light/Dark Mode**: Built-in system theme toggles adjusting backgrounds, borders, and cards dynamically.
6. **Voice Input (Speech-to-Text)**: Speak symptoms directly via browser microphone integration.
7. **Multi-language Support**: Updates language preferences globally. Assessments and chat replies translate instantly to English, Spanish, French, German, or Hindi.
8. **PDF Export**: Single-click document compilation downloading professional medical cards client-side.
