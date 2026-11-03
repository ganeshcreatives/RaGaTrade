FROM node:22-alpine AS build
WORKDIR /app
COPY . .
ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL
RUN npm ci && npm --workspace apps/web run build
FROM nginx:1.27-alpine
ENV API_INTERNAL_HOST=api
COPY infra/docker/nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/apps/web/dist /usr/share/nginx/html
EXPOSE 80
