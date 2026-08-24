export interface Snapshot {
  city?: string | null;
  market_layer?: string | null;
  rate?: number | null;
  min_rate?: number | null;
  max_rate?: number | null;
  spread?: number | null;
  observation_count?: number;
  source_count?: number;
  freshest_at?: string | null;
  category_rates?: Record<string, number>;
}

export interface Source {
  username?: string;
  name?: string | null;
  active?: boolean;
  focused_categories?: string[] | null;
}

export interface Target {
  chat_id?: number;
  title?: string;
  username?: string | null;
  enabled?: boolean;
}

export interface Subscriber {
  chat_id?: number;
  first_name?: string | null;
  username?: string | null;
  city?: string | null;
  created_at?: string | null;
  subscribed?: boolean;
}

export interface DashboardState {
  service?: string;
  source_count?: number;
  target_count?: number;
  subscriber_count?: number;
  subscribers?: Subscriber[];
  observation_count?: number;
  snapshots?: Snapshot[];
  sources?: Source[];
  targets?: Target[];
  demo_data?: boolean;
  db_connected?: boolean;
  waiting_for_data?: boolean;
  checked_at?: string;
}

export interface MetalObservation {
  rate?: number | null;
  rate_role?: string | null;
  city?: string | null;
  source?: string | null;
  created_at?: string | null;
  product?: string | null;
}

export interface Metals {
  silver_kg?: MetalObservation[];
  dubai_lira?: MetalObservation[];
}

export interface TemplateVariable {
  key: string;
  label: string;
  example: string;
  description: string;
}

export interface Template {
  id?: number;
  name?: string;
  body?: string;
  destination?: string;
}

export interface TemplatesResponse {
  templates?: Template[];
  variables?: TemplateVariable[];
}
