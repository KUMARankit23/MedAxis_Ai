FROM nginx:1.25-alpine
RUN rm -f /etc/nginx/conf.d/default.conf
EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
