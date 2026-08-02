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

      <div class="fs-summary-grid">
        <div class="fs-summary-card">
          <span class="fs-summary-label">Visible logs</span>
          <strong>{{ logs().length }}</strong>
        </div>
        <div class="fs-summary-card">
          <span class="fs-summary-label">Unique actions</span>
          <strong>{{ uniqueActionCount() }}</strong>
        </div>
        <div class="fs-summary-card">
          <span class="fs-summary-label">Latest activity</span>
          <strong>{{ latestLogLabel() }}</strong>
        </div>
      </div>

      <div class="fs-card">
        <div class="fs-card-header">
          <span class="fs-eyebrow">Audit stream</span>
          <h2>Audit Logs</h2>
          <p class="fs-muted">Track sensitive actions, resource access, and system changes across the platform.</p>
        </div>

        @if (loading()) {
          <div class="fs-skeleton">Loading...</div>
        } @else if (error()) {
          <div class="fs-alert is-error">{{ error() }}</div>
        } @else if (logs().length === 0) {
          <div class="fs-empty-state">
            <strong>No audit logs found</strong>
            <p class="fs-muted">Audit records will appear here once the platform starts recording activity.</p>
          </div>
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
                    <td data-label="ID">
                      <span class="fs-cell-label">Log</span>
                      <strong>#{{ l.id ?? 'n/a' }}</strong>
                    </td>
                    <td data-label="Timestamp">
                      <span class="fs-cell-label">Created</span>
                      <strong>{{ l.created_at ?? 'Unavailable' }}</strong>
                    </td>
                    <td data-label="Type">
                      <span class="fs-status-pill">{{ l.event_type ?? 'event' }}</span>
                    </td>
                    <td data-label="Action">
                      <span class="fs-cell-label">Action</span>
                      <strong>{{ l.action ?? 'Unknown' }}</strong>
                    </td>
                    <td data-label="Resource">
                      <span class="fs-cell-label">Resource</span>
                      <strong>
                        {{ l.resource_type ?? 'n/a' }}
                        @if (l.resource_id) {
                          #{{ l.resource_id }}
                        }
                      </strong>
                    </td>
                    <td data-label="IP">
                      <span class="fs-cell-label">Address</span>
                      <strong>{{ l.ip_address ?? 'Unavailable' }}</strong>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </div>
    </section>
  `,
  styleUrl: './audit.page.scss',
})
export class AuditPage {
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly logs = signal<AuditLog[]>([]);

  constructor() {
    void this.load();
  }

  protected uniqueActionCount(): number {
    return new Set(this.logs().map((log) => log.action ?? 'unknown')).size;
  }

  protected latestLogLabel(): string {
    return this.logs()[0]?.created_at ?? 'No data';
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
