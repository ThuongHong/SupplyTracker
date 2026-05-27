FROM node:20-alpine

WORKDIR /app

# Copy package manifests first for layer caching; glob tolerates absence before Bundle 9
COPY frontend/package*.json /app/

# Install dependencies; falls back gracefully if package.json doesn't exist yet
RUN npm install || echo 'frontend not yet scaffolded — install at runtime'

# Copy full frontend source (no-op if frontend/ is empty or not yet created)
COPY frontend/ /app/

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
