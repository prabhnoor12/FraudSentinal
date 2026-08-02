import { Component, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { api, ApiError } from '../api';

@Component({
  selector: 'fs-sign-up-page',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <section class="fs-auth">
      <div class="fs-auth-shell">
        <aside class="fs-auth-aside">
          <p class="fs-auth-kicker">FraudSentinal</p>
          <h1>Create an account that keeps fraud operations organised from day one.</h1>
          <p class="fs-auth-lead">
            Set up your organisation, connect the API, and start routing high-risk activity into a
            cleaner review workflow.
          </p>
          <div class="fs-auth-points">
            <div class="fs-auth-point">
              <strong>Launch quickly</strong>
              <p>Get a working fraud operations surface without building separate internal tools.</p>
            </div>
            <div class="fs-auth-point">
              <strong>Versioned integration path</strong>
              <p>Start from a stable <code>/api/v1</code> contract and expand without guesswork.</p>
            </div>
            <div class="fs-auth-point">
              <strong>Audit-ready by default</strong>
              <p>Track key actions, review events, and decisions in one product loop.</p>
            </div>
          </div>
        </aside>

        <div class="fs-auth-card fs-card">
          <div class="fs-card-header">
            <p class="fs-auth-eyebrow">Get started</p>
            <h2>Create account</h2>
            <p class="fs-muted">Register and sign in to get started.</p>
          </div>

          @if (error()) {
            <div class="fs-alert is-error">{{ error() }}</div>
          }

          <form class="fs-form" [formGroup]="form" (ngSubmit)="submit()">
            <div class="fs-form-grid">
              <label class="fs-field fs-field-full">
                <span>Organisation name</span>
                <input class="fs-input" formControlName="organisation_name" autocomplete="organization" />
              </label>

              <label class="fs-field fs-field-full">
                <span>Full name</span>
                <input class="fs-input" formControlName="full_name" autocomplete="name" />
              </label>

              <label class="fs-field fs-field-full">
                <span>Email</span>
                <input class="fs-input" formControlName="email" autocomplete="email" />
              </label>

              <label class="fs-field fs-field-full">
                <span>Password</span>
                <input
                  class="fs-input"
                  type="password"
                  formControlName="password"
                  autocomplete="new-password"
                />
              </label>
            </div>

            <button class="fs-button" type="submit" [disabled]="busy() || form.invalid">
              @if (busy()) { Creating... } @else { Create account }
            </button>
          </form>

          <div class="fs-auth-footer">
            <span class="fs-muted">Already have an account?</span>
            <a routerLink="/login/sign-in">Sign in</a>
          </div>
        </div>
      </div>
    </section>
  `,
  styleUrl: './sign-up.page.scss',
})
export class SignUpPage {
  private readonly fb = new FormBuilder();
  private readonly router: Router;

  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = this.fb.group({
    organisation_name: this.fb.control('', { nonNullable: true }),
    full_name: this.fb.control('', { nonNullable: true }),
    email: this.fb.control('', { nonNullable: true, validators: [Validators.required, Validators.email] }),
    password: this.fb.control('', { nonNullable: true, validators: [Validators.required, Validators.minLength(8)] }),
  });

  constructor(router: Router) {
    this.router = router;
  }

  async submit(): Promise<void> {
    if (this.busy()) return;
    if (this.form.invalid) return;

    this.busy.set(true);
    this.error.set(null);

    const payload = this.form.getRawValue();
    try {
      await api.auth.register({
        email: payload.email,
        password: payload.password,
        full_name: payload.full_name || null,
        organisation_name: payload.organisation_name || null,
      });
      await api.auth.login({ email: payload.email, password: payload.password });
      await this.router.navigate(['/dashboard']);
    } catch (e) {
      const err = e as ApiError;
      this.error.set(err?.message ?? 'Registration failed.');
    } finally {
      this.busy.set(false);
    }
  }
}
