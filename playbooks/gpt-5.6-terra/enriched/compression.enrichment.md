### Nginx: Configure gzip MIME types for legacy fonts

The Nginx configuration enables gzip and includes legacy font MIME types in `gzip_types`.

```nginx
http {
  gzip on;
  gzip_comp_level 9;
  gzip_vary on;
  gzip_types text/plain text/css application/json application/x-javascript \
             application/javascript text/xml application/xml application/rss+xml \
             text/javascript image/svg+xml application/vnd.ms-fontobject \
             application/x-font-ttf font/opentype;
}
```

> **Source PRs** — **approach:** next-step/infra-subway-k8s#16