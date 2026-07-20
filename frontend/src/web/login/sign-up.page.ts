import { Component, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { api, ApiError } from '../api';

@Component({
  selector: 'fs-sign-up-page',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <section class="fs-auth">
      <div class="fs-auth-card fs-card">
        <div class="fs-card-header">
          <h1>Create account</h1>
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
            @if (busy()) { Creating… } @else { Create account }
          </button>
        </form>

        <div class="fs-auth-footer">
          <span class="fs-muted">Already have an account?</span>
          <a routerLink="/login/sign-in">Sign in</a>
        </div>
      </div>
    </section>
  `,
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

