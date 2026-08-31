# DATA-260 HW1 — Part I static app (Campus Course Catalogue & Enrolment)
# Served on PORT_BASE = 8008 (8000 + SID4 mod 900, SID4 = 1808)
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY app.js /usr/share/nginx/html/app.js

EXPOSE 8008
