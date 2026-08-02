import { Component } from '@angular/core';

@Component({
  selector: 'fs-billing-page',
  template: `
    <section class="fs-page">
      <div class="fs-page-header">
        <h1>Billing</h1>
        <p class="fs-muted">Manage billing plans, payment methods, invoices, and account readiness.</p>
      </div>

      <div class="fs-summary-grid">
        <div class="fs-summary-card">
          <span class="fs-summary-label">Plan status</span>
          <strong>Integration pending</strong>
        </div>
        <div class="fs-summary-card">
          <span class="fs-summary-label">Payment methods</span>
          <strong>Not connected</strong>
        </div>
        <div class="fs-summary-card">
          <span class="fs-summary-label">Invoices</span>
          <strong>Awaiting backend</strong>
        </div>
      </div>

      <div class="fs-dashboard-grid">
        <div class="fs-card">
          <div class="fs-card-header">
            <span class="fs-eyebrow">Billing readiness</span>
            <h2>Integration Status</h2>
            <p class="fs-muted">This surface is styled and ready for live data once billing endpoints are connected.</p>
          </div>

          <div class="fs-alert is-info">
            Billing endpoints are not wired on the backend yet. This page is ready for integration.
          </div>

          <div class="fs-readiness-list">
            <div class="fs-readiness-item">
              <span class="fs-meta-label">Customer plans</span>
              <strong>UI prepared for plan tiers, renewals, and entitlements.</strong>
            </div>
            <div class="fs-readiness-item">
              <span class="fs-meta-label">Payment methods</span>
              <strong>Space reserved for saved cards, bank accounts, and default billing method.</strong>
            </div>
            <div class="fs-readiness-item">
              <span class="fs-meta-label">Invoices</span>
              <strong>Ready for invoice history, downloadable receipts, and billing cycle details.</strong>
            </div>
          </div>
        </div>

        <div class="fs-card">
          <div class="fs-card-header">
            <span class="fs-eyebrow">Planned modules</span>
            <h2>What will live here</h2>
          </div>

          <div class="fs-stack">
            <div class="fs-module-card">
              <div class="fs-list-title">Subscription overview</div>
              <div class="fs-list-meta">Current plan, limits, renewal date, and billing owner details.</div>
            </div>
            <div class="fs-module-card">
              <div class="fs-list-title">Payment methods</div>
              <div class="fs-list-meta">Saved methods, fallback method, and secure update actions.</div>
            </div>
            <div class="fs-module-card">
              <div class="fs-list-title">Invoice history</div>
              <div class="fs-list-meta">Invoice status, amount, due date, and downloadable documents.</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  `,
  styleUrl: './billing.page.scss',
})
export class BillingPage {}
