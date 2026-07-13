import { Component, OnInit, AfterViewInit, OnDestroy, inject, ViewChild, ElementRef } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Chart, registerables } from 'chart.js';
import { KpiService, KpiData, KpiResumen, StageCount, Conversacion, MegacableData, MegacableResumen, MegacableConversacion, UtmData, MetaInsightsData, MetaInsightRow, FunnelData, FunnelTransicion, CostoResultado, CostoResumen, CostoDetalle, RoiData, RoiCampana } from '../../services/kpi.service';
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

  costoResumen: CostoResumen[] = [];
  costoDetalle: CostoDetalle[] = [];
  costoLoading = true;
  costoError = '';
  @ViewChild('costoChart') costoChartRef!: ElementRef<HTMLCanvasElement>;
  private costoChart?: Chart;

  @ViewChild('metaSpendChart') metaSpendChartRef!: ElementRef<HTMLCanvasElement>;
  private metaSpendChart?: Chart;

  utmData: UtmData | null = null;
  utmLoading = true;
  utmError = '';
  utmDesde = '';
  utmHasta = '';

  @ViewChild('utmFuenteChart') utmFuenteChartRef!: ElementRef<HTMLCanvasElement>;
  private utmFuenteChart?: Chart;

  roiData: RoiData | null = null;
  roiLoading = true;
  roiError = '';
  roiDesde = '';
  roiHasta = '';

  @ViewChild('roiChart') roiChartRef!: ElementRef<HTMLCanvasElement>;
  private roiChart?: Chart;

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
    this.loadCostoResultado();
    this.loadRoi();
    this.loadMeta();
    this.loadUtm();
    this.loadMegacable();
  }

  ngAfterViewInit(): void {
    this.chartsReady = true;
    if (this.resumen) this.renderCharts();
    if (this.funnelData) this.renderFunnelChart();
    if (this.costoResumen.length) this.renderCostoChart();
    if (this.roiData) this.renderRoiChart();
    if (this.metaData) this.renderMetaChart();
    if (this.utmData) this.renderUtmChart();
    if (this.megacableData) this.renderMegacableCharts();
  }

  ngOnDestroy(): void {
    this.stageChart?.destroy();
    this.msgChart?.destroy();
    this.funnelChart?.destroy();
    this.costoChart?.destroy();
    this.roiChart?.destroy();
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
          if (this.chartsReady) setTimeout(() => {
            this.renderCharts();
            if (this.funnelData) this.renderFunnelChart();
          }, 0);
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
    // Tasa de conversión acumulada vs el primer stage
    const convRates = stages.map(s => max > 0 ? +((s.total / max) * 100).toFixed(1) : 0);

    // Usamos barras verticales para compatibilidad natural con línea de tasa
    this.funnelChart = new Chart(this.funnelChartRef.nativeElement, {
      data: {
        labels: stages.map(s => s.label),
        datasets: [
          {
            type: 'bar' as const,
            label: 'Deals',
            data: stages.map(s => s.total),
            backgroundColor: colors,
            borderRadius: 5,
            borderSkipped: false,
            yAxisID: 'yDeals',
            order: 2,
          },
          {
            type: 'line' as const,
            label: '% conversión',
            data: convRates,
            borderColor: '#f59e0b',
            backgroundColor: 'rgba(245,158,11,0.08)',
            pointBackgroundColor: '#f59e0b',
            pointRadius: 4,
            tension: 0.3,
            yAxisID: 'yRate',
            order: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'top', labels: { font: { family: 'Inter', size: 12 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                if (ctx.dataset.label === '% conversión') {
                  return ` Conversión: ${ctx.parsed.y}%`;
                }
                const val = ctx.parsed.y ?? 0;
                const pct = max > 0 ? ((val / max) * 100).toFixed(1) : '0';
                const stage = stages[ctx.dataIndex];
                const avg = stage?.avg_fmt ? ` · prom. ${stage.avg_fmt}` : '';
                return ` ${val} deals (${pct}%)${avg}`;
              },
            },
          },
        },
        scales: {
          yDeals: {
            type: 'linear',
            position: 'left',
            beginAtZero: true,
            grid: { color: '#f1f5f9' },
            ticks: { font: { family: 'Inter' } },
          },
          yRate: {
            type: 'linear',
            position: 'right',
            beginAtZero: true,
            max: 100,
            grid: { display: false },
            ticks: { font: { family: 'Inter' }, callback: (v) => `${v}%` },
          },
          x: {
            grid: { display: false },
            ticks: { font: { family: 'Inter', size: 11 }, maxRotation: 30 },
          },
        },
      },
    });
  }

  loadCostoResultado(): void {
    this.costoLoading = true;
    this.costoError = '';
    this.kpiSvc.getCostoResultado(this.desde || undefined, this.hasta || undefined).subscribe({
      next: (data) => {
        this.costoResumen = data.resumen;
        this.costoDetalle = data.detalle;
        this.costoLoading = false;
        if (this.chartsReady) setTimeout(() => this.renderCostoChart(), 0);
      },
      error: () => {
        this.costoError = 'Error al cargar costos.';
        this.costoLoading = false;
      },
    });
  }

  private renderCostoChart(): void {
    if (!this.costoResumen.length || !this.costoChartRef) return;
    this.costoChart?.destroy();

    const labels  = this.costoResumen.map(r => r.stage_nombre);
    const costos  = this.costoResumen.map(r => r.costo_promedio_usd);
    const convs   = this.costoResumen.map(r => r.conversaciones);

    const colorMap: Record<string, string> = {
      'C90:WON':       '#10b981',
      'C90:LOSE':      '#94a3b8',
      'C90:NEW':       '#e8001d',
      'C90:PROSPECTO': '#6366f1',
    };
    const barColors = this.costoResumen.map(r =>
      colorMap[r.stage_id] ?? '#3b82f6'
    );

    this.costoChart = new Chart(this.costoChartRef.nativeElement, {
      data: {
        labels,
        datasets: [
          {
            type: 'bar' as const,
            label: 'Costo promedio (USD)',
            data: costos,
            backgroundColor: barColors,
            borderRadius: 5,
            yAxisID: 'yCosto',
            order: 2,
          },
          {
            type: 'line' as const,
            label: 'Conversaciones',
            data: convs,
            borderColor: '#f59e0b',
            backgroundColor: 'rgba(245,158,11,0.1)',
            pointBackgroundColor: '#f59e0b',
            tension: 0.3,
            yAxisID: 'yConvs',
            order: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'top', labels: { font: { family: 'Inter', size: 12 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                if (ctx.dataset.yAxisID === 'yCosto') {
                  const r = this.costoResumen[ctx.dataIndex];
                  return [
                    ` Costo prom: $${(ctx.parsed.y ?? 0).toFixed(4)} USD`,
                    ` Total: $${r.costo_total_usd.toFixed(4)} USD`,
                    ` Tokens entrada prom: ${r.avg_tokens_entrada.toLocaleString()}`,
                    ` Tokens salida prom: ${r.avg_tokens_salida.toLocaleString()}`,
                    ` Msgs bot: ${r.mensajes_bot}`,
                  ];
                }
                return ` ${ctx.parsed.y} conversaciones`;
              },
            },
          },
        },
        scales: {
          yCosto: {
            type: 'linear',
            position: 'left',
            beginAtZero: true,
            title: { display: true, text: 'USD promedio', font: { family: 'Inter', size: 11 } },
            grid: { color: '#f1f5f9' },
            ticks: {
              font: { family: 'Inter' },
              callback: (v) => `$${Number(v).toFixed(4)}`,
            },
          },
          yConvs: {
            type: 'linear',
            position: 'right',
            beginAtZero: true,
            title: { display: true, text: 'Conversaciones', font: { family: 'Inter', size: 11 } },
            grid: { display: false },
            ticks: { font: { family: 'Inter' } },
          },
          x: {
            grid: { display: false },
            ticks: { font: { family: 'Inter', size: 11 } },
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

  loadRoi(): void {
    this.roiLoading = true;
    this.roiError = '';
    this.kpiSvc.getRoiData(this.roiDesde || undefined, this.roiHasta || undefined).subscribe({
      next: (data) => {
        this.roiData = data;
        this.roiLoading = false;
        if (this.chartsReady) setTimeout(() => this.renderRoiChart(), 0);
      },
      error: () => {
        this.roiError = 'Error al cargar datos de ROI.';
        this.roiLoading = false;
      },
    });
  }

  applyRoiFilter(): void { this.loadRoi(); }

  clearRoiFilter(): void {
    this.roiDesde = '';
    this.roiHasta = '';
    this.loadRoi();
  }

  private renderRoiChart(): void {
    if (!this.roiData || !this.roiChartRef) return;
    this.roiChart?.destroy();
    const campanas = this.roiData.campanas.filter(c => c.spend > 0).slice(0, 8);
    if (!campanas.length) return;

    this.roiChart = new Chart(this.roiChartRef.nativeElement, {
      data: {
        labels: campanas.map(c => c.name),
        datasets: [
          {
            type: 'bar' as const,
            label: 'CPL (MXN)',
            data: campanas.map(c => c.cpl ?? 0),
            backgroundColor: '#3b82f6',
            borderRadius: 4,
            borderSkipped: false,
            yAxisID: 'yCpl',
            order: 2,
          },
          {
            type: 'bar' as const,
            label: 'CPA (MXN)',
            data: campanas.map(c => c.cpa ?? 0),
            backgroundColor: '#e8001d',
            borderRadius: 4,
            borderSkipped: false,
            yAxisID: 'yCpl',
            order: 2,
          },
          {
            type: 'line' as const,
            label: '% Conversión',
            data: campanas.map(c => c.pct_conv),
            borderColor: '#10b981',
            backgroundColor: 'rgba(16,185,129,0.1)',
            pointBackgroundColor: '#10b981',
            pointRadius: 4,
            tension: 0.3,
            yAxisID: 'yConv',
            order: 1,
          },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'top', labels: { font: { family: 'Inter', size: 12 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                if (ctx.dataset.label === '% Conversión') return ` Conv: ${ctx.parsed.x}%`;
                return ` ${ctx.dataset.label}: $${(ctx.parsed.x ?? 0).toFixed(2)} MXN`;
              },
            },
          },
        },
        scales: {
          yCpl: {
            axis: 'x',
            type: 'linear',
            position: 'bottom',
            beginAtZero: true,
            grid: { color: '#f1f5f9' },
            title: { display: true, text: 'MXN', font: { family: 'Inter', size: 11 } },
            ticks: { font: { family: 'Inter' }, callback: (v) => `$${v}` },
          },
          yConv: {
            axis: 'x',
            type: 'linear',
            position: 'top',
            beginAtZero: true,
            max: 100,
            grid: { display: false },
            title: { display: true, text: '% Conv.', font: { family: 'Inter', size: 11 } },
            ticks: { font: { family: 'Inter' }, callback: (v) => `${v}%` },
          },
          y: { grid: { display: false }, ticks: { font: { family: 'Inter', size: 11 } } },
        },
      },
    });
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
    const rows = this.metaData.rows.slice(0, 10);
    // Barras horizontales: nombres completos en eje Y sin truncar
    this.metaSpendChart = new Chart(this.metaSpendChartRef.nativeElement, {
      type: 'bar',
      data: {
        labels: rows.map(r => r.campaign_name),
        datasets: [
          {
            label: 'Gasto (MXN)',
            data: rows.map(r => r.spend),
            backgroundColor: '#e8001d',
            borderRadius: 4,
            borderSkipped: false,
            xAxisID: 'xSpend',
          },
          {
            label: 'Convs. WhatsApp',
            data: rows.map(r => r.wa_conversaciones),
            backgroundColor: '#10b981',
            borderRadius: 4,
            borderSkipped: false,
            xAxisID: 'xConvs',
          },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { position: 'top', labels: { font: { family: 'Inter', size: 12 } } } },
        scales: {
          xSpend: {
            axis: 'x',
            type: 'linear',
            position: 'bottom',
            beginAtZero: true,
            grid: { color: '#f1f5f9' },
            title: { display: true, text: 'Gasto MXN', font: { family: 'Inter', size: 11 } },
            ticks: { font: { family: 'Inter' }, callback: (v) => `$${v}` },
          },
          xConvs: {
            axis: 'x',
            type: 'linear',
            position: 'top',
            beginAtZero: true,
            grid: { display: false },
            title: { display: true, text: 'Convs. WhatsApp', font: { family: 'Inter', size: 11 } },
            ticks: { font: { family: 'Inter' } },
          },
          y: { grid: { display: false }, ticks: { font: { family: 'Inter', size: 11 } } },
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
    this.loadCostoResultado();
    this.loadMegacable();
  }

  clearFilter(): void {
    this.desde = '';
    this.hasta = '';
    this.stageFilter = '';
    this.search = '';
    this.load(1);
    this.loadFunnel();
    this.loadCostoResultado();
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

  // ── Chart info modal ─────────────────────────────────────────────────────

  activeInfo: string | null = null;

  readonly CHART_INFO: Record<string, {
    titulo: string;
    fuente: string;
    que_mide: string;
    como_leer: string[];
    alertas: string[];
  }> = {
    'kpi-cards': {
      titulo: 'KPI Cards — Resumen general',
      fuente: 'kpi_conversaciones + bitrix_eventos',
      que_mide: 'Métricas globales del periodo seleccionado: volumen, conversión, velocidad de respuesta y carga del equipo humano.',
      como_leer: [
        'Total conversaciones: leads que iniciaron contacto con el bot. Es el volumen bruto de la campaña.',
        'Conversiones (Venta): deals en stage C90:WON. La tasa = Ventas / Total. Meta recomendada: >10%.',
        'Tiempo 1ª respuesta: segundos entre el primer mensaje del cliente y la primera respuesta del bot. Debe ser <30s.',
        'Escalados a asesor: deals que llegaron a Escalamiento Humano o Prospecto. Representa la carga real del equipo.',
      ],
      alertas: [
        'Tiempo 1ª respuesta > 30s: posible problema de carga del servidor o debounce mal configurado.',
        'Tasa de conversión < 5%: revisar calidad de leads en Meta Ads o el guion del bot.',
        'Escalados > 60% del total: el bot está escalando demasiado; revisar nodo de objeciones.',
      ],
    },
    'funnel': {
      titulo: 'Funnel de conversión',
      fuente: 'bitrix_deal_timeline — una fila por deal, una columna por stage',
      que_mide: 'Cuántos deals pasaron por cada etapa del pipeline. Permite ver dónde se pierde el mayor volumen de leads.',
      como_leer: [
        'Barras verticales (azul/rojo/verde): número de deals que llegaron a cada stage. IA Porta es siempre el 100% de referencia.',
        'Línea amarilla: % de conversión acumulada respecto al primer stage (IA Porta).',
        'Tooltip al pasar el mouse: muestra cantidad de deals, % respecto a IA Porta y tiempo promedio en esa etapa.',
        'Barra verde = Venta (resultado exitoso). Barra gris = Caído (resultado perdido).',
      ],
      alertas: [
        'Rescate 1 > 50% de IA Porta: más de la mitad de los leads se enfrían. Revisar nodo de sondeo u oferta.',
        'Prospecto < 15%: el bot no está completando KPIs. Revisar nodo de cierre.',
        'Venta < 10% de Prospecto: los asesores no están convirtiendo. Revisar tiempo de contacto post-escalamiento.',
        'Tiempo promedio en Escalamiento > 2h: los asesores tardan demasiado en contactar al lead.',
      ],
    },
    'transiciones': {
      titulo: 'Transiciones de etapa recientes',
      fuente: 'bitrix_eventos (tipo sistema) — últimas 50 transiciones, ordenadas por fecha descendente',
      que_mide: 'El historial de movimientos de deals entre stages, con el contexto exacto del último mensaje del cliente y la última respuesta del bot en cada transición.',
      como_leer: [
        'Deal: ID del deal en Bitrix. Transición: movimiento "etapa anterior → etapa nueva".',
        'Duración en etapa: tiempo que el deal estuvo en la etapa anterior antes de moverse. "—" = primer movimiento sin historial.',
        'Último mensaje cliente / Última resp. Vera: contexto textual justo antes del cambio de stage.',
        'Asesor: ID numérico de Bitrix. Para ver el nombre, buscarlo en Bitrix24 > Empleados.',
      ],
      alertas: [
        'Deal aparece varias veces en secuencia (Rescate 1 → Caído → Rescate 1): posible loop de sincronización en job_bitrix_sync.',
        'Transición a Caído con último mensaje del cliente positivo ("qué promoción tienen"): el asesor no contactó al lead.',
        'Duración en IA Porta > 15 min: el bot está tardando demasiado en capturar KPIs. Auditar nodos de sondeo/cierre.',
      ],
    },
    'costo': {
      titulo: 'Costo del bot por resultado de conversación',
      fuente: 'bitrix_eventos — filas tipo "bot" con costo_usd registrado (disponible desde jun 2026)',
      que_mide: 'Cuánto gasta el LLM (en USD) en cada etapa del funnel. Permite identificar etapas costosas y optimizar el uso de tokens.',
      como_leer: [
        'Barras (eje izquierdo): costo promedio por mensaje del bot en esa etapa, en USD.',
        'Línea amarilla (eje derecho): número de conversaciones distintas con actividad del bot en esa etapa.',
        'Tooltip: muestra costo prom., total, tokens entrada/salida y mensajes del bot para esa etapa.',
        'Colores: Rojo = IA Porta, Morado = Prospecto, Verde = Venta, Gris = Caído, Azul = resto.',
      ],
      alertas: [
        'Costo en Rescate 2/3 > costo en Prospecto: el bot gasta más tokens en leads fríos que en los que convierten.',
        'Tokens entrada > 8,000 en etapas tempranas: el historial de conversación es muy extenso; considerar acortar la ventana de contexto.',
        'Muchas conversaciones en "Sin stage": mensajes del bot sin stage_id asignado (datos históricos previos a la activación del webhook de Bitrix).',
      ],
    },
    'stage': {
      titulo: 'Distribución por etapa (doughnut)',
      fuente: 'kpi_conversaciones — estado actual de cada conversación en el periodo',
      que_mide: 'Cómo están distribuidas las conversaciones activas del periodo entre los distintos stages del pipeline.',
      como_leer: [
        'Cada segmento representa un stage. La leyenda muestra: Etapa: N (X%) con cantidad y porcentaje.',
        'Verde = Venta (resultado exitoso). Gris = Caído. Rojo = IA Porta (aún en manos del bot).',
        'Un porcentaje alto en IA Porta es normal si el rango de fechas incluye conversaciones recientes.',
        'El tooltip al pasar el mouse muestra el número exacto de deals y el % del total.',
      ],
      alertas: [
        'Caído > 40%: alta tasa de abandono. Revisar calidad de leads o el guion del bot.',
        'Escalamiento Humano > 30%: muchos leads solicitan asesor antes de completar el flujo. Revisar nodo de objeciones.',
        'Venta + Prospecto < 10%: el funnel no está convirtiendo en el periodo analizado.',
      ],
    },
    'mensajes': {
      titulo: 'Mensajes por actor',
      fuente: 'kpi_conversaciones — total y promedio de mensajes por tipo de actor en el periodo',
      que_mide: 'Cuántos mensajes generó cada actor (cliente, bot, asesor) en total y en promedio por conversación.',
      como_leer: [
        'Barras (eje izquierdo): total de mensajes acumulados por actor en el periodo.',
        'Línea amarilla (eje derecho): promedio de mensajes por conversación para cada actor.',
        'Bot (Vera) con promedio > 5 msg/conv: conversaciones largas — revisar si el bot está siendo eficiente.',
        'Asesor Humano > 0: indica conversaciones donde el asesor tomó el control activamente.',
      ],
      alertas: [
        'Promedio del cliente > promedio del bot en más del doble: el cliente hace más preguntas de las que el bot responde — posibles lagunas en el guion.',
        'Promedio del asesor muy alto (> 10): los asesores están gestionando conversaciones largas; considerar mejorar el handoff del bot.',
      ],
    },
    'roi': {
      titulo: 'ROI de Campaña — CPL, CPA y % Conversión',
      fuente: 'Meta Marketing API (spend/leads WA) + JOIN kpi_conversaciones / leads (ventas) + bitrix_eventos (costo IA)',
      que_mide: 'Rentabilidad de la inversión publicitaria: cuánto cuesta cada lead (CPL), cuánto cuesta cada venta (CPA) y qué porcentaje de leads se convierten en ventas, desglosado por campaña.',
      como_leer: [
        'KPI Cards: Inversión Meta MXN (gasto total), CPL (inversión / leads WhatsApp), % Conversión (ventas / leads), CPA Meta (inversión / ventas).',
        'Gráfica horizontal: barras azul = CPL, barras rojas = CPA por campaña. Línea verde = % conversión (eje superior).',
        'Tabla: una fila por campaña con todos los indicadores. Badge verde = conversión ≥ 5%.',
        'Si Meta no está disponible, las cards de inversión muestran "—" pero las ventas siguen calculándose.',
      ],
      alertas: [
        'CPL > $150 MXN: costo por lead elevado para la campaña; considerar ajustar la segmentación en Meta.',
        'CPA > $1,000 MXN: el costo de adquisición por venta es alto; revisar conversión del asesor post-escalamiento.',
        '% Conversión < 3%: el funnel completo (anuncio → bot → asesor → venta) tiene fuga significativa.',
        'Campaña con muchos leads pero 0 ventas: el anuncio atrae leads de baja calidad; revisar la segmentación.',
      ],
    },
    'meta': {
      titulo: 'Meta Ads — Gasto vs Conversaciones WhatsApp',
      fuente: 'Meta Marketing API — cuenta Portabilidad 2 Callcom (act_3292969264212775)',
      que_mide: 'Métricas de inversión publicitaria: impresiones, clics, CTR, gasto y conversaciones WhatsApp iniciadas desde anuncios Click-to-WhatsApp.',
      como_leer: [
        'KPI Cards: Gasto total MXN, Impresiones, Clics (CTR), Convs. WhatsApp (CPL).',
        'Gráfica horizontal: barras rojas = gasto MXN (eje inferior), barras verdes = conversaciones WA (eje superior) por campaña/conjunto/anuncio.',
        'Tabla: detalle completo por entidad. CPC = costo por clic. CPM = costo por 1,000 impresiones.',
        'Cambiar el nivel (Campaña / Conjunto / Anuncio) para ver el desglose más granular.',
      ],
      alertas: [
        'CTR < 1%: el anuncio no está generando interés. Revisar creativos o segmentación.',
        'CPL WA > $200 MXN: el costo por conversación WhatsApp es elevado. Comparar con el CPA de ventas para evaluar.',
        'Conversaciones WA = 0 con gasto > 0: posible problema de atribución o el anuncio no tiene botón Click-to-WhatsApp activo.',
      ],
    },
    'utm': {
      titulo: 'Atribución UTM / Meta Ads',
      fuente: 'tabla leads — campos utm_source, utm_campaign, ad_id, ctwa_clid capturados en el webhook de WhatsApp',
      que_mide: 'Qué anuncios y campañas de Meta originaron los leads del bot, y qué porcentaje de esos leads se convirtió en venta.',
      como_leer: [
        '% con UTM capturado: qué tan completa es la atribución. <80% indica que hay leads que entraron sin pasar por un anuncio rastreable.',
        'Gráfica: leads y ventas por fuente UTM (Facebook, Instagram, etc.).',
        'Tabla por campaña: leads → prospectos → ventas → tasa de conversión por campaña.',
        'Tabla por anuncio (Ad ID): qué anuncio individual genera más leads y cuál convierte mejor.',
      ],
      alertas: [
        '% UTM capturado < 60%: muchos leads sin atribución. Verificar que los anuncios de Meta tengan parámetros UTM configurados.',
        'Campaña con tasa < 2%: mala conversión del embudo completo para ese anuncio. Pausar y revisar.',
        'Un Ad ID con muchos leads pero 0 ventas: el anuncio atrae curiosos, no compradores. Revisar el copy y la segmentación.',
      ],
    },
    'megacable': {
      titulo: 'Megacable — KPIs del agente conversacional',
      fuente: 'BD externa bot_megacable (147.79.78.75:5433) — tablas conversations, conversation_history, agent_runs',
      que_mide: 'Estado y desempeño del agente conversacional de Megacable: conversaciones activas, cerradas, escaladas y métricas de tiempo.',
      como_leer: [
        'KPI Cards: total conversaciones, cerradas vs abiertas, escaladas, tiempo de 1ª respuesta y cierre promedio.',
        'Doughnut de estado: distribución entre abierta / cerrada / escalada.',
        'Mensajes por actor: cuánto automatiza el bot vs. cuánto interviene el asesor humano.',
        'Tabla: historial de conversaciones recientes con timestamps de inicio, cierre y escalamiento.',
      ],
      alertas: [
        'Escaladas > 40%: el bot de Megacable escala demasiado; revisar los nodos de objeciones.',
        'T. 1ª respuesta > 60s: latencia alta del agente Megacable; revisar la infraestructura del servidor externo.',
        'T. cierre promedio > 30 min: conversaciones largas; el bot puede no estar cerrando eficientemente.',
      ],
    },
  };

  showInfo(id: string): void { this.activeInfo = id; }
  closeInfo(): void { this.activeInfo = null; }

  openDetail(id: string): void {
    this.router.navigate(['/conversation', id]);
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

    // 1. Doughnut con % y cantidad en leyenda y tooltip
    const totalStage = this.porStage.reduce((s, r) => s + r.cantidad, 0);
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
          legend: {
            position: 'right',
            labels: {
              font: { family: 'Inter', size: 12 },
              padding: 12,
              generateLabels: (chart) => {
                const ds = chart.data.datasets[0];
                const bg = ds.backgroundColor as string[];
                return (chart.data.labels as string[]).map((label, i) => {
                  const val = ds.data[i] as number;
                  const pct = totalStage > 0 ? ((val / totalStage) * 100).toFixed(1) : '0';
                  return {
                    text: `${label}: ${val} (${pct}%)`,
                    fillStyle: bg[i],
                    strokeStyle: '#fff',
                    lineWidth: 2,
                    hidden: false,
                    index: i,
                  };
                });
              },
            },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const val = ctx.parsed ?? 0;
                const pct = totalStage > 0 ? ((val / totalStage) * 100).toFixed(1) : '0';
                return ` ${val} deals (${pct}%)`;
              },
            },
          },
        },
        cutout: '60%',
      },
    });

    // 2. Mensajes por actor: totales + promedio por conversación
    if (this.resumen) {
      const totalConvs = this.resumen.total_conversaciones || 1;
      const msgTotales = [
        this.resumen.total_msgs_cliente,
        this.resumen.total_msgs_bot,
        this.resumen.total_msgs_humano,
      ];
      const msgPromedios = msgTotales.map(v => +(v / totalConvs).toFixed(1));

      this.msgChart = new Chart(this.msgChartRef.nativeElement, {
        type: 'bar',
        data: {
          labels: ['Cliente', 'Bot (Vera)', 'Asesor Humano'],
          datasets: [
            {
              label: 'Total mensajes',
              data: msgTotales,
              backgroundColor: ['#3b82f6', '#e8001d', '#10b981'],
              borderRadius: 6,
              borderSkipped: false,
              yAxisID: 'yTotal',
              order: 2,
            },
            {
              label: 'Prom. por conversación',
              data: msgPromedios,
              type: 'line' as const,
              borderColor: '#f59e0b',
              backgroundColor: 'rgba(245,158,11,0.12)',
              pointBackgroundColor: '#f59e0b',
              tension: 0.3,
              yAxisID: 'yProm',
              order: 1,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { position: 'top', labels: { font: { family: 'Inter', size: 12 } } },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  if (ctx.dataset.yAxisID === 'yProm') {
                    return ` Prom/conv: ${ctx.parsed.y}`;
                  }
                  return ` Total: ${ctx.parsed.y}`;
                },
              },
            },
          },
          scales: {
            yTotal: {
              type: 'linear',
              position: 'left',
              beginAtZero: true,
              grid: { color: '#f1f5f9' },
              title: { display: true, text: 'Total', font: { family: 'Inter', size: 11 } },
              ticks: { font: { family: 'Inter' } },
            },
            yProm: {
              type: 'linear',
              position: 'right',
              beginAtZero: true,
              grid: { display: false },
              title: { display: true, text: 'Promedio', font: { family: 'Inter', size: 11 } },
              ticks: { font: { family: 'Inter' } },
            },
            x: { grid: { display: false }, ticks: { font: { family: 'Inter' } } },
          },
        },
      });
    }
  }
}
