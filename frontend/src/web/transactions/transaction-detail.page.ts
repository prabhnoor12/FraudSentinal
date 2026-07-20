import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ApiError, Decision, RiskSignal, Transaction, api } from '../api';

@Component({
  selector: 'fs-transaction-detail-page',
  imports: [RouterLink],
  template: `
    <section class="fs-page">
      <div class="fs-page-header">
        <a class="fs-back-link" routerLink="/review-cases">← Back to Review Cases</a>
        <h1>Transaction Detail</h1>
        <p class="fs-muted">Review the transaction record, fraud decision, and supporting signals.</p>
      </div>

      @if (loading()) {
        <div class="fs-card">
          <div class="fs-skeleton">Loading transaction context…</div>
        </div>
      } @else if (error()) {
        <div class="fs-card">
          <div class="fs-alert is-error">{{ error() }}</div>
        </div>
      } @else if (transaction()) {
        <div class="fs-detail-grid">
          <div class="fs-stat-card">
            <span class="fs-stat-label">Transaction</span>
            <strong>#{{ transaction()!.id }}</strong>
          </div>
          <div class="fs-stat-card">
            <span class="fs-stat-label">Amount</span>
            <strong>{{ transaction()!.amount }} {{ transaction()!.currency }}</strong>
          </div>
          <div class="fs-stat-card">
            <span class="fs-stat-label">Payment Method</span>
            <strong>{{ transaction()!.payment_method }}</strong>
          </div>
          <div class="fs-stat-card">
            <span class="fs-stat-label">Channel</span>
            <strong>{{ transaction()!.channel }}</strong>
          </div>
          <div class="fs-stat-card">
            <span class="fs-stat-label">Customer</span>
            <strong>{{ transaction()!.customer_email || transaction()!.customer_id || 'unknown' }}</strong>
          </div>
          <div class="fs-stat-card">
            <span class="fs-stat-label">Created</span>
            <strong>{{ transaction()!.created_at }}</strong>
          </div>
        </div>

        <div class="fs-grid">
          <div class="fs-card">
            <div class="fs-card-header">
              <h2>Transaction Context</h2>
            </div>
            <div class="fs-info-grid">
              <div><span class="fs-stat-label">External ID</span><div>{{ transaction()!.external_transaction_id || 'n/a' }}</div></div>
              <div><span class="fs-stat-label">IP Address</span><div>{{ transaction()!.ip_address || 'n/a' }}</div></div>
              <div><span class="fs-stat-label">Device ID</span><div>{{ transaction()!.device_id || 'n/a' }}</div></div>
              <div><span class="fs-stat-label">Account Age</span><div>{{ transaction()!.account_age_days ?? 'n/a' }}</div></div>
              <div><span class="fs-stat-label">Billing Country</span><div>{{ transaction()!.billing_country || 'n/a' }}</div></div>
              <div><span class="fs-stat-label">Shipping Country</span><div>{{ transaction()!.shipping_country || 'n/a' }}</div></div>
              <div><span class="fs-stat-label">Tx Last 24h</span><div>{{ transaction()!.transactions_last_24h }}</div></div>
              <div><span class="fs-stat-label">Failed Attempts</span><div>{{ transaction()!.failed_attempts_last_24h }}</div></div>
            </div>
          </div>

          <div class="fs-card">
            <div class="fs-card-header">
              <h2>Fraud Decision</h2>
            </div>

            @if (decisions().length === 0) {
              <div class="fs-muted">No decision found for this transaction.</div>
            } @else {
              @for (decision of decisions(); track decision.id) {
                <div class="fs-card fs-card-subtle">
                  <div class="fs-detail-grid">
                    <div class="fs-stat-card">
                      <span class="fs-stat-label">Decision</span>
                      <strong>{{ decision.decision }}</strong>
                    </div>
                    <div class="fs-stat-card">
                      <span class="fs-stat-label">Risk Score</span>
                      <strong>{{ decision.risk_score }}</strong>
                    </div>
                  </div>
                  <div class="fs-stack">
                    <div>
                      <span class="fs-stat-label">Reason Codes</span>
                      <div class="fs-chip-group fs-chip-group-static">
                        @for (reason of decision.reason_codes; track reason) {
                          <span class="fs-chip is-static">{{ reason }}</span>
                        }
                      </div>
                    </div>
                    <div>
                      <span class="fs-stat-label">Scoring Snapshot</span>
                      <pre class="fs-json">{{ prettyJson(decision.scoring_snapshot) }}</pre>
                    </div>
                  </div>
                </div>
              }
            }
          </div>
        </div>

        <div class="fs-grid">
          <div class="fs-card">
            <div class="fs-card-header">
              <h2>Risk Signals</h2>
            </div>

            @if (riskSignals().length === 0) {
              <div class="fs-muted">No risk signals recorded for this transaction.</div>
            } @else {
              <ul class="fs-list">
                @for (signal of riskSignals(); track signal.id) {
                  <li class="fs-list-item">
                    <div class="fs-list-title">{{ signal.rule_code }} · {{ signal.reason_code }}</div>
                    <div class="fs-list-meta">
                      weight {{ signal.weight }} · decision #{{ signal.decision_id }} · {{ signal.created_at }}
                    </div>
                    <pre class="fs-json">{{ prettyJson(signal.details) }}</pre>
                  </li>
                }
              </ul>
            }
          </div>

          <div class="fs-card">
            <div class="fs-card-header">
              <h2>Metadata</h2>
            </div>
            <pre class="fs-json">{{ metadataPreview() }}</pre>
          </div>
        </div>
      }
    </section>
  `,
})
export class TransactionDetailPage {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly transaction = signal<Transaction | null>(null);
  protected readonly decisions = signal<Decision[]>([]);
  protected readonly riskSignals = signal<RiskSignal[]>([]);
  protected readonly metadataPreview = signal('{}');

  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const transactionId = Number(params.get('transactionId'));
      if (!Number.isFinite(transactionId) || transactionId <= 0) {
        this.error.set('Invalid transaction identifier.');
        this.loading.set(false);
        return;
      }
      void this.load(transactionId);
    });
  }

  protected prettyJson(value: unknown): string {
    return JSON.stringify(value ?? {}, null, 2);
  }

  private async load(transactionId: number): Promise<void> {
    this.loading.set(true);
    this.error.set(null);

    try {
      const [transaction, decisions, riskSignals] = await Promise.all([
        api.transactions.get(transactionId),
        api.decisions.list({ transaction_id: transactionId, limit: 20 }),
        api.riskSignals.list({ transaction_id: transactionId, limit: 100 }),
      ]);

      this.transaction.set(transaction);
      this.decisions.set(decisions);
      this.riskSignals.set(riskSignals);
      this.metadataPreview.set(JSON.stringify(transaction.metadata ?? {}, null, 2));
    } catch (e) {
      const err = e as ApiError;
      this.error.set(err?.message ?? 'Failed to load transaction detail.');
    } finally {
      this.loading.set(false);
    }
  }
}

