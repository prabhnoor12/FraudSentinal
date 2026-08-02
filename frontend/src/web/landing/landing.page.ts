import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'fs-landing-page',
  standalone: true,
  imports: [RouterLink],
  template: `
    <section class="fs-landing">
      <main class="fs-landing-hero">
        <header class="fs-landing-copy">
          <p class="fs-landing-kicker">FraudSentinal</p>
          <h1>Stop fraud faster without turning your team into a manual review queue.</h1>
          <p class="fs-landing-lead">
            FraudSentinal gives SaaS teams a single place to score transactions, explain
            decisions, route risky cases into review, and keep every action tenant-scoped under a
            versioned <code>/api/v1</code> contract.
          </p>
          <p class="fs-landing-actions">
            <a class="fs-button" routerLink="/login/sign-up">Start free</a>
            <a class="fs-button is-secondary" routerLink="/docs">Read docs</a>
          </p>
          <div class="fs-landing-metrics">
            <div class="fs-metric-card">
              <span class="fs-metric-label">Signals</span>
              <strong>Real-time scoring</strong>
            </div>
            <div class="fs-metric-card">
              <span class="fs-metric-label">Workflows</span>
              <strong>Review-ready queues</strong>
            </div>
            <div class="fs-metric-card">
              <span class="fs-metric-label">Trust</span>
              <strong>Tenant-safe decisions</strong>
            </div>
          </div>
        </header>

        <aside class="fs-landing-panel">
          <div class="fs-proof-card">
            <p class="fs-panel-kicker">Live decision snapshot</p>
            <div class="fs-proof-score">
              <span class="fs-proof-label">Risk score</span>
              <strong>0.91</strong>
              <span class="fs-proof-badge">Escalate to analyst</span>
            </div>
            <div class="fs-proof-flow">
              <div class="fs-proof-step">
                <strong>Velocity spike detected</strong>
                <p>7 checkout attempts in 9 minutes across 2 devices.</p>
              </div>
              <div class="fs-proof-step">
                <strong>Decision explained</strong>
                <p>Reason codes and scoring context stay visible to operators.</p>
              </div>
              <div class="fs-proof-step">
                <strong>Case routed instantly</strong>
                <p>Analysts get a queue item instead of digging through logs.</p>
              </div>
            </div>
          </div>

          <div class="fs-panel-card">
            <h2>Why SaaS teams switch</h2>
            <div class="fs-panel-list">
              <div class="fs-panel-list-item">
                <strong>Explain decisions clearly</strong>
                <p>Use reason codes and risk signals to justify outcomes.</p>
              </div>
              <div class="fs-panel-list-item">
                <strong>Keep tenant boundaries clean</strong>
                <p>Every read and write stays scoped to the correct organisation.</p>
              </div>
              <div class="fs-panel-list-item">
                <strong>Move from signal to action</strong>
                <p>Fraud checks, review cases, billing, and audit all connect in one workflow.</p>
              </div>
            </div>
          </div>
        </aside>
      </main>

      <section class="fs-trust-strip">
        <div class="fs-trust-card">
          <strong>Tenant-safe</strong>
          <p>Every request stays scoped to the active organisation.</p>
        </div>
        <div class="fs-trust-card">
          <strong>Versioned API</strong>
          <p>Built around a stable <code>/api/v1</code> contract for integrations.</p>
        </div>
        <div class="fs-trust-card">
          <strong>Operator-ready</strong>
          <p>Review cases, metrics, and audit trails are part of the product.</p>
        </div>
      </section>

      <section class="fs-feature-grid">
        <article class="fs-feature-section">
          <h2>What the platform does</h2>
          <div class="fs-feature-cards">
            <div class="fs-feature-card">
              <strong>Ship faster</strong>
              <p>Launch fraud controls without building a separate operations stack.</p>
            </div>
            <div class="fs-feature-card">
              <strong>Score</strong>
              <p>Evaluate transactions in real time with layered fraud signals.</p>
            </div>
            <div class="fs-feature-card">
              <strong>Review</strong>
              <p>Route edge cases into a queue your analysts can manage.</p>
            </div>
            <div class="fs-feature-card">
              <strong>Explain</strong>
              <p>See why a decision was made instead of guessing after the fact.</p>
            </div>
            <div class="fs-feature-card">
              <strong>Operate</strong>
              <p>Track usage, billing, and audit history alongside the core workflow.</p>
            </div>
          </div>
        </article>

        <article class="fs-process-section">
          <h2>How teams use it</h2>
          <div class="fs-process-steps">
            <div class="fs-process-step">
              <strong>1. Connect your app</strong>
              <p>Point your SaaS backend at <code>/api/v1</code> and start sending events.</p>
            </div>
            <div class="fs-process-step">
              <strong>2. Score and classify</strong>
              <p>Let the engine approve, flag, or decline based on risk and rules.</p>
            </div>
            <div class="fs-process-step">
              <strong>3. Review and audit</strong>
              <p>Use cases, metrics, and logs to resolve exceptions with confidence.</p>
            </div>
          </div>
        </article>
      </section>

      <article class="fs-cta-banner">
        <div class="fs-cta-copy">
          <p class="fs-landing-kicker">Ready to launch</p>
          <h2>Put fraud control into your SaaS flow without adding operational clutter.</h2>
          <p>
            Start with the dashboard, connect the API, and keep the full customer and analyst loop
            inside one versioned platform.
          </p>
        </div>
        <p class="fs-landing-actions">
          <a class="fs-button" routerLink="/login/sign-up">Start free</a>
          <a class="fs-button is-secondary" routerLink="/docs">See the docs</a>
        </p>
      </article>
    </section>
  `,
  styleUrl: './landing.page.scss',
})
export class LandingPage {}
