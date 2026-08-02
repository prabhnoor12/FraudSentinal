import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'fs-docs-page',
  imports: [RouterLink],
  template: `
    <section class="fs-docs-shell">
      <header class="fs-docs-masthead">
        <div class="fs-docs-brand">
          <a class="fs-docs-home" routerLink="/">FraudSentinal</a>
          <span class="fs-docs-badge">Documentation</span>
        </div>
        <a class="fs-docs-exit fs-docs-exit--desktop" routerLink="/dashboard">Back to dashboard</a>
      </header>

      <div class="fs-page fs-docs">
        <div class="fs-page-header">
          <p class="fs-kicker">Docs</p>
          <h1>Getting started with FraudSentinal</h1>
          <p class="fs-muted">
            A concise guide for new teammates, implementers, and product integrators.
          </p>
        </div>

        <nav class="fs-docs-toc" aria-label="Documentation sections">
          <a href="#overview">Overview</a>
          <a href="#integration">Integration</a>
          <a href="#api-reference">API reference</a>
          <a href="#workflow">Workflow</a>
          <a href="#auth">Authentication</a>
        </nav>

        <div class="fs-grid">
          <article class="fs-card" id="overview">
            <div class="fs-card-header">
              <h2>Purpose</h2>
            </div>
            <p>
              FraudSentinal is a multi-tenant fraud detection and operations platform. It scores
              transactions, records decisions, opens review cases, tracks usage and billing, and
              preserves an audit trail for every important action.
            </p>
            <p>
              The frontend is an Angular client that consumes the backend REST API under <code>/api/v1</code>.
            </p>
          </article>

          <article class="fs-card">
            <div class="fs-card-header">
              <h2>What to expect</h2>
            </div>
            <ul class="fs-checklist">
              <li>Public landing and docs pages for discovery and onboarding.</li>
              <li>Protected dashboards and workflow pages for day-to-day operations.</li>
              <li>A stable REST API with tenant-aware resource boundaries.</li>
              <li>Structured audit, metrics, and request tracing across actions.</li>
            </ul>
          </article>
        </div>

        <div class="fs-grid">
          <article class="fs-card">
            <div class="fs-card-header">
              <h2>Quick start</h2>
            </div>
            <ol class="fs-ordered-list">
              <li>Run the backend and frontend locally.</li>
              <li>Open <code>/</code> to read the landing page and <code>/docs</code> for guidance.</li>
              <li>Create a tenant account from <code>/login/sign-up</code>.</li>
              <li>Complete a fraud check from the dashboard or API client.</li>
              <li>Review the resulting decision and review case workflow.</li>
            </ol>
          </article>

          <article class="fs-card">
            <div class="fs-card-header">
              <h2>Docs focus</h2>
            </div>
            <p class="fs-muted">
              This documentation area is intentionally separate from the application workspace so
              readers can stay focused on implementation guidance without being dropped into the
              dashboard flow.
            </p>
            <p class="fs-muted">
              When you are ready to return to operations, use the dashboard link in the page
              footer.
            </p>
          </article>
        </div>

        <div class="fs-grid">
        <article class="fs-card" id="integration">
          <div class="fs-card-header">
            <h2>Integration steps</h2>
          </div>
          <ol class="fs-ordered-list">
            <li>Set the frontend API base URL to the backend host plus <code>/api/v1</code>.</li>
            <li>Authenticate with bearer tokens for analysts or service-account keys for machines.</li>
            <li>Keep the <code>organisation_id</code> from the authenticated session and reuse it for tenant-bound flows.</li>
            <li>Send <code>Idempotency-Key</code> on writes that may be retried.</li>
            <li>Use the returned <code>X-Request-ID</code> when tracing issues across logs and support.</li>
          </ol>
        </article>

        <article class="fs-card">
          <div class="fs-card-header">
            <h2>Core workflows</h2>
          </div>
          <ul class="fs-checklist">
            <li>Fraud check: submit a transaction, receive a decision, and inspect reason codes.</li>
            <li>Review queue: investigate cases that require analyst review.</li>
            <li>Rules management: create, edit, enable, and disable fraud rules safely.</li>
            <li>Audit and billing: trace usage, entitlements, and compliance activity.</li>
          </ul>
        </article>
        </div>

        <div class="fs-grid">
        <article class="fs-card" id="api-reference">
          <div class="fs-card-header">
            <h2>Backend contract highlights</h2>
          </div>
          <div class="fs-info-grid">
            <div class="fs-stat-card">
              <span class="fs-stat-label">Auth</span>
              <strong>Bearer tokens and service-account API keys</strong>
            </div>
            <div class="fs-stat-card">
              <span class="fs-stat-label">Writes</span>
              <strong>Idempotent and traceable</strong>
            </div>
            <div class="fs-stat-card">
              <span class="fs-stat-label">Multi-tenancy</span>
              <strong>Organisation-scoped reads and writes</strong>
            </div>
            <div class="fs-stat-card">
              <span class="fs-stat-label">Observability</span>
              <strong>Request IDs, audit logs, metrics</strong>
            </div>
          </div>
        </article>

        <article class="fs-card">
          <div class="fs-card-header">
            <h2>Troubleshooting</h2>
          </div>
          <ul class="fs-checklist">
            <li>If a request fails with <code>401</code>, re-authenticate and confirm the token is present.</li>
            <li>If a tenant resource appears missing, confirm the session belongs to that organisation.</li>
            <li>If a write is retried, keep the same <code>Idempotency-Key</code>.</li>
            <li>If logs are hard to trace, copy the <code>X-Request-ID</code> into your support note.</li>
          </ul>
        </article>
        </div>

        <article class="fs-card">
        <div class="fs-card-header">
          <h2>Common API calls</h2>
          <p class="fs-muted">
            A short reference for the requests new integrators usually need first. These match
            the current frontend API client.
          </p>
        </div>
        <div class="fs-table-wrap">
          <table class="fs-table fs-doc-table">
            <thead>
              <tr>
                <th>Goal</th>
                <th>Method</th>
                <th>Path</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td data-label="Goal">Sign in</td>
                <td data-label="Method">POST</td>
                <td data-label="Path"><code>/api/v1/auth/login</code></td>
                <td data-label="Notes">Returns access and refresh tokens.</td>
              </tr>
              <tr>
                <td data-label="Goal">Register</td>
                <td data-label="Method">POST</td>
                <td data-label="Path"><code>/api/v1/auth/register</code></td>
                <td data-label="Notes">Creates a user and organisation shell.</td>
              </tr>
              <tr>
                <td data-label="Goal">Refresh session</td>
                <td data-label="Method">POST</td>
                <td data-label="Path"><code>/api/v1/auth/refresh</code></td>
                <td data-label="Notes">Uses the refresh token to renew access.</td>
              </tr>
              <tr>
                <td data-label="Goal">Sign out</td>
                <td data-label="Method">POST</td>
                <td data-label="Path"><code>/api/v1/auth/logout</code></td>
                <td data-label="Notes">Clears session state and tokens.</td>
              </tr>
              <tr>
                <td data-label="Goal">Current user</td>
                <td data-label="Method">GET</td>
                <td data-label="Path"><code>/api/v1/auth/me</code></td>
                <td data-label="Notes">Returns the authenticated user profile.</td>
              </tr>
              <tr>
                <td data-label="Goal">Run fraud check</td>
                <td data-label="Method">POST</td>
                <td data-label="Path"><code>/api/v1/check-fraud</code></td>
                <td data-label="Notes">Use <code>Idempotency-Key</code> for safe retries.</td>
              </tr>
              <tr>
                <td data-label="Goal">My review queue</td>
                <td data-label="Method">GET</td>
                <td data-label="Path"><code>/api/v1/review-cases/queue/my</code></td>
                <td data-label="Notes">Shows analyst work items assigned to the current user.</td>
              </tr>
              <tr>
                <td data-label="Goal">Review cases</td>
                <td data-label="Method">GET</td>
                <td data-label="Path"><code>/api/v1/review-cases</code></td>
                <td data-label="Notes">Filters by status, decision, or transaction.</td>
              </tr>
              <tr>
                <td data-label="Goal">Audit trail</td>
                <td data-label="Method">GET</td>
                <td data-label="Path"><code>/api/v1/audit</code></td>
                <td data-label="Notes">Useful for debugging and compliance.</td>
              </tr>
              <tr>
                <td data-label="Goal">Usage summary</td>
                <td data-label="Method">GET</td>
                <td data-label="Path"><code>/api/v1/usage/summaries</code></td>
                <td data-label="Notes">Provides usage rollups for billing and analytics.</td>
              </tr>
              <tr>
                <td data-label="Goal">Fraud rules</td>
                <td data-label="Method">GET/POST/PUT</td>
                <td data-label="Path"><code>/api/v1/fraud-rules</code></td>
                <td data-label="Notes">List, create, update, enable, or disable rules.</td>
              </tr>
              <tr>
                <td data-label="Goal">Billing records</td>
                <td data-label="Method">GET</td>
                <td data-label="Path"><code>/api/v1/billing/records</code></td>
                <td data-label="Notes">Tracks usage and subscription activity.</td>
              </tr>
            </tbody>
          </table>
        </div>
        </article>

        <div class="fs-grid">
        <article class="fs-card" id="workflow">
          <div class="fs-card-header">
            <h2>Suggested integration flow</h2>
          </div>
          <div class="fs-flow">
            <div class="fs-flow-step">
              <span class="fs-flow-index">1</span>
              <div>
                <strong>Authenticate</strong>
                <p>Sign in as a user or service account and store the issued tokens securely.</p>
              </div>
            </div>
            <div class="fs-flow-step">
              <span class="fs-flow-index">2</span>
              <div>
                <strong>Resolve tenant</strong>
                <p>Use the authenticated organisation scope for all subsequent requests.</p>
              </div>
            </div>
            <div class="fs-flow-step">
              <span class="fs-flow-index">3</span>
              <div>
                <strong>Submit fraud check</strong>
                <p>Send transaction details to <code>/api/v1/check-fraud</code> and keep the request ID.</p>
              </div>
            </div>
            <div class="fs-flow-step">
              <span class="fs-flow-index">4</span>
              <div>
                <strong>Handle result</strong>
                <p>Route approved, reviewed, or declined outcomes into your business process.</p>
              </div>
            </div>
            <div class="fs-flow-step">
              <span class="fs-flow-index">5</span>
              <div>
                <strong>Investigate</strong>
                <p>If review is needed, open the review case page and use the audit trail.</p>
              </div>
            </div>
          </div>
        </article>

        <article class="fs-card">
          <div class="fs-card-header">
            <h2>Example payload shape</h2>
            <p class="fs-muted">
              The frontend uses this same shape when sending a fraud check request.
            </p>
          </div>
          <pre class="fs-json">{{
            '{' +
              '\n  "user_id": 123,' +
              '\n  "organisation_id": 456,' +
              '\n  "amount": 99.99,' +
              '\n  "currency": "USD",' +
              '\n  "payment_method": "card",' +
              '\n  "channel": "api",' +
              '\n  "customer_id": "cust_001"' +
              '\n}'
          }}</pre>
        </article>
        </div>

        <article class="fs-card">
        <div class="fs-card-header">
          <h2>Integration checklist</h2>
          <p class="fs-muted">
            Use this when you are wiring a service or a new frontend into FraudSentinal.
          </p>
        </div>
        <div class="fs-info-grid">
          <div class="fs-stat-card">
            <span class="fs-stat-label">1. Base URL</span>
            <strong>Point the client to the backend host plus <code>/api/v1</code>.</strong>
          </div>
          <div class="fs-stat-card">
            <span class="fs-stat-label">2. Auth</span>
            <strong>Store tokens securely and send them on protected requests.</strong>
          </div>
          <div class="fs-stat-card">
            <span class="fs-stat-label">3. Tenant scope</span>
            <strong>Keep requests scoped to the authenticated organisation.</strong>
          </div>
          <div class="fs-stat-card">
            <span class="fs-stat-label">4. Retries</span>
            <strong>Reuse the same idempotency key for retry-safe writes.</strong>
          </div>
        </div>
        </article>

        <div class="fs-grid">
        <article class="fs-card" id="auth">
          <div class="fs-card-header">
            <h2>Authentication and tenants</h2>
          </div>
          <ul class="fs-checklist">
            <li>Use <code>/api/v1/auth/login</code> to establish a session and persist both tokens.</li>
            <li>Call <code>/api/v1/auth/me</code> after login to confirm the active user and organisation.</li>
            <li>Keep every tenant-bound request scoped to the authenticated organisation.</li>
            <li>Prefer service accounts for machine-to-machine flows and analyst tokens for UI access.</li>
          </ul>
        </article>

        <article class="fs-card">
          <div class="fs-card-header">
            <h2>Error handling</h2>
          </div>
          <ul class="fs-checklist">
            <li>Expect <code>401</code> when a token expires or is missing.</li>
            <li>Expect <code>403</code> when the token is valid but lacks permission.</li>
            <li>Expect <code>404</code> when a tenant-scoped resource does not belong to the active organisation.</li>
            <li>Keep <code>Idempotency-Key</code> stable across retries for write operations.</li>
          </ul>
        </article>
        </div>

        <article class="fs-card">
        <div class="fs-card-header">
          <h2>Request and response examples</h2>
          <p class="fs-muted">
            These are the patterns new integrations usually need first.
          </p>
        </div>
        <div class="fs-example-grid">
          <article class="fs-example-card">
            <div class="fs-card-header">
              <h3>Sign in</h3>
              <p class="fs-muted"><code>POST /api/v1/auth/login</code></p>
            </div>
            <div class="fs-example-block">
              <span class="fs-example-label">Request</span>
              <pre class="fs-json">{{ loginRequestExample }}</pre>
            </div>
            <div class="fs-example-block">
              <span class="fs-example-label">Response</span>
              <pre class="fs-json">{{ loginResponseExample }}</pre>
            </div>
          </article>

          <article class="fs-example-card">
            <div class="fs-card-header">
              <h3>Current user</h3>
              <p class="fs-muted"><code>GET /api/v1/auth/me</code></p>
            </div>
            <div class="fs-example-block">
              <span class="fs-example-label">Response</span>
              <pre class="fs-json">{{ meResponseExample }}</pre>
            </div>
          </article>

          <article class="fs-example-card">
            <div class="fs-card-header">
              <h3>Review queue</h3>
              <p class="fs-muted"><code>GET /api/v1/review-cases?status=open&limit=20</code></p>
            </div>
            <div class="fs-example-block">
              <span class="fs-example-label">Response</span>
              <pre class="fs-json">{{ reviewCasesResponseExample }}</pre>
            </div>
          </article>

          <article class="fs-example-card">
            <div class="fs-card-header">
              <h3>Common error</h3>
              <p class="fs-muted">Use this shape as a baseline for client-side handling.</p>
            </div>
            <div class="fs-example-block">
              <span class="fs-example-label">Response</span>
              <pre class="fs-json">{{ errorResponseExample }}</pre>
            </div>
          </article>
        </div>
        </article>
      </div>

      <footer class="fs-docs-footer">
        <div>
          <strong>Finished reading?</strong>
          <p class="fs-muted">Jump back into the product workspace when you are ready.</p>
        </div>
        <div class="fs-docs-footer-actions">
          <a class="fs-docs-exit" routerLink="/dashboard">Go to dashboard</a>
          <a class="fs-docs-secondary" routerLink="/">Back to landing</a>
        </div>
      </footer>
    </section>
  `,
  styleUrl: './docs.page.scss',
})
export class DocsPage {
  protected readonly loginRequestExample = `{
  "email": "analyst@example.com",
  "password": "********"
}`;

  protected readonly loginResponseExample = `{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer"
}`;

  protected readonly meResponseExample = `{
  "id": 17,
  "organisation_id": 456,
  "email": "analyst@example.com",
  "full_name": "Analyst One",
  "is_active": true,
  "created_at": "2026-08-01T10:00:00Z"
}`;

  protected readonly reviewCasesResponseExample = `[
  {
    "id": 101,
    "transaction_id": 9001,
    "decision_id": 7001,
    "status": "open",
    "created_at": "2026-08-01T10:00:00Z"
  }
]`;

  protected readonly errorResponseExample = `{
  "status": 401,
  "message": "Authentication required"
}`;
}
