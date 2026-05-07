FROM node:23-bookworm AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:23-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/package*.json ./
COPY --from=build /app/dist ./dist
RUN npm ci --omit=dev
EXPOSE 6060
CMD ["node", "dist/server/index.js"]
