import { Component, OnInit, AfterViewInit, OnDestroy, inject, ViewChild, ElementRef } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Chart, registerables } from 'chart.js';
import { KpiService, KpiData, KpiResumen, StageCount, Conversacion } from '../../services/kpi.service';
import { AuthService } from '../../services/auth.service';

Chart.register(...registerables);

const STAGE_LABELS: Record<string, string> = {
  'C90:NEW': 'IA Porta',
  'C90:PROSPECTO': 'Prospecto',
  'C90:SEGUIMIENTO': 'Seguimiento',
  'C90:UC_8WB2DT': 'Escalado',
  'C90:WON': 'Venta',
  'C90:1': 'Rescate 1',
  'C90:2': 'Rescate 2',
  'C90:3': 'Rescate 3',
  'C90:8': 'Recuperación',
  'C90:LOSE': 'Caído',
};

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, DatePipe, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('stageChart') stageChartRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('msgChart') msgChartRef!: ElementRef<HTMLCanvasElement>;

  private kpiSvc = inject(KpiService);
  private auth = inject(AuthService);
  private router = inject(Router);

  loading = true;
  error = '';
  exportLoading = false;
  exportMsg = '';

  resumen: KpiResumen | null = null;
  porStage: StageCount[] = [];
  conversaciones: Conversacion[] = [];
  paginacion = { total: 0, page: 1, page_size: 20, total_pages: 1 };

  desde = '';
  hasta = '';
  search = '';
  stageFilter = '';

  readonly stageOptions = [
    { value: '', label: 'Todos los stages' },
    { value: 'C90:NEW', label: 'IA Porta' },
    { value: 'C90:PROSPECTO', label: 'Prospecto' },
    { value: 'C90:SEGUIMIENTO', label: 'Seguimiento' },
    { value: 'C90:UC_8WB2DT', label: 'Escalado' },
    { value: 'C90:WON', label: 'Venta' },
    { value: 'C90:1', label: 'Rescate 1' },
    { value: 'C90:2', label: 'Rescate 2' },
    { value: 'C90:3', label: 'Rescate 3' },
    { value: 'C90:8', label: 'Recuperación' },
    { value: 'C90:LOSE', label: 'Caído' },
  ];

  private stageChart?: Chart;
  private msgChart?: Chart;
  private chartsReady = false;

  ngOnInit(): void {
    this.load();
  }

  ngAfterViewInit(): void {
    this.chartsReady = true;
    if (this.resumen) this.renderCharts();
  }

  ngOnDestroy(): void {
    this.stageChart?.destroy();
    this.msgChart?.destroy();
  }

  load(page = 1): void {
    this.loading = true;
    this.error = '';
    this.kpiSvc.getData(
      page,
      this.paginacion.page_size,
      this.desde || undefined,
      this.hasta || undefined,
      this.stageFilter || undefined,
      this.search.trim() || undefined,
    )
      .subscribe({
        next: (data: KpiData) => {
          this.resumen = data.resumen;
          this.porStage = data.por_stage;
          this.conversaciones = data.conversaciones;
          this.paginacion = data.paginacion;
          this.loading = false;
          if (this.chartsReady) this.renderCharts();
        },
        error: (err: { status?: number }) => {
          if (err.status === 403) {
            this.auth.logout();
            this.router.navigate(['/login']);
          } else {
            this.error = 'Error al cargar datos. Intenta de nuevo.';
          }
          this.loading = false;
        },
      });
  }

  applyFilter(): void {
    this.load(1);
  }

  clearFilter(): void {
    this.desde = '';
    this.hasta = '';
    this.stageFilter = '';
    this.search = '';
    this.load(1);
  }

  goPage(p: number): void {
    if (p < 1 || p > this.paginacion.total_pages) return;
    this.load(p);
  }

  stageLabel(stage: string): string {
    return STAGE_LABELS[stage] ?? stage;
  }

  formatSecs(s: number | null): string {
    if (s == null || s === 0) return '—';
    if (s < 60) return `${Math.round(s)}s`;
    return `${Math.round(s / 60)}m ${Math.round(s % 60)}s`;
  }

  get filteredConversaciones(): Conversacion[] {
    return this.conversaciones;
  }

  triggerExport(): void {
    this.exportLoading = true;
    this.exportMsg = '';
    this.kpiSvc.triggerExport().subscribe({
      next: () => {
        this.exportMsg = 'Export iniciado — revisa los logs para el progreso.';
        this.exportLoading = false;
      },
      error: () => {
        this.exportMsg = 'Error al iniciar el export.';
        this.exportLoading = false;
      },
    });
  }

  logout(): void {
    this.auth.logout();
    this.router.navigate(['/login']);
  }

  minVal(a: number, b: number): number {
    return Math.min(a, b);
  }

  get pages(): number[] {
    const { page, total_pages } = this.paginacion;
    const delta = 2;
    const range: number[] = [];
    for (let i = Math.max(1, page - delta); i <= Math.min(total_pages, page + delta); i++) {
      range.push(i);
    }
    return range;
  }

  private renderCharts(): void {
    this.stageChart?.destroy();
    this.msgChart?.destroy();

    const stageColors = [
      '#e8001d','#10b981','#f59e0b','#3b82f6',
      '#8b5cf6','#ec4899','#14b8a6','#f97316','#6366f1','#64748b',
    ];

    this.stageChart = new Chart(this.stageChartRef.nativeElement, {
      type: 'doughnut',
      data: {
        labels: this.porStage.map(s => this.stageLabel(s.stage)),
        datasets: [{
          data: this.porStage.map(s => s.cantidad),
          backgroundColor: stageColors.slice(0, this.porStage.length),
          borderWidth: 2,
          borderColor: '#fff',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'right', labels: { font: { family: 'Inter', size: 12 }, padding: 12 } },
        },
        cutout: '60%',
      },
    });

    if (this.resumen) {
      this.msgChart = new Chart(this.msgChartRef.nativeElement, {
        type: 'bar',
        data: {
          labels: ['Cliente', 'Bot (Vera)', 'Asesor Humano'],
          datasets: [{
            label: 'Mensajes totales',
            data: [
              this.resumen.total_msgs_cliente,
              this.resumen.total_msgs_bot,
              this.resumen.total_msgs_humano,
            ],
            backgroundColor: ['#3b82f6', '#e8001d', '#10b981'],
            borderRadius: 6,
            borderSkipped: false,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: { family: 'Inter' } } },
            x: { grid: { display: false }, ticks: { font: { family: 'Inter' } } },
          },
        },
      });
    }
  }
}
