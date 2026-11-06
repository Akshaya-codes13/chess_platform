FROM python:3.12-slim

WORKDIR /code

# INSTALL_DEV=true also installs the test tools (requirements-dev.txt).
# docker-compose.yml enables it for the development backend service only.
ARG INSTALL_DEV=false

COPY requirements.txt requirements-dev.txt ./

RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
