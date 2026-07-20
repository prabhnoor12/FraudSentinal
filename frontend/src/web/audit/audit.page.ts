import { Component, signal } from '@angular/core';
import { api, ApiError } from '../api';

type AuditLog = {
  id?: number;
  created_at?: string;
  event_type?: string;
  action?: string;
  resource_type?: string | null;
  resource_id?: string | null;
  ip_address?: string | null;
};

@Component({
  selector: 'fs-audit-page',
  template: `
    <section class="fs-page">
      <div class="fs-page-header">
        <h1>Audit</h1>
        <p class="fs-muted">View and manage system audit logs.</p>
      </div>

      <div class="fs-card">
        <div class="fs-card-header">
          <h2>Audit Logs</h2>
        </div>

        @if (loading()) {
          <div class="fs-skeleton">Loading…</div>
        } @else if (error()) {
          <div class="fs-alert is-error">{{ error() }}</div>
        } @else if (logs().length === 0) {
          <div class="fs-muted">No audit logs found.</div>
        } @else {
          <div class="fs-table-wrap">
            <table class="fs-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Timestamp</th>
                  <th>Type</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                @for (l of logs(); track l.id ?? $index) {
                  <tr>
                    <td>{{ l.id ?? '' }}</td>
                    <td>{{ l.created_at ?? '' }}</td>
                    <td>{{ l.event_type ?? '' }}</td>
                    <td>{{ l.action ?? '' }}</td>
                    <td>
                      {{ l.resource_type ?? '' }}
                      @if (l.resource_id) {
                        #{{ l.resource_id }}
                      }
                    </td>
                    <td>{{ l.ip_address ?? '' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </div>
    </section>
  `,
})
export class AuditPage {
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly logs = signal<AuditLog[]>([]);

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);

    try {
      const data = (await api.audit.list({ limit: 100, offset: 0 })) as AuditLog[];
      this.logs.set(data ?? []);
    } catch (e) {
      const err = e as ApiError;
      if (err?.status === 403) {
        this.error.set('Audit access requires admin role.');
      } else {
        this.error.set(err?.message ?? 'Failed to load audit logs.');
      }
    } finally {
      this.loading.set(false);
    }
  }
}

