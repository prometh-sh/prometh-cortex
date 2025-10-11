# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

The `main` branch always contains the latest stable release.

## Reporting a Vulnerability

The Prometh Cortex team takes security seriously. If you discover a security vulnerability, please follow these steps:

### For Security Issues

**DO NOT** open a public GitHub issue for security vulnerabilities.

Instead, please report security issues via one of these methods:

1. **Email**: Send details to **786743+ivannagy@users.noreply.github.com**
2. **GitHub Security Advisories**: Use the [Security Advisory](https://github.com/ivannagy/prometh-cortex/security/advisories/new) feature

### What to Include

When reporting a vulnerability, please include:

- **Description**: Clear explanation of the vulnerability
- **Impact**: What could an attacker accomplish?
- **Reproduction Steps**: Detailed steps to reproduce the issue
- **Affected Versions**: Which versions are vulnerable?
- **Proposed Fix**: If you have suggestions (optional)
- **Your Contact Info**: So we can follow up with questions

### What to Expect

- **Acknowledgment**: We'll acknowledge receipt within 48 hours
- **Assessment**: We'll assess the severity and impact within 5 business days
- **Updates**: We'll keep you informed of progress
- **Credit**: We'll credit you in the security advisory (if you wish)
- **Timeline**: Critical issues will be addressed immediately; others within 30 days

## Security Considerations for Users

### General Best Practices

1. **Keep Updated**: Always use the latest version from the `main` branch
2. **Secure Configuration**: Keep `config.toml` and authentication tokens private
3. **Network Security**: Use HTTPS and secure connections for cloud vector stores
4. **Access Control**: Restrict access to HTTP server endpoints with strong auth tokens
5. **Data Privacy**: Be mindful of sensitive information in indexed documents

### Authentication & Authorization

#### HTTP Server Security
- **Bearer Tokens**: Always use strong, randomly generated authentication tokens
- **Token Storage**: Store tokens securely in `config.toml` (gitignored by default)
- **Token Rotation**: Rotate tokens regularly, especially after exposure
- **Network Binding**: Bind to `localhost` for local-only access, use firewall rules for remote access

Example secure token generation:
```bash
# Generate a secure random token
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### MCP Integration Security
- **Local Only**: MCP servers run locally via stdio (no network exposure)
- **No Authentication**: MCP uses stdio transport (inherently local)
- **Environment Variables**: Keep environment-based configurations private

### Data Security

#### Document Processing
- **Sensitive Data**: Be cautious when indexing documents containing PII, credentials, or secrets
- **YAML Frontmatter**: Review metadata before indexing (author names, emails, etc.)
- **Index Storage**: Protect `.rag_index/` directory (contains document embeddings)
- **Qdrant Cloud**: Use encryption in transit (HTTPS) and at rest for cloud deployments

#### Best Practices for Private Data
- **Gitignore**: Ensure `config.toml`, `.rag_index/`, and `qdrant_storage/` are gitignored
- **Access Control**: Restrict file system permissions on index directories
- **Sanitization**: Review documents before indexing to remove sensitive information
- **Backup Security**: Encrypt backups if they contain sensitive document embeddings

### Network Security

#### HTTP Server
- **Localhost Binding**: Default binding to `localhost:8080` (local access only)
- **Remote Access**: If exposing remotely, use reverse proxy with TLS (nginx, Caddy)
- **CORS Configuration**: Restrict CORS origins in production deployments
- **Rate Limiting**: Consider rate limiting for production HTTP endpoints

#### Qdrant Vector Store
- **Local Docker**: Use network isolation for local Qdrant containers
- **Cloud Qdrant**: Always use API keys and HTTPS connections
- **API Key Storage**: Store Qdrant API keys in `config.toml` (never commit to git)

### Known Limitations & Risks

1. **No Built-in Rate Limiting**: HTTP server lacks rate limiting (use reverse proxy)
2. **File System Access**: CLI has full file system access (run with appropriate user permissions)
3. **Markdown Processing**: No sandboxing for Markdown content (trust your document sources)
4. **Embedding Models**: Downloaded from HuggingFace (verify model sources)
5. **No Input Sanitization**: Query inputs are not sanitized (validate before use in sensitive contexts)
6. **Vector Store Access**: No built-in access control beyond authentication tokens

### Deployment Recommendations

#### Development
```toml
[server]
host = "localhost"
port = 8080
auth_token = "dev-token-only"  # Weak token OK for local dev
```

#### Production
```toml
[server]
host = "127.0.0.1"  # Local only, use reverse proxy for external access
port = 8080
auth_token = "use-strong-random-token-here"  # Strong token required

[vector_store.qdrant]
use_https = true  # Always use HTTPS for cloud Qdrant
api_key = "your-secure-api-key"
```

## Security Updates

Security updates will be:

- Released immediately for critical vulnerabilities
- Announced via GitHub Security Advisories
- Documented in CHANGELOG.md
- Tagged with version numbers

## Disclosure Policy

- **Private Disclosure**: Security issues are disclosed privately to maintainers
- **Public Disclosure**: Only after a fix is available or 90 days (whichever comes first)
- **Coordinated Release**: Fixes released with public disclosure when possible

## Common Security Questions

### Q: Is my data sent to external servers?
**A**: No. All embedding generation and vector indexing happens locally or in your chosen vector store (FAISS local or Qdrant). No document content is sent to external APIs.

### Q: What data does the HTTP server expose?
**A**: The HTTP server exposes search results from your indexed documents. Protect the server with authentication tokens and network controls.

### Q: Can I use this in a corporate environment?
**A**: Yes, with appropriate security controls:
- Use local FAISS storage or on-premises Qdrant
- Bind HTTP server to localhost only
- Review documents before indexing to exclude confidential information
- Use strong authentication tokens

### Q: How do I secure my Qdrant deployment?
**A**:
- Use API keys for authentication
- Enable HTTPS/TLS encryption
- Use network isolation for Docker deployments
- Regularly backup and encrypt Qdrant storage

## Security Checklist

Before deploying Prometh Cortex:

- [ ] Strong authentication tokens configured
- [ ] `config.toml` added to `.gitignore` (default)
- [ ] Qdrant API keys stored securely (not in git)
- [ ] HTTP server bound to appropriate network interface
- [ ] Reverse proxy with TLS for remote access (if needed)
- [ ] File system permissions set appropriately
- [ ] Document content reviewed before indexing
- [ ] Regular security updates applied
- [ ] Backup strategy implemented
- [ ] Monitoring and logging configured

## Additional Resources

- [GitHub Security](https://github.com/ivannagy/prometh-cortex/security)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [Model Context Protocol Security](https://modelcontextprotocol.io/docs/security)

---

**Thank you for helping keep Prometh Cortex secure!**
