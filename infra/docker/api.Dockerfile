FROM node:22-alpine
WORKDIR /app
COPY . .
RUN npm ci && npm --workspace apps/api run build
ENV NODE_ENV=production
EXPOSE 4000
CMD ["npm","--workspace","apps/api","run","start"]
