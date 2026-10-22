FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci --no-audit --no-fund
COPY apps/web apps/web
COPY packages/contracts packages/contracts
ENV NEXT_TELEMETRY_DISABLED=1 PAO_API_URL=http://api:8000
RUN npm run build
USER node
EXPOSE 3000
CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
