import { Component } from '@angular/core';

@Component({
  selector: 'fs-billing-page',
  template: `
    <section class="fs-page">
      <div class="fs-page-header">
        <h1>Billing</h1>
        <p class="fs-muted">Manage billing plans, payment methods, and invoices.</p>
      </div>

      <div class="fs-card">
        <div class="fs-alert is-info">
          Billing endpoints are not wired on the backend yet. This page is ready for integration.
        </div>
      </div>
    </section>
  `,
})
export class BillingPage {}

