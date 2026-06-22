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
  resumen: string;
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

  triggerExport(): Observable<{ status: string; message: string }> {
    return this.http.post<{ status: string; message: string }>(
      '/api/admin/kpi-export',
      {},
      { headers: this.headers }
    );
  }
}
