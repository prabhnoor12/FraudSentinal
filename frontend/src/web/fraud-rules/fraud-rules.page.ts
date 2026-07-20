import { Component, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiError, FraudRule, api } from '../api';
import { FIELD_NAMES, OPERATORS, REASON_CODES } from './fraud-rule-options';

type RuleFilter = 'all' | 'enabled' | 'disabled';

@Component({
  selector: 'fs-fraud-rules-page',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <section class="fs-page">
      <div class="fs-page-header">
        <h1>Fraud Rules</h1>
        <p class="fs-muted">Manage risk rules, thresholds, and rule activation.</p>
      </div>

      <div class="fs-dashboard-grid">
        <div class="fs-card">
          <div class="fs-card-header">
            <h2>Create Rule</h2>
            <p class="fs-muted">Add a rule scoped to the current organisation.</p>
          </div>

          @if (formError()) {
            <div class="fs-alert is-error">{{ formError() }}</div>
          }

          <form class="fs-form" [formGroup]="form" (ngSubmit)="createRule()">
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
            </div>

            <div class="fs-form-actions">
              <button class="fs-button" type="submit" [disabled]="busy() || form.invalid">
                @if (busy()) { Creating… } @else { Create rule }
              </button>
            </div>
          </form>
        </div>

        <div class="fs-card">
          <div class="fs-toolbar">
            <div class="fs-card-header">
              <h2>Active Rules</h2>
              <p class="fs-muted">{{ rules().length }} rule(s)</p>
            </div>
            <div class="fs-chip-group">
              @for (filter of filters; track filter.value) {
                <button
                  type="button"
                  class="fs-chip"
                  [class.is-active]="activeFilter() === filter.value"
                  (click)="changeFilter(filter.value)"
                >
                  {{ filter.label }}
                </button>
              }
            </div>
          </div>

          @if (listError()) {
            <div class="fs-alert is-error">{{ listError() }}</div>
          }

          @if (loading()) {
            <div class="fs-skeleton">Loading rules…</div>
          } @else if (rules().length === 0) {
            <div class="fs-muted">No rules found for the selected filter.</div>
          } @else {
            <div class="fs-stack">
              @for (rule of rules(); track rule.id) {
                <div class="fs-card fs-card-subtle">
                  <div class="fs-rule-row">
                    <div class="fs-rule-main">
                      <div class="fs-list-title">{{ rule.name }}</div>
                      <div class="fs-list-meta">
                        {{ rule.rule_code }} · {{ rule.field_name }} {{ rule.operator }}
                        {{ rule.comparison_value }} · weight {{ rule.weight }} · priority {{ rule.priority }}
                      </div>
                      <div class="fs-list-meta">
                        {{ rule.reason_code }} · {{ rule.enabled ? 'enabled' : 'disabled' }}
                      </div>
                    </div>
                    <div class="fs-inline-actions">
                      <a class="fs-button is-secondary" [routerLink]="['/fraud-rules', rule.id, 'edit']">
                        Edit
                      </a>
                      <button
                        class="fs-button is-secondary"
                        type="button"
                        (click)="toggleRule(rule)"
                        [disabled]="toggleBusyId() === rule.id"
                      >
                        @if (toggleBusyId() === rule.id) {
                          Saving…
                        } @else if (rule.enabled) {
                          Disable
                        } @else {
                          Enable
                        }
                      </button>
                    </div>
                  </div>
                </div>
              }
            </div>
          }
        </div>
      </div>
    </section>
  `,
})
export class FraudRulesPage {
  private readonly fb = new FormBuilder();

  protected readonly reasonCodes = REASON_CODES;
  protected readonly fieldNames = FIELD_NAMES;
  protected readonly operators = OPERATORS;
  protected readonly filters = [
    { value: 'all' as RuleFilter, label: 'All' },
    { value: 'enabled' as RuleFilter, label: 'Enabled' },
    { value: 'disabled' as RuleFilter, label: 'Disabled' },
  ];

  protected readonly loading = signal(true);
  protected readonly busy = signal(false);
  protected readonly listError = signal<string | null>(null);
  protected readonly formError = signal<string | null>(null);
  protected readonly activeFilter = signal<RuleFilter>('all');
  protected readonly toggleBusyId = signal<number | null>(null);
  protected readonly rules = signal<FraudRule[]>([]);

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
    comparison_value: this.fb.control('3', { nonNullable: true, validators: [Validators.required] }),
    weight: this.fb.control(10, { nonNullable: true, validators: [Validators.required] }),
    priority: this.fb.control(10, { nonNullable: true, validators: [Validators.required] }),
  });

  constructor() {
    void this.loadRules();
  }

  async changeFilter(filter: RuleFilter): Promise<void> {
    if (this.activeFilter() === filter) return;
    this.activeFilter.set(filter);
    await this.loadRules();
  }

  async loadRules(): Promise<void> {
    this.loading.set(true);
    this.listError.set(null);
    try {
      const filter = this.activeFilter();
      const rules = await api.fraudRules.list({
        enabled: filter === 'all' ? undefined : filter === 'enabled',
        limit: 100,
      });
      this.rules.set(rules);
    } catch (e) {
      const err = e as ApiError;
      this.listError.set(err?.message ?? 'Failed to load fraud rules.');
    } finally {
      this.loading.set(false);
    }
  }

  async createRule(): Promise<void> {
    if (this.form.invalid || this.busy()) return;
    this.busy.set(true);
    this.formError.set(null);

    const raw = this.form.getRawValue();
    try {
      const created = await api.fraudRules.create({
        ...raw,
        description: raw.description || null,
        comparison_value: this.parseComparisonValue(raw.comparison_value),
      });
      this.rules.update((items) => [created, ...items]);
      this.form.reset({
        name: '',
        rule_code: '',
        description: '',
        reason_code: REASON_CODES[0],
        field_name: FIELD_NAMES[0],
        operator: OPERATORS[0],
        comparison_value: '3',
        weight: 10,
        priority: 10,
      });
    } catch (e) {
      const err = e as ApiError;
      this.formError.set(err?.message ?? 'Failed to create fraud rule.');
    } finally {
      this.busy.set(false);
    }
  }

  async toggleRule(rule: FraudRule): Promise<void> {
    if (this.toggleBusyId() === rule.id) return;
    this.toggleBusyId.set(rule.id);
    this.listError.set(null);

    try {
      const updated = rule.enabled
        ? await api.fraudRules.disable(rule.id)
        : await api.fraudRules.enable(rule.id);
      this.rules.update((items) => {
        const next = items.map((item) => (item.id === updated.id ? updated : item));
        if (this.activeFilter() === 'enabled') return next.filter((item) => item.enabled);
        if (this.activeFilter() === 'disabled') return next.filter((item) => !item.enabled);
        return next;
      });
    } catch (e) {
      const err = e as ApiError;
      this.listError.set(err?.message ?? 'Failed to update fraud rule.');
    } finally {
      this.toggleBusyId.set(null);
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
