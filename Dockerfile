FROM python:alpine

WORKDIR /app

COPY pyproject.toml README.md License ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir build \
    && python -m build \
    && pip install --no-cache-dir dist/*.whl \
    && rm -rf dist

ENTRYPOINT ["fhtoolkit"]
CMD ["--help"]
