FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install --silent

COPY . .

# Build-time environment variables
ARG REACT_APP_API_URL=http://localhost:8000
ARG REACT_APP_SENTRY_DSN=
ARG REACT_APP_ENVIRONMENT=production

ENV REACT_APP_API_URL=$REACT_APP_API_URL
ENV REACT_APP_SENTRY_DSN=$REACT_APP_SENTRY_DSN
ENV REACT_APP_ENVIRONMENT=$REACT_APP_ENVIRONMENT
ENV DISABLE_ESLINT_PLUGIN=true

RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
