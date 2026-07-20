import { Component, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiError, ReviewCase, api } from '../api';

type CaseScope = 'all' | 'open' | 'resolved' | 'my-queue';

const RESOLUTION_OPTIONS = [
  'approved_by_analyst',
  'declined_by_analyst',
  'false_positive',
  'fraud_confirmed',
];

@Component({
  selector: 'fs-review-cases-page',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <section class="fs-page">
      <div class="fs-page-header">
        <h1>Review Cases</h1>
        <p class="fs-muted">Investigate flagged transactions and resolve analyst queues.</p>
      </div>

      <div class="fs-card">
        <div class="fs-toolbar">
          <div class="fs-chip-group">
            @for (scope of scopes; track scope.value) {
              <button
                type="button"
                class="fs-chip"
                [class.is-active]="activeScope() === scope.value"
                (click)="changeScope(scope.value)"
              >
                {{ scope.label }}
              </button>
            }
          </div>
          <button class="fs-button is-secondary" type="button" (click)="reload()" [disabled]="loading()">
            Refresh
          </button>
        </div>
      </div>

      <div class="fs-dashboard-grid">
        <div class="fs-card">
          <div class="fs-card-header">
            <h2>Case Queue</h2>
            <p class="fs-muted">{{ cases().length }} case(s)</p>
          </div>

          @if (loading()) {
            <div class="fs-skeleton">Loading cases…</div>
          } @else if (error()) {
            <div class="fs-alert is-error">{{ error() }}</div>
          } @else if (cases().length === 0) {
            <div class="fs-muted">No cases found for the current filter.</div>
          } @else {
            <ul class="fs-list">
              @for (reviewCase of cases(); track reviewCase.id) {
                <li>
                  <button
                    type="button"
                    class="fs-list-item fs-list-button"
                    [class.is-selected]="selectedCaseId() === reviewCase.id"
                    (click)="selectCase(reviewCase.id)"
                  >
                    <div class="fs-list-title">Case #{{ reviewCase.id }} · Tx {{ reviewCase.transaction_id }}</div>
                    <div class="fs-list-meta">
                      {{ reviewCase.status }} · decision {{ reviewCase.decision_id }} ·
                      {{ reviewCase.updated_at }}
                    </div>
                  </button>
                </li>
              }
            </ul>
          }
        </div>

        <div class="fs-card">
          <div class="fs-card-header">
            <h2>Case Details</h2>
          </div>

          @if (detailLoading()) {
            <div class="fs-skeleton">Loading case details…</div>
          } @else if (detailError()) {
            <div class="fs-alert is-error">{{ detailError() }}</div>
          } @else if (!selectedCase()) {
            <div class="fs-muted">Select a case from the queue to inspect it.</div>
          } @else {
            <div class="fs-detail-grid">
              <div class="fs-stat-card">
                <span class="fs-stat-label">Status</span>
                <strong>{{ selectedCase()!.status }}</strong>
              </div>
              <div class="fs-stat-card">
                <span class="fs-stat-label">Resolution</span>
                <strong>{{ selectedCase()!.resolution_code || 'pending' }}</strong>
              </div>
              <div class="fs-stat-card">
                <span class="fs-stat-label">Transaction</span>
                <strong>#{{ selectedCase()!.transaction_id }}</strong>
              </div>
              <div class="fs-stat-card">
                <span class="fs-stat-label">Decision</span>
                <strong>#{{ selectedCase()!.decision_id }}</strong>
              </div>
            </div>

            <div class="fs-stack">
              <div class="fs-card fs-card-subtle">
                <div class="fs-card-header">
                  <h3>Notes</h3>
                </div>
                <p class="fs-prewrap">{{ selectedCase()!.notes || 'No notes recorded.' }}</p>
              </div>

              <div class="fs-card fs-card-subtle">
                <div class="fs-card-header">
                  <h3>Metadata</h3>
                </div>
                <pre class="fs-json">{{ metadataPreview() }}</pre>
              </div>

              @if (selectedCase()!.status === 'open') {
                <form class="fs-form" [formGroup]="resolveForm" (ngSubmit)="resolveSelectedCase()">
                  <div class="fs-card-header">
                    <h3>Resolve Case</h3>
                  </div>
                  <label class="fs-field">
                    <span>Resolution</span>
                    <select class="fs-input" formControlName="resolution_code">
                      @for (option of resolutionOptions; track option) {
                        <option [value]="option">{{ option }}</option>
                      }
                    </select>
                  </label>
                  <label class="fs-field">
                    <span>Analyst Notes</span>
                    <textarea class="fs-input" rows="4" formControlName="notes"></textarea>
                  </label>
                  <div class="fs-form-actions">
                    <button class="fs-button" type="submit" [disabled]="actionBusy() || resolveForm.invalid">
                      @if (actionBusy()) { Resolving… } @else { Resolve case }
                    </button>
                    <a class="fs-button is-secondary" [routerLink]="['/transactions', selectedCase()!.transaction_id]">
                      Open transaction
                    </a>
                    <a class="fs-button is-secondary" [routerLink]="['/review-cases', selectedCase()!.id]">
                      Open detail page
                    </a>
                  </div>
                </form>
              } @else {
                <form class="fs-form" [formGroup]="reopenForm" (ngSubmit)="reopenSelectedCase()">
                  <div class="fs-card-header">
                    <h3>Reopen Case</h3>
                  </div>
                  <label class="fs-field">
                    <span>Reason</span>
                    <textarea class="fs-input" rows="4" formControlName="reason"></textarea>
                  </label>
                  <div class="fs-form-actions">
                    <button class="fs-button" type="submit" [disabled]="actionBusy() || reopenForm.invalid">
                      @if (actionBusy()) { Reopening… } @else { Reopen case }
                    </button>
                    <a class="fs-button is-secondary" [routerLink]="['/transactions', selectedCase()!.transaction_id]">
                      Open transaction
                    </a>
                    <a class="fs-button is-secondary" [routerLink]="['/review-cases', selectedCase()!.id]">
                      Open detail page
                    </a>
                  </div>
                </form>
              }
            </div>
          }
        </div>
      </div>
    </section>
  `,
})
export class ReviewCasesPage {
  private readonly fb = new FormBuilder();

  protected readonly scopes = [
    { value: 'all' as CaseScope, label: 'All Cases' },
    { value: 'open' as CaseScope, label: 'Open' },
    { value: 'resolved' as CaseScope, label: 'Resolved' },
    { value: 'my-queue' as CaseScope, label: 'My Queue' },
  ];
  protected readonly resolutionOptions = RESOLUTION_OPTIONS;

  protected readonly loading = signal(true);
  protected readonly detailLoading = signal(false);
  protected readonly actionBusy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly detailError = signal<string | null>(null);
  protected readonly activeScope = signal<CaseScope>('my-queue');
  protected readonly cases = signal<ReviewCase[]>([]);
  protected readonly selectedCaseId = signal<number | null>(null);
  protected readonly selectedCase = signal<ReviewCase | null>(null);
  protected readonly metadataPreview = signal('{}');

  protected readonly resolveForm = this.fb.group({
    resolution_code: this.fb.control(RESOLUTION_OPTIONS[0], {
      nonNullable: true,
      validators: [Validators.required],
    }),
    notes: this.fb.control('', { nonNullable: true }),
  });

  protected readonly reopenForm = this.fb.group({
    reason: this.fb.control('', { nonNullable: true, validators: [Validators.required] }),
  });

  constructor() {
    void this.reload();
  }

  async changeScope(scope: CaseScope): Promise<void> {
    if (this.activeScope() === scope) return;
    this.activeScope.set(scope);
    await this.reload();
  }

  async reload(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    this.selectedCaseId.set(null);
    this.selectedCase.set(null);
    this.metadataPreview.set('{}');

    try {
      const scope = this.activeScope();
      const data =
        scope === 'my-queue'
          ? await api.reviewCases.listMyQueue()
          : await api.reviewCases.list({
              status: scope === 'all' ? undefined : scope,
              limit: 100,
            });

      this.cases.set(data);
      if (data.length > 0) await this.selectCase(data[0].id);
    } catch (e) {
      const err = e as ApiError;
      this.error.set(err?.message ?? 'Failed to load review cases.');
    } finally {
      this.loading.set(false);
    }
  }

  async selectCase(caseId: number): Promise<void> {
    this.selectedCaseId.set(caseId);
    this.detailLoading.set(true);
    this.detailError.set(null);

    try {
      const detail = await api.reviewCases.get(caseId);
      this.selectedCase.set(detail);
      this.metadataPreview.set(JSON.stringify(detail.metadata ?? {}, null, 2));
    } catch (e) {
      const err = e as ApiError;
      this.detailError.set(err?.message ?? 'Failed to load case details.');
    } finally {
      this.detailLoading.set(false);
    }
  }

  async resolveSelectedCase(): Promise<void> {
    const reviewCase = this.selectedCase();
    if (!reviewCase || this.resolveForm.invalid || this.actionBusy()) return;

    this.actionBusy.set(true);
    this.detailError.set(null);
    try {
      const updated = await api.reviewCases.resolve(reviewCase.id, this.resolveForm.getRawValue());
      this.applyUpdatedCase(updated);
    } catch (e) {
      const err = e as ApiError;
      this.detailError.set(err?.message ?? 'Failed to resolve case.');
    } finally {
      this.actionBusy.set(false);
    }
  }

  async reopenSelectedCase(): Promise<void> {
    const reviewCase = this.selectedCase();
    if (!reviewCase || this.reopenForm.invalid || this.actionBusy()) return;

    this.actionBusy.set(true);
    this.detailError.set(null);
    try {
      const updated = await api.reviewCases.reopen(reviewCase.id, this.reopenForm.getRawValue());
      this.applyUpdatedCase(updated);
    } catch (e) {
      const err = e as ApiError;
      this.detailError.set(err?.message ?? 'Failed to reopen case.');
    } finally {
      this.actionBusy.set(false);
    }
  }

  private applyUpdatedCase(updated: ReviewCase): void {
    this.selectedCase.set(updated);
    this.metadataPreview.set(JSON.stringify(updated.metadata ?? {}, null, 2));
    this.cases.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
    this.resolveForm.patchValue({ notes: '' });
    this.reopenForm.patchValue({ reason: '' });
  }
}
