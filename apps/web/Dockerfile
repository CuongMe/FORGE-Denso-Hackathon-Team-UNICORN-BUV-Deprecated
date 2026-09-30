FROM node:22-alpine AS build

WORKDIR /workspace/apps/web
RUN corepack enable

COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml apps/web/.npmrc ./
RUN pnpm install --frozen-lockfile

COPY apps/web ./
ARG NEXT_PUBLIC_FORGE_API_URL=/api
ENV NEXT_PUBLIC_FORGE_API_URL=$NEXT_PUBLIC_FORGE_API_URL
RUN pnpm build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /workspace/apps/web/package.json ./package.json
COPY --from=build /workspace/apps/web/.next ./.next
COPY --from=build /workspace/apps/web/public ./public
COPY --from=build /workspace/apps/web/node_modules ./node_modules

EXPOSE 3000
CMD ["node", "./node_modules/next/dist/bin/next", "start", "--hostname", "0.0.0.0"]
