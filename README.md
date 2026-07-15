# Coding Club Web App - Backend

FastAPI + MongoDB (Beanie ODM) backend service for the Coding Club application.

## Prerequisites

- **Python 3.10+**
- **MongoDB** running locally (`mongodb://localhost:27017`) or a remote MongoDB Atlas URI.

## Getting Started

1. **Clone/Navigate** to the backend directory:
   ```bash
   cd backend
   ```

2. **Create a Virtual Environment**:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Copy `.env.example` to `.env` and adjust the variables if needed:
   ```bash
   copy .env.example .env
   ```

5. **Start the Application**:
   Run the dev server using Uvicorn:
   ```bash
   uvicorn app.main:app --reload
   ```

6. **API Documentation**:
   Once started, visit:
   - Interactive Swagger docs: [http://localhost:8000/docs](http://localhost:8000/docs)
   - Alternative ReDoc docs: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Directory Structure

- `app/main.py`: Entrypoint configuring CORS, endpoints, and Lifespan startup hooks.
- `app/core/`: Security utils (JWT, bcrypt) and global configurations.
- `app/models/`: MongoDB document models mapped using Beanie ODM.
- `app/api/`: REST routing handlers separated by resources (e.g. auth, members, events).
