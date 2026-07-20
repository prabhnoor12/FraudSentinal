import { Component, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { api, ApiError } from '../api';

type Me = { organisation_id?: number | null };
type OrgSettings = {
  organisation_id: number;
  currency: string;
  timezone: string;
  enable_billing: boolean;
  enable_usage_tracking: boolean;
  notification_email?: string | null;
  notes?: string | null;
};

@Component({
  selector: 'fs-settings-page',
  imports: [ReactiveFormsModule],
  template: `
    <section class="fs-page">
      <div class="fs-page-header">
        <h1>Settings</h1>
        <p class="fs-muted">Configure organisation and account preferences.</p>
      </div>

      <div class="fs-card">
        <div class="fs-card-header">
          <h2>Organisation Settings</h2>
        </div>

        @if (loading()) {
          <div class="fs-skeleton">Loading…</div>
        } @else if (error()) {
          <div class="fs-alert is-error">{{ error() }}</div>
        } @else {
          <form class="fs-form" [formGroup]="form" (ngSubmit)="save()">
            <div class="fs-form-grid">
              <label class="fs-field">
                <span>Currency</span>
                <input class="fs-input" formControlName="currency" />
              </label>

              <label class="fs-field">
                <span>Timezone</span>
                <input class="fs-input" formControlName="timezone" />
              </label>

              <label class="fs-field fs-field-full">
                <span>Notification Email</span>
                <input class="fs-input" formControlName="notification_email" />
              </label>

              <label class="fs-field fs-field-check">
                <input type="checkbox" formControlName="enable_billing" />
                <span>Enable billing</span>
              </label>

              <label class="fs-field fs-field-check">
                <input type="checkbox" formControlName="enable_usage_tracking" />
                <span>Enable usage tracking</span>
              </label>

              <label class="fs-field fs-field-full">
                <span>Notes</span>
                <textarea class="fs-input" rows="4" formControlName="notes"></textarea>
              </label>
            </div>

            <div class="fs-form-actions">
              <button class="fs-button" type="submit" [disabled]="saving() || form.invalid">
                @if (saving()) { Saving… } @else { Save changes }
              </button>
              @if (saved()) {
                <span class="fs-muted">Saved.</span>
              }
            </div>
          </form>
        }
      </div>
    </section>
  `,
})
export class SettingsPage {
  private readonly fb = new FormBuilder();

  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly saved = signal(false);
  protected readonly error = signal<string | null>(null);
  protected organisationId: number | null = null;

  protected readonly form = this.fb.group({
    currency: this.fb.control('USD', { nonNullable: true, validators: [Validators.required] }),
    timezone: this.fb.control('UTC', { nonNullable: true, validators: [Validators.required] }),
    enable_billing: this.fb.control(true, { nonNullable: true }),
    enable_usage_tracking: this.fb.control(true, { nonNullable: true }),
    notification_email: this.fb.control<string | null>(null),
    notes: this.fb.control<string | null>(null),
  });

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);

    try {
      const me = (await api.auth.me()) as Me;
      const orgId = me.organisation_id ?? null;
      if (!orgId) {
        this.error.set('Missing organisation_id for current user.');
        return;
      }

      this.organisationId = orgId;
      const settings = (await api.settings.get(orgId)) as OrgSettings;
      this.form.patchValue({
        currency: settings.currency,
        timezone: settings.timezone,
        enable_billing: settings.enable_billing,
        enable_usage_tracking: settings.enable_usage_tracking,
        notification_email: settings.notification_email ?? null,
        notes: settings.notes ?? null,
      });
    } catch (e) {
      const err = e as ApiError;
      this.error.set(err?.message ?? 'Failed to load settings.');
    } finally {
      this.loading.set(false);
    }
  }

  async save(): Promise<void> {
    if (!this.organisationId) return;
    if (this.saving()) return;
    if (this.form.invalid) return;

    this.saving.set(true);
    this.saved.set(false);
    this.error.set(null);

    try {
      await api.settings.update(this.organisationId, this.form.getRawValue() as any);
      this.saved.set(true);
    } catch (e) {
      const err = e as ApiError;
      this.error.set(err?.message ?? 'Failed to save settings.');
    } finally {
      this.saving.set(false);
    }
  }
}

