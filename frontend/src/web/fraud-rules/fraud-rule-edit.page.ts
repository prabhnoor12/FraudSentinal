import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ApiError, FraudRule, api } from '../api';
import { FIELD_NAMES, OPERATORS, REASON_CODES } from './fraud-rule-options';

@Component({
  selector: 'fs-fraud-rule-edit-page',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <section class="fs-page">
      <div class="fs-page-header">
        <a class="fs-back-link" routerLink="/fraud-rules">← Back to Fraud Rules</a>
        <h1>Edit Fraud Rule</h1>
        <p class="fs-muted">Update rule behavior, thresholds, and activation state.</p>
      </div>

      <div class="fs-card">
        @if (loading()) {
          <div class="fs-skeleton">Loading rule…</div>
        } @else if (error()) {
          <div class="fs-alert is-error">{{ error() }}</div>
        } @else {
          <form class="fs-form" [formGroup]="form" (ngSubmit)="save()">
            <div class="fs-form-grid">
              <label class="fs-field">
                <span>Name</span>
                <input class="fs-input" formControlName="name" />
              </label>

              <label class="fs-field">
                <span>Rule Code</span>
                <input class="fs-input" formControlName="rule_code" />
              </label>

              <label class="fs-field fs-field-full">
                <span>Description</span>
                <textarea class="fs-input" rows="3" formControlName="description"></textarea>
              </label>

              <label class="fs-field">
                <span>Reason Code</span>
                <select class="fs-input" formControlName="reason_code">
                  @for (reason of reasonCodes; track reason) {
                    <option [value]="reason">{{ reason }}</option>
                  }
                </select>
              </label>

              <label class="fs-field">
                <span>Field</span>
                <select class="fs-input" formControlName="field_name">
                  @for (field of fieldNames; track field) {
                    <option [value]="field">{{ field }}</option>
                  }
                </select>
              </label>

              <label class="fs-field">
                <span>Operator</span>
                <select class="fs-input" formControlName="operator">
                  @for (operator of operators; track operator) {
                    <option [value]="operator">{{ operator }}</option>
                  }
                </select>
              </label>

              <label class="fs-field">
                <span>Comparison Value</span>
                <input class="fs-input" formControlName="comparison_value" />
              </label>

              <label class="fs-field">
                <span>Weight</span>
                <input class="fs-input" type="number" formControlName="weight" />
              </label>

              <label class="fs-field">
                <span>Priority</span>
                <input class="fs-input" type="number" formControlName="priority" />
              </label>

              <label class="fs-field fs-field-check">
                <input type="checkbox" formControlName="enabled" />
                <span>Enabled</span>
              </label>
            </div>

            <div class="fs-form-actions">
              <button class="fs-button" type="submit" [disabled]="saving() || form.invalid">
                @if (saving()) { Saving… } @else { Save changes }
              </button>
              <a class="fs-button is-secondary" routerLink="/fraud-rules">Cancel</a>
            </div>
          </form>
        }
      </div>
    </section>
  `,
})
export class FraudRuleEditPage {
  private readonly fb = new FormBuilder();
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly reasonCodes = REASON_CODES;
  protected readonly fieldNames = FIELD_NAMES;
  protected readonly operators = OPERATORS;

  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly rule = signal<FraudRule | null>(null);
  protected readonly ruleId = signal<number | null>(null);

  protected readonly form = this.fb.group({
    name: this.fb.control('', { nonNullable: true, validators: [Validators.required, Validators.minLength(3)] }),
    rule_code: this.fb.control('', {
      nonNullable: true,
      validators: [Validators.required, Validators.minLength(3)],
    }),
    description: this.fb.control('', { nonNullable: true }),
    reason_code: this.fb.control(REASON_CODES[0], { nonNullable: true, validators: [Validators.required] }),
    field_name: this.fb.control(FIELD_NAMES[0], { nonNullable: true, validators: [Validators.required] }),
    operator: this.fb.control(OPERATORS[0], { nonNullable: true, validators: [Validators.required] }),
    comparison_value: this.fb.control('', { nonNullable: true, validators: [Validators.required] }),
    weight: this.fb.control(10, { nonNullable: true, validators: [Validators.required] }),
    priority: this.fb.control(10, { nonNullable: true, validators: [Validators.required] }),
    enabled: this.fb.control(true, { nonNullable: true }),
  });

  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const ruleId = Number(params.get('ruleId'));
      if (!Number.isFinite(ruleId) || ruleId <= 0) {
        this.error.set('Invalid fraud rule identifier.');
        this.loading.set(false);
        return;
      }
      this.ruleId.set(ruleId);
      void this.load(ruleId);
    });
  }

  async save(): Promise<void> {
    const ruleId = this.ruleId();
    if (!ruleId || this.form.invalid || this.saving()) return;

    this.saving.set(true);
    this.error.set(null);
    const raw = this.form.getRawValue();

    try {
      const updated = await api.fraudRules.update(ruleId, {
        ...raw,
        description: raw.description || null,
        comparison_value: this.parseComparisonValue(raw.comparison_value),
      });
      this.rule.set(updated);
      await this.router.navigate(['/fraud-rules']);
    } catch (e) {
      const err = e as ApiError;
      this.error.set(err?.message ?? 'Failed to update fraud rule.');
    } finally {
      this.saving.set(false);
    }
  }

  private async load(ruleId: number): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const rule = await api.fraudRules.get(ruleId);
      this.rule.set(rule);
      this.form.reset({
        name: rule.name,
        rule_code: rule.rule_code,
        description: rule.description ?? '',
        reason_code: rule.reason_code,
        field_name: rule.field_name,
        operator: rule.operator,
        comparison_value: String(rule.comparison_value ?? ''),
        weight: rule.weight,
        priority: rule.priority,
        enabled: rule.enabled,
      });
    } catch (e) {
      const err = e as ApiError;
      this.error.set(err?.message ?? 'Failed to load fraud rule.');
    } finally {
      this.loading.set(false);
    }
  }

  private parseComparisonValue(value: string): string | number | boolean {
    const trimmed = value.trim();
    if (trimmed === 'true') return true;
    if (trimmed === 'false') return false;
    const asNumber = Number(trimmed);
    return Number.isNaN(asNumber) ? trimmed : asNumber;
  }
}

