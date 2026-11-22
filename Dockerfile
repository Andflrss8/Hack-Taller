FROM node:22-slim

# openssl es requerido por Prisma en imágenes slim
RUN apt-get update -y && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar manifiestos primero para aprovechar la caché de capas
COPY package*.json ./
RUN npm install

# Generar el cliente de Prisma
COPY prisma ./prisma/
RUN npx prisma generate

# Copiar el resto del código fuente
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
