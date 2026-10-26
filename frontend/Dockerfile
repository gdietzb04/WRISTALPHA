FROM node:26.12.1-alpine

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build && chown -R node:node /app

USER node
EXPOSE 5173
CMD ["npm", "run", "preview"]
