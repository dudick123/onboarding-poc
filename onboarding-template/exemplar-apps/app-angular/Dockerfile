# Multi-stage: build with Node, serve with nginx.
# angular.json configures outputPath.browser="" so files land directly in dist/
FROM node:20-alpine AS build
WORKDIR /app
COPY . .
RUN npm ci && npm run build --configuration=production

FROM nginx:alpine
COPY --from=build /app/dist/ /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
