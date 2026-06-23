import { Component, OnInit, AfterViewInit, OnDestroy, inject, ViewChild, ElementRef } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Chart, registerables } from 'chart.js';
import { KpiService, KpiData, KpiResumen, StageCount, Conversacion, MegacableData, MegacableResumen, MegacableConversacion, UtmData, MetaInsightsData, MetaInsightRow, FunnelData, FunnelTransicion } from '../../services/kpi.service';
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
  private mgEstadoChart?: Chart;
  private mgActorChart?: Chart;
  private chartsReady = false;

  metaData: MetaInsightsData | null = null;
  metaLoading = true;
  metaError = '';
  metaDesde = '';
  metaHasta = '';
  metaLevel = 'campaign';

  funnelData: FunnelData | null = null;
  funnelLoading = true;
  funnelError = '';
  funnelTransiciones: FunnelTransicion[] = [];

  @ViewChild('funnelChart') funnelChartRef!: ElementRef<HTMLCanvasElement>;
  private funnelChart?: Chart;

  @ViewChild('metaSpendChart') metaSpendChartRef!: ElementRef<HTMLCanvasElement>;
  private metaSpendChart?: Chart;

  utmData: UtmData | null = null;
  utmLoading = true;
  utmError = '';
  utmDesde = '';
  utmHasta = '';

  @ViewChild('utmFuenteChart') utmFuenteChartRef!: ElementRef<HTMLCanvasElement>;
  private utmFuenteChart?: Chart;

  megacableData: MegacableData | null = null;
  megacableLoading = true;
  megacableError = '';
  mgDesde = '';
  mgHasta = '';

  @ViewChild('mgEstadoChart') mgEstadoChartRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('mgActorChart') mgActorChartRef!: ElementRef<HTMLCanvasElement>;

  ngOnInit(): void {
    this.load();
    this.loadFunnel();
    this.loadMeta();
    this.loadUtm();
    this.loadMegacable();
  }

  ngAfterViewInit(): void {
    this.chartsReady = true;
    if (this.resumen) this.renderCharts();
    if (this.funnelData) this.renderFunnelChart();
    if (this.metaData) this.renderMetaChart();
    if (this.utmData) this.renderUtmChart();
    if (this.megacableData) this.renderMegacableCharts();
  }

  ngOnDestroy(): void {
    this.stageChart?.destroy();
    this.msgChart?.destroy();
    this.funnelChart?.destroy();
    this.metaSpendChart?.destroy();
    this.utmFuenteChart?.destroy();
    this.mgEstadoChart?.destroy();
    this.mgActorChart?.destroy();
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
          // setTimeout(0) espera a que Angular renderice el bloque @else
          // antes de intentar acceder a los canvas via @ViewChild
          if (this.chartsReady) setTimeout(() => this.renderCharts(), 0);
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

  loadFunnel(): void {
    this.funnelLoading = true;
    this.funnelError = '';
    this.kpiSvc.getFunnelData(this.desde || undefined, this.hasta || undefined).subscribe({
      next: (data) => {
        this.funnelData = data;
        this.funnelTransiciones = data.transiciones ?? [];
        this.funnelLoading = false;
        if (this.chartsReady) setTimeout(() => this.renderFunnelChart(), 0);
      },
      error: () => {
        this.funnelError = 'Error al cargar funnel.';
        this.funnelLoading = false;
      },
    });
  }

  private renderFunnelChart(): void {
    if (!this.funnelData || !this.funnelChartRef) return;
    this.funnelChart?.destroy();
    const stages = this.funnelData.stages;
    const max = stages[0]?.total || 1;
    const colors = stages.map(s => {
      if (s.stage === 'C90:WON')  return '#10b981';
      if (s.stage === 'C90:LOSE') return '#94a3b8';
      if (s.stage === 'C90:NEW')  return '#e8001d';
      return '#3b82f6';
    });
    this.funnelChart = new Chart(this.funnelChartRef.nativeElement, {
      type: 'bar',
      data: {
        labels: stages.map(s => s.label),
        datasets: [{
          label: 'Deals',
          data: stages.map(s => s.total),
          backgroundColor: colors,
          borderRadius: 5,
          borderSkipped: false,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const val = ctx.parsed.x ?? 0;
                const pct = max > 0 ? ((val / max) * 100).toFixed(1) : '0';
                const stage = stages[ctx.dataIndex];
                const avg = stage?.avg_fmt ? ` · prom. ${stage.avg_fmt}` : '';
                return ` ${val} deals (${pct}%)${avg}`;
              },
            },
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            max,
            grid: { color: '#f1f5f9' },
            ticks: { font: { family: 'Inter' } },
          },
          y: {
            grid: { display: false },
            ticks: { font: { family: 'Inter', size: 12 } },
          },
        },
      },
    });
  }

  applyMgFilter(): void {
    this.loadMegacable();
  }

  clearMgFilter(): void {
    this.mgDesde = '';
    this.mgHasta = '';
    this.loadMegacable();
  }

  loadMeta(): void {
    this.metaLoading = true;
    this.metaError = '';
    this.kpiSvc.getMetaInsights(
      this.metaDesde || undefined,
      this.metaHasta || undefined,
      this.metaLevel,
    ).subscribe({
      next: (data) => {
        this.metaData = data;
        this.metaLoading = false;
        if (this.chartsReady) setTimeout(() => this.renderMetaChart(), 0);
      },
      error: () => {
        this.metaError = 'Error al cargar datos de Meta Ads.';
        this.metaLoading = false;
      },
    });
  }

  applyMetaFilter(): void { this.loadMeta(); }

  clearMetaFilter(): void {
    this.metaDesde = '';
    this.metaHasta = '';
    this.metaLevel = 'campaign';
    this.loadMeta();
  }

  private renderMetaChart(): void {
    if (!this.metaData || !this.metaSpendChartRef) return;
    this.metaSpendChart?.destroy();
    const rows = this.metaData.rows.slice(0, 8);
    const labels = rows.map(r => r.campaign_name.length > 28 ? r.campaign_name.slice(0, 28) + '…' : r.campaign_name);
    this.metaSpendChart = new Chart(this.metaSpendChartRef.nativeElement, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Gasto (MXN)',
            data: rows.map(r => r.spend),
            backgroundColor: '#e8001d',
            borderRadius: 5,
            borderSkipped: false,
            yAxisID: 'ySpend',
          },
          {
            label: 'Convs. WhatsApp',
            data: rows.map(r => r.wa_conversaciones),
            backgroundColor: '#10b981',
            borderRadius: 5,
            borderSkipped: false,
            yAxisID: 'yConvs',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'top', labels: { font: { family: 'Inter', size: 12 } } } },
        scales: {
          ySpend: {
            type: 'linear',
            position: 'left',
            beginAtZero: true,
            grid: { color: '#f1f5f9' },
            ticks: { font: { family: 'Inter' }, callback: (v) => `$${v}` },
          },
          yConvs: {
            type: 'linear',
            position: 'right',
            beginAtZero: true,
            grid: { display: false },
            ticks: { font: { family: 'Inter' } },
          },
          x: { grid: { display: false }, ticks: { font: { family: 'Inter', size: 11 }, maxRotation: 30 } },
        },
      },
    });
  }

  loadUtm(): void {
    this.utmLoading = true;
    this.utmError = '';
    this.kpiSvc.getUtmData(this.utmDesde || undefined, this.utmHasta || undefined).subscribe({
      next: (data) => {
        this.utmData = data;
        this.utmLoading = false;
        if (this.chartsReady) setTimeout(() => this.renderUtmChart(), 0);
      },
      error: () => {
        this.utmError = 'Error al cargar datos de atribución.';
        this.utmLoading = false;
      },
    });
  }

  applyUtmFilter(): void { this.loadUtm(); }

  clearUtmFilter(): void {
    this.utmDesde = '';
    this.utmHasta = '';
    this.loadUtm();
  }

  private renderUtmChart(): void {
    if (!this.utmData || !this.utmFuenteChartRef) return;
    this.utmFuenteChart?.destroy();
    const fuentes = this.utmData.por_fuente.slice(0, 8);
    this.utmFuenteChart = new Chart(this.utmFuenteChartRef.nativeElement, {
      type: 'bar',
      data: {
        labels: fuentes.map(f => f.fuente),
        datasets: [
          {
            label: 'Leads',
            data: fuentes.map(f => f.total),
            backgroundColor: '#3b82f6',
            borderRadius: 5,
            borderSkipped: false,
          },
          {
            label: 'Ventas',
            data: fuentes.map(f => f.ventas),
            backgroundColor: '#10b981',
            borderRadius: 5,
            borderSkipped: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'top', labels: { font: { family: 'Inter', size: 12 } } } },
        scales: {
          y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: { family: 'Inter' } } },
          x: { grid: { display: false }, ticks: { font: { family: 'Inter' }, maxRotation: 30 } },
        },
      },
    });
  }

  loadMegacable(): void {
    this.megacableLoading = true;
    this.megacableError = '';
    this.kpiSvc.getMegacableData(this.mgDesde || undefined, this.mgHasta || undefined).subscribe({
      next: (data) => {
        this.megacableData = data;
        this.megacableLoading = false;
        if (this.chartsReady) setTimeout(() => this.renderMegacableCharts(), 0);
      },
      error: () => {
        this.megacableError = 'Error al cargar datos de Megacable.';
        this.megacableLoading = false;
      },
    });
  }

  applyFilter(): void {
    this.load(1);
    this.loadFunnel();
    this.loadMegacable();
  }

  clearFilter(): void {
    this.desde = '';
    this.hasta = '';
    this.stageFilter = '';
    this.search = '';
    this.load(1);
    this.loadFunnel();
    this.loadMegacable();
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

  private renderMegacableCharts(): void {
    if (!this.megacableData || !this.mgEstadoChartRef || !this.mgActorChartRef) return;
    this.mgEstadoChart?.destroy();
    this.mgActorChart?.destroy();

    this.mgEstadoChart = new Chart(this.mgEstadoChartRef.nativeElement, {
      type: 'doughnut',
      data: {
        labels: this.megacableData.por_estado.map(e => e.estado),
        datasets: [{
          data: this.megacableData.por_estado.map(e => e.cantidad),
          backgroundColor: ['#10b981', '#f59e0b', '#3b82f6', '#e8001d'],
          borderWidth: 2,
          borderColor: '#fff',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'right', labels: { font: { family: 'Inter', size: 12 }, padding: 12 } } },
        cutout: '60%',
      },
    });

    this.mgActorChart = new Chart(this.mgActorChartRef.nativeElement, {
      type: 'bar',
      data: {
        labels: this.megacableData.por_actor.map(a => a.actor.charAt(0).toUpperCase() + a.actor.slice(1)),
        datasets: [{
          label: 'Mensajes',
          data: this.megacableData.por_actor.map(a => a.cantidad),
          backgroundColor: ['#3b82f6', '#8b5cf6', '#10b981'],
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
