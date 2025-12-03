FROM node:20
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 3002
CMD ["npm","run","start","--","-p","3002","-H","0.0.0.0"]
