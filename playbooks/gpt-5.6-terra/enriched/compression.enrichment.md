applicable_flavors for the playbook this content is being added to: ['cs', 'ams']

### Configure gzip compression level

```nginx
gzip on;
gzip_comp_level 9;
```

The evidence includes an Nginx reverse-proxy configuration with gzip enabled at compression level 9.

> **Source PRs** — **approach:** next-step/infra-subway-k8s#16