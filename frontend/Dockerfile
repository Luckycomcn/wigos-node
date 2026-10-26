# 两段式：build 段只装依赖、跑 vite build；运行段用 nginx 静态服务。
# 原版直接 `CMD npm run dev`，交付出去的是一个 Vite 开发服务器：源码与
# HMR 通道对外可见，性能与稳定性都不是生产形态。
FROM node:22-slim AS build

WORKDIR /app

# 先拷 lockfile 再装，改业务代码不会让这一层缓存失效。
COPY package.json package-lock.json* ./
# 有 lockfile 就用 ci（可复现），没有才退回 install。
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.container.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]