import { Component, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { api, ApiError } from '../api';

@Component({
  selector: 'fs-sign-in-page',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <section class="fs-auth">
      <div class="fs-auth-shell">
        <aside class="fs-auth-aside">
          <p class="fs-auth-kicker">FraudSentinal</p>
          <h1>Sign in without losing sight of what needs review.</h1>
          <p class="fs-auth-lead">
            Access your dashboard, monitor high-risk activity, and keep analyst workflows tidy in
            one place.
          </p>
          <div class="fs-auth-points">
            <div class="fs-auth-point">
              <strong>See decisions clearly</strong>
              <p>Reason codes, audit context, and review actions stay close together.</p>
            </div>
            <div class="fs-auth-point">
              <strong>Keep queues under control</strong>
              <p>Surface the risky transactions first instead of digging through raw logs.</p>
            </div>
            <div class="fs-auth-point">
              <strong>Stay tenant-safe</strong>
              <p>Organisation boundaries and operational visibility remain built into the flow.</p>
            </div>
          </div>
        </aside>

        <div class="fs-auth-card fs-card">
          <div class="fs-card-header">
            <p class="fs-auth-eyebrow">Welcome back</p>
            <h2>Sign in</h2>
            <p class="fs-muted">Access your FraudSentinal dashboard.</p>
          </div>

          @if (error()) {
            <div class="fs-alert is-error">{{ error() }}</div>
          }

          @if (info()) {
            <div class="fs-alert is-info">{{ info() }}</div>
          }

          <form class="fs-form" [formGroup]="form" (ngSubmit)="submit()">
            <label class="fs-field">
              <span>Email</span>
              <input class="fs-input" formControlName="email" autocomplete="email" />
            </label>

            <label class="fs-field">
              <span>Password</span>
              <input
                class="fs-input"
                type="password"
                formControlName="password"
                autocomplete="current-password"
              />
            </label>

            <button class="fs-button" type="submit" [disabled]="busy() || form.invalid">
              @if (busy()) { Signing in... } @else { Sign in }
            </button>
          </form>

          <div class="fs-auth-footer">
            <span class="fs-muted">No account?</span>
            <a routerLink="/login/sign-up">Create one</a>
          </div>
        </div>
      </div>
    </section>
  `,
  styleUrl: './sign-in.page.scss',
})
export class SignInPage {
  private readonly fb = new FormBuilder();
  private readonly router: Router;

  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly info = signal<string | null>(null);

  protected readonly form = this.fb.group({
    email: this.fb.control('', { nonNullable: true, validators: [Validators.required, Validators.email] }),
    password: this.fb.control('', { nonNullable: true, validators: [Validators.required] }),
  });

  constructor(router: Router) {
    this.router = router;
  }

  async submit(): Promise<void> {
    if (this.busy()) return;
    if (this.form.invalid) return;

    this.busy.set(true);
    this.error.set(null);
    this.info.set(null);

    const payload = this.form.getRawValue();
    try {
      const result = await api.auth.login(payload);
      if (result.mfa_required) {
        this.info.set('MFA is required for this account. Complete MFA login is not implemented in the web UI yet.');
        return;
      }
      await this.router.navigate(['/dashboard']);
    } catch (e) {
      const err = e as ApiError;
      this.error.set(err?.message ?? 'Sign-in failed.');
    } finally {
      this.busy.set(false);
    }
  }
}
