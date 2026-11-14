# 與 apps/web/.nvmrc 同步 (Dockerfile 讀不到它)。只寫 major, 才吃得到修補版。
ARG NODE_VERSION=26

# ---- deps stage ----
FROM node:${NODE_VERSION}-slim AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

# ---- dev stage ----
FROM node:${NODE_VERSION}-slim AS dev
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
CMD ["npm", "run", "dev"]

# ---- builder stage ----
FROM node:${NODE_VERSION}-slim AS builder
# 沒有 build 期設定, 一律執行期注入 (見 shared/runtime/config.ts)。
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_SERVER_ACTIONS_ENCRYPTION_KEY 在 Next 裡扛兩個需求相反的角色:
#
#   build 期   Server Action id 的 salt, 會寫進 server-reference-manifest.json。要穩定
#              (換了開著的分頁會 "Server Action was not found"), 但不需保密。
#   執行期     閉包參數的 AES-GCM 金鑰。要保密、要能輪替。
#
# 同一個值兩用的話, 真金鑰會跟著 manifest 被烤進 image。所以 build 期只給這個
# **公開常數**, 真金鑰由 compose 在執行期注入 —— Next 的實作是環境變數優先於 manifest
# (以上都實測過, 不要憑讀碼推翻)。忘了注入由 instrumentation.ts 在開機時擋下,
# ci.yml 的 e2e job 也會檢查 image 裡只有這個常數。
ARG NEXT_ACTIONS_ID_SALT="cHVibGljLWFjdGlvbi1pZC1zYWx0LW5vdC1zZWNyZXQ="
RUN NEXT_SERVER_ACTIONS_ENCRYPTION_KEY="$NEXT_ACTIONS_ID_SALT" npm run build

# ---- prod stage (standalone) ----
FROM node:${NODE_VERSION}-slim AS prod
ENV NODE_ENV=production
# standalone 的 server.js 綁在 $HOSTNAME, 而 Docker 會把它設成容器 ID ——
# 不覆寫的話 127.0.0.1 沒人在聽, healthcheck 永遠不過, nginx 也就永遠起不來。
ENV HOSTNAME=0.0.0.0
WORKDIR /app
# 以 node 映像檔內建的非 root 使用者執行。
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public
USER node
CMD ["node", "server.js"]
