FROM node:24-alpine AS frontend-builder
WORKDIR /app/frontend

COPY app/frontend/package*.json ./
RUN npm install

COPY app/frontend/tsconfig*.json ./
COPY app/frontend/vite.config.ts ./
COPY app/frontend/tailwind.config.cjs app/frontend/postcss.config.cjs app/frontend/.prettierrc ./
COPY app/frontend/src ./src
COPY app/frontend/index.html ./

RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app
COPY README.md USER_GUIDE.md ./
COPY --from=frontend-builder /app/frontend/dist ./app/frontend/dist

# App configuration
ENV PORT=8000

# Start the FastAPI app with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
