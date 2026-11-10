# Multi-stage Dockerfile for FridgeChef AI Web Frontend
# PRD References: Section 15.1, Section 15.2, Implementation Plan Phase 9 Task 6

# ==========================================
# Stage 1: Build static frontend assets
# ==========================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency specifications
COPY package.json package-lock.json* ./

# Clean install of frontend dependencies
RUN npm ci

# Copy full frontend application source
COPY . .

# Build production assets (TypeScript check + Vite production bundle + PWA)
RUN npm run build


# ==========================================
# Stage 2: Serve with lightweight Nginx Alpine
# ==========================================
FROM nginx:1.27-alpine AS runner

# Remove default Nginx site configs and files
RUN rm -rf /etc/nginx/conf.d/default.conf /usr/share/nginx/html/*

# Copy custom Nginx reverse-proxy and routing configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Set appropriate permissions for standard nginx user
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

EXPOSE 80

# Healthcheck testing frontend server availability
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

