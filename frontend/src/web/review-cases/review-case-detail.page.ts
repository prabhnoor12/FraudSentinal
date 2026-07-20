import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ApiError, ReviewCase, api } from '../api';

const RESOLUTION_OPTIONS = [
  'approved_by_analyst',
  'declined_by_analyst',
  'false_positive',
  'fraud_confirmed',
];

@Component({
  selector: 'fs-review-case-detail-page',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <section class="fs-page">
      <div class="fs-page-header">
        <a class="fs-back-link" routerLink="/review-cases">← Back to Review Cases</a>
        <h1>Review Case Detail</h1>
        <p class="fs-muted">Inspect the case record and take analyst action.</p>
      </div>

      <div class="fs-card">
        @if (loading()) {
          <div class="fs-skeleton">Loading case…</div>
        } @else if (error()) {
          <div class="fs-alert is-error">{{ error() }}</div>
        } @else if (reviewCase()) {
          <div class="fs-detail-grid">
            <div class="fs-stat-card">
              <span class="fs-stat-label">Case</span>
              <strong>#{{ reviewCase()!.id }}</strong>
            </div>
            <div class="fs-stat-card">
              <span class="fs-stat-label">Status</span>
              <strong>{{ reviewCase()!.status }}</strong>
            </div>
            <div class="fs-stat-card">
              <span class="fs-stat-label">Resolution</span>
              <strong>{{ reviewCase()!.resolution_code || 'pending' }}</strong>
            </div>
            <div class="fs-stat-card">
              <span class="fs-stat-label">Resolved At</span>
              <strong>{{ reviewCase()!.resolved_at || 'not resolved' }}</strong>
            </div>
            <div class="fs-stat-card">
              <span class="fs-stat-label">Transaction</span>
              <strong>#{{ reviewCase()!.transaction_id }}</strong>
            </div>
            <div class="fs-stat-card">
              <span class="fs-stat-label">Decision</span>
              <strong>#{{ reviewCase()!.decision_id }}</strong>
            </div>
          </div>

          <div class="fs-stack">
            <div class="fs-card fs-card-subtle">
              <div class="fs-card-header">
                <h3>Analyst Notes</h3>
              </div>
              <p class="fs-prewrap">{{ reviewCase()!.notes || 'No notes recorded.' }}</p>
            </div>

            <div class="fs-card fs-card-subtle">
              <div class="fs-card-header">
                <h3>Metadata</h3>
              </div>
              <pre class="fs-json">{{ metadataPreview() }}</pre>
            </div>

            @if (reviewCase()!.status === 'open') {
              <form class="fs-form" [formGroup]="resolveForm" (ngSubmit)="resolveCase()">
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
                  <a class="fs-button is-secondary" [routerLink]="['/transactions', reviewCase()!.transaction_id]">
                    Open transaction
                  </a>
                </div>
              </form>
            } @else {
              <form class="fs-form" [formGroup]="reopenForm" (ngSubmit)="reopenCase()">
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
                  <a class="fs-button is-secondary" [routerLink]="['/transactions', reviewCase()!.transaction_id]">
                    Open transaction
                  </a>
                </div>
              </form>
            }
          </div>
        }
      </div>
    </section>
  `,
})
export class ReviewCaseDetailPage {
  private readonly fb = new FormBuilder();
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly resolutionOptions = RESOLUTION_OPTIONS;
  protected readonly loading = signal(true);
  protected readonly actionBusy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly reviewCase = signal<ReviewCase | null>(null);
  protected readonly caseId = signal<number | null>(null);
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
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const caseId = Number(params.get('caseId'));
      if (!Number.isFinite(caseId) || caseId <= 0) {
        this.error.set('Invalid review case identifier.');
        this.loading.set(false);
        return;
      }
      this.caseId.set(caseId);
      void this.load(caseId);
    });
  }

  async resolveCase(): Promise<void> {
    const caseId = this.caseId();
    if (!caseId || this.resolveForm.invalid || this.actionBusy()) return;

    this.actionBusy.set(true);
    this.error.set(null);
    try {
      const updated = await api.reviewCases.resolve(caseId, this.resolveForm.getRawValue());
      this.applyUpdatedCase(updated);
    } catch (e) {
      const err = e as ApiError;
      this.error.set(err?.message ?? 'Failed to resolve case.');
    } finally {
      this.actionBusy.set(false);
    }
  }

  async reopenCase(): Promise<void> {
    const caseId = this.caseId();
    if (!caseId || this.reopenForm.invalid || this.actionBusy()) return;

    this.actionBusy.set(true);
    this.error.set(null);
    try {
      const updated = await api.reviewCases.reopen(caseId, this.reopenForm.getRawValue());
      this.applyUpdatedCase(updated);
    } catch (e) {
      const err = e as ApiError;
      this.error.set(err?.message ?? 'Failed to reopen case.');
    } finally {
      this.actionBusy.set(false);
    }
  }

  private async load(caseId: number): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const reviewCase = await api.reviewCases.get(caseId);
      this.applyUpdatedCase(reviewCase);
    } catch (e) {
      const err = e as ApiError;
      this.error.set(err?.message ?? 'Failed to load review case.');
    } finally {
      this.loading.set(false);
    }
  }

  private applyUpdatedCase(reviewCase: ReviewCase): void {
    this.reviewCase.set(reviewCase);
    this.metadataPreview.set(JSON.stringify(reviewCase.metadata ?? {}, null, 2));
    this.resolveForm.patchValue({ notes: '' });
    this.reopenForm.patchValue({ reason: '' });
  }
}

