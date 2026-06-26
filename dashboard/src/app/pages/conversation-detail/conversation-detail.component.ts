import { Component, OnInit, inject } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { KpiService, ConversationDetail, ConversationEvento } from '../../services/kpi.service';

const STAGE_LABELS: Record<string, string> = {
  'C90:NEW': 'IA Porta',
  'C90:PROSPECTO': 'Prospecto',
  'C90:SEGUIMIENTO': 'Seguimiento',
  'C90:UC_8WB2DT': 'Escalamiento',
  'C90:WON': 'Venta',
  'C90:1': 'Rescate 1',
  'C90:2': 'Rescate 2',
  'C90:3': 'Rescate 3',
  'C90:8': 'Recuperación',
  'C90:PREPAYMENT_INVOIC': 'Recuperación',
  'C90:LOSE': 'Caído',
};

@Component({
  selector: 'app-conversation-detail',
  standalone: true,
  imports: [CommonModule, DatePipe, RouterLink],
  templateUrl: './conversation-detail.component.html',
})
export class ConversationDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private kpiSvc = inject(KpiService);

  id = '';
  loading = true;
  error = '';
  data: ConversationDetail | null = null;

  get mensajes(): ConversationEvento[] {
    return this.data?.eventos.filter(e => e.tipo_actor !== 'sistema') ?? [];
  }

  get transiciones(): ConversationEvento[] {
    return this.data?.eventos.filter(e => e.tipo_actor === 'sistema') ?? [];
  }

  ngOnInit(): void {
    this.id = this.route.snapshot.paramMap.get('id') ?? '';
    this.kpiSvc.getConversationDetail(this.id).subscribe({
      next: (d) => { this.data = d; this.loading = false; },
      error: () => { this.error = 'No se pudo cargar la conversación.'; this.loading = false; },
    });
  }

  back(): void {
    this.router.navigate(['/dashboard']);
  }

  stageLabel(id: string): string {
    return STAGE_LABELS[id] || id;
  }

  formatSecs(secs: number | null | undefined): string {
    if (secs == null) return '—';
    if (secs < 60) return `${Math.round(secs)}s`;
    const m = Math.floor(secs / 60);
    if (m < 60) return `${m}m ${Math.round(secs % 60)}s`;
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m`;
  }

  formatCost(usd: number | null): string {
    if (usd == null) return '';
    return `$${usd.toFixed(4)}`;
  }
}
