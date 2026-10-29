FROM node:22-alpine AS build
WORKDIR /app
COPY . .
RUN npm ci && npm --workspace apps/web run build
FROM nginx:1.27-alpine
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html
EXPOSE 80
