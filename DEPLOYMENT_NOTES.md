# Deployment Strategy & Considerations

This document outlines the general steps and considerations for deploying the Podcast-to-Reels web application, which consists of a Django backend, a React frontend, and Celery workers.

## 1. Choosing a Hosting Platform/Strategy

The choice depends on budget, scalability needs, and team expertise. Options include:

*   **Platform-as-a-Service (PaaS):**
    *   **Heroku:** Simplifies deployment, good for rapid development. Manages infrastructure. Requires a Procfile. Add-ons for databases (Heroku Postgres) and message brokers (Heroku Redis).
    *   **AWS Elastic Beanstalk:** More configurable than Heroku, integrates with AWS services.
    *   **Google App Engine:** Similar to Elastic Beanstalk for Google Cloud.
*   **Containers (Docker):**
    *   **Docker Compose:** Good for single-server deployments or development/staging. Define services (web, worker, redis, db) in `docker-compose.yml`.
    *   **Kubernetes (EKS, GKE, AKS):** For scalable, resilient deployments. More complex to set up and manage.
*   **Infrastructure-as-a-Service (IaaS):**
    *   **AWS EC2, Google Compute Engine, Azure VMs:** Full control over virtual servers. Requires manual setup of web servers, databases, process managers, etc.

**Recommendation for initial deployment:** Start with a PaaS like Heroku for ease of use, or Docker Compose on a single VM for more control with containerization benefits.

## 2. Backend Deployment (Django - `webapp/`)

*   **Web Server (WSGI):**
    *   **Gunicorn:** A popular choice for Python WSGI. Example `gunicorn_config.py`.
        ```bash
        # Procfile (Heroku) or command for Docker/systemd
        web: gunicorn webapp_project.wsgi --config gunicorn_config.py
        ```
    *   **uWSGI:** Another robust option.
*   **Database:**
    *   Use a managed PostgreSQL or MySQL service (e.g., Heroku Postgres, AWS RDS, Google Cloud SQL).
    *   Update Django's `settings.py` (`DATABASES` setting) to use the production database URL (usually via an environment variable like `DATABASE_URL`).
    *   Run migrations: `python manage.py migrate`.
*   **Static Files:**
    *   Run `python manage.py collectstatic`.
    *   Serve static files using a dedicated web server like Nginx, or a CDN (e.g., AWS CloudFront, Cloudflare), or a service like Whitenoise if using a simpler setup (e.g., Heroku with Gunicorn directly serving static files for simplicity, not ideal for high traffic).
    *   Configure `STATIC_ROOT`, `STATIC_URL` in `settings.py`.
*   **Media Files (User Uploads - Not applicable for current app, but paths to generated videos are):**
    *   The `final_video_path` etc., stored in `VideoProject` are currently conceptual paths. In production, these would point to:
        *   Files served by the Django app itself (requires `MEDIA_ROOT`, `MEDIA_URL` setup, and Django to serve them - okay for smaller scale).
        *   Files stored and served from a cloud storage service (e.g., AWS S3, Google Cloud Storage). This is recommended for scalability. The pipeline would upload generated files there, and store the public URL.
*   **Environment Variables:**
    *   **`SECRET_KEY`**: Must be unique and kept secret.
    *   **`DEBUG = False`**.
    *   **`ALLOWED_HOSTS`**: Set to your domain(s).
    *   `DATABASE_URL`.
    *   `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` (pointing to production Redis/RabbitMQ).
    *   `OPENAI_API_KEY`, `STABILITY_API_KEY`.
    *   `FASTTEXT_MODEL_PATH` (if used by pipeline in production).
    *   Use a `.env` file for local development, but actual environment variables on the server or platform's config vars.

## 3. Frontend Deployment (React - `frontend/`)

*   **Build Static Files:**
    *   Run `npm run build` (or `yarn build`) in the `frontend/` directory. This creates an optimized static build in `frontend/build/`.
*   **Serving Strategies:**
    *   **Nginx/Apache:** Configure a web server to serve the static files from `frontend/build/` as the primary site, and proxy API requests (e.g., `/api/v1/*`) to the Django backend (Gunicorn).
        ```nginx
        # Example Nginx config snippet
        server {
            listen 80;
            server_name yourdomain.com;

            location / {
                root /path/to/your/frontend/build;
                try_files $uri /index.html; # For React Router
            }

            location /api/v1/ {
                proxy_pass http://localhost:8000; # Or your Gunicorn socket
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            }
            # Add locations for /static/ and /media/ if Django serves them
        }
        ```
    *   **CDN:** Upload the `frontend/build/` contents to a CDN for fast global delivery. API calls still go to your backend server.
    *   **Django Serving Static Build (Simpler, less performant):** Configure Django to serve the `index.html` from the React build and route all other non-API calls to it. Static assets from the build would be collected by `collectstatic`.

## 4. Celery Worker & Broker Deployment

*   **Celery Workers:**
    *   Run Celery worker processes on the server(s).
        ```bash
        # Example command (managed by systemd, supervisord, or platform's process manager)
        celery -A webapp_project worker -l info --concurrency=4
        ```
    *   Ensure workers have access to the same codebase and environment variables as the Django app.
*   **Message Broker (Redis/RabbitMQ):**
    *   Use a managed Redis or RabbitMQ service in production (e.g., Heroku Redis, AWS ElastiCache, Google Memorystore, CloudAMQP).
    *   Configure `CELERY_BROKER_URL` in Django settings.
*   **Result Backend:**
    *   Configure `CELERY_RESULT_BACKEND` similarly. Using `django-celery-results` can store results in the Django database, which is convenient.
*   **Monitoring:**
    *   **Flower:** A web-based tool for monitoring Celery tasks and workers.
        ```bash
        celery -A webapp_project flower --port=5555
        ```
        This would typically run as a separate process and might need to be behind auth.

## 5. Domain & HTTPS

*   **Custom Domain:** Configure DNS records for your domain to point to your hosting platform/server IP.
*   **HTTPS:** Essential for security.
    *   Use Let's Encrypt for free SSL/TLS certificates.
    *   Most PaaS platforms offer automated SSL certificate provisioning.
    *   If using Nginx/Apache, configure them to handle SSL termination.

## 6. Example Files (Conceptual)

*   **`Dockerfile` (for backend `webapp/`)**
    ```dockerfile
    # Dockerfile (example for Django backend)
    FROM python:3.11-slim
    ENV PYTHONUNBUFFERED 1
    WORKDIR /app
    COPY webapp/requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    # If pipeline is a local package, copy it too and install
    # COPY podcast_to_reels /app/podcast_to_reels
    # RUN pip install -e ./podcast_to_reels
    COPY webapp /app/webapp
    # COPY scripts /app/scripts # If Celery task calls scripts directly
    # COPY lid.176.bin /app/lid.176.bin # If FastText model is used

    # Add user, collectstatic, etc.
    # CMD [ "gunicorn", "webapp_project.wsgi", "--bind", "0.0.0.0:8000" ]
    ```
*   **`Dockerfile.frontend` (for `frontend/`)**
    ```dockerfile
    # Dockerfile.frontend (example for React frontend - multi-stage build)
    # Build stage
    FROM node:18 as build
    WORKDIR /app
    COPY frontend/package.json frontend/yarn.lock ./
    # Use yarn if yarn.lock exists, else npm
    RUN yarn install --frozen-lockfile
    COPY frontend /app/frontend
    RUN yarn --cwd frontend build

    # Production stage (serve with Nginx)
    FROM nginx:alpine
    COPY --from=build /app/frontend/build /usr/share/nginx/html
    # COPY nginx.conf /etc/nginx/conf.d/default.conf # If custom Nginx config needed
    EXPOSE 80
    CMD ["nginx", "-g", "daemon off;"]
    ```
*   **`docker-compose.yml` (Example)**
    ```yaml
    # docker-compose.yml (example)
    version: '3.8'
    services:
      db:
        image: postgres:15
        volumes:
          - postgres_data:/var/lib/postgresql/data/
        environment:
          - POSTGRES_DB=yourdb
          # ...
      redis:
        image: redis:alpine

      web: # Django app
        build:
          context: .
          dockerfile: Dockerfile # Assumes Dockerfile is for webapp
        # command: gunicorn webapp_project.wsgi ...
        volumes:
          - ./webapp:/app/webapp # For dev, or remove for prod build
        ports:
          - "8000:8000"
        depends_on:
          - db
          - redis
        environment:
          - DATABASE_URL=postgres://...
          - CELERY_BROKER_URL=redis://redis:6379/0
          # ... other env vars

      frontend: # React app served by Nginx
        build:
          context: .
          dockerfile: Dockerfile.frontend
        ports:
          - "80:80" # Or 3000:80 if Nginx listens on 80 internally
        # depends_on: # Not strictly, as it calls API of 'web'
        #   - web

      worker: # Celery worker
        build:
          context: .
          dockerfile: Dockerfile # Same image as web, or dedicated if needed
        # command: celery -A webapp_project worker -l info
        depends_on:
          - db
          - redis
        environment:
          # ... same env vars as web
    volumes:
      postgres_data:
    ```

## 7. CI/CD Pipeline for Deployment

Extend the existing `.github/workflows/webapp-ci.yml` (or create a new `deploy.yml`):
*   **Trigger:** On push to `main` branch (or specific tags like `v*.*.*`).
*   **Steps:**
    1.  Checkout code.
    2.  Set up Python, Node.js.
    3.  Run linters and tests (backend & frontend).
    4.  Build React frontend static assets.
    5.  (If using Docker) Build Docker images for backend & frontend.
    6.  Push Docker images to a container registry (e.g., Docker Hub, AWS ECR, Google Artifact Registry).
    7.  Deploy to chosen platform:
        *   **Heroku:** `git push heroku main` or use Heroku CLI commands.
        *   **Docker on VM:** SSH to server, pull new images, `docker-compose up -d --build`.
        *   **Kubernetes:** `kubectl apply -f kubernetes-manifests/`.
        *   **PaaS specific CLI commands.**
    8.  Run database migrations (if applicable, often a step after deploying new code but before routing traffic).
    9.  Health checks.

This outline provides a starting point. Actual deployment can be complex and platform-specific.


## 8. Post-Deployment: Monitoring & Iteration

Once the application is deployed, ongoing monitoring and iteration are crucial for stability, performance, and user satisfaction.

### 8.1. Application Performance Monitoring (APM)

*   **Goal:** Identify and diagnose errors and performance bottlenecks in both backend and frontend code.
*   **Tools:**
    *   **Sentry:** Excellent for error tracking (Python/Django, JavaScript/React, Celery) and basic performance monitoring. Easy to integrate.
    *   **New Relic, Datadog, Dynatrace:** More comprehensive APM suites, often with infrastructure monitoring included. Can be more expensive.
*   **Key Metrics to Track:**
    *   **Backend (Django/Celery):** API error rates (5xx, 4xx), request latency (p50, p90, p99), Celery task failure rates, task execution times, database query times.
    *   **Frontend (React):** JavaScript error rates, page load times (LCP, FCP), interaction delays (FID), API call latencies from client-side.

### 8.2. Centralized Logging

*   **Goal:** Aggregate logs from all components (Django, Gunicorn, Nginx, Celery, React client-side if needed) for easier debugging and analysis.
*   **Tools:**
    *   **ELK Stack (Elasticsearch, Logstash, Kibana):** Powerful, open-source, but can be complex to manage.
    *   **Grafana Loki with Promtail:** Simpler, modern log aggregation, integrates well with Grafana.
    *   **Cloud-based services:** Papertrail, Loggly, Datadog Logs, AWS CloudWatch Logs.
*   **Best Practices:**
    *   Use structured logging (e.g., JSON format).
    *   Include context in logs (user ID, request ID, task ID).
    *   Set appropriate log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL).

### 8.3. Infrastructure Monitoring

*   **Goal:** Ensure the underlying servers, databases, and services are healthy and performant.
*   **Tools:**
    *   **Prometheus & Grafana:** Popular open-source solution for metrics collection and visualization.
    *   **Cloud Provider Tools:** AWS CloudWatch, Google Cloud Monitoring, Azure Monitor. These often provide good default metrics for managed services.
    *   **Netdata:** Real-time, per-second monitoring for systems.
*   **Key Metrics:**
    *   **Server:** CPU utilization, memory usage, disk I/O, disk space, network traffic.
    *   **Database:** Connection counts, query throughput, replication lag (if applicable), resource utilization.
    *   **Message Broker (Redis/RabbitMQ):** Queue lengths, memory usage, connection counts.

### 8.4. Uptime Monitoring

*   **Goal:** Get alerted immediately if the application becomes inaccessible to users.
*   **Tools:**
    *   **UptimeRobot:** Free and paid plans for HTTP(s) checks, keyword checks, ping checks.
    *   **Pingdom, StatusCake, Better Uptime:** Commercial alternatives with more features.
*   **Setup:** Configure checks for key endpoints (e.g., homepage, API health check endpoint).

### 8.5. User Analytics

*   **Goal:** Understand how users interact with the application, identify popular features, drop-off points, and inform product decisions.
*   **Tools:**
    *   **Google Analytics (GA4):** Widely used, free, good for traffic analysis and basic event tracking.
    *   **Mixpanel, Amplitude:** Product analytics tools focused on event-based tracking and user funnels.
    *   **PostHog:** Open-source product analytics suite, can be self-hosted.
    *   **Hotjar, Clarity:** For heatmaps, session recordings to understand user behavior qualitatively.
*   **Key Metrics:** Page views, active users (DAU/MAU), feature adoption rates, user journey funnels (e.g., from landing page to job submission, to customization, to video completion), bounce rates.

### 8.6. Feedback Collection

*   **Goal:** Provide channels for users to report issues, ask questions, and suggest improvements.
*   **Methods:**
    *   **Feedback Form:** A simple form on the website (e.g., linked in the footer).
    *   **Support Email:** A dedicated email address for support queries.
    *   **In-app Widgets:** Tools like Intercom, Crisp, or UserVoice for chat or feedback boards.
    *   **Community Forums/Discord:** If a community grows around the app.

### 8.7. Iteration Process & Cycle

*   **Review:** Regularly (e.g., weekly or bi-weekly) review data from monitoring tools, analytics, and user feedback.
*   **Prioritize:**
    *   Critical bugs and performance issues first.
    *   High-impact features or improvements based on user needs and business goals.
*   **Backlog Management:** Maintain a product backlog (e.g., using Jira, Trello, Asana, GitHub Issues).
*   **Development Sprints/Cycles:** Plan development work in manageable iterations (e.g., 1-2 week sprints).
*   **Testing:** Ensure new features and fixes are thoroughly tested before release (regression tests are vital).
*   **Release Management:** Have a clear process for deploying updates (blue/green deployments, canary releases if applicable for larger systems).
*   **Communication:** Inform users about significant updates, new features, or planned downtime (e.g., via in-app notifications, email newsletter, blog).
*   **Documentation:** Keep user documentation and internal technical documentation up-to-date.

Continuous monitoring and iteration are key to the long-term success and health of any web application.
