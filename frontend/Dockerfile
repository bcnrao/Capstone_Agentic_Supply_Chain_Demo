# Multi-stage build for the React + Ant Design product UI. Stage 1 builds the
# static bundle with Vite; stage 2 serves it with nginx. VITE_API_BASE_URL is
# baked in at build time (Vite inlines env vars), overridable via build-arg.
FROM node:20-alpine AS build
WORKDIR /app

ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
