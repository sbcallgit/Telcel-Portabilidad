import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';

export interface KpiResumen {
  total_conversaciones: number;
  conversiones: number;
  tasa_conversion: number;
  avg_primera_respuesta_segs: number;
  total_msgs_cliente: number;
  total_msgs_bot: number;
  total_msgs_humano: number;
  escalados: number;
}

export interface StageCount {
  stage: string;
  cantidad: number;
}

export interface Conversacion {
  id_conversacion: string;
  telefono: string;
  estado_actual: string;
  etapa: string;
  empleado: string;
  creado_el: string | null;
  cerrado_el: string | null;
  mensajes_cliente: number;
  mensajes_bot: number;
  mensajes_humano: number;
  tiempo_primera_respuesta_segs: number | null;
  tiempo_cierre_segs: number | null;
  resumen: string;
  motivo_escalacion: string;
}

export interface Paginacion {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface KpiData {
  resumen: KpiResumen;
  por_stage: StageCount[];
  conversaciones: Conversacion[];
  paginacion: Paginacion;
}

export interface MegacableResumen {
  total: number;
  cerradas: number;
  abiertas: number;
  escaladas: number;
  con_agente: number;
  avg_primera_resp_segs: number;
  avg_cierre_segs: number;
}

export interface MegacableConversacion {
  conversation_id: string;
  phone: string;
  estado: string;
  empleado: string | null;
  created_at: string | null;
  closed_at: string | null;
  escalated_at: string | null;
  msgs_cliente: number;
  msgs_bot: number;
  msgs_humano: number;
}

export interface MetaInsightRow {
  campaign_id: string;
  campaign_name: string;
  adset_name: string;
  ad_id: string;
  ad_name: string;
  impressions: number;
  reach: number;
  clicks: number;
  spend: number;
  cpc: number;
  cpm: number;
  ctr: number;
  wa_conversaciones: number;
  cpa_wa: number | null;
}

export interface MetaInsightsData {
  resumen: {
    total_spend: number;
    total_impressions: number;
    total_clicks: number;
    total_wa_convs: number;
    cpl_wa: number | null;
    avg_ctr: number;
  };
  rows: MetaInsightRow[];
  level: string;
}

export interface UtmResumen {
  total_leads: number;
  con_utm: number;
  pct_con_utm: number;
  total_ventas: number;
  ventas_atribuidas: number;
  pct_ventas_atrib: number;
}

export interface UtmCampana {
  campana: string;
  fuente: string;
  medio: string;
  total: number;
  ventas: number;
  prospectos: number;
  tasa: number;
}

export interface UtmAnuncio {
  ad_id: string;
  campana: string;
  total: number;
  ventas: number;
  tasa: number;
}

export interface UtmFuente {
  fuente: string;
  total: number;
  ventas: number;
  tasa: number;
}

export interface UtmData {
  resumen: UtmResumen;
  por_campana: UtmCampana[];
  por_anuncio: UtmAnuncio[];
  por_fuente: UtmFuente[];
}

export interface CostoResumen {
  stage_id: string;
  stage_nombre: string;
  conversaciones: number;
  mensajes_bot: number;
  costo_promedio_usd: number;
  costo_total_usd: number;
  avg_tokens_entrada: number;
  avg_tokens_salida: number;
}

export interface CostoDetalle {
  id_conversacion: string;
  deal_id: string;
  stage_id: string;
  stage_nombre: string;
  mensajes_bot: number;
  costo_total_usd: number;
  costo_promedio_usd: number;
  tokens_entrada: number;
  tokens_salida: number;
}

export interface CostoResultado {
  resumen: CostoResumen[];
  detalle: CostoDetalle[];
}

export interface FunnelStage {
  stage: string;
  label: string;
  total: number;
  avg_segs: number;
  avg_fmt: string;
}

export interface FunnelTransicion {
  id_conversacion: string;
  deal_id: string;
  telefono: string;
  fecha_evento: string | null;
  stage_anterior: string;
  stage_nuevo: string;
  duracion: string;
  ultimo_usuario: string;
  ultimo_bot: string;
  empleado_id: string;
}

export interface FunnelData {
  stages: FunnelStage[];
  transiciones: FunnelTransicion[];
}

export interface MegacableData {
  resumen: MegacableResumen;
  por_estado: { estado: string; cantidad: number }[];
  por_actor: { actor: string; cantidad: number }[];
  intents: { intent: string; cantidad: number }[];
  conversaciones: MegacableConversacion[];
}

export interface RoiCampana {
  campaign_id: string | null;
  name: string;
  spend: number;
  leads: number;
  ventas: number;
  cpl: number | null;
  cpa: number | null;
  pct_conv: number;
}

export interface RoiGlobal {
  total_spend_mxn: number;
  total_leads_wa: number;
  total_leads_reales: number;
  total_ventas: number;
  ai_cost_usd: number;
  cpl: number | null;
  cpa_meta: number | null;
  ai_costo_por_venta: number | null;
  pct_conversion: number;
  meta_disponible: boolean;
}

export interface RoiData {
  global: RoiGlobal;
  campanas: RoiCampana[];
}

export interface ConversationEvento {
  fecha_evento: string | null;
  tipo_actor: 'usuario' | 'bot' | 'humano' | 'sistema';
  texto: string;
  stage_id: string;
  stage_nombre: string;
  tokens_entrada: number | null;
  tokens_salida: number | null;
  costo_usd: number | null;
  stage_anterior: string | null;
  stage_anterior_nombre: string | null;
  duracion_en_stage_segs: number | null;
  duracion_formateada: string | null;
  empleado_id: string | null;
}

export interface ConversationTotales {
  costo_total_usd: number;
  tokens_entrada_total: number;
  tokens_salida_total: number;
  mensajes_bot: number;
  mensajes_usuario: number;
  mensajes_humano: number;
}

export interface ConversationDetail {
  summary: Conversacion | null;
  totales: ConversationTotales;
  eventos: ConversationEvento[];
}

@Injectable({ providedIn: 'root' })
export class KpiService {
  private http = inject(HttpClient);
  private auth = inject(AuthService);

  private get headers(): HttpHeaders {
    return new HttpHeaders({ 'Authorization': `Bearer ${this.auth.getToken()}` });
  }

  getData(page = 1, pageSize = 20, desde?: string, hasta?: string, stage?: string, buscar?: string): Observable<KpiData> {
    let params = new HttpParams()
      .set('page', page)
      .set('page_size', pageSize);
    if (desde) params = params.set('desde', desde);
    if (hasta) params = params.set('hasta', hasta);
    if (stage) params = params.set('stage', stage);
    if (buscar) params = params.set('buscar', buscar);

    return this.http.get<KpiData>('/api/admin/kpi-data', {
      headers: this.headers,
      params,
    });
  }

  getMetaInsights(desde?: string, hasta?: string, level = 'campaign'): Observable<MetaInsightsData> {
    let params = new HttpParams().set('level', level);
    if (desde) params = params.set('desde', desde);
    if (hasta) params = params.set('hasta', hasta);
    return this.http.get<MetaInsightsData>('/api/admin/meta-insights', { headers: this.headers, params });
  }

  getUtmData(desde?: string, hasta?: string): Observable<UtmData> {
    let params = new HttpParams();
    if (desde) params = params.set('desde', desde);
    if (hasta) params = params.set('hasta', hasta);
    return this.http.get<UtmData>('/api/admin/utm-data', { headers: this.headers, params });
  }

  getMegacableData(desde?: string, hasta?: string): Observable<MegacableData> {
    let params = new HttpParams();
    if (desde) params = params.set('desde', desde);
    if (hasta) params = params.set('hasta', hasta);
    return this.http.get<MegacableData>('/api/admin/megacable-data', {
      headers: this.headers,
      params,
    });
  }

  getCostoResultado(desde?: string, hasta?: string): Observable<CostoResultado> {
    let params = new HttpParams();
    if (desde) params = params.set('desde', desde);
    if (hasta) params = params.set('hasta', hasta);
    return this.http.get<CostoResultado>('/api/admin/costo-resultado', { headers: this.headers, params });
  }

  getFunnelData(desde?: string, hasta?: string): Observable<FunnelData> {
    let params = new HttpParams();
    if (desde) params = params.set('desde', desde);
    if (hasta) params = params.set('hasta', hasta);
    return this.http.get<FunnelData>('/api/admin/funnel-data', { headers: this.headers, params });
  }

  getRoiData(desde?: string, hasta?: string): Observable<RoiData> {
    let params = new HttpParams();
    if (desde) params = params.set('desde', desde);
    if (hasta) params = params.set('hasta', hasta);
    return this.http.get<RoiData>('/api/admin/roi-data', { headers: this.headers, params });
  }

  getConversationDetail(id: string): Observable<ConversationDetail> {
    return this.http.get<ConversationDetail>(`/api/admin/conversation/${id}`, { headers: this.headers });
  }

  triggerExport(): Observable<{ status: string; message: string }> {
    return this.http.post<{ status: string; message: string }>(
      '/api/admin/kpi-export',
      {},
      { headers: this.headers }
    );
  }
}
