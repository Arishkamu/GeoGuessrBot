FROM node:22-alpine
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.js ./
COPY src ./src
COPY public ./public
RUN npm run build
EXPOSE 8000

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "8000", "--strictPort"]
